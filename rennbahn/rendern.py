"""Rendert Ansichten der Rennbahn für den Vergleich mit den Originalfotos.
Aufruf: blender -b rennbahn.blend --python-exit-code 1 --python rendern.py -- <ordner> <breite> <samples> [ansicht ...]
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).parent))
from geometrie import Bahn, lade_parameter

args = sys.argv[sys.argv.index("--") + 1:]
AUS, BREITE, SAMPLES, WAHL = Path(args[0]), int(args[1]), int(args[2]), args[3:]
P = lade_parameter(Path(__file__).parent / "parameter.json")
bahn = Bahn(P)
T = P["tribuene"]
sm = T["s_mitte"]


def f(s, u, dz=0.0):
    x, y, z = bahn.flaeche(s, u)
    return (x, y, z + dz)


def tribuene(x, z, y=0.0):
    ox, oy, _ = bahn.versetzt(sm, 1, T["abstand_zaun"], 0)
    nx, ny = bahn.aussen_richtung(sm)
    tx, ty = bahn.tangente(sm)
    return (ox + nx * x + tx * y, oy + ny * x + ty * y, z)


def blick(von, rechts, runter):
    """Zielpunkt für einen Blick nach Norden entlang der Westgeraden, gedreht und geneigt in Grad.
    Die Winkel kommen aus dem Fluchtpunkt von Zaun und Innenkante im jeweiligen Foto."""
    tx, ty = bahn.tangente(bahn.L / 2)
    nx, ny = bahn.aussen_richtung(bahn.L / 2)
    r = math.tan(math.radians(rechts))
    return (von[0] + (-tx - nx * r) * 100, von[1] + (-ty - ny * r) * 100,
            von[2] - math.tan(math.radians(runter)) * 100 * math.hypot(1, r))


ANSICHTEN = {
    # Blick nach Norden über die Westgerade, Fluchtpunkt der Rahmen wie im Foto nahe dem vorderen Bein
    "gerippe": dict(von=tribuene(1.5, 1.4, 45), nach=tribuene(7, 2.8), linse=62, format=1.5,
                    weg=("bahn", "zaun", "holzbank", "turm", "innenfeld", "wall")),
    "thalbach3": dict(von=f(338, 0.45, 2.0), nach=blick(f(338, 0.45, 2.0), -11, 7.2), linse=60, format=1.45),
    "bild0078": dict(von=bahn.versetzt(280, 1, 0.5, 9), nach=blick(bahn.versetzt(280, 1, 0.5, 9), 26, 11.3),
                     linse=30, format=1.56),
    "kurve": dict(von=f(170, 0.25, 1.5), nach=f(118, 0.55, 1.0), linse=80, format=1.5),
    "karte": dict(von=(25, 190, 38), nach=(-5, 5, 0), linse=30, format=1.6),
}


def licht():
    welt = bpy.data.worlds.new("himmel")
    nt = welt.node_tree
    nt.nodes.clear()
    hg = nt.nodes.new("ShaderNodeBackground")
    hg.inputs["Color"].default_value = (0.78, 0.78, 0.78, 1)
    hg.inputs["Strength"].default_value = 0.9
    nt.links.new(hg.outputs["Background"], nt.nodes.new("ShaderNodeOutputWorld").inputs["Surface"])
    bpy.context.scene.world = welt

    sonne = bpy.data.lights.new("sonne", "SUN")
    sonne.energy = 3.0
    sonne.angle = math.radians(2)
    ob = bpy.data.objects.new("sonne", sonne)
    bpy.context.scene.collection.objects.link(ob)
    # Sonne im Westsüdwesten: Der Zaun wirft in Thalbach-3 und 13-01-0026 Schatten auf die Bahn
    ob.rotation_euler = Vector((-0.7, -0.45, 0.8)).to_track_quat("Z", "Y").to_euler()


def kamera(a):
    daten = bpy.data.cameras.new("kamera")
    daten.lens = a["linse"]
    daten.clip_end = 2000
    ob = bpy.data.objects.new("kamera", daten)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = a["von"]
    ob.rotation_euler = (Vector(a["nach"]) - Vector(a["von"])).to_track_quat("-Z", "Y").to_euler()
    return ob


szene = bpy.context.scene
szene.render.engine = "CYCLES"
szene.cycles.samples = SAMPLES
szene.cycles.use_denoising = True
szene.view_settings.view_transform = "Standard"
szene.render.image_settings.file_format = "PNG"
licht()
AUS.mkdir(parents=True, exist_ok=True)

for name, a in ANSICHTEN.items():
    if WAHL and name not in WAHL:
        continue
    for ob in bpy.data.objects:
        if ob.type == "MESH":
            ob.hide_render = ob.name in a.get("weg", ())
    szene.camera = kamera(a)
    szene.render.resolution_x = BREITE
    szene.render.resolution_y = round(BREITE / a["format"])
    szene.render.filepath = str(AUS / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"GERENDERT {name}")
