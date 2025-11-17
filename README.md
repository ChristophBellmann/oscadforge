# OpenSCADForge

Pandoc-style CAD pipeline for parameterised OpenSCAD projects.\
Instead of hand-editing `.scad`, you describe geometry in YAML, pass it to the CLI, and let the engine produce SCAD/STL/PNG artefacts — exactly like Pandoc turns Markdown into PDFs.


## create 
```
python3 -m oscadforge.oscadforge oscadforge/templates/model_opengrid-papierkorb.yaml oscadforge/config/export_opengrid_papierkorb_step_freecad.yaml
```

## INFO

```
# List registered engine models
python3 -m oscadforge.oscadforge -l

# Papierkorb run: defaults + "no honeycomb" override from config
python3 -m oscadforge.oscadforge \
  oscadforge/templates/model_papierkorb.yaml \
  oscadforge/config/papierkorb_nohex.yaml

# Papierkorb run: Ultimaker-ready OpenGrid tiles (assembled + flat sheets)
python3 -m oscadforge.oscadforge \
  oscadforge/templates/model_papierkorb.yaml \
  oscadforge/config/papierkorb_opengrid.yaml

# Papierkorb (OpenGrid 2) – panels & connectors straight from the OpenGrid sources
python3 -m oscadforge.oscadforge \
  oscadforge/templates/model_opengrid_2.yaml

# Papierkorb (OpenGrid Full, 1 Tile kürzer)
python3 -m oscadforge.oscadforge \
  oscadforge/templates/model_opengrid-papierkorb.yaml

# OpenGrid-Papierkorb (SCAD + STEP Export)
python3 -m oscadforge.oscadforge \
  oscadforge/templates/model_opengrid-papierkorb.yaml \
  oscadforge/config/export_opengrid_papierkorb_step_freecad.yaml
# Das Template setzt `dimension_rounding: floor`, daher reduziert sich die Breite (132 mm)
# automatisch auf 4 OpenGrid-Zellen à 28 mm und bleibt im 256 mm Druckbett.

# Papierkorb (CSG → FreeCAD STEP + dedup cache)
python3 -m oscadforge.oscadforge \
  oscadforge/templates/model_papierkorb.yaml \
  oscadforge/config/export_papierkorb_step_freecad_dedup.yaml

# Pipeline from stdin → render artefact → JSON metadata
cat papierkorb_config.yaml | python3 -m oscadforge.oscadforge \
  - --result-json out/run.json -o out/papierkorb.png

# Standalone SCAD → STEP conversion
python3 -m oscadforge.tools.scad2step \
  my_model.scad out/my_model.step \
  --backend freecad_csg --freecad-bin ./tooling/freecadcmd-local.sh

# Experimentelle UI mit Template/Config-Selector
python3 -m oscadforge.tools.ui

Die Tkinter-Oberfläche listet alle Modellyamls aus `oscadforge/templates/`
und die Overrides aus `oscadforge/config/`. Wähle links ein Modell, rechts
beliebige Overrides, entscheide optional auf „Dry run“ und starte den Build.
Die Ausgabe zeigt dieselben Logs wie der CLI-Run und beendet mit dem neuen
Statistik-Block (Laufzeit +, falls verfügbar, Energieverbrauch). Für volle
Exports gelten dieselben Tooling-Abhängigkeiten wie beim Terminal-Aufruf
(OpenSCAD/FreeCAD-Pfade etc.).

# Web UI (lokaler HTTP-Server)
python3 -m oscadforge.tools.webui

Der kleine HTTP-Server läuft standardmäßig auf `http://127.0.0.1:8765/` und
liefert dieselben Listen/Optionen wie die Tkinter-App – nur diesmal im Browser.
Modell auswählen, Configs markieren, auf „Run“ klicken, fertig. Logs, SCAD-/STEP-
Pfade sowie der Statistikblock erscheinen im Browserfenster.

