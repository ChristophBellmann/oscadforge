# Konzept: SCAD → STEP mit geometrischer Duplikat-Erkennung

Dieses Dokument beschreibt ein allgemeines, systemunabhängiges Verfahren, um eine Vielzahl von OpenSCAD-Dateien automatisiert in STEP-Dateien zu überführen.  
Das Verfahren erkennt dabei geometrisch identische Modelle und vermeidet redundante STEP-Erzeugungen.

Das Dokument enthält **keinen Code**, nur die abstrakte Logik.

---

## 1. Zielsetzung

- Jede SCAD-Datei soll eine gleichnamige STEP-Datei erhalten.
- Wenn zwei oder mehr SCAD-Dateien tatsächlich dasselbe 3D-Modell erzeugen, soll die STEP-Datei nur **ein einziges Mal** berechnet werden.
- Nicht-repräsentative Dateien sollen mittels **Verweis oder Symlink** auf die STEP-Datei des repräsentativen Modells zeigen.
- Die Erkennung von Duplikaten soll **geometriebasiert** erfolgen, nicht durch einfachen Textvergleich.

---

## 2. Grundprinzipien

### 2.1 SCAD → CSG

Jede SCAD-Datei wird zunächst durch OpenSCAD in ein CSG-Format überführt.

Der CSG-Baum:

- repräsentiert die *konstruktive Struktur* des Modells,
- ist unabhängig von Formatierung, Kommentaren oder Schreibweisen,
- eignet sich ideal für die Erkennung von echten geometrischen Duplikaten.

### 2.2 Hashing des CSG-Baums

Der Inhalt des CSG-Baums wird in eine Prüfgröße (z. B. einen Hashwert) überführt.

Ziel:

- **Identische CSG-Bäume ergeben denselben Hashwert.**
- Unterschiede im Modell führen zu unterschiedlichen Hashwerten.

Damit können Modelle eindeutig gruppiert werden.

### 2.3 Gruppierung identischer Modelle

Alle SCAD-Dateien mit identischem CSG-Hash bilden eine Gruppe:

- Eine Gruppe steht für eine konkrete Modellgeometrie.
- Die Reihenfolge, Schreibweise oder Struktur der SCAD-Dateien ist irrelevant.
- Jede Gruppe benötigt genau **eine** STEP-Datei.

---

## 3. STEP-Erzeugung

### 3.1 Repräsentant pro Gruppe

Für jede Gruppe wird eine Datei als Vertreter ausgewählt.

Ein STEP-Konverter (z. B. `csg2step`) erzeugt daraus:

- eine *.step*-Datei,
- basierend ausschließlich auf der tatsächlichen Geometrie.

### 3.2 Verweise auf den Repräsentanten

Alle weiteren SCAD-Dateien derselben Gruppe referenzieren die erzeugte STEP-Datei:

- über Symlink,
- über symbolischen Verweis,
- oder über ein anderes verwendetes Referenzierungssystem.

Damit erhält jede SCAD-Datei formal eine STEP-Datei, ohne zusätzliche Berechnungen.

---

## 4. Ablaufübersicht

1. Alle SCAD-Dateien im Zielverzeichnis erfassen.
2. Jede SCAD-Datei in eine CSG-Darstellung überführen.
3. Aus jeder CSG-Datei eine eindeutige geometrische Kennung ableiten.
4. Dateien nach identischer Geometrie gruppieren.
5. Für jede Gruppe:
   - eine STEP-Datei erzeugen,
   - die anderen Dateien auf diese verweisen lassen.
6. Ergebnis:  
   Für jede SCAD-Datei existiert eine zugehörige STEP-Datei,  
   aber die STEP-Erzeugung erfolgt nur einmal pro Modellgeometrie.

---

## 5. Vorteile

- **Hohe Effizienz** — STEP wird nur einmal pro Geometrie berechnet, nicht pro Datei.
- **Robuste Identifikation** — Geometrische Gleichheit bleibt auch bei unterschiedlichen Parameternamen, Formatierungen oder SCAD-Schreibweisen erhalten.
- **Skalierbarkeit** — Ideal für große parametrische Projekte mit vielen Varianten oder Sheets.
- **Kompatibilität** — STEP-Dateien sind mit jedem CAD-System nutzbar.

---

## 6. Erweiterungen (optional)

- Parallelisierung der STEP-Erzeugung für große Datenmengen.
- Parametrische Analyse ähnlicher Dateien (nicht nur identischer).
- Automatische Assembly-Erkennung.
- Erzeugung eines Struktur- oder Baumdiagramms der gesamten SCAD-Projektarchitektur.
- Multi-Cache-System über verschiedene Projektordner hinweg.

## 7. Referenz-Konfigurationen

- `oscadforge/config/export_papierkorb_step_freecad_dedup.yaml` — nutzt OpenSCAD → CSG → FreeCAD, aktiviert `step_dedup`, schreibt SCAD/STL/STEP und cached die STEP-Dateien unter `out/.step_cache_freecad/`.
- `oscadforge/config/export_step_dedup.yaml` — allgemeines Beispiel für das OpenSCAD → CSG → FreeCAD-Backend inklusive Hash-Cache (`step_backend: freecad_csg`), reduziert auf STEP-Exports ohne zusätzliche STL-Ausgabe.

---

Dieses Dokument beschreibt ein abstraktes, systemunabhängiges Konzept zur effizienten Überführung großer Mengen von SCAD-Dateien in STEP-Dateien unter Berücksichtigung von Duplikaten.
