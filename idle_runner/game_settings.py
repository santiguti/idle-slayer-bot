"""Check the in-game settings the bot needs, at the first Start of each day (the runner keeps the date). Not
in the original, which only listed them.

The settings are a dialog behind the shop's "⋮" tab (measured 2026-10-28): a list that opens at its top (on
Windows not always, so there it's wheeled up first) and scrolls 50 px per wheel notch. A toggle shows a red
cross (F83308) on its left when off and a green tick (1DD700) on its right when on. Each row is told by its label's white pixels, in English or Spanish (the game's
other languages give "not found", never a wrong reading). The bot only reads the list: it ends with "Delete Save" and "Delete Idle Slayer Account" and holds
"Remove Ads" purchases, so the only click inside the dialog is Cancel, and the wheel turns in the empty strip
beside the scrollbar.
"""
import sys

import numpy as np

from idle_runner.actions import TAB_SELECTED
from idle_runner.game import Game
from idle_runner.log import event
from idle_runner.shop import Shop

# Each setting the bot needs, by its English name: its label's right edge (client x) and white pixels in English
# and in Spanish (measured 2026-10-28 on Linux; Spanish names in the comments), and the state it needs.
SETTINGS: dict[str, tuple[tuple[tuple[int, int], ...], bool]] = {
    # the coin, bonus and SP readers read plain numbers
    "Use scientific notation": (((680, 722), (695, 750)), False),  # "Usar notación científica"
    "Disable custom cursor": (((680, 713), (818, 1058)), True),  # "Desactivar el cursor personalizado"
    "Rounded bulk buy": (((635, 700), (744, 912)), True),  # "Compra masiva redondeada"
    # Locked event rewards would sit in the Upgrades list. "Ocultar recompensas de Misiones Bloqueadas": two
    # lines, told by the first.
    "Hide locked Quest rewards": (((731, 911), (801, 1127)), True),
    "Confirm dialogue when activating the Portal": (((846, 1360), (848, 1204)), False),  # "Confirmar diálogo al
                                                                                        # activar el portal"
}
# Windows only (Linux keeps its exact fingerprints above and its reading as it was: it works there). On Windows a
# label's white count moves a few pixels with the list's fractional scroll position (live 2026-11-12, English):
# "Use scientific notation" 720/722/723/731, "Disable custom cursor" 713/721, "Rounded bulk buy" 706/712, "Hide
# locked..." 911/929, "Confirm..." 1359/1360. So on Windows an English label is its exact right edge and a white
# count in a range around those. 680 is the only right edge two labels of the Windows list share (the whole list
# measured): those two are told by their first letter, the white pixels in the label's first 6 columns ("U" 29,
# "D" 39, the same in every reading). Entry: right edge, white count range, first-letter range or None.
ON_WINDOWS = sys.platform == "win32"
FIRST_LETTER_COLUMNS = 6
WINDOWS_SETTINGS: dict[str, tuple[int, tuple[int, int], tuple[int, int] | None]] = {
    "Use scientific notation": (680, (705, 745), (20, 34)),
    "Disable custom cursor": (680, (700, 735), (35, 50)),
    "Rounded bulk buy": (635, (690, 725), None),
    "Hide locked Quest rewards": (731, (895, 945), None),
    "Confirm dialogue when activating the Portal": (846, (1330, 1390), None),
}


def _windows_label(name: str, right: int, white: int, first_letter: int) -> bool:
    """Whether a label on the Windows build is the setting `name` (see WINDOWS_SETTINGS)."""
    edge, (low, high), letter = WINDOWS_SETTINGS[name]
    return (right == edge and low <= white <= high
            and (letter is None or letter[0] <= first_letter <= letter[1]))


# The "Settings" button's label in the "⋮" menu, width and white pixels: "Settings", "Ajustes".
SETTINGS_LABELS = ((89, 558), (83, 535))
OFF, ON = (0xF8, 0x33, 0x08), (0x1D, 0xD7, 0x00)
APPLY_GREEN, CANCEL_RED = 0x00A400, 0xAF0000
# The list differs between builds: the Windows one lacks "Portrait" and more, and is 285 px shorter above the
# settings (2026-10-28), so fixed scrolls missed four of them there. It's read from its top a page at a time:
# 300 px of the 432 the list shows, so every row is whole on some page. 12 pages pass the Linux list's end (~58
# notches); the Linux settings are all read 42 notches down.
PAGE_NOTCHES = 6
MAX_PAGES = 12
# Windows only: the list usually opens at its top, but on 2026-11-12 it opened ~300 px down. Wheeling up past
# the top stretches the list, which springs back by fractions of a pixel for ~3 s (live: the labels' white
# counts kept changing until then). The dialog is half transparent over the running game, so only the white
# text tells when it has settled: it must stay the same for STILL_MS.
TOP_NOTCHES = PAGE_NOTCHES * MAX_PAGES
STILL_STEP_MS, STILL_MS, STILL_TIMEOUT_MS = 250, 500, 5000


def _bands(white: np.ndarray) -> list[tuple[int, int]]:
    """The runs of rows that hold white pixels: (first, end)."""
    rows = white.any(axis=1)
    bands, y = [], 0
    while y < len(rows):
        if rows[y]:
            start = y
            while y < len(rows) and rows[y]:
                y += 1
            bands.append((start, y))
        y += 1
    return bands