Need to re-emit the legacy reference SCAD from `in/Papierkorb/`? The old AnchorSCAD script still works:

```bash
python3 -m venv oscadforge/.venv
source oscadforge/.venv/bin/activate
pip install anchorscad-core pyyaml
python Papierkorb/tiled_bin_anchorscad.py --scad in/Papierkorb/papierkorb_tiles.scad
```

That directory remains as historical documentation—the current engine generates everything from the YAML stacks under `oscadforge/templates/` (model presets) plus `oscadforge/config/` (printer/export overrides).

```

Need to prep OpenGrid 2 artifacts on a slower laptop and finish STEP on a bigger workstation? Temporarily set `export.step: false` inside `oscadforge/config/export_opengrid2_step_freecad.yaml`, run the command above to refresh `out/opengrid2_freecad/*.scad`, sync that directory to the faster machine, flip `export.step` back to `true`, and rerun the same command to let FreeCAD convert every sheet into STEP.

Need die kürzere OpenGrid-Full-Variante? Ersetze das Modellyaml durch
`oscadforge/templates/model_opengrid-papierkorb.yaml` und kombiniere es bei
STEP-basierten Läufen mit `oscadforge/config/export_opengrid_papierkorb_step_freecad.yaml`
– identischer Workflow, aber Ausgaben landen unter `out/opengrid_papierkorb_freecad/`.

Bulk STL folder? Point the converter at the root directory and let it spawn one FreeCAD job per file:

```bash
python3 -m oscadforge.tools.stl2step in \
  --freecad-bin ./tooling/freecadcmd-local.sh --workers 24
```

Every `.stl` under `in/` (and its subdirectories) receives a sibling `.step`. Existing STEP files are skipped unless you pass `--force`.

### OpenGrid 2 workflow notes

* The OpenGrid preset now uses `connectors.generate_connectors: false` (see `oscadforge/templates/model_opengrid_2.yaml`), so no separate `opengrid2_freecad_connectors.scad` is produced. Only the assembled bin and the per-sheet QuackWorks tiles land in `out/opengrid2_freecad/`.
* Die neue `oscadforge/templates/model_opengrid-papierkorb.yaml` Variante bleibt beim selben Generator, nutzt aber konsequent die OpenGrid-"Full"-Boards samt Connector-Sleeves aus `third_party/QuackWorks/openGrid` und kürzt das Gehäuse um eine Tile (28 mm). Für STEP/PNG gleich `oscadforge/config/export_opengrid_papierkorb_step_freecad.yaml` mergen, Ausgabe landet unter `out/opengrid_papierkorb_freecad/`.
* STEP generation relies on the FreeCAD STL backend. If a conversion stalls or you want tighter control, call the helper manually:

  ```
  python3 -m oscadforge.tools.scad2step \
    out/opengrid2_freecad/opengrid2_freecad_sheet01.scad \
    out/opengrid2_freecad/opengrid2_freecad_sheet01.step \
    --backend freecad \
    --openscad-bin ./tooling/OpenSCAD-nightly.AppDir/AppRun \
    --freecad-bin ./tooling/freecadcmd-local.sh
  
  
  ```
* Repeat the command for each `sheetXX` (or wrap it in a shell loop) on the faster host. The CLI automatically reuses the `opengrid2_freecad/*.scad` files you generated earlier, so only FreeCAD needs to do work during the second pass.

Outputs land in `export.output_dir` (or the path you pass via `-o`). PNGs fallback to a deterministic top-down render when OpenSCAD cannot create a GL context. Need STEP? Set `export.step: true` (or run with `-o out/model.step`). By default the CLI calls OpenSCAD with `--export-format step` (needs a 2025+ snapshot). Prefer the “Export as CSG → FreeCAD → STEP” workflow? Set `export.step_backend: freecad_csg` and `export.freecad_bin: ./tooling/freecadcmd-local.sh` — the CLI now emits a CSG tree, feeds it into FreeCAD’s OpenSCAD importer, and writes a solid STEP (exactly like opening the CSG manually in FreeCAD before saving as STEP and importing into SolidWorks). The legacy `freecad` backend (STL → STEP) is still available as a fallback when you already have a watertight mesh around.

Jeder CLI-Lauf beendet nun mit einem kurzen Statistikblock (`Run duration …, energy Δ …`), sodass du direkt siehst, wie lange der Merge/Export gedauert hat und – falls dein Kernel RAPL-/powercap-Werte liefert – wie viel Energie (auf Basis von `/sys/class/powercap/**/energy_uj`) verbraucht wurde. Die gleichen Werte landen in `result.metadata.stats`, falls du sie später maschinell auswerten willst.

Need to keep large YAML runs manageable? Enable the STEP dedup cache: `export.step_dedup: true` (or pass a mapping with `cache_dir`, `link`, etc.). The engine now hashes the generated CSG tree, writes a single STEP per unique geometry, and links every duplicate artifact back to the cached file (symlink by default, falls back to hardlink/copy). See `oscadforge/docs/concept_scad_to_step_dedup.md` for the design and `oscadforge/config/export_step_dedup.yaml` for a ready-to-merge preset.

## Repository Map

| Path | Purpose | |------|---------| | `oscadforge/oscadforge.py` | Pandoc-like CLI entrypoint (`python3 -m oscadforge.oscadforge …`). | | `oscadforge/core/*` | Engine, exporters, config utilities. | | `oscadforge/config/` | Printer/export overrides and shared YAML blocks (e.g. `export_local.yaml`, `papierkorb_nohex.yaml`, `layout_both.yaml`). The CLI auto-searches here when you pass bare filenames. | | `oscadforge/templates/` | Model YAML presets (e.g. `model_papierkorb.yaml`, `model_opengrid_2.yaml`, `model_opengrid-papierkorb.yaml`). The CLI searches this directory after `oscadforge/config/`. | | `in/Papierkorb/` | Project docs for the Papierkorb reference model (now SCAD-native). | | `oscadforge/docs/opengrid_2.md` | Notes for the OpenGrid-backed Papierkorb variant (panels + connectors imported from the QuackWorks/openGrid repos). | | `oscadforge/docs/concept_scad_to_step_dedup.md` | Concept: CSG hashing + STEP deduplication flow (no code). | | `third_party/BOSL2/` | Vendored [BOSL2](https://github.com/BelfrySCAD/BOSL2) OpenSCAD library (primitives, rounding, attachments). | | `third_party/jl_scad/` | Vendored [jl_scad](https://github.com/lijon/jl_scad) sources powering the Papierkorb shell. | | `out/` | Default artefact directory (SCAD/STL/PNG). | | `tests/` | Pytest suite covering CLI flows and geometry smoke tests. | | `in/opengrid_printables/` | Printables dumps (OpenGrid tiles, Multiconnect clips, mounting docs, etc.) for manual reference. | | `in/opengrid_angle/` | 90° OpenGrid angle connectors from Printables (`*_Nx.stl` plus PDF instructions). |

### OpenSCAD Library Path

The SCAD sources load BOSL2 via `include <BOSL2/std.scad>` inside the vendored `jl_scad` files, so OpenSCAD must be told where `third_party/` lives.\
When using the CLI or running OpenSCAD manually, prepend the repo path to `OPENSCADPATH` (or pass `--include /path/to/third_party`):

```
export OPENSCADPATH="$PWD/third_party${OPENSCADPATH:+:$OPENSCADPATH}"
```

With that in place both the CLI renders and the OpenSCAD GUI can resolve `BOSL2/*` and `jl_scad/*` includes without extra tweaks.

Want the path to stick across shells/GUI sessions? Append this to `~/.bashrc` (or `~/.profile`) so `OPENSCADPATH` always includes the vendored libraries:

```
if [ -d "$HOME/OpenSCADForge/third_party" ]; then
  OPENSCADFORGE_LIBS="$HOME/OpenSCADForge/third_party"
  case ":$OPENSCADPATH:" in
    *":$OPENSCADFORGE_LIBS:"*) ;;
    *) export OPENSCADPATH="$OPENSCADFORGE_LIBS${OPENSCADPATH:+:$OPENSCADPATH}" ;;
  esac
fi
```

### Models & Configs

* **Engine models** live in `oscadforge/core/models/`. They contain the actual geometry (anchorscad classes) for targets like `papierkorb_tiles` or `solar_bus_roof` — think “Pandoc output formats”.
* **Configs** live anywhere, but the repository ships curated YAML presets under `oscadforge/config/`. Each YAML file is just a partial dictionary; the CLI deep-merges everything you pass (`python3 -m oscadforge.oscadforge base.yaml override.yaml ...`).

### Papierkorb Coordinate Space & Layout Modes

* The Papierkorb engine works in a **design space** where the assembled bin spans `[-L/2, +L/2]` in X, `[-B/2, +B/2]` in Y, and `[0, H]` in Z. Floors are centred at `wall_mm / 2` but AnchorSCAD’s translation keeps the physical bottom on `Z≈0` (only ±0.0005 mm EPS shows up in tests/renders).
* `layout.mode: assembled` therefore yields a watertight bin already sitting on the build plane. `layout.mode: flat` reorients every panel onto the printer bed – origins differ on purpose so that sheets are printable.
* Use `layout.mode: both` when you want separate assembled + sheet artefacts from a single run, or `layout.mode: debug_assembled_with_panels` to emit a single SCAD where the assembled bin stays at the origin and the flattened sheets are shifted to the +X side (same coordinate basis, handy for OpenSCAD overlays).
* The smoke tests clamp tolerances to `EPS = 1e-3`; if you inspect the generated SCAD/STL manually you can do the same (e.g. treat any `abs(z) < EPS` as “on the bed”) without introducing extra translations into the geometry code.

## Workflows

### 1. YAML Only

```
python3 -m oscadforge.oscadforge \
  oscadforge/config/bus.yaml \
  oscadforge/config/panels.yaml \
  oscadforge/templates/model_solar_bus.yaml \
  oscadforge/config/export_bus.yaml
```

### 2. YAML via stdin

```
cat papierkorb_config.yaml | python3 -m oscadforge.oscadforge \
  - --result-json out/run.json
```

The CLI expects the merged YAML to contain `model.*` and `export.*` sections.\
Use `--openscad-bin` to point at a specific OpenSCAD binary (default is `openscad` resolved via `$PATH`; pass `/usr/local/bin/openscad-snapshot` or `./tooling/OpenSCAD-nightly.AppDir/AppRun` if you prefer a specific build).\
The repo ships wrappers under `tooling/OpenSCAD-nightly.AppDir/AppRun` and `tooling/freecadcmd-local.sh` that unpack the matching AppImages on first use, so you no longer have to extract the `.AppImage` payloads manually.

Need both the assembled Papierkorb and every flattened sheet in one go? Stack the layout overlay derived from `jl_scad`:

```
python3 -m oscadforge.oscadforge \
  oscadforge/templates/model_papierkorb.yaml \
  oscadforge/config/printer_ultimaker2.yaml \
  oscadforge/config/layout_both.yaml \
  oscadforge/config/export_papierkorb_flat.yaml
```

## Config Schema Quick Reference

```
model:
  name: papierkorb_tiles
  params:
    L_mm: 514
    B_mm: 170
    H_mm: 605
    wall_mm: 3.6
    enable_tiles: true
    enable_honeycomb: false
    enable_opengrid: true
    opengrid_cell_mm: 24
    opengrid_bar_mm: 3.2
    opengrid_margin_mm: 12
  layout:
    mode: both          # assembled, flat, both, or debug_assembled_with_panels
    bed_mm: [200, 200]
    spacing_mm: 6
export:
  scad: true
  stl: true
  step: true
  step_backend: freecad_auto   # optional; defaults to "openscad"
  freecad_bin: ./tooling/freecadcmd-local.sh
  freecad_mesh_tolerance: 0.12
  step_assembly: panel         # panel (default) or scad
  png:
    enabled: true
    viewall: true
    imgsize: [600, 400]
  output_dir: ./out/papierkorb
  basename: papierkorb_tiles
```

Split this across as many files as you like — the CLI deep-merges everything in order.

When `step_backend: freecad` is enabled the CLI first emits an STL (reusing the one you already requested, if any) and then runs the FreeCAD CLI specified via `freecad_bin` to convert it into STEP. `freecad_mesh_tolerance` tweaks the `Part.Shape.makeShapeFromMesh` tolerance (in mm); the default of `0.1` works well for the Papierkorb scale, but bump it up slightly for noisier meshes.\
Prefer the exact OpenSCAD → CSG → FreeCAD path? Use `step_backend: freecad_csg` instead — the CLI tells OpenSCAD to export `.csg`, pipes that into FreeCAD’s OpenSCAD importer (headless), and exports a union of all resulting solids as STEP so downstream CAD (SolidWorks, etc.) sees the same parametric bodies you would get from a manual FreeCAD import. See `oscadforge/config/export_papierkorb_step_freecad_dedup.yaml` for a preset that keeps SCAD/STL output, runs FreeCAD on the CSG tree, and deduplicates identical geometries under `out/.step_cache_freecad/`. We keep a user-writable copy of `/usr/share/freecad/Mod/OpenSCAD` under `~/.local/freecad_mods/Mod`, and the exporter automatically prepends it to `PYTHONPATH` so FreeCAD can generate its `parsetab.py` without touching `/usr/share`.\
Need both worlds? Set `step_backend: freecad_auto` — the exporter inspects the generated SCAD: if it references external STLs it routes that artifact through the classic STL → STEP converter, otherwise it emits a `.csg` and lets FreeCAD’s OpenSCAD importer create the solid. Should FreeCAD choke on the CSG (huge tree, missing modules), the exporter automatically falls back to STL conversion for that artifact. Assemblies such as `opengrid_2` go a step further: every unique panel geometry is exported once as a planar STEP, and the final `opengrid2_freecad.step` gets assembled by FreeCAD in seconds by instantiating those panels with the placement matrices embedded in the SCAD. No more 55 MB STL → STEP runs for the full bin, while the sheet-level STEP exports stay untouched.\
Prefer the old “one giant STEP from the assembled SCAD” behavior? Set `export.step_assembly: scad` and the exporter reverts to the monolithic conversion path. Omitting the key (or leaving it at `panel`) keeps the faster per-panel assembly for any model that exposes tile placements (Papierkorb + OpenGrid). Regardless of backend, `export.step_dedup` can deduplicate identical geometries: the engine exports a temporary `.csg`, hashes it, and stores the canonical STEP file under `cache_dir/<hash>.step`. Later artifacts with the same geometry simply symlink (or hardlink/copy) to that cached STEP instead of re-running OpenSCAD/FreeCAD.

Just need to convert a single `.scad` file? Use the CLI wrapper:

```
python3 -m oscadforge.tools.scad2step \
  input.scad output.step \
  --backend freecad_csg \
  --freecad-bin ./tooling/freecadcmd-local.sh
```

Add `--dedup-cache out/.step_cache_local` to reuse geometry hashes across runs.

### Printer presets (Bambu Lab P1S)

Need larger tiles for a 256 × 256 × 256 mm build volume? The repo now ships printer overrides for the Bambu Lab P1S:

```
# Papierkorb (JL shell)
python3 -m oscadforge.oscadforge \
  oscadforge/templates/model_papierkorb.yaml \
  oscadforge/config/printer_bambulab_p1s.yaml \
  oscadforge/config/export_papierkorb_step_freecad.yaml

# Papierkorb (OpenGrid 2 backend)
python3 -m oscadforge.oscadforge \
  oscadforge/templates/model_opengrid_2.yaml \
  oscadforge/config/printer_bambulab_p1s_opengrid2.yaml \
  oscadforge/config/export_opengrid2_step_freecad.yaml

# Papierkorb (OpenGrid Full, kürzeres Layout)
python3 -m oscadforge.oscadforge \
  oscadforge/templates/model_opengrid-papierkorb.yaml \
  oscadforge/config/printer_bambulab_p1s_opengrid2.yaml \
  oscadforge/config/export_opengrid_papierkorb_step_freecad.yaml
```

The printer configs bump `layout.bed_mm` to `[256, 256]` and clamp each tile to 248 mm so OpenGrid slices (and the JL shell panels) stay printable on the P1S while respecting the original Papierkorb dimensions.

### JL_SCAD-inspired joints

Panels are still cut directly out of the jl_scad shell, but they now ship ohne Legacy-Steckverbinder. Nur die optionalen Flansche (`flange_depth_mm`) an den kurzen Seiten bleiben aktiv, damit die langen Paneele eingeschoben werden können; OpenGrid/Honeycomb liegen panel-lokal und folgen jeder Layout-Transformation ohne zusätzliche Zapfen.

The assembled output colours each tile differently (using the same palette as the flat sheets) so OpenSCAD previews immediately show how the tiles stack up.

Short-side tiles (`wall_posX/negX`) also sprout 10 mm U-shaped flanges whenever `flange_depth_mm > 0`, letting the long-side panels slide into them for extra stiffness. Tune that overhang with the YAML key `flange_depth_mm`.

### Papierkorb jl_scad backend

`papierkorb_tiles` now renders geometry entirely via the vendored `jl_scad` library. Python is still responsible for parameter merging, layout planning (assembled + sheets), and emitting one SCAD file per artefact, but every wall/floor/rim primitive ultimately derives from the jl_scad shell. The `panel_geom_*` modules slice that shell into printable tiles, add only the optional flanges defined in the YAML params, and then the layout step either keeps the assembled transform or applies the sheet packing transform. Every assembled placement carries a deterministic `color([r,g,b,a]) multmatrix(...) panel_geom_*();` wrapper so OpenSCAD previews mirror the CLI renders when you check tile alignment.\
Other models (e.g. `solar_bus_roof`) still use AnchorSCAD, so both ecosystems happily coexist inside the same CLI.

See `THIRD_PARTY_NOTICES.md` for the jl_scad license.

## Tests

```
python3 -m pytest
```

This runs geometry smoke tests plus CLI integration (YAML stacks, stdin pipelines, PNG/STL validation).\
Ensure the configured OpenSCAD binary (`openscad` by default) is present for STL generation; PNG renders fallback to the built-in preview when GL isn’t available.\
Need a custom snapshot? Point the suite to it via `OPENSCAD_TEST_BIN=/path/to/openscad` — otherwise it tries `.openscad-appimage/AppRun` first and then whatever `which openscad` resolves.

## Dependencies

* Python 3.10+
* `anchorscad-core`, `pythonopenscad`, `pyyaml`, `pytest` (see `requirements-dev.txt`)
* OpenSCAD CLI (snapshot AppImage or system install; add to `PATH` or export `OPENSCAD_TEST_BIN`)
* FreeCAD CLI (`./tooling/freecadcmd-local.sh`) when `step_backend: freecad_csg`/`freecad` is enabled.

## Credits & Further Reading

* AnchorSCAD: https://github.com/obenno/anchorscad
* OpenSCAD Libraries: https://openscad.org/libraries.html
* Original Papierkorb spec in `in/Papierkorb/Papierkorb_Original.cs`
