from __future__ import annotations

import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

import anchorscad as ad
from anchorscad.renderer import render as render_shape

from ...engine import BuildContext, EngineResult
from ...export import (
    ExportError,
    StepAssemblyPart,
    StepExportTask,
    assemble_step_from_parts,
    build_png_args,
    export_step_artifacts_parallel,
    run_openscad,
)
from ...preview import RectPrismSpec, render_isometric_preview
from . import layout as layout_builder
from . import panels as panel_builder
from .panels import Vec3
from . import render as panel_render
from . import scad_writer
from . import shell as shell_builder
from .params import PapierkorbParams


@dataclass
class LayoutArtifact:
    label: str
    basename: str
    placements: Iterable[layout_builder.PanelPlacement]
    preview_prisms: List[RectPrismSpec]
    maker: ad.Maker | None = None


@dataclass
class AssemblyPlan:
    placements: List[layout_builder.PanelPlacement]
    step_path: Path
    record: Dict[str, Any]
    scad_path: Path


PARAM_FIELDS = {f.name for f in fields(PapierkorbParams)}
DEBUG_LAYOUT_MODE = "debug_assembled_with_panels"
ROOT_DIR = Path(__file__).resolve().parents[4]
JL_SCAD_DIR = ROOT_DIR / "third_party" / "jl_scad"


