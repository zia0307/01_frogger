"""
GameEngine: owns the frog and all vehicles, and runs one frame's worth
of game logic.

Features:
  - Task 1: rectangle-based vehicle collisions (see game/collisions.py)
  - Task 2: 3 lives, respawn at start with a short grace period
  - Task 3: score tracking and a win state when the goal is reached
  - Task 4: 30-second timer per attempt; timeout costs a life
"""

import math
import random

import pygame

from game.frog import Frog
from game.vehicle import Vehicle
from game.collisions import check_collision
from game import renderer
from game.renderer import (
    GRID_COLS, GRID_ROWS, GOAL_ROW, ROAD_ROWS, START_ROW, CELL_SIZE, WIDTH, HEIGHT,
)

LANE_SPEEDS = [1.5, -2, 2, -2.5, 1.5, -2]   # one entry per road row, alternating direction

STARTING_LIVES = 3
ATTEMPT_SECONDS = 30
RESPAWN_GRACE_MS = 1000     # frog can't be hit right after respawning
POINTS_PER_ROW = 10         # each new row of forward progress in an attempt
GOAL_BONUS = 100
TIME_BONUS_PER_SECOND = 5   # for each second left when reaching the goal

PLAYING, WON, GAME_OVER = "playing", "won", "game_over"


class GameEngine:
    def __init__(self):
        self._build_entities()

    # ------------------------------------------------------------------ setup
    def _build_entities(self):
        start_col = GRID_COLS // 2
        self.frog = Frog(
            col=start_col, row=START_ROW,
            start_col=start_col, start_row=START_ROW,
            cols=GRID_COLS, start_row_limit=START_ROW,
        )
        frog_x_range = (start_col * CELL_SIZE, start_col * CELL_SIZE + CELL_SIZE)

        self.vehicles = []
        for i, row in enumerate(ROAD_ROWS):
            speed = LANE_SPEEDS[i % len(LANE_SPEEDS)]
            vehicle_width = 40 if i % 2 == 0 else 70   # mix of cars and wider trucks
            spacing = 300
            count = 2

            # Try a few random phases and keep the first one that doesn't
            # already overlap the frog's starting column - guarantees a
            # safe first lane instead of leaving it to chance.
            for _attempt in range(20):
                phase = random.randint(0, spacing - 1)
                positions = []
                safe = True
                for n in range(count):
                    offset = phase + n * spacing
                    x = offset if speed > 0 else WIDTH - offset - vehicle_width
                    positions.append(x)
                    if not (x + vehicle_width <= frog_x_range[0] or x >= frog_x_range[1]):
                        safe = False
                if safe:
                    break

            for x in positions:
                self.vehicles.append(Vehicle(x=x, row=row, width=vehicle_width,
                                              height=CELL_SIZE - 8, speed=speed))

        # Game-state (lives / score / timer)
        self.state = PLAYING
        self.lives = STARTING_LIVES
        self.score = 0
        self._start_attempt()

    def _start_attempt(self):
        """Begin a fresh attempt: frog at start, timer back to 30s."""
        now = pygame.time.get_ticks()
        self.frog.reset()
        self.best_row = self.frog.row
        self.attempt_start = now
        self.grace_until = now + RESPAWN_GRACE_MS
        self.time_left = float(ATTEMPT_SECONDS)

    # ------------------------------------------------------------------ input
    def handle_keydown(self, key):
        if key == pygame.K_r:
            self._build_entities()
            return

        if self.state != PLAYING:
            return

        if key == pygame.K_UP:
            self.frog.move(0, -1)
        elif key == pygame.K_DOWN:
            self.frog.move(0, 1)
        elif key == pygame.K_LEFT:
            self.frog.move(-1, 0)
        elif key == pygame.K_RIGHT:
            self.frog.move(1, 0)

        # Score for reaching a new furthest row in this attempt
        if self.frog.row < self.best_row:
            self.score += POINTS_PER_ROW * (self.best_row - self.frog.row)
            self.best_row = self.frog.row

    # ----------------------------------------------------------------- update
    def _lose_life(self):
        self.lives -= 1
        if self.lives <= 0:
            self.lives = 0
            self.state = GAME_OVER
        else:
            self._start_attempt()

    def update(self):
        if self.state != PLAYING:
            return   # world freezes on win / game over; press R to restart

        for v in self.vehicles:
            v.update(road_width_px=WIDTH)

        now = pygame.time.get_ticks()
        self.time_left = max(0.0, ATTEMPT_SECONDS - (now - self.attempt_start) / 1000)

        # Goal first, so reaching it on the same frame as a hit still counts
        if self.frog.row == GOAL_ROW:
            self.score += GOAL_BONUS + int(self.time_left) * TIME_BONUS_PER_SECOND
            self.state = WON
            return

        if self.time_left <= 0:
            self._lose_life()
            return

        if now >= self.grace_until and check_collision(self.frog, self.vehicles):
            self._lose_life()

    # ------------------------------------------------------------------- draw
    def draw(self, surface, font):
        now = pygame.time.get_ticks()
        in_grace = self.state == PLAYING and now < self.grace_until
        frog_visible = not (in_grace and (now // 120) % 2 == 0)   # blink while safe

        renderer.draw_scene(surface, self.frog, self.vehicles, frog_visible)

        secs = math.ceil(self.time_left)
        hud = f"Score: {self.score}   Lives: {self.lives}   Time: {secs:02d}"
        renderer.draw_text(surface, font, hud, (10, 14))

        if self.state == WON:
            renderer.draw_banner(surface, font, f"YOU WIN!  Score: {self.score}  -  Press R to play again")
        elif self.state == GAME_OVER:
            renderer.draw_banner(surface, font, "GAME OVER  -  Press R to restart")
        else:
            renderer.draw_text(surface, font, "Arrow keys to move. R to restart.", (10, HEIGHT - 24))
