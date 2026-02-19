#!/usr/bin/env python3
"""
Space Defense (ASCII Shooter)

Controls:
  ← / A : move left
  → / D : move right
  SPACE : shoot
  Q     : quit
  R     : restart (on game over)

Run:
  python3 space_defense.py
"""

import curses
import random
import time
from dataclasses import dataclass, field


# -----------------------------
# Data structures
# -----------------------------

@dataclass
class Player:
    x: int
    lives: int = 3
    last_shot_time: float = 0.0


@dataclass
class Bullet:
    x: int
    y: float


@dataclass
class Enemy:
    x: int
    y: float
    hp: int
    kind: str
    speed: float


@dataclass
class Explosion:
    x: int
    y: int
    ttl: float = 0.12


@dataclass
class GameState:
    width: int
    height: int
    score: int = 0
    level: int = 1
    enemies: list = field(default_factory=list)
    bullets: list = field(default_factory=list)
    explosions: list = field(default_factory=list)
    combo_multiplier: int = 1
    last_kill_time: float = 0.0
    game_over: bool = False


# -----------------------------
# Gameplay constants
# -----------------------------

FIRE_COOLDOWN = 0.2
FPS = 30
FRAME_TIME = 1.0 / FPS

ENEMY_POINTS = {
    "basic": 10,
    "fast": 20,
    "tank": 50,
}

ENEMY_TYPES = [
    ("basic", 1, 0.35),
    ("fast", 1, 0.60),
    ("tank", 3, 0.24),
]


def load_highscore(path="/tmp/.space_defense_highscore"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip() or "0")
    except Exception:
        return 0


def save_highscore(score, path="/tmp/.space_defense_highscore"):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(score))
    except Exception:
        pass


def compute_level(score: int) -> int:
    return max(1, score // 500 + 1)


def spawn_interval(level: int) -> float:
    # Faster spawns as level increases
    return max(0.18, 1.0 - (level - 1) * 0.08)


def enemy_speed_multiplier(level: int) -> float:
    return 1.0 + (level - 1) * 0.10


def pick_enemy_type(level: int):
    # Weighted by level progression
    if level < 3:
        weights = [0.85, 0.15, 0.00]
    elif level < 6:
        weights = [0.65, 0.25, 0.10]
    else:
        weights = [0.45, 0.35, 0.20]

    r = random.random()
    acc = 0.0
    for i, w in enumerate(weights):
        acc += w
        if r <= acc:
            return ENEMY_TYPES[i]
    return ENEMY_TYPES[0]


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)   # player
    curses.init_pair(2, curses.COLOR_RED, -1)     # enemy
    curses.init_pair(3, curses.COLOR_YELLOW, -1)  # bullet
    curses.init_pair(4, curses.COLOR_CYAN, -1)    # hud
    curses.init_pair(5, curses.COLOR_MAGENTA, -1) # explosion


def can_shoot(player: Player, now: float) -> bool:
    return now - player.last_shot_time >= FIRE_COOLDOWN


def add_bullet(gs: GameState, player: Player):
    gs.bullets.append(Bullet(x=player.x, y=gs.height - 4))


def spawn_enemy(gs: GameState):
    kind, hp, base_speed = pick_enemy_type(gs.level)
    # Keep away from borders
    x = random.randint(2, gs.width - 3)
    speed = base_speed * enemy_speed_multiplier(gs.level)
    gs.enemies.append(Enemy(x=x, y=2.0, hp=hp, kind=kind, speed=speed))


def update_bullets(gs: GameState, dt: float):
    for b in gs.bullets:
        b.y -= 25.0 * dt
    gs.bullets = [b for b in gs.bullets if b.y >= 2]


def update_enemies(gs: GameState, dt: float):
    for e in gs.enemies:
        e.y += e.speed * 12.0 * dt


def update_explosions(gs: GameState, dt: float):
    for ex in gs.explosions:
        ex.ttl -= dt
    gs.explosions = [ex for ex in gs.explosions if ex.ttl > 0]


def handle_collisions(gs: GameState, player: Player, now: float):
    bullets_to_remove = set()
    enemies_to_remove = set()

    # Bullet-enemy collisions (grid-cell overlap)
    for bi, b in enumerate(gs.bullets):
        bx, by = b.x, int(round(b.y))
        for ei, e in enumerate(gs.enemies):
            ex, ey = e.x, int(round(e.y))
            if bx == ex and by == ey:
                bullets_to_remove.add(bi)
                e.hp -= 1
                if e.hp <= 0:
                    enemies_to_remove.add(ei)
                    gs.explosions.append(Explosion(x=ex, y=ey))

                    # Combo: kill within 1 second -> x2
                    gs.combo_multiplier = 2 if now - gs.last_kill_time <= 1.0 else 1
                    gs.last_kill_time = now
                    gs.score += ENEMY_POINTS[e.kind] * gs.combo_multiplier
                break

    gs.bullets = [b for i, b in enumerate(gs.bullets) if i not in bullets_to_remove]
    gs.enemies = [e for i, e in enumerate(gs.enemies) if i not in enemies_to_remove]

    # Enemy reaches player row / bottom -> lose life
    hit = False
    player_y = gs.height - 3
    for e in gs.enemies:
        ey = int(round(e.y))
        if ey >= player_y:
            hit = True
            break

    if hit:
        player.lives -= 1
        gs.enemies.clear()
        gs.bullets.clear()
        gs.explosions.clear()
        if player.lives <= 0:
            gs.game_over = True


