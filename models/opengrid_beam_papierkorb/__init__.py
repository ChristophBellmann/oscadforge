from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

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
from ..papierkorb import layout as layout_builder
from ..papierkorb.layout import LayoutConfig, PanelPlacement
from .connectors import ConnectorPlan, plan_connectors
from .panels import OpenGridPanelSet, build_panels
from .params import OpenGrid2Params
from .scad_writer import (
    BeamPlacementMode,
    IncludePaths,
    build_scad_for_artifact,
    build_scad_for_panel,
    placement_matrix,
    _beam_panel_id,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass
class LayoutArtifact:
    label: str
    basename: str
    placements: Iterable[PanelPlacement]
    preview_prisms: List[RectPrismSpec]
    is_connector_sheet: bool = False
    beam_mode: BeamPlacementMode = BeamPlacementMode.PANEL_ONLY


@dataclass
class AssemblyPlan:
    placements: List[PanelPlacement]
    step_path: Path
    record: Dict[str, Any]
    scad_path: Path


def build(context: BuildContext) -> EngineResult:
    params = OpenGrid2Params.from_mapping(context.model_params)
    panel_set = build_panels(params.bin, params.board)
    params.board.bin_length = panel_set.length_mm
    params.board.bin_width = panel_set.width_mm
    params.board.bin_height = panel_set.height_mm
    params.board.angle_connector_path = _relpath(
        REPO_ROOT / "in" / "opengrid_angle" / "2-1_8x.stl", context.out_dir
    )
    layout_cfg = _extract_layout_cfg(context)
    plan = layout_builder.build_layout(panel_set.panels, layout_cfg)
    connector_plan = plan_connectors(
        panel_set, include_floor_edges=params.connectors.include_floor_edges
    )
    if not params.connectors.generate_connectors:
        connector_plan = ConnectorPlan(snap_count=0, corner_count=0)

    artifacts = _build_artifacts(plan, context, panel_set, connector_plan, layout_cfg)
    if not artifacts:
        raise ValueError("no layout artifacts produced; check layout.mode configuration")

    png_enabled, png_args = build_png_args(context.export.get("png"))
    assembly_mode = str(context.export.get("step_assembly", "panel") or "panel").lower()
    panel_assembly_enabled = assembly_mode == "panel"
    scad_primary: Path | None = None
    stl_paths: List[Path] = []
    step_paths: List[Path] = []
    png_paths: List[Path] = []
    step_tasks: List[StepExportTask] = []
    assembly_plan: AssemblyPlan | None = None
    panel_step_sources: Dict[str, Path] = {}
    logs: List[str] = []
    artifact_records: List[Dict[str, Any]] = []
    artifact_record_map: Dict[str, Dict[str, Any]] = {}
    panel_step_sources: Dict[str, Path] = {}
    png_tasks: List[PNGExportTask] = []

    includes = _resolve_includes(context.out_dir)

    backend = str(context.export.get("step_backend", "openscad") or "openscad").lower()
    include_preview_imports = backend != "freecad_csg"

    panel_scad_paths: Dict[str, Path] = {}
    if panel_set is not None and context.export.get("step") and panel_assembly_enabled:
        for panel in panel_set.panels:
            if panel.panel_id in panel_scad_paths:
                continue
            panel_scad_path = context.out_dir / f"panel_geom_{panel.panel_id}.scad"
            panel_scad_text = build_scad_for_panel(
                panel=panel,
                board=params.board,
                includes=includes,
            )
            panel_scad_path.write_text(panel_scad_text, encoding="utf-8")
            panel_scad_paths[panel.panel_id] = panel_scad_path
            panel_step_path = context.out_dir / f"panel_geom_{panel.panel_id}.step"
            step_tasks.append(
                StepExportTask(
                    scad_path=panel_scad_path,
                    step_path=panel_step_path,
                    export_cfg=context.export,
                    openscad_bin=context.openscad_bin,
                    freecad_bin=context.freecad_bin,
                    metadata={"panel_id": panel.panel_id, "panel_step": True},
                )
            )

    artifact_inputs = [(artifact, list(artifact.placements)) for artifact in artifacts]
    rendered_artifacts = _render_artifacts_concurrently(
        artifact_inputs,
        panel_set,
        params.board,
        connector_plan,
        params.connectors,
        includes,
        include_preview_imports,
    )

    for rendered in rendered_artifacts:
        artifact = rendered.artifact
        placements = rendered.placements
        scad_text = rendered.scad_text
        scad_path = context.out_dir / f"{artifact.basename}.scad"
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
            export_cfg = context.export
            if backend == "freecad_csg" and artifact.is_connector_sheet:
                export_cfg = dict(context.export)
                export_cfg["step_backend"] = "freecad"
            step_tasks.append(
                StepExportTask(
                    scad_path=scad_path,
                    step_path=step_path,
                    export_cfg=export_cfg,
                    openscad_bin=context.openscad_bin,
                    freecad_bin=context.freecad_bin,
                    stl_path=artifact_stl,
                    metadata={
                        "artifact_basename": artifact.basename,
                        "artifact_label": artifact.label,
                    },
                )
            )

        if png_enabled:
            png_path = context.out_dir / f"{artifact.basename}.png"
            png_paths.append(png_path)
            artifact_png = png_path
            png_tasks.append(
                PNGExportTask(
                    scad_path=scad_path,
                    png_path=png_path,
                    preview_prisms=artifact.preview_prisms,
                    png_args=png_args,
                )
            )

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
            continue

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

    if png_enabled and png_tasks:
        png_logs = _run_png_tasks_concurrently(png_tasks, context.openscad_bin)
        logs.extend(png_logs)

    if assembly_plan and context.export.get("step") and panel_assembly_enabled:
        try:
            if not context.freecad_bin:
                raise ExportError("freecad binary not configured for assembly export")
            parts: List[StepAssemblyPart] = []
            missing_panels: List[str] = []
            for placement in assembly_plan.placements:
                panel_id = placement.panel.panel_id
                step_source = panel_step_sources.get(panel_id)
                if not step_source:
                    missing_panels.append(panel_id)
                    continue
                parts.append(
                    StepAssemblyPart(
                        step_path=step_source,
                        matrix=placement_matrix(placement),
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
        "model": "opengrid-beam_papierkorb",
        "dimensions_mm": {
            "length": panel_set.length_mm,
            "width": panel_set.width_mm,
            "height": panel_set.height_mm,
        },
        "tile_size_mm": params.board.tile_size_mm,
        "panel_counts": {
            "length": len(panel_set.length_chunks.cells),
            "width": len(panel_set.width_chunks.cells),
            "height": len(panel_set.height_chunks.cells),
        },
        "connectors": connector_plan.as_dict(),
        "layout": {
            "mode": _layout_mode(_extract_layout_section(context)),
            "bed_mm": list(layout_cfg.bed_size_mm),
            "spacing_mm": layout_cfg.spacing_mm,
            "sheet_count": len(plan.flat_sheets),
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


def _build_artifacts(
    plan: layout_builder.LayoutPlan,
    context: BuildContext,
    panel_set: OpenGridPanelSet,
    connector_plan: ConnectorPlan,
    layout_cfg: LayoutConfig,
) -> List[LayoutArtifact]:
    section = _extract_layout_section(context)
    mode = _layout_mode(section)
    artifacts: List[LayoutArtifact] = []
    basename = context.basename

    if mode in ("assembled", "both"):
        artifacts.append(
            LayoutArtifact(
                label="assembled",
                basename=_artifact_basename(basename, "assembled"),
                placements=plan.assembled,
                preview_prisms=_assembled_preview_prisms(panel_set),
                beam_mode=BeamPlacementMode.BOTH,
            )
        )

    if mode in ("flat", "both"):
        for sheet in plan.flat_sheets:
            sheet_label = sheet.module_label or sheet.name
            sheet_beam_label = (
                _beam_panel_id(sheet_label) if sheet.module_label else f"{sheet_label}_beam"
            )
            artifacts.append(
                LayoutArtifact(
                    label=sheet.name,
                    basename=_artifact_basename(basename, sheet_label),
                    placements=sheet.placements,
                    preview_prisms=_sheet_preview_prisms(sheet, panel_set),
                )
            )
            artifacts.append(
                LayoutArtifact(
                    label=f"{sheet.name}_beam",
                    basename=_artifact_basename(basename, sheet_beam_label),
                    placements=sheet.placements,
                    preview_prisms=_sheet_preview_prisms(sheet, panel_set),
                    beam_mode=BeamPlacementMode.BEAM_ONLY,
                )
            )
        if plan.flat_sheets or layout_cfg.sheet_combined_mode == "assembled":
            combined_placements = _combined_placements(plan, layout_cfg.sheet_combined_mode)
            preview = _preview_for_mode(plan, panel_set, layout_cfg.sheet_combined_mode)
            if layout_cfg.combined_sheets:
                artifacts.append(
                sheet_label = sheet.module_label or sheet.name
                beam_label = _beam_panel_id(sheet_label) if sheet.module_label else f"{sheet_label}_beam"
                LayoutArtifact(
                    label="sheet",
                    basename=_artifact_basename(basename, sheet_label),
                    placements=combined_placements,
                    preview_prisms=preview,
                    beam_mode=BeamPlacementMode.PANEL_ONLY,
                    )
                )
            if layout_cfg.combined_beams:
                beam_placements = _combined_placements(plan, layout_cfg.beam_combined_mode)
                beam_preview = _preview_for_mode(plan, panel_set, layout_cfg.beam_combined_mode)
                artifacts.append(
                    LayoutArtifact(
                        label="beam",
                        basename=_artifact_basename(basename, "beam"),
                        placements=beam_placements,
                        preview_prisms=beam_preview,
                        beam_mode=BeamPlacementMode.BEAM_ONLY,
                    )
                )

    if connector_plan.snap_count or connector_plan.corner_count:
        artifacts.append(
            LayoutArtifact(
                label="connectors",
                basename=_artifact_basename(basename, "connectors"),
                placements=[],
                preview_prisms=_connector_preview(panel_set),
                is_connector_sheet=True,
            )
        )
    return artifacts


def _artifact_basename(base: str, label: str) -> str:
    if label == "assembled":
        return base
    return f"{base}_{label}"


def _assembled_preview_prisms(panel_set: OpenGridPanelSet) -> List[RectPrismSpec]:
    length = panel_set.length_mm
    width = panel_set.width_mm
    height = panel_set.height_mm
    return [
        RectPrismSpec(
            x0=-length / 2.0,
            y0=-width / 2.0,
            z0=0.0,
            x1=length / 2.0,
            y1=width / 2.0,
            z1=height,
            color=(120, 150, 210),
        )
    ]


def _sheet_preview_prisms(sheet, panel_set: OpenGridPanelSet) -> List[RectPrismSpec]:
    width = getattr(sheet, "width", panel_set.length_mm)
    height = getattr(sheet, "height", panel_set.width_mm)
    return [
        RectPrismSpec(
            x0=-width / 2.0,
            y0=-height / 2.0,
            z0=0.0,
            x1=width / 2.0,
            y1=height / 2.0,
            z1=panel_set.wall_thickness_mm,
            color=(180, 180, 180),
        )
    ]


def _combined_placements(plan: layout_builder.LayoutPlan, mode: str) -> List[PanelPlacement]:
    if mode == "assembled" or not plan.flat_sheets:
        return list(plan.assembled)
    combined: List[PanelPlacement] = []
    for sheet in plan.flat_sheets:
        combined.extend(sheet.placements)
    return combined


def _preview_for_mode(plan: layout_builder.LayoutPlan, panel_set: OpenGridPanelSet, mode: str) -> List[RectPrismSpec]:
    if mode == "assembled" or not plan.flat_sheets:
        return _assembled_preview_prisms(panel_set)
    return _sheet_preview_prisms(plan.flat_sheets[0], panel_set)


def _connector_preview(panel_set: OpenGridPanelSet) -> List[RectPrismSpec]:
    size = max(panel_set.length_mm, panel_set.width_mm) * 0.15
    thickness = panel_set.wall_thickness_mm
    return [
        RectPrismSpec(
            x0=-size / 2.0,
            y0=-size / 2.0,
            z0=0.0,
            x1=size / 2.0,
            y1=size / 2.0,
            z1=thickness,
            color=(200, 150, 120),
        )
    ]


@dataclass
class RenderedArtifact:
    artifact: LayoutArtifact
    placements: List[PanelPlacement]
    scad_text: str


def _render_artifacts_concurrently(
    inputs: list[tuple[LayoutArtifact, list[PanelPlacement]]],
    panel_set: OpenGridPanelSet,
    board: BoardOptions,
    connector_plan: ConnectorPlan,
    connector_opts: ConnectorOptions,
    includes: IncludePaths,
    include_preview_imports: bool,
) -> list[RenderedArtifact]:
    max_workers = max(1, min(32, os.cpu_count() or 1))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for artifact, placements in inputs:
            connectors = connector_plan if artifact.is_connector_sheet else None
            connector_options = connector_opts if artifact.is_connector_sheet else None
            futures.append(
                executor.submit(
                    _build_artifact_scad_text,
                    artifact,
                    placements,
                    panel_set,
                    board,
                    connectors,
                    connector_options,
                    includes,
                    include_preview_imports,
                )
            )
    return [future.result() for future in futures]


def _build_artifact_scad_text(
    artifact: LayoutArtifact,
    placements: list[PanelPlacement],
    panel_set: OpenGridPanelSet,
    board: BoardOptions,
    connectors: ConnectorPlan | None,
    connector_opts: ConnectorOptions | None,
    includes: IncludePaths,
    include_preview_imports: bool,
) -> RenderedArtifact:
        scad_text = build_scad_for_artifact(
            artifact_label=artifact.label,
            placements=placements,
            panel_set=panel_set,
            board=board,
            connectors=connectors,
            connector_opts=connector_opts,
            includes=includes,
            include_preview_imports=include_preview_imports,
            beam_mode=artifact.beam_mode,
        )
        return RenderedArtifact(artifact=artifact, placements=placements, scad_text=scad_text)


@dataclass
class PNGExportTask:
    scad_path: Path
    png_path: Path
    preview_prisms: List[RectPrismSpec]
    png_args: Sequence[str]


def _run_png_tasks_concurrently(tasks: List[PNGExportTask], openscad_bin: str | None) -> List[str]:
    if not tasks:
        return []
    max_workers = max(1, min(16, os.cpu_count() or 1))
    logs: List[str] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_run_single_png_task, task, openscad_bin) for task in tasks]
        for future in futures:
            logs.extend(future.result())
    return logs


def _run_single_png_task(task: PNGExportTask, openscad_bin: str | None) -> List[str]:
    try:
        run_openscad(task.scad_path, task.png_path, openscad_bin, task.png_args)
    except ExportError as exc:
        render_isometric_preview(task.preview_prisms, task.png_path)
        return [f"PNG fallback rendered to {task.png_path} ({exc})"]
    else:
        return [f"PNG written to {task.png_path}"]


def _resolve_includes(out_dir: Path) -> IncludePaths:
    bosl2 = REPO_ROOT / "third_party" / "BOSL2" / "std.scad"
    open_grid = REPO_ROOT / "third_party" / "QuackWorks" / "openGrid" / "openGrid.scad"
    open_grid_beam = REPO_ROOT / "third_party" / "QuackWorks" / "openGrid" / "openGrid-beam.scad"
    snap = REPO_ROOT / "third_party" / "QuackWorks" / "openGrid" / "opengrid-snap.scad"
    angle = REPO_ROOT / "in" / "opengrid_angle" / "1-1_1x.stl"
    return IncludePaths(
        bosl2=_relpath(bosl2, out_dir),
        open_grid=_relpath(open_grid, out_dir),
        open_grid_beam=_relpath(open_grid_beam, out_dir),
        snap=_relpath(snap, out_dir),
        angle_connector=_relpath(angle, out_dir),
    )


def _relpath(target: Path, base: Path) -> str:
    return os.path.relpath(target, base).replace("\\", "/")


def _extract_layout_section(context: BuildContext) -> Mapping[str, Any]:
    if isinstance(context.model, Mapping) and "layout" in context.model:
        entry = context.model["layout"]
        if isinstance(entry, Mapping):
            return entry
    raw = context.raw_config
    if isinstance(raw, Mapping) and "layout" in raw:
        entry = raw["layout"]
        if isinstance(entry, Mapping):
            return entry
    return {}


def _layout_mode(section: Mapping[str, Any]) -> str:
    mode = str(section.get("mode", "assembled")).lower()
    if mode not in {"assembled", "flat", "both"}:
        return "assembled"
    return mode


def _extract_layout_cfg(context: BuildContext) -> LayoutConfig:
    section = _extract_layout_section(context)
    bed = section.get("bed_mm", (200.0, 200.0))
    if isinstance(bed, (list, tuple)) and len(bed) == 2:
        bed_tuple = (float(bed[0]), float(bed[1]))
    else:
        bed_tuple = (200.0, 200.0)
    spacing = float(section.get("spacing_mm", 6.0))
    combined_sheets = bool(section.get("combined_sheets", True))
    combined_beams = bool(section.get("combined_beams", True))
    sheet_mode = str(section.get("sheet_combined_mode", "flat")).lower()
    if sheet_mode not in {"flat", "assembled", "combined"}:
        sheet_mode = "flat"
    if sheet_mode == "combined":
        sheet_mode = "assembled"
    beam_mode = str(section.get("beam_combined_mode", "flat")).lower()
    if beam_mode not in {"flat", "assembled", "combined"}:
        beam_mode = "flat"
    if beam_mode == "combined":
        beam_mode = "assembled"
    return LayoutConfig(
        bed_size_mm=bed_tuple,
        spacing_mm=spacing,
        combined_sheets=combined_sheets,
        combined_beams=combined_beams,
        sheet_combined_mode=sheet_mode,
        beam_combined_mode=beam_mode,
    )
