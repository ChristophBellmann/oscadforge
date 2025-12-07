# Papierkorb Modularization Plan

Goal: Rework the current `tiled_bin_anchorscad.py` monolith into modular components that mirror the "Pandoc" philosophy—data → CLI → engine—so that future features (flat layout, multi-printer presets, optional accessories) can be added cleanly.

## Current Pain Points
1. **Monolithic builder** – `TiledBin.build()` unions everything immediately, so we cannot re-use geometry for different layout outputs.
2. **Patterns baked in** – honeycomb/OpenGrid perforations belong to the entire Maker, not to a specific panel, making rotation or flattening impossible without copying.
3. **No layout separation** – assembled view and potential flat view share the same coordinate system; no way to author multiple output modes.

## Target Architecture

### 1. Panel Module
- Provide classes (or data structures) for each panel type (floor tile, X-wall tile, Y-wall tile, rim strip).
- Each panel stores:
  - `geometry` (anchorscad Maker)
  - `type` (`floor`, `wall_x`, `wall_y`, `rim`)
  - `bounding_box`, `local_axes`
  - breakdown of accessories: OpenGrid/Honeycomb bores plus optional flanges.
- Pattern drilling becomes a helper function returning panel-affixed geometry.

**Files/Modules to add:**
- `oscadforge/models/paperkorb/panels.py`
- `oscadforge/models/paperkorb/patterns.py` (OpenGrid/Honeycomb helpers)
- `oscadforge/models/paperkorb/layout.py`

### 2. Layout Module
- `layout_mode`: `assembled`, `flat`, `both`.
- Layout manager takes a list of panel objects and returns positioned instances:
  - For `assembled`: current positions (using original center + orientation).
  - For `flat`: rotate according to panel type (e.g., walls go horizontal), arrange on sheets respecting printer bed size (default 200×200 mm, but allow presets from YAML).
- Provide sheet metadata (sheet name, bounding box) to the exports.

**Files/Modules to add:**
- `oscadforge/models/paperkorb/layout.py` for assembled/flat transforms & bed packing.

### 3. Model Entry Point
- `tiled_bin_anchorscad.py` becomes thin: create panel objects → call layout manager → union results.
- Expose parameters (`layout.mode`, `layout.bed_mm`, `layout.spacing_mm`, `simple_shell`, …) so pure YAML configs can drive every feature through the CLI.

### 4. YAML Enhancements
- Document the knobs provided by `oscadforge/config/*.yaml` (layout presets, printer beds, optional accessories).
- Provide override files (e.g., `papierkorb_nohex.yaml`, `papierkorb_shell.yaml`) instead of Python templates.
- Track pattern-specific options (`enable_opengrid`, honeycomb pitch, flange depth, etc.) so wir Features gezielt zu- oder abschalten können.

### 5. Export Pipeline
- Engine exports separate files per layout (e.g., `*_assembled.scad`, `*_flat_sheet01.scad`, plus STLs and PNGs).
- PNG fallback uses layout metadata to render either isometric assembled view or top-down flattened sheets.

## Step-by-Step Implementation
1. **Module scaffolding:** Create `panels.py`, `patterns.py`, `layout.py`. Move relevant code out of `tiled_bin_anchorscad.py`.
2. **Panel generation rewrite:** Floor, wall, rim panels produced as objects with pattern/perforation metadata attached.
3. **Layout manager:** Implement assembled vs. flat transforms, bed packing, sheet metadata.
4. **Engine integration:** Update `oscadforge/core/models/papierkorb.py` to use new layout module and emit separate SCAD/STL/PNG outputs.
5. **Template updates:** Expose YAML knobs (layout mode, bed presets, spacing).
6. **Tests & Docs:** Update CLI integration tests, geometry smoke tests, README with modular layout description.

## Notes
- Modularization is a prerequisite to flattening and multi-layout exports; once the system is split, future extensions (e.g., printer-specific presets, partial reprints) become straightforward.
- OpenGrid/Honeycomb accessories follow panels—critical for flat layout, but also so users can disable them per panel type if needed.

## Status (2024)
- `oscadforge/core/models/papierkorb/panels.py` + `layout.py` liefern die Panel-API inkl. OpenGrid-/Honeycomb-Zuordnung.
- `oscadforge/core/models/papierkorb/__init__.py` exportiert separate Artefakte (`assembled`, `flat sheetNN`) und erzeugt PNG/STL je Layout.
- YAML-Pipelines (z. B. `oscadforge/config/model_papierkorb.yaml` + `oscadforge/config/papierkorb_nohex.yaml`) reichen Layout-Blöcke direkt über den CLI-Merger durch.
- Tests sichern die neue Architektur (`tests/test_engine_core.py::test_flat_layout_produces_sheet_artifacts`), Anchorscad-Makro nutzt dieselben Module.
- Papierkorb nutzt inzwischen die jl_scad-Shell als „Urgeometrie“: Python erzeugt die Tiles via `intersection` + Feature-Booleans, Layout/CLI bleiben unverändert.
