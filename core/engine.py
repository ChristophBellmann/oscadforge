from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from . import export as export_utils


@dataclass
class EngineResult:
    scad_path: Path | None = None
    stl_paths: list[Path] = field(default_factory=list)
    step_paths: list[Path] = field(default_factory=list)
    png_paths: list[Path] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BuildContext:
    raw_config: Mapping[str, Any]
    model: Mapping[str, Any]
    export: Mapping[str, Any]
    out_dir: Path
    basename: str
    openscad_bin: str | None
    freecad_bin: str | None

    @property
    def model_name(self) -> str:
        return self.model.get("name", "")

    @property
    def model_params(self) -> Mapping[str, Any]:
        return self.model.get("params", {})


def _ensure_registry():
    from .models import (
        opengrid_papierkorb,
        opengrid_beam_papierkorb,
        papierkorb,
        solar_bus,
    )

    return {
        "papierkorb_tiles": papierkorb.build,
        "solar_bus_roof": solar_bus.build,
        "opengrid_2": opengrid_papierkorb.build,
        "opengrid_papierkorb": opengrid_papierkorb.build,
        "opengrid-beam_papierkorb": opengrid_beam_papierkorb.build,
        "opengrid_beam_papierkorb": opengrid_beam_papierkorb.build,
    }


MODEL_REGISTRY = _ensure_registry()


def available_models() -> list[str]:
    """Return the sorted list of registered model names."""
    return sorted(MODEL_REGISTRY.keys())


def build_model(config: Mapping[str, Any]) -> EngineResult:
    model_cfg = config.get("model")
    if not isinstance(model_cfg, Mapping):
        raise ValueError("config.model must be provided")
    model_name = model_cfg.get("name")
    if not model_name:
        raise ValueError("config.model.name must be provided")

    if model_name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model '{model_name}'. Available: {', '.join(MODEL_REGISTRY)}")

    export_cfg = config.get("export", {})
    if not isinstance(export_cfg, Mapping):
        raise ValueError("config.export must be a mapping")

    out_dir = Path(export_cfg.get("output_dir", "out")).expanduser()
    export_utils.ensure_directory(out_dir)
    basename = export_cfg.get("basename", model_name)
    context = BuildContext(
        raw_config=config,
        model=model_cfg,
        export=export_cfg,
        out_dir=out_dir,
        basename=basename,
        openscad_bin=export_cfg.get("openscad_bin"),
        freecad_bin=export_cfg.get("freecad_bin"),
    )
    builder: Callable[[BuildContext], EngineResult] = MODEL_REGISTRY[model_name]
    result = builder(context)
    result.metadata.setdefault("model_name", model_name)
    result.metadata.setdefault("output_dir", str(out_dir))
    result.metadata.setdefault("basename", basename)
    return result