def build(context: BuildContext) -> EngineResult:
    params = PapierkorbParams.from_mapping(_filter_params(context.model_params))
    layout_cfg = _extract_layout_cfg(context)
    assembly_mode = str(context.export.get("step_assembly", "panel") or "panel").lower()
    panel_set = None
    plan = None
    if params.simple_shell:
        shell_maker = shell_builder.build_simple_shell(params)
        artifacts = [
            LayoutArtifact(
                label="assembled",
                basename=context.basename,
                placements=[],
                preview_prisms=_assembled_preview_prisms(params),
                maker=shell_maker,
            )
        ]
        sheet_count = 0
    else:
        panel_set = panel_builder.build_panels(params)
        plan = layout_builder.build_layout(panel_set.panels, layout_cfg)
        artifacts = _build_artifacts(plan, context, layout_cfg, params)

        sheet_count = len(plan.flat_sheets)

    if not artifacts:
        raise ValueError("no layout artifacts produced; check layout.mode configuration")

    png_enabled, png_args = build_png_args(context.export.get("png"))
    panel_assembly_enabled = (
        assembly_mode == "panel"
        and panel_set is not None
        and not params.simple_shell
    )
    scad_primary: Path | None = None
    stl_paths: List[Path] = []
    step_paths: List[Path] = []
    png_paths: List[Path] = []
    step_tasks: List[StepExportTask] = []
    panel_step_sources: Dict[str, Path] = {}
    assembly_plan: AssemblyPlan | None = None
    logs: List[str] = []
    artifact_records: List[Dict[str, Any]] = []
    artifact_record_map: Dict[str, Dict[str, Any]] = {}

    if panel_assembly_enabled and context.export.get("step") and panel_set is not None:
        jl_include_root = os.path.relpath(JL_SCAD_DIR, context.out_dir)
        seen_panels: set[str] = set()
        for panel in panel_set.panels:
            if panel.panel_id in seen_panels:
                continue
            seen_panels.add(panel.panel_id)
            panel_scad_path = context.out_dir / f"{panel.panel_id}_panel.scad"
            panel_scad_text = scad_writer.build_scad_for_panel(
                params=params,
                panel=panel,
                jl_scad_path=jl_include_root,
            )
            panel_scad_path.write_text(panel_scad_text, encoding="utf-8")
            panel_step_path = panel_scad_path.with_suffix(".step")
            step_tasks.append(
                StepExportTask(
                    scad_path=panel_scad_path,
                    step_path=panel_step_path,
                    export_cfg=context.export,
                    openscad_bin=context.openscad_bin,
                    freecad_bin=context.freecad_bin,
                    metadata={"panel_step": True, "panel_id": panel.panel_id},
                )
            )

    for idx, artifact in enumerate(artifacts):
        placements = list(artifact.placements)
        scad_path = context.out_dir / f"{artifact.basename}.scad"
        if artifact.maker is not None:
            render_result = render_shape(artifact.maker)
            with scad_path.open("w", encoding="utf-8") as handle:
                render_result.rendered_shape.dump(handle)
        else:
            if panel_set is None:
                raise ValueError("panel data unavailable for jl_scad artifact generation")
            jl_scad_include = os.path.relpath(JL_SCAD_DIR, scad_path.parent)
            scad_text = scad_writer.build_scad_for_artifact(
                params=params,
                panel_result=panel_set,
                artifact_label=artifact.label,
                placements=placements,
                jl_scad_path=jl_scad_include.replace("\\", "/"),
            )
            scad_path.write_text(scad_text, encoding="utf-8")
        if scad_primary is None:
            scad_primary = scad_path
        logs.append(f"SCAD written to {scad_path}")

        artifact_stl: Path | None = None
        artifact_png: Path | None = None

        if context.export.get("stl"):
            stl_path = context.out_dir / f"{artifact.basename}.stl"
            run_openscad(scad_path, stl_path, context.openscad_bin)
            stl_paths.append(stl_path)
            logs.append(f"STL written to {stl_path}")
            artifact_stl = stl_path

        if context.export.get("step") and (artifact.label != "assembled" or not panel_assembly_enabled):
            step_path = context.out_dir / f"{artifact.basename}.step"
            step_tasks.append(
                StepExportTask(
                    scad_path=scad_path,
                    step_path=step_path,
                    export_cfg=context.export,
                    openscad_bin=context.openscad_bin,
                    freecad_bin=context.freecad_bin,
                    stl_path=artifact_stl,
                    metadata={"artifact_basename": artifact.basename},
                )
            )

        preview_prisms = artifact.preview_prisms
        if png_enabled:
            png_path = context.out_dir / f"{artifact.basename}.png"
            try:
                run_openscad(scad_path, png_path, context.openscad_bin, png_args)
            except ExportError as exc:
                render_isometric_preview(preview_prisms, png_path)
                logs.append(f"PNG fallback rendered to {png_path} ({exc})")
            else:
                logs.append(f"PNG written to {png_path}")
            png_paths.append(png_path)
            artifact_png = png_path

        record = {
            "label": artifact.label,
            "basename": artifact.basename,
            "scad": str(scad_path),
            "stl": str(artifact_stl) if artifact_stl else None,
            "step": None,
            "png": str(artifact_png) if artifact_png else None,
        }
        artifact_records.append(record)
        artifact_record_map[artifact.basename] = record

        if artifact.label == "assembled" and panel_assembly_enabled:
            assembly_plan = AssemblyPlan(
                placements=placements,
                step_path=context.out_dir / f"{artifact.basename}.step",
                record=record,
                scad_path=scad_path,
            )

    if step_tasks:
        for task, step_result in export_step_artifacts_parallel(step_tasks):
            meta = task.metadata or {}
            if meta.get("panel_step") and meta.get("panel_id"):
                panel_id = str(meta["panel_id"])
                panel_step_sources[panel_id] = step_result.step_path
                logs.append(f"STEP panel {panel_id} -> {step_result.step_path}")
                continue

            step_paths.append(step_result.step_path)
            basename = meta.get("artifact_basename")
            if basename and basename in artifact_record_map:
                artifact_record_map[basename]["step"] = str(step_result.step_path)
            if step_result.dedup_hit and step_result.cache_path:
                logs.append(
                    f"STEP linked to cached geometry {step_result.cache_path} -> {step_result.step_path}"
                )
            else:
                logs.append(f"STEP written to {step_result.step_path}")

    if assembly_plan and panel_assembly_enabled and context.export.get("step"):
        try:
            if not context.freecad_bin:
                raise ExportError("freecad binary not configured for assembly export")
            parts: List[StepAssemblyPart] = []
            missing_panels: List[str] = []
            for placement in assembly_plan.placements:
                panel_id = placement.panel.panel_id
                step_src = panel_step_sources.get(panel_id)
                if not step_src:
                    missing_panels.append(panel_id)
                    continue
                parts.append(
                    StepAssemblyPart(
                        step_path=step_src,
                        matrix=scad_writer.placement_transform_matrix(placement, placement.panel),
                    )
                )
            if missing_panels:
                raise ExportError(
                    f"missing STEP panels for assembly: {', '.join(sorted(set(missing_panels)))}"
                )
            assemble_step_from_parts(parts, assembly_plan.step_path, context.freecad_bin)
            step_paths.append(assembly_plan.step_path)
            assembly_plan.record["step"] = str(assembly_plan.step_path)
            logs.append(
                f"STEP assembled from {len(parts)} panels -> {assembly_plan.step_path}"
            )
        except ExportError as exc:
            logs.append(f"STEP assembly fallback via SCAD export ({exc})")
            fallback = export_step_artifact(
                assembly_plan.scad_path,
                assembly_plan.step_path,
                export_cfg=context.export,
                openscad_bin=context.openscad_bin,
                freecad_bin=context.freecad_bin,
            )
            step_paths.append(fallback.step_path)
            assembly_plan.record["step"] = str(fallback.step_path)
            if fallback.dedup_hit and fallback.cache_path:
                logs.append(
                    f"STEP linked to cached geometry {fallback.cache_path} -> {fallback.step_path}"
                )
            else:
                logs.append(f"STEP written to {fallback.step_path}")

    meta = {
        "params": asdict(params),
        "panel_count": len(panel_set.panels) if panel_set else 1,
        "layout": {
            "mode": _layout_mode(_extract_layout_section(context)),
            "bed_mm": list(layout_cfg.bed_size_mm),
            "spacing_mm": layout_cfg.spacing_mm,
            "sheet_count": sheet_count,
        },
        "artifacts": artifact_records,
    }
    return EngineResult(
        scad_path=scad_primary,
        stl_paths=stl_paths,
        step_paths=step_paths,
        png_paths=png_paths,
        logs=logs,
        metadata=meta,
    )


