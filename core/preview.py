from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
import struct
import zlib
from typing import Sequence


@dataclass
class RectSpec:
    x0: float
    y0: float
    x1: float
    y1: float
    color: tuple[int, int, int]


@dataclass
class RectPrismSpec:
    x0: float
    y0: float
    z0: float
    x1: float
    y1: float
    z1: float
    color: tuple[int, int, int]


def render_rect_preview(
    rects: Sequence[RectSpec],
    path: Path,
    size: tuple[int, int] = (800, 400),
    background: tuple[int, int, int] = (240, 244, 248),
) -> None:
    if not rects:
        rects = [RectSpec(-1.0, -1.0, 1.0, 1.0, (150, 150, 150))]

    width, height = size
    min_x = min(r.x0 for r in rects)
    max_x = max(r.x1 for r in rects)
    min_y = min(r.y0 for r in rects)
    max_y = max(r.y1 for r in rects)

    span_x = max_x - min_x
    span_y = max_y - min_y
    pad_x = span_x * 0.1 if span_x > 0 else 1.0
    pad_y = span_y * 0.1 if span_y > 0 else 1.0
    min_x -= pad_x
    max_x += pad_x
    min_y -= pad_y
    max_y += pad_y

    span_x = max(max_x - min_x, 1e-3)
    span_y = max(max_y - min_y, 1e-3)

    scale_x = (width - 1) / span_x
    scale_y = (height - 1) / span_y

    pixels = bytearray(width * height * 3)
    bg_r, bg_g, bg_b = background
    for i in range(0, len(pixels), 3):
        pixels[i : i + 3] = bytes((bg_r, bg_g, bg_b))

    def clamp(val: int, low: int, high: int) -> int:
        return max(low, min(high, val))

    for rect in rects:
        px0 = clamp(int(round((rect.x0 - min_x) * scale_x)), 0, width - 1)
        px1 = clamp(int(round((rect.x1 - min_x) * scale_x)), 0, width - 1)
        if px1 < px0:
            px0, px1 = px1, px0

        py_top = clamp(int(round((max_y - rect.y1) * scale_y)), 0, height - 1)
        py_bottom = clamp(int(round((max_y - rect.y0) * scale_y)), 0, height - 1)
        if py_bottom < py_top:
            py_top, py_bottom = py_bottom, py_top

        color = bytes(rect.color)
        for py in range(py_top, py_bottom + 1):
            base = py * width * 3
            for px in range(px0, px1 + 1):
                idx = base + px * 3
                pixels[idx : idx + 3] = color

    _write_png(path, width, height, pixels)


def render_isometric_preview(
    prisms: Sequence[RectPrismSpec],
    path: Path,
    size: tuple[int, int] = (900, 600),
    background: tuple[int, int, int] = (230, 234, 238),
) -> None:
    if not prisms:
        prisms = [
            RectPrismSpec(-50, -50, 0, 50, 50, 100, (150, 150, 150)),
        ]

    def iso_project(x: float, y: float, z: float) -> tuple[float, float]:
        u = (x - y) * 0.5
        v = (x + y) * 0.25 - z
        return u, v

    polygons: list[tuple[list[tuple[float, float]], tuple[int, int, int]]] = []
    min_u = float("inf")
    max_u = float("-inf")
    min_v = float("inf")
    max_v = float("-inf")

    def add_poly(points, color):
        nonlocal min_u, max_u, min_v, max_v
        polygons.append((points, color))
        for u, v in points:
            min_u = min(min_u, u)
            max_u = max(max_u, u)
            min_v = min(min_v, v)
            max_v = max(max_v, v)

    for prism in prisms:
        top = [
            iso_project(prism.x0, prism.y0, prism.z1),
            iso_project(prism.x1, prism.y0, prism.z1),
            iso_project(prism.x1, prism.y1, prism.z1),
            iso_project(prism.x0, prism.y1, prism.z1),
        ]
        side_y = [
            iso_project(prism.x1, prism.y0, prism.z0),
            iso_project(prism.x1, prism.y0, prism.z1),
            iso_project(prism.x1, prism.y1, prism.z1),
            iso_project(prism.x1, prism.y1, prism.z0),
        ]
        side_x = [
            iso_project(prism.x0, prism.y1, prism.z0),
            iso_project(prism.x0, prism.y1, prism.z1),
            iso_project(prism.x1, prism.y1, prism.z1),
            iso_project(prism.x1, prism.y1, prism.z0),
        ]
        add_poly(side_y, _adjust_color(prism.color, 0.7))
        add_poly(side_x, _adjust_color(prism.color, 0.85))
        add_poly(top, prism.color)

    width, height = size
    span_u = max(max_u - min_u, 1e-3)
    span_v = max(max_v - min_v, 1e-3)
    margin = 0.1
    scale = min(
        (width * (1 - 2 * margin)) / span_u,
        (height * (1 - 2 * margin)) / span_v,
    )

    def to_pixel(u: float, v: float) -> tuple[float, float]:
        px = (u - min_u) * scale + width * margin
        py = (max_v - v) * scale + height * margin
        return px, py

    pixel_polys = [
        ([to_pixel(u, v) for u, v in poly], color) for poly, color in polygons
    ]

    pixels = bytearray(width * height * 3)
    bg_r, bg_g, bg_b = background
    for i in range(0, len(pixels), 3):
        pixels[i : i + 3] = bytes((bg_r, bg_g, bg_b))

    for pts, color in pixel_polys:
        _fill_polygon(pixels, width, height, pts, color)

    _write_png(path, width, height, pixels)


def _write_png(path: Path, width: int, height: int, pixels: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    row_bytes = width * 3
    for y in range(height):
        raw.append(0)
        start = y * row_bytes
        raw.extend(pixels[start : start + row_bytes])
    compressed = zlib.compress(bytes(raw), level=9)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    with path.open("wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(chunk(b"IHDR", ihdr))
        fh.write(chunk(b"IDAT", compressed))
        fh.write(chunk(b"IEND", b""))


def _fill_polygon(pixels: bytearray, width: int, height: int, pts, color):
    if len(pts) < 3:
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x = max(int(math.floor(min(xs))), 0)
    max_x = min(int(math.ceil(max(xs))), width - 1)
    min_y = max(int(math.floor(min(ys))), 0)
    max_y = min(int(math.ceil(max(ys))), height - 1)
    col = bytes(color)
    for py in range(min_y, max_y + 1):
        for px in range(min_x, max_x + 1):
            if _point_in_poly(px + 0.5, py + 0.5, pts):
                idx = (py * width + px) * 3
                pixels[idx : idx + 3] = col


def _point_in_poly(x: float, y: float, pts) -> bool:
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        ):
            inside = not inside
        j = i
    return inside


def _adjust_color(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in color)
