from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass
class BinDimensions:
    length_mm: float = 514.0
    width_mm: float = 170.0
    height_mm: float = 605.0
    wall_thickness_mm: float = 6.8  # OpenGrid "Full" default
    max_tile_mm: float = 200.0
    dimension_rounding: str = "nearest"  # nearest|ceil|floor

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "BinDimensions":
        kwargs = {}
        for field in ("length_mm", "width_mm", "height_mm", "wall_thickness_mm", "max_tile_mm", "dimension_rounding"):
            if field in data:
                kwargs[field] = data[field]
        return cls(**kwargs)


@dataclass
class BoardOptions:
    variant: str = "Full"  # Full, Lite, Heavy
    tile_size_mm: float = 28.0
    chamfers: str = "Corners"
    screw_mounting: str = "None"
    connector_holes: bool = True
    adhesive_base: bool = False

    @property
    def thickness_mm(self) -> float:
        key = self.variant.strip().lower()
        if key == "lite":
            return 4.0
        if key == "heavy":
            return 13.8
        return 6.8

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "BoardOptions":
        kwargs = {}
        for field in (
            "variant",
            "tile_size_mm",
            "chamfers",
            "screw_mounting",
            "connector_holes",
            "adhesive_base",
        ):
            if field in data:
                kwargs[field] = data[field]
        return cls(**kwargs)


@dataclass
class ConnectorOptions:
    snap_variant: str = "lite"  # lite/full/heavy connectors
    directional_snaps: bool = False
    include_floor_edges: bool = True
    generate_connectors: bool = True

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "ConnectorOptions":
        kwargs = {}
        for field in (
            "snap_variant",
            "directional_snaps",
            "include_floor_edges",
            "generate_connectors",
        ):
            if field in data:
                kwargs[field] = data[field]
        return cls(**kwargs)


@dataclass
class OpenGrid2Params:
    bin: BinDimensions
    board: BoardOptions
    connectors: ConnectorOptions

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "OpenGrid2Params":
        bin_section = data.get("bin", {})
        board_section = data.get("board", {})
        connectors_section = data.get("connectors", {})
        if not isinstance(bin_section, Mapping):
            bin_section = {}
        if not isinstance(board_section, Mapping):
            board_section = {}
        if not isinstance(connectors_section, Mapping):
            connectors_section = {}
        return cls(
            bin=BinDimensions.from_mapping(bin_section),
            board=BoardOptions.from_mapping(board_section),
            connectors=ConnectorOptions.from_mapping(connectors_section),
        )
