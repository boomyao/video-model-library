import math
import numpy as np
from . import dims as D
from .util import (MM, mesh_np, obj, MeshAccum, revolve_profile, fillet_polyline, recalc_normals, add_bevel,
                   add_smooth_mod, circle_2d, rounded_rect_2d, slab_from_loops, sweep_section_along_path3d,
                   fillet_path3d)

Z_COVER0 = D.Z_PT + 0.3
Z_PCB0 = D.PSU_PCB_Z
Z_PCB1 = D.PSU_PCB_Z + D.PSU_PCB_T


def cover_mesh():
    r = D.PSU_R + 0.6
    zt = Z_PCB0 - 0.05
    pts = [(0.0, Z_COVER0), (r - 1.2, Z_COVER0), (r, Z_COVER0 + 1.2), (r, zt), (r - 0.9, zt),
           (r - 0.9, Z_COVER0 + 0.8), (0.0, Z_COVER0 + 0.8)]
    prof = fillet_polyline(pts, [0, 0.8, 0.3, 0.15, 0.15, 0.3, 0], arc_seg=5)
    v, f, rings = revolve_profile(prof, 256)
    acc = MeshAccum()
    acc.add(v, f)
    for k in range(4):
        a = math.radians(45 + 90 * k)
        c = np.array([math.cos(a), math.sin(a)]) * (D.PSU_R + 2.4)
        tab = rounded_rect_2d(9.0, 7.0, 2.0, 4)
        ca, sa = math.cos(a), math.sin(a)
        R = np.array([[ca, -sa], [sa, ca]])
        o = tab @ R.T + c
        hole = circle_2d(1.6, 16) + c
        vv, ff = slab_from_loops(o, [hole], zt - 1.0, zt)
        acc.add(vv, ff)
    return acc.build('PSU_Cover')


def toroid(acc_wire, cx, cy, z0, R=10.0, r=4.6, turns=38, nu=96, nv=20):
    verts = []
    wind = []
    for i in range(nu):
        u = 2 * math.pi * i / nu
        for j in range(nv):
            v = 2 * math.pi * j / nv
            x = (R + r * math.cos(v)) * math.cos(u)
            y = (R + r * math.cos(v)) * math.sin(u)
            z = r * math.sin(v)
            verts.append((cx + x, cy + y, z0 + r + z))
            wind.append(turns * u / 2.0)
    faces = []
    for i in range(nu):
        for j in range(nv):
            a = i * nv + j
            b = ((i + 1) % nu) * nv + j
            c = ((i + 1) % nu) * nv + (j + 1) % nv
            d = i * nv + (j + 1) % nv
            faces.append((a, b, c, d))
    acc_wire.add(np.array(verts), faces)
    acc_wire.wind = getattr(acc_wire, 'wind', []) + wind


