"""AutoIt-compatible facade over the platform backend (X11 or Win32).

Every coordinate given to `Game` is an *AutoIt coordinate*, copied verbatim from the original
Idle Runner: relative to the game window's top-left corner *including* the Windows title bar
and borders (`Opt("PixelCoordMode", 0)` / `Opt("MouseCoordMode", 0)`). `offset` converts them
to client-area pixels, so each line of the port stays traceable to the AutoIt source.
"""
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Protocol

import numpy as np

from idle_runner.log import event, inputs, log
from idle_runner.png import write_png

Point = tuple[int, int]

STUCK_MS = 60_000  # safety net for loops the AutoIt original would spin in forever
LEFT, WHEEL_UP, WHEEL_DOWN = 1, 4, 5
HELD_KEYS = ("Up", "Right", "a", "d", "r")  # every key the bot ever presses


class GameUnavailable(Exception):
    """The game window can't be used right now (not focused, minimized or gone)."""


class WindowGone(GameUnavailable):
    """The game window was destroyed (e.g. the game was closed or restarted); find it again by name."""


class Backend(Protocol):
    """What Game needs from the outside world: X11Backend or Win32Backend in production, FakeBackend in tests."""

    def find_window(self) -> None: ...
    def size(self) -> tuple[int, int]: ...
    def is_active(self) -> bool: ...
    def grab(self, x: int, y: int, w: int, h: int) -> np.ndarray: ...
    def move(self, x: int, y: int) -> None: ...
    def pointer_over_game(self) -> bool: ...
    def button(self, button: int, down: bool) -> None: ...
    def key(self, name: str, down: bool) -> None: ...
    def now_ms(self) -> float: ...
    def sleep_ms(self, ms: float) -> None: ...


def open_backend(window_name: str) -> Backend:
    """The backend of this platform (imported lazily: python-xlib only exists on Linux)."""
    if sys.platform == "win32":
        from idle_runner.win32 import Win32Backend
        return Win32Backend(window_name)
    from idle_runner.x11 import X11Backend
    return X11Backend(window_name)


