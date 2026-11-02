"""Stellt Renders neben die Originalfotos, beide in Graustufen.
Aufruf: python -P vergleich.py <originale> <renderordner> <ausgabeordner> [ansicht ...]"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

Image.MAX_IMAGE_PIXELS = None
ORIG, RENDER, AUS = map(Path, sys.argv[1:4])
WAHL = sys.argv[4:]
AUS.mkdir(parents=True, exist_ok=True)
T = "Concordia Rennbahn/Tribüne Rennbahn/"
B = "Concordia Rennbahn/Bauweise Rennbahn/"
# Ausschnitt als Anteile des Originals, damit Rahmen und Beschriftung wegfallen
PAARE = {
    "thalbach3": (T + "Rennbahn Thalbach-3.jpg", (0.12, 0.15, 0.88, 0.80)),
    "gerippe": (T + "Concordia Tribühne Gerippe.jpg", (0.10, 0.0, 0.86, 0.74)),
    "bild0078": (B + "Toni Fischer Fotos-Band Rot Bild-0078.jpg", (0, 0, 1, 1)),
    "kurve": (B + "13-01-0015.jpg", (0.01, 0.01, 0.99, 0.99)),
    "karte": (B + "00000072klein.jpg", (0.03, 0.04, 0.97, 0.70)),
}
HOEHE = 760
schrift = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)

for name, (rel, box) in PAARE.items():
    if WAHL and name not in WAHL:
        continue
    with Image.open(ORIG / rel) as im:
        w, h = im.size
        links = im.convert("L").crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))
    rechts = Image.open(RENDER / f"{name}.png").convert("L")
    bilder = [ImageOps.autocontrast(i, cutoff=0.5) for i in (links, rechts)]
    bilder = [i.resize((round(i.width * HOEHE / i.height), HOEHE), Image.LANCZOS) for i in bilder]
    bogen = Image.new("RGB", (bilder[0].width + bilder[1].width + 20, HOEHE + 40), "white")
    bogen.paste(bilder[0], (0, 40))
    bogen.paste(bilder[1], (bilder[0].width + 20, 40))
    d = ImageDraw.Draw(bogen)
    d.text((8, 10), f"Original: {Path(rel).name}", fill="black", font=schrift)
    d.text((bilder[0].width + 28, 10), f"Modell: {name}", fill="black", font=schrift)
    bogen.save(AUS / f"{name}.jpg", quality=88)
    print(AUS / f"{name}.jpg")
