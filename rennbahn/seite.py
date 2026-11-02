"""Schreibt die Maßtabelle aus parameter.json in docs/index.html und kopiert das GLB nach docs/.
Aufruf: python -P seite.py <ordner mit rennbahn.glb>"""
import json
import math
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from geometrie import Bahn, lade_parameter

HIER = Path(__file__).parent
SEITE = HIER.parent / "docs" / "index.html"
P = lade_parameter(HIER / "parameter.json")
with open(HIER / "parameter.json", encoding="utf-8") as f:
    ROH = json.load(f)

HERKUNFT = {
    "belegt": ("belegt", "herkunft--belegt"),
    "luftbild": ("Luftbild", ""),
    "foto": ("Foto", ""),
    "anker": ("Foto", ""),
    "annahme": ("Annahme", "herkunft--annahme"),
}


def m(wert, stellen=None):
    text = f"{wert:g}" if stellen is None else f"{wert:.{stellen}f}"
    return text.replace(".", ",")


def status(teil, name):
    return ROH[teil][name]["status"]


def aussenmass():
    """Länge und Breite der Außenkante entlang der Bahnachse."""
    bahn = Bahn(P)
    az = math.radians(P["bahn"]["azimut"])
    punkte = [bahn.flaeche(i * 2.0, 1) for i in range(251)]
    laengs = [x * math.sin(az) + y * math.cos(az) for x, y, _ in punkte]
    quer = [x * math.cos(az) - y * math.sin(az) for x, y, _ in punkte]
    return max(laengs) - min(laengs), max(quer) - min(quer)


b, z, t, u = P["bahn"], P["zaun"], P["tribuene"], P["turm"]
lang, breit = aussenmass()
GRUPPEN = [
    ("Bahn", [
        ("Länge an der Messlinie", f"{m(b['laenge'])} m", status("bahn", "laenge")),
        ("Fahrbahnbreite", f"{m(b['breite'])} m", status("bahn", "breite")),
        ("Überhöhung, Kurve", f"{m(b['ueberhoehung'], 2)} m", status("bahn", "ueberhoehung")),
        ("Überhöhung, Gerade", f"{m(b['ueberhoehung_gerade'], 1)} m", status("bahn", "ueberhoehung_gerade")),
        ("Kurvenradius", f"{m(b['kurvenradius'])} m", status("bahn", "kurvenradius")),
        ("Außenmaß", f"{lang:.0f} × {breit:.0f} m", status("bahn", "kurvenradius")),
    ]),
    ("Betontribüne", [
        ("Länge eines Rahmens", f"{m(t['laenge'], 1)} m", status("tribuene", "laenge")),
        ("Höhe hinten, vorn", f"{m(t['hoehe_hinten'], 1)} m, {m(t['hoehe_vorn'], 1)} m", status("tribuene", "hoehe_hinten")),
        ("Stütze am Fuß, am Hals", f"{m(t['fuss'], 1)} m, {m(t['hals'], 1)} m", status("tribuene", "fuss")),
        ("Stützendicke", f"{m(t['dicke'], 1)} m", status("tribuene", "dicke")),
        ("Anzahl Rahmen", f"{t['rahmen']}", status("tribuene", "rahmen")),
        ("Abstand der Rahmen", f"{m(t['achsabstand'], 1)} m", status("tribuene", "achsabstand")),
        ("Sitzreihen", f"{t['reihen']}", status("tribuene", "reihen")),
    ]),
    ("Turm", [
        ("Grundfläche", f"{m(u['seite'], 1)} × {m(u['seite'], 1)} m", status("turm", "seite")),
        ("Wandhöhe", f"{m(u['wand'], 1)} m", status("turm", "wand")),
        ("Dachhöhe", f"{m(u['dach'], 1)} m", status("turm", "dach")),
    ]),
    ("Zaun und Wall", [
        ("Zaunhöhe", f"{m(z['hoehe'], 1)} m", status("zaun", "hoehe")),
        ("Höhe der Wallkrone", f"{m(b['wall_krone'], 1)} m", status("bahn", "wall_krone")),
    ]),
]

zeilen = ['<table>', '<thead><tr><th scope="col">Bauteil</th><th scope="col" class="mass">Maß</th><th scope="col">Herkunft</th></tr></thead>']
for gruppe, reihen in GRUPPEN:
    zeilen += ["<tbody>", f'<tr><th scope="rowgroup" colspan="3">{gruppe}</th></tr>']
    for name, wert, st in reihen:
        wort, klasse = HERKUNFT[st]
        klassen = f"herkunft {klasse}".strip()
        zeilen.append(f'<tr><th scope="row">{name}</th><td class="mass">{wert}</td><td class="{klassen}">{wort}</td></tr>')
    zeilen.append("</tbody>")
zeilen.append("</table>")

html = SEITE.read_text(encoding="utf-8")
neu = re.sub(r"(<!-- masse:anfang -->\n).*?(\s*<!-- masse:ende -->)",
             lambda t: t.group(1) + "\n".join("    " + z for z in zeilen) + t.group(2), html, flags=re.S)
SEITE.write_text(neu, encoding="utf-8", newline="\n")
shutil.copyfile(Path(sys.argv[1]) / "rennbahn.glb", SEITE.parent / "rennbahn.glb")
print(f"Tabelle: {sum(len(r) for _, r in GRUPPEN)} Zeilen, Außenmaß {lang:.1f} x {breit:.1f} m")
