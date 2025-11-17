# Gesamtkonzept: Papierkorb-Modularisierung & Flattening

Dieses Dokument bündelt alle Ziele und Pläne rund um den Umbau des Papierkorb-Workflows – von der Modularisierung (Pandoc-Stil) bis zum „Flatten“-Layout auf dem Druckbett.

## Ausgangssituation
- Das aktuelle `tiled_bin_anchorscad.py` erzeugt den montierten Korb als ein monolithisches Objekt.
- STL/PNG zeigen nur die montierte Variante → Wände wirken „schwebend“, Druckbett-Anordnung ist nicht sichtbar.
- Panels (Boden, Wände, Rim) sind nicht separat, daher keine Wiederverwendung oder alternative Layouts möglich.
- OpenGrid/Honeycomb sind global, nicht Panel-gebunden.
- PNG-Fallback ist top-down und zu nah, liefert keinen Überblick.

## Ziele
1. **Modularisierung (Pandoc-Style):**
   - Data (YAML stacks) → CLI → Engine Model.
   - Panels und Connectoren als wiederverwendbare Module, Layout als eigene Komponente.
2. **Dual-Layout (assembled + flat):**
   - Montierte Ansicht bleibt erhalten.
   - Neue „flat sheets“ für Druckbett (Start 200×200 mm, später presets für weitere Drucker).
   - Symmetrische Verteilung, möglichst wenige Sheets, klare Panel-Trennung.
3. **Verbindungs-Features:**
   - Klassische Steckverbinder entfallen; nur die Rim-Kanten und optionalen U-Schenkel (`flange_depth_mm`) liefern mechanische Führung.
   - Paneelöffnungen werden über OpenGrid oder Honeycomb erzeugt und sind direkt im Panel verankert.
4. **Outputs:**
   - Separate SCAD/STL/PNG (optional STEP) pro Layout/SHEET.
   - PNGs zentriert, definierte Perspektive (isometrisch) bzw. Top-Down für flatten.
5. **Konfigurierbarkeit:**
   - `layout.mode`, `layout.bed_mm`, `layout.spacing_mm`, `export.*` etc. aus YAML/Template steuerbar.
6. **Tests & Doku:** Neue Layouts müssen durch CLI/pytest abgedeckt werden; README/Dokumentation beschreibt Modularisierung + Flatten-Workflow.

## Architekturplan

### 1. Panel-Module
- `panels.py`: Panel-Datenklasse (Maker, Typ, Bounding Box, Patternliste).
- Ein Pattern-Helper injiziert optional OpenGrid (24 mm Zellen, 3.2 mm Stege, 12 mm Rand) oder Honeycomb-Bohrungen.
- Jeder Panel ist unabhängig; Layout/Tiling greift darauf zu.

### 2. Layout-Manager
- `layout_mode`: `assembled`, `flat`, `both`.
- Layoutmodul berechnet Transformationsdaten:
  - assembled = original Positionen.
  - flat = Panelrotation (z. B. Wände flach legen), Druckbett-Pack (Gitter + Abstände + Sheets).
- Sheets erhalten Namen/Metadaten (z. B. `sheet01`, bounding box, etc.).

### 3. Engine-Integration
- `tiled_bin_anchorscad.py` reduziert sich auf: Panels aufbauen → Layout anwenden → Maker unionen.
- `oscadforge/core/models/papierkorb.py` sieht nun Layout-Infos und exportiert pro Layout/SHEET.
- PNG-Fallback wählt Layout-spezifische Darstellung (isometrisch assembled, top-down flat).

### 4. YAML/CLI
- YAML-Dateien (`oscadforge/templates/model_papierkorb.yaml`, `oscadforge/config/papierkorb_nohex.yaml`, `oscadforge/config/papierkorb_shell.yaml`, …) enthalten Modellparameter, Layout-Blöcke und Export-Overrides.
- CLI (`oscadforge/oscadforge.py`) deep-mergt beliebig viele Dateien, optional ergänzt durch stdin (`-`). `-o` erzeugt gezielt ein Artefakt, `--result-json` listet die erzeugten Sheets/Metadaten.
- `simple_shell: true` im YAML aktiviert den einteiligen Shell-Korpus (kein Panel-Layout, kein Honeycomb) – praktisch für schnelle Prototypen ähnlich wie im ursprünglichen Einzelkörper-Workflow.

### 5. Tests & QA
- Geometrie-Smoketests prüfen assembled/flat-Bounds.
- CLI-Integration testet `layout_mode=flat` (Sheets, Panelanzahl).
- PNG-Fallback-Vergleich (zentriert, definierte Perspektive).

## Umsetzungsschritte
1. **Dokumentation & Planung (erledigt):**
   - `papierkorb-modularization.md`
   - `papierkorb-flat-layout-plan.md`
2. **Panel-Refactor (WIP):**
   - Panel-Datenklassen, Connector-Bindung.
3. **Layout Engine + Sheets:**
   - assembled/flat transforms, bed packing, 90°-Ecke/180°-Verbinder-Handling.
4. **Template/CLI-Update:**
   - YAML-Felder, CLI-Exports pro Layout.
5. **Tests/Docs neu:**
   - README, CLI-Docs, pytest, PNG-Fallbacks.

## Fazit
Dieser Umbau ist umfangreich, aber essenziell, um die Pandoc-Analogie vollständig zu leben: Daten (YAML) → CLI → Engine Model → Layouts (assembled/flat) → Artefakte (SCAD/STL/PNG/STEP). Sobald die Panel- und Layout-Module stehen, lassen sich weitere Funktionen (z. B. Druckbett-Presets, Teil-Reprints, Parametrische Accessoires) leicht ergänzen.

Seit 2024/10 wird der Papierkorb vollständig über das vendorte `jl_scad`-Shellmodul aufgebaut: Python erzeugt eine jl_scad-Box (inkl. Rim) und die `panel_geom_*`-Module schneiden daraus jedes Tile heraus, addieren Dovetail-/Flansch-Features und wenden anschließend die Layout-Transforms (`multmatrix`) an. Damit bleiben CLI, Tests und der Web-Konfigurator unverändert, obwohl der CAD-Kern jetzt in reinem OpenSCAD/jl_scad lebt.

- Panel-/Layout-Module liegen unter `oscadforge/core/models/papierkorb/` und werden sowohl vom Anchorscad-Makro als auch vom Engine-Builder genutzt.
- YAML/CLI steuern `layout.mode`, `layout.bed_mm`, `layout.spacing_mm`; Flat-Sheets werden als `*_sheetNN.{scad,stl,png}` exportiert.
- PNG-Fallback erzeugt wahlweise isometrische (assembled) oder top-down (flat) Previews auf Basis der neuen Layout-Metadaten.
- Tests/Docs aktualisiert (`tests/test_engine_core.py::test_flat_layout_produces_sheet_artifacts`, diese Datei, Modularization- und Flat-Layou-Plan).
