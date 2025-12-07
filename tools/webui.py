from __future__ import annotations

import html
import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs

from ..core import engine, io
from ..oscadforge import _read_total_energy_uj

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "oscadforge" / "config"


def _list_yaml_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))


class ForgeRequestHandler(BaseHTTPRequestHandler):
    server_version = "oscadforge-webui/1.0"

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        if self.path not in ("/", ""):
            self.send_error(404, "Not Found")
            return
        self._render_page()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/run":
            self.send_error(404, "Not Found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length).decode("utf-8", errors="replace")
        fields = parse_qs(data)
        config_names = fields.get("configs", [])
        dry_run = fields.get("dry_run", ["off"])[0] == "on"
        message, result_html = self._handle_run(config_names, dry_run)
        self._render_page(message=message, result_html=result_html)

    def log_message(self, format: str, *args) -> None:  # pragma: no cover - quiet server
        return

    def _render_page(self, *, message: str = "", result_html: str = "") -> None:
        configs = _list_yaml_files(CONFIG_DIR)
        cfg_options = "\n".join(
            f'<option value="{html.escape(path.name)}">{html.escape(path.name)}</option>' for path in configs
        )
        message_html = f"<p class='message'>{html.escape(message)}</p>" if message else ""
        page = f"""
<!doctype html>
<html>
  <head>
    <meta charset='utf-8'>
    <title>OpenSCADForge Web UI</title>
    <style>
      body {{ font-family: sans-serif; margin: 2rem; }}
      form {{ margin-bottom: 1rem; }}
      select {{ width: 100%; min-height: 8rem; }}
      textarea {{ width: 100%; height: 20rem; }}
      .result {{ white-space: pre-wrap; background:#111; color:#eee; padding:1rem; border-radius:6px; }}
      .message {{ color: #0a0; }}
    </style>
  </head>
  <body>
    <h1>OpenSCADForge Web UI</h1>
    {message_html}
    <form method='post' action='/run'>
      <label>Config files (STRG/SHIFT für Mehrfachauswahl)</label>
      <select name='configs' multiple required>
        {cfg_options}
      </select>
      <label><input type='checkbox' name='dry_run'> Dry run (nur Merge anzeigen)</label>
      <div style='margin-top:0.5rem;'>
        <button type='submit'>Run</button>
      </div>
    </form>
    <div class='result'>{result_html}</div>
  </body>
</html>
"""
        payload = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _handle_run(self, config_names: Iterable[str], dry_run: bool) -> tuple[str, str]:
        config_map = {path.name: path for path in _list_yaml_files(CONFIG_DIR)}
        configs = [config_map[name] for name in config_names if name in config_map]
        if not configs:
            return "Bitte mindestens eine Config auswählen", ""
        try:
            merged = _merge_configs(configs)
            if dry_run:
                return "Dry run abgeschlossen", html.escape(json.dumps(merged, indent=2, sort_keys=True))
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
        except Exception as exc:  # pragma: no cover - runtime errors
            return "Build fehlgeschlagen", html.escape(str(exc))
        return "Build abgeschlossen", _format_result_html(result)


def _merge_configs(paths: Iterable[Path]) -> dict:
    dicts = [io.load_yaml(path) for path in paths]
    return io.merge_dicts(dicts)


def _format_result_html(result: engine.EngineResult) -> str:
    lines = []
    if result.scad_path:
        lines.append(f"SCAD: {result.scad_path}")
    lines.extend(result.logs)
    for path in result.stl_paths:
        lines.append(f"STL: {path}")
    for path in result.step_paths:
        lines.append(f"STEP: {path}")
    for path in result.png_paths:
        lines.append(f"PNG: {path}")
    stats = result.metadata.get("stats", {})
    if stats:
        msg = "Stats:
"
        duration = stats.get("duration_seconds")
        if duration is not None:
            msg += f"  Duration: {duration:.2f}s\n"
        energy = stats.get("energy_microjoules")
        if energy is not None:
            msg += f"  Energy Δ: {energy / 1_000_000:.3f} J\n"
        lines.append(msg.rstrip())
    return html.escape("\n".join(lines))


def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = HTTPServer((host, port), ForgeRequestHandler)
    print(f"OpenSCADForge Web UI läuft auf http://{host}:{port}")
    print("Mit STRG+C stoppen.")
    server.serve_forever()


if __name__ == "__main__":  # pragma: no cover
    main()
