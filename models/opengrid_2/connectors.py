from __future__ import annotations

from dataclasses import dataclass

from .panels import OpenGridPanelSet


@dataclass
class ConnectorPlan:
    snap_count: int
    corner_count: int

    def as_dict(self) -> dict[str, int]:
        return {
            "snap_count": self.snap_count,
            "corner_count": self.corner_count,
        }


def plan_connectors(panel_set: OpenGridPanelSet, include_floor_edges: bool = True) -> ConnectorPlan:
    length_cells_total = panel_set.length_chunks.total_cells
    width_cells_total = panel_set.width_chunks.total_cells
    height_cells_total = panel_set.height_chunks.total_cells

    length_chunk_count = len(panel_set.length_chunks.cells)
    width_chunk_count = len(panel_set.width_chunks.cells)
    height_chunk_count = len(panel_set.height_chunks.cells)

    # Coplanar seams running vertically (between columns)
    vertical_seams_len = max(length_chunk_count - 1, 0)
    vertical_seams_width = max(width_chunk_count - 1, 0)
    snap_vertical = 2 * (vertical_seams_len + vertical_seams_width) * height_cells_total

    # Horizontal seams (between stacked tiles)
    horizontal_levels = max(height_chunk_count - 1, 0)
    snap_horizontal_len = 2 * horizontal_levels * length_cells_total
    snap_horizontal_width = 2 * horizontal_levels * width_cells_total

    # Floor seams between tiles
    snap_floor_len = max(length_chunk_count - 1, 0) * width_cells_total
    snap_floor_width = max(width_chunk_count - 1, 0) * length_cells_total
    snap_floor = snap_floor_len + snap_floor_width

    snap_total = snap_vertical + snap_horizontal_len + snap_horizontal_width + snap_floor

    corner_count = 0
    if include_floor_edges:
        # Right-angle connectors along the floor perimeter (floor to wall seams)
        corner_count = 2 * length_cells_total + 2 * width_cells_total

    return ConnectorPlan(snap_count=snap_total, corner_count=corner_count)
