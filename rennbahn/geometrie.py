"""Grundriss und Querschnitt der Bahn, ohne Blender nutzbar.

Koordinaten in Metern: x nach Osten, y nach Norden, z nach oben, Ursprung in der Bahnmitte.
s läuft gegen den Uhrzeigersinn entlang der Messlinie, s = 0 ist die Mitte der Ostgeraden,
s = laenge / 2 die Mitte der Westgeraden.
"""
import json
import math


def lade_parameter(pfad):
    with open(pfad, encoding="utf-8") as f:
        roh = json.load(f)
    return {teil: {k: v["wert"] for k, v in werte.items()} for teil, werte in roh.items()}


class Bahn:
    SCHRITT = 0.25

    def __init__(self, P):
        b = P["bahn"]
        self.L = b["laenge"]
        self.breite = b["breite"]
        self.h_kurve = b["ueberhoehung"]
        self.h_gerade = b["ueberhoehung_gerade"]
        self.linear = b["profil_linear"]
        self.versatz = b["messlinie_abstand"]
        self.z_innen = b["hoehe_innenkante"]
        self.R = b["kurvenradius"]
        self.T = b["uebergang"]
        self.A = math.pi * self.R - self.T
        self.S = self.L / 2 - 2 * self.T - self.A
        if self.S < 0:
            raise ValueError("Radius und Übergang passen nicht in die Bahnlänge")
        self._w_cache = {}
        self._integrieren(math.radians(b["azimut"]))

    def faktor(self, s):
        """Anteil der Kurve bei s: 0 auf der Geraden, 1 im Bogen."""
        s %= self.L / 2
        a = self.S / 2
        if s < a or s >= a + 2 * self.T + self.A:
            return 0.0
        if s < a + self.T:
            return (1 - math.cos(math.pi * (s - a) / self.T)) / 2
        if s < a + self.T + self.A:
            return 1.0
        return (1 + math.cos(math.pi * (s - a - self.T - self.A) / self.T)) / 2

    def _integrieren(self, az):
        n = round(self.L / self.SCHRITT)
        x, y, th = 0.0, 0.0, math.pi / 2
        px, py, tx, ty = [], [], [], []
        for i in range(n):
            px.append(x)
            py.append(y)
            tx.append(math.cos(th))
            ty.append(math.sin(th))
            dth = self.faktor((i + 0.5) * self.SCHRITT) / self.R * self.SCHRITT
            mitte = th + dth / 2
            x += math.cos(mitte) * self.SCHRITT
            y += math.sin(mitte) * self.SCHRITT
            th += dth
        self.schluss = math.hypot(x - px[0], y - py[0])
        mx, my = sum(px) / n, sum(py) / n
        ca, sa = math.cos(az), math.sin(az)
        dreh = lambda u, v: (u * ca + v * sa, -u * sa + v * ca)
        self._p = [dreh(u - mx, v - my) for u, v in zip(px, py)]
        self._t = [dreh(u, v) for u, v in zip(tx, ty)]

    def _lesen(self, feld, s):
        q = (s % self.L) / self.SCHRITT
        i = int(q)
        f = q - i
        a, b = feld[i % len(feld)], feld[(i + 1) % len(feld)]
        return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f

    def messlinie(self, s):
        return self._lesen(self._p, s)

    def tangente(self, s):
        tx, ty = self._lesen(self._t, s)
        n = math.hypot(tx, ty)
        return tx / n, ty / n

    def aussen_richtung(self, s):
        tx, ty = self.tangente(s)
        return ty, -tx

    def hoehe(self, s):
        return self.h_gerade + (self.h_kurve - self.h_gerade) * self.faktor(s)

    def _bogen(self, w, h):
        n, summe = 16, 0.0
        for i in range(n):
            u = (i + 0.5) / n
            summe += math.hypot(w, h * (self.linear + 2 * (1 - self.linear) * u)) / n
        return summe

    def waagrecht(self, h):
        """Waagrechte Breite des Querschnitts, damit die Fläche selbst self.breite misst."""
        k = round(h, 2)
        if k not in self._w_cache:
            lo, hi = 0.1, self.breite
            for _ in range(25):
                mitte = (lo + hi) / 2
                if self._bogen(mitte, k) > self.breite:
                    hi = mitte
                else:
                    lo = mitte
            self._w_cache[k] = (lo + hi) / 2
        return self._w_cache[k]

    def flaeche(self, s, u):
        """Punkt auf der Fahrbahn, u = 0 Innenkante, u = 1 Außenkante."""
        px, py = self.messlinie(s)
        nx, ny = self.aussen_richtung(s)
        h = self.hoehe(s)
        d = self.waagrecht(h) * u - self.versatz
        z = self.z_innen + h * (self.linear * u + (1 - self.linear) * u * u)
        return px + nx * d, py + ny * d, z

    def versetzt(self, s, u, abstand, z):
        """Punkt um abstand nach außen vom Fahrbahnpunkt u, auf Höhe z."""
        x, y, _ = self.flaeche(s, u)
        nx, ny = self.aussen_richtung(s)
        return x + nx * abstand, y + ny * abstand, z

    def z_aussen(self, s):
        return self.z_innen + self.hoehe(s)