def draw_borders(stdscr, gs: GameState):
    w = gs.width
    h = gs.height
    stdscr.addstr(0, 0, "+" + "-" * (w - 2) + "+")
    for y in range(1, h - 1):
        stdscr.addstr(y, 0, "|")
        stdscr.addstr(y, w - 1, "|")
    stdscr.addstr(h - 1, 0, "+" + "-" * (w - 2) + "+")


def render(stdscr, gs: GameState, player: Player, highscore: int):
    stdscr.erase()
    draw_borders(stdscr, gs)

    hearts = "♥" * max(0, player.lives)
    hud = f" SCORE: {gs.score:05d}  HIGH: {highscore:05d}  LIVES: {hearts:<3}  LEVEL: {gs.level} "
    stdscr.addstr(1, 2, hud[: gs.width - 4], curses.color_pair(4))

    # Enemies
    for e in gs.enemies:
        x, y = e.x, int(round(e.y))
        if 1 < y < gs.height - 2 and 1 < x < gs.width - 1:
            ch = "V" if e.kind != "tank" else "W"
            stdscr.addstr(y, x, ch, curses.color_pair(2))

    # Bullets
    for b in gs.bullets:
        x, y = b.x, int(round(b.y))
        if 1 < y < gs.height - 2 and 1 < x < gs.width - 1:
            stdscr.addstr(y, x, "|", curses.color_pair(3))

    # Explosions
    for ex in gs.explosions:
        if 1 < ex.y < gs.height - 2 and 1 < ex.x < gs.width - 1:
            stdscr.addstr(ex.y, ex.x, "*", curses.color_pair(5))

    # Player
    py = gs.height - 3
    stdscr.addstr(py, player.x, "^", curses.color_pair(1))

    footer = " ←/A →/D Move   SPACE Shoot   Q Quit "
    stdscr.addstr(gs.height - 2, 2, footer[: gs.width - 4])

    if gs.combo_multiplier > 1 and time.time() - gs.last_kill_time <= 1.0:
        stdscr.addstr(2, gs.width - 14, "COMBO x2!", curses.color_pair(3))

    if gs.game_over:
        msg1 = "GAME OVER"
        msg2 = f"Score: {gs.score}   Level: {gs.level}"
        msg3 = "Press R to restart or Q to quit"
        cx = gs.width // 2
        stdscr.addstr(gs.height // 2 - 1, max(2, cx - len(msg1) // 2), msg1, curses.color_pair(2))
        stdscr.addstr(gs.height // 2, max(2, cx - len(msg2) // 2), msg2)
        stdscr.addstr(gs.height // 2 + 1, max(2, cx - len(msg3) // 2), msg3)

    stdscr.refresh()


def game(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)
    init_colors()

    h, w = stdscr.getmaxyx()
    width = max(50, min(100, w - 1))
    height = max(20, min(35, h - 1))

    gs = GameState(width=width, height=height)
    player = Player(x=width // 2)
    highscore = load_highscore()

    last = time.time()
    spawn_cd = 0.0

    while True:
        now = time.time()
        dt = now - last
        last = now

        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            break

        if gs.game_over:
            if key in (ord("r"), ord("R")):
                gs = GameState(width=width, height=height)
                player = Player(x=width // 2)
                spawn_cd = 0.0
                last = time.time()
            render(stdscr, gs, player, highscore)
            time.sleep(FRAME_TIME)
            continue

        # Input
        if key in (curses.KEY_LEFT, ord("a"), ord("A")):
            player.x = max(2, player.x - 1)
        elif key in (curses.KEY_RIGHT, ord("d"), ord("D")):
            player.x = min(width - 3, player.x + 1)
        elif key == ord(" "):
            if can_shoot(player, now):
                add_bullet(gs, player)
                player.last_shot_time = now

        # Update
        gs.level = compute_level(gs.score)
        update_bullets(gs, dt)
        update_enemies(gs, dt)
        update_explosions(gs, dt)

        spawn_cd -= dt
        if spawn_cd <= 0.0:
            spawn_enemy(gs)
            spawn_cd = spawn_interval(gs.level)

        handle_collisions(gs, player, now)

        if gs.score > highscore:
            highscore = gs.score
            save_highscore(highscore)

        render(stdscr, gs, player, highscore)

        # Target frame rate
        elapsed = time.time() - now
        sleep_for = FRAME_TIME - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)


def main():
    curses.wrapper(game)


if __name__ == "__main__":
    main()
