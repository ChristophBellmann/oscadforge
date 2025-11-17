from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

import anchorscad as ad

from .layout import PanelPlacement
from .panels import AxisDirection, Panel, PanelFeature, Vec3

EPS = 1.0e-3


def centre_to_post(size_z: float, centre_z: float) -> float:
    """
    Convert a world-space centre coordinate into the "post" translation that
    AnchorSCAD expects. Its renderer adds the primitive's half-height along Z,
    so supplying ``-centre_z`` yields a final SCAD translation of
    ``centre_z - size_z / 2`` (i.e. the minimum corner touches Z=0).
    """
    return -centre_z


def build_maker(placements: Iterable[PanelPlacement], *, layout_label: str) -> ad.Maker:
    maker: ad.Maker | None = None

    def add_shape(shape_maker: ad.Maker) -> None:
        nonlocal maker
        if maker is None:
            maker = shape_maker
        else:
            maker.add(shape_maker)

    for placement in placements:
        panel_colour = placement.panel.colour
        for feature in placement.panel.features:
            name = _feature_name(feature, placement, layout_label)
            if feature.feature_type == "box":
                shape = _box_shape(placement, feature, name, panel_colour)
                add_shape(shape)
            else:
                shape = _cylinder_shape(placement, feature, name, panel_colour)
                add_shape(shape)
    assert maker is not None, "at least one panel feature required"
    return maker


def _feature_name(feature: PanelFeature, placement: PanelPlacement, layout_label: str) -> str:
    if layout_label == "assembled":
        return feature.label
    return f"{feature.label}_{layout_label}"


def _box_shape(
    placement: PanelPlacement,
    feature: PanelFeature,
    name: str,
    colour: ad.Colour | None,
) -> ad.Maker:
    size_x, size_y, size_z = _box_sizes_world(placement, feature)
    offset = _offset_world(placement, feature)
    centre = placement.origin + offset
    post = ad.translate([centre.x, centre.y, centre_to_post(size_z, centre.z)])
    shape = ad.Box((size_x, size_y, size_z))
    named = shape.solid(name) if feature.role == "solid" else shape.hole(name)
    if colour is not None and feature.role == "solid":
        named = named.colour(colour)
    return named.at("centre", post=post)


def _cylinder_shape(
    placement: PanelPlacement,
    feature: PanelFeature,
    name: str,
    colour: ad.Colour | None,
) -> ad.Maker:
    axis_dir = placement.axes.axis_for(feature.axis)
    rotation = _rotation_to_axis(axis_dir)
    offset = _offset_world(placement, feature)
    centre = placement.origin + offset
    size_z = _cylinder_extent_z(axis_dir, feature)
    post = ad.translate([centre.x, centre.y, centre_to_post(size_z, centre.z)])
    if rotation is not None:
        post = rotation * post
    shape = ad.Cylinder(feature.radius, feature.height)
    named = shape.solid(name) if feature.role == "solid" else shape.hole(name)
    if colour is not None and feature.role == "solid":
        named = named.colour(colour)
    return named.at("centre", post=post)


def _box_sizes_world(placement: PanelPlacement, feature: PanelFeature) -> Tuple[float, float, float]:
    axes = placement.axes
    size_map = {
        axes.u.axis: feature.size_u,
        axes.v.axis: feature.size_v,
        axes.w.axis: feature.size_w,
    }
    return (size_map.get("x", 0.0), size_map.get("y", 0.0), size_map.get("z", 0.0))


def _offset_world(placement: PanelPlacement, feature: PanelFeature) -> Vec3:
    u_vec = placement.axes.u.vector()
    v_vec = placement.axes.v.vector()
    w_vec = placement.axes.w.vector()
    return Vec3(
        feature.offset_u * u_vec.x + feature.offset_v * v_vec.x + feature.offset_w * w_vec.x,
        feature.offset_u * u_vec.y + feature.offset_v * v_vec.y + feature.offset_w * w_vec.y,
        feature.offset_u * u_vec.z + feature.offset_v * v_vec.z + feature.offset_w * w_vec.z,
    )


def _rotation_to_axis(axis: AxisDirection) -> ad.GMatrix | None:
    mapping = {
        ("x", 1): ad.ROTY_90,
        ("x", -1): ad.ROTY_270,
        ("y", 1): ad.ROTX_270,
        ("y", -1): ad.ROTX_90,
        ("z", 1): None,
        ("z", -1): ad.ROTX_180,
    }
    return mapping[(axis.axis, axis.sign)]


def _cylinder_extent_z(axis: AxisDirection, feature: PanelFeature) -> float:
    if axis.axis == "z":
        return feature.height
    return feature.radius * 2.0 + EPS
