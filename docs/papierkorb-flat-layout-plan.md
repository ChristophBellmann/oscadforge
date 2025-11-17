# Papierkorb Flattening & Layout Plan

Dieses Dokument fasst die Anforderungen und Schritte zusammen, die wir aus unseren Diskussionen herleiten. Ziel ist, den Papierkorb so umzubauen, dass:
- STL/SCAD/PNG wahlweise die montierte Version **und** ein „flach ausgelegtes“ Layout zeigen,
- jede Platte (Boden, Wände, Rim) echte Panels sind (inkl. OpenGrid/Honeycomb),
- Druckbettgrenzen eingehalten werden (Start mit 200×200 mm, später erweiterbar),
- PNG-Previews zentriert und perspektivisch sinnvoll aussehen (keine „schwebenden“ Wände mehr).

## Aktuelle Probleme
1. STL/PNG zeigen nur die montierte Version → Wände wirken „schwebend“ und die Druckbett-Anordnung ist nicht sichtbar.
2. Panels sind nicht isoliert, sodass wir sie weder rotiert noch umpositioniert ausgeben können.
3. OpenGrid/Honeycomb/Rim sind global angebracht; beim Flatten würden sie nirgends „mitwandern“.
4. PNG ist zu nah dran, ohne Achs-/Layout-Kontext.

## Anforderungen

### Layout & Druckbett
- Standard-Bett: 200 × 200 mm (Ultimaker), später weitere Presets.
- Layout soll möglichst wenige Sheets benötigen; Panels symmetrisch verteilen.
- An Panelgrenzen muss eine sichtbare Trennung sein (keine „krummen“ restlichen Panels).
- Montierte und flache Variante separat ausgeben (z. B. `assembled.scad/.stl`, `flat_sheet01.stl`, …).
- PNGs: zentriert, definierte Perspektive, nicht zu stark gezoomt.

### Panels & Muster
- Boden-/Wand-/Rim-Kacheln als eigenständige Panel-Objekte; OpenGrid/Honeycomb hängen direkt an diesen Panels.
- Rim-Streifen sollen weiterhin 90°-Eckverbinder bekommen, optionale U-Schenkel (`flange_depth_mm`) sichern die langen Seiten.

### Template/CLI/YAML
- YAML soll Bettgröße/Spacing/Layout steuern: `layout.mode`, `layout.bed_mm`, `layout.spacing_mm`, etc.
- Template generiert nur noch Panelparametrisierung (Abmessungen, Layout-Flags).
- CLI/Engine exportieren pro Layout die gewünschten Dateien (SCAD, STL, PNG optional STEP).

## Umsetzungsschritte
1. **Panel-API:** Boden-, Wand-, Rim-Panels mit eigener Maker-Geometrie, Bounding Box, Zubehörlisten.
2. **Pattern-/Flange-Module:** OpenGrid/Honeycomb und optionale Flansche zu Panels zuordnen, damit sie zusammen mit dem Panel flatten.
3. **Layout-Engine:**
   - `assembled`: wie bisher (Panels an ihren realen Positionen).
   - `flat`: Panels (ggf. mehrere Sheets) auf Druckbett-Raster legen, Wände rotieren, Symmetrie wahren.
   - `layout_mode`: `assembled`, `flat`, `both`.
4. **Export & CLI:** Separates SCAD/STL/PNG/STEP pro Layout/Sheet, optional JSON-Ergebnis mit Sheet-Liste.
5. **PNG-Fallback:** isometrische Ansicht zentriert, definierter Abstand; für flat ggf. top-down Raster.
6. **Tests/Doku:** CLI-Integration, Layoutfakten (Panel-Anzahl, Betteinhaltung), README/Docs aktualisieren.

## Hinweis
Der Umbau ist umfangreich (mehrere hundert Zeilen). Wir gehen iterativ vor:
1. Panels + Accessoires modularisieren.
2. Layout-Manager implementieren.
3. Template/CLI/YAML, Export/PNG, Tests aktualisieren.

## Umsetzungsstand
- `oscadforge/core/models/papierkorb/panels.py` kapselt Boden-, Wand- und Rim-Panels inklusive OpenGrid/Honeycomb.
- `oscadforge/core/models/papierkorb/layout.py` berechnet `assembled`- und `flat`-Platzierungen und packt automatische Sheets (Standard 200×200 mm, konfigurierbar).
- Der Engine-Builder erzeugt pro Layout eigene Artefakte (`basename.scad` für montiert, `basename_sheetNN.scad`/`*.png` für flat). Die YAML/CLI steuern das über `model.layout.mode|bed_mm|spacing_mm`.
- `tiled_bin_anchorscad.py` nutzt dieselben Module, damit Anchorscad-CLI und oscadforge-Engine identische Panels teilen.
- Tests (`tests/test_engine_core.py::test_flat_layout_produces_sheet_artifacts`) sichern ab, dass Flat-Sheets ausgegeben werden.
