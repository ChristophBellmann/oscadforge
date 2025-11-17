# Strategie: anchorscad-core + OpenSCAD – mit/ohne Docker

## 1. Aktuelle Ziele

Python+anchorscad+OpenSCAD-CLI-Workflow 

- Modelle **im Terminal** mit **Python + anchorscad-core** erzeugen  
- `.scad` / `.stl` Dateien **lokal speichern**  
- ziel ist Diese Dateien dann mit dem 3D-Drucker verwenden  
- Projektstruktur soll so sein, dass später:
  - eine **Engine-Schicht** (wie in `Solar-Bus-Konfigurator.md`) bleibt
  - eine **Web-UI / Website** leicht darauf aufbauen kann

---

## 2. Soll ich jetzt schon Docker benutzen?

### Empfehlung: **Jetzt noch nicht.**

Für dein jetziges Szenario:

> „Ich sitze an meinem Rechner, starte Python-Skripte, speichere STLs und drucke sie“

ist Docker eher **Ballast**:

- du musst dich um **Volumes** kümmern (`docker run -v ...`), damit die STLs außerhalb des Containers landen  
- `openscad`-CLI im Container, aber Files auf dem Host: zusätzliche Reibung  
- Debugging (Pfadprobleme, Rechte, User-ID etc.) wird komplizierter

Du gewinnst in der frühen Phase **fast nichts**, verlierst aber Komfort.

**Besser:**

1. Lokales Python-Setup (virtuelle Umgebung)  
2. anchorscad-core + OpenSCAD lokal installieren  
3. Engine-API so bauen, dass sie „sauber“ ist (keine komischen globalen Zustände, Pfade als Parameter etc.)

So kannst du schnell iterieren, experimentieren, drucken.  

---

## 3. Warum trotzdem an Docker „denken“?

Später, wenn du:

- eine **Web-API** bauen willst (`/api/OpenSCADForge/render`)  
- oder einen **Konfigurator als Website**  
- oder den Service auf einem Server/VPS laufen lässt

… ist Docker super:

- reproduzierbare Umgebung  
- gleiche Version von Python, anchorscad-core, OpenSCAD  
- leichter deploybar (Docker Compose, Kubernetes, whatever)

**Deshalb:**  
Jetzt **architektonisch darauf vorbereiten**, aber nicht gleich containerisieren.

---

## 4. Konkreter Vorschlag für JETZT (ohne Docker)

### 4.1 Lokale Python-Umgebung

```bash
# Projektverzeichnis

cd oscadforge

# Virtuelle Umgebung
python3 -m venv .venv
source .venv/bin/activate

# Basis-Pakete installieren
pip install --upgrade pip
pip install anchorscad-core pyyaml
# ggf. weitere libs später (numpy, rich, ...)

# OpenSCAD ist installeirt 
usr/local/bin/openscad

genaugenommen: /usr/local/bin/openscad-snapshot 

usage: /usr/local/bin/openscad-snapshot -o out/test.stl in/test.scad

#P rojektstruktur:

oscadforge/
├─ .venv/
├─ core/
│  ├─ __init__.py
│  ├─ engine.py          # anchorscad + openscad logic
│  ├─ export.py
│  └─ settings.yaml     # für core usw...
│  ├─ io.py             # load_config() hier
│  └─ models/
│     ├─ bus.scad
│     ├─ panel.scad
│     └─ ...
├─ configs/
│  ├─ config.yaml       # include: [...]
│  ├─ bus.yaml
│  ├─ panels.yaml
│  ├─ battery.yaml
│  ├─ wiring.yaml
│  ├─ mounting.yaml
│  └─ export.yaml
├─ cli.py                # Terminal interface
├─ web/                  # später: API oder WASM/JS
├─ docs/
│  ├─ Solar-Bus-Konfigurator.md
│  └─ setup-strategy.md
└─ README.md

# Solar-Bus-Konfigurator – Engine-Design (topologische Ebene)

Dieses Dokument beschreibt die **Engine-Schicht** für einen zukünftigen Solar-Konfigurator
(z. B. Solaranlage für einen Bus/Camper), so dass sie zuerst **im Terminal** nutzbar ist
und später relativ einfach in eine **Browser-Webapp** überführt werden kann.

Ziel: Du kannst dieses Dokument 1:1 als Spezifikation in `codex` verwenden.


---

## 1. Zielbild & Topologie

### 1.1 Aktuelle Phase (Terminal)

Topologie:

> **Terminal → Engine → Datei → (Viewer/Browser)**

- Eingaben: CLI-Argumente oder eine Konfigurationsdatei (`.yaml` / `.json`)
- Engine: Python + anchorscad-core + OpenSCAD-CLI
- Output:
  - `.scad` (OpenSCAD-Quelltext)
  - `.stl` (3D-Modell)
  - optional: `.png` (Screenshot/Preview)

Typischer Flow:

1. `config.yaml` definieren (Parameter der Anlage).
2. `python solar_engine.py config.yaml` ausführen.
3. Engine erzeugt `.scad` und `.stl`.
4. Diese Dateien im Viewer oder Browser anschauen.

---

### 1.2 Spätere Phase (Browser/UI)

Topologie (Backend-Variante):

> **Browser (UI) → HTTP-API → Engine → Dateien/Streams → Browser (3D-View)**

oder (WASM-Variante):

> **Browser (UI) → JS → OpenSCAD-WASM → Browser (WebGL/Canvas)**

Wichtig: In beiden Fällen bleibt die **Engine-Schnittstelle logisch identisch**:

> `f(parameter) → Modell`


---

## 2. Datenmodell – Parameter der Solaranlage

### 2.1 Grundidee: Eine zentrale `SolarConfig`

Eine Solaranlage wird über eine Konfiguration beschrieben.

Vorschlag: YAML/JSON-Schema mit folgenden Bereichen:

```yaml
bus:
  length_mm: 6000
  width_mm: 2000
  roof_shape: "flat"          # "flat", "curved", "segmented"
  margin_edge_mm: 50          # Sicherheitsabstand zu Dachkanten