def read_toggles(game: Game) -> dict[str, bool]:
    """The settings on screen in the dialog's list, by name: whether each is on."""
    pixels = game.grab(373, 126, 908, 566)  # client x 365-900, y 95-535
    white = (pixels[:, 80:] == 255).all(axis=2)  # the labels, from client x 445
    found: dict[str, bool] = {}
    for start, end in _bands(white):
        band = white[start:end]
        columns = np.nonzero(band.any(axis=0))[0]
        label = (int(columns.max()) + 445, int(band.sum()))
        first_letter = int(band[:, columns.min():columns.min() + FIRST_LETTER_COLUMNS].sum())
        for name, (fingerprints, _) in SETTINGS.items():
            if label in fingerprints or (ON_WINDOWS and _windows_label(name, *label, first_letter)):
                box = pixels[max(0, start - 8):end + 8, :75]  # the toggle, client x 365-439
                found[name] = int((box == ON).all(axis=2).sum()) > int((box == OFF).all(axis=2).sum())
    return found


def _list_text(game: Game) -> np.ndarray:
    """The list's white pixels (its text): the only part that doesn't change with the game behind it."""
    return (game.grab(373, 126, 908, 566) == 255).all(axis=2)


def scroll_to_top(game: Game) -> None:
    """Wheel the list up to its top and wait until its text stops moving (or STILL_TIMEOUT_MS pass)."""
    game.wheel(up=True, notches=TOP_NOTCHES)
    deadline = game.now() + STILL_TIMEOUT_MS
    previous, still_since = _list_text(game), game.now()
    while game.now() < deadline:
        game.sleep(STILL_STEP_MS)
        current = _list_text(game)
        if not np.array_equal(current, previous):
            previous, still_since = current, game.now()
        elif game.now() - still_since >= STILL_MS:
            return


def find_settings_button(game: Game) -> tuple[int, int] | None:
    """Where to click the "⋮" menu's Settings button (AutoIt), found by its label; None if it isn't there.
    The menu's left column is searched: an event's card above the buttons comes and goes."""
    white = (game.grab(840, 161, 1024, 656) == 255).all(axis=2)  # client x 832-1016, y 130-625
    for start, end in _bands(white):
        columns = np.nonzero(white[start:end].any(axis=0))[0]
        if (int(columns[-1] - columns[0] + 1), int(white[start:end].sum())) in SETTINGS_LABELS:
            return 840 + int(columns[0] + columns[-1]) // 2, 161 + start - 15
    return None


def _close(game: Game) -> None:
    """Cancel the dialog if it shows (it's modal: the shop's X takes no click under it), then close the shop.
    The dialog fades out after Cancel and an X click then did nothing (live, 2026-10-28): the X is clicked
    again if the shop is still open a second later, never sooner (a click while it closes leaves an empty
    panel that takes every click, see Shop.close_if_open)."""
    if game.pixel_is(791, 631, CANCEL_RED):
        game.click(791, 631)  # Cancel: changes nothing
        deadline = game.now() + 2000
        while game.pixel_is(791, 631, CANCEL_RED) and game.now() < deadline:
            game.sleep(50)
        game.sleep(300)
    for _ in range(2):
        game.click(1244, 712)  # close the shop
        game.sleep(1000)
        if not game.pixel_search(807, 140, 807, 155, 0xFFFFFF):  # the shop's corner, as in Shop.open_shop
            return


def check_game_settings(game: Game, shop: Shop) -> bool:
    """Open the settings, read the ones the bot needs, close them with Cancel and log what's wrong. True only
    when every one was found and right."""
    shop.close_if_open()
    if not shop.open_shop():
        event("Game settings not checked", reason="shop not open")
        return False
    game.click(1158, 696)  # the "⋮" tab: inside it in both tab bars (see shop.X_TAB_RED)
    button = None
    deadline = game.now() + 2000
    while game.pixel_search(1130, 700, 1130, 700, TAB_SELECTED, variation=6) is None and game.now() < deadline:
        game.sleep(20)  # the selected shade fades in (5A251A-62271C), as in Shop.tab_shown
    if game.pixel_search(1130, 700, 1130, 700, TAB_SELECTED, variation=6):
        game.sleep(200)
        button = find_settings_button(game)
    if button is None:
        event("Game settings not checked", reason="no Settings button")
        game.save_frame("settings-menu-not-shown")
        game.click(1244, 712)  # close the shop
        return False
    game.click(*button)
    # The dialog grows from the middle as it opens: Apply reaches (428, 631) last (seen live, 2026-10-28).
    deadline = game.now() + 3000
    while not (game.pixel_is(791, 631, CANCEL_RED) and game.pixel_is(428, 631, APPLY_GREEN)):
        if game.now() > deadline:
            event("Game settings not checked", reason="dialog not shown")
            game.save_frame("settings-dialog-not-shown")
            _close(game)
            return False
        game.sleep(50)
    game.sleep(300)
    found: dict[str, bool] = {}
    game.move(916, 331)  # between the list and its scrollbar: no control there
    if ON_WINDOWS:
        scroll_to_top(game)
    for _ in range(MAX_PAGES):
        game.wheel(up=False, notches=PAGE_NOTCHES)
        game.sleep(500)  # a notch is usually drawn within 30 ms
        found |= read_toggles(game)
        if len(found) == len(SETTINGS):
            break
    if len(found) < len(SETTINGS):
        game.save_frame("settings-not-found")
    _close(game)
    wrong = []
    for name, (_, needed) in SETTINGS.items():
        if name not in found:
            event("Game setting not found", setting=name)
        elif found[name] != needed:
            event("Game setting wrong", setting=name, should_be="on" if needed else "off")
            wrong.append(name)
    missing = [name for name in SETTINGS if name not in found]
    event("Game settings checked", wrong=wrong, missing=missing)
    return not wrong and not missing
