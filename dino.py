#!/usr/bin/env python3
"""
Terminal Dino Runner (Chrome offline style)
Controls:
  space / ↑ : jump
  ↓         : duck (hold)
  p         : pause
  q         : quit
"""

import curses
import random
import time

GROUND_Y = 18
WIDTH = 70
HEIGHT = 24


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class DinoGame:
    def __init__(self):
        self.score = 0
        self.best = 0
        self.speed = 1.0
        self.tick = 0.04
        # Physics in rows/second and rows/second² for stable jump arcs.
        self.gravity = 55.0
        self.jump_velocity = -18.0

        self.player_x = 8
        self.player_y = float(GROUND_Y)
        self.player_vy = 0.0
        self.ducking = False

        self.obstacles = []  # [{x, w, h, kind}]
        self.spawn_timer = 0

        self.game_over = False
        self.paused = False

    def reset(self):
        self.best = max(self.best, self.score)
        self.score = 0
        self.speed = 1.0
        self.player_y = float(GROUND_Y)
        self.player_vy = 0.0
        self.ducking = False
        self.obstacles.clear()
        self.spawn_timer = 20
        self.game_over = False
        self.paused = False

    def is_on_ground(self):
        return self.player_y >= GROUND_Y - 1e-6

    def jump(self):
        if self.is_on_ground():
            self.player_vy = self.jump_velocity

    def set_duck(self, yes):
        self.ducking = yes and self.is_on_ground()

    def player_box(self):
        if self.ducking and self.is_on_ground():
            w, h = 4, 1
            y = GROUND_Y
        else:
            w, h = 3, 2
            y = int(round(self.player_y)) - 1
        return self.player_x, y, w, h

    def spawn_obstacle(self):
        # Mostly cacti, sometimes low-flying bird
        if random.random() < 0.22 and self.score > 200:
            h = 1
            y = GROUND_Y - random.choice([3, 4])
            self.obstacles.append({"x": WIDTH - 2, "w": 4, "h": h, "y": y, "kind": "bird"})
        else:
            h = random.choice([2, 3])
            w = random.choice([2, 3, 4])
            y = GROUND_Y - h + 1
            self.obstacles.append({"x": WIDTH - 2, "w": w, "h": h, "y": y, "kind": "cactus"})

        base = max(18, 46 - int(self.speed * 6))
        jitter = random.randint(-8, 8)
        self.spawn_timer = max(10, base + jitter)

    @staticmethod
    def intersects(a, b):
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by

    def update(self):
        if self.game_over or self.paused:
            return

        # physics (dt-based integration)
        dt = self.tick
        self.player_vy += self.gravity * dt
        self.player_y += self.player_vy * dt

        # Keep player in visible area and on the ground.
        if self.player_y < 0:
            self.player_y = 0.0
            self.player_vy = max(0.0, self.player_vy)
        if self.player_y > GROUND_Y:
            self.player_y = float(GROUND_Y)
            self.player_vy = 0.0

        # obstacles movement
        step = self.speed
        for o in self.obstacles:
            o["x"] -= step
        self.obstacles = [o for o in self.obstacles if o["x"] + o["w"] > 0]

        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self.spawn_obstacle()

        # difficulty ramp
        self.score += int(1 + self.speed)
        self.speed = clamp(1.0 + self.score / 600.0, 1.0, 5.0)

        # collisions
        pbox = self.player_box()
        for o in self.obstacles:
            obox = (int(o["x"]), o["y"], o["w"], o["h"])
            if self.intersects(pbox, obox):
                self.game_over = True
                self.best = max(self.best, self.score)
                break


def draw(stdscr, g: DinoGame):
    stdscr.erase()
    stdscr.addstr(0, 2, "DINO RUNNER")
    stdscr.addstr(1, 2, f"Score: {g.score}")
    stdscr.addstr(1, 20, f"Best: {g.best}")
    stdscr.addstr(1, 36, f"Speed: {g.speed:.2f}")

    # sky / ground
    for x in range(WIDTH):
        stdscr.addstr(GROUND_Y + 1, x, "_")

    # little clouds
    for i in range(3):
        cx = int((WIDTH - (g.score // (20 + i * 5)) % (WIDTH + 20)) - 10)
        cy = 3 + i * 2
        if 0 <= cx < WIDTH - 3:
            stdscr.addstr(cy, cx, "~~~")

    # player
    px, py, pw, ph = g.player_box()
    if g.ducking and g.is_on_ground():
        sprite = "__o>"
        if 0 <= py < HEIGHT:
            stdscr.addstr(py, px, sprite[:pw])
    else:
        if 0 <= py < HEIGHT:
            stdscr.addstr(py, px, " o ")
        if 0 <= py + 1 < HEIGHT:
            stdscr.addstr(py + 1, px, "/|\\")

    # obstacles
    for o in g.obstacles:
        ox = int(o["x"])
        if ox < -6 or ox >= WIDTH:
            continue

        if o["kind"] == "cactus":
            for dy in range(o["h"]):
                y = o["y"] + dy
                if 0 <= y < HEIGHT:
                    stdscr.addstr(y, ox, "|" * o["w"])
        else:
            y = o["y"]
            if 0 <= y < HEIGHT:
                stdscr.addstr(y, ox, "<^^>")

    stdscr.addstr(HEIGHT - 2, 2, "space/↑ jump  ↓ duck  p pause  q quit")

    if g.paused:
        stdscr.addstr(HEIGHT // 2, WIDTH // 2 - 4, "PAUSED")

    if g.game_over:
        stdscr.addstr(HEIGHT // 2 - 1, WIDTH // 2 - 5, "GAME OVER")
        stdscr.addstr(HEIGHT // 2, WIDTH // 2 - 12, "Press r to restart or q to quit")

    stdscr.refresh()


def run(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    g = DinoGame()
    g.spawn_timer = 25

    while True:
        key = stdscr.getch()

        if key == ord("q"):
            break

        if g.game_over:
            if key == ord("r"):
                g.reset()
            draw(stdscr, g)
            time.sleep(g.tick)
            continue

        if key == ord("p"):
            g.paused = not g.paused

        if key in (ord(" "), curses.KEY_UP):
            g.jump()

        g.set_duck(key == curses.KEY_DOWN)

        g.update()
        draw(stdscr, g)
        time.sleep(g.tick)


def main():
    curses.wrapper(run)


if __name__ == "__main__":
    main()
