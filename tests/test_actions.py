from pathlib import Path

import pytest

from idle_runner.actions import box_beside_panel, box_on_screen, close_all
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