class Game:
    def __init__(self, backend: Backend, offset: Point = (8, 31), tolerance: int = 0,
                 frames_dir: Path | None = None) -> None:
        self.backend = backend
        self.ox, self.oy = offset
        self.tolerance = tolerance
        self.frames_dir = frames_dir
        self.size = backend.size()

    # --- time: AutoIt Sleep / TimerInit / TimerDiff ---
    def now(self) -> float:
        return self.backend.now_ms()

    def sleep(self, ms: float) -> None:
        self.backend.sleep_ms(ms)

    def is_active(self) -> bool:
        return self.backend.is_active()

    # --- screen ---
    def pixel_search(self, left: int, top: int, right: int, bottom: int, color: int,
                     variation: int = 0, quiet: bool = False) -> Point | None:
        """AutoIt PixelSearch.

        Returns the first pixel whose RGB channels are each within `variation` of `color`.
        Like AutoIt, it walks column by column (left to right), each column top to bottom;
        `left > right` or `top > bottom` reverses that direction. Bounds are inclusive and
        clipped to the client area. `quiet` logs only a hit: for checks the main loop makes many times a second.
        """
        found = self._search(left, top, right, bottom, color, variation)
        if found or not quiet:
            log.debug("pixel_search (%d,%d,%d,%d) 0x%06X v%d -> %s",
                      left, top, right, bottom, color, variation, found)
        return found

    def _search(self, left: int, top: int, right: int, bottom: int, color: int, variation: int) -> Point | None:
        width, height = self.size
        x0, x1 = sorted((left - self.ox, right - self.ox))
        y0, y1 = sorted((top - self.oy, bottom - self.oy))
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, width - 1), min(y1, height - 1)
        if x0 > x1 or y0 > y1:
            return None
        region = self.backend.grab(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
        target = np.array([(color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF], dtype=np.uint8)
        tolerance = variation + self.tolerance
        if tolerance == 0:
            mask = (region == target).all(axis=2)
        else:
            mask = (np.abs(region.astype(np.int16) - target.astype(np.int16)) <= tolerance).all(axis=2)
        if top > bottom:
            mask = mask[::-1]
        if left > right:
            mask = mask[:, ::-1]
        if not mask.any():
            return None
        # Column-major like AutoIt (x is the outer loop): search the transposed mask.
        col, row = divmod(int(mask.T.argmax()), mask.shape[0])
        y = y1 - row if top > bottom else y0 + row
        x = x1 - col if left > right else x0 + col
        return x + self.ox, y + self.oy

    def grab(self, left: int, top: int, right: int, bottom: int) -> np.ndarray:
        """RGB pixels of an AutoIt rectangle, bounds inclusive (for reading text such as the coins)."""
        return self.backend.grab(left - self.ox, top - self.oy, right - left + 1, bottom - top + 1)

    def pixel_is(self, x: int, y: int, color: int, quiet: bool = False) -> bool:
        return self.pixel_search(x, y, x, y, color, quiet=quiet) is not None

    def find_until(self, left: int, top: int, right: int, bottom: int, color: int,
                   timeout_ms: float = 15_000, label: str | None = None,
                   also: tuple[int, int, int] | None = None) -> Point | None:
        """FindPixelUntilFound from Common.au3: poll until the colour shows up or time runs out.

        With a `label`, a timeout is logged as a "Sync timeout" event plus a frame: minigames use
        it for the markers they synchronize on, so a missed sync is visible without DEBUG logs.
        `also` is a pixel (x, y, colour) that must show at the same time.
        """
        start = self.now()
        while self.now() - start <= timeout_ms:
            found = self._search(left, top, right, bottom, color, 0)
            if found and also and not self._search(also[0], also[1], also[0], also[1], also[2], 0):
                found = None
            if found:
                log.debug("find_until 0x%06X found at %s after %.0f ms", color, found, self.now() - start)
                return found
            self.sleep(1)
        log.debug("find_until 0x%06X in (%d,%d,%d,%d) timed out after %.0f ms",
                  color, left, top, right, bottom, timeout_ms)
        if label:
            event("Sync timeout", where=label, timeout_ms=timeout_ms)
            self.save_frame(f"sync-{label}")
        return None

    def find_window(self) -> None:
        """Find the game window again after WindowGone (raises GameUnavailable while there is none)."""
        self.backend.find_window()
        self.refresh_size()

    def refresh_size(self) -> tuple[int, int]:
        """Re-read the window size (it can change mid-run, e.g. if the window gets maximized)."""
        self.size = self.backend.size()
        return self.size

    # --- debugging aids ---
    def save_frame(self, label: str) -> Path | None:
        """Save the whole client area as PNG under frames_dir (no-op when frames are disabled)."""
        if self.frames_dir is None:
            return None
        try:
            rgb = self.backend.grab(0, 0, *self.size)
        except GameUnavailable:
            return None
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        path = self.frames_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]}-{label}.png"
        write_png(path, rgb)
        event("frame", label=label, path=str(path))
        return path

    def stuck(self, where: str, **fields: object) -> None:
        """Report a safety-net timeout (a loop the AutoIt original would spin in forever)."""
        event("stuck", where=where, **fields)
        self.save_frame(f"stuck-{where}")

    @contextmanager
    def routine(self, name: str) -> Iterator[None]:
        """Log start, end and duration of a routine; save a frame if it crashes."""
        start = self.now()
        event("routine_start", name=name)
        try:
            yield
        except GameUnavailable:
            event("routine_abort", name=name, ms=round(self.now() - start))
            raise
        except Exception:
            log.exception("routine %s crashed", name)
            self.save_frame(f"crash-{name}")
            raise
        event("routine_end", name=name, ms=round(self.now() - start))

    # --- input (refused while the game isn't focused) ---
    def _require_focus(self) -> None:
        if not self.backend.is_active():
            raise GameUnavailable("the game window is not focused")

    def _client(self, x: int, y: int) -> Point | None:
        cx, cy = x - self.ox, y - self.oy
        if 0 <= cx < self.size[0] and 0 <= cy < self.size[1]:
            return cx, cy
        event("click_outside_window", x=x, y=y)
        return None

    def _require_pointer_on_game(self) -> None:
        """C8, not in the original: never press a button over another window (a notification, Steam's
        overlay). X11 reports the window under the pointer right after an XTEST move (50 of 50 at 0 ms,
        measured 2026-10-26). Aborts the routine like a focus loss."""
        if not self.backend.pointer_over_game():
            event("click_outside_window", covered=True)
            raise GameUnavailable("another window is over the game under the pointer")

    def move(self, x: int, y: int) -> None:
        """MouseMove(x, y, 0)."""
        self._require_focus()
        inputs.info("move (%d,%d)", x, y)
        point = self._client(x, y)
        if point:
            self.backend.move(*point)

    def click(self, x: int, y: int, clicks: int = 1) -> None:
        """MouseClick("left", x, y, clicks, 0): instant move, 10 ms down/up delays (AutoIt defaults)."""
        self._require_focus()
        inputs.info("click (%d,%d) x%d", x, y, clicks)
        point = self._client(x, y)
        if point is None:
            return
        self.backend.move(*point)
        self._require_pointer_on_game()
        for _ in range(clicks):
            self.backend.button(LEFT, True)
            self.sleep(10)
            self.backend.button(LEFT, False)
            self.sleep(10)

    def mouse_down(self) -> None:
        self._require_focus()
        inputs.info("mouse down")
        self.backend.button(LEFT, True)

    def mouse_up(self) -> None:
        inputs.info("mouse up")
        self.backend.button(LEFT, False)  # never refused: a stuck button is worse than a stray release

    def wheel(self, up: bool, notches: int) -> None:
        """MouseWheel($MOUSE_WHEEL_UP/DOWN, notches) at the current pointer position."""
        self._require_focus()
        inputs.info("wheel %s x%d", "up" if up else "down", notches)
        button = WHEEL_UP if up else WHEEL_DOWN
        self._require_pointer_on_game()
        for _ in range(notches):
            self.backend.button(button, True)
            self.backend.button(button, False)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """MouseClickDrag("left", ...) at AutoIt's default speed: press, wait, glide, wait, release."""
        self._require_focus()
        inputs.info("drag (%d,%d) -> (%d,%d)", x1, y1, x2, y2)
        start, end = self._client(x1, y1), self._client(x2, y2)
        if start is None or end is None:
            return
        self.backend.move(*start)
        self._require_pointer_on_game()
        self.backend.button(LEFT, True)
        self.sleep(250)
        steps = 20
        for i in range(1, steps + 1):
            self.backend.move(start[0] + (end[0] - start[0]) * i // steps,
                              start[1] + (end[1] - start[1]) * i // steps)
            self.sleep(10)
        self.sleep(250)
        self.backend.button(LEFT, False)

    def key_down(self, key: str) -> None:
        self._require_focus()
        inputs.info("key down %s", key)
        self.backend.key(key, True)

    def key_up(self, key: str) -> None:
        inputs.info("key up %s", key)
        self.backend.key(key, False)  # never refused, like mouse_up

    def tap(self, key: str) -> None:
        """Send("{key}") / ControlSend with AutoIt's default 5 ms key delays."""
        self._require_focus()
        inputs.debug("tap %s", key)  # mostly the jumper: too frequent for INFO
        self.backend.key(key, True)
        self.sleep(5)
        self.backend.key(key, False)
        self.sleep(5)

    def hold(self, press_ms: float, post_ms: float = 0, key: str = "Up") -> None:
        """cSend() from Common.au3: hold `key` for press_ms, release, then wait post_ms.

        Focus is re-checked every 50 ms while the key is down, so a long hold (Ascending Heights
        holds `d` for 15 s) is released at once if the user switches windows, instead of
        auto-repeating into the newly focused window.
        """
        self._require_focus()
        inputs.info("hold %s %d ms, then %d ms", key, press_ms, post_ms)
        self.backend.key(key, True)
        try:
            deadline = self.now() + press_ms
            while (remaining := deadline - self.now()) > 0:
                self.sleep(min(50, remaining))
                self._require_focus()
        finally:
            self.backend.key(key, False)
        self.sleep(post_ms)

    def release_all(self) -> None:
        """Release every key and the mouse button (on exit, so nothing stays stuck in X)."""
        for key in HELD_KEYS:
            self.backend.key(key, False)
        self.backend.button(LEFT, False)
