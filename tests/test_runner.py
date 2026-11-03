import signal
import time
from pathlib import Path
from dataclasses import replace
from datetime import date

import numpy as np
import pytest

import idle_runner.runner as runner_module
from idle_runner.config import Settings
from idle_runner.game import Game
from idle_runner.log import log
from idle_runner.state import load_state, update_state
from idle_runner.runner import (BOX_RETRY_MS, MAX_CONSECUTIVE_CRASHES, RAGE_HOLDOFF_MS, SIX_COIN_TIMEOUT_MS,
                                 WINDOW_RETRY_MS, Runner, install_stop_signals, megahorde_shown)
from idle_runner.game import GameUnavailable, WindowGone
from tests.fakes import OFFSET, FakeBackend, read_png

MEGAHORDE = Path(__file__).parent / "fixtures" / "megahorde"


def show(fake: FakeBackend, name: str) -> None:
    """A recorded frame's middle (tests/fixtures/megahorde: client x 360-919, y 190-309)."""
    fake.frame[190:310, 360:920] = read_png(MEGAHORDE / f"{name}.png")


def test_silver_box_is_collected(game, fake, jumper, event_names) -> None:
    fake.paint(650, 36, 0xCA9700)
    Runner(game, Settings(), jumper).tick()

    assert (644, 49) in fake.clicks()
    assert "Silver Box Collected" in event_names()


def test_silver_box_matches_its_pulsing_button(game, fake, jumper) -> None:
    runner = Runner(game, Settings(), jumper)
    # Measured 2026-10-28 over 1,086 frames: the button pulses B78800 -> F8BB00 about once a second, about
    # 107 shades; the exact CA9700 of the original was 0.46% of them and never matched in 14 minutes.
    for color, expected in ((0xB78800, False), (0xC29100, True), (0xD9A400, True), (0xF8BB00, False)):
        fake.paint(650, 36, color)
        fake.actions.clear()
        runner.tick()
        assert ((644, 49) in fake.clicks()) is expected, hex(color)


def test_unfocused_game_gets_no_input_and_pause_is_logged_once(game, fake, jumper, event_names) -> None:
    fake.paint(650, 36, 0xCA9700)
    fake.active = False
    runner = Runner(game, Settings(), jumper)
    runner.tick()
    runner.tick()

    assert fake.clicks() == []
    assert event_names().count("Paused: game not focused") == 1


def test_megahorde_with_soul_bonus_crafts_and_rages(game, fake, jumper, event_names) -> None:
    show(fake, "horde")
    fake.paint(627, 150, 0xA86D0A)  # soul bonus
    Runner(game, replace(Settings(), craft_rage_pill=True), jumper).tick()

    assert (160, 100) in fake.clicks()  # crafting menu opened
    assert "r" in fake.taps()
    assert jumper.pauses >= 1
    names = event_names()
    assert "MegaHorde Rage with SoulBonus" in names and "MegaHorde Rage" in names


def test_no_rage_without_soul_bonus_when_disabled(game, fake, jumper) -> None:
    show(fake, "horde")
    Runner(game, replace(Settings(), disable_rage_without_soul_bonus=True), jumper).tick()

    assert "r" not in fake.taps()


@pytest.mark.parametrize("name", ["horde", "horde-low"])
def test_megahorde_is_seen_on_a_recorded_horde(game, fake, name) -> None:
    show(fake, name)  # "horde-low": the text 13 px lower, it bobs
    assert megahorde_shown(game)


@pytest.mark.parametrize("name", ["ascension-panel", "minions-panel-closing", "coin-banner"])
def test_panels_and_other_banners_are_not_a_megahorde(game, fake, name) -> None:
    """All three have the original's 140C1C at (385, 280): 232 of 395 rages on Linux (10-29/30) came from a panel."""
    show(fake, name)
    assert game.pixel_is(385, 280, 0x140C1C)
    assert not megahorde_shown(game)


def test_rage_once_per_megahorde(game, fake, jumper, event_names) -> None:
    show(fake, "horde")
    runner = Runner(game, Settings(), jumper)
    for _ in range(20):  # the text shows about 1 s: ~20 loops
        runner.tick()
    assert fake.taps().count("r") == 1 and event_names().count("MegaHorde Rage") == 1

    fake.t += RAGE_HOLDOFF_MS
    runner.tick()
    assert fake.taps().count("r") == 2


