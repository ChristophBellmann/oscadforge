# Solar-Bus Engine Primer

Der Zweck dieses Ordners ist identisch mit `setup-strategy.md`:  
*Terminal → Engine → Dateien* zuerst stabilisieren, damit später eine Web-UI einfach dieselbe Engine nutzt.

## Engine-Schicht

- `oscadforge/core/io.py` lädt mehrere YAMLs (z. B. `configs/bus.yaml`, `configs/panels.yaml`) und merged sie rekursiv.
- `oscadforge/core/engine.py` kapselt `build_model(config)` – egal ob Terminal, API oder Browser die Parameter liefern.
- Modelle registrieren sich unter `oscadforge/core/models/*`. Aktuell existiert `papierkorb_tiles`, später folgt `solar_bus`.
- `oscadforge/core/export.py` bündelt Ausgabepfade + OpenSCAD-CLI-Aufruf, damit diese Logik nicht im Modell-Code landet.

## Typischer Flow

**Papierkorb (Bestand):**

```bash
python3 -m oscadforge.oscadforge \
  oscadforge/templates/model_papierkorb.yaml \
  oscadforge/config/export_local.yaml
```

**Solar-Bus-Aufbau (neu, mit STL+PNG Export):**

```bash
python3 -m oscadforge.oscadforge \
  oscadforge/config/bus.yaml \
  oscadforge/config/panels.yaml \
  oscadforge/config/battery.yaml \
  oscadforge/config/wiring.yaml \
  oscadforge/config/mounting.yaml \
  oscadforge/templates/model_solar_bus.yaml \
  oscadforge/config/export_bus.yaml
```

1. CLI merged alle YAMLs in der gegebenen Reihenfolge (letztes gewinnt).  
2. `build_model()` sucht `model.name` → greift auf den Registry-Eintrag (`papierkorb_tiles` oder `solar_bus_roof`).  
3. Das Modell rendert zu `.scad` und – sofern `export.stl/png` aktiv sind – delegiert an die OpenSCAD-CLI, um `.stl` und `.png` zu erzeugen.  
4. Resultate erscheinen unter `export.output_dir` und werden vom Terminal ausgegeben (siehe `oscadforge/oscadforge.py`).

## Warum diese Struktur?

- **Austauschbare UI:** Terminal, REST-API oder WASM können denselben Config-→Engine→Output Weg nutzen.  
- **Kleine Config-Blöcke:** `configs/panels.yaml` beschreibt ausschließlich Panel-Parameter; andere Projekte können denselben Block wiederverwenden.  
- **Späteres Docker/CI:** Weil Engine + CLI keine globalen Zustände besitzen, lässt sich das Ganze später in Docker/CI verpacken, ohne Code zu ändern.

## Nächste Schritte

- HTTP-Layer (FastAPI) aufsetzen, der denselben `build_model()`-Call kapselt.  
- Optional: WASM-Export der anchorscad-Modelle für Browser-Previews.
