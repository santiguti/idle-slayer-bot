"""Boss fights, ported from Libraries/BossFightVictor.au3 and BossFightKnight.au3.

Not in the original (measured live 2026-11-05, `logs/recordings/2026-11-05-victor*/`): the fight ends on 5 empty
hearts, a charge left of the attack column is dodged, the flame jump waits for the pillar, stage 2 keeps
shooting between dodges, and the loop's searches log only hits.
"""
from typing import Protocol

import numpy as np

from idle_runner.game import STUCK_MS, Game
from idle_runner.log import event
from idle_runner.minigames.common import slide_until_gone
from idle_runner.repeater import Repeater

# The original gives up after 200 s (`If 200000 < TimerDiff($hTimeEndBoss)`). Not enough now: stage 1 takes ~80 s
# and stage 2 needs minutes of shooting; a lost fight ends on its empty hearts anyway.
GIVE_UP_MS = 400_000

# The 5 hearts under the arena; a full one is F01840, an empty one 200309 (client (440 + 100k, 635)).
HEARTS = [(448 + 100 * k, 666) for k in range(5)]
EMPTY_HEART = 0x200309

# The original's attack column is x 919. Victor sometimes teleports left of it (client x ~700-880) and his comet
# never crosses it. Before each comet he charges for ~400 ms: an exact-white blob >= 500 px and ~110 px tall.
ATTACK_COLUMN_X = 919
CHARGE_AREA = (339, 231, 1000, 491)  # client x 331..992, y 200..460
CHARGE_TO_LAUNCH_MS = 400
COMET_PX_PER_MS = 1.34
PLAYER_RIGHT_X = 308  # AutoIt; client ~300
COLUMN_TO_PLAYER_MS = (ATTACK_COLUMN_X - PLAYER_RIGHT_X) / COMET_PX_PER_MS  # ~456 ms: the original's warning
LOW_CHARGE_Y = 380  # a charge centred lower is a comet whose top is under the original's y 370: DownAttack

# Stage 2: after the spark at x 1072 a fire pillar runs left along the ground at ~0.92 px/ms. The original's
# Sleep(350) + 100 ms hold landed the player into it (3 of 3, 2026-11-05). Calibration knobs for the next fight:
FLAME_ROW_Y = 471  # client 440
PILLAR_COLOURS = (0xE32CFF, 0x8E1B27)  # on that row: the magenta pillar and the dark red one
FLAME_SEARCH = (338, 908)  # client 330..900: the player (dark red too) is left of it, Victor's aura right
FLAME_JUMP_X = 590  # jump when the pillar's front reaches this x (the original jumped at ~690; the pillar
#                     crosses the player while its front goes ~300 -> ~145, and a 100 ms jump peaks ~380 ms in)
FLAME_HOLD_MS = 300  # the original holds 100 ms: its jump barely tops the pillar; 300 ms clears it (21:22:01)
FLAME_WAIT_MS = 900  # no pillar by then: jump anyway, like the original


class Shooter(Protocol):
    """AdlibRegister("Shoot", 50) / AdlibUnRegister("Shoot")."""

    def resume(self) -> None: ...
    def pause(self) -> None: ...


def boss_fight_knight(game: Game) -> None:
    # The original returns right after this log line: its Knight logic is disabled, so it isn't ported.
    event("Start of BossFight Knight")


def boss_fight_victor(game: Game) -> None:
    event("Start of BossFight Victor")
    slide_until_gone(game, "victor", 653, 222, 653, 222, 0xFFF38F)
    game.save_frame("victor-start")
    shooter = Repeater(game, ("Up",), 50, "victor-shoot")
    try:
        victor_battle(game, shooter)
    finally:
        shooter.stop()
        game.save_frame("victor-end")


