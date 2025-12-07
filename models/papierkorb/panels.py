from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

import anchorscad as ad

from .params import PapierkorbParams

EPS = 1.0e-3
PANEL_COLOUR_NAMES = [
    "gold",
    "lightskyblue",
    "lightcoral",
    "mediumaquamarine",
    "plum",
    "khaki",
    "tomato",
    "lightseagreen",
    "dodgerblue",
    "orchid",
    "palegreen",
    "sandybrown",
]


@dataclass(frozen=True)
class Vec3:
    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)


class PanelKind(Enum):
    FLOOR = "floor"
    WALL_POS_Y = "wall_posY"
    WALL_NEG_Y = "wall_negY"
    WALL_POS_X = "wall_posX"
    WALL_NEG_X = "wall_negX"
    RIM_POS_Y = "rim_posY"
    RIM_NEG_Y = "rim_negY"
    RIM_POS_X = "rim_posX"
    RIM_NEG_X = "rim_negX"


PANEL_KIND_ORDER = {kind: idx for idx, kind in enumerate(PanelKind)}


@dataclass(frozen=True)
class AxisDirection:
    axis: str  # 'x', 'y', 'z'
    sign: int = 1

    def vector(self) -> Vec3:
        if self.axis == "x":
            return Vec3(self.sign, 0.0, 0.0)
        if self.axis == "y":
            return Vec3(0.0, self.sign, 0.0)
        if self.axis == "z":
            return Vec3(0.0, 0.0, self.sign)
        raise ValueError(f"Unsupported axis {self.axis}")


@dataclass(frozen=True)
class PanelAxes:
    u: AxisDirection
    v: AxisDirection
    w: AxisDirection

    def axis_for(self, local_axis: str) -> AxisDirection:
        return {"u": self.u, "v": self.v, "w": self.w}[local_axis]


@dataclass
class PanelFeature:
    label: str
    feature_type: str  # 'box' or 'cylinder'
    role: str  # 'solid' or 'hole'
    size_u: float = 0.0
    size_v: float = 0.0
    size_w: float = 0.0
    radius: float = 0.0
    height: float = 0.0
    axis: str = "w"
    offset_u: float = 0.0
    offset_v: float = 0.0
    offset_w: float = 0.0

    @classmethod
    def box(
        cls,
        label: str,
        role: str,
        size_u: float,
        size_v: float,
        size_w: float,
        *,
        offset_u: float = 0.0,
        offset_v: float = 0.0,
        offset_w: float = 0.0,
    ) -> "PanelFeature":
        return cls(
            label=label,
            feature_type="box",
            role=role,
            size_u=size_u,
            size_v=size_v,
            size_w=size_w,
            offset_u=offset_u,
            offset_v=offset_v,
            offset_w=offset_w,
        )

    @classmethod
    def cylinder(
        cls,
        label: str,
        role: str,
        radius: float,
        height: float,
        *,
        axis: str = "w",
        offset_u: float = 0.0,
        offset_v: float = 0.0,
        offset_w: float = 0.0,
    ) -> "PanelFeature":
        return cls(
            label=label,
            feature_type="cylinder",
            role=role,
            radius=radius,
            height=height,
            axis=axis,
            offset_u=offset_u,
            offset_v=offset_v,
            offset_w=offset_w,
        )


@dataclass
class Panel:
    panel_id: str
    kind: PanelKind
    width: float
    height: float
    thickness: float
    origin: Vec3
    axes: PanelAxes
    bounds: Tuple[float, float, float, float, float, float]
    indices: Tuple[int, int, int]
    features: List[PanelFeature] = field(default_factory=list)
    colour: ad.Colour | None = None

    def add_feature(self, feature: PanelFeature) -> None:
        self.features.append(feature)


@dataclass
class PanelGrid:
    Nx: int
    Ny: int
    Nz: int
    tile_x: float
    tile_y: float
    tile_z: float


@dataclass
class PanelBuildResult:
    params: PapierkorbParams
    grid: PanelGrid
    panels: List[Panel]


