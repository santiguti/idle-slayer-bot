"""The Idle Runner window (`idle-runner`, or `python -m idle_runner gui`): start and stop the bot, see what it
does, change its settings and its Ascension Tree order.

The bot runs as a child process (`run --stop-on-stdin-eof`): closing its stdin stops it like Ctrl+C, on
Linux and Windows, and it also stops if this window dies. What the dashboard shows comes from the events the
bot writes to logs/events.jsonl (ui/activity.py).
"""
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from collections import deque
from pathlib import Path
from tkinter import messagebox, ttk

from idle_runner import DONATE_URL, REPO, __version__
from idle_runner.blackbox import mark
from idle_runner.config import Settings, load_settings
from idle_runner.game import open_backend
from idle_runner.log import setup_logging
from idle_runner.process import self_command
from idle_runner.state import state_path, update_state
from idle_runner.stats import summarize
from idle_runner.ui.activity import EventTail, Session, apply, describe
from idle_runner.ui.i18n import set_language, t
from idle_runner.ui.settings_page import SettingsPage
from idle_runner.ui.theme import ASSETS, PALETTE, apply_theme, panel
from idle_runner.ui.tree_page import TreePage
from idle_runner.ui.updates import latest_tag, newer

PAGES = ("Dashboard", "Settings", "Tree order", "Activity", "Help")
KIND_COLOURS = {"buy": PALETTE.gold, "ascend": PALETTE.accent, "tree": PALETTE.accent, "minigame": PALETTE.text,
                "box": PALETTE.text, "quest": PALETTE.gold, "problem": PALETTE.danger_text, "state": PALETTE.muted,
                "raw": PALETTE.muted}
STATS = ("Running for", "Upgrades", "Equipment", "Ascensions", "Last bonus", "Tree nodes", "Minigames", "Silver boxes",
         "Problems")
FILTERS = {"Everything": None, "Purchases": {"buy", "quest", "tree"}, "Ascensions": {"ascend"},
           "Minigames": {"minigame", "box"}, "Problems": {"problem"}}
SETUP = """Before you start, in Idle Slayer:
•  Windowed, 1280×720, in English or Spanish.
•  Keys: jump = Up arrow, boost = Right arrow.
•  Custom cursor off, portal dialogue off, scientific notation off.
•  Rounded bulk on, hide locked quest rewards on.
•  Don't buy the Vertical Magnet.
At the first Start of each day the bot reads these settings (then presses Cancel) and lists any wrong
one under Problems. Settings, "Check game settings now" reads them again.

The bot only plays while the game window is in front. Click another window to pause it, click the game to
resume."""
SAFETY = """What the bot will never do:
•  Read or change the game's memory, files or network. It only looks at the window and presses keys.
•  Spend jewels. It presses Buy in the tree only when the game shows enough Slayer Points.
•  Ultra Ascend.
Tree buying stays off until you turn it on. Ascending is on: at a +20% CpS bonus, at the latest every
30 minutes (Settings, Ascension)."""


class BotProcess:
    """The bot as a child process, with its console output collected by a reader thread."""

    def __init__(self) -> None:
        self.process: subprocess.Popen[str] | None = None
        self.lines: queue.Queue[str] = queue.Queue()

    def start(self, config: Path) -> None:
        self.process = subprocess.Popen(
            self_command("run", "--config", str(config), "--stop-on-stdin-eof"),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))  # no console window on Windows
        threading.Thread(target=self._read, args=(self.process,), daemon=True).start()

    def _read(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            self.lines.put(line.rstrip("\n"))

    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def exit_code(self) -> int | None:
        return None if self.process is None else self.process.poll()

    def send(self, command: str) -> bool:
        """Send the running bot a command line (process.stop_on_stdin_eof). False if there's no bot to hear it."""
        if not self.running() or not self.process or not self.process.stdin or self.process.stdin.closed:
            return False
        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
        except OSError:  # it has just stopped
            return False
        return True

    def stop(self) -> None:
        """Ask the bot to stop (it releases every held key first)."""
        if self.running() and self.process and self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()

    def stop_and_wait(self, seconds: float = 5) -> None:
        self.stop()
        if self.process is not None:
            try:
                self.process.wait(timeout=seconds)
            except subprocess.TimeoutExpired:
                self.process.kill()


class GameProbe:
    """A read-only look at the game window for the dashboard: never sends input."""

    def __init__(self) -> None:
        self.backend = None

    def status(self, window_name: str) -> tuple[str, str]:
        """("ok" | "warning" | "off", text). Never raises."""
        try:
            if self.backend is None:
                self.backend = open_backend(window_name)
            else:
                self.backend.find_window()
            width, height = self.backend.size()
        except Exception:
            self.backend = None
            return "off", t("Idle Slayer isn't running")
        if (width, height) != (1280, 720):
            return "warning", t("Idle Slayer's window is {width}×{height}: set it to 1280×720, windowed",
                                width=width, height=height)
        return "ok", t("Idle Slayer found, 1280×720")


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)])