def test_a_horde_right_after_a_panel_still_rages(game, fake, jumper) -> None:
    runner = Runner(game, Settings(), jumper)
    show(fake, "ascension-panel")
    runner.tick()
    show(fake, "horde")
    runner.tick()
    assert fake.taps().count("r") == 1


def test_dimensional_staff_is_crafted_once_per_run(game, fake, jumper, event_names) -> None:
    show(fake, "horde")
    runner = Runner(game, replace(Settings(), craft_dimensional_staff=True), jumper)
    runner.tick()
    runner.tick()

    assert event_names().count("Trying to CraftingTemp Item") == 1


def test_auto_buy_runs_on_the_slow_tick_after_its_interval(game, fake, jumper, event_names) -> None:
    runner = Runner(game, replace(Settings(), auto_buy_upgrades=True, auto_buy_minutes=0.1), jumper)
    fake.t += 7_000
    runner.tick()

    assert "AutoUpgrade Active" in event_names()


def test_auto_ascend_runs_on_the_slow_tick_after_its_interval(game, fake, jumper, event_names) -> None:
    runner = Runner(game, replace(Settings(), auto_ascend=True, auto_ascend_minutes=0.1), jumper)
    fake.t += 7_000
    runner.tick()

    assert "Ascend skipped" in event_names()  # the fake screen has no ascend button


def test_ascend_bonus_is_sampled_on_the_slow_tick_after_its_interval(game, fake, jumper, event_names) -> None:
    runner = Runner(game, replace(Settings(), ascend_bonus_sample_minutes=0.1), jumper)
    runner.tick()
    assert "Ascend bonus not shown" not in event_names()  # not due yet

    fake.t += 7_000
    runner.tick()

    assert "Ascend bonus not shown" in event_names()  # the fake screen has no ascension panel


@pytest.mark.parametrize(("bonus", "ascends"), [(12.0, True), (10.0, True), (8.0, False), (None, False)])
def test_auto_ascend_when_the_sampled_bonus_reaches_its_percent(game, fake, jumper, monkeypatch,
                                                                bonus: float | None, ascends: bool) -> None:
    settings = replace(Settings(), auto_ascend=True, auto_ascend_minutes=60, auto_ascend_percent=10,
                       ascend_bonus_sample_minutes=0.1)
    runner = Runner(game, settings, jumper)
    ascended = []
    asked = []
    monkeypatch.setattr(runner.shop, "sample_ascend_bonus", lambda keep_open_at=None: asked.append(keep_open_at)
                        or bonus)
    monkeypatch.setattr(runner.shop, "auto_ascend", lambda: ascended.append(fake.t) is None)
    fake.t += 7_000
    runner.tick()  # the 60-minute timer isn't due

    assert bool(ascended) is ascends
    assert asked == [10]  # the panel stays open when the bonus reaches 10 %, for the ascension


def test_focus_loss_mid_routine_aborts_without_more_input(game, fake, jumper, event_names) -> None:
    def lose_focus(action: tuple) -> None:
        if action[0] == "click":
            fake.active = False

    fake.on_action = lose_focus
    runner = Runner(game, Settings(), jumper)
    fake.t += 6_000  # the first slow check reads the game settings: its first click opens the shop
    with pytest.raises(GameUnavailable):
        runner.tick()

    assert fake.clicks() == [(1163, 655)]
    assert "routine_abort" in event_names()


def test_run_warns_on_wrong_window_size_and_releases_keys_on_ctrl_c(jumper, event_names) -> None:
    fake = FakeBackend(width=1600, height=900)
    fake.stop_at = 1_000  # Ctrl+C after one virtual second
    Runner(Game(fake, offset=OFFSET), Settings(), jumper).run()

    names = event_names()
    assert "Window size mismatch" in names and "Bot stopped" in names
    assert ("key", "Up", False) in fake.actions and ("button", 1, False) in fake.actions
    assert jumper.running and jumper.stopped


