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
