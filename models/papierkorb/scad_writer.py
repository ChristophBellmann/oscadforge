from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from .layout import PanelPlacement
from .panels import Panel, PanelFeature, PanelGrid, PanelKind, PanelBuildResult
from .params import PapierkorbParams

EPS = 0.01


@dataclass
class PanelModule:
    panel: Panel
    core_module: str
    geom_module: str


def build_scad_for_artifact(
    *,
    params: PapierkorbParams,
    panel_result: PanelBuildResult,
    artifact_label: str,
    placements: Iterable[PanelPlacement],
    jl_scad_path: str,
) -> str:
    header = _scad_header(jl_scad_path)
    shell_module = _shell_module(params)
    panel_modules = _panel_modules(panel_result, params)
    placement_block = _artifact_union(artifact_label, placements, panel_result)
    body = f"""
{header}

{shell_module}

{panel_modules}

{placement_block}

artifact_{artifact_label}();
"""
    return body


def build_scad_for_panel(
    *,
    params: PapierkorbParams,
    panel: Panel,
    jl_scad_path: str,
) -> str:
    header = _scad_header(jl_scad_path)
    shell_module = _shell_module(params)
    panel_module = _panel_module(panel, params)
    return (
        f"{header}\n\n{shell_module}\n\n{panel_module}\n\npanel_geom_{panel.panel_id}();\n"
    )


def _scad_header(jl_scad_path: str) -> str:
    return f"""// Generated via oscadforge Papierkorb jl_scad backend
include <{jl_scad_path}/box.scad>;
include <{jl_scad_path}/parts.scad>;
"""


def _shell_module(params: PapierkorbParams) -> str:
    rim_height = params.rim_height_mm if params.enable_rim else 0.0
    rim_wall = params.rim_width_mm if params.enable_rim else params.wall_mm / 2.0
    shell = f"""
module papierkorb_shell_master() {{
    open_round_box(
        size=[{params.length_mm:.4f}, {params.width_mm:.4f}, {params.height_mm:.4f}],
        wall_side={params.wall_mm:.4f},
        wall_bot={params.wall_mm:.4f},
        rim_height={rim_height:.4f},
        rim_wall={rim_wall:.4f},
        rim_inside=false,
        rsides=0,
        rbot=0
    );
}}
"""
    return shell


def _panel_modules(panel_result: PanelBuildResult, params: PapierkorbParams) -> str:
    modules: List[str] = []
    for panel in panel_result.panels:
        modules.append(_panel_module(panel, params))
    return "\n".join(modules)


def _panel_module(panel: Panel, params: PapierkorbParams) -> str:
    core = _panel_core_module(panel)
    solids: List[str] = []
    holes: List[str] = []
    features = panel.features[1:] if panel.features else []
    for feat in features:
        snippet = _feature_to_scad(panel, feat)
        if not snippet:
            continue
        if feat.role == "solid":
            solids.append(snippet)
        else:
            holes.append(snippet)
    geom_lines: List[str] = []
    geom_lines.append(core)
    geom_lines.append(f"module panel_geom_{panel.panel_id}() {{")
    geom_lines.append("  difference() {")
    geom_lines.append("    union() {")
    geom_lines.append(f"      panel_core_{panel.panel_id}();")
    for solid in solids:
        geom_lines.append(_indent(solid, 6))
    geom_lines.append("    }")
    if holes:
        geom_lines.append("    union() {")
        for hole in holes:
            geom_lines.append(_indent(hole, 6))
        geom_lines.append("    }")
    geom_lines.append("  }")
    geom_lines.append("}")
    return "\n".join(geom_lines)


def _panel_core_module(panel: Panel) -> str:
    x0, x1, y0, y1, z0, z1 = panel.bounds
    x0 -= EPS
    y0 -= EPS
    z0 -= EPS
    x1 += EPS
    y1 += EPS
    z1 += EPS
    size_x = x1 - x0
    size_y = y1 - y0
    size_z = z1 - z0
    lines = [
        f"module panel_core_{panel.panel_id}() {{",
        "  intersection() {",
        "    papierkorb_shell_master();",
        f"    translate([{x0:.4f}, {y0:.4f}, {z0:.4f}]) cube([{size_x:.4f}, {size_y:.4f}, {size_z:.4f}], center=false);",
        "  }",
        "}",
    ]
    return "\n".join(lines)


def _feature_to_scad(panel: Panel, feature: PanelFeature) -> str:
    matrix = _panel_matrix(panel)
    matrix_str = _format_matrix(matrix)
    offset = f"[{feature.offset_u:.4f}, {feature.offset_v:.4f}, {feature.offset_w:.4f}]"
    if feature.feature_type == "box":
        shape = f"cube([{feature.size_u:.4f}, {feature.size_v:.4f}, {feature.size_w:.4f}], center=true);"
    elif feature.feature_type == "cylinder":
        shape = _cylinder_shape(feature)
    else:
        return ""
    return f"    multmatrix({matrix_str}) translate({offset}) {shape}"


