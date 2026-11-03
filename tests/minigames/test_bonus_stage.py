from pathlib import Path

import pytest

from idle_runner.minigames.bonus_stage import (BS2_SECTIONS, bonus_stage, bs2_section, bs3_section1, run_bs2, run_bs3,
                                               stage_number)
from idle_runner.minigames.common import slider_showing
from tests.fakes import read_png

FIXTURES = Path(__file__).parents[1] / "fixtures" / "bonus_stage"


def test_bs2_stops_and_logs_when_the_stage_fails(game, fake, event_names) -> None:
    fake.paint(716, 600, 0xAF0000)  # the fail screen's close button
    run_bs2(game, sb=False)

    names = event_names()
    assert "BonusStage2" in names and "BonusStage2 Failed" in names
    assert "BonusStage2 Section 1 Complete" not in names
    assert (716, 600) in fake.clicks()


def test_bs3_retries_one_failed_section_once(game) -> None:
    calls = []
    pending_failures = {1: 1}  # section index 1 fails once

    def make(index: int):
        def section(g, sb: bool) -> bool:
            calls.append(index)
            if pending_failures.get(index):
                pending_failures[index] -= 1
                return False
            return True
        return section

    run_bs3(game, False, sections=tuple(make(i) for i in range(4)))

    assert calls == [0, 1, 1, 2, 3]


def test_bs3_gives_up_after_the_second_failure(game) -> None:
    calls = []

    def ok(g, sb: bool) -> bool:
        calls.append("ok")
        return True

    def bad(g, sb: bool) -> bool:
        calls.append("bad")
        return False

    run_bs3(game, False, sections=(ok, bad, ok, ok))

    assert calls == ["ok", "bad", "bad"]


def test_skip_bonus_stage_waits_for_the_fail_screen(game, fake, event_names) -> None:
    fake.paint(716, 600, 0xAF0000)
    bonus_stage(game, skip=True)

    names = event_names()
    assert "Do nothing BonusStage Active" in names and "BonusStage2 Failed" in names


def test_bonus_stage_returns_once_the_run_is_back(game, fake) -> None:
    # Live 2026-10-28 20:17: the reward run, "Bonus Stage Completed!" and the fade lasted 14 s after the last
    # section, and the shop and ascension clicks made meanwhile all failed. The shop button's grey tells the run.
    fake.paint(716, 600, 0xAF0000)
    grab = fake.grab

    def run_back_at_10_s(x: int, y: int, w: int, h: int):
        if fake.t >= 10_000:
            fake.paint(1130, 604, 0x989898)
        return grab(x, y, w, h)

    fake.grab = run_back_at_10_s
    bonus_stage(game, skip=True)

    assert fake.t >= 10_000


def test_bs3_sync_timeouts_are_logged(game, events) -> None:
    bs3_section1(game, False)

    assert any(r["event"] == "Sync timeout" and r["where"] == "BonusStage3-s1-1" for r in events())


def test_skipped_bonus_stage_saves_the_end_frame(game, fake, events) -> None:
    fake.paint(716, 600, 0xAF0000)
    bonus_stage(game, skip=True)

    labels = [r["label"] for r in events() if r["event"] == "frame"]
    assert labels == ["bonus-stage-start", "bonus-stage-end"]


def test_bs2_takes_second_wind_and_reruns_the_failed_section(game, fake, event_names) -> None:
    fake.paint(716, 600, 0xAF0000)  # fail screen: Close button...
    fake.paint(615, 590, 0x00A400)  # ...and the Second Wind button
    for x, y, color in ((220, 465, 0xCFBCB8), (767, 631, 0x151515), (508, 631, 0x151515), (200, 400, 0x0D2030)):
        fake.paint(x, y, color)  # every section's sync marker, so the test doesn't wait out timeouts

    def second_wind(action: tuple) -> None:
        if action == ("click", 560 - 8, 600 - 31):  # Second Wind: the dialog closes
            fake.paint(716, 600, 0)
            fake.paint(615, 590, 0)

    fake.on_action = second_wind
    run_bs2(game, sb=False)

    names = event_names()
    assert fake.clicks().count((560, 600)) == 1 and (716, 600) not in fake.clicks()
    assert "BonusStage2 Retry" in names and "BonusStage2 Section 4 Complete" in names
    assert "BonusStage2 Failed" not in names


def test_bs2_closes_the_fail_screen_when_the_rerun_fails_too(game, fake, event_names) -> None:
    fake.paint(716, 600, 0xAF0000)
    fake.paint(615, 590, 0x00A400)  # stays up: the rerun fails as well
    run_bs2(game, sb=False)

    assert fake.clicks().count((560, 600)) == 1 and fake.clicks()[-1] == (716, 600)
    assert "BonusStage2 Failed" in event_names()


@pytest.mark.parametrize("edge_x", [163, 179, 205, 220])  # light edges of the resting block, measured in 3 runs
def test_bs2_first_sync_finds_the_block_wherever_it_stops(game, fake, event_names, edge_x: int) -> None:
    fake.paint(edge_x, 465, 0xCFBCB8)
    bs2_section(game, BS2_SECTIONS[0], "BonusStage2-s1")

    assert "Sync timeout" not in event_names()


