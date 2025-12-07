from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ...core.engine import BuildContext, EngineResult
from ...core.export import ExportError, build_png_args, run_openscad
from ..papierkorb.params import PapierkorbParams
from ..papierkorb.panels import Panel, PanelGrid, PanelKind, build_panels
from . import BeamJointParams, _render_scad

REPO_ROOT = next(p for p in Path(__file__).resolve().parents if p.name == "oscadforge").parent


def _cells(value: float, tile: float) -> int:
    return max(1, round(value / tile))


def _edge_flags(panel: Panel, grid: PanelGrid) -> Tuple[bool, bool, bool, bool]:
    Nx, Ny, Nz = grid.Nx, grid.Ny, grid.Nz

    if panel.kind is PanelKind.FLOOR:
        ix, iy, _ = panel.indices
        bottom = iy == 0
        top = iy == Ny - 1
        left = ix == 0
        right = ix == Nx - 1
    elif panel.kind in (PanelKind.WALL_POS_Y, PanelKind.WALL_NEG_Y):
        ix, _, iz = panel.indices
        bottom = iz == 0
        top = iz == Nz - 1
        left = ix == 0
        right = ix == Nx - 1
    elif panel.kind in (PanelKind.WALL_POS_X, PanelKind.WALL_NEG_X):
        _, iy, iz = panel.indices
        bottom = iz == 0
        top = iz == Nz - 1
        left = iy == 0
        right = iy == Ny - 1
    else:
        bottom = top = left = right = False
    return bottom, right, left, top


def _beam_params_for_panel(panel, params: BeamJointParams, grid: PanelGrid) -> BeamJointParams:
    tile = params.tile_size_mm
    bw = _cells(panel.width, tile)
    bh = _cells(panel.height, tile)
    bottom, right, left, top = _edge_flags(panel, grid)
    # Edge-aware flags: only outer edges get beams/joints/connectors
    board_conn = bottom or right or left or top

    layer_bottom = panel.kind is PanelKind.FLOOR
    layer_top = (
        panel.kind in (PanelKind.WALL_POS_Y, PanelKind.WALL_NEG_Y, PanelKind.WALL_POS_X, PanelKind.WALL_NEG_X)
        and panel.indices[2] == grid.Nz - 1
    )

    chamfer_edge = layer_top  # chamfer only the top rim

    # Corner joints: only the four bottom corners of the floor
    corner_bl = bottom and left and layer_bottom
    corner_br = bottom and right and layer_bottom
    corner_tl = top and left and layer_bottom
    corner_tr = top and right and layer_bottom

    return replace(
        params,
        board_width=bw,
        board_height=bh,
        beam_bottom=bottom,
        beam_top=top,
        beam_left=left,
        beam_right=right,
        boardconnector_cutouts=False,  # keep tile faces out of beams
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

def _z_overhang(panel: Panel, params: BeamJointParams, grid: PanelGrid) -> float:
    """Return extra height above tile_thickness contributed by beams/joints/chamfer."""
    variant = params.board_variant.lower()
    has_joints = (panel.kind is PanelKind.FLOOR)
    top_layer = (
        panel.kind in (PanelKind.WALL_POS_Y, PanelKind.WALL_NEG_Y, PanelKind.WALL_POS_X, PanelKind.WALL_NEG_X)
        and panel.indices[2] == grid.Nz - 1
    )
    has_chamfer = top_layer

    # measured extras (mm) relative to tile thickness
    if variant == "lite":
        if has_chamfer:
            return 9.25
        if has_joints:
            return 13.5
        return 5.1
    if variant == "heavy":
        if has_chamfer:
            return 11.2
        if has_joints:
            return 13.5
        return 5.1
    # default full
    if has_chamfer:
        return 9.25
    if has_joints:
        return 13.5
    return 5.1


def _write_panel_beam(panel, params: BeamJointParams, grid: PanelGrid, out_dir: Path, openscad_bin: str | None, png_cfg) -> Tuple[Path, Path | None]:
    panel_params = _beam_params_for_panel(panel, params, grid)
    z_shift = _z_overhang(panel, panel_params, grid)
    bosl = (REPO_ROOT / "third_party" / "BOSL2" / "std.scad").resolve()
    og = (REPO_ROOT / "third_party" / "QuackWorks" / "openGrid" / "openGrid.scad").resolve()
    prelude = (
        f'include <{bosl.as_posix()}>;\n'
        f'use <{og.as_posix()}>;\n'
        f'$tags_shown = \"ALL\";\n'
        f'$tags_hidden = [];\n'
        f'$tags = [];\n'
        f'$tag = \"\";\n'
    )
    scad_body = _render_scad(panel_params, call_scene=False)
    scad_text = f"{prelude}\n{scad_body}\ntranslate([0,0,-{z_shift}]) scene(Board_Width=Board_Width, Board_Height=Board_Height);\n"
    scad_path = out_dir / f"{panel.panel_id}_beam.scad"
    scad_path.write_text(scad_text, encoding="utf-8")

    png_enabled, png_args = build_png_args(png_cfg)
    png_path: Path | None = None
    if png_enabled:
        png_path = out_dir / f"{panel.panel_id}_beam.png"
        try:
            run_openscad(scad_path, png_path, openscad_bin, png_args)
        except ExportError:
            png_path = None
    return scad_path, png_path


def build(context: BuildContext) -> EngineResult:
    papierkorb_params = PapierkorbParams.from_model_config(context.model_params)
    panel_result = build_panels(papierkorb_params)
    grid = panel_result.grid

    board_cfg = context.model_params.get("board", {})
    base = BeamJointParams.from_mapping(context.model_params)
    base.board_variant = str(board_cfg.get("variant", base.board_variant))
    base.tile_size_mm = board_cfg.get("tile_size_mm", base.tile_size_mm)
    base.tile_thickness_mm = board_cfg.get("thickness_mm", board_cfg.get("tile_thickness_mm", base.tile_thickness_mm))
    base.board_width = base.board_height = 1  # overwritten per panel

    out_dir = context.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    scad_paths: List[Path] = []
    png_paths: List[Path] = []
    logs: List[str] = []

    max_workers = max(1, int(os.getenv("OSCADFORGE_WORKERS", os.cpu_count() or 4)))

    panels = panel_result.panels

    def _task(panel):
        scad_path, png_path = _write_panel_beam(
            panel=panel,
            params=base,
            grid=grid,
            out_dir=out_dir,
            openscad_bin=context.openscad_bin,
            png_cfg=context.export.get("png"),
        )
        return panel.panel_id, scad_path, png_path

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_task, panel): panel for panel in panels}
        for fut in as_completed(futures):
            panel = futures[fut]
            try:
                panel_id, scad_path, png_path = fut.result()
            except Exception as exc:  # surface first failure
                raise RuntimeError(f"beam build failed for panel {panel.panel_id}") from exc
            scad_paths.append(scad_path)
            logs.append(f"SCAD written to {scad_path}")
            if png_path:
                png_paths.append(png_path)
                logs.append(f"PNG written to {png_path}")

    metadata: Dict[str, Any] = {
        "panel_count": len(panels),
        "tile_size_mm": base.tile_size_mm,
    }

    return EngineResult(
        scad_path=None,
        stl_paths=[],
        step_paths=[],
        png_paths=png_paths,
        logs=logs,
        metadata=metadata,
    )
