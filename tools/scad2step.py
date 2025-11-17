from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from ..core.export import ExportError, export_step_artifact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m oscadforge.tools.scad2step",
        description="Convert an existing SCAD file into STEP using the oscadforge exporters.",
    )
    parser.add_argument("scad", type=Path, help="Path to the input .scad file.")
    parser.add_argument("step", type=Path, help="Destination .step file.")
    parser.add_argument(
        "--backend",
        default="freecad_csg",
        choices=["freecad_csg", "freecad", "freecad_stl", "openscad"],
        help="Exporter backend to use (default: freecad_csg).",
    )
    parser.add_argument(
        "--openscad-bin",
        default=shutil.which("openscad"),
        help="Path to the OpenSCAD binary (default: first openscad on PATH).",
    )
    parser.add_argument(
        "--freecad-bin",
        default=shutil.which("freecadcmd"),
        help="Path to the FreeCAD command-line binary (default: first freecadcmd on PATH).",
    )
    parser.add_argument(
        "--freecad-mesh-tolerance",
        type=float,
        default=None,
        help="Tolerance passed to the FreeCAD mesh-to-STEP conversion (freecad backend only).",
    )
    parser.add_argument(
        "--stl",
        type=Path,
        default=None,
        help="Optional existing STL file to reuse when step_backend uses FreeCAD STL.",
    )
    parser.add_argument(
        "--dedup-cache",
        type=Path,
        default=None,
        help="Enable STEP deduplication by pointing to a cache directory.",
    )
    parser.add_argument(
        "--dedup-link",
        default="symlink",
        choices=["symlink", "hardlink", "copy"],
        help="How to link cache hits back to the requested STEP path (default: symlink).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    scad_path = args.scad.expanduser().resolve()
    step_path = args.step.expanduser().resolve()

    if not scad_path.exists():
        parser.error(f"SCAD file not found: {scad_path}")

    export_cfg: dict[str, object] = {"step_backend": args.backend}
    if args.freecad_mesh_tolerance is not None:
        export_cfg["freecad_mesh_tolerance"] = args.freecad_mesh_tolerance
    if args.dedup_cache:
        export_cfg["step_dedup"] = {
            "enabled": True,
            "cache_dir": str(args.dedup_cache.expanduser()),
            "link": args.dedup_link,
        }

    stl_path = args.stl.expanduser().resolve() if args.stl else None

    try:
        result = export_step_artifact(
            scad_path,
            step_path,
            export_cfg=export_cfg,
            openscad_bin=args.openscad_bin,
            freecad_bin=args.freecad_bin,
            stl_path=stl_path,
        )
    except ExportError as exc:
        parser.exit(status=2, message=f"scad2step failed: {exc}\n")

    if result.dedup_hit:
        print(f"STEP reused from cache {result.cache_path} -> {result.step_path}")
    else:
        print(f"STEP written to {result.step_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
