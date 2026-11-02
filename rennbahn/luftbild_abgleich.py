"""Legt den Grundriss aus parameter.json über das Luftbild 1945.
Aufruf: python -P luftbild_abgleich.py <originale> <ausgabe.jpg> [meter_pro_px mitte_x mitte_y]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from PIL import Image, ImageDraw
from geometrie import Bahn, lade_parameter

BILD = "Concordia Rennbahn/Tribüne Rennbahn/1945 Bildschirmfoto_2-9-2025_103219_www.ldbv.bayern.de.jpeg"
AUSSCHNITT = (380, 130, 570, 350)
FAKTOR = 6

P = lade_parameter(Path(__file__).parent / "parameter.json")
b = Bahn(P)
m_px = float(sys.argv[3]) if len(sys.argv) > 3 else 1.2
mx = float(sys.argv[4]) if len(sys.argv) > 4 else 459
my = float(sys.argv[5]) if len(sys.argv) > 5 else 243.5


def nach_px(x, y):
    return ((mx + x / m_px - AUSSCHNITT[0]) * FAKTOR, (my - y / m_px - AUSSCHNITT[1]) * FAKTOR)


with Image.open(Path(sys.argv[1]) / BILD) as im:
    c = im.convert("RGB").crop(AUSSCHNITT)
c = c.resize((c.width * FAKTOR, c.height * FAKTOR), Image.LANCZOS)
d = ImageDraw.Draw(c)
ss = [i * 2.0 for i in range(251)]
for u, farbe in [(0.0, (255, 80, 40)), (1.0, (60, 220, 255))]:
    d.line([nach_px(*b.flaeche(s, u)[:2]) for s in ss], fill=farbe, width=2)
for s in (P["tribuene"]["s_mitte"],):
    d.ellipse([v - 6 for v in nach_px(*b.versetzt(s, 1, 8, 0)[:2])] + [v + 6 for v in nach_px(*b.versetzt(s, 1, 8, 0)[:2])], outline=(255, 255, 0), width=2)
c.save(sys.argv[2], quality=90)

xs = [b.flaeche(s, 1)[0] for s in ss]
ys = [b.flaeche(s, 1)[1] for s in ss]
print(f"Gerade {b.S:.1f} m, Bogen {b.A:.1f} m, Schlussfehler {b.schluss:.3f} m")
print(f"Außenkante: Ausdehnung {max(xs) - min(xs):.1f} x {max(ys) - min(ys):.1f} m")
print(f"Waagrechte Breite Kurve {b.waagrecht(b.h_kurve):.2f} m, Gerade {b.waagrecht(b.h_gerade):.2f} m")
