from pathlib import Path

import numpy as np
import pytest

from idle_runner import game_settings
from idle_runner.game_settings import check_game_settings, find_settings_button, read_toggles
from idle_runner.shop import Shop
from tests.fakes import OFFSET, read_png

FIXTURES = Path(__file__).parent / "fixtures" / "game_settings"
# Recorded live on 2026-10-28 (Santi's settings): the shop's "⋮" menu, and the Settings dialog at its top and
# 33 and 39 wheel notches down.
MENU, TOP, AT33, AT39 = (read_png(FIXTURES / f"{name}.png") for name in ("menu", "top", "at33", "at39"))
# The same with the game in Spanish (2026-10-28): "Ajustes", "Usar notación científica", ...
ES_MENU, ES_TOP, ES_AT33, ES_AT39 = (read_png(FIXTURES / f"es-{name}.png") for name in ("menu", "top", "at33", "at39"))
# The list's content (client x 365-900) from 1,200 px down (24 notches, the Accessibility section's "Key
# Bindings" row) to "Vibration", on Linux: stitched from frames 6 notches apart (live, 2026-10-28 21:56).
LIST = read_png(FIXTURES / "list.png")
LINUX_LIST_AT = 1200
# The Windows build's list is 285 px shorter above the settings (no "Portrait" and more; frames of
# 2026-10-28 21:14): "Rounded bulk buy" at client y 111 after 33 notches, at 396 on Linux.
WINDOWS_LIST_AT = LINUX_LIST_AT - 285
# The Windows list's content (client x 365-900, y 95-535) read from its top 24 and 30 notches down (live,
# 2026-11-12). Its labels have a few white pixels more or less than on Linux: "Use scientific notation" 723
# (722), "Rounded bulk buy" 712 (700), "Confirm dialogue..." 1359 (1360); the other two are equal.
WIN_AT24, WIN_AT30 = (read_png(FIXTURES / f"win-at{n}.png") for n in (24, 30))
# The same page after the list was wheeled up past its top and settled: "Use scientific notation" 720 (the
# counts on Windows move a few pixels with the list's fractional position; live 2026-11-12).
WIN_AT24_SETTLED = read_png(FIXTURES / "win-at24-settled.png")


@pytest.fixture(autouse=True)
def linux(monkeypatch) -> None:
    """Every test runs the Linux behaviour (whatever OS runs the suite) unless it asks for `windows`."""
    monkeypatch.setattr(game_settings, "ON_WINDOWS", False)


@pytest.fixture
def windows(monkeypatch) -> None:
    monkeypatch.setattr(game_settings, "ON_WINDOWS", True)


def windows_page(content: np.ndarray, top: np.ndarray = TOP) -> np.ndarray:
    """The dialog with a recorded page of the Windows list in it."""
    frame = top.copy()
    frame[95:536, 365:901] = content
    return frame


def test_reads_the_toggles_on_screen(game, fake) -> None:
    fake.frame[:] = AT33
    assert read_toggles(game) == {"Use scientific notation": False, "Disable custom cursor": True,
                                  "Rounded bulk buy": True, "Hide locked Quest rewards": True}
    fake.frame[:] = AT39
    assert read_toggles(game) == {"Hide locked Quest rewards": True,
                                  "Confirm dialogue when activating the Portal": False}


def test_reads_the_toggles_with_the_game_in_spanish(game, fake) -> None:
    fake.frame[:] = ES_AT33
    assert read_toggles(game) == {"Use scientific notation": False, "Disable custom cursor": True,
                                  "Rounded bulk buy": True, "Hide locked Quest rewards": True}
    fake.frame[:] = ES_AT39
    assert read_toggles(game) == {"Hide locked Quest rewards": True,
                                  "Confirm dialogue when activating the Portal": False}


def test_reads_the_toggles_on_the_windows_build(game, fake, windows) -> None:
    # 2026-11-12: every Windows start since 10-28 found only "Disable custom cursor" and "Hide locked Quest
    # rewards"; the other three labels' white counts differ from the Linux ones.
    fake.frame[:] = windows_page(WIN_AT24)
    assert read_toggles(game) == {"Use scientific notation": False, "Disable custom cursor": True}
    fake.frame[:] = windows_page(WIN_AT30)
    assert read_toggles(game) == {"Rounded bulk buy": True, "Hide locked Quest rewards": True,
                                  "Confirm dialogue when activating the Portal": False}


