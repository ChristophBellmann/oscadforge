from __future__ import annotations

import argparse
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

from ..core.export import ExportError, convert_stl_to_step_with_freecad


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m oscadforge.tools.stl2step",
        description="Convert every STL under a directory (recursively) into STEP using FreeCAD.",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Directories or STL files to convert (directories are scanned recursively).",
    )
    parser.add_argument(
        "--freecad-bin",
        default=shutil.which("freecadcmd"),
        help="Path to the FreeCAD command-line binary (default: first freecadcmd on PATH).",
    )
    parser.add_argument(
        "--freecad-mesh-tolerance",
        type=float,
        default=0.12,
        help="Tolerance passed to the FreeCAD mesh-to-STEP conversion (default: 0.12 mm).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count() or 4,
        help="Maximum number of parallel conversions (default: CPU count).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing STEP files instead of skipping them.",
    )
    return parser


def discover_stl_files(entries: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()

    for entry in entries:
        path = Path(entry).resolve()
        if path.is_file() and path.suffix.lower() == ".stl":
            if path not in seen:
                files.append(path)
                seen.add(path)
            continue
        if path.is_dir():
            for stl in path.rglob("*.stl"):
                stl_resolved = stl.resolve()
                if stl_resolved not in seen:
                    files.append(stl_resolved)
                    seen.add(stl_resolved)
        else:
            print(f"warning: {path} is neither an STL file nor a directory; skipping")
    return files


def convert_one(
    stl_path: Path,
    *,
    freecad_bin: str,
    tolerance: float,
    force: bool,
) -> tuple[Path, bool, str | None]:
    step_path = stl_path.with_suffix(".step")
    if step_path.exists() and not force:
        return stl_path, False, "exists"
    try:
        convert_stl_to_step_with_freecad(stl_path, step_path, freecad_bin, tolerance)
    except ExportError as exc:
        return stl_path, False, str(exc)
    return stl_path, True, None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.freecad_bin:
        parser.error("FreeCAD binary not found; pass --freecad-bin explicitly.")

    stl_files = discover_stl_files(args.paths)
    if not stl_files:
        print("No STL files found.")
        return 0

    print(f"Converting {len(stl_files)} STL files with {args.workers} workers...")
    converted = 0
    skipped = 0
    failures: list[tuple[Path, str]] = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                convert_one,
                path,
                freecad_bin=args.freecad_bin,
                tolerance=args.freecad_mesh_tolerance,
                force=args.force,
            ): path
            for path in stl_files
        }
        for future in as_completed(futures):
            stl_path, success, info = future.result()
            if success:
                converted += 1
                print(f"[ok] {stl_path.with_suffix('.step')}")
            else:
                if info == "exists":
                    skipped += 1
                else:
                    failures.append((stl_path, info or "unknown error"))
                    print(f"[fail] {stl_path}: {info}")

    print(
        f"Done. converted={converted} skipped={skipped} failures={len(failures)}",
    )
    if failures:
        print("Failures:")
        for path, message in failures:
            print(f"  - {path}: {message}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