class PanelCatalog:
    def __init__(self) -> None:
        self._registry: Dict[Tuple[PanelKind, Tuple[int, int, int]], Panel] = {}

    def register(self, panel: Panel) -> None:
        self._registry[(panel.kind, panel.indices)] = panel

    def get(self, kind: PanelKind, idx: Tuple[int, int, int]) -> Panel:
        return self._registry[(kind, idx)]

    def find(self, kind: PanelKind, predicate) -> Iterable[Panel]:
        for (panel_kind, _), panel in self._registry.items():
            if panel_kind is kind and predicate(panel):
                yield panel


def build_panels(params: PapierkorbParams) -> PanelBuildResult:
    Nx, Ny, Nz = params.tile_counts()
    tile_x = params.length_mm / Nx
    tile_y = params.width_mm / Ny
    tile_z = params.height_mm / Nz
    grid = PanelGrid(Nx=Nx, Ny=Ny, Nz=Nz, tile_x=tile_x, tile_y=tile_y, tile_z=tile_z)

    builder = _PanelBuilder(params, grid)
    builder.build_floor_panels()
    builder.build_wall_panels()
    builder.build_rim_panels()
    builder.apply_length_flanges()
    builder.attach_honeycomb()
    builder.attach_opengrid()
    return PanelBuildResult(params=params, grid=grid, panels=builder.panels)


