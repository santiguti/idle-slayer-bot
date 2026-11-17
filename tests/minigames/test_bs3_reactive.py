from pathlib import Path

import numpy as np
import pytest

from idle_runner.minigames.bs3_reactive import (ORB, Speed, air_time, high_jump_lands, orbs_above, plan,
                                                platforms, play_section, player, section_done)
from tests.fakes import read_png

FIXTURES = Path(__file__).parents[1] / "fixtures" / "bonus_stage"


def frame(name: str) -> np.ndarray:
    return read_png(FIXTURES / f"{name}.png")


def draw_platform(img: np.ndarray, left: int, right: int, top: int) -> None:
    """A BS3 platform in client coordinates: dark gap, B9BBFC top edge, light body."""
    img[top - 3:top, left:right + 1] = (0x15, 0x15, 0x15)
    img[top:top + 3, left:right + 1] = (0xB9, 0xBB, 0xFC)
    img[top + 3:top + 40, left:right + 1] = (0x91, 0x9E, 0xB7)


def draw_runner(img: np.ndarray, feet: int) -> None:
    """The running player: magenta from its trail (x 40) to its front (x 135), feet on a top at `feet`."""
    img[feet - 80:feet - 4, 40:136] = (0xE3, 0x2C, 0xFF)


def holds(fake) -> list[tuple[float, float]]:
    """(press time, held ms) of every Up press, from the timed key log."""
    out, down = [], None
    for t, action in fake.timed:
        if action[0] == "key" and action[1] == "Up":
            if action[2]:
                down = t
            elif down is not None:
                out.append((down, t - down))
                down = None
    return out


@pytest.fixture
def timed(fake):
    fake.timed = []
    fake.on_action = lambda action: fake.timed.append((fake.t, action))
    return fake


# --- reading the screen ---

def test_a_platform_keeps_its_width_under_the_boost_trail() -> None:
    """17:37:06: the boost trail hid the block's top edge under the player (0-133 looked like its end); its body,
    15 px lower, shows the whole block."""
    img = frame("bs3-boost-trail-on-block")

    assert (0, 198, 363) in platforms(img)
    assert player(img)[1] >= 160  # the trail itself: the boost is on


def test_the_player_is_found_in_its_darker_shade_after_a_fall() -> None:
    assert player(frame("bs3-player-dark")) is not None


@pytest.mark.parametrize(("name", "done"), [("bs3-section-banner", True), ("bs3-s4-wall", False),
                                            ("bs3-s4-grid", False)])
def test_the_section_completed_banner(name: str, done: bool) -> None:
    assert section_done(frame(name)) is done


def test_orbs_hanging_over_a_tall_block() -> None:
    assert orbs_above(frame("bs3-s4-grid"), 260) > 30
    assert orbs_above(frame("bs3-s4-wall"), 466) == 0


def test_speed_ignores_stale_grabs() -> None:
    """A grab can be a stale picture (the game hasn't redrawn yet): no motion against the previous grab. The
    estimate compares against grabs 120-300 ms old instead."""
    speed, x, v = Speed(), 1200.0, 0.0
    for i in range(60):
        t = i * 0.01
        if i % 3:  # two of every three grabs are fresh
            x = 1200 - 485 * t
        v = speed.update(t, [(int(x), int(x) + 96, 260)], 1280)
    assert 430 <= v <= 540


# --- deciding ---

def test_air_time_depends_on_the_height_to_land_at() -> None:
    assert air_time("up", 206) == pytest.approx(0.62)
    assert air_time("up", 103) == pytest.approx(0.80)
    assert air_time("same", 0) == pytest.approx(0.70)
    assert air_time("down", -103) == pytest.approx(0.90)


