"""Command line entry point: python -m idle_runner <command>."""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from idle_runner import __version__
from idle_runner.blackbox import BlackBox, mark
from idle_runner.png import write_png
from idle_runner.process import self_command, single_instance, stop_on_stdin_eof
from idle_runner.config import Settings, load_settings
from idle_runner.game import Game, GameUnavailable, open_backend
from idle_runner.log import setup_logging
from idle_runner.repeater import Repeater
from idle_runner.runner import Runner, install_stop_signals
from idle_runner.state import state_path
from idle_runner.stats import summarize


def run_probe(args: argparse.Namespace) -> int:
    """Calibration/debugging: window info, colours, timings, a screenshot and manual input tests."""
    backend = open_backend(args.name)
    if args.delay:
        print(f"waiting {args.delay:g} s: focus the game window now...")
        time.sleep(args.delay)
    width, height = backend.size()
    origin_x, origin_y = backend.origin()
    print(f"window 0x{backend.window_id:x}: client {width}x{height} at screen ({origin_x}, {origin_y}), "
          f"focused={backend.is_active()}")

    if (args.key or args.click) and not backend.is_active():
        print("error: refusing to send input while the game is not focused (use --delay)", file=sys.stderr)
        return 1
    if args.key:
        backend.key(args.key, True)
        time.sleep(0.05)
        backend.key(args.key, False)
        print(f"tapped {args.key}")
    if args.click:
        x, y = args.click
        backend.move(x, y)
        backend.button(1, True)
        time.sleep(0.05)
        backend.button(1, False)
        print(f"clicked client ({x}, {y})")
    if args.pixel:
        x, y = args.pixel
        r, g, b = (int(c) for c in backend.grab(x, y, 1, 1)[0, 0])
        print(f"pixel client ({x}, {y}) = 0x{r:02X}{g:02X}{b:02X}")

    start = time.perf_counter()
    for _ in range(100):
        backend.grab(width // 2, height // 2, 1, 1)
    one_pixel_ms = (time.perf_counter() - start) * 10
    start = time.perf_counter()
    for _ in range(10):
        frame = backend.grab(0, 0, width, height)
    full_frame_ms = (time.perf_counter() - start) * 100
    print(f"grab timings: 1 px {one_pixel_ms:.2f} ms, full frame {full_frame_ms:.1f} ms")

    if args.find is not None:
        target = np.array([(args.find >> 16) & 0xFF, (args.find >> 8) & 0xFF, args.find & 0xFF], dtype=np.uint8)
        ys, xs = np.nonzero((frame == target).all(axis=2))
        first = list(zip(xs[:20].tolist(), ys[:20].tolist()))
        print(f"0x{args.find:06X}: {len(xs)} client pixels, first: {first}")

    write_png(args.out, frame)
    print(f"saved {args.out}")
    return 0


def read_settings(config_path: Path) -> Settings | None:
    """Load the config, or print why it can't be used and return None."""
    if not config_path.exists():
        print(f"error: {config_path} not found; copy config.example.toml to {config_path} and edit it",
              file=sys.stderr)
        return None
    try:
        return load_settings(config_path)
    except ValueError as exc:  # also covers tomllib.TOMLDecodeError
        print(f"error: {exc}", file=sys.stderr)
        return None


def run_bot(config_path: Path, stop_on_eof: bool = False) -> int:
    settings = read_settings(config_path)
    if settings is None:
        return 1
    instance = single_instance()
    if instance is None:
        print("error: another Idle Runner bot is already running", file=sys.stderr)
        return 1
    log_dir = Path(settings.log_dir)
    setup_logging(log_dir, settings.log_level)
    backend = open_backend(settings.window_name)
    game = Game(backend, tolerance=settings.color_tolerance,
                frames_dir=log_dir / "frames" if settings.save_frames else None)
    jumper = Repeater(game, ("Up", "Right"), settings.jump_interval_ms, "jumper")
    runner = Runner(game, settings, jumper, state_path(config_path))
    install_stop_signals()
    if stop_on_eof:  # the window's "Check game settings now" and "Buy now" arrive as lines
        stop_on_stdin_eof(sys.stdin, commands={"check-settings": runner.settings_request.set,
                                                "buy-now": runner.buy_request.set})
    recorder = None
    if settings.blackbox_fps:
        # It stops when this pipe closes: here, or by the OS if this process is killed outright.
        recorder = subprocess.Popen(self_command("blackbox", "--config", str(config_path), "--stop-on-stdin-eof"),
                                    stdin=subprocess.PIPE)
    try:
        runner.run()
    finally:
        if recorder:
            recorder.stdin.close()
            try:
                recorder.wait(timeout=3)
            except subprocess.TimeoutExpired:
                recorder.terminate()
        instance.close()
    return 0


def run_blackbox(config_path: Path, stop_on_eof: bool = False) -> int:
    settings = read_settings(config_path)
    if settings is None:
        return 1
    if not settings.blackbox_fps:
        print("error: the black box is off (blackbox_fps = 0)", file=sys.stderr)
        return 1
    install_stop_signals()
    if stop_on_eof:
        stop_on_stdin_eof(sys.stdin)
    box = BlackBox(open_backend(settings.window_name), Path(settings.log_dir), settings.blackbox_minutes)
    try:
        box.run(settings.blackbox_fps)
    except KeyboardInterrupt:  # Ctrl+C reaches the bot and its black box alike
        pass
    return 0


def prepare_frozen_process() -> None:
    """A PyInstaller exe works from its own folder (config.toml and logs/ live there) and, built
    windowed, has no stdout/stderr to print to."""
    if not getattr(sys, "frozen", False):
        return
    os.chdir(Path(sys.executable).parent)
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    prepare_frozen_process()
    parser = argparse.ArgumentParser(prog="idle-runner")
    parser.add_argument("--version", action="version", version=f"Idle Runner {__version__}")
    sub = parser.add_subparsers(dest="command")

    probe = sub.add_parser("probe", help="inspect the game window (calibration and debugging)")
    probe.add_argument("--name", default="Idle Slayer", help="game window title")
    probe.add_argument("--delay", type=float, default=0, help="seconds to wait first (time to focus the game)")
    probe.add_argument("--out", type=Path, default=Path("probe.png"), help="where to save the screenshot")
    probe.add_argument("--pixel", type=int, nargs=2, metavar=("X", "Y"), help="print the colour at client X Y")
    probe.add_argument("--find", type=lambda s: int(s, 16), metavar="RRGGBB",
                       help="list client coordinates with exactly this colour")
    probe.add_argument("--key", help="tap this key (X keysym name, e.g. Up)")
    probe.add_argument("--click", type=int, nargs=2, metavar=("X", "Y"), help="left-click at client X Y")

    stats = sub.add_parser("stats", help="summarize logs/events.jsonl")
    stats.add_argument("--log-dir", type=Path, default=Path("logs"))

    run = sub.add_parser("run", help="run the bot (Ctrl+C to stop)")
    run.add_argument("--config", type=Path, default=Path("config.toml"))
    run.add_argument("--stop-on-stdin-eof", action="store_true", help="stop when stdin closes (used by the window)")

    gui = sub.add_parser("gui", help="open the Idle Runner window")
    gui.add_argument("--config", type=Path, default=Path("config.toml"))

    blackbox = sub.add_parser("blackbox", help="only record the game (`run` starts this by itself)")
    blackbox.add_argument("--config", type=Path, default=Path("config.toml"))
    blackbox.add_argument("--stop-on-stdin-eof", action="store_true", help="stop when stdin closes (used by the window)")

    mark_cmd = sub.add_parser("mark", help="note a problem; keeps the black box's last minutes in logs/marks/")
    mark_cmd.add_argument("text", help="what you saw")
    mark_cmd.add_argument("--minutes", type=float, default=5, help="how much of the recording to keep")
    mark_cmd.add_argument("--log-dir", type=Path, default=Path("logs"))

    argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(argv or ["gui"])  # no arguments at all: open the window
    if args.command is None:
        parser.error("a command is required")
    try:
        if args.command == "probe":
            return run_probe(args)
        if args.command == "stats":
            print("\n".join(summarize(args.log_dir / "events.jsonl")))
            return 0
        if args.command == "run":
            return run_bot(args.config, args.stop_on_stdin_eof)
        if args.command == "gui":
            from idle_runner.ui.app import main as gui_main  # tkinter only loads for the window
            return gui_main(args.config)
        if args.command == "blackbox":
            return run_blackbox(args.config, args.stop_on_stdin_eof)
        if args.command == "mark":
            setup_logging(args.log_dir)
            print(f"saved to {mark(args.log_dir, args.text, args.minutes)}")
            return 0
    except GameUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
