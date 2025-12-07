from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence

from ..papierkorb.panels import (
    AxisDirection,
    Panel,
    PanelAxes,
    PanelKind,
    Vec3,
)
from .params import BoardOptions, BinDimensions


@dataclass
class AxisChunks:
    cells: List[int]
    total_cells: int
    total_mm: float


@dataclass
class OpenGridPanelSet:
    panels: List[Panel]
    length_chunks: AxisChunks
    width_chunks: AxisChunks
    height_chunks: AxisChunks
    tile_size_mm: float
    wall_thickness_mm: float

    @property
    def length_mm(self) -> float:
        return self.length_chunks.total_mm

    @property
    def width_mm(self) -> float:
        return self.width_chunks.total_mm

    @property
    def height_mm(self) -> float:
        return self.height_chunks.total_mm


def build_panels(bin_cfg: BinDimensions, board: BoardOptions) -> OpenGridPanelSet:
    tile_size = board.tile_size_mm
    wall_thickness = bin_cfg.wall_thickness_mm or board.thickness_mm
    max_cells_per_tile = max(1, int(bin_cfg.max_tile_mm // tile_size))

    length_chunks = _axis_chunks(bin_cfg.length_mm, tile_size, bin_cfg.dimension_rounding, max_cells_per_tile)
    width_chunks = _axis_chunks(bin_cfg.width_mm, tile_size, bin_cfg.dimension_rounding, max_cells_per_tile)
    height_chunks = _axis_chunks(bin_cfg.height_mm, tile_size, bin_cfg.dimension_rounding, max_cells_per_tile)

    panels: List[Panel] = []
    panels.extend(
        _build_floor_panels(length_chunks.cells, width_chunks.cells, tile_size, wall_thickness, length_chunks.total_mm, width_chunks.total_mm)
    )
    panels.extend(
        _build_side_panels(
            length_chunks.cells,
            height_chunks.cells,
            tile_size,
            wall_thickness,
            length_chunks.total_mm,
            width_chunks.total_mm,
            height_chunks.total_mm,
        )
    )
    panels.extend(
        _build_end_panels(
            width_chunks.cells,
            height_chunks.cells,
            tile_size,
            wall_thickness,
            length_chunks.total_mm,
            width_chunks.total_mm,
            height_chunks.total_mm,
        )
    )

    return OpenGridPanelSet(
        panels=panels,
        length_chunks=length_chunks,
        width_chunks=width_chunks,
        height_chunks=height_chunks,
        tile_size_mm=tile_size,
        wall_thickness_mm=wall_thickness,
    )


def _axis_chunks(target_mm: float, tile_size: float, rounding: str, max_cells: int) -> AxisChunks:
    cells = _snap_to_cells(target_mm, tile_size, rounding)
    total_mm = cells * tile_size
    chunk_list = _split_into_chunks(cells, max_cells)
    return AxisChunks(cells=chunk_list, total_cells=cells, total_mm=total_mm)


def _snap_to_cells(value_mm: float, tile_size: float, rounding: str) -> int:
    ratio = value_mm / tile_size
    if rounding == "ceil":
        cells = math.ceil(ratio)
    elif rounding == "floor":
        cells = max(1, math.floor(ratio))
    else:
        cells = max(1, round(ratio))
    return max(1, cells)


def _split_into_chunks(total_cells: int, max_chunk: int) -> List[int]:
    if max_chunk <= 0:
        return [total_cells]
    chunk_count = max(1, math.ceil(total_cells / max_chunk))
    base = total_cells // chunk_count
    remainder = total_cells % chunk_count
    parts: List[int] = []
    for idx in range(chunk_count):
        size = base + (1 if idx < remainder else 0)
        size = max(1, size)
        parts.append(size)
    return parts


def _edges_from_chunks(chunks: Sequence[int], total_mm: float, tile_size: float, *, centered: bool = True) -> List[float]:
    edges = [-total_mm / 2.0] if centered else [0.0]
    current = edges[0]
    for cells in chunks:
        current += cells * tile_size
        edges.append(current)
    return edges


def _build_floor_panels(
    length_chunks: Sequence[int],
    width_chunks: Sequence[int],
    tile_size: float,
    thickness: float,
    length_mm: float,
    width_mm: float,
) -> List[Panel]:
    panels: List[Panel] = []
    x_edges = _edges_from_chunks(length_chunks, length_mm, tile_size, centered=True)
    y_edges = _edges_from_chunks(width_chunks, width_mm, tile_size, centered=True)
    for ix, cells_x in enumerate(length_chunks):
        for iy, cells_y in enumerate(width_chunks):
            x_min, x_max = x_edges[ix], x_edges[ix + 1]
            y_min, y_max = y_edges[iy], y_edges[iy + 1]
            panel = Panel(
                panel_id=f"floor_{ix}_{iy}",
                kind=PanelKind.FLOOR,
                width=x_max - x_min,
                height=y_max - y_min,
                thickness=thickness,
                origin=Vec3((x_min + x_max) / 2.0, (y_min + y_max) / 2.0, thickness / 2.0),
                axes=PanelAxes(AxisDirection("x"), AxisDirection("y"), AxisDirection("z")),
                bounds=(x_min, x_max, y_min, y_max, 0.0, thickness),
                indices=(ix, iy, 0),
            )
            panels.append(panel)
    return panels


def _build_side_panels(
    length_chunks: Sequence[int],
    height_chunks: Sequence[int],
    tile_size: float,
    thickness: float,
    length_mm: float,
    width_mm: float,
    height_mm: float,
) -> List[Panel]:
    """Build panels for the ±Y walls."""
    panels: List[Panel] = []
    x_edges = _edges_from_chunks(length_chunks, length_mm, tile_size, centered=True)
    z_edges = _edges_from_chunks(height_chunks, height_mm, tile_size, centered=False)
    offset = thickness
    y_pos = width_mm / 2.0 + offset
    y_neg = -width_mm / 2.0 - offset
    for ix in range(len(length_chunks)):
        x_min, x_max = x_edges[ix], x_edges[ix + 1]
        for iz in range(len(height_chunks)):
            z_min, z_max = z_edges[iz], z_edges[iz + 1]
            # Positive Y wall
            z_min_shift = z_min + thickness
            z_max_shift = z_max + thickness
            panel = Panel(
                panel_id=f"wall_posY_{ix}_{iz}",
                kind=PanelKind.WALL_POS_Y,
                width=x_max - x_min,
                height=z_max_shift - z_min_shift,
                thickness=thickness,
                origin=Vec3((x_min + x_max) / 2.0, y_pos - thickness / 2.0, (z_min_shift + z_max_shift) / 2.0),
                axes=PanelAxes(AxisDirection("x"), AxisDirection("z"), AxisDirection("y")),
                bounds=(x_min, x_max, y_pos - thickness, y_pos, z_min_shift, z_max_shift),
                indices=(ix, 0, iz),
            )
            panels.append(panel)
            # Negative Y wall
            panel_neg = Panel(
                panel_id=f"wall_negY_{ix}_{iz}",
                kind=PanelKind.WALL_NEG_Y,
                width=x_max - x_min,
                height=z_max_shift - z_min_shift,
                thickness=thickness,
                origin=Vec3((x_min + x_max) / 2.0, y_neg + thickness / 2.0, (z_min_shift + z_max_shift) / 2.0),
                axes=PanelAxes(AxisDirection("x"), AxisDirection("z"), AxisDirection("y", sign=-1)),
                bounds=(x_min, x_max, y_neg, y_neg + thickness, z_min_shift, z_max_shift),
                indices=(ix, 0, iz),
            )
            panels.append(panel_neg)
    return panels


def _build_end_panels(
    width_chunks: Sequence[int],
    height_chunks: Sequence[int],
    tile_size: float,
    thickness: float,
    length_mm: float,
    width_mm: float,
    height_mm: float,
) -> List[Panel]:
    """Build panels for the ±X walls (the narrow ends)."""
    panels: List[Panel] = []
    y_edges = _edges_from_chunks(width_chunks, width_mm, tile_size, centered=True)
    z_edges = _edges_from_chunks(height_chunks, height_mm, tile_size, centered=False)
    offset = thickness
    x_pos = length_mm / 2.0 + offset
    x_neg = -length_mm / 2.0 - offset
    for iy in range(len(width_chunks)):
        y_min, y_max = y_edges[iy], y_edges[iy + 1]
        for iz in range(len(height_chunks)):
            z_min, z_max = z_edges[iz], z_edges[iz + 1]
            z_min_shift = z_min + thickness
            z_max_shift = z_max + thickness
            panel = Panel(
                panel_id=f"wall_posX_{iy}_{iz}",
                kind=PanelKind.WALL_POS_X,
                width=y_max - y_min,
                height=z_max_shift - z_min_shift,
                thickness=thickness,
                origin=Vec3(x_pos - thickness / 2.0, (y_min + y_max) / 2.0, (z_min_shift + z_max_shift) / 2.0),
                axes=PanelAxes(AxisDirection("y"), AxisDirection("z"), AxisDirection("x")),
                bounds=(x_pos - thickness, x_pos, y_min, y_max, z_min_shift, z_max_shift),
                indices=(0, iy, iz),
            )
            panels.append(panel)

            panel_neg = Panel(
                panel_id=f"wall_negX_{iy}_{iz}",
                kind=PanelKind.WALL_NEG_X,
                width=y_max - y_min,
                height=z_max_shift - z_min_shift,
                thickness=thickness,
                origin=Vec3(x_neg + thickness / 2.0, (y_min + y_max) / 2.0, (z_min_shift + z_max_shift) / 2.0),
                axes=PanelAxes(AxisDirection("y"), AxisDirection("z"), AxisDirection("x", sign=-1)),
                bounds=(x_neg, x_neg + thickness, y_min, y_max, z_min_shift, z_max_shift),
                indices=(0, iy, iz),
            )
            panels.append(panel_neg)
    return panels
