from __future__ import annotations

import math
from dataclasses import fields
from pathlib import Path
from typing import Any, Iterable, Mapping

import anchorscad as ad
from anchorscad.renderer import render as render_shape

from ..engine import BuildContext, EngineResult
from ..export import ExportError, build_png_args, export_step_artifact, run_openscad
from ..preview import RectSpec, render_rect_preview

EPS = 1.0e-3


@ad.shape
@ad.datatree
class SolarBusAssembly(ad.CompositeShape):
    bus_length_mm: float = ad.dtfield(6000.0, "Overall bus length along X")
    bus_width_mm: float = ad.dtfield(2000.0, "Overall bus width along Y")
    roof_thickness_mm: float = ad.dtfield(20.0, "Roof slab thickness")
    margin_edge_mm: float = ad.dtfield(50.0, "Keep-out margin from roof edges")

    panel_count: int = ad.dtfield(2, "Number of PV panels")
    panel_length_mm: float = ad.dtfield(1200.0, "Panel length along X")
    panel_width_mm: float = ad.dtfield(540.0, "Panel width along Y")
    panel_height_mm: float = ad.dtfield(35.0, "Panel height")
    panel_gap_mm: float = ad.dtfield(40.0, "Gap between panels")
    panel_tilt_deg: float = ad.dtfield(0.0, "Reserved for future tilt support")

    mounting_show: bool = ad.dtfield(True, "Whether to render mounting rails")
    mounting_height_mm: float = ad.dtfield(40.0, "Rail height above roof")
    mounting_width_mm: float = ad.dtfield(20.0, "Rail width")

    battery_count: int = ad.dtfield(1, "Battery modules rendered below the roof")
    battery_length_mm: float = ad.dtfield(330.0, "Battery size along X")
    battery_width_mm: float = ad.dtfield(170.0, "Battery size along Y")
    battery_height_mm: float = ad.dtfield(220.0, "Battery size along Z")
    battery_spacing_mm: float = ad.dtfield(80.0, "Gap between battery modules")
    battery_offset_x_mm: float = ad.dtfield(0.0, "Offset along X from bus center")
    battery_clearance_mm: float = ad.dtfield(200.0, "Distance below the roof slab")

    cable_show: bool = ad.dtfield(False, "Render simplified cable trunk")
    cable_entry: str = ad.dtfield("rear_left", "Cable entry corner")
    cable_width_mm: float = ad.dtfield(15.0, "Cable trunk width")
    cable_height_mm: float = ad.dtfield(10.0, "Cable trunk height")

    def build(self) -> ad.Maker:
        maker = None

        def add(shape_maker: ad.Maker):
            nonlocal maker
            if maker is None:
                maker = shape_maker
            else:
                maker.add(shape_maker)

        def roof_z() -> float:
            return self.roof_thickness_mm / 2.0

        roof = (
            ad.Box((self.bus_length_mm, self.bus_width_mm, self.roof_thickness_mm + EPS))
            .solid("roof")
            .at("centre", post=ad.translate([0.0, 0.0, roof_z()]))
        )
        add(roof)

        panel_centers = self._panel_centers()
        panel_z = self.roof_thickness_mm + (self.mounting_height_mm if self.mounting_show else 0.0)
        panel_centre_z = panel_z + self.panel_height_mm / 2.0

        for idx, (px, py) in enumerate(panel_centers):
            panel = (
                ad.Box(
                    (
                        self.panel_length_mm,
                        self.panel_width_mm,
                        self.panel_height_mm + EPS,
                    )
                )
                .solid(f"panel_{idx}")
                .at("centre", post=ad.translate([px, py, panel_centre_z]))
            )
            add(panel)

        if self.mounting_show and panel_centers:
            rail_length = self.bus_length_mm - 2 * self.margin_edge_mm
            if rail_length <= 0:
                rail_length = max(self.panel_length_mm, self.bus_length_mm * 0.25)
            rail_z = self.roof_thickness_mm + self.mounting_height_mm / 2.0
            unique_rows = sorted({round(py, 6) for _, py in panel_centers})
            for row_idx, row_y in enumerate(unique_rows):
                rail = (
                    ad.Box((rail_length, self.mounting_width_mm, self.mounting_height_mm + EPS))
                    .solid(f"rail_row_{row_idx}")
                    .at(
                        "centre",
                        post=ad.translate([0.0, row_y, rail_z]),
                    )
                )
                add(rail)

        if self.battery_count > 0 and self.battery_height_mm > 0:
            battery_positions = self._battery_centers()
            z_bat = -self.battery_clearance_mm - self.battery_height_mm / 2.0
            for idx, (bx, by) in enumerate(battery_positions):
                battery = (
                    ad.Box(
                        (
                            self.battery_length_mm,
                            self.battery_width_mm,
                            self.battery_height_mm + EPS,
                        )
                    )
                    .solid(f"battery_{idx}")
                    .at("centre", post=ad.translate([bx, by, z_bat]))
                )
                add(battery)

        if self.cable_show and panel_centers:
            entry = self._entry_point()
            cable_len = self.bus_length_mm - 2 * self.margin_edge_mm
            cable_start_x = -self.bus_length_mm / 2.0 + self.margin_edge_mm + cable_len / 2.0
            cable_y = entry[1]
            cable_z = self.roof_thickness_mm + self.cable_height_mm / 2.0
            cable = (
                ad.Box((cable_len, self.cable_width_mm, self.cable_height_mm + EPS))
                .solid("cable_trunk")
                .at("centre", post=ad.translate([cable_start_x, cable_y, cable_z]))
            )
            add(cable)

        assert maker is not None, "SolarBusAssembly should have at least the roof"
        return maker

    def _panel_centers(self) -> list[tuple[float, float]]:
        if self.panel_count <= 0:
            return []
        usable_length = self.bus_length_mm - 2 * self.margin_edge_mm
        usable_width = self.bus_width_mm - 2 * self.margin_edge_mm
        if usable_length <= 0 or usable_width <= 0:
            raise ValueError("Margins exceed roof dimensions")

        cols = self._max_columns(usable_length)
        if cols == 0:
            cols = 1
        cols = min(self.panel_count, cols)

        while cols > 0:
            rows = math.ceil(self.panel_count / cols)
            total_width = rows * self.panel_width_mm + max(rows - 1, 0) * self.panel_gap_mm
            if total_width <= usable_width + EPS:
                break
            cols -= 1
        if cols == 0:
            raise ValueError("Panel grid cannot fit on the roof with current parameters")

        rows = math.ceil(self.panel_count / cols)
        total_length = cols * self.panel_length_mm + max(cols - 1, 0) * self.panel_gap_mm
        leftover_x = max(usable_length - total_length, 0.0)
        start_x = -self.bus_length_mm / 2.0 + self.margin_edge_mm + self.panel_length_mm / 2.0 + leftover_x / 2.0

        total_width = rows * self.panel_width_mm + max(rows - 1, 0) * self.panel_gap_mm
        leftover_y = max(usable_width - total_width, 0.0)
        start_y = -self.bus_width_mm / 2.0 + self.margin_edge_mm + self.panel_width_mm / 2.0 + leftover_y / 2.0

        centers = []
        for idx in range(self.panel_count):
            row = idx // cols
            col = idx % cols
            x = start_x + col * (self.panel_length_mm + self.panel_gap_mm)
            y = start_y + row * (self.panel_width_mm + self.panel_gap_mm)
            centers.append((x, y))
        return centers

    def _max_columns(self, usable_length: float) -> int:
        if self.panel_length_mm <= 0:
            return 0
        if usable_length < self.panel_length_mm:
            return 1
        return max(1, int(usable_length // (self.panel_length_mm + EPS)))

    def _battery_centers(self) -> list[tuple[float, float]]:
        centers = []
        if self.battery_count <= 0:
            return centers
        usable_width = self.bus_width_mm - 2 * self.margin_edge_mm
        stride = self.battery_width_mm + self.battery_spacing_mm
        total_width = self.battery_count * self.battery_width_mm + max(self.battery_count - 1, 0) * self.battery_spacing_mm
        offset_y = max((usable_width - total_width) / 2.0, 0.0)
        start_y = -self.bus_width_mm / 2.0 + self.margin_edge_mm + self.battery_width_mm / 2.0 + offset_y
        for idx in range(self.battery_count):
            y = start_y + idx * stride
            centers.append((self.battery_offset_x_mm, y))
        return centers

    def _entry_point(self) -> tuple[float, float]:
        x = -self.bus_length_mm / 2.0 + self.margin_edge_mm
        y = self.bus_width_mm / 2.0 - self.margin_edge_mm
        mapping = {
            "rear_left": (-self.bus_length_mm / 2.0 + self.margin_edge_mm, self.bus_width_mm / 2.0 - self.margin_edge_mm),
            "rear_right": (-self.bus_length_mm / 2.0 + self.margin_edge_mm, -self.bus_width_mm / 2.0 + self.margin_edge_mm),
            "front_left": (self.bus_length_mm / 2.0 - self.margin_edge_mm, self.bus_width_mm / 2.0 - self.margin_edge_mm),
            "front_right": (self.bus_length_mm / 2.0 - self.margin_edge_mm, -self.bus_width_mm / 2.0 + self.margin_edge_mm),
        }
        return mapping.get(self.cable_entry, (x, y))


def _allowed_fields() -> set[str]:
    return {f.name for f in fields(SolarBusAssembly)}


def _flatten(seq: Iterable[Any]) -> list[Any]:
    return list(seq)


ALLOWED_PARAMS = _allowed_fields()


def _shape_kwargs(context: BuildContext) -> dict[str, Any]:
    cfg = context.raw_config
    bus_cfg = cfg.get("bus", {})
    panels_cfg = cfg.get("panels", {})
    battery_cfg = cfg.get("battery", {})
    mounting_cfg = cfg.get("mounting", {})
    wiring_cfg = cfg.get("wiring", {})

    defaults = {
        "bus_length_mm": bus_cfg.get("length_mm"),
        "bus_width_mm": bus_cfg.get("width_mm"),
        "margin_edge_mm": bus_cfg.get("margin_edge_mm"),
        "panel_count": panels_cfg.get("count"),
        "panel_length_mm": _flatten(panels_cfg.get("size_mm", [1200, 540, 35]))[0],
        "panel_width_mm": _flatten(panels_cfg.get("size_mm", [1200, 540, 35]))[1],
        "panel_height_mm": _flatten(panels_cfg.get("size_mm", [1200, 540, 35]))[2],
        "panel_tilt_deg": panels_cfg.get("tilt_deg"),
        "panel_gap_mm": panels_cfg.get("gap_mm"),
        "mounting_show": mounting_cfg.get("show_mounting"),
        "mounting_height_mm": mounting_cfg.get("rail_height_mm"),
        "battery_count": battery_cfg.get("count"),
        "battery_length_mm": _flatten(battery_cfg.get("size_mm", [330, 170, 220]))[0],
        "battery_width_mm": _flatten(battery_cfg.get("size_mm", [330, 170, 220]))[1],
        "battery_height_mm": _flatten(battery_cfg.get("size_mm", [330, 170, 220]))[2],
        "battery_offset_x_mm": (battery_cfg.get("custom_pos_mm") or [0, 0, 0])[0],
        "battery_spacing_mm": battery_cfg.get("spacing_mm"),
        "battery_clearance_mm": battery_cfg.get("floor_drop_mm"),
        "cable_show": wiring_cfg.get("show_cables"),
        "cable_entry": wiring_cfg.get("entry_point"),
    }

    params = dict(defaults)
    model_params: Mapping[str, Any] = context.model_params if isinstance(context.model_params, Mapping) else {}
    params.update({k: v for k, v in model_params.items() if k in ALLOWED_PARAMS})
    cleaned = {k: v for k, v in params.items() if v is not None}
    return cleaned


def _solar_preview_rects_from_shape(shape: SolarBusAssembly) -> list[RectSpec]:
    rects: list[RectSpec] = [
        RectSpec(
            -shape.bus_length_mm / 2.0,
            -shape.bus_width_mm / 2.0,
            shape.bus_length_mm / 2.0,
            shape.bus_width_mm / 2.0,
            (210, 210, 215),
        )
    ]

    panel_centers = shape._panel_centers()
    for px, py in panel_centers:
        rects.append(
            RectSpec(
                px - shape.panel_length_mm / 2.0,
                py - shape.panel_width_mm / 2.0,
                px + shape.panel_length_mm / 2.0,
                py + shape.panel_width_mm / 2.0,
                (70, 125, 205),
            )
        )

    if shape.mounting_show and panel_centers:
        rail_length = shape.bus_length_mm - 2 * shape.margin_edge_mm
        if rail_length <= 0:
            rail_length = max(shape.panel_length_mm, shape.bus_length_mm * 0.25)
        unique_rows = sorted({round(py, 6) for _, py in panel_centers})
        for row_y in unique_rows:
            rects.append(
                RectSpec(
                    -rail_length / 2.0,
                    row_y - shape.mounting_width_mm / 2.0,
                    rail_length / 2.0,
                    row_y + shape.mounting_width_mm / 2.0,
                    (80, 80, 80),
                )
            )

    if shape.battery_count > 0 and shape.battery_height_mm > 0:
        for bx, by in shape._battery_centers():
            rects.append(
                RectSpec(
                    bx - shape.battery_length_mm / 2.0,
                    by - shape.battery_width_mm / 2.0,
                    bx + shape.battery_length_mm / 2.0,
                    by + shape.battery_width_mm / 2.0,
                    (215, 150, 90),
                )
            )

    if shape.cable_show and panel_centers:
        entry = shape._entry_point()
        cable_len = shape.bus_length_mm - 2 * shape.margin_edge_mm
        cable_start_x = -shape.bus_length_mm / 2.0 + shape.margin_edge_mm + cable_len / 2.0
        rects.append(
            RectSpec(
                cable_start_x - cable_len / 2.0,
                entry[1] - shape.cable_width_mm / 2.0,
                cable_start_x + cable_len / 2.0,
                entry[1] + shape.cable_width_mm / 2.0,
                (225, 100, 100),
            )
        )

    return rects


def build(context: BuildContext) -> EngineResult:
    shape_kwargs = _shape_kwargs(context)
    shape = SolarBusAssembly(**shape_kwargs)
    render_result = render_shape(shape)

    png_enabled, png_args = build_png_args(context.export.get("png"))
    scad_required = context.export.get("scad", True)
    scad_path = context.out_dir / f"{context.basename}.scad"
    scad_written = False
    if scad_required or context.export.get("stl") or png_enabled:
        with scad_path.open("w", encoding="utf-8") as handle:
            render_result.rendered_shape.dump(handle)
        scad_written = True

    stl_paths = []
    step_paths = []
    if context.export.get("stl"):
        stl_path = context.out_dir / f"{context.basename}.stl"
        run_openscad(scad_path, stl_path, context.openscad_bin)
        stl_paths.append(stl_path)

    logs: list[str] = []
    if scad_written:
        logs.append(f"SCAD written to {scad_path}")
    if stl_paths:
        logs.append(f"STL written to {stl_paths[-1]}")
    if context.export.get("step"):
        step_path = context.out_dir / f"{context.basename}.step"
        step_result = export_step_artifact(
            scad_path,
            step_path,
            export_cfg=context.export,
            openscad_bin=context.openscad_bin,
            freecad_bin=context.freecad_bin,
            stl_path=stl_paths[-1] if stl_paths else None,
        )
        step_paths.append(step_result.step_path)
        if step_result.dedup_hit and step_result.cache_path:
            logs.append(
                f"STEP linked to cached geometry {step_result.cache_path} -> {step_result.step_path}"
            )
        else:
            logs.append(f"STEP written to {step_result.step_path}")

    png_paths = []
    if png_enabled:
        png_path = context.out_dir / f"{context.basename}.png"
        try:
            run_openscad(scad_path, png_path, context.openscad_bin, png_args)
        except ExportError as exc:
            preview_rects = _solar_preview_rects_from_shape(shape)
            render_rect_preview(preview_rects, png_path)
            logs.append(f"PNG fallback rendered to {png_path} ({exc})")
        else:
            logs.append(f"PNG written to {png_path}")
        png_paths.append(png_path)

    meta = {
        "panel_count": shape.panel_count,
        "battery_count": shape.battery_count,
        "bus_length_mm": shape.bus_length_mm,
    }
    return EngineResult(
        scad_path=scad_path if scad_written else None,
        stl_paths=stl_paths,
        step_paths=step_paths,
        png_paths=png_paths,
        logs=logs,
        metadata=meta,
    )
