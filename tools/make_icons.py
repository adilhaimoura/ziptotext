#!/usr/bin/env python3
"""Rasterize Zip to Text app icons as PNG files."""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIZES = (16, 22, 24, 32, 48, 64, 128, 256)


def _png(width: int, height: int, rgba: bytearray) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw.extend(rgba[y * stride : (y + 1) * stride])

    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)),
            chunk(b"IEND", b""),
        ]
    )


def _blend(dst: bytearray, idx: int, color: tuple[int, int, int, int], cover: float) -> None:
    if cover <= 0:
        return
    cover = min(1.0, cover)
    sr, sg, sb, sa = color
    sa = int(sa * cover)
    if sa <= 0:
        return
    dr, dg, db, da = dst[idx : idx + 4]
    inv = 255 - sa
    out_a = sa + da * inv // 255
    if out_a == 0:
        dst[idx : idx + 4] = b"\x00\x00\x00\x00"
        return
    dst[idx] = (sr * sa + dr * da * inv // 255) // out_a
    dst[idx + 1] = (sg * sa + dg * da * inv // 255) // out_a
    dst[idx + 2] = (sb * sa + db * da * inv // 255) // out_a
    dst[idx + 3] = out_a


def _fill_round_rect(
    px: bytearray,
    size: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    radius: float,
    color: tuple[int, int, int, int],
) -> None:
    for y in range(size):
        cy = y + 0.5
        for x in range(size):
            cx = x + 0.5
            dx = 0.0
            dy = 0.0
            if cx < x0 + radius:
                dx = x0 + radius - cx
            elif cx > x1 - radius:
                dx = cx - (x1 - radius)
            if cy < y0 + radius:
                dy = y0 + radius - cy
            elif cy > y1 - radius:
                dy = cy - (y1 - radius)
            dist = math.hypot(dx, dy) if dx and dy else max(dx, dy)
            if cx < x0 or cx > x1 or cy < y0 or cy > y1:
                continue
            cover = 1.0
            if dx and dy:
                cover = max(0.0, min(1.0, radius + 0.5 - dist))
            if cover > 0:
                _blend(px, (y * size + x) * 4, color, cover)


def _fill_rect(
    px: bytearray,
    size: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    color: tuple[int, int, int, int],
) -> None:
    for y in range(max(0, int(y0)), min(size, int(y1) + 1)):
        for x in range(max(0, int(x0)), min(size, int(x1) + 1)):
            cover_x = min(x + 1, x1) - max(x, x0)
            cover_y = min(y + 1, y1) - max(y, y0)
            cover = max(0.0, cover_x) * max(0.0, cover_y)
            if cover > 0:
                _blend(px, (y * size + x) * 4, color, cover)


def render(size: int) -> bytes:
    px = bytearray(size * size * 4)
    s = size / 256.0

    _fill_round_rect(px, size, 8 * s, 8 * s, 248 * s, 248 * s, 56 * s, (15, 23, 42, 255))
    _fill_round_rect(px, size, 40 * s, 52 * s, 152 * s, 200 * s, 14 * s, (251, 191, 36, 255))
    _fill_rect(px, size, 84 * s, 52 * s, 108 * s, 200 * s, (15, 23, 42, 46))

    for y in (64, 90, 116, 142):
        _fill_round_rect(
            px, size, 90 * s, y * s, 102 * s, (y + 18) * s, 3 * s, (248, 250, 252, 255)
        )
    _fill_round_rect(px, size, 88 * s, 166 * s, 104 * s, 188 * s, 4 * s, (51, 65, 85, 255))

    _fill_round_rect(px, size, 104 * s, 78 * s, 210 * s, 214 * s, 14 * s, (255, 255, 255, 255))
    _fill_rect(px, size, 168 * s, 78 * s, 210 * s, 106 * s, (226, 232, 240, 255))

    _fill_round_rect(px, size, 128 * s, 124 * s, 192 * s, 132 * s, 4 * s, (37, 99, 235, 255))
    _fill_round_rect(px, size, 128 * s, 144 * s, 180 * s, 152 * s, 4 * s, (148, 163, 184, 255))
    _fill_round_rect(px, size, 128 * s, 164 * s, 188 * s, 172 * s, 4 * s, (148, 163, 184, 255))
    _fill_round_rect(px, size, 128 * s, 184 * s, 168 * s, 192 * s, 4 * s, (203, 213, 225, 255))
    return _png(size, size, px)


def main() -> None:
    for size in SIZES:
        out = ROOT / "share" / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "ziptotext.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(render(size))
        print(f"wrote {out}")
    pixmap = ROOT / "share" / "pixmaps" / "ziptotext.png"
    pixmap.parent.mkdir(parents=True, exist_ok=True)
    pixmap.write_bytes((ROOT / "share/icons/hicolor/48x48/apps/ziptotext.png").read_bytes())
    print(f"wrote {pixmap}")


if __name__ == "__main__":
    main()
