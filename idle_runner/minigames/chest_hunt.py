"""Chest hunt, ported from Libraries/ChestHunt.au3."""
from enum import IntEnum

from idle_runner.game import STUCK_MS, Game, Point
from idle_runner.log import event

GRID_X, GRID_Y, STEP = 185, 325, 95  # chest grid: 3 rows x 10 columns


class Chest(IntEnum):
    REWARD = 0
    MIMIC = 1
    X2 = 2
    END = 3
    LIFE_SAVER = 4


class State(IntEnum):
    NO_MIMIC = 0
    ONE_MIMIC = 1
    TWO_MIMICS = 2
    OPEN_LIFE_SAVER = 3
    NORMAL = 4


def updated_state(count: int, state: State, chest: Chest, perfect: bool, no_reinforced: bool) -> State:
    """GetUpdatedState: what to do after opening chest number `count` (0-based)."""
    if state == State.NORMAL or chest == Chest.LIFE_SAVER:  # after the life saver: just open chests
        return State.NORMAL
    if chest == Chest.X2:  # always open the life saver after a 2x chest
        return State.OPEN_LIFE_SAVER
    if perfect:
        perfect_next = perfect_state(chest, state, count)
        if perfect_next is not None:
            return perfect_next
    if count == 0:
        if no_reinforced:
            return State.OPEN_LIFE_SAVER
        if chest == Chest.REWARD:
            return State.NO_MIMIC
        if chest == Chest.MIMIC:
            return State.ONE_MIMIC
    elif count == 1:
        if not perfect:  # normal strategy: open the life saver after the 2nd chest
            return State.OPEN_LIFE_SAVER
        if state == State.NO_MIMIC:
            if chest == Chest.REWARD:
                return State.NO_MIMIC
            if chest == Chest.MIMIC:
                return State.ONE_MIMIC
        elif state == State.ONE_MIMIC:
            if chest == Chest.REWARD:
                return State.ONE_MIMIC
            if chest == Chest.MIMIC:
                return State.TWO_MIMICS
    return state


def perfect_state(chest: Chest, state: State, count: int) -> State | None:
    """PerfectChestHuntState: ignore the life saver until a 2x is found or enough chests are open."""
    if chest == Chest.REWARD and (state, count) in (
            (State.NO_MIMIC, 13), (State.ONE_MIMIC, 15), (State.TWO_MIMICS, 21)):
        return State.OPEN_LIFE_SAVER
    return None


def find_saver(game: Game) -> Point | None:
    for row in range(3):
        for col in range(10):
            x, y = GRID_X + col * STEP, GRID_Y + row * STEP
            if game.pixel_search(x, y - 1, x + 5, y, 0xFFEB04):
                return x, y
    return None


def open_chest(game: Game, x: int, y: int, no_lockpicking: bool) -> Chest:
    game.click(x + 33, y - 23)
    game.sleep(1500 if no_lockpicking else 550)
    if game.pixel_is(550, 694, 0xAF0000):  # close button: the hunt is over
        return Chest.END
    if game.pixel_is(500, 210, 0x00FF00):  # 2x
        game.sleep(1000)
        return Chest.X2
    if game.pixel_is(434, 211, 0xFF0000):  # mimic
        game.sleep(2500 if no_lockpicking else 1500)
        return Chest.MIMIC
    return Chest.REWARD


def open_life_saver(game: Game, saver: Point | None, no_lockpicking: bool) -> None:
    if saver is None:  # the original clicked at (33, -23) here
        event("Life saver skipped: saver not found")
        return
    game.click(saver[0] + 33, saver[1] - 23)
    game.sleep(1500 if no_lockpicking else 550)
    event("Life saver opened")


def process_grid(game: Game, saver: Point | None, no_lockpicking: bool, perfect: bool,
                 no_reinforced: bool) -> None:
    count = 0
    state = State.NO_MIMIC
    for row in range(3):
        for col in range(10):
            x, y = GRID_X + col * STEP, GRID_Y + row * STEP
            if (x, y) == saver:
                continue
            chest = open_chest(game, x, y, no_lockpicking)
            if chest == Chest.END:
                return
            state = updated_state(count, state, chest, perfect, no_reinforced)
            event("Chest opened", index=count, row=row, col=col, result=chest.name, state=state.name)
            if state == State.OPEN_LIFE_SAVER:
                open_life_saver(game, saver, no_lockpicking)
                state = State.NORMAL
            count += 1


def chest_hunt(game: Game, no_lockpicking: bool, perfect: bool, no_reinforced: bool) -> None:
    event("Chesthunt Started", perfect_strategy=perfect)
    game.sleep(4000 if no_lockpicking else 2000)
    game.save_frame("chesthunt-start")
    saver = find_saver(game)
    if saver is None:
        event("Chesthunt saver not found")
        game.save_frame("chesthunt-no-saver")
    process_grid(game, saver, no_lockpicking, perfect, no_reinforced)

    perfect_found = False
    attempts = 0
    deadline = game.now() + 5 * STUCK_MS
    while True:  # wait for the close button, clicking the perfect-chest reward if it shows
        game.sleep(50)
        attempts += 1
        if game.pixel_is(550, 694, 0xAF0000):
            break
        if game.pixel_is(457, 439, 0xF68F37):
            perfect_found = True
            game.click(457, 439)
        # Not in the original: after a perfect hunt the bonus chests open by themselves for ~14 s (2026-11-12
        # and 11-16), past the 10 s below; there is no grid left to click, so wait for Close.
        if attempts > 200 and not perfect_found:
            event("Chsthunt  Blocked divinity  X, Start Again ")  # exact text of ChestHunt.au3, typos included
            game.save_frame("chesthunt-blocked")
            process_grid(game, saver, no_lockpicking, perfect, no_reinforced)
            attempts = 0
        if game.now() > deadline:
            game.stuck("chest_hunt.end_screen")
            break
    if perfect_found:
        event("Perfect ChestHunt Completed")
    game.save_frame("chesthunt-end")
    game.click(643, 693)
