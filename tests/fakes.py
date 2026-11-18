"""Test doubles shared by the test suite."""
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from idle_runner.png import read_png  # noqa: F401  (the tests import it from here)

OFFSET = (8, 31)  # AutoIt window-frame offset used by every test


class FakeBackend:
    """In-memory stand-in for X11Backend.

    - `frame` is the client area; `paint()` takes AutoIt coordinates, like the code under test.
    - Virtual clock: `sleep_ms` advances `t`; every other backend call costs `cost_ms`.
    - `actions` logs input in client coordinates; `clicks()` / `taps()` summarize it.
    """

    def __init__(self, width: int = 1280, height: int = 720) -> None:
        self.frame = np.zeros((height, width, 3), dtype=np.uint8)
        self.t = 0.0
        self.cost_ms = 1.0
        self.active = True
        self.pointer_over = True  # False: another window is under the pointer
        self.realtime = False  # also really sleep (for threaded tests)
        self.stop_at: float | None = None  # raise KeyboardInterrupt once t reaches this
        self.pointer = (0, 0)
        self.actions: list[tuple] = []
        self.on_action: Callable[[tuple], None] | None = None

    def paint(self, x: int, y: int, color: int, w: int = 1, h: int = 1) -> None:
        cx, cy = x - OFFSET[0], y - OFFSET[1]
        self.frame[cy:cy + h, cx:cx + w] = ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)

    def clicks(self) -> list[tuple[int, int]]:
        """Left-button presses, in AutoIt coordinates."""
        return [(a[1] + OFFSET[0], a[2] + OFFSET[1]) for a in self.actions if a[0] == "click"]

    def taps(self) -> list[str]:
        """Names of pressed keys, in order."""
        return [a[1] for a in self.actions if a[0] == "key" and a[2]]

    # --- Backend protocol ---
    def find_window(self) -> None:
        pass

    def size(self) -> tuple[int, int]:
        return self.frame.shape[1], self.frame.shape[0]

    def is_active(self) -> bool:
        return self.active

    def grab(self, x: int, y: int, w: int, h: int) -> np.ndarray:
        self.t += self.cost_ms
        return self.frame[y:y + h, x:x + w]

    def move(self, x: int, y: int) -> None:
        self.pointer = (x, y)
        self._record(("move", x, y))

    def pointer_over_game(self) -> bool:
        return self.pointer_over

    def button(self, button: int, down: bool) -> None:
        if button == 1 and down:
            self._record(("click", *self.pointer))
        else:
            self._record(("button", button, down))

    def key(self, name: str, down: bool) -> None:
        self._record(("key", name, down))

    def now_ms(self) -> float:
        return self.t

    def sleep_ms(self, ms: float) -> None:
        if self.realtime:
            time.sleep(ms / 1000)
        self.t += ms
        if self.stop_at is not None and self.t >= self.stop_at:
            raise KeyboardInterrupt

    def _record(self, action: tuple) -> None:
        self.t += self.cost_ms
        self.actions.append(action)
        if self.on_action:
            self.on_action(action)


class FakeJumper:
    """Stand-in for the jump Repeater: records pauses instead of tapping keys."""

    def __init__(self) -> None:
        self.pauses = 0
        self.running = False
        self.stopped = False

    @contextmanager
    def paused(self) -> Iterator[None]:
        self.pauses += 1
        yield

    def resume(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.stopped = True
