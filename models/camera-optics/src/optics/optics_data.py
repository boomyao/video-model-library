"""Computed optics for the 2D scenes ("本片计算"): every number here comes out of our own trace or a textbook formula.

uv run --with beautifulsoup4 --with numpy python optics_data.py [output.json]

- singlet: one spherical biconvex lens in the patent's low-dispersion plastic (nd 1.544, vd 55.9), traced at three
  wavelengths: edge rays focus short (spherical aberration), blue focuses short of red (chromatic aberration).
- doublet: the same positive lens plus a negative lens in the patent's high-dispersion plastic (1.639 / 23.5),
  powers split by the thin-lens achromat condition, then traced: red and blue come back to one focus.
- scaling: the patent lens scaled to other sensor sizes (TTL grows with the image diagonal), 24 mm-equivalent lens.
- airy: diffraction spot diameter 2.44 * lambda * N against pixel pitches.
- vcm: how far the lens stack must move forward to focus at a distance u (thin-lens, f = 5.38 mm).
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lens_trace as LT  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, ".."))
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "build", "optics.json")
WL = {"red": 0.6563, "green": 0.5876, "blue": 0.4861}   # C, d, F lines (micrometres)


def system(elems, stop_after=0):
    """elems: list of (R_front, R_back, thickness, gap_after, nd, vd). Returns a lens_trace-style dict."""
    surf = [dict(name="Object", R=None, t=None, mat="", n=None, vd=None, k=0.0, A={})]
    if stop_after < 0:   # aperture stop at the first vertex
        surf.append(dict(name="Ape. Stop", R=None, t=0.0, mat="", n=None, vd=None, k=0.0, A={}))
    for i, (r1, r2, th, gap, nd, vd) in enumerate(elems):
        surf.append(dict(name="Lens %d" % (i + 1), R=r1, t=th, mat="Plastic", n=nd, vd=vd, k=0.0, A={}))
        surf.append(dict(name="", R=r2, t=gap, mat="", n=None, vd=None, k=0.0, A={}))
        if i == stop_after:
            surf.append(dict(name="Ape. Stop", R=None, t=0.0, mat="", n=None, vd=None, k=0.0, A={}))
    surf.append(dict(name="Image", R=None, t=None, mat="", n=None, vd=None, k=0.0, A={}))
    return dict(f=None, fno=None, hfov=None, surf=surf)


def at_wavelength(d, lam):
    import copy
    e = copy.deepcopy(d)
    for s in e["surf"]:
        if s.get("n"):
            s["n"] = LT.cauchy(s["n"], s.get("vd"))(lam)
    return e


def paraxial_focus(L):
    h = 1e-4
    pts, D = L.trace(h, 0.0)
    z, y = pts[-2]       # last refracting surface hit (the image plane is pts[-1])
    return z - y * D[0] / D[1]


def fan(d, heights, lam, image_z):
    e = at_wavelength(d, lam)
    e["surf"][-2]["t"] = image_z - sum(s["t"] for s in e["surf"][1:-2] if s["t"] is not None)
    L = LT.Lens(e)
    out = []
    for h in heights:
        r = L.trace(h, 0.0)
        if not r:
            continue
        pts, D = r
        pts = [q for j, q in enumerate(pts) if j == 0 or "Stop" not in L.S[j - 1]["name"]]
        z, y = pts[-2]
        cross = z - y * D[0] / D[1] if abs(D[1]) > 1e-12 else None   # where this ray crosses the axis
        out.append(dict(h=h, pts=[[round(float(a), 4), round(float(b), 4)] for a, b in pts], cross=cross))
    return out


def lens_outline(elems):
    """Outlines of spherical elements for drawing: list of dicts with z positions and radii (mm)."""
    out, z = [], 0.0
    for (r1, r2, th, gap, nd, vd) in elems:
        out.append(dict(z1=z, z2=z + th, R1=r1, R2=r2, nd=nd, vd=vd))
        z += th + gap
    return out


def main():
    res = {}
    # ---- singlet: biconvex, R = +-20 mm, 4 mm thick, aperture radius 6 mm
    single = [(20.0, -20.0, 4.0, 30.0, 1.544, 55.9)]
    d1 = system(single, stop_after=-1)
    Lg = LT.Lens(at_wavelength(d1, WL["green"]))
    fz = paraxial_focus(Lg)
    heights = [float(h) for h in np.linspace(-6, 6, 13) if abs(h) > 1e-9]
    res["singlet"] = dict(elements=lens_outline(single), aperture=6.0, image_z=fz,
                          fans={c: fan(d1, heights, lam, fz + 6) for c, lam in WL.items()},
                          focus={c: paraxial_focus(LT.Lens(at_wavelength(d1, lam))) for c, lam in WL.items()})
    # ---- achromat: positive 1.544/55.9 + negative 1.639/23.5, thin-lens powers phi1 = phi V1/(V1-V2), phi2 = -phi V2/(V1-V2)
    V1, V2, n1, n2, f = 55.9, 23.5, 1.544, 1.639, 20.0
    phi = 1 / f
    p1, p2 = phi * V1 / (V1 - V2), -phi * V2 / (V1 - V2)
    R = 2 * (n1 - 1) / p1                  # equi-convex first element
    # second element cemented to the first (front radius -R); back radius from its power
    inv_r2b = (-1 / R) - p2 / (n2 - 1)
    double = [(R, -R, 3.5, 0.0, n1, V1), (-R, 1 / inv_r2b, 1.5, 30.0, n2, V2)]
    d2 = system(double, stop_after=-1)
    Lg2 = LT.Lens(at_wavelength(d2, WL["green"]))
    fz2 = paraxial_focus(Lg2)
    heights2 = [float(h) for h in np.linspace(-3, 3, 9) if abs(h) > 1e-9]
    res["doublet"] = dict(elements=lens_outline(double), aperture=3.0, image_z=fz2,
                          fans={c: fan(d2, heights2, lam, fz2 + 6) for c, lam in WL.items()},
                          focus={c: paraxial_focus(LT.Lens(at_wavelength(d2, lam))) for c, lam in WL.items()})
    # singlet at the same small aperture, for a fair colour comparison
    res["singlet_small"] = dict(focus={c: paraxial_focus(LT.Lens(at_wavelength(d1, lam))) for c, lam in WL.items()})
    # ---- scaling of the patent lens with the sensor size (image circle diagonal), 26.7 mm-equivalent as designed
    ttl0, diag0 = 7.200, 8.92
    sensors = [("1/2.55 英寸", 6.30), ("1/1.28 英寸", 12.5), ("1 英寸", 15.86), ("全画幅", 43.27)]
    res["scaling"] = dict(ttl0=ttl0, diag0=diag0, ratio=ttl0 / diag0,
                          sensors=[dict(name=n, diag=dg, ttl=round(ttl0 * dg / diag0, 2)) for n, dg in sensors])
    # ---- diffraction spot vs pixels
    N, lam = 1.9, 0.55
    res["airy"] = dict(N=N, lam_um=lam, diameter_um=round(2.44 * lam * N, 2), pixels_um=[2.4, 1.6, 1.22, 1.0, 0.8, 0.6])
    # ---- VCM: forward travel to focus at distance u (mm), thin lens, f = 5.38 mm
    fv = 5.38
    res["vcm"] = dict(f=fv, curve=[dict(u=u, shift_um=round(1000 * fv * fv / (u - fv), 1))
                                  for u in (100, 150, 200, 300, 500, 1000, 3000, 10000)])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
    s, dd = res["singlet"]["focus"], res["doublet"]["focus"]
    print("singlet paraxial focus (mm from first vertex): red %.3f green %.3f blue %.3f  -> blue-red %.3f mm"
          % (s["red"], s["green"], s["blue"], s["blue"] - s["red"]))
    edge = [r["cross"] for r in res["singlet"]["fans"]["green"] if abs(r["h"]) == 6.0]
    print("singlet green: edge ray (h=6) crosses the axis at %.3f mm vs paraxial %.3f" % (edge[0], s["green"]))
    print("doublet (R1=%.2f, R3=%.2f): red %.3f green %.3f blue %.3f -> blue-red %.3f mm"
          % (R, 1 / inv_r2b, dd["red"], dd["green"], dd["blue"], dd["blue"] - dd["red"]))
    print("scaling:", res["scaling"]["sensors"])
    print("airy diameter um:", res["airy"]["diameter_um"], " vcm:", res["vcm"]["curve"][:3])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
