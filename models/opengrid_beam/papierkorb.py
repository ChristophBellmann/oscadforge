from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Sequence
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from ...core.engine import BuildContext, EngineResult
from ...core.export import ExportError, build_png_args, run_openscad
from ..papierkorb.layout import build_layout, LayoutConfig
from ..papierkorb.params import PapierkorbParams
from ..papierkorb.panels import Panel, PanelGrid, build_panels
from ..papierkorb.scad_writer import build_scad_for_panel
from . import BEAM_SCAD_PATH, BeamJointParams, _render_scad

REPO_ROOT = next(p for p in Path(__file__).resolve().parents if p.name == "oscadforge").parent


def _panel_ids_by_sheet(panels: Sequence[Panel], cfg: LayoutConfig) -> Dict[str, List[str]]:
    plan = build_layout(panels, cfg)
    mapping: Dict[str, List[str]] = {}
    for sheet in plan.flat_sheets:
        mapping[sheet.name] = [p.panel.panel_id for p in sheet.placements]
    mapping["assembled"] = [p.panel.panel_id for p in plan.assembled]
    return mapping


def placement_matrix(place) -> List[List[float]]:
    panel = place.panel
    origin = panel.origin
    u_vec = panel.axes.u.vector()
    v_vec = panel.axes.v.vector()
    w_vec = panel.axes.w.vector()
    return [
        [u_vec.x, v_vec.x, w_vec.x, origin.x],
        [u_vec.y, v_vec.y, w_vec.y, origin.y],
        [u_vec.z, v_vec.z, w_vec.z, origin.z],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _edge_flags(panel: Panel, grid: PanelGrid):
    Nx, Ny, Nz = grid.Nx, grid.Ny, grid.Nz
    if panel.kind is panel.kind.FLOOR:
        ix, iy, _ = panel.indices
        bottom = iy == 0
        top = iy == Ny - 1
        left = ix == 0
        right = ix == Nx - 1
    elif panel.kind in (panel.kind.WALL_POS_Y, panel.kind.WALL_NEG_Y):
        ix, _, iz = panel.indices
        bottom = iz == 0
        top = iz == Nz - 1
        left = ix == 0
        right = ix == Nx - 1
    elif panel.kind in (panel.kind.WALL_POS_X, panel.kind.WALL_NEG_X):
        _, iy, iz = panel.indices
        bottom = iz == 0
        top = iz == Nz - 1
        left = iy == 0
        right = iy == Ny - 1
    else:
        bottom = top = left = right = False
    return bottom, right, left, top


def _z_overhang_mm(variant: str, has_joints: bool, has_chamfer: bool) -> float:
    key = variant.lower()
    if key == "lite":
        return 9.25 if has_chamfer else (13.5 if has_joints else 5.1)
    if key == "heavy":
        return 11.2 if has_chamfer else (13.5 if has_joints else 5.1)
    return 9.25 if has_chamfer else (13.5 if has_joints else 5.1)


def _overhang_xy_mm(variant: str) -> float:
    return {"lite": 9.1, "full": 11.9, "heavy": 18.9}.get(variant.lower(), 11.9)


def _prelude(out_dir: Path) -> str:
    bosl = (REPO_ROOT / "third_party" / "BOSL2" / "std.scad").resolve()
    og = (REPO_ROOT / "third_party" / "QuackWorks" / "openGrid" / "openGrid.scad").resolve()
    bosl_abs = bosl.as_posix()
    og_abs = og.as_posix()
    return (
        f'include <{bosl_abs}>;\n'
        f'use <{og_abs}>;\n'
        f'$tags_shown = \"ALL\";\n'
        f'$tags_hidden = [];\n'
        f'$tags = [];\n'
        f'$tag = \"\";\n'
    )


def _beam_scad_for_panel(panel, params: BeamJointParams, grid: PanelGrid, out_dir: Path) -> str:
    tile = params.tile_size_mm
    bw = max(1, round(panel.width / tile))
    bh = max(1, round(panel.height / tile))
    bottom, right, left, top = _edge_flags(panel, grid)

    layer_bottom = panel.kind is panel.kind.FLOOR
    layer_top = (
        panel.kind in (panel.kind.WALL_POS_Y, panel.kind.WALL_NEG_Y, panel.kind.WALL_POS_X, panel.kind.WALL_NEG_X)
        and panel.indices[2] == grid.Nz - 1
    )

    chamfer_edge = layer_top

    corner_bl = bottom and left and layer_bottom
    corner_br = bottom and right and layer_bottom
    corner_tl = top and left and layer_bottom
    corner_tr = top and right and layer_bottom

    board_conn = bottom or right or left or top

    bp = replace(
        params,
        board_width=bw,
        board_height=bh,
        beam_bottom=bottom,
        beam_top=top,
        beam_left=left,
        beam_right=right,
        boardconnector_cutouts=False,  # always off: avoid tile face rendering on beams
        beamconnector_cutouts=board_conn,
        boardconnector_bottom_l=False,
        boardconnector_bottom_r=False,
        boardconnector_top_l=False,
        boardconnector_top_r=False,
        boardconnector_left_l=False,
        boardconnector_left_r=False,
        boardconnector_right_l=False,
        boardconnector_right_r=False,
        beamconnector_bottom_l=bottom,
        beamconnector_bottom_r=bottom,
        beamconnector_top_l=top,
        beamconnector_top_r=top,
        beamconnector_left_l=left,
        beamconnector_left_r=left,
        beamconnector_right_l=right,
        beamconnector_right_r=right,
        joints_enabled=corner_bl or corner_br or corner_tl or corner_tr,
        joint_bottom_l=corner_bl,
        joint_bottom_r=corner_br,
        joint_top_l=corner_tl,
        joint_top_r=corner_tr,
        joint_left_l=False,
        joint_left_r=False,
        joint_right_l=False,
        joint_right_r=False,
        chamfers=chamfer_edge,
        chamfer_bottom_l=chamfer_edge and bottom,
        chamfer_bottom_r=chamfer_edge and bottom,
        chamfer_left_l=chamfer_edge and left,
        chamfer_left_r=chamfer_edge and left,
        chamfer_top_l=chamfer_edge and top,
        chamfer_top_r=chamfer_edge and top,
        chamfer_right_l=chamfer_edge and right,
        chamfer_right_r=chamfer_edge and right,
    )

    has_joints = corner_bl or corner_br or corner_tl or corner_tr
    has_chamfer = chamfer_edge
    z_shift = _z_overhang_mm(bp.board_variant, has_joints, has_chamfer)
    prelude = _prelude(out_dir)
    body = _render_scad(bp, call_scene=False, include_prelude=False)
    include_src = f'include <{BEAM_SCAD_PATH.resolve().as_posix()}>;'
    module_name = f"beam_geom_{panel.panel_id}"
    return (
        f"{prelude}\n"
        f"{include_src}\n"
        f"module {module_name}() {{\n"
        f"{body}\n"
        f"  translate([0,0,-{z_shift}]) scene(Board_Width=Board_Width, Board_Height=Board_Height);\n"
        f"}}\n\n"
        f"if (is_undef($beam_autorender) || $beam_autorender) {module_name}();\n"
    )


def build(context: BuildContext) -> EngineResult:
    papierkorb_params = PapierkorbParams.from_model_config(context.model_params)
    panel_result = build_panels(papierkorb_params)
    panels = panel_result.panels
    grid = panel_result.grid

    layout_cfg = LayoutConfig(
        bed_size_mm=tuple(context.model.get("layout", {}).get("bed_mm", [256.0, 256.0])),  # optional
        spacing_mm=context.model.get("layout", {}).get("spacing_mm", 6.0),
    )
    sheet_map = _panel_ids_by_sheet(panels, layout_cfg)

    base = BeamJointParams.from_mapping(context.model_params)
    board_cfg = context.model_params.get("board", {})
    base.board_variant = str(board_cfg.get("variant", base.board_variant))
    base.tile_size_mm = board_cfg.get("tile_size_mm", base.tile_size_mm)
    base.tile_thickness_mm = board_cfg.get("thickness_mm", board_cfg.get("tile_thickness_mm", base.tile_thickness_mm))
    base.board_width = base.board_height = 1

    out_dir = context.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    beam_paths: Dict[str, Path] = {}
    panel_paths: Dict[str, Path] = {}
    png_paths: List[Path] = []
    logs: List[str] = []

    max_workers = max(1, int(os.getenv("OSCADFORGE_WORKERS", os.cpu_count() or 4)))

    jl_scad_dir = (REPO_ROOT / "third_party" / "jl_scad").resolve()
    jl_scad_path = os.path.relpath(jl_scad_dir, out_dir)
    jl_scad_path = jl_scad_path.replace(os.sep, "/")

    def task_panel(panel):
        # beam
        beam_text = _beam_scad_for_panel(panel, base, grid, out_dir)
        beam_path = out_dir / f"{panel.panel_id}_beam.scad"
        beam_path.write_text(beam_text, encoding="utf-8")
        # panel
        panel_text = build_scad_for_panel(
            params=papierkorb_params,
            panel=panel,
            jl_scad_path=jl_scad_path,
        )
        panel_path = out_dir / f"{panel.panel_id}_panel.scad"
        panel_path.write_text(panel_text, encoding="utf-8")
        return panel.panel_id, beam_path, panel_path

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(task_panel, panel): panel for panel in panels}
        for fut in as_completed(futures):
            panel = futures[fut]
            pid, beam_path, panel_path = fut.result()
            beam_paths[pid] = beam_path
            panel_paths[pid] = panel_path
            logs.append(f"SCAD written to {beam_path}")
            logs.append(f"SCAD written to {panel_path}")

    # Build assembled combo SCAD that includes tiles and beams aligned
    # Build assembled (panels + beams) with placement transforms
    plan = build_layout(panels, layout_cfg)
    assembled_lines = [
        "// Combined panels + beams",
        "$fn=64;",
        '$tags_shown=\"ALL\";',
        '$tags_hidden=[];',
        '$tags=[];',
        '$tag=\"\";',
        '$beam_autorender=false;',
    ]
    # Use (not include) so only module definitions are imported
    for path in beam_paths.values():
        assembled_lines.append(f"include <{path.name}>;")
    for path in panel_paths.values():
        assembled_lines.append(f"include <{path.name}>;")

    for place in plan.assembled:
        pid = place.panel.panel_id
        beam_path = beam_paths.get(pid)
        panel_path = panel_paths.get(pid)
        if not beam_path or not panel_path:
            continue
        mat = placement_matrix(place)
        mat_flat = ", ".join(
            "[" + ", ".join(f"{v:.6g}" for v in row) + "]" for row in mat
        )
        assembled_lines.append(f"multmatrix([{mat_flat}]) {{")
        assembled_lines.append(f"  beam_geom_{pid}();")
        assembled_lines.append(f"  panel_geom_{pid}();")
        assembled_lines.append("}")
    assembled_text = "\n".join(assembled_lines)
    assembled_path = out_dir / f"{context.basename}_assembled.scad"
    assembled_path.write_text(assembled_text, encoding="utf-8")
    logs.append(f"SCAD written to {assembled_path}")

    # Manifest (Beam + Panel placements)
    manifest = []
    for place in plan.assembled:
        pid = place.panel.panel_id
        beam_path = beam_paths.get(pid)
        panel_path = panel_paths.get(pid)
        if not beam_path or not panel_path:
            continue
        mat = placement_matrix(place)
        manifest.append(
            {
                "panel_id": pid,
                "beam_scad": str(beam_path),
                "panel_scad": str(panel_path),
                "matrix": mat,
            }
        )
    manifest_path = out_dir / f"{context.basename}_placements.json"
    import json

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logs.append(f"Manifest written to {manifest_path}")

    png_enabled, png_args = build_png_args(context.export.get("png"))
    if png_enabled:
        png_targets = []
        png_targets.append((assembled_path, out_dir / f"{context.basename}_assembled.png"))
        for pid, bpath in beam_paths.items():
            png_targets.append((bpath, out_dir / f"{pid}_beam.png"))
        for pid, ppath in panel_paths.items():
            png_targets.append((ppath, out_dir / f"{pid}_panel.png"))

        # Ensure assembled (and others) get high resolution unless overridden by env/PNG cfg
        assembled_args = ["--viewall", "--imgsize", "2400,1800"]
        def render_png(src_dst):
            src, dst = src_dst
            args = assembled_args if dst.name.startswith(f"{context.basename}_assembled") else png_args
            run_openscad(src, dst, context.openscad_bin, args)
            return dst

        max_workers = max(1, int(os.getenv("OSCADFORGE_WORKERS", os.cpu_count() or 4)))
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(render_png, pair): pair for pair in png_targets}
            for fut in as_completed(futures):
                src, dst = futures[fut]
                try:
                    out = fut.result()
                except Exception:
                    continue
                png_paths.append(out)
                logs.append(f"PNG written to {out}")

    metadata = {
        "panel_count": len(panels),
        "sheets": sheet_map,
        "variant": base.board_variant,
        "manifest": str(manifest_path),
    }
    return EngineResult(
        scad_path=assembled_path,
        stl_paths=[],
        step_paths=[],
        png_paths=png_paths,
        logs=logs,
        metadata=metadata,
    )
