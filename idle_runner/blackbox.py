"""Black box: records the game window all the time and keeps the last minutes of it, so a problem can be
looked at afterwards without reproducing it. Not in the original.

It runs as its own process (`python -m idle_runner blackbox`, started by `run`), so grabbing and
compressing frames (22-27 ms each, measured 2026-10-22) never delays the bot's key timings.
Frames go to log_dir/blackbox/; frames worth keeping are hard-linked into log_dir/marks/<time>-<why>/:
around every anomaly the bot logs, and when the user runs `mark`.
"""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from idle_runner.game import Backend, GameUnavailable, WindowGone
from idle_runner.log import event
from idle_runner.png import write_png

PRUNE_EVERY_MS = 60_000
WINDOW_RETRY_MS = 2000
KEEP_BEFORE_S = 60  # an anomaly keeps the frames from a minute before it...
KEEP_AFTER_S = 30   # ...to 30 s after (e.g. whether the jumper got a box after shopping stopped for it)
# Events that mean something went wrong or needs a look.
ANOMALIES = frozenset({
    "stuck", "Sync timeout", "tick_crash", "repeater_error", "Bot stopped after repeated errors",
    "Game window lost", "click_outside_window", "Shop click retried", "Shop tab not shown",
    "AutoUpgrade shop not open", "Claim quests: shop not open", "Upgrade click had no effect",
    "Shopping stopped for a Random Box", "Ascend skipped", "Coins reading timed out",
    "Chesthunt saver not found", "Life saver skipped: saver not found", "Portal destination not found",
    "Ascending Heights timed out after 4 minutes", "Ascend bonus not shown", "Ascend bonus unreadable",
    "Tree not shown", "Tree node not bought", "Tree jewel offer closed", "Extra daily quests click had no effect",
    "Minions SP not readable", "Minions tab not shown", "Minions buttons unknown", "Minion not claimed",
    "Minions daily bonus click had no effect", "Game setting wrong", "Game setting not found", "Game settings not checked",
})


class BlackBox:
    def __init__(self, backend: Backend, log_dir: Path, minutes: float) -> None:
        self.backend = backend
        self.log_dir = log_dir
        self.folder = log_dir / "blackbox"
        self.minutes = minutes
        self.folder.mkdir(parents=True, exist_ok=True)
        self._events: BinaryIO | None = None  # events.jsonl, opened at its end once it exists
        self._pending: list[tuple[float, float, str, str]] = []  # (keep at, since, folder name, note)

    def capture(self) -> Path | None:
        """Save the client area as PNG; skipped while the game isn't focused (the bot is paused then)."""
        if not self.backend.is_active():
            return None
        width, height = self.backend.size()
        path = self.folder / f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.png"
        write_png(path, self.backend.grab(0, 0, width, height))
        return path

    def prune(self) -> None:
        """Delete frames older than `minutes`."""
        cutoff = time.time() - self.minutes * 60
        for path in self.folder.glob("*.png"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except FileNotFoundError:
                continue  # another black box (e.g. a second bot) pruned it first

    def watch_events(self, now: float) -> None:
        """Read the bot's new events; KEEP_AFTER_S after an anomaly, keep the frames around it."""
        if self._events is None:
            path = self.log_dir / "events.jsonl"
            if not path.exists():
                return
            self._events = path.open("rb")
            self._events.seek(0, os.SEEK_END)
        while True:
            start = self._events.tell()
            line = self._events.readline()
            if not line.endswith(b"\n"):  # nothing new, or a line still being written
                self._events.seek(start)
                break
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("event") in ANOMALIES:
                name = f"{datetime.fromtimestamp(record['ts']).strftime('%Y%m%d-%H%M%S')}-{record['event']}"
                self._pending.append((now + KEEP_AFTER_S, record["ts"] - KEEP_BEFORE_S,
                                      re.sub(r"\W+", "-", name).strip("-"), line.decode().strip()))
        for due, since, name, note in [p for p in self._pending if p[0] <= now]:
            keep(self.log_dir, name, since, note)
        self._pending = [p for p in self._pending if p[0] > now]

    def run(self, fps: float) -> None:
        """Record at `fps` until the parent process (the bot) is gone, even if it was killed."""
        b = self.backend
        parent = os.getppid()
        next_prune = 0.0
        while os.getppid() == parent:
            start = b.now_ms()
            try:
                self.capture()
            except WindowGone:  # the game was closed or restarted
                b.sleep_ms(WINDOW_RETRY_MS)
                try:
                    b.find_window()
                except GameUnavailable:
                    pass
            except GameUnavailable:
                pass  # e.g. minimized
            self.watch_events(time.time())
            if start >= next_prune:
                self.prune()
                next_prune = start + PRUNE_EVERY_MS
            b.sleep_ms(1000 / fps - (b.now_ms() - start))


def keep(log_dir: Path, name: str, since: float, note: str) -> tuple[Path, int]:
    """Hard-link the black box frames saved since `since` (epoch seconds) into log_dir/marks/<name>/,
    with a note. Nothing is copied, and the black box deleting its own copy later doesn't touch them."""
    folder = log_dir / "marks" / name
    folder.mkdir(parents=True, exist_ok=True)
    frames = 0
    for path in sorted((log_dir / "blackbox").glob("*.png")):
        try:
            if path.stat().st_mtime >= since:
                os.link(path, folder / path.name)
                frames += 1
        except (FileNotFoundError, FileExistsError):
            continue  # pruned meanwhile, or already kept by an overlapping mark
    (folder / "note.txt").write_text(note + "\n", encoding="utf-8")
    return folder, frames


def mark(log_dir: Path, text: str, minutes: float = 5) -> Path:
    """The user saw a problem: keep the black box's last `minutes` and log the note."""
    folder, frames = keep(log_dir, datetime.now().strftime("%Y%m%d-%H%M%S"), time.time() - minutes * 60, text)
    event("User note", text=text, frames=frames, folder=str(folder))
    return folder