class App:
    def __init__(self, root: tk.Tk, config_path: Path) -> None:
        self.root, self.config_path = root, config_path
        apply_theme(root)
        root.title("Idle Runner")
        root.geometry("1060x700")
        root.minsize(900, 600)
        try:
            self.icon = tk.PhotoImage(file=str(ASSETS / "icon.png"))
            root.iconphoto(True, self.icon)
        except tk.TclError:
            pass
        self.bot = BotProcess()
        self.probe = GameProbe()
        self.session = Session()
        self.feed: deque[tuple[float, str, str]] = deque(maxlen=2000)  # (time, kind, text)
        self.tail = EventTail(Path("logs") / "events.jsonl")
        self.started_settings: Settings | None = None
        self.last_probe = 0.0
        self.last_output = ""
        self.game_status = ("off", t("Looking for Idle Slayer…"))
        self.added = 0  # lines ever added to the feed; the texts are redrawn only when it grows
        self.update_tag: str | None = None  # set by the update check's thread, shown by poll()
        self.drawn = -1

        self.build_sidebar()
        self.content = ttk.Frame(root, padding=(24, 20, 24, 16))
        self.content.pack(side="left", fill="both", expand=True)
        self.pages: dict[str, ttk.Frame] = {}
        self.settings_page = SettingsPage(self.content, config_path, self.settings_saved, self.check_game_settings)
        self.pages["Settings"] = self.settings_page
        self.tree_page = TreePage(self.content, self.settings_page.tree_order, self.settings_page.set_tree_order)
        self.pages["Tree order"] = self.tree_page
        for name, build in (("Dashboard", self.build_dashboard), ("Activity", self.build_activity),
                            ("Help", self.build_help)):
            self.pages[name] = ttk.Frame(self.content)
            build(self.pages[name])
        self.use_log_dir(self.settings_page.settings)
        self.show("Settings" if self.settings_page.load_error else "Dashboard")
        root.protocol("WM_DELETE_WINDOW", self.close)
        threading.Thread(target=self.check_for_update, daemon=True).start()
        self.refresh()
        root.after(250, self.poll)

    # --- layout ---
    def build_sidebar(self) -> None:
        side = ttk.Frame(self.root, padding=(0, 18, 0, 14))
        side.pack(side="left", fill="y")
        try:
            self.logo = tk.PhotoImage(file=str(ASSETS / "logo.png"))
            ttk.Label(side, image=self.logo).pack(anchor="w", padx=16, pady=(0, 22))
        except tk.TclError:
            ttk.Label(side, text="Idle Runner", style="Title.TLabel").pack(anchor="w", padx=16, pady=(0, 22))
        self.nav = {}
        for name in PAGES:
            self.nav[name] = ttk.Button(side, text=t(name), style="Nav.TButton", command=lambda n=name: self.show(n))
            self.nav[name].pack(fill="x")
        ttk.Frame(side).pack(fill="both", expand=True)
        self.support_button: ttk.Button | None = None
        if DONATE_URL:
            self.support_button = ttk.Button(side, text=t("Support Idle Runner"), style="Support.TButton",
                                             command=lambda: webbrowser.open(DONATE_URL))
            self.support_button.pack(fill="x", padx=16, pady=(0, 14))
        self.update_label = ttk.Label(side, text="", style="Muted.TLabel", cursor="hand2", wraplength=200)
        self.update_label.pack(anchor="w", padx=18)
        ttk.Label(side, text=t("Version {version}", version=__version__), style="Muted.TLabel").pack(anchor="w",
                                                                                                padx=18)

    def show(self, name: str) -> None:
        for page_name, page in self.pages.items():
            page.pack_forget()
            self.nav[page_name].configure(style="Nav.TButton")
        self.pages[name].pack(fill="both", expand=True)
        self.nav[name].configure(style="Current.Nav.TButton")

    def build_dashboard(self, page: ttk.Frame) -> None:
        head = ttk.Frame(page)
        head.pack(fill="x")
        text = ttk.Frame(head)
        text.pack(side="left", fill="x", expand=True)
        self.state_label = ttk.Label(text, text=t("Stopped"), style="Title.TLabel")
        self.state_label.pack(anchor="w")
        self.state_detail = ttk.Label(text, text="", style="Muted.TLabel", wraplength=560, justify="left")
        self.state_detail.pack(anchor="w", pady=(2, 0))
        game = ttk.Frame(text)
        game.pack(anchor="w", pady=(10, 0))
        self.game_led = tk.Canvas(game, width=12, height=12, highlightthickness=0, bg=PALETTE.bg)
        self.game_led.pack(side="left", padx=(0, 8))
        self.game_label = ttk.Label(game, text=t("Looking for Idle Slayer…"))
        self.game_label.pack(side="left")
        self.start_button = ttk.Button(head, text=t("Start"), style="Start.TButton", command=self.start_or_stop)
        self.start_button.pack(side="right", anchor="n")
        self.buy_button = ttk.Button(head, text=t("Buy now"), command=self.buy_now)  # a shop visit at the next check
        self.buy_button.pack(side="right", anchor="s", padx=12)
        self.restart_bar = ttk.Frame(page)
        ttk.Label(self.restart_bar, text=t("Settings changed. Restart the bot to use them."),
                  style="Warning.TLabel").pack(side="left")
        ttk.Button(self.restart_bar, text=t("Restart"), command=self.restart).pack(side="left", padx=10)

        stats = panel(page, t("This run"))
        stats.outer.pack(fill="x", pady=(18, 14))
        self.stat_values: dict[str, ttk.Label] = {}
        grid = ttk.Frame(stats, style="Panel.TFrame")
        grid.pack(fill="x", pady=(8, 0))
        for i, name in enumerate(STATS):
            cell = ttk.Frame(grid, style="Panel.TFrame")
            cell.grid(row=i // 5, column=i % 5, sticky="w", padx=(0, 26), pady=(0, 10))
            self.stat_values[name] = ttk.Label(cell, text="–", style="Stat.Panel.TLabel")
            self.stat_values[name].pack(anchor="w")
            ttk.Label(cell, text=t(name), style="Muted.Panel.TLabel").pack(anchor="w")

        recent = panel(page, t("Latest"))
        recent.outer.pack(fill="both", expand=True)
        self.recent = tk.Text(recent, height=8, wrap="word", bd=0, highlightthickness=0, padx=0, pady=6,
                              state="disabled", cursor="arrow")
        self.recent.pack(fill="both", expand=True)

        note = ttk.Frame(page)
        note.pack(fill="x", pady=(14, 0))
        ttk.Label(note, text=t("Something went wrong?")).pack(side="left")
        self.note = ttk.Entry(note)
        self.note.pack(side="left", fill="x", expand=True, padx=10)
        self.note.bind("<Return>", lambda e: self.mark_problem())
        ttk.Button(note, text=t("Mark problem"), command=self.mark_problem).pack(side="left")

    def build_activity(self, page: ttk.Frame) -> None:
        bar = ttk.Frame(page)
        bar.pack(fill="x", pady=(0, 10))
        self.filter = tk.StringVar(value="Everything")
        for name in FILTERS:
            ttk.Radiobutton(bar, text=t(name), value=name, variable=self.filter, command=self.render_activity).pack(
                side="left", padx=(0, 12))
        self.raw = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text=t("Bot output"), variable=self.raw, command=self.render_activity).pack(side="left")
        tools = ttk.Frame(page)  # below the feed: the filters fill the top row, longer in Spanish
        tools.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(tools, text=t("Statistics"), command=self.show_stats).pack(side="right")
        ttk.Button(tools, text=t("Open logs folder"), command=lambda: open_folder(self.log_dir)).pack(side="right",
                                                                                                padx=8)
        body = panel(page)
        body.outer.pack(fill="both", expand=True)
        self.activity = tk.Text(body, wrap="word", bd=0, highlightthickness=0, state="disabled")
        scroll = ttk.Scrollbar(body, command=self.activity.yview)
        self.activity.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.activity.pack(fill="both", expand=True)
        for widget in (self.activity, self.recent):
            widget.tag_configure("time", foreground=PALETTE.muted)
            for kind, colour in KIND_COLOURS.items():
                widget.tag_configure(kind, foreground=colour)

    def build_help(self, page: ttk.Frame) -> None:
        for title, text in ((t("Set up the game"), t(SETUP)), (t("Safety"), t(SAFETY))):
            body = panel(page, title)
            body.outer.pack(fill="x", pady=(0, 14))
            ttk.Label(body, text=text, style="Panel.TLabel", justify="left", wraplength=720).pack(anchor="w",
                                                                                               pady=(6, 0))
        links = panel(page, t("Links"))
        links.outer.pack(fill="x")
        links_list = [(t("Project page on GitHub"), f"https://github.com/{REPO}"),
                      (t("Report a problem"), f"https://github.com/{REPO}/issues/new/choose"),
                      (t("All versions"), f"https://github.com/{REPO}/releases")]
        if DONATE_URL:
            links_list.append((t("Support Idle Runner"), DONATE_URL))
        for text, url in links_list:
            link = ttk.Label(links, text=text, style="Link.Panel.TLabel", cursor="hand2")
            link.pack(anchor="w", pady=(6, 0))
            link.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

    # --- the bot ---
    def start_or_stop(self) -> None:
        if self.bot.running():
            self.bot.stop()
            self.state_detail.configure(text=t("Stopping…"))
            return
        if not self.settings_page.save():
            self.show("Settings")
            return
        self.started_settings = self.settings_page.settings
        self.last_output = ""
        self.bot.start(self.config_path)
        self.refresh()

    def restart(self) -> None:
        self.bot.stop_and_wait()
        self.start_or_stop()

    def check_game_settings(self) -> None:
        """The game's settings are checked once a day: check them again, now or at the next Start."""
        if self.bot.send("check-settings"):
            text = t("The bot checks the game's settings in a few seconds, while the game is in front.")
        else:
            update_state(state_path(self.config_path), settings_ok_date=None)
            text = t("The bot checks the game's settings at the next Start.")
        self.settings_page.show_message(text)

    def settings_saved(self, settings: Settings) -> None:
        self.use_log_dir(settings)
        self.refresh()

    def use_log_dir(self, settings: Settings) -> None:
        self.log_dir = Path(settings.log_dir)
        path = self.log_dir / "events.jsonl"
        if path != self.tail.path:
            self.tail = EventTail(path)
            self.tail.offset = path.stat().st_size if path.exists() else 0  # this window's runs only

    def poll(self) -> None:
        while not self.bot.lines.empty():
            line = self.bot.lines.get()
            self.last_output = line or self.last_output
            self.add(time.time(), "raw", line)
        for record in self.tail.read_new():
            apply(self.session, record)
            described = describe(record, self.session)
            if described:
                self.add(record.get("ts", time.time()), *described)
        if self.update_tag and not self.update_label.cget("text"):
            self.show_update(self.update_tag)
        if not self.bot.running() and time.monotonic() - self.last_probe > 2:
            self.last_probe = time.monotonic()
            self.game_status = self.probe.status(self.settings_page.settings.window_name)
        self.refresh()
        self.root.after(250, self.poll)

    def refresh(self) -> None:
        running = self.bot.running()
        s = self.session
        if running and s.state == "paused":
            title, detail = t("Paused"), t("{reason}. Click the game to resume.", reason=t(s.detail).capitalize())
        elif running and s.state == "game lost":
            title, detail = t("Waiting for the game"), t("Its window closed. The bot looks for it every 2 seconds.")
        elif running and s.doing:  # the window polls every 250 ms: a shorter routine may not show
            title, detail = t("Running"), f"{t(s.doing)}…"
        elif running:
            title, detail = t("Running"), t("Playing while the game is in front. Click another window to pause it.")
        elif self.bot.exit_code() not in (None, 0):
            title = t("Stopped")
            detail = self.last_output or t("The bot stopped (exit code {code}).", code=self.bot.exit_code())
        else:
            title, detail = t("Stopped"), t("Press Start, then click the game.")
        self.state_label.configure(text=title)
        self.state_detail.configure(text=detail)
        self.start_button.configure(text=t("Stop") if running else t("Start"),
                                    style="Stop.TButton" if running else "Start.TButton")
        level, text = self.game_status
        if running:
            level, text = ("ok", t("Idle Slayer found, 1280×720")) if s.state == "running" else (level, text)
        self.game_led.delete("all")
        self.game_led.create_rectangle(1, 1, 11, 11, width=0, fill={"ok": "#2FD158", "warning": PALETTE.warning}.get(
            level, PALETTE.danger))
        self.game_label.configure(text=text)
        changed = running and self.started_settings not in (None, self.settings_page.settings)
        if changed:
            self.restart_bar.pack(fill="x", pady=(12, 0), after=self.start_button.master)
        else:
            self.restart_bar.pack_forget()
        minutes = int((time.time() - s.started_ts) // 60) if running and s.started_ts else None
        values = {"Running for": "–" if minutes is None else f"{minutes // 60}h {minutes % 60:02d}m",
                  "Upgrades": s.upgrades, "Equipment": s.equipment, "Ascensions": s.ascensions,
                  "Last bonus": "–" if s.last_bonus is None else f"+{s.last_bonus}%", "Tree nodes": s.tree_nodes,
                  "Minigames": s.minigames, "Silver boxes": s.boxes, "Problems": s.problems}
        for name, value in values.items():
            self.stat_values[name].configure(text=str(value))
        self.stat_values["Problems"].configure(foreground=PALETTE.danger_text if s.problems else PALETTE.gold)
        if set(self.tree_page.bought) != s.nodes_bought:
            self.tree_page.set_bought(set(s.nodes_bought))
        if self.drawn != self.added:
            self.drawn = self.added
            self.write(self.recent, [item for item in self.feed if item[1] != "raw"][-8:])
            self.render_activity()

    def render_activity(self) -> None:
        kinds = FILTERS[self.filter.get()]
        items = [item for item in self.feed
                 if (item[1] == "raw") == self.raw.get() and (kinds is None or item[1] in kinds or item[1] == "raw")]
        self.write(self.activity, items[-500:], follow=True)

    def write(self, widget: tk.Text, items: list[tuple[float, str, str]], follow: bool = False) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        for ts, kind, text in items:
            widget.insert("end", time.strftime("%H:%M  ", time.localtime(ts)), "time")
            widget.insert("end", text + "\n", kind)
        if not items:
            widget.insert("end", t("Nothing yet. Press Start on the Dashboard.") if widget is self.activity
                          else t("Nothing yet."), "state")
        widget.configure(state="disabled")
        if follow:
            widget.see("end")

    def add(self, ts: float, kind: str, text: str) -> None:
        self.feed.append((ts, kind, text))
        self.added += 1

    # --- other actions ---
    def mark_problem(self) -> None:
        text = self.note.get().strip() or t("(no description)")
        setup_logging(self.log_dir)
        folder = mark(self.log_dir, text)
        self.note.delete(0, "end")
        self.add(time.time(), "state", t("Marked: {text} (saved in {folder})", text=text, folder=folder))
        self.refresh()

    def buy_now(self) -> None:
        """Ask the running bot to visit the shop at its next slow check, as its timer would."""
        if self.bot.send("buy-now"):
            text = t("The bot buys at its next check, in a few seconds.")
        else:
            text = t("Start the bot first: it buys while it runs.")
        self.add(time.time(), "state", text)
        self.refresh()

    def show_stats(self) -> None:
        for line in summarize(self.log_dir / "events.jsonl"):
            self.add(time.time(), "raw", line)
        self.raw.set(True)
        self.render_activity()

    def check_for_update(self) -> None:
        """In a thread: no Tk calls here (Tk belongs to the main thread)."""
        tag = latest_tag()
        if tag and newer(__version__, tag):
            self.update_tag = tag

    def show_update(self, tag: str) -> None:
        self.update_label.configure(text=t("Version {version} is available", version=tag.lstrip("v")),
                                    style="Link.TLabel")
        self.update_label.bind("<Button-1>", lambda e: webbrowser.open(f"https://github.com/{REPO}/releases"))

    def close(self) -> None:
        if self.bot.running():
            if not messagebox.askyesno("Idle Runner", t("Stop the bot and quit?")):
                return
            self.bot.stop_and_wait()
        if self.settings_page.pending:
            self.settings_page.save()
        self.root.destroy()


def main(config_path: Path) -> int:
    if sys.platform == "win32":
        from idle_runner.win32 import enable_dpi_awareness
        enable_dpi_awareness()  # before any window: crisp text at 125 % or 150 % scaling
    try:  # the language first: every text is set as the window is built
        set_language(load_settings(config_path).language if config_path.exists() else "auto")
    except ValueError:  # the Settings page shows the problem
        set_language("auto")
    root = tk.Tk()
    App(root, config_path)
    root.mainloop()
    return 0