def test_windows_reads_labels_drawn_a_fraction_of_a_pixel_elsewhere(game, fake, windows) -> None:
    # Seen live: "Use scientific notation" 720, 722, 723, 731; "Disable custom cursor" 713, 721; both end at
    # x 680, so their first letter ("U", "D") tells them apart.
    fake.frame[:] = windows_page(WIN_AT24_SETTLED)
    assert read_toggles(game) == {"Use scientific notation": False, "Disable custom cursor": True}


def test_windows_tells_the_two_labels_ending_at_680_by_their_first_letter(game, fake, windows) -> None:
    # Swap the two rows' labels: each is still read by its own letter, not by its place.
    page = WIN_AT24.copy()
    sci, cursor = page[314 - 95:329 - 95, 80:].copy(), page[394 - 95:409 - 95, 80:].copy()
    page[314 - 95:329 - 95, 80:], page[394 - 95:409 - 95, 80:] = cursor, sci
    fake.frame[:] = windows_page(page)
    assert read_toggles(game) == {"Disable custom cursor": False, "Use scientific notation": True}


def test_linux_reads_only_its_own_fingerprints(game, fake) -> None:
    # The Windows counts are a Windows-only addition: Linux reads exactly what it read before.
    fake.frame[:] = windows_page(WIN_AT24)
    assert read_toggles(game) == {"Disable custom cursor": True}
    fake.frame[:] = windows_page(WIN_AT30)
    assert read_toggles(game) == {"Hide locked Quest rewards": True}


def test_a_list_elsewhere_reads_nothing(game, fake) -> None:
    fake.frame[:] = TOP
    assert read_toggles(game) == {}


def test_finds_the_settings_button_by_its_label(game, fake) -> None:
    fake.frame[:] = MENU
    assert find_settings_button(game) == (930, 558)  # client (922, 527), on the button above its label
    fake.frame[:] = TOP
    assert find_settings_button(game) is None
    fake.frame[:] = ES_MENU  # "Ajustes"
    assert find_settings_button(game) == (930, 558)


def show_list(fake, scrolled: int, list_at: int, content: np.ndarray) -> None:
    """The dialog's list (client y 101-532) scrolled `scrolled` px down; `content` starts `list_at` px into it
    (blank rows stand for the Screen and Audio sections above and for the end below)."""
    rows = np.full((432, 536, 3), 0x13, np.uint8)
    for y in range(432):
        if 0 <= (row := scrolled + y - list_at) < len(content):
            rows[y] = content[row]
    fake.frame[101:533, 365:901] = rows


def play_settings(fake, list_at: int = LINUX_LIST_AT, content: np.ndarray = LIST, pages: dict | None = None,
                  menu=MENU, top=TOP, opens_at: int = 0) -> None:
    """The shop opens (its corner and tab bar), "⋮" shows the menu, Settings opens the dialog `opens_at`
    notches down (its top by default), each wheel notch scrolls the list 50 px (never above its top) and
    Cancel goes back. `pages`: recorded frames shown at those notch counts instead (each stands in for the
    page it was recorded near)."""
    notches = [opens_at]

    def act(action: tuple) -> None:
        if action[0] == "button" and action[1] in (4, 5) and action[2]:
            notches[0] = max(0, notches[0] + (1 if action[1] == 5 else -1))
            fake.frame[:] = top
            if pages and notches[0] in pages:
                fake.frame[:] = pages[notches[0]]
            else:
                show_list(fake, 50 * notches[0], list_at, content)
        if action[0] != "click":
            return
        click = (action[1] + OFFSET[0], action[2] + OFFSET[1])
        if click == (1163, 655):  # the shop button
            fake.frame[:] = menu  # the corner and the tab bar are what open_shop looks at
        elif click == (1158, 696):  # the "⋮" tab
            fake.frame[:] = menu
        elif click == (930, 558):  # Settings
            fake.frame[:] = top
            if opens_at:
                show_list(fake, 50 * notches[0], list_at, content)
        elif click == (791, 631):  # Cancel
            fake.frame[:] = menu
        elif click == (1244, 712):  # the shop's X
            fake.frame.fill(0)

    fake.on_action = act