def _cylinder_shape(feature: PanelFeature) -> str:
    rotations = {
        "u": "rotate([0,90,0]) ",
        "v": "rotate([90,0,0]) ",
        "w": "",
    }
    prefix = rotations.get(feature.axis, "")
    return f"{prefix}cylinder(h={feature.height:.4f}, r={feature.radius:.4f}, center=true);"


def _artifact_union(
    artifact_label: str,
    placements: Iterable[PanelPlacement],
    panel_result: PanelBuildResult,
) -> str:
    base_mats = {panel.panel_id: _panel_matrix(panel) for panel in panel_result.panels}
    lines = [f"module artifact_{artifact_label}() {{", "  union() {"]
    for placement in placements:
        panel = placement.panel
        transform = _placement_transform(placement, base_mats[panel.panel_id])
        call = f"panel_geom_{panel.panel_id}();"
        colour_prefix = _colour_prefix(panel.colour)
        statement = call
        if transform:
            statement = f"multmatrix({transform}) {statement}"
        if colour_prefix:
            statement = f"{colour_prefix} {statement}"
        lines.append(f"    {statement}")
    lines.append("  }")
    lines.append("}")
    return "\n".join(lines)


def _colour_prefix(colour) -> str | None:
    if colour is None:
        return None
    r, g, b, a = (max(0.0, min(1.0, c)) for c in colour.value)
    return f"color([{r:.4f}, {g:.4f}, {b:.4f}, {a:.4f}])"


def _panel_matrix(panel: Panel) -> List[List[float]]:
    return _placement_matrix(panel.origin, panel.axes.u.vector(), panel.axes.v.vector(), panel.axes.w.vector())


def _placement_matrix(origin, u_vec, v_vec, w_vec) -> List[List[float]]:
    return [
        [u_vec.x, v_vec.x, w_vec.x, origin.x],
        [u_vec.y, v_vec.y, w_vec.y, origin.y],
        [u_vec.z, v_vec.z, w_vec.z, origin.z],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _format_matrix(matrix: Sequence[Sequence[float]]) -> str:
    rows = []
    for row in matrix:
        rows.append("[{}]".format(", ".join(f"{value:.6f}" for value in row)))
    return "[{}]".format(", ".join(rows))


    width_vec = vec(feature.axis_width, feature.sign_width)
    slide_vec = vec(feature.axis_slide, feature.sign_slide)
    height_vec = vec(feature.axis_height, feature.sign_height)
    return [
        [width_vec[0], slide_vec[0], height_vec[0], feature.offset_u],
        [width_vec[1], slide_vec[1], height_vec[1], feature.offset_v],
        [width_vec[2], slide_vec[2], height_vec[2], feature.offset_w],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _placement_transform(placement: PanelPlacement, base_matrix: List[List[float]]) -> str | None:
    target_matrix = _placement_matrix(
        placement.origin,
        placement.axes.u.vector(),
        placement.axes.v.vector(),
        placement.axes.w.vector(),
    )
    transform = _matrix_multiply(target_matrix, _matrix_inverse(base_matrix))
    if _is_identity(transform):
        return None
    return _format_matrix(transform)


def placement_transform_matrix(placement: PanelPlacement, panel: Panel) -> List[List[float]]:
    base_matrix = _panel_matrix(panel)
    target_matrix = _placement_matrix(
        placement.origin,
        placement.axes.u.vector(),
        placement.axes.v.vector(),
        placement.axes.w.vector(),
    )
    return _matrix_multiply(target_matrix, _matrix_inverse(base_matrix))


def _matrix_inverse(mat: List[List[float]]) -> List[List[float]]:
    rot = [[mat[r][c] for c in range(3)] for r in range(3)]
    trans = [mat[r][3] for r in range(3)]
    rot_t = [[rot[c][r] for c in range(3)] for r in range(3)]
    new_trans = [-sum(rot_t[r][c] * trans[c] for c in range(3)) for r in range(3)]
    inv = []
    for r in range(3):
        inv.append(rot_t[r] + [new_trans[r]])
    inv.append([0.0, 0.0, 0.0, 1.0])
    return inv


def _matrix_multiply(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    result = [[0.0 for _ in range(4)] for _ in range(4)]
    for i in range(4):
        for j in range(4):
            result[i][j] = sum(a[i][k] * b[k][j] for k in range(4))
    return result


def _is_identity(matrix: List[List[float]], tol: float = 1e-6) -> bool:
    for r in range(4):
        for c in range(4):
            expected = 1.0 if r == c else 0.0
            if abs(matrix[r][c] - expected) > tol:
                return False
    return True


def _indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else "" for line in text.splitlines())
