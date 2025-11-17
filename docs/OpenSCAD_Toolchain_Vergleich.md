# Vergleich moderner OpenSCAD- und Lasercut-Tools

## Übersicht
Diese Datei vergleicht die wichtigsten Bibliotheken und Tools für parametrische 3D- und 2D-Modellierung
im OpenSCAD- und Python-Umfeld — mit Fokus auf Elektronikgehäuse, DIY-Mechanik und Lasercut-Projekte.

---

## 🔧 Kurzbeschreibung

| Tool | Sprache / Umgebung | Hauptzweck | Schwerpunkt |
|:--|:--|:--|:--|
| **Boxes.py** | Python 3, optional Inkscape | 2D-Lasercut-Vorlagen | Boxen, Platten, Finger-Joints |
| **Lasercut** | OpenSCAD + Python Scripts | 2D + 3D Lasercut‑Konstruktionen | Finger‑Joints, Tabs, Clips |
| **BOSL2** | OpenSCAD Library | 3D Geometrie‑/Konstruktionsbibliothek | Formen, Rounding, Attachments |
| **jl_scad** | OpenSCAD Library (BOSL2‑basiert) | Elektronik‑Gehäusegenerator | Deckel, Platinenhalter, Schrauben |
| **AnchorSCAD** | Python → SCAD‑Generator | 3D‑Modellierung in Python | Objektorientierte Geometrie, Anchors |

---

## 🧩 Technologische Merkmale

| Kategorie | **Boxes.py** | **Lasercut** | **BOSL2** | **jl_scad** | **AnchorSCAD** |
|:--|:--|:--|:--|:--|:--|
| Sprache | Python 3 | OpenSCAD + Python | OpenSCAD | OpenSCAD | Python |
| Paradigma | 2D‑Parameter‑Design | 2D + 3D CAD‑Kombination | CAD‑Bibliothek | Gehäuse‑Spezialbibliothek | Python‑Objektmodell |
| Primärer Fokus | Laserschneiden | Lasercut‑Teile in 3D | Geometrie‑Tools | Elektronik‑Boxen | Python‑basiertes CAD |
| OpenSCAD‑Abhängigkeit | Optional | Ja | Ja | Ja (BOSL2 nötig) | Generiert SCAD |
| 3D‑Fähigkeit | ✗ | ✓ | ✓ | ✓ | ✓ |
| 2D‑Export | ✓ (SVG/DXF) | ✓ | ✗ | ✗ | ✗ |
| Mechanische Features | Finger‑Joints, Hinges | Tabs, Clips | Schrauben, Lager | Platinenhalter, Deckel | Beliebig erweiterbar |
| Lernkurve | Niedrig | Mittel | Hoch | Mittel | Mittel‑Hoch |
| Lizenz | GPL‑3.0 | BSD‑2 | BSD‑2 | BSD‑2 | MIT |
| Community | Groß | Klein‑Mittel | Sehr groß | Klein | Klein‑Wachsend |

---

## 🧠 Wann welches Tool?

| Ziel / Use‑Case | Empfehlung |
|:--|:--|
| **Schnelle 2D‑Box oder Lasercut‑Platte** | 🟢 Boxes.py |
| **3D‑Lasercut‑Assembly in OpenSCAD** | 🟢 Lasercut |
| **Parametrische 3D‑Konstruktion allgemein** | 🟢 BOSL2 |
| **Elektronik‑Box mit Schrauben, Deckel, PCB‑Halter** | 🟢 jl_scad |
| **Python‑gesteuerte 3D‑Generierung (z. B. Varianten, Automatisierung)** | 🟢 AnchorSCAD |

---

## 💡 Empfehlung für Elektronik‑/DIY‑Entwickler

| Ziel | Empfohlene Kombination |
|:--|:--|
| Elektronikgehäuse + schnelle Prototypen | **jl_scad + BOSL2** |
| Komplexe Mechanik, Halter, Geometrie‑Tools | **BOSL2 solo** |
| Automatisierte Gehäusevarianten via Skript | **AnchorSCAD + BOSL2** |
| Lasercut‑Platten oder Acryl‑Wände | **Boxes.py** oder **Lasercut** |

---

© 2025 – Technologischer Vergleich von OpenSCAD‑Toolchains (erstellt für MCOIH)