def wheel_notches(fake) -> int:
    return fake.actions.count(("button", 5, True))


def test_checks_the_settings_and_only_cancels(game, fake, events) -> None:
    play_settings(fake)
    assert check_game_settings(game, Shop(game))  # all found and right

    names = [r["event"] for r in events()]
    assert "Game setting wrong" not in names and "Game setting not found" not in names
    assert names.count("Game settings checked") == 1
    assert (503, 631) not in fake.clicks()  # never Apply
    assert fake.clicks()[-2:] == [(791, 631), (1244, 712)]  # Cancel, then the shop's X


def test_reads_the_whole_list_a_page_at_a_time_and_stops_once_all_are_found(game, fake) -> None:
    play_settings(fake)
    assert check_game_settings(game, Shop(game))

    assert wheel_notches(fake) == 42  # "Confirm dialogue..." shows 42 notches down; the list goes on to ~58


def test_reads_the_shorter_windows_list(game, fake, events) -> None:
    # 2026-10-28 on Windows: 33 and 39 notches (the Linux list's places) showed four of them cut off or
    # scrolled past, and they were all reported "not found".
    play_settings(fake, list_at=WINDOWS_LIST_AT)
    assert check_game_settings(game, Shop(game))


def test_checks_the_settings_on_the_windows_build(game, fake, events, windows) -> None:
    play_settings(fake, content=LIST[:0], pages={24: windows_page(WIN_AT24), 30: windows_page(WIN_AT30)})
    assert check_game_settings(game, Shop(game))

    assert not [r for r in events() if r["event"] == "Game setting not found"]


def wheels(fake) -> list[int]:
    return [a[1] for a in fake.actions if a[0] == "button" and a[2]]  # 4 up, 5 down


def test_windows_reads_the_list_from_its_top_when_it_opens_scrolled_down(game, fake, events, windows) -> None:
    # Live 2026-11-12 (Windows): the dialog opened with its list ~300 px from the top (it usually opens at
    # the top); 6-notch pages then miss rows, and the labels at other heights have other white counts (the
    # 11-09 23:11 start found none of the five).
    play_settings(fake, opens_at=40)
    assert check_game_settings(game, Shop(game))

    assert wheels(fake)[0] == 4  # up first
    assert wheels(fake).count(5) == 42  # then the same pages as from the top


def test_windows_waits_for_the_text_to_stop_after_wheeling_up(game, fake, windows) -> None:
    # Live 2026-11-12: past the top the list springs back by fractions of a pixel for ~3 s (its labels' white
    # counts keep changing), while the half-transparent dialog shows the running game behind it, so the
    # pixels never stay the same. Only the white text tells when it has settled.
    play_settings(fake, opens_at=40)
    played, grab = fake.on_action, fake.grab
    wheeled_up_at: list[float] = []
    wheeled_down_at: list[float] = []

    def act(action: tuple) -> None:
        played(action)
        if action[0] == "button" and action[1] == 4 and not wheeled_up_at:
            wheeled_up_at.append(fake.t)
        if action[0] == "button" and action[1] == 5:
            wheeled_down_at.append(fake.t)

    def springing(x: int, y: int, w: int, h: int):
        region = grab(x, y, w, h).copy()
        if (w, h) != (536, 441):  # only the list
            return region
        region[-1, :, :] = int(fake.t) % 200  # the game behind the dialog never stops (never white)
        if wheeled_up_at and fake.t < wheeled_up_at[0] + 3000:
            region[0, int(fake.t) % w] = 255  # the text still moves
        return region

    fake.on_action, fake.grab = act, springing
    assert check_game_settings(game, Shop(game))

    assert wheeled_down_at[0] >= wheeled_up_at[0] + 3000


def test_linux_never_wheels_up(game, fake) -> None:
    play_settings(fake)
    assert check_game_settings(game, Shop(game))

    assert 4 not in wheels(fake)


def test_checks_the_settings_with_the_game_in_spanish(game, fake, events) -> None:
    play_settings(fake, content=LIST[:0], pages={30: ES_AT33, 36: ES_AT39}, menu=ES_MENU, top=ES_TOP)

    assert check_game_settings(game, Shop(game))
    assert (428, 631) not in fake.clicks()  # never Aplicar


