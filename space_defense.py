#!/usr/bin/env python3
"""
Space Defense (ASCII Shooter)

Controls:
  ← / A : move left
  → / D : move right
  SPACE : shoot
  B     : bomb (if available)
  Q     : quit
  R     : restart (on game over)
"""

import curses
import random
import time
from dataclasses import dataclass, field


@dataclass
class Player:
    x: int
    lives: int = 3
    last_shot_time: float = 0.0
    shield_charges: int = 0
    bombs: int = 0


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
class PowerUp:
    x: int
    y: float
    kind: str  # shield | bomb
    speed: float = 0.35


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
    powerups: list = field(default_factory=list)
    combo_multiplier: int = 1
    last_kill_time: float = 0.0
    game_over: bool = False
    boss_level_spawned: int = 0


FIRE_COOLDOWN = 0.2
FPS = 30
FRAME_TIME = 1.0 / FPS

ENEMY_POINTS = {"basic": 10, "fast": 20, "tank": 50, "boss": 300}
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
    return max(0.16, 1.0 - (level - 1) * 0.08)


def enemy_speed_multiplier(level: int) -> float:
    return 1.0 + (level - 1) * 0.10


def pick_enemy_type(level: int):
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
    curses.init_pair(6, curses.COLOR_BLUE, -1)    # shield


def can_shoot(player: Player, now: float) -> bool:
    return now - player.last_shot_time >= FIRE_COOLDOWN


def add_bullet(gs: GameState, player: Player):
    gs.bullets.append(Bullet(x=player.x, y=gs.height - 4))


def spawn_enemy(gs: GameState):
    kind, hp, base_speed = pick_enemy_type(gs.level)
    x = random.randint(2, gs.width - 3)
    speed = base_speed * enemy_speed_multiplier(gs.level)
    gs.enemies.append(Enemy(x=x, y=2.0, hp=hp, kind=kind, speed=speed))


