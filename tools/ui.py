from __future__ import annotations

import threading
import time
import traceback
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from typing import Iterable, List

import yaml

from ..core import engine, io
from ..oscadforge import _read_total_energy_uj


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "oscadforge" / "config"


class OscadForgeUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OpenSCADForge UI")
        self.geometry("900x600")
        self.config_paths: list[Path] = []
        self._build_widgets()
        self._refresh_lists()

    def _build_widgets(self) -> None:
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        lists_frame = ttk.Frame(main_frame)
        lists_frame.pack(fill=tk.X)

        cfg_frame = ttk.Frame(lists_frame)
        cfg_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(cfg_frame, text="Config presets (multi-select)").pack(anchor=tk.W)
        self.config_list = tk.Listbox(cfg_frame, selectmode=tk.MULTIPLE, exportselection=False, height=12)
        self.config_list.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(main_frame)
        controls.pack(fill=tk.X, pady=5)
        self.dry_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="Dry run (no build)", variable=self.dry_run_var).pack(side=tk.LEFT)
        ttk.Button(controls, text="Refresh", command=self._refresh_lists).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Run", command=self._start_run).pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Bereit")
        ttk.Label(main_frame, textvariable=self.status_var).pack(anchor=tk.W)

        self.output_box = ScrolledText(main_frame, height=20, state=tk.DISABLED)
        self.output_box.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def _refresh_lists(self) -> None:
        self.config_paths = _list_yaml_files(CONFIG_DIR)
        self.config_list.delete(0, tk.END)
        for path in self.config_paths:
            self.config_list.insert(tk.END, path.name)
        self.status_var.set("Configs aktualisiert")

    def _start_run(self) -> None:
        configs = [self.config_paths[i] for i in self.config_list.curselection()]
        if not configs:
            messagebox.showwarning("Fehlende Auswahl", "Bitte mindestens eine Config auswählen.")
            return
        dry_run = self.dry_run_var.get()
        self.status_var.set("Baue …")
        self._append_output(f"Starte Build mit {len(configs)} Config(s)\n")
        threading.Thread(target=self._run_build, args=(configs, dry_run), daemon=True).start()

    def _run_build(self, configs: Iterable[Path], dry_run: bool) -> None:
        try:
            config_dicts: List[dict] = []
            for cfg in configs:
                config_dicts.append(io.load_yaml(cfg))
            merged = io.merge_dicts(config_dicts)
            if dry_run:
                text = yaml.safe_dump(merged, sort_keys=False)
                self._append_output(f"-- Dry run merged config --\n{text}\n")
                self._set_status("Dry run abgeschlossen")
                return
            start = time.perf_counter()
            energy_start = _read_total_energy_uj()
            result = engine.build_model(merged)
            duration = time.perf_counter() - start
            energy_end = _read_total_energy_uj()
            energy_delta = None
            if energy_start is not None and energy_end is not None:
                energy_delta = max(0, energy_end - energy_start)
            result.metadata.setdefault(
                "stats",
                {
                    "duration_seconds": duration,
                    "energy_microjoules": energy_delta,
                },
            )
        except Exception as exc:  # pragma: no cover - UI error path
            tb = traceback.format_exc()
            self._append_output(f"Fehler beim Build: {exc}\n{tb}\n")
            self._set_status("Fehler")
            return

        log_lines = [f"SCAD: {result.scad_path}" if result.scad_path else "SCAD: (none)"]
        log_lines.extend(result.logs)
        for path in result.stl_paths:
            log_lines.append(f"STL: {path}")
        for path in result.step_paths:
            log_lines.append(f"STEP: {path}")
        for path in result.png_paths:
            log_lines.append(f"PNG: {path}")
        stats = result.metadata.get("stats", {})
        if stats:
            duration = stats.get("duration_seconds")
            energy = stats.get("energy_microjoules")
            msg = "Stats: "
            if duration is not None:
                msg += f"{duration:.2f}s"
            if energy is not None:
                msg += f", ΔE ≈ {energy / 1_000_000:.3f} J"
            log_lines.append(msg)
        self._append_output("\n".join(log_lines) + "\n")
        self._set_status("Build abgeschlossen")

    def _append_output(self, text: str) -> None:
        def _write() -> None:
            self.output_box.configure(state=tk.NORMAL)
            self.output_box.insert(tk.END, text + "\n")
            self.output_box.configure(state=tk.DISABLED)
            self.output_box.see(tk.END)

        self.after(0, _write)

    def _set_status(self, text: str) -> None:
        self.after(0, lambda: self.status_var.set(text))


def _list_yaml_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))


def main() -> None:
    app = OscadForgeUI()
    app.mainloop()


if __name__ == "__main__":
    main()
