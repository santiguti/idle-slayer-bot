import logging
import subprocess
import sys
import types

import pytest

from idle_runner.game import Game, GameUnavailable, open_backend
from idle_runner.log import inputs, log
from tests.fakes import OFFSET


def test_pixel_search_uses_autoit_coordinates(game, fake) -> None:
    fake.paint(650, 36, 0xCA9700)

    assert game.pixel_search(640, 30, 660, 40, 0xCA9700) == (650, 36)
    assert game.pixel_is(650, 36, 0xCA9700)
    assert not game.pixel_is(651, 36, 0xCA9700)


def test_pixel_search_scan_order_follows_autoit(game, fake) -> None:
    for x, y in ((100, 100), (110, 100), (100, 110)):
        fake.paint(x, y, 0x123456)

    assert game.pixel_search(90, 90, 120, 120, 0x123456) == (100, 100)  # top row first, left to right
    assert game.pixel_search(120, 90, 90, 120, 0x123456) == (110, 100)  # left > right: right to left
    assert game.pixel_search(90, 120, 120, 90, 0x123456) == (100, 110)  # top > bottom: bottom to top


def test_variation_and_global_tolerance(fake) -> None:
    fake.paint(200, 200, 0x101010)

    assert Game(fake, offset=OFFSET).pixel_search(200, 200, 200, 200, 0x141414) is None
    assert Game(fake, offset=OFFSET).pixel_search(200, 200, 200, 200, 0x141414, variation=4) == (200, 200)
    assert Game(fake, offset=OFFSET, tolerance=4).pixel_is(200, 200, 0x141414)


def test_pixel_search_clips_to_the_client_area(game, fake) -> None:
    fake.paint(8, 31, 0xABCDEF)  # client pixel (0, 0)

    assert game.pixel_search(0, 0, 20, 40, 0xABCDEF) == (8, 31)
    assert game.pixel_search(2000, 2000, 2100, 2100, 0xABCDEF) is None


def test_find_until_times_out_on_the_clock(game, fake) -> None:
    assert game.find_until(10, 40, 10, 40, 0xFFFFFF, timeout_ms=100) is None
    assert fake.t >= 100


def test_click_requires_focus(game, fake) -> None:
    game.click(644, 49, clicks=2)
    assert fake.clicks() == [(644, 49), (644, 49)]

    fake.active = False
    with pytest.raises(GameUnavailable):
        game.click(644, 49)


def test_click_outside_the_window_is_refused_and_logged(game, fake, event_names) -> None:
    game.click(33, -23)

    assert fake.clicks() == []
    assert "click_outside_window" in event_names()


def test_hold_presses_the_key_for_the_whole_duration(game, fake) -> None:
    start = fake.t
    game.hold(300, 100, "Up")

    assert [a for a in fake.actions if a[0] == "key"] == [("key", "Up", True), ("key", "Up", False)]
    assert fake.t - start >= 400


def test_routine_logs_duration_and_saves_a_frame_on_crash(game, events) -> None:
    with game.routine("demo"):
        game.sleep(250)
    with pytest.raises(RuntimeError):
        with game.routine("boom"):
            raise RuntimeError("bug")

    records = events()
    end = next(r for r in records if r["event"] == "routine_end")
    assert end["name"] == "demo" and end["ms"] >= 250
    assert any(r["event"] == "frame" and r["label"] == "crash-boom" for r in records)


def test_stuck_logs_and_saves_a_frame(game, events, tmp_path) -> None:
    game.stuck("shop.scroll", y=170)

    records = events()
    assert any(r["event"] == "stuck" and r["where"] == "shop.scroll" and r["y"] == 170 for r in records)
    assert list((tmp_path / "frames").glob("*-stuck-shop.scroll.png"))


def test_release_all_releases_keys_and_button(game, fake) -> None:
    fake.active = False  # must work even when the game lost focus (e.g. on Ctrl+C)
    game.release_all()

    assert ("key", "Up", False) in fake.actions
    assert ("key", "d", False) in fake.actions
    assert ("button", 1, False) in fake.actions


