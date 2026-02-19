#!/usr/bin/env python3
"""
Terminal Tetris (curses)
Controls:
  ←/→ : move
  ↓   : soft drop
  ↑   : rotate
  space: hard drop
  p   : pause
  q   : quit

Options:
  --start-level N       Start at level N (default 1)
  --speed-multiplier X  Global speed factor (default 1.0, higher=faster)
  --fixed-level         Keep level constant (no level-up)
"""

import argparse
import curses
import random
import time

BOARD_W = 10
BOARD_H = 20
TICK_START = 0.5
MIN_TICK = 0.08

SHAPES = {
    "I": [[1, 1, 1, 1]],
    "O": [[1, 1], [1, 1]],
    "T": [[0, 1, 0], [1, 1, 1]],
    "S": [[0, 1, 1], [1, 1, 0]],
    "Z": [[1, 1, 0], [0, 1, 1]],
    "J": [[1, 0, 0], [1, 1, 1]],
    "L": [[0, 0, 1], [1, 1, 1]],
}

PIECES = list(SHAPES.keys())


def rotate_clockwise(mat):
    return [list(row) for row in zip(*mat[::-1])]


def level_tick(level, speed_multiplier=1.0):
    base = max(MIN_TICK, TICK_START - (level - 1) * 0.04)
    return max(0.03, base / max(0.1, speed_multiplier))


class Piece:
    def __init__(self, kind):
        self.kind = kind
        self.shape = [row[:] for row in SHAPES[kind]]
        self.y = 0
        self.x = BOARD_W // 2 - len(self.shape[0]) // 2


class Game:
    def __init__(self, start_level=1, speed_multiplier=1.0, fixed_level=False):
        self.board = [[0] * BOARD_W for _ in range(BOARD_H)]
        self.score = 0
        self.lines = 0
        self.level = max(1, start_level)
        self.start_level = self.level
        self.speed_multiplier = speed_multiplier
        self.fixed_level = fixed_level
        self.tick = level_tick(self.level, self.speed_multiplier)
        self.game_over = False
        self.paused = False
        self.cur = self.spawn()
        self.next_kind = random.choice(PIECES)

    def spawn(self):
        p = Piece(random.choice(PIECES))
        if not self.valid(p, p.y, p.x, p.shape):
            self.game_over = True
        return p

    def collides(self, y, x, shape):
        for r, row in enumerate(shape):
            for c, cell in enumerate(row):
                if not cell:
                    continue
                ny, nx = y + r, x + c
                if nx < 0 or nx >= BOARD_W or ny >= BOARD_H:
                    return True
                if ny >= 0 and self.board[ny][nx]:
                    return True
        return False

    def valid(self, piece, y, x, shape):
        return not self.collides(y, x, shape)

    def lock_piece(self):
        for r, row in enumerate(self.cur.shape):
            for c, cell in enumerate(row):
                if cell:
                    by, bx = self.cur.y + r, self.cur.x + c
                    if 0 <= by < BOARD_H and 0 <= bx < BOARD_W:
                        self.board[by][bx] = 1
        self.clear_lines()
        self.cur = Piece(self.next_kind)
        self.next_kind = random.choice(PIECES)
        if self.collides(self.cur.y, self.cur.x, self.cur.shape):
            self.game_over = True

    def clear_lines(self):
        new_rows = [row for row in self.board if not all(row)]
        cleared = BOARD_H - len(new_rows)
        if cleared:
            self.board = [[0] * BOARD_W for _ in range(cleared)] + new_rows
            self.lines += cleared
            self.score += [0, 100, 300, 500, 800][cleared] * self.level
            if not self.fixed_level:
                self.level = self.start_level + self.lines // 10
            self.tick = level_tick(self.level, self.speed_multiplier)

    def move(self, dx):
        nx = self.cur.x + dx
        if self.valid(self.cur, self.cur.y, nx, self.cur.shape):
            self.cur.x = nx

    def soft_drop(self):
        ny = self.cur.y + 1
        if self.valid(self.cur, ny, self.cur.x, self.cur.shape):
            self.cur.y = ny
            self.score += 1
            return True
        self.lock_piece()
        return False

    def hard_drop(self):
        dropped = 0
        while self.valid(self.cur, self.cur.y + 1, self.cur.x, self.cur.shape):
            self.cur.y += 1
            dropped += 1
        self.score += dropped * 2
        self.lock_piece()

    def rotate(self):
        rotated = rotate_clockwise(self.cur.shape)
        for kick in (0, -1, 1, -2, 2):
            nx = self.cur.x + kick
            if self.valid(self.cur, self.cur.y, nx, rotated):
                self.cur.shape = rotated
                self.cur.x = nx
                return


