from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from .panels import Panel, PanelAxes, AxisDirection, PanelKind, Vec3


@dataclass
class LayoutConfig:
    bed_size_mm: Tuple[float, float] = (200.0, 200.0)
    spacing_mm: float = 6.0


@dataclass
class PanelPlacement:
    panel: Panel
    origin: Vec3
    axes: PanelAxes
    sheet: str | None = None


@dataclass
class FlatSheet:
    name: str
    width: float
    height: float
    placements: List[PanelPlacement]


@dataclass
class LayoutPlan:
    assembled: List[PanelPlacement]
    flat_sheets: List[FlatSheet]


def build_layout(panels: Sequence[Panel], cfg: LayoutConfig) -> LayoutPlan:
    assembled = [PanelPlacement(panel=p, origin=p.origin, axes=p.axes) for p in panels]
    flat_sheets = _build_flat_sheets(panels, cfg)
    return LayoutPlan(assembled=assembled, flat_sheets=flat_sheets)


def _build_flat_sheets(panels: Sequence[Panel], cfg: LayoutConfig) -> List[FlatSheet]:
    width, height = cfg.bed_size_mm
    spacing = max(0.0, cfg.spacing_mm)
    ordered = sorted(panels, key=lambda p: (p.kind.value, -p.width * p.height))
    sheets: List[FlatSheet] = []
    current: List[PanelPlacement] = []
    sheet_idx = 1
    cursor_x = spacing
    cursor_y = spacing
    row_height = 0.0

    def new_sheet() -> None:
        nonlocal cursor_x, cursor_y, row_height, current, sheet_idx
        if current:
            sheets.append(FlatSheet(name=f"sheet{sheet_idx:02d}", width=width, height=height, placements=current))
            sheet_idx += 1
        current = []
        cursor_x = spacing
        cursor_y = spacing
        row_height = 0.0

    new_sheet()
    for panel in ordered:
        panel_w = panel.width
        panel_h = panel.height
        if cursor_x + panel_w + spacing > width:
            cursor_x = spacing
            cursor_y += row_height + spacing
            row_height = 0.0
        if cursor_y + panel_h + spacing > height and current:
            new_sheet()
        centre_x = cursor_x + panel_w / 2.0
        centre_y = cursor_y + panel_h / 2.0
        origin = Vec3(centre_x - width / 2.0, centre_y - height / 2.0, panel.thickness / 2.0)
        placement = PanelPlacement(
            panel=panel,
            origin=origin,
            axes=_flat_axes_for(panel.kind),
            sheet=f"sheet{sheet_idx:02d}",
        )
        current.append(placement)
        cursor_x += panel_w + spacing
        row_height = max(row_height, panel_h)
    if current:
        sheets.append(FlatSheet(name=f"sheet{sheet_idx:02d}", width=width, height=height, placements=current))
    return sheets


def _flat_axes_for(kind: PanelKind) -> PanelAxes:
    # All panels lie flat on the bed; u->X, v->Y, w->Z.
    return PanelAxes(AxisDirection("x"), AxisDirection("y"), AxisDirection("z"))
