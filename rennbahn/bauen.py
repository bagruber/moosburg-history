"""Erzeugt die Rennbahn aus parameter.json und speichert rennbahn.blend und rennbahn.glb.
Aufruf: blender -b --factory-startup --python-exit-code 1 --python bauen.py -- <ausgabeordner>
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from geometrie import Bahn, lade_parameter

AUS = Path(sys.argv[sys.argv.index("--") + 1])
P = lade_parameter(Path(__file__).parent / "parameter.json")
bahn = Bahn(P)
bpy.ops.wm.read_factory_settings(use_empty=True)
rng = np.random.default_rng(1925)
Z = (0.0, 0.0, 1.0)
SCHRITT = 2.0
SS = [i * SCHRITT for i in range(round(bahn.L / SCHRITT) + 1)]
KACHEL_BAHN = 6.0
KACHEL_PLANKE = (2.4, 1.3)


# --- Texturen und Materialien ---

def rauschen(h, w, staerke):
    """Kachelbares Rauschen: wiederholt mit dem eigenen Versatz gemittelt."""
    n = rng.random((h, w))
    for ax, schritte in ((0, 4), (1, 12)):
        for k in range(schritte):
            n = (n + np.roll(n, 1 + k, axis=ax)) / 2
    return (n - n.mean()) / (n.std() + 1e-6) * staerke


def bild(name, grau, tint=(1, 1, 1)):
    h, w = grau.shape
    rgba = np.ones((h, w, 4), np.float32)
    for k in range(3):
        rgba[..., k] = np.clip(grau * tint[k], 0, 1)
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(rgba.ravel())
    img.pack()
    return img


def textur_bahn():
    h, w = 256, 1024
    d = 0.80 + rauschen(h, w, 0.006)
    for v in (0.25, 0.5, 0.75):
        d[int(v * h), :] *= 0.95
    for u in (0, w // 2):
        d[:, u:u + 3] *= 0.6
    for v, dick, grau in ((0.12, 2, 0.4), (0.35, 2, 0.6)):
        a = int(v * h)
        d[a:a + dick, :] = grau
    return bild("bahn", d)


def textur_planken():
    h, w = 128, 1024
    planken = 20
    d = np.zeros((h, w))
    breite = w // planken
    for i in range(planken):
        d[:, i * breite:(i + 1) * breite] = rng.uniform(0.34, 0.5)
        d[:, i * breite:i * breite + 3] = 0.12
    return bild("planken", d + rauschen(h, w, 0.015), (1.0, 0.92, 0.8))


def material(name, farbe=None, textur=None, rauheit=0.9):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    aus = nt.nodes.new("ShaderNodeOutputMaterial")
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Roughness"].default_value = rauheit
    if textur:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = textur
        nt.links.new(t.outputs["Color"], p.inputs["Base Color"])
    else:
        p.inputs["Base Color"].default_value = (*farbe, 1)
    nt.links.new(p.outputs["BSDF"], aus.inputs["Surface"])
    return m


PLANKEN = textur_planken()
M_BAHN = material("bahn", textur=textur_bahn())
M_KIES = material("kies", (0.42, 0.40, 0.36))
M_GRAS = material("gras", (0.09, 0.12, 0.06))
M_ERDE = material("erde", (0.16, 0.14, 0.10))
M_BODEN = material("boden", (0.20, 0.20, 0.13))
M_ZAUN = material("zaun", textur=PLANKEN)
M_WEISS = material("tafel", (0.75, 0.74, 0.70))
M_BETON = material("beton", (0.48, 0.46, 0.42))
M_HOLZ = material("holz", (0.17, 0.13, 0.09))
M_TURM = material("turm", textur=PLANKEN)
M_DACH = material("dach", (0.30, 0.28, 0.24))
M_DUNKEL = material("dunkel", (0.015, 0.015, 0.015))


# --- Netzbau ---

class Netz:
    def __init__(self):
        self.v, self.f, self.uv, self.m = [], [], [], []

    def flaeche(self, punkte, uv=None, mat=0):
        i = len(self.v)
        self.v.extend(punkte)
        self.uv.extend(uv or [(0, 0)] * len(punkte))
        self.f.append(list(range(i, i + len(punkte))))
        self.m.append(mat)

    def band(self, spalten, uv=None, mat=None):
        """spalten[j][i]: Querschnitt j entlang der Bahn, Punkt i im Querschnitt."""
        start = len(self.v)
        ni = len(spalten[0])
        for j, sp in enumerate(spalten):
            self.v.extend(sp)
            self.uv.extend(uv[j] if uv else [(0, 0)] * ni)
        for j in range(len(spalten) - 1):
            for i in range(ni - 1):
                a = start + j * ni + i
                self.f.append([a, a + 1, a + ni + 1, a + ni])
                self.m.append(mat(j, i) if mat else 0)

    def quader(self, m, achsen, masse, mat=0, kachel=None):
        """m: Mittelpunkt, achsen: rechtshändig und senkrecht, masse: Kantenlängen."""
        ax, ay, az = achsen
        sx, sy, sz = (masse[0] / 2, masse[1] / 2, masse[2] / 2)

        def ecke(i, j, k):
            return tuple(m[n] + i * sx * ax[n] + j * sy * ay[n] + k * sz * az[n] for n in range(3))

        seiten = [
            ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)),
            ((-1, 1, -1), (-1, -1, -1), (-1, -1, 1), (-1, 1, 1)),
            ((1, 1, -1), (-1, 1, -1), (-1, 1, 1), (1, 1, 1)),
            ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)),
            ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)),
            ((-1, 1, -1), (1, 1, -1), (1, -1, -1), (-1, -1, -1)),
        ]
        for n, s in enumerate(seiten):
            uv = None
            if kachel:
                waagrecht = 1 if n < 2 else 0
                groesse = (sx, sy)[waagrecht]
                uv = [(e[waagrecht] * groesse / kachel[0], e[2] * sz / kachel[1]) for e in s]
            self.flaeche([ecke(*e) for e in s], uv, mat)


def objekt(name, netz, materialien, glatt=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(netz.v, [], netz.f)
    me.update()
    schicht = me.uv_layers.new(name="UVMap")
    idx = [0] * len(me.loops)
    me.loops.foreach_get("vertex_index", idx)
    schicht.uv.foreach_set("vector", [w for i in idx for w in netz.uv[i]])
    me.polygons.foreach_set("material_index", netz.m)
    for m in materialien:
        me.materials.append(m)
    if glatt:
        me.shade_smooth()
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


# --- Bahn, Innenfeld, Erdwall, Zaun ---

def baue_bahn():
    n = Netz()
    QUER = 8
    spalten = [[bahn.flaeche(s, i / QUER) for i in range(QUER + 1)] for s in SS]
    uv = [[(s / KACHEL_BAHN, i / QUER) for i in range(QUER + 1)] for s in SS]
    n.band(spalten, uv)
    objekt("bahn", n, [M_BAHN], glatt=True)


def baue_innenfeld():
    b = P["bahn"]
    n = Netz()
    kante = [bahn.versetzt(s, 0, -b["kiesstreifen"], 0.0) for s in SS]
    n.band([[bahn.flaeche(s, 0), k][::-1] for s, k in zip(SS, kante)], mat=lambda j, i: 0)
    n.flaeche(kante[:-1], mat=1)
    objekt("innenfeld", n, [M_KIES, M_GRAS])


def baue_wall():
    b = P["bahn"]
    n = Netz()
    spalten = []
    for s in SS:
        z = bahn.z_aussen(s)
        ausserhalb = max(b["wall_offen_von"] - s, s - b["wall_offen_bis"])
        anteil = min(max(ausserhalb / 8, 0), 1)
        krone = z + max(b["wall_krone"] - z, 0) * anteil
        x1 = b["plattform"]
        x2 = x1 + (krone - z) * b["boeschung"]
        x3 = x2 + b["wall_kronenbreite"]
        spalten.append([
            bahn.flaeche(s, 1),
            bahn.versetzt(s, 1, x1, z),
            bahn.versetzt(s, 1, x2, krone),
            bahn.versetzt(s, 1, x3, krone),
            bahn.versetzt(s, 1, x3 + (krone + 0.05) * b["boeschung"], -0.05),
        ])
    n.band(spalten)
    objekt("wall", n, [M_ERDE])


def baue_zaun(s_turm):
    f = P["zaun"]["hoehe"]
    w = P["zaun"]["weiss_laenge"] / 2
    n = Netz()
    spalten, uv = [], []
    for s in SS:
        z = bahn.z_aussen(s)
        spalten.append([
            bahn.flaeche(s, 1),
            bahn.versetzt(s, 1, 0, z + f),
            bahn.versetzt(s, 1, 0.06, z + f),
            bahn.versetzt(s, 1, 0.06, z),
        ])
        u = s / KACHEL_PLANKE[0]
        uv.append([(u, 0), (u, 1), (u, 1), (u, 0)])
    n.band(spalten, uv, mat=lambda j, i: 1 if abs(SS[j] + SCHRITT / 2 - s_turm) < w else 0)
    objekt("zaun", n, [M_ZAUN, M_WEISS])


# --- Betontribüne ---

def bezier(a, c, b, stufen=6):
    return [tuple((1 - t) ** 2 * a[k] + 2 * t * (1 - t) * c[k] + t * t * b[k] for k in (0, 1))
            for t in (i / stufen for i in range(1, stufen + 1))]


def rahmen_umriss(T):
    """Umriss eines Rahmens im Uhrzeigersinn. x: von der vorderen Spitze nach hinten, z: nach oben."""
    laenge = T["laenge"]
    x0, x1 = T["kragarm_vorn"], laenge - T["kragarm_hinten"]
    z0, z1 = T["hoehe_vorn"], T["hoehe_hinten"]
    spitze = 0.35
    dx, dz = (x1 - x0) / T["reihen"], (z1 - z0) / T["reihen"]
    d = T["traegerhoehe"]

    def unter(x):
        if x > x1:
            return z1 - spitze - (laenge - x) * (d - spitze) / (laenge - x1)
        if x < x0:
            return z0 - spitze + x * (spitze - d) / x0
        return z0 + (x - x0) * dz / dx - d

    p = [(0.0, z0 - spitze), (0.0, z0)]
    for i in range(T["reihen"]):
        p += [(x0 + i * dx, z0 + i * dz), (x0 + i * dx, z0 + (i + 1) * dz)]
    p += [(x1, z1), (laenge, z1), (laenge, z1 - spitze)]

    r_hinten, r_vorn = 1.0, 0.7
    fuss_z = -0.05
    for xl in sorted(T["beine"], reverse=True):
        hinten = xl + T["hals"] / 2
        vorn_oben = xl - T["hals"] / 2
        vorn_unten = hinten - T["fuss"]
        p.append((hinten + r_hinten, unter(hinten + r_hinten)))
        p += bezier(p[-1], (hinten, unter(hinten)), (hinten, unter(hinten) - r_hinten))
        p += [(hinten, fuss_z), (vorn_unten, fuss_z), (vorn_oben, unter(vorn_oben) - r_vorn)]
        p += bezier(p[-1], (vorn_oben, unter(vorn_oben)), (vorn_oben - r_vorn, unter(vorn_oben - r_vorn)))
    return p


def baue_tribuene():
    T = P["tribuene"]
    s = T["s_mitte"]
    nx, ny = bahn.aussen_richtung(s)
    tx, ty = bahn.tangente(s)
    n3, t3 = (nx, ny, 0.0), (tx, ty, 0.0)
    ox, oy, _ = bahn.versetzt(s, 1, T["abstand_zaun"], 0)
    laengs = (T["rahmen"] - 1) * T["achsabstand"]

    def welt(x, y, z):
        return (ox + nx * x + tx * y, oy + ny * x + ty * y, z)

    beton = Netz()
    umriss = rahmen_umriss(T)
    for k in range(T["rahmen"]):
        y = (k - (T["rahmen"] - 1) / 2) * T["achsabstand"]
        y1, y2 = y + T["dicke"] / 2, y - T["dicke"] / 2
        beton.flaeche([welt(x, y1, z) for x, z in umriss])
        beton.flaeche([welt(x, y2, z) for x, z in reversed(umriss)])
        for a, b in zip(umriss, umriss[1:] + umriss[:1]):
            beton.flaeche([welt(a[0], y1, a[1]), welt(a[0], y2, a[1]), welt(b[0], y2, b[1]), welt(b[0], y1, b[1])])
    objekt("beton", beton, [M_BETON])

    holz = Netz()
    achsen = (n3, t3, Z)
    x0, x1 = T["kragarm_vorn"], T["laenge"] - T["kragarm_hinten"]
    z0, z1 = T["hoehe_vorn"], T["hoehe_hinten"]
    dx, dz = (x1 - x0) / T["reihen"], (z1 - z0) / T["reihen"]
    lang = laengs + 1.2
    for i in range(T["reihen"]):
        z = z0 + (i + 1) * dz
        holz.quader(welt(x0 + (i + 0.5) * dx, 0, z + 0.03), achsen, (dx * 0.96, lang, 0.05))
        sitz = x0 + (i + 1) * dx - 0.2
        holz.quader(welt(sitz, 0, z + 0.43), achsen, (0.3, lang, 0.05))
        for k in range(T["rahmen"]):
            y = (k - (T["rahmen"] - 1) / 2) * T["achsabstand"]
            holz.quader(welt(sitz, y, z + 0.21), achsen, (0.1, 0.1, 0.4))
    holz.quader(welt((x1 + T["laenge"]) / 2, 0, z1 + 0.03), achsen, (T["laenge"] - x1, lang, 0.05))
    holz.quader(welt(x0 / 2, 0, z0 + 0.03), achsen, (x0, lang, 0.05))

    # Geländer hinten und an beiden Seiten
    x_h = T["laenge"] - 0.06
    for y in np.arange(-lang / 2, lang / 2 + 0.1, lang / 6):
        holz.quader(welt(x_h, y, z1 + 0.5), achsen, (0.08, 0.08, 1.0))
    for hoehe in (0.55, 1.0):
        holz.quader(welt(x_h, 0, z1 + hoehe), achsen, (0.06, lang, 0.08))
    laenge_rake = math.hypot(x1 - x0, z1 - z0)
    steigung = math.atan2(z1 - z0, x1 - x0)
    ax = (n3[0] * math.cos(steigung), n3[1] * math.cos(steigung), math.sin(steigung))
    az = (-n3[0] * math.sin(steigung), -n3[1] * math.sin(steigung), math.cos(steigung))
    for y in (-lang / 2, lang / 2):
        for hoehe in (0.55, 1.0):
            holz.quader(welt((x0 + x1) / 2, y, (z0 + z1) / 2 + hoehe), (ax, t3, az), (laenge_rake, 0.06, 0.08))
        for f in np.arange(0, 1.01, 0.2):
            holz.quader(welt(x0 + f * (x1 - x0), y, z0 + f * (z1 - z0) + 0.5), achsen, (0.08, 0.08, 1.0))
    objekt("holzbank", holz, [M_HOLZ])


# --- Turm ---

def baue_turm(s):
    T = P["turm"]
    nx, ny = bahn.aussen_richtung(s)
    tx, ty = bahn.tangente(s)
    achsen = ((nx, ny, 0.0), (tx, ty, 0.0), Z)
    a = T["seite"]
    cx, cy, _ = bahn.versetzt(s, 1, T["abstand_zaun"] + a / 2, 0)
    zb = bahn.z_aussen(s) - 1.0
    traufe = bahn.z_aussen(s) + T["wand"]
    sturz = 0.25
    unten = traufe - T["fensterband"] - sturz

    n = Netz()
    n.quader((cx, cy, (zb + unten) / 2), achsen, (a, a, unten - zb), mat=0, kachel=KACHEL_PLANKE)
    n.quader((cx, cy, traufe - sturz / 2), achsen, (a, a, sturz), mat=0, kachel=KACHEL_PLANKE)
    n.quader((cx, cy, (unten + traufe) / 2), achsen, (a - 0.3, a - 0.3, traufe - unten), mat=1)
    for i in (-1, 1):
        for j in (-1, 1):
            d = a / 2 - 0.1
            m = (cx + (nx * i + tx * j) * d, cy + (ny * i + ty * j) * d, (unten + traufe) / 2)
            n.quader(m, achsen, (0.2, 0.2, traufe - unten), mat=0, kachel=KACHEL_PLANKE)

    ue = a / 2 + 0.45
    ecken = [(cx + (nx * i + tx * j) * ue, cy + (ny * i + ty * j) * ue, traufe)
             for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    spitze = (cx, cy, traufe + T["dach"])
    for e1, e2 in zip(ecken, ecken[1:] + ecken[:1]):
        n.flaeche([e1, e2, spitze], mat=2)
    n.flaeche(ecken[::-1], mat=2)
    n.quader((cx, cy, spitze[2] + 1.0), achsen, (0.06, 0.06, 2.0), mat=2)
    objekt("turm", n, [M_TURM, M_DUNKEL, M_DACH])


def baue_boden():
    n = Netz()
    g = 700.0
    n.flaeche([(-g, -g, -0.05), (g, -g, -0.05), (g, g, -0.05), (-g, g, -0.05)])
    objekt("boden", n, [M_BODEN])


# --- Bau und Prüfung ---

T = P["tribuene"]
halbe_tribuene = (T["rahmen"] - 1) / 2 * T["achsabstand"] + 0.6
s_turm = T["s_mitte"] - halbe_tribuene - P["turm"]["abstand_tribuene"] - P["turm"]["seite"] / 2

baue_bahn()
baue_innenfeld()
baue_wall()
baue_zaun(s_turm)
baue_tribuene()
baue_turm(s_turm)
baue_boden()


def strecke(punkte):
    return sum(math.dist(a, b) for a, b in zip(punkte, punkte[1:]))


umfang = strecke([bahn.messlinie(s * 0.5) for s in range(1001)])
mitte_kurve = bahn.L / 4
quer_kurve = strecke([bahn.flaeche(mitte_kurve, i / 200) for i in range(201)])
quer_gerade = strecke([bahn.flaeche(0, i / 200) for i in range(201)])
hoehe_kurve = bahn.flaeche(mitte_kurve, 1)[2] - bahn.flaeche(mitte_kurve, 0)[2]
pruefung = {
    "Messlinie": (umfang, P["bahn"]["laenge"]),
    "Fahrbahnbreite Kurve": (quer_kurve, P["bahn"]["breite"]),
    "Fahrbahnbreite Gerade": (quer_gerade, P["bahn"]["breite"]),
    "Überhöhung Kurve": (hoehe_kurve, P["bahn"]["ueberhoehung"]),
}
for name, (ist, soll) in pruefung.items():
    print(f"PRUEFUNG {name}: {ist:.3f} m, Soll {soll} m")
    assert abs(ist - soll) < 0.02 * soll + 0.02, name

AUS.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(AUS / "rennbahn.blend"), compress=True)
bpy.ops.export_scene.gltf(filepath=str(AUS / "rennbahn.glb"), export_format="GLB", export_image_format="JPEG")
dreiecke = sum(sum(len(f.vertices) - 2 for f in o.data.polygons) for o in bpy.data.objects)
print(f"PRUEFUNG Dreiecke: {dreiecke}, Turm bei s = {s_turm:.1f} m")
print(f"PRUEFUNG GLB: {(AUS / 'rennbahn.glb').stat().st_size / 1024 ** 2:.1f} MB")
