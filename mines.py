#!/usr/bin/env python3
"""
Terminal Minesweeper (curses)

Controls:
  Arrow keys / WASD : move cursor
  Space or Enter    : reveal cell
  F                 : flag/unflag
  R                 : restart
  Q                 : quit
"""

import curses
import random
import time


W, H = 12, 12
MINES = 20


class Game:
    def __init__(self, w=W, h=H, mines=MINES):
        self.w = w
        self.h = h
        self.mines = mines
        self.reset()

    def reset(self):
        self.board = [[0 for _ in range(self.w)] for _ in range(self.h)]
        self.revealed = [[False for _ in range(self.w)] for _ in range(self.h)]
        self.flagged = [[False for _ in range(self.w)] for _ in range(self.h)]
        self.cursor_x = 0
        self.cursor_y = 0
        self.game_over = False
        self.win = False
        self.started = False
        self.start_time = time.time()

    def in_bounds(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def neighbors(self, x, y):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if self.in_bounds(nx, ny):
                    yield nx, ny

    def place_mines(self, safe_x, safe_y):
        candidates = [(x, y) for y in range(self.h) for x in range(self.w) if not (x == safe_x and y == safe_y)]
        for x, y in random.sample(candidates, self.mines):
            self.board[y][x] = -1

        for y in range(self.h):
            for x in range(self.w):
                if self.board[y][x] == -1:
                    continue
                self.board[y][x] = sum(1 for nx, ny in self.neighbors(x, y) if self.board[ny][nx] == -1)

    def flood_reveal(self, x, y):
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if not self.in_bounds(cx, cy):
                continue
            if self.revealed[cy][cx] or self.flagged[cy][cx]:
                continue
            self.revealed[cy][cx] = True
            if self.board[cy][cx] == 0:
                for nx, ny in self.neighbors(cx, cy):
                    if not self.revealed[ny][nx]:
                        stack.append((nx, ny))

    def reveal(self, x, y):
        if self.game_over or self.flagged[y][x] or self.revealed[y][x]:
            return

        if not self.started:
            self.place_mines(x, y)
            self.started = True
            self.start_time = time.time()

        if self.board[y][x] == -1:
            self.revealed[y][x] = True
            self.game_over = True
            self.win = False
            return

        self.flood_reveal(x, y)
        self.check_win()

    def toggle_flag(self, x, y):
        if self.game_over or self.revealed[y][x]:
            return
        self.flagged[y][x] = not self.flagged[y][x]

    def check_win(self):
        hidden_non_mines = 0
        for y in range(self.h):
            for x in range(self.w):
                if self.board[y][x] != -1 and not self.revealed[y][x]:
                    hidden_non_mines += 1
        if hidden_non_mines == 0:
            self.game_over = True
            self.win = True

    def elapsed(self):
        if not self.started:
            return 0
        return int(time.time() - self.start_time)


def draw(stdscr, g: Game):
    stdscr.erase()
    stdscr.addstr(0, 0, "MINESWEEPER")
    stdscr.addstr(1, 0, f"Grid: {g.w}x{g.h}   Mines: {g.mines}   Time: {g.elapsed()}s")
    flags_used = sum(1 for row in g.flagged for v in row if v)
    stdscr.addstr(2, 0, f"Flags: {flags_used}/{g.mines}")

    top = 4
    left = 2

    stdscr.addstr(top - 1, left, "+" + "--" * g.w + "+")
    for y in range(g.h):
        stdscr.addstr(top + y, left, "|")
        for x in range(g.w):
            ch = "·"
            if g.revealed[y][x]:
                if g.board[y][x] == -1:
                    ch = "*"
                elif g.board[y][x] == 0:
                    ch = " "
                else:
                    ch = str(g.board[y][x])
            elif g.flagged[y][x]:
                ch = "F"
            elif g.game_over and not g.win and g.board[y][x] == -1:
                ch = "*"

            attr = curses.A_NORMAL
            if x == g.cursor_x and y == g.cursor_y:
                attr |= curses.A_REVERSE
            stdscr.addstr(top + y, left + 1 + x * 2, ch + " ", attr)

        stdscr.addstr(top + y, left + 1 + g.w * 2, "|")
    stdscr.addstr(top + g.h, left, "+" + "--" * g.w + "+")

    stdscr.addstr(top + g.h + 2, 0, "Arrows/WASD move  Space/Enter reveal  F flag  R restart  Q quit")

    if g.game_over:
        if g.win:
            stdscr.addstr(top + g.h + 4, 0, "You win! Press R to play again.")
        else:
            stdscr.addstr(top + g.h + 4, 0, "Boom! You hit a mine. Press R to retry.")

    stdscr.refresh()


def run(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    g = Game()

    while True:
        key = stdscr.getch()

        if key in (ord("q"), ord("Q")):
            break
        elif key in (ord("r"), ord("R")):
            g.reset()
        elif key in (curses.KEY_LEFT, ord("a"), ord("A")):
            g.cursor_x = max(0, g.cursor_x - 1)
        elif key in (curses.KEY_RIGHT, ord("d"), ord("D")):
            g.cursor_x = min(g.w - 1, g.cursor_x + 1)
        elif key in (curses.KEY_UP, ord("w"), ord("W")):
            g.cursor_y = max(0, g.cursor_y - 1)
        elif key in (curses.KEY_DOWN, ord("s"), ord("S")):
            g.cursor_y = min(g.h - 1, g.cursor_y + 1)
        elif key in (ord("f"), ord("F")):
            g.toggle_flag(g.cursor_x, g.cursor_y)
        elif key in (ord(" "), 10, 13, curses.KEY_ENTER):
            g.reveal(g.cursor_x, g.cursor_y)

        draw(stdscr, g)
        time.sleep(0.02)


def main():
    curses.wrapper(run)


if __name__ == "__main__":
    main()
