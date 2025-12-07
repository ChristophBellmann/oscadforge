from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple


@dataclass
class PapierkorbParams:
    length_mm: float = 514.0
    width_mm: float = 170.0
    height_mm: float = 605.0
    wall_mm: float = 3.6
    max_tile_mm: float = 200.0
    enable_tiles: bool = True
    enable_rim: bool = True
    rim_height_mm: float = 20.0
    rim_width_mm: float = 2.5
    enable_honeycomb: bool = True
    honeycomb_pitch_mm: float = 35.0
    honeycomb_radius_mm: float = 8.0
    honeycomb_margin_mm: float = 25.0
    enable_opengrid: bool = False
    opengrid_cell_mm: float = 24.0
    opengrid_bar_mm: float = 3.2
    opengrid_margin_mm: float = 12.0
    simple_shell: bool = False
    flange_depth_mm: float = 10.0

    def tile_counts(self) -> Tuple[int, int, int]:
        """Return tile count along X/Y/Z axes (Nx, Ny, Nz)."""
        Nx = max(1, int((self.length_mm + self.max_tile_mm - 1) // self.max_tile_mm))
        Ny = max(1, int((self.width_mm + self.max_tile_mm - 1) // self.max_tile_mm))
        Nz = max(1, int((self.height_mm + self.max_tile_mm - 1) // self.max_tile_mm))
        if not self.enable_tiles:
            Nx = 1
            Ny = 1
        return Nx, Ny, Nz

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "PapierkorbParams":
        kwargs = {}
        for field in cls.__dataclass_fields__:  # type: ignore[attr-defined]
            if field in data:
                kwargs[field] = data[field]
        return cls(**kwargs)

    @classmethod
    def from_model_config(cls, data: Mapping[str, object]) -> "PapierkorbParams":
        flattened: dict[str, object] = {}
        # Support legacy `bin` block (length, width, height, wall_thickness)
        bin_cfg = data.get("bin")
        if isinstance(bin_cfg, Mapping):
            if "length_mm" in bin_cfg:
                flattened.setdefault("length_mm", bin_cfg["length_mm"])
            if "width_mm" in bin_cfg:
                flattened.setdefault("width_mm", bin_cfg["width_mm"])
            if "height_mm" in bin_cfg:
                flattened.setdefault("height_mm", bin_cfg["height_mm"])
            if "wall_thickness_mm" in bin_cfg:
                flattened.setdefault("wall_mm", bin_cfg["wall_thickness_mm"])
            if "max_tile_mm" in bin_cfg:
                flattened.setdefault("max_tile_mm", bin_cfg["max_tile_mm"])
        # Copy recognized top-level fields directly
        for field_name in cls.__dataclass_fields__:
            if field_name in data and field_name not in flattened:
                flattened[field_name] = data[field_name]
        return cls.from_mapping(flattened)
