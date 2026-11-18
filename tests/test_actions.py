from pathlib import Path

import pytest

from idle_runner.actions import PANEL_X_RED, box_beside_panel, box_on_screen, close_all, close_panel, open_ascension_tab
from tests.fakes import read_png

FIXTURES = Path(__file__).parent / "fixtures" / "boxes"


@pytest.mark.parametrize(("name", "expected"), [
    ("silver-box", True),              # flying in (recorded 2026-10-23, shop open on the right)
    ("silver-box-over-player", True),  # hovering over the player, waiting to be hit
    ("orange-box", True),              # recorded 2026-10-23 (logs/recordings/2026-10-23-boxes, frame 518)
    ("orange-box-hovering", True),     # frame 170: the sword box waiting to be hit
    ("no-box", False),
    ("no-box-wasps", False),
])
def test_floating_box_is_detected(game, fake, name: str, expected: bool) -> None:
    fake.frame[100:480, 0:790] = read_png(FIXTURES / f"{name}.png")  # client area, as recorded

    assert box_on_screen(game) is expected


@pytest.mark.parametrize(("name", "expected"), [
    ("beside-panel-silver", True),   # black box 2026-11-12 00:36:15, the Minions tab open on the left
    ("beside-panel-orange", True),   # 00:43:42, the sword box flying in
    ("beside-panel-none", False),    # 00:36:12, the Minions tab open, nothing in the run
    ("beside-panel-coins", False),   # 00:43:44, coins and gems (the box was already on the left)
    # 00:39:04: the shop open, its quest "Hit 20 Random Boxes" with the box's own icon. After a routine stopped by
    # a focus loss, the shop stayed open under the ascension panel (00:45:42-00:46:35).
    ("beside-panel-shop-quests", False),
])
def test_a_box_is_seen_beside_the_ascension_panel(game, fake, name: str, expected: bool) -> None:
    fake.frame[100:480, 640:1280] = read_png(FIXTURES / f"{name}.png")  # client x 640-1279, as recorded

    assert box_beside_panel(game) is expected


def test_close_all_does_not_blind_the_main_loop(game, fake) -> None:
    start = fake.t

    close_all(game)

    assert fake.t - start < 100  # the original slept 2 s here, every 5 s


def test_close_panel_waits_until_the_panel_is_gone(game, fake) -> None:
    # 2026-11-16 21:07:44: the bonus sample closed the panel and auto_ascend, 38 ms later, still saw its X tab,
    # so it clicked the Ascension tab of a closing panel and waited 2 s for nothing.
    fake.paint(538, 681, PANEL_X_RED)
    closed_at: list[float] = []

    def act(action: tuple) -> None:
        if action == ("click", 570 - 8, 694 - 31):
            closed_at.append(fake.t + 100)

    def sleep(ms: float) -> None:
        fake.t += ms
        if closed_at and fake.t >= closed_at[0]:
            fake.paint(538, 681, 0)

    fake.on_action = act
    fake.sleep_ms = sleep
    close_panel(game)

    assert fake.clicks() == [(570, 694)]
    assert closed_at[0] <= fake.t < closed_at[0] + 50
    open_ascension_tab(game)
    assert fake.clicks()[1] == (95, 90)  # the ascension button: the panel is closed


def test_open_ascension_tab_closes_the_shop_first(game, fake) -> None:
    # 2026-11-12 20:08 and 20:10: the bot started with the shop open; the ascension button does nothing then,
    # so send_minions waited 2 x 2 s and gave up.
    fake.paint(807, 140, 0xFFFFFF)  # the shop's corner
    fake.on_action = lambda a: fake.paint(807, 140, 0) if a == ("click", 1244 - 8, 712 - 31) else None
    open_ascension_tab(game)

    assert fake.clicks()[:2] == [(1244, 712), (95, 90)]


def test_open_ascension_tab_lets_a_closing_shop_close(game, fake) -> None:
    # Live 2026-11-17 10:49:04: auto_upgrade closed the shop and its corner still showed 40 ms later. A click on
    # the X tab of a closing shop leaves a dark panel that takes every click (Shop.close_if_open).
    fake.paint(807, 140, 0xFFFFFF)
    sleep = fake.sleep_ms
    start = fake.t

    def closing(ms: float) -> None:
        sleep(ms)
        if fake.t - start >= 100:
            fake.paint(807, 140, 0)

    fake.sleep_ms = closing
    open_ascension_tab(game)

    assert (1244, 712) not in fake.clicks() and fake.clicks()[0] == (95, 90)
