from __future__ import annotations

import importlib
import runpy
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


class TemplateError(RuntimeError):
    """Raised when a template python file/module is invalid."""


@dataclass
class Template:
    name: str
    path: Path | None
    build_config: Callable[..., dict]


def load_template(ref: str) -> Template:
    base_dir = Path(__file__).resolve().parents[1] / "templates"
    ref_path = Path(ref)
    search_paths = [
        ref_path,
        base_dir / ref,
        base_dir / f"{ref}.py",
    ]
    for path in search_paths:
        if not path.exists():
            continue
        module_globals = runpy.run_path(str(path))
        build = module_globals.get("build_config")
        if not callable(build):
            raise TemplateError(f"Template {path} does not define build_config(data, **kwargs)")
        name = module_globals.get("TEMPLATE_NAME", path.stem)
        return Template(name=name, path=path, build_config=build)

    module_name = ref
    if module_name.endswith(".py"):
        module_name = module_name[:-3]
    module_name = module_name.replace("/", ".")
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise TemplateError(f"Template '{ref}' not found as file or module") from exc
    build = getattr(module, "build_config", None)
    if not callable(build):
        raise TemplateError(f"Template module '{module_name}' missing build_config(data, **kwargs)")
    name = getattr(module, "TEMPLATE_NAME", module_name.split(".")[-1])
    path = Path(getattr(module, "__file__", "")) if getattr(module, "__file__", None) else None
    return Template(name=name, path=path, build_config=build)