def _filter_params(raw: Mapping[str, Any]) -> Dict[str, Any]:
    return {k: raw[k] for k in raw if k in PARAM_FIELDS}


def _extract_layout_section(context: BuildContext) -> Mapping[str, Any]:
    if isinstance(context.model, Mapping) and "layout" in context.model:
        layout_section = context.model["layout"]
        if isinstance(layout_section, Mapping):
            return layout_section
    raw = context.raw_config
    if isinstance(raw, Mapping) and "layout" in raw:
        entry = raw["layout"]
        if isinstance(entry, Mapping):
            return entry
    return {}


def _layout_mode(section: Mapping[str, Any]) -> str:
    mode = str(section.get("mode", "assembled")).lower()
    if mode not in {"assembled", "flat", "both", DEBUG_LAYOUT_MODE}:
        return "assembled"
    return mode


def _extract_layout_cfg(context: BuildContext) -> layout_builder.LayoutConfig:
    section = _extract_layout_section(context)
    bed = section.get("bed_mm", (200.0, 200.0))
    if isinstance(bed, (list, tuple)) and len(bed) == 2:
        bed_tuple = (float(bed[0]), float(bed[1]))
    else:
        bed_tuple = (200.0, 200.0)
    spacing = float(section.get("spacing_mm", 6.0))
    return layout_builder.LayoutConfig(bed_size_mm=bed_tuple, spacing_mm=spacing)


def _build_artifacts(
    plan: layout_builder.LayoutPlan,
    context: BuildContext,
    cfg: layout_builder.LayoutConfig,
    params: PapierkorbParams,
) -> List[LayoutArtifact]:
    section = _extract_layout_section(context)
    mode = _layout_mode(section)
    artifacts: List[LayoutArtifact] = []
    basename = context.basename
    if mode == DEBUG_LAYOUT_MODE:
        artifacts.append(_build_debug_artifact(plan, context, cfg, params, basename))
        return artifacts
    if mode in ("assembled", "both"):
        prisms = _assembled_preview_prisms(params)
        artifacts.append(
            LayoutArtifact(
                label="assembled",
                basename=basename,
                placements=plan.assembled,
                preview_prisms=prisms,
            )
        )
    if mode in ("flat", "both"):
        for sheet in plan.flat_sheets:
            prisms = _flat_preview_prisms(sheet)
            artifacts.append(
                LayoutArtifact(
                    label=sheet.name,
                    basename=f"{basename}_{sheet.name}",
                    placements=sheet.placements,
                    preview_prisms=prisms,
                )
            )
    return artifacts