def draw(stdscr, g):
    stdscr.erase()
    stdscr.addstr(0, 0, "TETRIS")
    stdscr.addstr(1, 0, f"Score: {g.score}")
    stdscr.addstr(2, 0, f"Lines: {g.lines}")
    stdscr.addstr(3, 0, f"Level: {g.level}")
    stdscr.addstr(4, 0, f"Speed x{g.speed_multiplier:.2f}")

    top, left = 1, 20
    stdscr.addstr(top - 1, left, "+" + "--" * BOARD_W + "+")
    for y in range(BOARD_H):
        line = "|"
        for x in range(BOARD_W):
            line += "██" if g.board[y][x] else "  "
        line += "|"
        stdscr.addstr(top + y, left, line)
    stdscr.addstr(top + BOARD_H, left, "+" + "--" * BOARD_W + "+")

    for r, row in enumerate(g.cur.shape):
        for c, cell in enumerate(row):
            if cell:
                y = g.cur.y + r
                x = g.cur.x + c
                if y >= 0:
                    stdscr.addstr(top + y, left + 1 + x * 2, "██")

    stdscr.addstr(7, 0, "Controls:")
    stdscr.addstr(8, 0, "←/→ move, ↑ rotate")
    stdscr.addstr(9, 0, "↓ soft drop, space hard drop")
    stdscr.addstr(10, 0, "p pause, q quit")

    if g.paused:
        stdscr.addstr(13, 0, "PAUSED")
    if g.game_over:
        stdscr.addstr(13, 0, "GAME OVER - press q")

    stdscr.refresh()


def run(stdscr, start_level=1, speed_multiplier=1.0, fixed_level=False):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    g = Game(start_level=start_level, speed_multiplier=speed_multiplier, fixed_level=fixed_level)
    last_tick = time.time()

    while True:
        now = time.time()
        key = stdscr.getch()

        if key == ord("q"):
            break
        if key == ord("p") and not g.game_over:
            g.paused = not g.paused

        if not g.paused and not g.game_over:
            if key == curses.KEY_LEFT:
                g.move(-1)
            elif key == curses.KEY_RIGHT:
                g.move(1)
            elif key == curses.KEY_UP:
                g.rotate()
            elif key == curses.KEY_DOWN:
                g.soft_drop()
            elif key == ord(" "):
                g.hard_drop()

            if now - last_tick >= g.tick:
                g.soft_drop()
                last_tick = now

        draw(stdscr, g)
        time.sleep(0.01)


def parse_args():
    p = argparse.ArgumentParser(description="Terminal Tetris")
    p.add_argument("--start-level", type=int, default=1, help="starting level (default: 1)")
    p.add_argument(
        "--speed-multiplier",
        type=float,
        default=1.0,
        help="global speed factor, higher=faster (default: 1.0)",
    )
    p.add_argument("--fixed-level", action="store_true", help="disable auto level-up")
    return p.parse_args()


def main():
    args = parse_args()
    curses.wrapper(
        lambda stdscr: run(
            stdscr,
            start_level=max(1, args.start_level),
            speed_multiplier=max(0.1, args.speed_multiplier),
            fixed_level=args.fixed_level,
        )
    )


if __name__ == "__main__":
    main()