@pytest.mark.parametrize(("name", "synced"), [
    # Section 2 opens with two pits 357 px apart. Without the tree's "Protect" node they're open (2026-10-28 14:21,
    # before the bot bought it at 17:14); with it slimes cover the second one, 13 px right of its edge, where the
    # original synced. Santi's run of 20:33 had them.
    ("s2-first-pit", False),  # the first pit at the sync column, ground left of it
    ("s2-second-pit", True),
    ("s2-second-pit-protect", True),
])
def test_bs2_second_sync_waits_for_the_second_pit_with_or_without_protect(
        game, fake, event_names, name: str, synced: bool) -> None:
    fake.frame[:] = read_png(FIXTURES / f"{name}.png")
    bs2_section(game, BS2_SECTIONS[1], "BonusStage2-s2")

    assert ("Sync timeout" not in event_names()) is synced


@pytest.mark.parametrize(("name", "showing"), [
    # "Swipe to Start" frames recorded 2026-10-22/23 (the handle in three of the four places), and 1 s later
    ("swipe-top-left", True), ("swipe-bottom-left", True), ("swipe-bottom-right", True), ("playing-bs2", False),
])
def test_slider_showing_on_recorded_frames(game, fake, name: str, showing: bool) -> None:
    fake.frame[:] = read_png(FIXTURES / f"{name}.png")

    assert slider_showing(game) is showing


def test_swipe_retried_while_the_slider_shows(game, fake, event_names) -> None:
    # The original retried while (775, 448) was white; on this version that pixel is 141416 with the dialog up.
    fake.paint(442, 560, 0x007E00)  # the handle, top left
    fake.paint(716, 600, 0xAF0000)  # the fail screen that ends the skipped stage
    swipes = []

    def handle_stays_after_the_first_swipe(action: tuple) -> None:
        if action == ("click", 840 - 8, 560 - 31):  # a swipe starts
            swipes.append(fake.t)
            if len(swipes) == 2:
                fake.paint(442, 560, 0)  # the second one takes

    fake.on_action = handle_stays_after_the_first_swipe
    bonus_stage(game, skip=True)

    assert len(swipes) == 2
    assert "Start of BonusStage" in event_names() and "stuck" not in event_names()


def test_one_swipe_is_enough_when_the_slider_goes(game, fake) -> None:
    fake.paint(442, 560, 0x007E00)
    fake.paint(716, 600, 0xAF0000)
    fake.on_action = lambda a: fake.paint(442, 560, 0) if a == ("click", 840 - 8, 560 - 31) else None
    bonus_stage(game, skip=True)

    assert fake.clicks().count((840, 560)) == 1


@pytest.mark.parametrize(("frame", "stage"), [("start-bs1", 1), ("start-bs2", 2)])
def test_the_stage_is_told_from_its_start_screen(game, fake, frame: str, stage: int) -> None:
    # Bonus Stage 1 (15 orbs, pink sky) shows while the tree's "Bonus Stage 2" node isn't bought, e.g. after
    # an Ultra Ascension. Its start screen's dimmed sky is 1E131F, BS2's 060519 (12 and 19 starts recorded).
    fake.frame[:] = read_png(FIXTURES / f"{frame}.png")

    assert stage_number(game) == stage


@pytest.mark.parametrize("skip", [False, True])
def test_bonus_stage_1_is_skipped_and_its_second_wind_declined(game, fake, event_names, skip: bool) -> None:
    # Left to the jumper it never got an orb: its blind jumps fall short of the orb arcs (0/15 in every
    # section, live 2026-10-26 and 2026-10-28), and buys paused it in the middle of the stage.
    fake.frame[:] = read_png(FIXTURES / "start-bs1.png")

    def fail_screen_after_the_swipe(action: tuple) -> None:
        if action[0] == "click" and action[1:] != (716 - 8, 600 - 31):
            fake.frame.fill(0)
            fake.paint(615, 590, 0x00A400)  # Second Wind
            fake.paint(716, 600, 0xAF0000)  # Close

    fake.on_action = fail_screen_after_the_swipe
    assert bonus_stage(game, skip=skip) == 1
    assert "BonusStage1 Failed" in event_names() and (560, 600) not in fake.clicks()


def test_bs2_stops_when_the_stage_ended_without_a_fail_screen(game, fake, event_names) -> None:
    """2026-11-02 15:46: the rerun of section 2 ran out of time at a wall and the stage ended with no fail screen
    (Second Wind already taken); the bot counted section 2 complete, waited 15 s for sections 3 and 4 each and
    played their jumps blind in the run. The run's shop button (1130, 604) 989898 shows the stage is over."""
    for x, y, color in ((220, 465, 0xCFBCB8), (767, 631, 0x151515), (508, 631, 0x151515), (200, 400, 0x0D2030)):
        fake.paint(x, y, color)  # every section's sync marker, so the test doesn't wait out timeouts
    fake.paint(1130, 604, 0x989898)  # back in the run
    run_bs2(game, sb=False)

    names = event_names()
    assert "BonusStage2 Section 1 Complete" not in names and "BonusStage2 Over" in names
    assert (716, 600) not in fake.clicks()
