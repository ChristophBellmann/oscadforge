from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import concurrent.futures
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence


class ExportError(RuntimeError):
    """Raised when OpenSCAD export fails."""


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_openscad(
    scad_path: Path,
    output_path: Path,
    openscad_bin: Optional[str],
    extra_args: Optional[Sequence[str]] = None,
) -> None:
    if not openscad_bin:
        raise ExportError("openscad binary not configured; set export.openscad_bin")
    cmd = [openscad_bin, "-o", str(output_path)]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(str(scad_path))
    env = os.environ.copy()
    env.setdefault("APPIMAGE_EXTRACT_AND_RUN", "1")
    repo_root = Path.cwd()
    third_party = repo_root / "third_party"
    if third_party.exists():
        existing = env.get("OPENSCADPATH")
        path_str = str(third_party)
        if existing:
            path_str = f"{path_str}:{existing}"
        env["OPENSCADPATH"] = path_str
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
    except FileNotFoundError as exc:
        raise ExportError(f"OpenSCAD binary not found: {openscad_bin}") from exc
    except subprocess.CalledProcessError as exc:
        raise ExportError(
            f"OpenSCAD failed with code {exc.returncode}: {exc.stderr}"
        ) from exc


@dataclass
class StepExportResult:
    step_path: Path
    cache_path: Path | None = None
    dedup_hit: bool = False
    dedup_hash: str | None = None


@dataclass
class StepExportTask:
    scad_path: Path
    step_path: Path
    export_cfg: Mapping[str, Any]
    openscad_bin: Optional[str]
    freecad_bin: Optional[str]
    stl_path: Path | None = None
    metadata: Mapping[str, Any] | None = None


@dataclass
class StepAssemblyPart:
    step_path: Path
    matrix: Sequence[Sequence[float]]


def export_step_artifact(
    scad_path: Path,
    step_path: Path,
    *,
    export_cfg: Mapping[str, Any],
    openscad_bin: Optional[str],
    freecad_bin: Optional[str],
    stl_path: Path | None = None,
) -> StepExportResult:
    scad_path = scad_path.resolve()
    step_path = step_path.resolve()
    backend_requested = str(export_cfg.get("step_backend", "openscad") or "openscad").lower()
    backend = _resolve_step_backend(backend_requested, scad_path, stl_path)
    allow_stl_fallback = backend_requested in {"freecad_auto", "auto"}
    dedup = StepDedupManager.from_config(
        export_cfg.get("step_dedup"),
        default_cache_dir=step_path.parent / ".step_cache",
    )

    csg_path: Path | None = None
    csg_generated = False

    def ensure_csg() -> Path:
        nonlocal csg_path, csg_generated
        if csg_path is None:
            csg_path = step_path.with_suffix(".step_source.csg")
            run_openscad(
                scad_path,
                csg_path,
                openscad_bin,
                ["--export-format", "csg"],
            )
            if not csg_path.exists():
                raise ExportError(
                    f"OpenSCAD did not produce CSG output at {csg_path}; "
                    "check the OpenSCAD logs (imports and surface primitives cannot be exported as CSG)."
                )
            csg_generated = True
        return csg_path

    conversion_target = step_path
    dedup_hash: str | None = None
    cache_step_path: Path | None = None

    try:
        if dedup.enabled:
            csg_for_hash = ensure_csg()
            dedup_hash = dedup.hash_csg(csg_for_hash)
            cache_step_path = dedup.cache_path_for_hash(dedup_hash)
            if cache_step_path.exists():
                dedup.link_to_output(cache_step_path, step_path)
                return StepExportResult(
                    step_path=step_path,
                    cache_path=cache_step_path,
                    dedup_hit=True,
                    dedup_hash=dedup_hash,
                )
            conversion_target = cache_step_path

        if backend == "openscad":
            run_openscad(
                scad_path,
                conversion_target,
                openscad_bin,
                ["--export-format", "step"],
            )
        elif backend in {"freecad", "freecad_stl"}:
            if not freecad_bin:
                raise ExportError("freecad binary not configured; set export.freecad_bin")
            tolerance = float(export_cfg.get("freecad_mesh_tolerance", 0.1))
            temp_stl: Path | None = None
            if stl_path is None:
                temp_stl = step_path.with_suffix(".step_source.stl")
                run_openscad(scad_path, temp_stl, openscad_bin)
                stl_path = temp_stl
            try:
                convert_stl_to_step_with_freecad(
                    stl_path, conversion_target, freecad_bin, tolerance
                )
            finally:
                if temp_stl:
                    temp_stl.unlink(missing_ok=True)
        elif backend in {"freecad_csg", "freecad-csg"}:
            if not freecad_bin:
                raise ExportError("freecad binary not configured; set export.freecad_bin")
            csg_input = ensure_csg()
            try:
                convert_csg_to_step_with_freecad(csg_input, conversion_target, freecad_bin)
            except ExportError:
                if not allow_stl_fallback:
                    raise
                tolerance = float(export_cfg.get("freecad_mesh_tolerance", 0.1))
                temp_stl: Path | None = None
                try:
                    if stl_path is None:
                        temp_stl = step_path.with_suffix(".step_source.stl")
                        run_openscad(scad_path, temp_stl, openscad_bin)
                        stl_path = temp_stl
                    convert_stl_to_step_with_freecad(
                        stl_path, conversion_target, freecad_bin, tolerance
                    )
                finally:
                    if temp_stl:
                        temp_stl.unlink(missing_ok=True)
        else:
            raise ExportError(f"unsupported STEP backend '{backend}'")

        if dedup.enabled:
            dedup.link_to_output(cache_step_path, step_path)
            return StepExportResult(
                step_path=step_path,
                cache_path=cache_step_path,
                dedup_hit=False,
                dedup_hash=dedup_hash,
            )
        return StepExportResult(step_path=step_path)
    finally:
        if csg_generated and csg_path:
            csg_path.unlink(missing_ok=True)