def test_circle_portals_rotate_destinations(game, fake, jumper, monkeypatch) -> None:
    taken = []
    monkeypatch.setattr(runner_module, "portal_ready", lambda g: True)
    monkeypatch.setattr(runner_module, "take_portal", lambda g, count: taken.append(count))
    runner = Runner(game, replace(Settings(), circle_portals=True, circle_portals_count=9), jumper)
    fake.t += 6_000
    runner.tick()
    fake.t += 6_000
    runner.tick()

    assert taken == [9, 1]


def test_chest_hunt_is_dispatched(game, fake, jumper, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(runner_module, "chest_hunt", lambda g, *flags: calls.append(flags))
    fake.paint(187, 296, 0xFFBB31)
    fake.paint(187, 303, 0xF68F37)
    fake.paint(180, 296, 0x151515)
    Runner(game, Settings(), jumper).tick()

    assert calls == [(True, False, False)]


def test_a_coin_on_the_chest_hunt_pixels_is_not_a_chest_hunt(game, fake, jumper, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(runner_module, "chest_hunt", lambda g, *flags: calls.append(flags))
    # 2026-10-28 14:19: every coin has FFBB31 with F68F37 7 px below it, and one crossed (187, 296).
    fake.paint(187, 296, 0xFFBB31)
    fake.paint(187, 303, 0xF68F37)
    fake.paint(180, 296, 0x81E1FF)  # sky
    Runner(game, Settings(), jumper).tick()

    assert calls == []


def test_bonus_stage_is_dispatched_on_the_slow_tick(game, fake, jumper, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(runner_module, "bonus_stage", lambda g, skip: calls.append(skip))
    fake.paint(660, 254, 0xFFE737)
    fake.paint(638, 236, 0xFFBB31)
    runner = Runner(game, replace(Settings(), skip_bonus_stage=True), jumper)
    fake.t += 6_000
    runner.tick()

    assert calls == [True]


def test_boss_fight_picks_knight_or_victor(game, fake, jumper, monkeypatch) -> None:
    fought = []
    monkeypatch.setattr(runner_module, "boss_fight_victor", lambda g: fought.append("victor"))
    monkeypatch.setattr(runner_module, "boss_fight_knight", lambda g: fought.append("knight"))
    for x, color in ((639, 0xFF878A), (634, 0xF263BD), (644, 0xFFF38F)):
        fake.paint(x, 224, color)
    runner = Runner(game, Settings(), jumper)
    fake.t += 6_000
    runner.tick()
    fake.paint(30, 690, 0x0B0303)  # Knight's arena
    fake.t += 6_000
    runner.tick()

    assert fought == ["victor", "knight"]


def test_ascending_heights_is_dispatched(game, fake, jumper, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(runner_module, "ascending_heights", lambda g: calls.append(True))
    fake.paint(671, 213, 0xC2F4F9)
    fake.paint(637, 300, 0xFFCC66)
    runner = Runner(game, Settings(), jumper)
    fake.t += 6_000
    runner.tick()

    assert calls == [True]


def test_post_ascend_ramp_buys_soon_then_backs_off(game, fake, jumper, monkeypatch) -> None:
    settings = replace(Settings(), auto_buy_upgrades=True, auto_buy_minutes=10,
                       auto_ascend=True, auto_ascend_minutes=1, post_ascend_first_buy_seconds=15)
    runner = Runner(game, settings, jumper)
    buys = []
    monkeypatch.setattr(runner.shop, "auto_ascend", lambda: True)
    monkeypatch.setattr(runner.shop, "auto_upgrade", lambda: buys.append(fake.t))

    fake.t += 61_000
    runner.tick()  # ascends; the 10-minute buy timer isn't due
    assert buys == [] and runner.buy_minutes == 0.25

    fake.t += 16_000
    runner.tick()  # 15 s after ascending: first fast buy
    assert len(buys) == 1 and runner.buy_minutes == 0.5


def test_post_ascend_ramp_can_be_disabled(game, fake, jumper, monkeypatch) -> None:
    settings = replace(Settings(), auto_buy_upgrades=True, auto_ascend=True, auto_ascend_minutes=1,
                       post_ascend_first_buy_seconds=0)
    runner = Runner(game, settings, jumper)
    monkeypatch.setattr(runner.shop, "auto_ascend", lambda: True)
    fake.t += 61_000
    runner.tick()

    assert runner.buy_minutes == settings.auto_buy_minutes


def test_wrong_window_size_pauses_input_and_warns(jumper, event_names, logs) -> None:
    fake = FakeBackend(width=1600, height=900)
    fake.paint(650, 36, 0xCA9700)
    Runner(Game(fake, offset=OFFSET), Settings(), jumper).tick()
    for handler in log.handlers:
        handler.flush()

    assert fake.clicks() == []
    assert "Paused: window is 1600x900, expected 1280x720" in event_names()
    assert "WARNING" in (logs / "idle_runner.log").read_text(encoding="utf-8")


def test_window_resized_mid_run_pauses_the_bot(game, fake, jumper, event_names) -> None:
    runner = Runner(game, Settings(), jumper)
    fake.frame = np.zeros((900, 1600, 3), dtype=np.uint8)  # e.g. the user maximized the window
    fake.paint(650, 36, 0xCA9700)
    runner.tick()

    assert fake.clicks() == []
    assert "Paused: window is 1600x900, expected 1280x720" in event_names()


def test_run_survives_an_unexpected_error_in_a_tick(game, fake, jumper, event_names, monkeypatch) -> None:
    runner = Runner(game, Settings(), jumper)
    real_tick = runner.tick
    calls = []

    def flaky_tick() -> None:
        calls.append(1)
        if len(calls) == 1:
            raise IndexError("bad grab")
        if len(calls) == 3:
            raise KeyboardInterrupt
        real_tick()

    monkeypatch.setattr(runner, "tick", flaky_tick)
    runner.run()

    assert len(calls) == 3
    assert "tick_crash" in event_names() and "Bot stopped" in event_names()


def test_run_gives_up_after_repeated_errors_and_still_releases_keys(game, fake, jumper, event_names,
                                                                    monkeypatch) -> None:
    runner = Runner(game, Settings(), jumper)

    def broken_tick() -> None:
        raise IndexError("always")

    monkeypatch.setattr(runner, "tick", broken_tick)
    with pytest.raises(IndexError):
        runner.run()

    assert event_names().count("tick_crash") == MAX_CONSECUTIVE_CRASHES
    assert ("key", "Up", False) in fake.actions


def test_run_releases_keys_even_if_stopping_the_jumper_is_interrupted(game, fake, jumper) -> None:
    def interrupted_stop() -> None:
        raise KeyboardInterrupt  # a second Ctrl+C during shutdown

    jumper.stop = interrupted_stop
    fake.stop_at = 100
    with pytest.raises(KeyboardInterrupt):
        Runner(game, Settings(), jumper).run()

    assert ("key", "Up", False) in fake.actions


def test_stop_signals_raise_keyboard_interrupt() -> None:
    signals = [s for s in (signal.SIGTERM, getattr(signal, "SIGHUP", None), getattr(signal, "SIGBREAK", None)) if s]
    previous = {s: signal.getsignal(s) for s in signals}
    try:
        install_stop_signals()
        with pytest.raises(KeyboardInterrupt):
            signal.raise_signal(signal.SIGTERM)  # os.kill(own pid, SIGTERM) on Windows ends pytest at once
            time.sleep(1)  # the handler runs between bytecodes
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def test_game_unavailable_is_logged_once_and_resumed_when_it_clears(game, fake, jumper, event_names) -> None:
    real_grab = fake.grab

    def grab_fails_for_3_seconds(x: int, y: int, w: int, h: int) -> np.ndarray:
        if fake.t < 3_000:
            raise GameUnavailable("cannot capture the game window (BadMatch)")
        return real_grab(x, y, w, h)

    fake.grab = grab_fails_for_3_seconds
    fake.stop_at = 5_000
    Runner(game, Settings(), jumper).run()

    names = event_names()
    assert names.count("Game unavailable") == 1
    assert names.count("Resumed") == 1 and names.index("Resumed") > names.index("Game unavailable")


def test_pause_after_game_unavailable_is_not_reported_as_resumed(game, fake, jumper, event_names) -> None:
    # The first slow check (5 s in) reads the game settings: its first click opens the shop.
    def lose_focus(action: tuple) -> None:
        if action[0] == "click":
            fake.active = False

    fake.on_action = lose_focus
    fake.stop_at = 8_000
    Runner(game, Settings(), jumper).run()

    names = event_names()
    assert names.count("Game unavailable") == 1 and "Paused: game not focused" in names
    assert "Resumed" not in names  # the game is still unfocused


def test_bot_started_logs_the_effective_settings(game, fake, jumper, events) -> None:
    fake.stop_at = 100
    Runner(game, replace(Settings(), jump_interval_ms=90), jumper).run()

    started = next(r for r in events() if r["event"] == "Bot started")
    assert started["jump_interval_ms"] == 90 and started["window_name"] == "Idle Slayer"


def test_restarted_game_window_is_found_again(game, fake, jumper, event_names) -> None:
    real_size = fake.size
    lookups = []

    def window_gone() -> tuple[int, int]:
        raise WindowGone("the game window is gone (BadDrawable)")

    def find_window() -> None:
        lookups.append(fake.t)
        if len(lookups) < 3:
            raise GameUnavailable("no X11 window named 'Idle Slayer'; is the game running?")
        fake.size = real_size  # the relaunched game's window

    fake.size = window_gone
    fake.find_window = find_window
    fake.paint(650, 36, 0xCA9700)  # silver box: proves ticks run again afterwards
    fake.stop_at = 20_000
    Runner(game, Settings(), jumper).run()

    names = event_names()
    assert names.count("Game window lost") == 1 and names.count("Game window found") == 1
    assert "Game unavailable" not in names
    assert len(lookups) == 3 and lookups[1] - lookups[0] >= WINDOW_RETRY_MS
    assert (644, 49) in fake.clicks()


def test_claim_trigger_matches_the_pulsing_shop_button_near_its_peak(game, fake, jumper, monkeypatch) -> None:
    runner = Runner(game, Settings(), jumper)
    claims = []
    monkeypatch.setattr(runner.shop, "claim_quests", lambda: claims.append(fake.t))
    # Measured 2026-10-22 at 144 FPS: the button glows smoothly from 989898 to CFCF46 and back,
    # so the exact CBCB4C of the original lasts one frame (~7 ms) and the 40 ms loop rarely sees it.
    for color, expected in ((0x989898, 0), (0xBCBC63, 0), (0xC3C35A, 1), (0xCFCF46, 2)):
        fake.paint(1130, 610, color)
        runner.tick()
        assert len(claims) == expected, hex(color)


def run_ticks_reading(runner: Runner, fake: FakeBackend, monkeypatch, readings: list) -> None:
    values = iter(readings)
    monkeypatch.setattr(runner_module, "read_coins", lambda g: next(values))
    for _ in readings:
        runner.tick()
        fake.t += 1_000


def test_buys_as_soon_as_coins_reach_six_after_an_ascension(game, fake, jumper, event_names, monkeypatch) -> None:
    runner = Runner(game, replace(Settings(), auto_buy_upgrades=True), jumper)
    buys = []
    monkeypatch.setattr(runner.shop, "auto_upgrade", lambda: buys.append(fake.t))
    run_ticks_reading(runner, fake, monkeypatch, [None, 0.0, 3.0, None, 7.5, 11.3])

    assert len(buys) == 1 and "Coins reached 6" in event_names()
    assert runner.buy_minutes == 0.25  # then the post-ascension ramp, from this buy


def test_tree_is_bought_at_start_and_after_each_ascension(game, fake, jumper, monkeypatch) -> None:
    settings = replace(Settings(), auto_buy_tree=True, auto_ascend=True, auto_ascend_minutes=1)
    runner = Runner(game, settings, jumper)
    runs = []
    monkeypatch.setattr(runner.tree, "buy", lambda: runs.append(fake.t))
    monkeypatch.setattr(runner.shop, "auto_ascend", lambda: True)
    fake.t += 6_000
    runner.tick()  # first slow tick: the user may have ascended by hand before the bot started
    fake.t += 6_000
    runner.tick()
    assert len(runs) == 1

    fake.t += 61_000
    runner.tick()  # ascends, then buys
    assert len(runs) == 2


def test_tree_is_bought_after_an_ascension_by_hand(game, fake, jumper, monkeypatch) -> None:
    runner = Runner(game, replace(Settings(), auto_buy_upgrades=True, auto_buy_tree=True), jumper)
    runner.tree_due = False
    monkeypatch.setattr(runner.shop, "auto_upgrade", lambda: True)
    run_ticks_reading(runner, fake, monkeypatch, [0.0, 7.5])  # the counter starts again from 0

    assert runner.tree_due


def test_tree_is_not_bought_unless_enabled(game, fake, jumper, monkeypatch) -> None:
    runner = Runner(game, Settings(), jumper)
    runs = []
    monkeypatch.setattr(runner.tree, "buy", lambda: runs.append(fake.t))
    fake.t += 6_000
    runner.tick()

    assert runs == []


def test_no_six_coin_buy_without_a_low_reading_first(game, fake, jumper, monkeypatch) -> None:
    runner = Runner(game, replace(Settings(), auto_buy_upgrades=True), jumper)
    buys = []
    monkeypatch.setattr(runner.shop, "auto_upgrade", lambda: buys.append(fake.t))
    run_ticks_reading(runner, fake, monkeypatch, [7.5, 11.3, 15.0])

    assert buys == []


def test_six_coin_buy_falls_back_after_two_minutes_of_unreadable_counter(game, fake, jumper, event_names,
                                                                        monkeypatch) -> None:
    runner = Runner(game, replace(Settings(), auto_buy_upgrades=True, auto_buy_minutes=60), jumper)
    buys = []
    monkeypatch.setattr(runner.shop, "auto_upgrade", lambda: buys.append(fake.t))
    run_ticks_reading(runner, fake, monkeypatch, [0.0] + [None] * 130)

    assert event_names().count("Coins reading timed out") == 1
    assert buys and SIX_COIN_TIMEOUT_MS <= buys[0] < SIX_COIN_TIMEOUT_MS + 5_000  # later buys: the ramp


def test_shop_not_open_retries_in_15_s(game, fake, jumper, event_names) -> None:
    runner = Runner(game, replace(Settings(), auto_buy_upgrades=True, auto_buy_minutes=10), jumper)

    runner.buy()  # nothing is painted: the shop never opens

    assert "AutoUpgrade shop not open" in event_names()
    assert runner.retry_buy_at is not None and runner.retry_buy_at <= fake.t + BOX_RETRY_MS


def test_shop_not_open_is_retried_only_once(game, fake, jumper, event_names) -> None:
    runner = Runner(game, replace(Settings(), auto_buy_upgrades=True, auto_buy_minutes=10), jumper)
    runner.buy()  # nothing is painted: the shop never opens
    fake.t = runner.retry_buy_at

    runner.buy()  # the retry, as tick() runs it: the shop still doesn't open

    assert event_names().count("AutoUpgrade shop not open") == 2
    assert runner.retry_buy_at is None  # back to the normal timer (a stuck panel once lasted 55 minutes)


def test_a_box_during_the_retry_is_retried_again(game, fake, jumper, monkeypatch) -> None:
    runner = Runner(game, replace(Settings(), auto_buy_upgrades=True, auto_buy_minutes=10), jumper)

    def stopped_by_a_box() -> bool:
        runner.shop.opened = True
        return False

    monkeypatch.setattr(runner.shop, "auto_upgrade", stopped_by_a_box)
    runner.buy()
    first_retry = runner.retry_buy_at
    fake.t = first_retry

    runner.buy()

    assert runner.retry_buy_at is not None and runner.retry_buy_at > first_retry


def test_buying_resumes_soon_after_a_box_interrupts_it(game, fake, jumper, event_names, monkeypatch) -> None:
    runner = Runner(game, replace(Settings(), auto_buy_upgrades=True, auto_buy_minutes=10), jumper)
    results = iter([False, True])
    buys = []

    def auto_upgrade() -> bool:
        buys.append(fake.t)
        return next(results)

    monkeypatch.setattr(runner.shop, "auto_upgrade", auto_upgrade)
    fake.t += 601_000
    runner.tick()  # the timed buy, interrupted by a box
    for _ in range(4):
        fake.t += 6_000
        runner.tick()

    assert len(buys) == 2 and buys[1] - buys[0] <= BOX_RETRY_MS + 10_000


def test_the_main_loop_never_clicks_second_wind(game, fake, jumper) -> None:
    # The same green is the Ascend dialog's "Yes" (client 493-624 x 525-578).
    runner = Runner(game, Settings(), jumper)
    fake.paint(615, 590, 0x00A400)
    fake.paint(716, 600, 0xAF0000)
    runner.tick()

    assert (560, 600) not in fake.clicks()


def test_minions_are_visited_at_start_after_each_tree_run_and_hourly_while_no_return_is_known(
        game, fake, jumper, monkeypatch) -> None:
    visits: list[float] = []
    monkeypatch.setattr(runner_module, "send_minions", lambda g: visits.append(fake.t) or ([], False))
    runner = Runner(game, replace(Settings(), auto_buy_tree=False), jumper)
    fake.t += 6_000
    runner.tick()  # the first slow check: the node may have been bought by hand
    fake.t += 6_000
    runner.tick()
    assert len(visits) == 1

    runner.tree_due = True
    runner.s = replace(runner.s, auto_buy_tree=True)
    monkeypatch.setattr(runner.tree, "buy", lambda: None)
    fake.t += 6_000
    runner.tick()  # the tree may have just bought a minion
    assert len(visits) == 2

    fake.t += 60 * 60_000
    runner.tick()  # nothing sent, so no return is known: an hourly look
    assert len(visits) == 3


def test_minions_are_visited_again_when_their_mission_ends(game, fake, jumper, monkeypatch) -> None:
    sends = iter([([10], False), ([], False), ([], False)])
    visits: list[float] = []
    monkeypatch.setattr(runner_module, "send_minions", lambda g: visits.append(fake.t) or next(sends))
    runner = Runner(game, replace(Settings(), work_benefits=True), jumper)  # 3 h x 0.85 = 153 min
    fake.t += 6_000
    runner.tick()  # sends the White Knight
    fake.t += 153 * 60_000
    runner.tick()  # not back yet, and no hourly look while a return is known
    assert len(visits) == 1

    fake.t += 2 * 60_000
    runner.tick()  # back (a minute's margin)
    assert len(visits) == 2


def test_the_daily_bonus_brings_the_missions_back_3_hours_sooner(game, fake, jumper, monkeypatch) -> None:
    # It's taken after the sends: the Dark Wizard sent in the same visit is back 3 hours sooner too, and the
    # next tick looks again (missions it ended wait to be claimed).
    sends = iter([([150], True), ([], False), ([], False)])
    visits: list[float] = []
    monkeypatch.setattr(runner_module, "send_minions", lambda g: visits.append(fake.t) or next(sends))
    runner = Runner(game, Settings(), jumper)
    fake.t += 6_000
    runner.tick()  # sends the Dark Wizard (6 h 30), then takes the bonus
    fake.t += 6_000
    runner.tick()  # at once: the claims the bonus made
    assert len(visits) == 2
    assert runner.minions_back == [pytest.approx(visits[0] + (390 - 180 + 1) * 60_000)]


def test_the_ascension_button_glow_starts_no_minion_routine(game, fake, jumper, monkeypatch) -> None:
    # The original's "minions are back" (99, 113) is the Ascension button's glow on this version: it glows
    # while ascending is "Recommended" and fired with no minions at all (2026-10-28 00:15:03).
    sent: list[float] = []
    monkeypatch.setattr(runner_module, "send_minions", lambda g: sent.append(fake.t) or ([], False))
    runner = Runner(game, Settings(), jumper)
    fake.t += 6_000
    runner.tick()
    fake.paint(99, 113, 0xFFFF7A)
    for _ in range(3):
        fake.t += 1_000
        runner.tick()

    assert len(sent) == 1


def test_the_game_settings_are_checked_once_at_start(game, fake, jumper, monkeypatch) -> None:
    checks: list[float] = []
    monkeypatch.setattr(runner_module, "check_game_settings", lambda g, shop: checks.append(fake.t))
    monkeypatch.setattr(runner_module, "send_minions", lambda g: ([], False))
    runner = Runner(game, Settings(), jumper)
    for _ in range(3):
        fake.t += 6_000
        runner.tick()

    assert len(checks) == 1


def settings_checks(fake, monkeypatch, result: bool) -> list[float]:
    checks: list[float] = []
    monkeypatch.setattr(runner_module, "check_game_settings", lambda g, shop: checks.append(fake.t) is None and result)
    monkeypatch.setattr(runner_module, "send_minions", lambda g: ([], False))
    return checks


def test_game_settings_found_right_are_not_checked_again_the_same_day(game, fake, jumper, monkeypatch, tmp_path,
                                                                      event_names) -> None:
    state = tmp_path / "state.json"
    checks = settings_checks(fake, monkeypatch, result=True)
    runner = Runner(game, Settings(), jumper, state)
    fake.t += 6_000
    runner.tick()
    assert len(checks) == 1 and load_state(state)["settings_ok_date"] == date.today().isoformat()

    runner = Runner(game, Settings(), jumper, state)  # the bot started again
    fake.t += 6_000
    runner.tick()

    assert len(checks) == 1
    assert "Game settings check skipped" in event_names()


def test_game_settings_are_checked_again_until_they_are_right(game, fake, jumper, monkeypatch, tmp_path) -> None:
    state = tmp_path / "state.json"
    update_state(state, settings_ok_date=date.today().isoformat())
    checks = settings_checks(fake, monkeypatch, result=False)
    runner = Runner(game, Settings(), jumper, state)
    runner.settings_request.set()  # the window's "Check game settings now"
    fake.t += 6_000
    runner.tick()
    assert len(checks) == 1 and load_state(state)["settings_ok_date"] is None  # something was wrong

    runner = Runner(game, Settings(), jumper, state)  # the next Start checks again
    fake.t += 6_000
    runner.tick()
    assert len(checks) == 2


def test_check_game_settings_now_while_the_bot_runs(game, fake, jumper, monkeypatch) -> None:
    checks = settings_checks(fake, monkeypatch, result=True)
    runner = Runner(game, Settings(), jumper)
    fake.t += 6_000
    runner.tick()
    runner.settings_request.set()
    fake.t += 1_000
    runner.tick()  # only at the slow check
    assert len(checks) == 1

    fake.t += 5_000
    runner.tick()
    assert len(checks) == 2 and not runner.settings_request.is_set()


def test_buy_now_runs_auto_upgrade_at_the_next_slow_check(game, fake, jumper, monkeypatch) -> None:
    """The window's "Buy now" (Heldof, 2026-10-29): a buy at the next slow check, then the timer counts from it."""
    runner = Runner(game, replace(Settings(), auto_buy_upgrades=False), jumper)  # no timed buys
    buys = []
    monkeypatch.setattr(runner, "buy", lambda: buys.append(fake.t))
    fake.t += 6_000
    runner.tick()
    runner.last_slow = fake.t  # the start's checks (settings, minions) take seconds of the clock
    runner.buy_request.set()
    fake.t += 1_000
    runner.tick()  # only at the slow check
    assert buys == []

    fake.t += 5_000
    runner.tick()
    assert len(buys) == 1 and not runner.buy_request.is_set() and runner.timer_buy == buys[0]


def test_buy_now_works_with_auto_buy_off(game, fake, jumper, monkeypatch) -> None:
    runner = Runner(game, replace(Settings(), auto_buy_upgrades=False), jumper)
    buys = []
    monkeypatch.setattr(runner, "buy", lambda: buys.append(fake.t))
    runner.buy_request.set()
    fake.t += 6_000
    runner.tick()
    assert len(buys) == 1


def test_buy_now_waits_for_a_minigame(game, fake, jumper, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(runner_module, "bonus_stage", lambda g, skip: calls.append("bonus stage"))
    fake.paint(660, 254, 0xFFE737)
    fake.paint(638, 236, 0xFFBB31)
    runner = Runner(game, Settings(), jumper)
    monkeypatch.setattr(runner, "buy", lambda: calls.append("buy"))
    runner.buy_request.set()
    fake.t += 6_000
    runner.tick()
    assert calls == ["bonus stage", "buy"]