def victor_battle(game: Game, shooter: Shooter) -> None:
    shooter.resume()
    game.sleep(5000)
    first_stage = True
    interval = 2000
    last_check = start = game.now()
    charges_from = start  # not in the original: one dodge per charge
    while True:
        if not first_stage and game.pixel_search(1072, 150, 1072, 488, 0xFFFFFF, quiet=True):
            flame_dodge(game, shooter)
        attack = game.pixel_search(919, 292, 919, 452, 0xFFFFFF, quiet=True)
        if attack:
            shooter.pause()
            event("Victor attack", y=attack[1], low=attack[1] > 370)
            if attack[1] > 370:
                down_attack(game, shooter, first_stage)
            else:
                upper_attack(game, shooter, first_stage)
        # Stage 1 only: seen there twice; in stage 2 the fire pillar's white core looks like a charge.
        elif first_stage and game.now() >= charges_from and (charge := charge_left_of_column(game)):
            charge_attack(game, shooter, first_stage, charge)
            charges_from = game.now() + 1000  # the charge may still show; comets come ~3.9 s apart

        if game.now() - last_check > interval:
            if game.pixel_is(835, 477, 0xFD3169):  # victory screen
                shooter.pause()
                game.sleep(500)
                game.click(615, 563)
                event("Victor Won")
                return
            if all(game.pixel_is(x, y, EMPTY_HEART) for x, y in HEARTS):  # not in the original
                shooter.pause()
                event("Victor Lost", reason="no hearts left")
                return
            if first_stage and game.pixel_is(272, 130, 0xAE6C37):  # stage 2 dialog
                first_stage = False
                interval = 10_000
                event("Victor Stage 2")
                shooter.resume()
                deadline = game.now() + STUCK_MS
                while True:
                    game.sleep(50)
                    if not game.pixel_is(272, 130, 0xAE6C37):
                        break
                    if game.now() > deadline:
                        game.stuck("victor.dialog")
                        break
                game.sleep(4000)  # the original pauses the shooter here; arrows still hurt Victor in stage 2
            if game.now() - start > GIVE_UP_MS:
                shooter.pause()
                event("Victor Lost")
                return
            last_check = game.now()


def charge_left_of_column(game: Game) -> tuple[int, int] | None:
    """(left x, centre y) of a charge lying wholly left of the attack column, in AutoIt coordinates."""
    left, top, right, bottom = CHARGE_AREA
    white = (game.grab(left, top, right, bottom) == 255).all(axis=2)
    if white.sum() < 500:
        return None
    columns = np.nonzero(white.any(axis=0))[0]
    for blob in np.split(columns, np.nonzero(np.diff(columns) > 12)[0] + 1):  # blobs: gaps over 12 px
        pixels = white[:, blob[0]:blob[-1] + 1]
        rows = np.nonzero(pixels.any(axis=1))[0]
        if pixels.sum() >= 500 and rows[-1] - rows[0] >= 80 and left + blob[-1] < ATTACK_COLUMN_X:
            return left + int(blob[0]), top + int(rows[0] + rows[-1]) // 2
    return None


def charge_attack(game: Game, shooter: Shooter, first_stage: bool, charge: tuple[int, int]) -> None:
    """Wait until the comet is as close as when the original's column sees it, then dodge like the original."""
    x, y = charge
    shooter.pause()
    event("Victor charge", x=x, y=y, low=y > LOW_CHARGE_Y)
    game.sleep(max(0.0, CHARGE_TO_LAUNCH_MS + (x - PLAYER_RIGHT_X) / COMET_PX_PER_MS - COLUMN_TO_PLAYER_MS))
    if y > LOW_CHARGE_Y:
        down_attack(game, shooter, first_stage)
    else:
        upper_attack(game, shooter, first_stage)


def flame_dodge(game: Game, shooter: Shooter) -> None:
    """Not in the original, which doesn't shoot in stage 2: stop the small jumps so the flame jump starts grounded
    (the player lands <= 270 ms after a pause; the pillar's front reaches FLAME_JUMP_X ~470 ms after the spark)."""
    shooter.pause()
    flame_attack(game)
    shooter.resume()


def flame_attack(game: Game) -> None:
    # The original: Sleep(350), then the jump. Here: wait for the pillar's front (not in the original).
    deadline = game.now() + FLAME_WAIT_MS
    front = None
    while game.now() < deadline:
        found = [game.pixel_search(FLAME_SEARCH[0], FLAME_ROW_Y, FLAME_SEARCH[1], FLAME_ROW_Y, colour, quiet=True)
                 for colour in PILLAR_COLOURS]
        front = min((f for f in found if f), default=None)
        if front and front[0] <= FLAME_JUMP_X:
            break
        game.sleep(5)
    event("Victor flame jump", pillar_x=front[0] if front else None)
    game.key_down("Up")
    game.sleep(FLAME_HOLD_MS)
    game.key_up("Up")
    for _ in range(18):
        game.sleep(10)
        game.tap("Up")


def down_attack(game: Game, shooter: Shooter, first_stage: bool) -> None:
    game.sleep(200)
    if first_stage:
        shooter.resume()
        return
    game.key_down("Up")
    game.sleep(100)
    game.key_up("Up")
    for _ in range(18):
        game.sleep(10)
        game.tap("Up")
    shooter.resume()  # not in the original: keep shooting in stage 2


def upper_attack(game: Game, shooter: Shooter, first_stage: bool) -> None:
    game.sleep(730)
    if first_stage:
        shooter.resume()
        return
    for _ in range(15):
        game.sleep(10)
        game.tap("Up")
    shooter.resume()  # not in the original: keep shooting in stage 2
