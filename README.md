# CT eMMC Trace Explorer

Python-Desktop-GUI zum manuellen und experimentell halbautomatischen Markieren von eMMC-Leitungen in CT-Schichtbildern.

## Windows-Start (ohne venv oder WSL)

```powershell
py -m pip install -r requirements.txt
py app.py
```

## Funktionen

- Bildordner laden: PNG, TIFF, JPG, BMP, natürliche Sortierung
- Durch Slices navigieren: Mausrad, Pfeiltasten, Slider
- Zoom mit Strg+Mausrad, Verschieben mit rechter Maustaste
- Transparente Überlagerung der nächsten Schicht
- Markierung von eMMC-Signalen (CLK, CMD, DAT0-DAT7 usw.)
- Halbautomatische lokale Helligkeitsverfolgung über maximal 15 weitere Schichten
- Projekte als JSON speichern/laden; CSV exportieren

**Hinweis:** Die automatische Verfolgung ist experimentell. Gestrichelte Markierungen sind nur Vorschläge und keine nachgewiesenen elektrischen Verbindungen. Die Slices müssen ausgerichtet sein. Eine echte 3D-Rekonstruktion, Via-Erkennung und automatische Leiterbahnsegmentierung sind noch nicht enthalten.