def test_pixel_search_scans_column_by_column_like_autoit(game, fake) -> None:
    fake.paint(110, 100, 0x123456)
    fake.paint(100, 105, 0x123456)

    # Row order would return (110, 100); AutoIt walks column by column, so column 100 wins.
    assert game.pixel_search(90, 90, 120, 120, 0x123456) == (100, 105)


def test_hold_releases_the_key_as_soon_as_focus_is_lost(game, fake) -> None:
    def lose_focus(action: tuple) -> None:
        if action == ("key", "d", True):
            fake.active = False

    fake.on_action = lose_focus
    start = fake.t
    with pytest.raises(GameUnavailable):
        game.hold(15_000, 0, "d")

    assert ("key", "d", False) in fake.actions
    assert fake.t - start < 200


def test_find_until_with_a_label_logs_the_timeout_and_a_frame(game, events) -> None:
    assert game.find_until(10, 40, 10, 40, 0xFFFFFF, timeout_ms=100, label="BonusStage3-s1-1") is None

    records = events()
    assert any(r["event"] == "Sync timeout" and r["where"] == "BonusStage3-s1-1" for r in records)
    assert any(r["event"] == "frame" and r["label"] == "sync-BonusStage3-s1-1" for r in records)


def test_inputs_are_logged_to_the_file(game, logs) -> None:
    game.click(1180, 170)
    game.move(1254, 172)
    game.wheel(up=False, notches=2)
    game.hold(94, 1640)
    game.tap("Up")  # the jumper taps ~13 times a second: DEBUG only
    for handler in log.handlers:
        handler.flush()

    text = (logs / "idle_runner.log").read_text(encoding="utf-8")
    assert "INFO    [MainThread] click (1180,170) x1" in text
    assert "INFO    [MainThread] move (1254,172)" in text
    assert "INFO    [MainThread] wheel down x2" in text
    assert "INFO    [MainThread] hold Up 94 ms, then 1640 ms" in text
    assert "DEBUG   [MainThread] tap Up" in text


def test_inputs_stay_off_the_console(logs) -> None:
    console = next(h for h in log.handlers if not isinstance(h, logging.FileHandler))
    record = inputs.makeRecord(inputs.name, logging.INFO, __file__, 0, "click (1,2) x1", (), None)

    assert not console.filter(record)
    assert console.filter(log.makeRecord(log.name, logging.INFO, __file__, 0, "Bot started", (), None))


def test_core_imports_without_xlib() -> None:
    code = ("import sys; sys.modules['Xlib'] = None; "
            "import idle_runner.runner, idle_runner.blackbox, idle_runner.__main__")
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


def test_open_backend_picks_the_platform(monkeypatch) -> None:
    fake = types.ModuleType("idle_runner.win32")
    fake.Win32Backend = lambda name: ("win32", name)
    monkeypatch.setitem(sys.modules, "idle_runner.win32", fake)
    monkeypatch.setattr(sys, "platform", "win32")

    assert open_backend("Idle Slayer") == ("win32", "Idle Slayer")


@pytest.mark.parametrize("act", [lambda g: g.click(400, 300), lambda g: g.wheel(up=True, notches=1),
                                 lambda g: g.drag(400, 300, 500, 300)])
def test_no_button_when_another_window_is_under_the_pointer(game, fake, events, act) -> None:
    # C8: measured 2026-10-26, X11 reports the window under the pointer right after an XTEST move (50/50).
    fake.pointer_over = False

    with pytest.raises(GameUnavailable, match="another window"):
        act(game)

    assert not [a for a in fake.actions if a[0] in ("button", "click")]
    assert [r["event"] for r in events()].count("click_outside_window") == 1


def test_quiet_pixel_search_logs_only_hits(game, fake, caplog) -> None:
    """The main loop's fast checks run ~25 times a second: logging their misses rotated 50 MB in 2 hours (10-30)."""
    fake.paint(385, 280, 0x140C1C)
    with caplog.at_level(logging.DEBUG, logger=log.name):
        assert game.pixel_is(385, 280, 0x140C1C, quiet=True)
        assert not game.pixel_is(650, 36, 0xCA9700, quiet=True)
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("pixel_search")]
    assert len(lines) == 1 and lines[0].startswith("pixel_search (385,280,")
