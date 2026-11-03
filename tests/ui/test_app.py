"""The window, built on a withdrawn root: never shown, so it never takes the game's focus."""
import json
import os
import sys
from pathlib import Path

import pytest

import idle_runner.ui.app as app_module
from idle_runner.ui.app import PAGES, App, BotProcess, GameProbe

pytestmark = pytest.mark.skipif(sys.platform == "linux" and not os.environ.get("DISPLAY"), reason="needs a display")


@pytest.fixture
def window(tmp_path, monkeypatch, root):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_module, "latest_tag", lambda: None)  # no network in tests
    monkeypatch.setattr(GameProbe, "status", lambda self, name: ("off", "Idle Slayer isn't running"))

    def build(config_text: str = "") -> App:
        config = tmp_path / "config.toml"
        config.write_text(config_text, encoding="utf-8")
        return App(root, config)

    return build


def test_the_window_builds_every_page(window) -> None:
    app = window()

    assert set(app.pages) == set(PAGES)
    assert app.state_label.cget("text") == "Stopped"


def test_the_window_starts_with_a_bad_config(window) -> None:
    app = window('[tree]\ntree_order = ["Moon Boots"]\n')

    assert "Moon Boots" in app.settings_page.message.cget("text")
    assert app.settings_page.settings.tree_order[0] == "Village Key"  # the defaults
    assert app.nav["Settings"].cget("style") == "Current.Nav.TButton"


def test_the_dashboard_follows_the_events(window, tmp_path) -> None:
    app = window()
    events = tmp_path / "logs" / "events.jsonl"
    events.parent.mkdir(exist_ok=True)
    lines = [{"ts": 1.0, "event": "Bot started"}, {"ts": 2.0, "event": "AutoUpgrade Done", "upgrades": 3,
             "equipment": 0}, {"ts": 3.0, "event": "Sync timeout", "where": "BonusStage2-s1"}]
    events.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    app.poll()

    assert app.stat_values["Upgrades"].cget("text") == "3"
    assert app.stat_values["Problems"].cget("text") == "1"
    assert "Bought 3 upgrades" in app.recent.get("1.0", "end")


def test_saving_a_setting_writes_the_config(window, tmp_path) -> None:
    app = window()
    app.settings_page.vars["auto_buy_minutes"].set("4")

    assert app.settings_page.save()
    assert "auto_buy_minutes = 4.0" in (tmp_path / "config.toml").read_text(encoding="utf-8")


def test_an_invalid_value_is_shown_and_not_saved(window, tmp_path) -> None:
    app = window()
    app.settings_page.vars["jump_interval_ms"].set("999")

    assert not app.settings_page.save()
    assert "“Time between jumps” must be 0-300" in app.settings_page.message.cget("text")
    assert (tmp_path / "config.toml").read_text(encoding="utf-8") == ""


def test_the_bot_stops_when_its_stdin_closes(monkeypatch, tmp_path) -> None:
    started = []

    class FakePopen:
        def __init__(self, args, **kwargs) -> None:
            started.append((args, kwargs))
            self.stdin = open(os.devnull, "w", encoding="utf-8")
            self.stdout = iter(["Bot started\n"])

        def poll(self):
            return None if not self.stdin.closed else 0

    monkeypatch.setattr(app_module.subprocess, "Popen", FakePopen)
    bot = BotProcess()
    bot.start(tmp_path / "config.toml")
    assert bot.running() and started[0][0][-1] == "--stop-on-stdin-eof"
    assert started[0][1]["stdin"] == app_module.subprocess.PIPE

    bot.stop()

    assert not bot.running()


def test_the_game_probe_never_raises(monkeypatch) -> None:
    def broken(name: str):
        raise RuntimeError("no display")

    monkeypatch.setattr(app_module, "open_backend", broken)

    assert GameProbe().status("Idle Slayer") == ("off", "Idle Slayer isn't running")


def test_the_support_button_opens_the_donation_page(window, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "DONATE_URL", "https://ko-fi.com/example")
    opened = []
    monkeypatch.setattr(app_module.webbrowser, "open", opened.append)
    app = window()

    app.support_button.invoke()

    assert opened == ["https://ko-fi.com/example"]


def test_no_support_button_without_a_donation_page(window, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "DONATE_URL", "")

    assert window().support_button is None


def test_the_dashboard_says_what_the_bot_is_doing(window, tmp_path, monkeypatch) -> None:
    app = window()
    monkeypatch.setattr(app.bot, "running", lambda: True)
    events = tmp_path / "logs" / "events.jsonl"
    events.parent.mkdir(exist_ok=True)
    with events.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": 1.0, "event": "Bot started"}) + "\n")
        f.write(json.dumps({"ts": 2.0, "event": "routine_start", "name": "buy_tree"}) + "\n")
    app.poll()
    assert app.state_detail.cget("text") == "Checking the Ascension Tree…"

    with events.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": 3.0, "event": "routine_end", "name": "buy_tree", "ms": 3600}) + "\n")
    app.poll()
    assert app.state_detail.cget("text").startswith("Playing while the game is in front")


def test_check_game_settings_now_asks_the_running_bot(window, monkeypatch) -> None:
    import io
    app = window()
    stdin = io.StringIO()
    monkeypatch.setattr(app.bot, "process", type("P", (), {"stdin": stdin, "poll": lambda self: None})())

    app.settings_page.check_button.invoke()

    assert stdin.getvalue() == "check-settings\n"
    assert "few seconds" in app.settings_page.message.cget("text")


def test_check_game_settings_now_with_the_bot_stopped_forgets_today_s_check(window, tmp_path) -> None:
    from idle_runner.state import load_state, update_state
    update_state(tmp_path / "state.json", settings_ok_date="2026-10-28", tree_bought=["Village Key"])
    app = window()

    app.settings_page.check_button.invoke()

    assert load_state(tmp_path / "state.json") == {"settings_ok_date": None, "tree_bought": ["Village Key"]}
    assert "next Start" in app.settings_page.message.cget("text")


def test_the_window_in_spanish(window, monkeypatch) -> None:
    from idle_runner.ui.i18n import set_language
    set_language("es")
    try:
        app = window()
    finally:
        set_language("en")

    assert [app.nav[name].cget("text") for name in PAGES] == ["Panel", "Configuración", "Orden del árbol",
                                                              "Actividad", "Ayuda"]
    assert (app.state_label.cget("text"), app.start_button.cget("text")) == ("Detenido", "Iniciar")


def test_the_language_setting_shows_names_and_saves_codes(window, tmp_path) -> None:
    app = window()
    assert app.settings_page.vars["language"].get() == "System language"

    app.settings_page.vars["language"].set("Español")

    assert app.settings_page.save()
    assert 'language = "es"' in (tmp_path / "config.toml").read_text(encoding="utf-8")


def test_buy_now_asks_the_running_bot(window, monkeypatch) -> None:
    import io
    app = window()
    stdin = io.StringIO()
    monkeypatch.setattr(app.bot, "process", type("P", (), {"stdin": stdin, "poll": lambda self: None})())

    app.buy_button.invoke()

    assert stdin.getvalue() == "buy-now\n"
    assert "few seconds" in app.feed[-1][2]


def test_buy_now_with_the_bot_stopped_says_so(window) -> None:
    app = window()

    app.buy_button.invoke()

    assert "Start" in app.feed[-1][2]
