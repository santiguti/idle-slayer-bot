"""Small UI routines from Idle Runner.au3: CloseAll, CheckForSoulBonus, BuyTempItem, CollectMinion."""
import numpy as np

from idle_runner.game import Game
from idle_runner.log import event

SOUL_BONUS = 0xA86D0A
RAGE_PILL = 0x871646
SOUL_COMPASS = 0x7D55D8
DIMENSIONAL_STAFF = 0xF37C55
BIDIMENSIONAL_STAFF = 0x526629
BOX_SLATE = np.array([0x5F, 0x6D, 0x95], dtype=np.uint8)  # frame of the floating silver Random Box
MIN_BOX_PIXELS = 100  # measured 2026-10-23: the box shows 117-508 of them, other objects at most 52
BOX_ORANGE = np.array([0xDF, 0x71, 0x26], dtype=np.uint8)  # frame of the floating orange (sword) Random Box
MIN_ORANGE_BOX_PIXELS = 100  # measured 2026-10-26 over 900 frames: 0 without a box, 599-817 with one, 104 entering
TAB_SELECTED = 0x5E261B  # ±6: a selected tab, in the shop and the ascension panel (fades 5A251A-62271C)
PANEL_X_RED = 0xAD1111  # the ascension panel's X tab at (538, 681), on any of its tabs (measured 2026-10-25)


def close_all(game: Game) -> None:
    """Close a popup (red X button) if one is showing.

    The original slept 2 s first (Idle Runner.au3:262), which left the fast checks blind 2 s out of
    every 5 for no reason; removed 2026-10-22.
    """
    if game.pixel_is(680, 593, 0xAF0000):
        game.click(780, 600)


def box_on_screen(game: Game) -> bool:
    """A silver or orange Random Box floats over the run, left of the shop panel. Not in the original.

    The player only gets it by jumping into it, so shopping stops while one is up. The top-centre
    bonus ("Silver Box Collected") sends 5 of them in a row. The orange one carries a sword and was
    found in the 2026-10-23 recording (its sword has 51 slate pixels, below the silver threshold).
    """
    return _box_in(game.grab(8, 131, 797, 510))  # client (0, 100)-(789, 479)


def box_beside_panel(game: Game) -> bool:
    """A Random Box floats in beside the open ascension panel (client x 0-639), where the run still shows. Not in
    the original. A box crosses the screen right to left at ~210 px/s (live 2026-11-12: client x 770 -> 145 in
    3.0 s), so it shows here for ~3 s before it goes behind the panel. Over the 2,607 frames recorded on
    2026-11-12 this strip matched only boxes and the open shop (its quest "Hit 20 Random Boxes" has the box's
    icon). The shop can stay open under the panel after a routine stopped by a focus loss (00:45:42), so with
    the shop open only the run between the two is searched."""
    shop_open = game.pixel_search(807, 140, 807, 155, 0xFFFFFF, quiet=True) is not None  # its corner (open_shop)
    return _box_in(game.grab(648, 131, 797 if shop_open else 1287, 510))  # client (640, 100)-(789 or 1279, 479)


def _box_in(region: np.ndarray) -> bool:
    return (int((region == BOX_SLATE).all(axis=2).sum()) >= MIN_BOX_PIXELS
            or int((region == BOX_ORANGE).all(axis=2).sum()) >= MIN_ORANGE_BOX_PIXELS)


def soul_bonus_active(game: Game) -> bool:
    return game.pixel_search(625, 143, 629, 214, SOUL_BONUS, quiet=True) is not None  # checked every loop


def buy_temp_item(game: Game, color: int) -> None:
    """Craft the temporary item whose icon has `color`."""
    item = f"0x{color:06X}"
    event("Trying to CraftingTemp Item", item=item)
    game.click(160, 100)  # open the menu
    game.sleep(150)
    game.click(260, 690)  # temporary items tab
    game.sleep(150)
    found = game.pixel_search(43, 330, 625, 630, color)
    if found:
        game.click(*found)
        game.sleep(200)
        game.click(420, 156)  # craft
        event("CraftingTemp Item Active", item=item)
    else:
        event("CraftingTemp Item Failed, not enough materials", item=item)
    game.click(440, 690)  # close
    game.sleep(100)


def open_ascension_tab(game: Game) -> bool:
    """Open the ascension panel on its Ascension tab and wait up to 2 s for the Ascend button; click
    once more if it doesn't show. Not in the original, which slept 400 ms after each click: on
    2026-10-25 the click that reopened the panel 21 ms after the bonus sample closed it was lost.
    The ascension button is clicked only while the panel is closed: on the tree tab, (95, 90) is the
    "Buy on Click" toggle, which would make any later click in the tree buy a node."""
    for attempt in range(2):
        if attempt:
            event("Shop click retried", target="ascension")
        if not game.pixel_is(538, 681, PANEL_X_RED):
            game.click(95, 90)  # ascension button
            game.sleep(400)
        game.click(93, 680)  # ascension tab
        if game.find_until(260, 480, 260, 480, 0x58188D, timeout_ms=2000):  # Ascend button
            return True
    return False
