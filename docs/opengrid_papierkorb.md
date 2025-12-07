# Papierkorb (opengrid_papierkorb) Variant

This variant rebuilds the Papierkorb panels with the official OpenGrid sources so that
tiles, snaps, and 90° connectors stay compatible with the ecosystem maintained by
David D., Hands on Katie, and the QuackWorks contributors.

## Source References

- **Panels & Snaps:** `third_party/QuackWorks/openGrid/openGrid.scad` and
  `third_party/QuackWorks/openGrid/opengrid-snap.scad` (Andy “BlackjackDuck” Levesque).
- **Right-angle connectors:** extracted Printables pack under `in/opengrid_angle/`
  (currently using the `1-1_1x` STL as the default sleeve footprint for the connector sheet).
- **Printables archive:** `in/opengrid_printables/...` keeps the STEP/3MF references that shipped with the
  original Printables release for cross-checking hole placement.

All of the above assets are CC BY-NC-SA; we merely parameterise them through the oscadforge CLI. This backend is implemented in `oscadforge/core/models/opengrid_papierkorb` (previously named `opengrid_2`), and the CLI exposes the same builder under `opengrid_papierkorb` and the new `opengrid-beam_papierkorb` alias (see `oscadforge/config/opengrid_beam_papierkorb.yaml`).

## Workflow Summary

1. Run the new model:
   ```bash
   python3 -m oscadforge.oscadforge \
     oscadforge/config/opengrid_papierkorb.yaml
   ```
   Für die gekürzte OpenGrid-Full-Variante tausche denselben Config-Stack gegen
   `oscadforge/config/papierkorb_opengrid.yaml` oder eine Custom-Override-Datei aus. Der Export
   liefert STEP/PNG direkt unter `out/opengrid_papierkorb_freecad/`; wenn du nur
   SCAD/PNG brauchst, setze `export.step: false` (z. B. via Inline-Override) und
   starte denselben Befehl erneut.
2. The CLI snaps the requested Papierkorb dimensions to the closest OpenGrid multiple of the
   configured tile size (default 28 mm). This guarantees that every seam lands on an actual
   OpenGrid connector line.
3. Each panel tile is emitted as a JL-free OpenGrid board (`Full`, `Lite`, or `Heavy`) with
   matching connector slots.
4. Layout output:
   - `*_assembled.scad` — assembled Papierkorb with OpenGrid tiles.
   - `*_sheetNN.scad` — flattened tiles that stay within the chosen bed (default 200×200 mm).
  - `*_connectors.scad` — accessory sheet containing the required straight snaps plus
    simple 90° corner sleeves sized to the OpenGrid pitch (swap in your preferred
    Monokini/Underware design later if you need the exact ecosystem geometry).

## Parameters

```yaml
model:
  name: opengrid_papierkorb
  params:
    bin:
      length_mm: 514.0          # original request
      width_mm: 170.0
      height_mm: 605.0
      max_tile_mm: 200.0        # sliced so Ultimaker beds are respected
      dimension_rounding: nearest   # snap to nearest OpenGrid cell count
    board:
      variant: Full             # Full | Lite | Heavy
      tile_size_mm: 28.0
      chamfers: Corners
      screw_mounting: None
      connector_holes: true
    connectors:
      snap_variant: lite        # forward to openGridSnap()
      directional_snaps: false
      include_floor_edges: true # adds Monokini L-channels for the floor
```

The resulting geometry keeps the OpenGrid cell pitch intact. If you need the original
dimensions, set `dimension_rounding` to `ceil`/`floor` and adjust the source measurements,
but remember that third-party snaps will only fit when the grid still equals 28 mm.

## Outputs & Counts

The metadata written into `EngineResult.metadata["connectors"]` lists how many straight
snaps (`openGridSnap`) and 90° connectors (`monokini_L_channel`) were generated so you
can re-use them outside of the Papierkorb context.