def _resolve_step_backend(backend: str, scad_path: Path, stl_path: Path | None) -> str:
    if backend in {"freecad_auto", "auto"}:
        if _scad_imports_stl(scad_path) or (stl_path and stl_path.exists()):
            return "freecad"
        return "freecad_csg"
    return backend


def _scad_imports_stl(scad_path: Path) -> bool:
    try:
        text = scad_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    lowered = text.lower()
    if "import(" not in lowered:
        return False
    for line in lowered.splitlines():
        if "import(" in line and ".stl" in line:
            return True
    return False


def convert_stl_to_step_with_freecad(
    stl_path: Path,
    step_path: Path,
    freecad_bin: str,
    tolerance: float,
) -> None:
    """Invoke FreeCAD CLI to convert STL mesh into a STEP solid."""
    script = textwrap.dedent(
        """
        import Mesh
        import Part
        import sys
        import os

        extra_mod = os.environ.get("OSC_FORGE_OPENSCAD_MOD")
        if extra_mod and extra_mod not in sys.path:
            sys.path.insert(0, extra_mod)

        if len(sys.argv) < 5:
            raise SystemExit("usage: freecadcmd script.py mesh.stl out.step tolerance")

        stl_path = sys.argv[2]
        step_path = sys.argv[3]
        tol = float(sys.argv[4])

        mesh = Mesh.Mesh(stl_path)
        shape = Part.Shape()
        shape.makeShapeFromMesh(mesh.Topology, tol)
        shell = Part.makeShell(shape.Faces)
        solid = Part.makeSolid(shell)
        try:
            solid = solid.removeSplitter()
        except Exception:
            pass
        solid.exportStep(step_path)
        """
    ).strip()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(script)
        script_path = Path(handle.name)

    env = os.environ.copy()
    repo_root = Path.cwd()
    freecad_user_home = repo_root / "tooling" / "freecad_home"
    freecad_user_home.mkdir(parents=True, exist_ok=True)
    env.setdefault("FREECAD_USER_HOME", str(freecad_user_home))
    env["PYTHONNOUSERSITE"] = "1"

    proc = None
    try:
        cmd = [
            freecad_bin,
            str(script_path),
            str(stl_path),
            str(step_path),
            str(tolerance),
        ]
        proc = subprocess.run(
            cmd, check=True, capture_output=True, text=True, env=env
        )
    except FileNotFoundError as exc:
        raise ExportError(f"FreeCAD binary not found: {freecad_bin}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or exc.stdout
        raise ExportError(
            f"FreeCAD STEP conversion failed ({exc.returncode}): {stderr}"
        ) from exc
    finally:
        try:
            os.remove(script_path)
        except FileNotFoundError:
            pass
    if proc and not step_path.exists():
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        raise ExportError(
            "FreeCAD finished without writing STEP output. "
            f"stdout: {stdout or '<empty>'}; stderr: {stderr or '<empty>'}"
        )


def convert_csg_to_step_with_freecad(
    csg_path: Path,
    step_path: Path,
    freecad_bin: str,
) -> None:
    """Invoke FreeCAD CLI to convert a CSG tree into a STEP solid."""
    script = textwrap.dedent(
        """
        import sys
        import os
        extra_mod = os.environ.get("OSC_FORGE_OPENSCAD_MOD")
        if extra_mod and extra_mod not in sys.path:
            sys.path.insert(0, extra_mod)
        import Part
        import importCSG
        import FreeCAD as App

        if len(sys.argv) < 4:
            raise SystemExit("usage: freecadcmd script.py mesh.csg out.step")

        csg_path = sys.argv[2]
        step_path = sys.argv[3]

        doc = App.newDocument("oscadforge_csg")
        importCSG.insert(csg_path, doc.Name)
        doc.recompute()
        objs = [obj for obj in doc.Objects if hasattr(obj, "Shape")]
        if not objs:
            raise SystemExit("no shapes produced from CSG input")
        Part.export(objs, step_path)
        """
    ).strip()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(script)
        script_path = Path(handle.name)

    env = os.environ.copy()
    # Force FreeCAD to keep its config/cache inside the workspace so sandboxed
    # runs do not fail when $HOME is read-only.
    repo_root = Path.cwd()
    freecad_user_home = repo_root / "tooling" / "freecad_home"
    freecad_user_home.mkdir(parents=True, exist_ok=True)
    env["FREECAD_USER_HOME"] = str(freecad_user_home)
    env["PYTHONNOUSERSITE"] = "1"

    user_mod = Path.home() / ".local" / "freecad_mods" / "Mod"
    if not user_mod.exists():
        repo_mod = freecad_user_home / "freecad_mods" / "Mod"
        user_mod = repo_mod if repo_mod.exists() else None

    if user_mod and user_mod.exists():
        openscad_mod = user_mod / "OpenSCAD"
        target_mod = openscad_mod if openscad_mod.exists() else user_mod
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            f"{target_mod}{os.pathsep}{existing}" if existing else str(target_mod)
        )
        env["OSC_FORGE_OPENSCAD_MOD"] = str(target_mod)
    proc = None
    try:
        cmd = [
            freecad_bin,
            str(script_path),
            str(csg_path),
            str(step_path),
        ]
        proc = subprocess.run(
            cmd, check=True, capture_output=True, text=True, env=env
        )
    except FileNotFoundError as exc:
        raise ExportError(f"FreeCAD binary not found: {freecad_bin}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or exc.stdout
        raise ExportError(
            f"FreeCAD STEP conversion failed ({exc.returncode}): {stderr}"
        ) from exc
    finally:
        try:
            os.remove(script_path)
        except FileNotFoundError:
            pass
    if proc and not step_path.exists():
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        raise ExportError(
            "FreeCAD finished without writing STEP output. "
            f"stdout: {stdout or '<empty>'}; stderr: {stderr or '<empty>'}"
        )


def assemble_step_from_parts(
    parts: Sequence[StepAssemblyPart],
    step_path: Path,
    freecad_bin: str,
) -> None:
    """Instantiate STEP parts with transforms and export combined STEP."""
    if not parts:
        raise ExportError("no STEP parts provided for assembly")
    instructions = []
    for part in parts:
        matrix = [[float(value) for value in row] for row in part.matrix]
        instructions.append({"step": str(part.step_path), "matrix": matrix})

    script = textwrap.dedent(
        """
        import json
        import Part
        import FreeCAD as App
        import sys

        if len(sys.argv) < 4:
            raise SystemExit("usage: freecadcmd script.py assembly.json out.step")

        data_path = sys.argv[2]
        step_path = sys.argv[3]

        with open(data_path, "r", encoding="utf-8") as handle:
            entries = json.load(handle)

        doc = App.newDocument("oscadforge_assembly")
        objects = []
        for idx, entry in enumerate(entries):
            shape = Part.Shape()
            shape.read(entry["step"])
            obj = doc.addObject("Part::Feature", f"Panel_{idx}")
            obj.Shape = shape
            matrix = entry["matrix"]
            if len(matrix) != 4 or any(len(row) != 4 for row in matrix):
                raise SystemExit("invalid matrix; expected 4x4")
            flat = [matrix[r][c] for r in range(4) for c in range(4)]
            mat = App.Matrix(*flat)
            obj.Placement = App.Placement(mat)
            objects.append(obj)

        doc.recompute()
        if not objects:
            raise SystemExit("no objects created for assembly")
        Part.export(objects, step_path)
        """
    ).strip()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as script_file:
        script_file.write(script)
        script_path = Path(script_file.name)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as data_file:
        json.dump(instructions, data_file)
        data_path = Path(data_file.name)

    env = os.environ.copy()
    repo_root = Path.cwd()
    freecad_user_home = repo_root / "tooling" / "freecad_home"
    freecad_user_home.mkdir(parents=True, exist_ok=True)
    env["FREECAD_USER_HOME"] = str(freecad_user_home)

    try:
        cmd = [
            freecad_bin,
            str(script_path),
            str(data_path),
            str(step_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
    except FileNotFoundError as exc:
        raise ExportError(f"FreeCAD binary not found: {freecad_bin}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or exc.stdout
        raise ExportError(
            f"FreeCAD STEP assembly failed ({exc.returncode}): {stderr}"
        ) from exc
    finally:
        script_path.unlink(missing_ok=True)
        data_path.unlink(missing_ok=True)


def export_step_artifacts_parallel(
    tasks: Sequence[StepExportTask],
    *,
    max_workers: int | None = None,
) -> list[tuple[StepExportTask, StepExportResult]]:
    if not tasks:
        return []
    results: list[StepExportResult | None] = [None] * len(tasks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map: dict[concurrent.futures.Future[StepExportResult], int] = {}
        for idx, task in enumerate(tasks):
            future = executor.submit(
                export_step_artifact,
                task.scad_path,
                task.step_path,
                export_cfg=task.export_cfg,
                openscad_bin=task.openscad_bin,
                freecad_bin=task.freecad_bin,
                stl_path=task.stl_path,
            )
            future_map[future] = idx
        for future in concurrent.futures.as_completed(future_map):
            idx = future_map[future]
            results[idx] = future.result()
    return [(task, results[i]) for i, task in enumerate(tasks) if results[i] is not None]


class StepDedupManager:
    """Handle hashing + caching of STEP exports derived from CSG."""

    def __init__(self, enabled: bool, cache_dir: Path | None, link_mode: str) -> None:
        self.enabled = enabled
        self.cache_dir = cache_dir if enabled else None
        self.link_mode = link_mode

    @classmethod
    def from_config(
        cls,
        cfg: Any,
        *,
        default_cache_dir: Path,
    ) -> StepDedupManager:
        if not cfg:
            return cls(False, None, "symlink")
        if isinstance(cfg, Mapping):
            enabled = bool(cfg.get("enabled", True))
            cfg_map: Mapping[str, Any] = cfg
        elif isinstance(cfg, bool):
            enabled = cfg
            cfg_map = {}
        else:
            enabled = True
            cfg_map = {}
        if not enabled:
            return cls(False, None, "symlink")
        cache_dir_value = cfg_map.get("cache_dir")
        cache_dir = (
            Path(cache_dir_value).expanduser()
            if cache_dir_value
            else default_cache_dir
        )
        link_mode = str(cfg_map.get("link", "symlink")).lower()
        if link_mode not in {"symlink", "hardlink", "copy"}:
            link_mode = "symlink"
        return cls(True, cache_dir, link_mode)

    def hash_csg(self, csg_path: Path) -> str:
        if not self.enabled:
            raise RuntimeError("step dedup disabled")
        digest = hashlib.sha256()
        with csg_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def cache_path_for_hash(self, digest: str) -> Path:
        if not self.enabled or self.cache_dir is None:
            raise RuntimeError("step dedup disabled")
        ensure_directory(self.cache_dir)
        return self.cache_dir / f"{digest}.step"

    def link_to_output(self, source: Path | None, target: Path) -> None:
        if not self.enabled or source is None:
            return
        if not source.exists():
            raise ExportError(f"dedup cache missing {source}")
        ensure_directory(target.parent)
        try:
            if target.exists() or target.is_symlink():
                try:
                    if target.samefile(source):
                        return
                except FileNotFoundError:
                    pass
                target.unlink()
        except FileNotFoundError:
            pass
        try:
            if self.link_mode == "hardlink":
                os.link(source, target)
            elif self.link_mode == "copy":
                shutil.copy2(source, target)
            else:
                rel = os.path.relpath(source, target.parent)
                os.symlink(rel, target)
        except OSError:
            shutil.copy2(source, target)


def build_png_args(cfg: Optional[object]) -> tuple[bool, list[str]]:
    if cfg is None:
        return False, []
    if isinstance(cfg, bool):
        return cfg, []
    enabled = cfg.get("enabled", True)
    args: list[str] = []
    imgsize = cfg.get("imgsize")
    if isinstance(imgsize, Iterable):
        vals = list(imgsize)
        if len(vals) == 2:
            args.extend(["--imgsize", f"{int(vals[0])},{int(vals[1])}"])
    if cfg.get("viewall"):
        args.append("--viewall")
    camera = cfg.get("camera")
    if camera:
        args.extend(["--camera", str(camera)])
    projection = cfg.get("projection")
    if projection:
        args.extend(["--projection", str(projection)])
    return bool(enabled), args