@pytest.mark.parametrize(("ground", "plats", "v", "expected"), [
    # pillar to pillar, 360 px apart: jump now
    ((50, 146, 260), [(410, 506, 260)], 485, ("jump", "same", (410, 506, 260))),
    # the next pillar still too far, but in reach before this block ends: wait
    ((50, 600, 260), [(700, 796, 260)], 485, ("wait", "same", (700, 796, 260))),
    # out of reach even from this pillar's end: no plan (the edge jump is the caller's)
    ((50, 300, 260), [(700, 796, 260)], 485, (None, "same", None)),
    # a low block right below the pillar's end: walk off and drop
    ((83, 179, 260), [(289, 487, 466), (597, 693, 260)], 485, ("drop", "down", (289, 487, 466))),
    # from the ground up to the first pillar
    ((0, 260, 466), [(370, 466, 260)], 485, ("jump", "up", (370, 466, 260))),
    # boosted (~900 px/s) on the wide block: the small block would be overshot, the wide low one is reached
    ((0, 198, 363), [(462, 609, 363), (719, 969, 466), (1079, 1175, 260)], 900, ("jump", "down", (719, 969, 466))),
])
def test_plan(ground, plats, v, expected) -> None:
    assert plan(ground, [ground, *plats], v) == expected


def test_a_high_jump_needs_somewhere_to_land() -> None:
    assert high_jump_lands((75, 840, 260), [(75, 840, 260), (847, 1279, 466)], 880) == (847, 1279, 466)
    assert high_jump_lands((50, 146, 260), [(50, 146, 260), (410, 506, 260)], 485) is None


# --- playing ---

def test_hops_to_the_next_pillar_with_a_short_hold(game, timed) -> None:
    draw_platform(timed.frame, 50, 146, 260)
    draw_platform(timed.frame, 410, 506, 260)
    draw_runner(timed.frame, 260)

    play_section(game, "BonusStage3-s1", max_ms=200)

    assert [ms for _, ms in holds(timed)][:1] == [pytest.approx(80, abs=5)]


def test_waits_while_the_next_pillar_is_out_of_reach(game, timed) -> None:
    draw_platform(timed.frame, 50, 300, 260)
    draw_platform(timed.frame, 700, 796, 260)
    draw_runner(timed.frame, 260)

    play_section(game, "BonusStage3-s1", max_ms=500)

    assert holds(timed) == []


def test_walks_off_onto_a_lower_block(game, timed) -> None:
    draw_platform(timed.frame, 0, 160, 260)
    draw_platform(timed.frame, 240, 438, 466)
    draw_runner(timed.frame, 260)

    play_section(game, "BonusStage3-s1", max_ms=500)

    assert holds(timed) == []


def test_a_wall_gets_the_longest_hold(game, timed) -> None:
    """S4 starts against a tall block's wall (19:05: 28 s stuck); standing still there the trail leaves the
    feet, so the magenta ends ~45 px above the top."""
    timed.frame[:] = frame("bs3-s4-wall")

    play_section(game, "BonusStage3-s4", max_ms=200)

    assert [ms for _, ms in holds(timed)][:1] == [pytest.approx(300, abs=5)]


def test_orb_grids_are_jumped_through_when_the_jump_can_land(game, timed) -> None:
    draw_platform(timed.frame, 75, 840, 260)
    draw_platform(timed.frame, 847, 1279, 466)
    draw_runner(timed.frame, 260)
    timed.frame[100:180, 150:400] = ORB

    play_section(game, "BonusStage3-s4", max_ms=200)
    assert holds(timed) == []  # without hops it drops off the end later

    play_section(game, "BonusStage3-s4", max_ms=200, hops=True)
    assert [ms for _, ms in holds(timed)][:1] == [pytest.approx(150, abs=5)]


def test_stops_at_the_section_banner(game, timed, events) -> None:
    timed.frame[:] = frame("bs3-section-banner")

    play_section(game, "BonusStage3-s1", max_ms=30_000)

    assert timed.t < 1000
    assert [(r["where"], r["end"]) for r in events() if r["event"] == "Bonus stage section played"] == [
        ("BonusStage3-s1", "banner")]


def test_stops_at_second_wind_once_its_button_takes_clicks(game, timed, events) -> None:
    timed.cost_ms = 50
    timed.paint(615, 590, 0x00A400)

    play_section(game, "BonusStage3-s1", max_ms=30_000)

    assert 3000 <= timed.t < 6000
    assert [r["end"] for r in events() if r["event"] == "Bonus stage section played"] == ["second wind"]