def build(coll, mats, **kw):
    objs = []
    cov = obj('PSU_Cover', cover_mesh(), coll, mat=mats['plastic'])
    add_smooth_mod(cov, 35)
    objs.append(cov)
    v, f, rings = revolve_profile([(0.0, Z_PCB0), (D.PSU_R - 0.4, Z_PCB0), (D.PSU_R, Z_PCB0 + 0.4),
                                   (D.PSU_R, Z_PCB1 - 0.4), (D.PSU_R - 0.4, Z_PCB1), (0.0, Z_PCB1)], 256)
    pcb = MeshAccum()
    pcb.add(v, f)
    pcbo = obj('PSU_PCB', pcb.build('PSU_PCB'), coll, mat=mats['pcb'])
    add_smooth_mod(pcbo, 35)
    objs.append(pcbo)

    wire = MeshAccum()
    toroid(wire, -36.0, -52.0, Z_PCB1 + 0.2, R=11.0, r=5.0, turns=44)
    toroid(wire, -6.0, -63.0, Z_PCB1 + 0.2, R=8.0, r=3.8, turns=32)
    toroid(wire, 38.0, -50.0, Z_PCB1 + 0.2, R=8.5, r=4.2, turns=34)
    toroid(wire, -14.0, 50.0, Z_PCB1 + 0.2, R=9.0, r=4.2, turns=36)
    me = wire.build('PSU_Toroids', recalc=False)
    from .util import recalc_normals as rn
    rn(me)
    at = me.attributes.new('wind', 'FLOAT', 'POINT')
    at.data.foreach_set('value', np.array(wire.wind, dtype=np.float32))
    for p in me.polygons:
        p.use_smooth = True
    objs.append(obj('PSU_Toroids', me, coll, mat=mats['cu_wire']))

    caps = MeshAccum()
    tops = MeshAccum()
    for (x, y, r, h) in [(14, -50, 5.0, 12.0), (58, -30, 4.0, 9.0), (-56, -22, 6.3, 13.5), (-42, 30, 6.3, 13.5),
                         (-62, 12, 4.0, 9.0), (8, 34, 5.0, 11.0)]:
        caps.add_cyl((x, y, Z_PCB1 + h / 2), r, h, n=40)
        tops.add_cyl((x, y, Z_PCB1 + h + 0.15), r * 0.82, 0.3, n=40)
    for (x, y) in [(-22.0, -6.0), (-22.0, 12.0)]:
        caps.add_cyl((x, y, Z_PCB1 + 8.2), 8.0, 30.0, n=48, axis='X')
    o = obj('PSU_Capacitors', caps.build('PSU_Capacitors'), coll, mat=mats['satin'])
    add_bevel(o, 0.5, 2)
    objs.append(o)
    o = obj('PSU_Capacitor_Tops', tops.build('PSU_Capacitor_Tops'), coll, mat=mats['al_sheet'])
    add_smooth_mod(o, 35)
    objs.append(o)

    blk = MeshAccum()
    blk.add_box((24.0, 8.0, Z_PCB1 + 7.5), (30.0, 26.0, 15.0))
    blk.add_box((-2.0, 30.0, Z_PCB1 + 6.0), (18.0, 14.0, 12.0))
    blk.add_box((60.0, -12.0, Z_PCB1 + 6.0), (6.0, 18.0, 12.0))
    blk.add_box((14.0, -68.0, Z_PCB1 + 4.0), (14.0, 8.0, 8.0))
    blk.add_box((60.0, -48.0, Z_PCB1 + 3.5), (10.0, 10.0, 7.0))
    for k in range(4):
        blk.add_box((56.0, -18.0 + k * 6.5, Z_PCB1 + 6.5), (4.5, 5.0, 13.0))
    o = obj('PSU_Blocks', blk.build('PSU_Blocks'), coll, mat=mats['plastic'])
    add_bevel(o, 0.6, 2)
    objs.append(o)

    tape = MeshAccum()
    tape.add_box((24.0, 8.0, Z_PCB1 + 7.5), (30.6, 8.0, 15.6))
    o = obj('PSU_Tape', tape.build('PSU_Tape'), coll, mat=mats['kapton'])
    add_bevel(o, 0.4, 2)
    objs.append(o)

    hs = MeshAccum()
    for k in range(2):
        hs.add_box((40.0 + 9.0 * k, -8.0, Z_PCB1 + 7.0), (1.6, 34.0, 14.0))
        for j in range(6):
            hs.add_box((40.0 + 9.0 * k + 2.2, -22.0 + j * 5.6, Z_PCB1 + 7.0), (2.8, 1.2, 14.0))
    o = obj('PSU_Heatsinks', hs.build('PSU_Heatsinks'), coll, mat=mats['al_sheet'])
    add_bevel(o, 0.25, 2)
    objs.append(o)

    bus = MeshAccum()
    path = [(66.0, 8.0, Z_PCB1 + 0.8), (66.0, 8.0, D.BOARD_Z - 6.0), (66.0, 14.0, D.BOARD_Z - 0.8)]
    sec = rounded_rect_2d(1.4, 8.0, 0.3, 3)
    v, f = sweep_section_along_path3d(fillet_path3d(path, 3.0, 8), sec, up=(1, 0, 0))
    bus.add(v, f)
    o = obj('PSU_BusBar', bus.build('PSU_BusBar'), coll, mat=mats['cu'])
    add_smooth_mod(o, 35)
    objs.append(o)
    ins = MeshAccum()
    ins.add_box((68.2, 9.5, Z_PCB1 + 9.0), (0.3, 11.0, 15.0))
    objs.append(obj('PSU_BusBar_Insulator', ins.build('PSU_BusBar_Insulator'), coll, mat=mats['plastic']))

    cable = MeshAccum()
    ac_x = D.HALF - 94.5
    path = [(ac_x + 2.0, 60.0, Z_PCB1 + 3.0), (ac_x + 2.0, 74.0, Z_PCB1 + 3.0), (ac_x, 84.0, D.PORT_Z - 2.0),
            (ac_x, 86.5, D.PORT_Z)]
    v, f = sweep_section_along_path3d(fillet_path3d(path, 4.0, 10), circle_2d(1.6, 16))
    cable.add(v, f)
    o = obj('PSU_AC_Cable', cable.build('PSU_AC_Cable'), coll, mat=mats['satin'])
    for p in o.data.polygons:
        p.use_smooth = True
    objs.append(o)

    scr = MeshAccum()
    for k in range(4):
        a = math.radians(45 + 90 * k)
        scr.add_cyl(((D.PSU_R + 2.4) * math.cos(a), (D.PSU_R + 2.4) * math.sin(a), Z_PCB0 + 0.4), 2.2, 1.0, n=24)
    for (x, y) in [(66.0, 4.0), (66.0, 12.0)]:
        scr.add_cyl((x, y, Z_PCB1 + 1.6), 2.0, 1.2, n=24)
    o = obj('PSU_Screws', scr.build('PSU_Screws'), coll, mat=mats['steel_dark'])
    add_bevel(o, 0.25, 2)
    objs.append(o)

    smd = MeshAccum()
    rng = np.random.default_rng(7)
    for _ in range(140):
        r = rng.uniform(15, 74)
        a = rng.uniform(0, 2 * math.pi)
        x, y = r * math.cos(a), r * math.sin(a)
        if abs(x - 24) < 18 and abs(y - 8) < 16:
            continue
        if min(math.hypot(x - tx, y - ty) for (tx, ty) in [(-36, -52), (-6, -63), (38, -50), (-14, 50)]) < 17:
            continue
        sx, sy = rng.choice([(2.0, 1.25), (3.2, 1.6), (1.6, 0.8), (5.0, 5.0)])
        if rng.random() < 0.5:
            sx, sy = sy, sx
        smd.add_box((x, y, Z_PCB1 + 0.45), (sx, sy, 0.9))
    o = obj('PSU_SMD', smd.build('PSU_SMD'), coll, mat=mats['chip'])
    objs.append(o)
    for o in objs:
        o['part'] = 'PSU'
    return dict(objects=objs)
