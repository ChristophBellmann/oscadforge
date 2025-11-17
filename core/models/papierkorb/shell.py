from __future__ import annotations

import anchorscad as ad

from .params import PapierkorbParams
from .render import centre_to_post


def _solid_box(corner: tuple[float, float, float], size: tuple[float, float, float], name: str) -> ad.Maker:
    cx = corner[0] + size[0] / 2.0
    cy = corner[1] + size[1] / 2.0
    cz = corner[2] + size[2] / 2.0
    return (
        ad.Box(size)
        .solid(name)
        .at(
            "centre",
            post=ad.translate([
                cx,
                cy,
                centre_to_post(size[2], cz),
            ]),
        )
    )


def build_simple_shell(params: PapierkorbParams) -> ad.Maker:
    L = params.length_mm
    B = params.width_mm
    H = params.height_mm
    wall = max(params.wall_mm, 0.1)
    rim_w = max(params.rim_width_mm, wall)
    rim_h = max(params.rim_height_mm, wall)
    bodies: list[ad.Maker] = []

    # Bottom
    bodies.append(
        _solid_box(( -L / 2.0, -B / 2.0, 0.0 ), (L, B, wall), "shell_bottom")
    )

    wall_height = H
    # Front wall (Y-)
    bodies.append(
        _solid_box(
            (-L / 2.0, -B / 2.0, 0.0),
            (L, wall, wall_height),
            "shell_wall_front",
        )
    )
    # Back wall (Y+)
    bodies.append(
        _solid_box(
            (-L / 2.0, B / 2.0 - wall, 0.0),
            (L, wall, wall_height),
            "shell_wall_back",
        )
    )
    # Left wall (X-)
    bodies.append(
        _solid_box(
            (-L / 2.0, -B / 2.0 + wall, 0.0),
            (wall, max(B - 2 * wall, wall), wall_height),
            "shell_wall_left",
        )
    )
    # Right wall (X+)
    bodies.append(
        _solid_box(
            (L / 2.0 - wall, -B / 2.0 + wall, 0.0),
            (wall, max(B - 2 * wall, wall), wall_height),
            "shell_wall_right",
        )
    )

    if params.enable_rim:
        rim_z = H - rim_h / 2.0
        bodies.append(
            _solid_box(
                (-L / 2.0, -B / 2.0, H - rim_h),
                (L, rim_w, rim_h),
                "shell_rim_front",
            )
        )
        bodies.append(
            _solid_box(
                (-L / 2.0, B / 2.0 - rim_w, H - rim_h),
                (L, rim_w, rim_h),
                "shell_rim_back",
            )
        )
        span_y = max(B - 2 * rim_w, rim_w)
        bodies.append(
            _solid_box(
                (-L / 2.0, -B / 2.0 + rim_w, H - rim_h),
                (rim_w, span_y, rim_h),
                "shell_rim_left",
            )
        )
        bodies.append(
            _solid_box(
                (L / 2.0 - rim_w, -B / 2.0 + rim_w, H - rim_h),
                (rim_w, span_y, rim_h),
                "shell_rim_right",
            )
        )

    maker: ad.Maker | None = None
    for body in bodies:
        if maker is None:
            maker = body
        else:
            maker.add(body)
    assert maker is not None
    return maker
