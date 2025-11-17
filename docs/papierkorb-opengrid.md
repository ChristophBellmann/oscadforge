# Papierkorb OpenGrid Layout

This note tracks the parameters that drive the new OpenGrid flavour of the Papierkorb panels.
The goals are:

- keep the legacy 514 × 170 × 605 mm outer dimensions,
- arrange panels/tiles so every flattened sheet fits the 200 × 200 mm Ultimaker 2 bed,
- replace the previous honeycomb perforation with a square OpenGrid pattern that can be tuned
  per printer (cell, strut, margin).

## Default Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `opengrid_cell_mm` | 24.0 | 24 mm clear opening aligns with the published OpenGrid sheet spec and stays divisible by a 0.4 mm nozzle width. |
| `opengrid_bar_mm` | 3.2 | Eight extrusion lines ≈3.2 mm deliver stiff struts while wasting little infill. |
| `opengrid_margin_mm` | 12.0 | Keeps the pattern away from edges/rims, leaving room for pins and the top flange. |

Additional notes:

- `enable_opengrid` automatically injects rectangular holes into floor and wall panels.
- Honeycomb remains available, but `papierkorb_opengrid.yaml` disables it so the two patterns do not clash.
- Margins/spacing guarantee that even the tallest wall tiles flatten without exceeding the 200 mm bed.

## Generating the SCAD

```bash
python3 -m oscadforge.oscadforge \
  oscadforge/templates/model_papierkorb.yaml \
  oscadforge/config/papierkorb_opengrid.yaml
```

Outputs land in `out/papierkorb/opengrid/` as:

- `papierkorb_opengrid.scad` (assembled view),
- `papierkorb_opengrid_sheetNN.scad`/`.png` for each Ultimaker sheet.

Use `--dry-run` to inspect the merged YAML before building, and pass `--openscad-bin` if you want STL/PNG renders from a custom OpenSCAD executable.
