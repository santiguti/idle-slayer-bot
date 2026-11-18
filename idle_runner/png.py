"""Minimal PNG writer and reader (stdlib only): debug frame dumps and the tree's reference image."""
import struct
import zlib
from pathlib import Path

import numpy as np


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


def write_png(path: Path, rgb: np.ndarray) -> None:
    """Write an (h, w, 3) uint8 RGB array as an 8-bit truecolor PNG."""
    height, width, _ = rgb.shape
    # Each scanline starts with filter type 0 (none).
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 6)) + _chunk(b"IEND", b"")
    path.write_bytes(png)


def read_png(path: Path) -> np.ndarray:
    """Read a PNG written by write_png (8-bit RGB, filter 0 on every row)."""
    data = path.read_bytes()
    width, height = struct.unpack(">II", data[16:24])
    raw = zlib.decompress(data[data.index(b"IDAT") + 4:data.index(b"IEND") - 8])
    rows = np.frombuffer(raw, dtype=np.uint8).reshape(height, 1 + width * 3)
    return rows[:, 1:].reshape(height, width, 3).copy()
