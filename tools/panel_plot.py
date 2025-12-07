import re
from collections import defaultdict

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

# === Pfad zu deiner generierten SCAD-Datei =====================
SCAD_PATH = "./../../out/opengrid-beam_papierkorb/opengrid-beam_papierkorb.scad"  # <- anpassen!

# Regex: fange Zeilen wie
# module panel_geom_wall_negY_0_1() {
# module panel_geom_floor_0_0() {
mod_re = re.compile(r"module\s+panel_geom_([A-Za-z0-9_]+)\s*\(\)\s*{")

modules = []

with open(SCAD_PATH, "r", encoding="utf-8") as f:
    for line in f:
        m = mod_re.search(line)
        if not m:
            continue
        name = m.group(1)  # z.B. "wall_negY_0_1" oder "floor_0_0"

        parts = name.split("_")
        # Typ + evtl. Richtung + x + y
        if len(parts) == 3:
            # floor_0_0, floorbeam_1_2 ...
            kind, x_str, y_str = parts
            direction = None
        elif len(parts) == 4:
            # wall_posY_0_1, wallbeam_negY_2_3 ...
            kind, direction, x_str, y_str = parts
        else:
            # Unerwartetes Muster – wir überspringen es
            print("Übersprungen (unerwartetes Muster):", name)
            continue

        x = int(x_str)
        y = int(y_str)

        modules.append({
            "raw": name,
            "kind": kind,           # floor / floorbeam / wall / wallbeam ...
            "direction": direction, # posY/negY/posX/negX oder None
            "x": x,
            "y": y,
        })

# Falls nichts gefunden: abbrechen
if not modules:
    raise SystemExit("Keine panel_geom_-Module gefunden.")

# === 3D-Koordinaten ableiten ===========================
# z-Ebene nur zur Visualisierung:
#   floor      -> 0
#   floorbeam  -> 1
#   wall       -> 2
#   wallbeam   -> 3
level_map = defaultdict(lambda: 4)  # unbekannte Typen auf Ebene 4
level_map.update({
    "floor": 0,
    "floorbeam": 1,
    "wall": 2,
    "wallbeam": 3,
})

xs, ys, zs = [], [], []
labels = []      # Textlabel für Tooltip / Debug
kinds = []       # für Legende / Gruppierung

for m in modules:
    xs.append(m["x"])
    ys.append(m["y"])
    zs.append(level_map[m["kind"]])
    kinds.append(m["kind"])
    if m["direction"]:
        labels.append(f"{m['kind']} ({m['direction']}) [{m['x']},{m['y']}]")
    else:
        labels.append(f"{m['kind']} [{m['x']},{m['y']}]")

# === Plot: nach Typ gruppieren, damit Legende sinnvoll ist =====
unique_kinds = sorted(set(kinds))

fig = plt.figure()
ax = fig.add_subplot(111, projection="3d")

for k in unique_kinds:
    idx = [i for i, kk in enumerate(kinds) if kk == k]
    ax.scatter(
        [xs[i] for i in idx],
        [ys[i] for i in idx],
        [zs[i] for i in idx],
        label=k,  # matplotlib vergibt automatisch Farben
        depthshade=True,
    )

ax.set_xlabel("X (Index)")
ax.set_ylabel("Y (Index)")
ax.set_zlabel("Ebene (Typ)")

# z-Ticks benennen
ax.set_zticks([0, 1, 2, 3])
ax.set_zticklabels(["floor", "floorbeam", "wall", "wallbeam"])

ax.legend()
ax.set_title("panel_geom-Module (OpenGrid) – Übersicht")

plt.tight_layout()
plt.show()
