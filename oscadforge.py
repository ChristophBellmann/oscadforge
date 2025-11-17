from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, NamedTuple, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_DIR = REPO_ROOT / "oscadforge" / "config"
DEFAULT_TEMPLATE_DIR = REPO_ROOT / "oscadforge" / "templates"

STDIN_SOURCE = "<stdin>"
MERGED_SOURCE = "<merged>"


class ConfigNote(NamedTuple):
    source: str
    description: str

if __package__ is None or __package__ == "":  # script mode
    sys.path.insert(0, str(REPO_ROOT))
    from oscadforge.core import engine, io  # type: ignore  # noqa: E402
    from oscadforge.projects.loader import TemplateError, load_template  # type: ignore  # noqa: E402
else:
    from .core import engine, io  # type: ignore  # noqa: F401
    from .projects.loader import TemplateError, load_template  # type: ignore  # noqa: F401


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="oscadforge",
        description="Terminal → Engine → Files workflow helper.",
    )
    parser.add_argument(
        "configs",
        nargs="*",
        help="YAML config files to merge (order matters; later files override earlier ones)",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List available engine models and project scripts.",
    )
    parser.add_argument(
        "--openscad-bin",
        help="Override export.openscad_bin (e.g. openscad or /usr/local/bin/openscad-snapshot)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and print the merged config without running the engine.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write rendered artifact (.scad/.stl/.png) to PATH (Pandoc-style).",
    )
    parser.add_argument(
        "--result-json",
        help="Write engine result metadata as JSON (use '-' for stdout).",
    )
    parser.add_argument(
        "-t",
        "--template",
        help="Python template (file or module) that converts YAML/JSON data into an engine config.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.list:
        _print_available_projects()
        return 0

    if args.dry_run and args.output:
        print("error: --dry-run cannot be combined with -o/--output", file=sys.stderr)
        return 1

    collected = _collect_config_dicts(args, require_input=not args.template)
    if collected is None:
        return 1
    config_dicts, config_notes = collected

    if args.template:
        try:
            template = load_template(args.template)
        except TemplateError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        data_payload = io.merge_dicts(config_dicts) if config_dicts else {}
        merged = _apply_template(template, data_payload)
    else:
        merged = io.merge_dicts(config_dicts)
    if args.openscad_bin:
        merged.setdefault("export", {})["openscad_bin"] = args.openscad_bin

    final_description = _extract_meta_description(merged)
    notes_for_output = list(config_notes)
    if final_description:
        notes_for_output.append(ConfigNote(MERGED_SOURCE, final_description))

    if args.dry_run:
        print(json.dumps(merged, indent=2, sort_keys=True))
        return 0

    temp_ctx = tempfile.TemporaryDirectory() if args.output else None
    if temp_ctx:
        merged = _prepare_for_artifact(merged, Path(temp_ctx.name), Path(args.output))

    energy_start = _read_total_energy_uj()
    start_time = time.perf_counter()
    try:
        result = engine.build_model(merged)
    except Exception:
        if temp_ctx:
            temp_ctx.cleanup()
        raise
    duration = time.perf_counter() - start_time
    energy_end = _read_total_energy_uj()
    energy_delta = None
    if energy_start is not None and energy_end is not None:
        energy_delta = max(0, energy_end - energy_start)
    stats = {
        "duration_seconds": duration,
        "energy_microjoules": energy_delta,
    }
    result.metadata["stats"] = stats

    if final_description:
        result.metadata.setdefault("description", final_description)
    if notes_for_output:
        result.metadata.setdefault(
            "config_descriptions",
            [{"source": note.source, "description": note.description} for note in notes_for_output],
        )

    if args.output:
        _emit_artifact(result, Path(args.output))
        if temp_ctx:
            temp_ctx.cleanup()

    wrote_json_stdout = False
    if args.result_json:
        wrote_json_stdout = _write_json_result(result, args.result_json)

    if not wrote_json_stdout:
        _print_config_descriptions(notes_for_output)
        _print_logs(result, stats)
    return 0


def _print_available_projects() -> None:
    print("Engine models registered in oscadforge:")
    for name in engine.available_models():
        print(f"  - {name}")

    print("\nPython templates under oscadforge/templates/:")
    templates_dir = REPO_ROOT / "oscadforge" / "templates"
    if not templates_dir.exists():
        print("  (none found)")
    else:
        template_files = sorted(templates_dir.glob("*.py"))
        if not template_files:
            print("  (none found)")
        else:
            for script in template_files:
                print(f"  - {script.relative_to(REPO_ROOT)}")

    print("\nModel YAML presets under oscadforge/templates/:")
    if not templates_dir.exists():
        print("  (none found)")
    else:
        yaml_files = sorted(list(templates_dir.glob("*.yaml")) + list(templates_dir.glob("*.yml")))
        if not yaml_files:
            print("  (none found)")
        else:
            for preset in yaml_files:
                print(f"  - {preset.relative_to(REPO_ROOT)}")


def _collect_config_dicts(
    args: argparse.Namespace, *, require_input: bool = True
) -> tuple[list[dict], list[ConfigNote]] | None:
    dicts: list[dict] = []
    notes: list[ConfigNote] = []
    stdin_used = False

    def _record_meta(source: str, cfg: Mapping[str, Any]) -> None:
        desc = _extract_meta_description(cfg)
        if desc:
            notes.append(ConfigNote(source, desc))

    def read_stdin() -> dict:
        text = sys.stdin.read()
        if not text.strip():
            raise SystemExit("error: stdin config is empty")
        data = io.load_yaml_string(text)
        _record_meta(STDIN_SOURCE, data)
        return data

    if args.configs:
        for entry in args.configs:
            if entry == "-":
                if stdin_used:
                    raise SystemExit("error: stdin specified multiple times")
                stdin_used = True
                dicts.append(read_stdin())
            else:
                cfg, resolved_path = _load_config_file(entry)
                dicts.append(cfg)
                _record_meta(str(resolved_path), cfg)
    else:
        if sys.stdin.isatty():
            if require_input:
                print("error: please provide config files, '-' for stdin, or use --list", file=sys.stderr)
                return None
            return [], []
        dicts.append(read_stdin())

    if not dicts and require_input:
        print("error: no configuration data supplied", file=sys.stderr)
        return None
    return dicts, notes


def _print_logs(result: engine.EngineResult, stats: dict | None = None) -> None:
    for line in result.logs:
        print(line)
    if result.scad_path:
        print(f"SCAD: {result.scad_path}")
    for stl in result.stl_paths:
        print(f"STL: {stl}")
    for step in result.step_paths:
        print(f"STEP: {step}")
    for png in result.png_paths:
        print(f"PNG: {png}")
    if stats:
        msg = f"Run duration: {stats['duration_seconds']:.2f}s"
        if stats.get("energy_microjoules") is not None:
            joules = stats["energy_microjoules"] / 1_000_000
            msg += f", energy Δ ≈ {joules:.3f} J"
        print(msg)


def _print_config_descriptions(notes: Sequence[ConfigNote]) -> None:
    visible = [note for note in notes if note.description]
    if not visible:
        return
    print("Config descriptions:")
    for note in visible:
        label = _format_source_label(note.source)
        print(f"  - {label}: {note.description}")


def _result_to_dict(result: engine.EngineResult) -> dict:
    return {
        "scad": str(result.scad_path) if result.scad_path else None,
        "stl": [str(p) for p in result.stl_paths],
        "step": [str(p) for p in result.step_paths],
        "png": [str(p) for p in result.png_paths],
        "logs": result.logs,
        "metadata": result.metadata,
    }


def _extract_meta_description(data: Mapping[str, Any]) -> str | None:
    meta = data.get("meta")
    if isinstance(meta, Mapping):
        desc = meta.get("description")
        if isinstance(desc, str):
            desc = desc.strip()
            if desc:
                return desc
    return None


def _format_source_label(source: str) -> str:
    if source == STDIN_SOURCE:
        return "stdin"
    if source == MERGED_SOURCE:
        return "merged config"
    try:
        path = Path(source)
        if path.is_absolute():
            try:
                return str(path.relative_to(REPO_ROOT))
            except ValueError:
                return str(path)
        return source
    except Exception:
        return source


def _apply_template(template, data: dict) -> dict:
    try:
        return template.build_config(data, root=REPO_ROOT)
    except TypeError:
        return template.build_config(data)


def _prepare_for_artifact(config: dict, temp_dir: Path, target_path: Path) -> dict:
    cfg = copy.deepcopy(config)
    export = copy.deepcopy(cfg.get("export", {}))
    export["output_dir"] = str(temp_dir)

    ext = target_path.suffix.lower()
    if ext == ".scad":
        export["scad"] = True
    elif ext == ".stl":
        export["stl"] = True
        export.setdefault("scad", True)
    elif ext == ".png":
        export["png"] = _ensure_png_options(export.get("png"))
        export["stl"] = True
        export["scad"] = True
    elif ext == ".step":
        export["step"] = True
        export.setdefault("scad", True)
    elif ext == ".step":
        export["step"] = True
        export.setdefault("scad", True)
    else:
        raise SystemExit(f"error: unsupported output extension '{ext}' (expected .scad/.stl/.png/.step)")

    cfg["export"] = export
    return cfg


def _ensure_png_options(current) -> dict:
    opts = {"enabled": True, "viewall": True, "imgsize": [800, 600]}
    if isinstance(current, dict):
        opts.update(current)
    return opts


def _emit_artifact(result: engine.EngineResult, target: Path) -> None:
    ext = target.suffix.lower()
    if ext == ".scad":
        source = result.scad_path
    elif ext == ".stl":
        source = result.stl_paths[0] if result.stl_paths else None
    elif ext == ".png":
        source = result.png_paths[0] if result.png_paths else None
    else:
        raise SystemExit(f"error: unsupported output extension '{ext}'")

    if not source or not Path(source).exists():
        raise SystemExit(f"error: expected artifact '{ext}' not produced by engine")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    print(f"Wrote {ext} artifact to {target}")


def _write_json_result(result: engine.EngineResult, dest: str) -> bool:
    data = json.dumps(_result_to_dict(result), indent=2)
    if dest == "-":
        print(data)
        return True
    out_path = Path(dest)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(data, encoding="utf-8")
    return False


def _load_config_file(entry: str) -> tuple[dict, Path]:
    path = Path(entry)
    search_tried = [path]
    if not path.exists():
        candidates = []
        for base in (DEFAULT_CONFIG_DIR, DEFAULT_TEMPLATE_DIR):
            if not base.exists():
                continue
            candidates.append(base / entry)
            if not entry.endswith(('.yaml', '.yml')):
                candidates.append(base / f"{entry}.yaml")
                candidates.append(base / f"{entry}.yml")
        for cand in candidates:
            if cand in search_tried:
                continue
            search_tried.append(cand)
            if cand.exists():
                path = cand
                break
        else:
            tried = ", ".join(str(p) for p in search_tried)
            raise SystemExit(f"error: config '{entry}' not found (searched: {tried})")
    return io.load_yaml(path), path


def _read_total_energy_uj() -> int | None:
    root = Path("/sys/class/powercap")
    if not root.exists():
        return None
    total = 0
    found = False
    for energy_file in root.rglob("energy_uj"):
        try:
            text = energy_file.read_text().strip()
            if not text:
                continue
            total += int(text)
            found = True
        except (OSError, ValueError):
            continue
    if not found:
        return None
    return total


if __name__ == "__main__":
    raise SystemExit(main())