class _PanelBuilder:
    def __init__(self, params: PapierkorbParams, grid: PanelGrid) -> None:
        self.params = params
        self.grid = grid
        self.panels: List[Panel] = []
        self.catalog = PanelCatalog()
        self._colour_palette = [ad.Colour(name) for name in PANEL_COLOUR_NAMES]

    def build_floor_panels(self) -> None:
        t = self.params.wall_mm
        for ix in range(self.grid.Nx):
            for iy in range(self.grid.Ny):
                x_min, x_max, y_min, y_max, z_min, _ = self._tile_bounds(ix, iy, 0)
                width = x_max - x_min
                height = y_max - y_min
                origin = Vec3((x_min + x_max) / 2.0, (y_min + y_max) / 2.0, t / 2.0)
                bounds = (x_min, x_max, y_min, y_max, 0.0, t)
                panel = Panel(
                    panel_id=f"bottom_{ix}_{iy}",
                    kind=PanelKind.FLOOR,
                    width=width,
                    height=height,
                    thickness=t,
                    origin=origin,
                    axes=PanelAxes(AxisDirection("x"), AxisDirection("y"), AxisDirection("z")),
                    bounds=bounds,
                    indices=(ix, iy, 0),
                )
                panel.add_feature(
                    PanelFeature.box(
                        label=panel.panel_id,
                        role="solid",
                        size_u=width,
                        size_v=height,
                        size_w=t + EPS,
                    )
                )
                self._register_panel(panel)

    def build_wall_panels(self) -> None:
        t = self.params.wall_mm
        for ix in range(self.grid.Nx):
            for iz in range(self.grid.Nz):
                x_min, x_max, _, _, z_min, z_max = self._tile_bounds(ix, 0, iz)
                width = x_max - x_min
                height = z_max - z_min
                origin_y = self.params.width_mm / 2.0 - t / 2.0
                origin = Vec3((x_min + x_max) / 2.0, origin_y, (z_min + z_max) / 2.0)
                bounds = (x_min, x_max, self.params.width_mm / 2.0 - t, self.params.width_mm / 2.0, z_min, z_max)
                panel = Panel(
                    panel_id=f"side_posY_{ix}_{iz}",
                    kind=PanelKind.WALL_POS_Y,
                    width=width,
                    height=height,
                    thickness=t,
                    origin=origin,
                    axes=PanelAxes(AxisDirection("x"), AxisDirection("z"), AxisDirection("y")),
                    bounds=bounds,
                    indices=(ix, 0, iz),
                )
                panel.add_feature(
                    PanelFeature.box(
                        label=panel.panel_id,
                        role="solid",
                        size_u=width,
                        size_v=height,
                        size_w=t + EPS,
                    )
                )
                self._register_panel(panel)

                origin_neg_y = -self.params.width_mm / 2.0 + t / 2.0
                bounds_neg = (x_min, x_max, -self.params.width_mm / 2.0, -self.params.width_mm / 2.0 + t, z_min, z_max)
                panel_neg = Panel(
                    panel_id=f"side_negY_{ix}_{iz}",
                    kind=PanelKind.WALL_NEG_Y,
                    width=width,
                    height=height,
                    thickness=t,
                    origin=Vec3((x_min + x_max) / 2.0, origin_neg_y, (z_min + z_max) / 2.0),
                    axes=PanelAxes(AxisDirection("x"), AxisDirection("z"), AxisDirection("y", sign=-1)),
                    bounds=bounds_neg,
                    indices=(ix, 0, iz),
                )
                panel_neg.add_feature(
                    PanelFeature.box(
                        label=panel_neg.panel_id,
                        role="solid",
                        size_u=width,
                        size_v=height,
                        size_w=t + EPS,
                    )
                )
                self._register_panel(panel_neg)

        for iy in range(self.grid.Ny):
            for iz in range(self.grid.Nz):
                _, _, y_min, y_max, z_min, z_max = self._tile_bounds(0, iy, iz)
                width = y_max - y_min
                height = z_max - z_min
                origin_x = self.params.length_mm / 2.0 - t / 2.0
                origin = Vec3(origin_x, (y_min + y_max) / 2.0, (z_min + z_max) / 2.0)
                bounds = (self.params.length_mm / 2.0 - t, self.params.length_mm / 2.0, y_min, y_max, z_min, z_max)
                panel = Panel(
                    panel_id=f"side_posX_{iy}_{iz}",
                    kind=PanelKind.WALL_POS_X,
                    width=width,
                    height=height,
                    thickness=t,
                    origin=origin,
                    axes=PanelAxes(AxisDirection("y"), AxisDirection("z"), AxisDirection("x")),
                    bounds=bounds,
                    indices=(0, iy, iz),
                )
                panel.add_feature(
                    PanelFeature.box(
                        label=panel.panel_id,
                        role="solid",
                        size_u=width,
                        size_v=height,
                        size_w=t + EPS,
                    )
                )
                self._register_panel(panel)

                origin_neg_x = -self.params.length_mm / 2.0 + t / 2.0
                bounds_neg = (-self.params.length_mm / 2.0, -self.params.length_mm / 2.0 + t, y_min, y_max, z_min, z_max)
                panel_neg = Panel(
                    panel_id=f"side_negX_{iy}_{iz}",
                    kind=PanelKind.WALL_NEG_X,
                    width=width,
                    height=height,
                    thickness=t,
                    origin=Vec3(origin_neg_x, (y_min + y_max) / 2.0, (z_min + z_max) / 2.0),
                    axes=PanelAxes(AxisDirection("y"), AxisDirection("z"), AxisDirection("x", sign=-1)),
                    bounds=bounds_neg,
                    indices=(0, iy, iz),
                )
                panel_neg.add_feature(
                    PanelFeature.box(
                        label=panel_neg.panel_id,
                        role="solid",
                        size_u=width,
                        size_v=height,
                        size_w=t + EPS,
                    )
                )
                self._register_panel(panel_neg)

    def build_rim_panels(self) -> None:
        if not self.params.enable_rim:
            return
        rim_h = max(0.1, self.params.rim_height_mm)
        rim_w = max(0.1, self.params.rim_width_mm)
        H = self.params.height_mm
        z0 = H - rim_h / 2.0

        panels = [
            (
                PanelKind.RIM_POS_Y,
                f"rim_posY",
                Vec3(0.0, self.params.width_mm / 2.0 - rim_w / 2.0, z0),
                self.params.length_mm,
                rim_w,
                PanelAxes(AxisDirection("x"), AxisDirection("y"), AxisDirection("z")),
            ),
            (
                PanelKind.RIM_NEG_Y,
                f"rim_negY",
                Vec3(0.0, -self.params.width_mm / 2.0 + rim_w / 2.0, z0),
                self.params.length_mm,
                rim_w,
                PanelAxes(AxisDirection("x"), AxisDirection("y"), AxisDirection("z")),
            ),
            (
                PanelKind.RIM_POS_X,
                f"rim_posX",
                Vec3(self.params.length_mm / 2.0 - rim_w / 2.0, 0.0, z0),
                self.params.width_mm,
                rim_w,
                PanelAxes(AxisDirection("y"), AxisDirection("x"), AxisDirection("z")),
            ),
            (
                PanelKind.RIM_NEG_X,
                f"rim_negX",
                Vec3(-self.params.length_mm / 2.0 + rim_w / 2.0, 0.0, z0),
                self.params.width_mm,
                rim_w,
                PanelAxes(AxisDirection("y"), AxisDirection("x"), AxisDirection("z")),
            ),
        ]
        for kind, name, origin, width, height, axes in panels:
            panel = Panel(
                panel_id=name,
                kind=kind,
                width=width,
                height=height,
                thickness=rim_h,
                origin=origin,
                axes=axes,
                bounds=(0.0, 0.0, 0.0, 0.0, H - rim_h, H),
                indices=(0, 0, 0),
            )
            panel.add_feature(
                PanelFeature.box(
                    label=name,
                    role="solid",
                    size_u=width,
                    size_v=height,
                    size_w=rim_h + EPS,
                )
            )
            self._register_panel(panel)

    def attach_honeycomb(self) -> None:
        if not self.params.enable_honeycomb:
            return
        centers = list(self._honeycomb_centers())
        if not centers:
            return
        hole_height = self.params.wall_mm + EPS
        for sign, kind in ((1, PanelKind.WALL_POS_Y), (-1, PanelKind.WALL_NEG_Y)):
            for (cx, cz) in centers:
                panel = self._panel_for_wall(kind, cx, cz)
                if panel is None:
                    continue
                local_u, local_v, _ = self._global_to_local(panel, Vec3(cx, panel.origin.y, cz))
                panel.add_feature(
                    PanelFeature.cylinder(
                        label=f"honeycomb_{'pos' if sign > 0 else 'neg'}_{panel.panel_id}_{len(panel.features)}",
                        role="hole",
                        radius=self.params.honeycomb_radius_mm,
                        height=hole_height,
                        offset_u=local_u,
                        offset_v=local_v,
                        offset_w=0.0,
                    )
                )


    def attach_opengrid(self) -> None:
        if not self.params.enable_opengrid:
            return
        targets = {
            PanelKind.FLOOR,
            PanelKind.WALL_POS_Y,
            PanelKind.WALL_NEG_Y,
            PanelKind.WALL_POS_X,
            PanelKind.WALL_NEG_X,
        }
        for panel in self.panels:
            if panel.kind not in targets:
                continue
            self._apply_opengrid(panel)


    def _apply_opengrid(self, panel: Panel) -> None:
        cell = max(EPS, self.params.opengrid_cell_mm)
        bar = max(EPS, self.params.opengrid_bar_mm)
        margin = max(0.0, self.params.opengrid_margin_mm)
        usable_u = panel.width - 2.0 * margin
        usable_v = panel.height - 2.0 * margin
        if usable_u <= cell or usable_v <= cell:
            return
        pitch = cell + bar
        if pitch <= EPS:
            return
        count_u = max(1, int(math.floor((usable_u + bar) / pitch)))
        count_v = max(1, int(math.floor((usable_v + bar) / pitch)))
        coverage_u = count_u * cell + (count_u - 1) * bar
        coverage_v = count_v * cell + (count_v - 1) * bar
        pad_u = max(0.0, (usable_u - coverage_u) / 2.0)
        pad_v = max(0.0, (usable_v - coverage_v) / 2.0)
        u0 = -panel.width / 2.0 + margin + pad_u + cell / 2.0
        v0 = -panel.height / 2.0 + margin + pad_v + cell / 2.0
        depth = panel.thickness + EPS
        for iu in range(count_u):
            for iv in range(count_v):
                offset_u = u0 + iu * pitch
                offset_v = v0 + iv * pitch
                feature = PanelFeature.box(
                    label=f"opengrid_{panel.panel_id}_{iu}_{iv}",
                    role="hole",
                    size_u=cell,
                    size_v=cell,
                    size_w=depth,
                    offset_u=offset_u,
                    offset_v=offset_v,
                    offset_w=0.0,
                )
                panel.add_feature(feature)


    def apply_length_flanges(self) -> None:
        depth = max(0.0, self.params.flange_depth_mm)
        if depth <= EPS:
            return
        for panel in self.panels:
            if panel.kind in (PanelKind.WALL_POS_X, PanelKind.WALL_NEG_X):
                self._add_length_flanges(panel, depth)


    def _add_length_flanges(self, panel: Panel, depth: float) -> None:
        flange_thickness = min(self.params.wall_mm, panel.width)
        if flange_thickness <= 0.0:
            return
        half_u = panel.width / 2.0
        offsets = [half_u - flange_thickness / 2.0, -half_u + flange_thickness / 2.0]
        if panel.kind == PanelKind.WALL_POS_X:
            direction = -1.0  # bend towards negative X (into the bin)
        elif panel.kind == PanelKind.WALL_NEG_X:
            direction = -1.0  # bend towards positive X (into the bin)
        else:
            direction = -panel.axes.w.sign
        offset_w = direction * (panel.thickness / 2.0 + depth / 2.0)
        for idx, offset_u in enumerate(offsets):
            feature = PanelFeature.box(
                label=f"flange_{panel.panel_id}_{idx}",
                role="solid",
                size_u=flange_thickness,
                size_v=panel.height,
                size_w=depth,
                offset_u=offset_u,
                offset_v=0.0,
                offset_w=offset_w,
            )
            panel.add_feature(feature)

    def _register_panel(self, panel: Panel) -> None:
        self._assign_colour(panel)
        self.panels.append(panel)
        self.catalog.register(panel)

    def _assign_colour(self, panel: Panel) -> None:
        if not self._colour_palette:
            return
        kind_idx = PANEL_KIND_ORDER.get(panel.kind, 0)
        ix, iy, iz = panel.indices
        colour_idx = (1 + kind_idx * 17 + ix * 13 + iy * 7 + iz * 5) % len(self._colour_palette)
        panel.colour = self._colour_palette[colour_idx]

    def _tile_bounds(self, ix: int, iy: int, iz: int) -> Tuple[float, float, float, float, float, float]:
        x0 = -self.params.length_mm / 2.0
        y0 = -self.params.width_mm / 2.0
        z0 = 0.0
        x_min = x0 + ix * self.grid.tile_x
        x_max = x0 + (ix + 1) * self.grid.tile_x
        y_min = y0 + iy * self.grid.tile_y
        y_max = y0 + (iy + 1) * self.grid.tile_y
        z_min = z0 + iz * self.grid.tile_z
        z_max = z0 + (iz + 1) * self.grid.tile_z
        return x_min, x_max, y_min, y_max, z_min, z_max

    def _honeycomb_centers(self) -> Iterable[Tuple[float, float]]:
        pitch = max(self.params.honeycomb_pitch_mm, self.params.honeycomb_radius_mm * 2.0 + 1.0)
        margin = max(0.0, self.params.honeycomb_margin_mm)
        x_min = -self.params.length_mm / 2.0 + margin
        x_max = self.params.length_mm / 2.0 - margin
        z_min = margin
        z_max = self.params.height_mm - margin
        if x_min >= x_max or z_min >= z_max:
            return []
        centers = []
        row_height = pitch * 0.86602540378
        row = 0
        z = z_min
        while z <= z_max:
            x = x_min + ((row % 2) * (pitch / 2.0))
            while x <= x_max:
                centers.append((x, z))
                x += pitch
            row += 1
            z += row_height
        return centers

    def _panel_for_wall(self, kind: PanelKind, x: float, z: float) -> Optional[Panel]:
        for panel in self.panels:
            if panel.kind is not kind:
                continue
            x_min, x_max, _, _, z_min, z_max = panel.bounds
            if x_min - EPS <= x <= x_max + EPS and z_min - EPS <= z <= z_max + EPS:
                return panel
        return None

    def _global_to_local(self, panel: Panel, point: Vec3) -> Tuple[float, float, float]:
        delta = point - panel.origin
        def project(axis_dir: AxisDirection) -> float:
            vec = axis_dir.vector()
            return vec.x * delta.x + vec.y * delta.y + vec.z * delta.z
        return project(panel.axes.u), project(panel.axes.v), project(panel.axes.w)