def maybe_spawn_boss(gs: GameState):
    if gs.level >= 5 and gs.level % 5 == 0 and gs.boss_level_spawned != gs.level:
        gs.boss_level_spawned = gs.level
        gs.enemies.append(
            Enemy(x=gs.width // 2, y=2.0, hp=20, kind="boss", speed=0.16 * enemy_speed_multiplier(gs.level))
        )


def maybe_spawn_powerup(gs: GameState):
    if random.random() < 0.004:
        kind = "shield" if random.random() < 0.6 else "bomb"
        gs.powerups.append(PowerUp(x=random.randint(2, gs.width - 3), y=2.0, kind=kind))


def update_bullets(gs: GameState, dt: float):
    for b in gs.bullets:
        b.y -= 25.0 * dt
    gs.bullets = [b for b in gs.bullets if b.y >= 2]


def update_enemies(gs: GameState, dt: float):
    for e in gs.enemies:
        e.y += e.speed * 12.0 * dt


def update_powerups(gs: GameState, dt: float):
    for p in gs.powerups:
        p.y += p.speed * 12.0 * dt
    gs.powerups = [p for p in gs.powerups if p.y < gs.height - 2]


def update_explosions(gs: GameState, dt: float):
    for ex in gs.explosions:
        ex.ttl -= dt
    gs.explosions = [ex for ex in gs.explosions if ex.ttl > 0]


def enemy_hitbox(e: Enemy):
    ex, ey = e.x, int(round(e.y))
    if e.kind == "boss":
        return ex - 2, ey, 5, 2
    return ex, ey, 1, 1


def intersects(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def apply_player_hit(gs: GameState, player: Player):
    if player.shield_charges > 0:
        player.shield_charges -= 1
        return
    player.lives -= 1
    gs.enemies.clear()
    gs.bullets.clear()
    gs.explosions.clear()
    if player.lives <= 0:
        gs.game_over = True


def detonate_bomb(gs: GameState, player: Player):
    if player.bombs <= 0:
        return
    player.bombs -= 1
    kills = len(gs.enemies)
    for e in gs.enemies:
        ex, ey = e.x, int(round(e.y))
        gs.explosions.append(Explosion(x=ex, y=ey, ttl=0.18))
    gs.enemies.clear()
    gs.score += kills * 15


def handle_collisions(gs: GameState, player: Player, now: float):
    bullets_to_remove = set()
    enemies_to_remove = set()

    for bi, b in enumerate(gs.bullets):
        bx, by = b.x, int(round(b.y))
        brect = (bx, by, 1, 1)
        for ei, e in enumerate(gs.enemies):
            ex, ey, ew, eh = enemy_hitbox(e)
            erect = (ex, ey, ew, eh)
            if intersects(brect, erect):
                bullets_to_remove.add(bi)
                e.hp -= 1
                if e.hp <= 0:
                    enemies_to_remove.add(ei)
                    gs.explosions.append(Explosion(x=e.x, y=ey))
                    gs.combo_multiplier = 2 if now - gs.last_kill_time <= 1.0 else 1
                    gs.last_kill_time = now
                    gs.score += ENEMY_POINTS[e.kind] * gs.combo_multiplier
                break

    gs.bullets = [b for i, b in enumerate(gs.bullets) if i not in bullets_to_remove]
    gs.enemies = [e for i, e in enumerate(gs.enemies) if i not in enemies_to_remove]

    player_y = gs.height - 3

    # Enemy reaches player line
    for e in gs.enemies:
        _, ey, _, eh = enemy_hitbox(e)
        if ey + eh - 1 >= player_y:
            apply_player_hit(gs, player)
            break

    # Powerup pickup
    powerups_left = []
    for p in gs.powerups:
        if int(round(p.y)) >= player_y and abs(p.x - player.x) <= 1:
            if p.kind == "shield":
                player.shield_charges = min(3, player.shield_charges + 1)
            else:
                player.bombs = min(3, player.bombs + 1)
        else:
            powerups_left.append(p)
    gs.powerups = powerups_left


def draw_borders(stdscr, gs: GameState):
    w, h = gs.width, gs.height
    stdscr.addstr(0, 0, "+" + "-" * (w - 2) + "+")
    for y in range(1, h - 1):
        stdscr.addstr(y, 0, "|")
        stdscr.addstr(y, w - 1, "|")
    stdscr.addstr(h - 1, 0, "+" + "-" * (w - 2) + "+")


def render(stdscr, gs: GameState, player: Player, highscore: int, hardcore: bool):
    stdscr.erase()
    draw_borders(stdscr, gs)

    hearts = "♥" * max(0, player.lives)
    hud = (
        f" SCORE: {gs.score:05d} HIGH: {highscore:05d} LIVES: {hearts:<3} "
        f"LVL: {gs.level} SH:{player.shield_charges} B:{player.bombs}"
    )
    stdscr.addstr(1, 2, hud[: gs.width - 4], curses.color_pair(4))
    if hardcore:
        stdscr.addstr(2, 2, "HARDCORE", curses.color_pair(2))

    # Enemies
    for e in gs.enemies:
        ex, ey = e.x, int(round(e.y))
        if e.kind == "boss":
            if 1 < ey < gs.height - 3 and 3 < ex < gs.width - 4:
                stdscr.addstr(ey, ex - 2, "[MMM]", curses.color_pair(2))
                stdscr.addstr(ey + 1, ex - 2, f" {e.hp:02d} ", curses.color_pair(2))
        else:
            if 1 < ey < gs.height - 2 and 1 < ex < gs.width - 1:
                ch = "V" if e.kind != "tank" else "W"
                stdscr.addstr(ey, ex, ch, curses.color_pair(2))

    # Bullets
    for b in gs.bullets:
        x, y = b.x, int(round(b.y))
        if 1 < y < gs.height - 2 and 1 < x < gs.width - 1:
            stdscr.addstr(y, x, "|", curses.color_pair(3))

    # Powerups
    for p in gs.powerups:
        x, y = p.x, int(round(p.y))
        if 1 < y < gs.height - 2 and 1 < x < gs.width - 1:
            ch = "#" if p.kind == "shield" else "B"
            col = curses.color_pair(6) if p.kind == "shield" else curses.color_pair(3)
            stdscr.addstr(y, x, ch, col)

    for ex in gs.explosions:
        if 1 < ex.y < gs.height - 2 and 1 < ex.x < gs.width - 1:
            stdscr.addstr(ex.y, ex.x, "*", curses.color_pair(5))

    py = gs.height - 3
    if player.shield_charges > 0:
        stdscr.addstr(py, player.x - 1, "(^)", curses.color_pair(6))
    else:
        stdscr.addstr(py, player.x, "^", curses.color_pair(1))

    footer = " ←/A →/D Move  SPACE Shoot  B Bomb  Q Quit "
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


def mode_menu(stdscr):
    stdscr.nodelay(False)
    hardcore = False
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        cx = w // 2
        stdscr.addstr(4, max(2, cx - 7), "SPACE DEFENSE")
        stdscr.addstr(6, max(2, cx - 15), "ENTER: Start game")
        stdscr.addstr(7, max(2, cx - 15), f"H: Toggle Hardcore [{'ON' if hardcore else 'OFF'}]")
        stdscr.addstr(8, max(2, cx - 15), "Q: Quit")
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord('q'), ord('Q')):
            return None
        if key in (ord('h'), ord('H')):
            hardcore = not hardcore
        if key in (10, 13, curses.KEY_ENTER):
            return hardcore


def reset_round(width: int, height: int, hardcore: bool):
    gs = GameState(width=width, height=height)
    player = Player(x=width // 2, lives=(1 if hardcore else 3))
    return gs, player


def game(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    init_colors()

    mode = mode_menu(stdscr)
    if mode is None:
        return
    hardcore = mode

    stdscr.nodelay(True)
    h, w = stdscr.getmaxyx()
    width = max(50, min(100, w - 1))
    height = max(20, min(35, h - 1))

    gs, player = reset_round(width, height, hardcore)
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
                gs, player = reset_round(width, height, hardcore)
                spawn_cd = 0.0
                last = time.time()
            render(stdscr, gs, player, highscore, hardcore)
            time.sleep(FRAME_TIME)
            continue

        if key in (curses.KEY_LEFT, ord("a"), ord("A")):
            player.x = max(2, player.x - 1)
        elif key in (curses.KEY_RIGHT, ord("d"), ord("D")):
            player.x = min(width - 3, player.x + 1)
        elif key == ord(" "):
            if can_shoot(player, now):
                add_bullet(gs, player)
                player.last_shot_time = now
        elif key in (ord("b"), ord("B")):
            detonate_bomb(gs, player)

        gs.level = compute_level(gs.score)
        maybe_spawn_boss(gs)
        update_bullets(gs, dt)
        update_enemies(gs, dt)
        update_powerups(gs, dt)
        update_explosions(gs, dt)
        maybe_spawn_powerup(gs)

        spawn_cd -= dt
        if spawn_cd <= 0.0:
            spawn_enemy(gs)
            spawn_cd = spawn_interval(gs.level)

        handle_collisions(gs, player, now)

        if gs.score > highscore:
            highscore = gs.score
            save_highscore(highscore)

        render(stdscr, gs, player, highscore, hardcore)

        elapsed = time.time() - now
        sleep_for = FRAME_TIME - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)


def main():
    curses.wrapper(game)


if __name__ == "__main__":
    main()