panels:
  type: "standard_120W"       # optional, für später (Datenbank)
  count: 2
  size_mm: [1200, 540, 35]    # [Länge, Breite, Höhe]
  tilt_deg: 0                 # Neigung relativ zur Dachfläche
  layout: "auto_grid"         # "auto_grid", "manual"
  manual_positions: []        # bei "manual": Liste fester Positionen (siehe unten)

battery:
  type: "LiFePO4_100Ah"
  count: 1
  size_mm: [330, 170, 220]
  position: "inside"          # "inside", "underfloor", "custom"
  custom_pos_mm: [0, 0, 0]    # optional für "custom"

wiring:
  entry_point: "rear_left"    # Einführpunkt ins Fahrzeug
  cable_routing: "shortest"   # später ggf. für Visualisierung
  show_cables: false          # ob im 3D-Modell sichtbar

mounting:
  type: "rail"                # "rail", "adhesive", "brackets"
  rail_height_mm: 40
  show_mounting: true

export:
  scad: true
  stl: true
  preview_png: false
  output_dir: "./out"
  basename: "my_solar_setup"

2.2 Erweiterbare Parameter

bus.roof_shape: später für gekrümmte Dächer.

panels.layout: zuerst nur "auto_grid", später "manual", "optimize_sun" usw.

wiring.show_cables: für spätere „schöne“ Visualisierungen.

mounting: kann später detaillierter werden (Bohrlöcher, Profile, Schrauben).

Topologisch wichtig:
Die Engine bekommt immer eine ModelConfig und erzeugt daraus ein Modell.


2.2.1

mehrere .yaml-Dateien  (z. B. für Papierkorb, Bus, Panels, Batterie, Halterungen usw.).

configs/
├─ bus.yaml
├─ panels.yaml
├─ battery.yaml
├─ wiring.yaml
├─ mounting.yaml
└─ export.yaml


Topologische Sicht:

config (Dict) → build_model → EngineResult (Pfad-Objekte)

3.2 CLI-Interface (Terminal)

Script: OSCADForgeShell.py

Terminal → OSCADForgeShell.py → Engine → Dateien

Also: OSCADForgeShell.py soll nur „Hülle“/Shell sein und die eigentliche Engine-Funktion z. B. build_model(config) aufrufen.

Verwendung:

# YAML-Konfig einlesen und Modell generieren
python3 OSCADForgeShell.py mypart.yaml 
python3 OSCADForgeShell.py busconfig.yaml --out ./out --basename bus_solar_01

CLI-Aufgaben: python3 OSCADForgeShell.py 

config.yaml laden (z. B. mit yaml.safe_load).

an build_model(config) übergeben.

Pfade der generierten Dateien ausgeben.
3. Topologisch eingeordnet