def _assembled_preview_prisms(params: PapierkorbParams) -> List[RectPrismSpec]:
    prisms: List[RectPrismSpec] = []
    L = params.length_mm
    B = params.width_mm
    H = params.height_mm
    wall = params.wall_mm

    Nx, Ny, _ = params.tile_counts()
    tile_x = L / Nx
    tile_y = B / Ny

    base_color = (120, 140, 200)
    for ix in range(Nx):
        for iy in range(Ny):
            x0 = -L / 2.0 + ix * tile_x
            y0 = -B / 2.0 + iy * tile_y
            prisms.append(
                RectPrismSpec(
                    x0,
                    y0,
                    0.0,
                    x0 + tile_x,
                    y0 + tile_y,
                    wall,
                    base_color,
                )
            )

    wall_color = (80, 90, 110)
    prisms.append(RectPrismSpec(-L / 2.0, B / 2.0 - wall, 0.0, L / 2.0, B / 2.0, H, wall_color))
    prisms.append(RectPrismSpec(-L / 2.0, -B / 2.0, 0.0, L / 2.0, -B / 2.0 + wall, H, wall_color))
    prisms.append(RectPrismSpec(L / 2.0 - wall, -B / 2.0, 0.0, L / 2.0, B / 2.0, H, wall_color))
    prisms.append(RectPrismSpec(-L / 2.0, -B / 2.0, 0.0, -L / 2.0 + wall, B / 2.0, H, wall_color))

    if params.enable_rim:
        rim_h = params.rim_height_mm
        rim_w = params.rim_width_mm
        rim_color = (200, 200, 215)
        prisms.append(RectPrismSpec(-L / 2.0, B / 2.0 - rim_w, H - rim_h, L / 2.0, B / 2.0, H, rim_color))
        prisms.append(RectPrismSpec(-L / 2.0, -B / 2.0, H - rim_h, L / 2.0, -B / 2.0 + rim_w, H, rim_color))
        prisms.append(RectPrismSpec(L / 2.0 - rim_w, -B / 2.0, H - rim_h, L / 2.0, B / 2.0, H, rim_color))
        prisms.append(RectPrismSpec(-L / 2.0, -B / 2.0, H - rim_h, -L / 2.0 + rim_w, B / 2.0, H, rim_color))
    return prisms


def _build_debug_artifact(
    plan: layout_builder.LayoutPlan,
    context: BuildContext,
    cfg: layout_builder.LayoutConfig,
    params: PapierkorbParams,
    basename: str,
) -> LayoutArtifact:
    assembled_maker = panel_render.build_maker(plan.assembled, layout_label="assembled")
    offset_x = params.length_mm / 2.0 + cfg.spacing_mm + cfg.bed_size_mm[0] / 2.0
    shifted_flat = _shift_flat_placements(plan.flat_sheets, offset_x)
    if shifted_flat:
        flat_maker = panel_render.build_maker(shifted_flat, layout_label="debug_panels")
        assembled_maker.add(flat_maker)
    prisms = _assembled_preview_prisms(params)
    prisms.extend(_flat_preview_prisms_shifted(plan.flat_sheets, offset_x))
    return LayoutArtifact(
        label=DEBUG_LAYOUT_MODE,
        basename=f"{basename}_debug",
        placements=[],
        preview_prisms=prisms,
        maker=assembled_maker,
    )


def _flat_preview_prisms(sheet: layout_builder.FlatSheet) -> List[RectPrismSpec]:
    prisms: List[RectPrismSpec] = []
    for placement in sheet.placements:
        panel = placement.panel
        centre = placement.origin
        x0 = centre.x - panel.width / 2.0
        x1 = centre.x + panel.width / 2.0
        y0 = centre.y - panel.height / 2.0
        y1 = centre.y + panel.height / 2.0
        z0 = 0.0
        z1 = panel.thickness
        prisms.append(RectPrismSpec(x0, y0, z0, x1, y1, z1, (90, 120, 180)))
    return prisms


def _flat_preview_prisms_shifted(
    sheets: List[layout_builder.FlatSheet], offset_x: float
) -> List[RectPrismSpec]:
    prisms: List[RectPrismSpec] = []
    for sheet in sheets:
        for base in _flat_preview_prisms(sheet):
            prisms.append(
                RectPrismSpec(
                    base.x0 + offset_x,
                    base.y0,
                    base.z0,
                    base.x1 + offset_x,
                    base.y1,
                    base.z1,
                    base.color,
                )
            )
    return prisms


def _shift_flat_placements(
    sheets: List[layout_builder.FlatSheet], offset_x: float
) -> List[layout_builder.PanelPlacement]:
    shifted: List[layout_builder.PanelPlacement] = []
    for sheet in sheets:
        for placement in sheet.placements:
            origin = placement.origin + Vec3(offset_x, 0.0, 0.0)
            shifted.append(
                layout_builder.PanelPlacement(
                    panel=placement.panel,
                    origin=origin,
                    axes=placement.axes,
                    sheet=placement.sheet,
                )
            )
    return shifted