def test_reports_a_wrong_setting(game, fake, events) -> None:
    content = LIST.copy()
    # Rounded bulk buy's row (label at y 738-753 of the list) turned off: the red cross instead of the green tick.
    toggle = content[724:769, 0:75]
    toggle[(toggle == (0x1D, 0xD7, 0x00)).all(axis=2)] = (0x39, 0x39, 0x39)
    content[729:764, 3:45] = (0xF8, 0x33, 0x08)
    play_settings(fake, content=content)
    assert not check_game_settings(game, Shop(game))

    wrong = [r for r in events() if r["event"] == "Game setting wrong"]
    assert [(r["setting"], r["should_be"]) for r in wrong] == [("Rounded bulk buy", "on")]


def test_a_list_it_cannot_read_reports_every_setting_missing(game, fake, events) -> None:
    # E.g. the game in another language: no label matches.
    play_settings(fake, content=LIST[:0])
    assert not check_game_settings(game, Shop(game))

    missing = [r["setting"] for r in events() if r["event"] == "Game setting not found"]
    assert len(missing) == 5


def test_without_the_menu_nothing_is_clicked_inside_it(game, fake, events) -> None:
    play_settings(fake)
    real = fake.on_action

    def menu_never_opens(action: tuple) -> None:
        if action[0] == "click" and (action[1] + OFFSET[0], action[2] + OFFSET[1]) == (1158, 696):
            fake.frame[600:720, 780:1280] = 0  # e.g. the click was lost: no "⋮" tab selected
            return
        real(action)

    fake.on_action = menu_never_opens
    assert not check_game_settings(game, Shop(game))

    assert (930, 558) not in fake.clicks()
    assert any(r["event"] == "Game settings not checked" for r in events())


def narrow_dialog_for(fake, ms: float) -> None:
    """The dialog grows from the middle when it opens (seen live on 2026-10-28): for `ms` after Settings is
    clicked, Cancel is already red at (791, 631) but Apply hasn't reached (428, 631) yet."""
    opened_at: list[float] = []
    played = fake.on_action
    grab = fake.grab

    def act(action: tuple) -> None:
        played(action)
        if action[0] == "click" and (action[1] + OFFSET[0], action[2] + OFFSET[1]) == (930, 558):
            opened_at.append(fake.t)

    def growing(x: int, y: int, w: int, h: int):
        region = grab(x, y, w, h)
        if opened_at and fake.t < opened_at[-1] + ms and x <= 420 < x + w and y <= 600 < y + h:
            region = region.copy()
            region[600 - y, 420 - x] = (0x11, 0x11, 0x11)
        return region

    fake.on_action = act
    fake.grab = growing


def test_waits_for_the_dialog_to_finish_opening(game, fake, events) -> None:
    play_settings(fake)
    narrow_dialog_for(fake, 500)
    check_game_settings(game, Shop(game))

    assert [r["event"] for r in events()].count("Game settings checked") == 1


def test_a_dialog_that_never_settles_is_cancelled_before_the_shop_closes(game, fake, events) -> None:
    play_settings(fake)
    narrow_dialog_for(fake, 60_000)
    check_game_settings(game, Shop(game))

    assert any(r["event"] == "Game settings not checked" for r in events())
    assert fake.clicks()[-2:] == [(791, 631), (1244, 712)]  # a modal dialog takes no click on the shop's X


def test_closes_the_shop_even_when_the_first_x_is_swallowed(game, fake) -> None:
    # Live 2026-10-28: right after Cancel the dialog still fades out and the shop's X click did nothing.
    play_settings(fake)
    played = fake.on_action
    x_clicks: list[float] = []

    def first_x_swallowed(action: tuple) -> None:
        if action[0] == "click" and (action[1] + OFFSET[0], action[2] + OFFSET[1]) == (1244, 712):
            x_clicks.append(fake.t)
            if len(x_clicks) == 1:
                return
        played(action)

    fake.on_action = first_x_swallowed
    check_game_settings(game, Shop(game))

    assert len(x_clicks) == 2 and x_clicks[1] - x_clicks[0] >= 1000  # not while it might be closing
    assert not fake.frame.any()  # closed