Damit hast du genau das Muster:

Terminal → OSCADForgeShell.py → Engine → Dateien

Terminal/UI-Schicht:
OSCADForgeShell.py – kümmert sich nur um:

Argumente

Config laden/mergen

Logging/Output

Engine-Schicht (UI-agnostisch):
oscadforge.core.build_model(config) – macht:

anchorscad-Modelle erzeugen

.scad schreiben

openscad-CLI ausführen

Pfade zurückgeben

Später kannst du:

Dieselbe build_model(config) von einem FastAPI/Flask-Dienst aufrufen

Oder eine WebSocket-/REST-API drum bauen

Oder in Docker einpacken

OSCADForgeShell bleibt dann einfach nur eine von mehreren möglichen Frontends.


5. Antwort auf deine implizite Frage 😉

„wenn cih nun schonaml mit dem terminal anfange, dann habe ich terminal -> engine -> briwser.“

Ja, genau 👍
Und das ist kein Umweg, sondern ein sehr guter Start:

Du trainierst deine Engine-Schnittstelle:

„Welche Parameter brauche ich für eine Solaranlage? Wie beschreibe ich das Modell?“

Später kannst du:

einen HTTP-Wrapper um dieselbe Engine legen

die Logik/Parametrisierung nach JavaScript/WASM spiegeln

oder beides: Server-Engine für „schwere Jobs“, WASM für schnelle Previews

Topologisch ist das alles das gleiche Muster.
Du verschiebst nur, wo UI und Engine laufen.

6. Nächster Schritt

Wenn du Lust hast, können wir als nächstes logisch aufschreiben:

Welche Parameter hätte ein „Solar-im-Bus“-Modell?

Wie sähe eine Funktion aus:
params → SCAD-Text oder params → STL

Das wäre exakt die Engine-Schicht, die du sowohl im Terminal als auch später im Browser ansteuern kannst.

a) Terminal-first (jetzt)

Eingabe: Terminal (Argumente, Config-Dateien, Python-Scripts)
Engine: anchorscad-core + openscad-CLI
Output: STL/SCAD-Dateien
Viewer: optional Browser oder CAD-Programm

Topologie:

3. Die wichtige Erkenntnis: Engine als Mitte designen

Wenn du deine Engine sauber definierst – also etwas wie:

„Nimm Parameter X, Y, Z und gib mir ein Modell / SCAD-Text / STL zurück“

… dann ist es egal, ob die Eingabe von:

einem Terminal-Script kommt

einer Browser-Oberfläche

einem REST-API-Call

Topologisch ist das immer:

[UI / Input] → Engine → [Output / Darstellung]

Und du kannst später die UI austauschen, ohne die Engine anzufassen.

# Topologische Übersicht – Terminal ↔ Engine ↔ Browser

## 1. Was du später willst: Browser ↔ Engine ↔ Browser

Zukünftiges Ziel (Solaranlage im Bus zusammenklicken):

- User klickt / schiebt Sachen im Browser  
- Diese Eingaben gehen zur Engine  
- Die Engine berechnet ein neues Modell  
- Ergebnis wird wieder im Browser angezeigt (Preview, STL-Download, etc.)

**Topologisch:**

> Browser (UI) → Engine → Browser (Anzeige)

Je nach Umsetzung kann die Engine sein:

### a) Im Browser (WASM / openscad-wasm)


Browser-UI → JS → WASM-Engine → Mesh → WebGL / Canvas im Browser

### b) Auf dem Server (klassisch mit openscad-CLI oder anchorscad)

Beides hat dieselbe Topologie:
> UI gibt Parameter rein → Engine rechnet → UI zeigt Resultat.

---

## 2. Was du jetzt machst: Terminal ↔ Engine ↔ (Browser als Viewer)

Wenn du jetzt anfängst nur mit Terminal, ist das im Prinzip:

> Terminal (du tippst) → Engine → Ergebnis-Datei → Browser (oder Viewer) zeigt sie

Konkreter Ablauf:

```bash
python script.py ...    # anchorscad-core generiert .scad
openscad -o out.stl in.scad  # Engine (Rendering)
out.stl im Browser-Viewer / CAD-Programm / 3D-Viewer öffnen


Das ist konzeptionell sehr nah an deinem späteren Web-Setup –
nur dass der „UI-Part“ jetzt eben das Terminal ist und die Ausgabe eine Datei, nicht direkt eine WebGL-Scene.
