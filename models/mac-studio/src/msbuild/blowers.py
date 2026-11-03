import math
import numpy as np
from . import dims as D
from .util import (MM, obj, MeshAccum, add_bevel, add_smooth_mod, rounded_rect_2d, circle_2d, slab_from_loops,
                   offset_polyline, revolve_profile, fillet_polyline, polygon_area)

R_IN = 20.0
R_OUT = D.IMP_D / 2
Z_IMP0 = D.IMP_Z0
Z_IMP1 = D.IMP_Z0 + D.IMP_H
Z_DIV = Z_IMP0 + D.IMP_SPLIT * D.IMP_H
Z_BOT0, Z_BOT1 = D.SHROUD_Z0, D.SHROUD_Z0 + 1.0
Z_TOP0, Z_TOP1 = D.SHROUD_Z1 - 1.0, D.SHROUD_Z1
Y_OUT = D.FIN_Y0 - 0.5
INTAKE_R = 20.5
WALL_LO = 1.2
WALL_HI = 2.2
SCROLL_R0 = 37.0
SCROLL_R1 = 43.0
TONGUE_DEG = 100.0


def cavity_path(side):
    th = np.radians(np.linspace(TONGUE_DEG, 360.0, 150))
    tt = (th - th[0]) / (th[-1] - th[0])
    r = SCROLL_R0 + (SCROLL_R1 - SCROLL_R0) * tt
    scroll = np.column_stack([r * np.cos(th), r * np.sin(th)])
    cy = D.BLOWER_CY
    left_end = np.array([1.0 - D.BLOWER_CX, Y_OUT - cy])
    right_end = np.array([86.5 - D.BLOWER_CX, Y_OUT - cy])
    pts = [left_end] + [p for p in scroll] + [right_end]
    radii = [0.0, 2.6] + [0.0] * (len(scroll) - 2) + [3.0, 0.0]
    path = fillet_polyline(pts, radii, arc_seg=8)
    dense = [path[0]]
    for q in path[1:]:
        p0 = dense[-1].copy()
        d = np.linalg.norm(q - p0)
        if d > 2.0:
            for k in np.linspace(0, 1, int(d / 2.0) + 2)[1:-1]:
                dense.append(p0 + (q - p0) * k)
        dense.append(q)
    path = np.array(dense)
    keep = [0]
    for i in range(1, len(path)):
        if np.linalg.norm(path[i] - path[keep[-1]]) > 1e-6:
            keep.append(i)
    path = path[keep]
    g = np.column_stack([path[:, 0] + D.BLOWER_CX, path[:, 1] + cy])
    if side < 0:
        g = np.column_stack([-g[:, 0], g[:, 1]])[::-1]
    return g


def wall_solid(path):
    sec = [(0.0, Z_BOT1 - 0.0), (WALL_LO, Z_BOT1), (WALL_LO, Z_DIV), (WALL_HI, Z_DIV + 0.6), (WALL_HI, Z_TOP0),
           (0.0, Z_TOP0)]
    from .util import sweep_section_along_path2d
    v, f = sweep_section_along_path2d(path, sec, 0.0, closed=False)
    return v, f


def weld(v, f, tol=1e-6):
    v = np.asarray(v, dtype=np.float64)
    key = np.round(v / tol).astype(np.int64)
    _, idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    nv = v[idx]
    nf = []
    for fc in f:
        q = []
        for i in fc:
            j = int(inv[i])
            if not q or q[-1] != j:
                q.append(j)
        if len(q) > 1 and q[0] == q[-1]:
            q.pop()
        if len(set(q)) >= 3:
            nf.append(tuple(q))
    return nv, nf


def blade_outline(r0, r1, phi, lean_deg, thick, n=9, direction=1):
    ts = np.linspace(0.0, 1.0, n)
    rr = r0 + (r1 - r0) * ts
    th = phi + direction * np.radians(lean_deg) * ts ** 1.6
    cen = np.column_stack([rr * np.cos(th), rr * np.sin(th)])
    tan = np.gradient(cen, axis=0)
    tan /= np.linalg.norm(tan, axis=1)[:, None]
    nrm = np.column_stack([tan[:, 1], -tan[:, 0]])
    a = cen + nrm * thick / 2
    b = cen - nrm * thick / 2
    return np.vstack([a, b[::-1]])


def impeller(side, mats, coll, name):
    import bpy
    cx, cy = side * D.BLOWER_CX, D.BLOWER_CY
    direction = 1 if side > 0 else -1
    parts = {'Upper': MeshAccum(), 'Lower': MeshAccum(), 'Core': MeshAccum()}
    tiers = [('Upper', Z_DIV + 0.25, Z_IMP1 - 0.45, D.BLADES_UPPER, D.BLADE_LEAN_UPPER, 0.0),
             ('Lower', Z_IMP0 + 0.45, Z_DIV - 0.25, D.BLADES_LOWER, D.BLADE_LEAN_LOWER, 0.5)]
    for (key, z0, z1, nb, lean, ph) in tiers:
        for i in range(nb):
            phi = 2 * math.pi * (i + ph) / nb
            o = blade_outline(R_IN, R_OUT - 0.15, phi, lean, 0.34, direction=direction)
            v, f = slab_from_loops(o, [], z0, z1)
            parts[key].add(v, f)
    for (key, z0, z1) in [('Upper', Z_IMP1 - 0.5, Z_IMP1), ('Lower', Z_IMP0, Z_IMP0 + 0.5)]:
        prof = [(R_OUT - 3.6, z0), (R_OUT + 0.1, z0), (R_OUT + 0.1, z1), (R_OUT - 3.6, z1), (R_OUT - 3.6, z0)]
        v, f, _ = revolve_profile(prof, 160)
        v, f = weld(v, f)
        parts[key].add(v, f)
    disc = [(0.0, Z_DIV - 0.32), (R_OUT + 1.1, Z_DIV - 0.32), (R_OUT + 1.4, Z_DIV - 0.12), (R_OUT + 1.4, Z_DIV + 0.12),
            (R_OUT + 1.1, Z_DIV + 0.32), (0.0, Z_DIV + 0.32)]
    v, f, _ = revolve_profile(disc, 160)
    parts['Core'].add(v, f)
    hub = fillet_polyline([(0.0, Z_DIV - 7.0), (9.0, Z_DIV - 7.0), (9.0, Z_DIV + 6.0), (0.0, Z_DIV + 6.0)], [0, 1.2, 2.5, 0], arc_seg=6)
    v, f, _ = revolve_profile(hub, 96)
    parts['Core'].add(v, f)
    for k in range(6):
        a = 2 * math.pi * k / 6 + 0.2
        for zz in (Z_DIV + 0.28 + 0.6, Z_DIV - 0.28 - 0.6):
            c = 13.5 * np.array([math.cos(a), math.sin(a)])
            o = rounded_rect_2d(9.0, 0.9, 0.3, 2)
            R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
            v, f = slab_from_loops(o @ R.T + c, [], zz - 0.6, zz + 0.6)
            parts['Core'].add(v, f)
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = 'CIRCLE'
    root.empty_display_size = R_OUT * MM
    root.location = (cx * MM, cy * MM, 0.0)
    coll.objects.link(root)
    root['blades_upper'] = D.BLADES_UPPER
    root['blades_lower'] = D.BLADES_LOWER
    root['blade_lean_upper_deg'] = D.BLADE_LEAN_UPPER
    root['blade_lean_lower_deg'] = D.BLADE_LEAN_LOWER
    root['divider_z_mm'] = round(Z_DIV, 2)
    root['upper_tier_fraction'] = round(1 - D.IMP_SPLIT, 2)
    root['rotation'] = 'CCW from top' if side > 0 else 'CW from top'
    root['spin_sign'] = direction
    root['note'] = 'rotate this empty about local Z to spin the impeller; children = Upper / Lower tiers and Core (divider disc + hub)'
    kids = []
    for key, acc in parts.items():
        me = acc.build(name + '_' + key, recalc=True)
        ch = obj(name + '_' + key, me, coll, mat=mats['satin'])
        ch.parent = root
        add_smooth_mod(ch, 35)
        ch['part'] = 'Blowers'
        kids.append(ch)
    return root, kids


def shroud(side, mats, coll, name):
    cx, cy = side * D.BLOWER_CX, D.BLOWER_CY
    path = cavity_path(side)
    acc = MeshAccum()
    v, f = wall_solid(path)
    acc.add(v, f)
    out_hi = offset_polyline(path, WALL_HI, closed=False)
    out_lo = offset_polyline(path, WALL_LO, closed=False)
    hole = circle_2d(INTAKE_R, 96) + np.array([cx, cy])
    loop = out_hi.copy()
    loop[0, 1] = Y_OUT
    loop[-1, 1] = Y_OUT
    v, f = slab_from_loops(loop, [hole], Z_TOP0, Z_TOP1)
    acc.add(v, f)
    loop2 = out_lo.copy()
    loop2[0, 1] = Y_OUT
    loop2[-1, 1] = Y_OUT
    v, f = slab_from_loops(loop2, [hole], Z_BOT0, Z_BOT1)
    acc.add(v, f)
    for (zb, sgn) in [(Z_TOP1, 1), (Z_BOT0, -1)]:
        prof = [(INTAKE_R, zb - sgn * 0.5), (INTAKE_R, zb + sgn * 0.6), (INTAKE_R + 1.2, zb + sgn * 0.9),
                (INTAKE_R + 2.8, zb + sgn * 0.6), (INTAKE_R + 3.6, zb - sgn * 0.05), (INTAKE_R + 3.6, zb - sgn * 0.5)]
        if sgn < 0:
            prof = prof[::-1]
        prof = list(prof) + [prof[0]]
        v, f, _ = revolve_profile(prof, 128)
        v, f = weld(v, f)
        v[:, 0] += cx
        v[:, 1] += cy
        acc.add(v, f)
    seam = MeshAccum()
    for k in range(7):
        th = np.radians(150 + k * 30)
        r = SCROLL_R0 + (SCROLL_R1 - SCROLL_R0) * (np.degrees(th) - TONGUE_DEG) / (360 - TONGUE_DEG) + WALL_HI + 0.4
        p = np.array([cx + side * r * math.cos(th), cy + r * math.sin(th)])
        nrm = np.array([side * math.cos(th), math.sin(th)])
        ang = math.atan2(nrm[1], nrm[0])
        o = rounded_rect_2d(1.6, 5.0, 0.3, 2)
        R = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
        v, f = slab_from_loops(o @ R.T + p, [], Z_DIV - 3.0, Z_DIV + 2.5)
        acc.add(v, f)
    me = acc.build(name, recalc=True)
    ob = obj(name, me, coll, mat=mats['plastic'])
    add_smooth_mod(ob, 35)
    return ob, path


def motor(side, mats, coll, name):
    cx, cy = side * D.BLOWER_CX, D.BLOWER_CY
    acc = MeshAccum()
    for k in range(3):
        a = 2 * math.pi * k / 3 + math.radians(30)
        p0 = np.array([cx, cy]) + 7.0 * np.array([math.cos(a), math.sin(a)])
        p1 = np.array([cx, cy]) + (INTAKE_R + 0.8) * np.array([math.cos(a), math.sin(a)])
        d = p1 - p0
        L = np.linalg.norm(d)
        ang = math.atan2(d[1], d[0])
        o = rounded_rect_2d(L, 2.8, 0.6, 3)
        R = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
        v, f = slab_from_loops(o @ R.T + (p0 + p1) / 2, [], Z_BOT0, Z_BOT1)
        acc.add(v, f)
    v, f = slab_from_loops(circle_2d(8.5, 64) + np.array([cx, cy]), [], Z_BOT0 - 0.3, Z_BOT1)
    acc.add(v, f)
    st = fillet_polyline([(0.0, Z_BOT1), (7.2, Z_BOT1), (7.2, Z_DIV - 7.6), (0.0, Z_DIV - 7.6)], [0, 0.4, 0.8, 0], arc_seg=4)
    v, f, _ = revolve_profile(st, 64)
    v[:, 0] += cx
    v[:, 1] += cy
    acc.add(v, f)
    me = acc.build(name)
    ob = obj(name, me, coll, mat=mats['plastic'])
    add_smooth_mod(ob, 35)
    return ob


def bridge(mats, coll):
    acc = MeshAccum()
    v, f = slab_from_loops(rounded_rect_2d(30.0, 64.0, 6.0, 6) + np.array([0.0, 28.0]), [], Z_BOT0 + 0.05, Z_BOT1 - 0.05)
    acc.add(v, f)
    acc.add_box((0.0, Y_OUT - 0.6, Z_BOT1 + 1.4), (176.0, 1.2, 2.8))
    for x in (-89.5, 89.5):
        v, f = slab_from_loops(rounded_rect_2d(9.0, 9.0, 3.0, 4) + np.array([x, 54.0]), [circle_2d(1.2, 16) + np.array([x, 54.0])], Z_BOT0, Z_BOT1)
        acc.add(v, f)
    v, f = slab_from_loops(rounded_rect_2d(9.0, 9.0, 3.0, 4) + np.array([0.0, 2.0]), [circle_2d(1.2, 16) + np.array([0.0, 2.0])], Z_BOT0, Z_BOT1)
    acc.add(v, f)
    me = acc.build('Blower_Bridge')
    ob = obj('Blower_Bridge', me, coll, mat=mats['plastic'])
    add_bevel(ob, 0.3, 2)
    lab = MeshAccum()
    v, f = slab_from_loops(rounded_rect_2d(18.0, 9.0, 1.0, 3) + np.array([0.0, 34.0]), [], Z_BOT0 - 0.02, Z_BOT0 + 0.01)
    lab.add(v, f)
    lo = obj('Blower_Label', lab.build('Blower_Label'), coll, mat=mats['label'])
    sc = MeshAccum()
    for (x, y) in [(-89.5, 54.0), (89.5, 54.0), (0.0, 2.0)]:
        sc.add_cyl((x, y, Z_BOT1 + 0.6), 2.2, 1.2, n=24)
    so = obj('Blower_Screws', sc.build('Blower_Screws'), coll, mat=mats['steel'])
    add_bevel(so, 0.25, 2)
    foam = MeshAccum()
    foam.add_box((0.0, Y_OUT - 1.5, Z_TOP1 + 0.9), (176.0, 4.0, 1.8))
    fo = obj('Blower_Seal_Foam', foam.build('Blower_Seal_Foam'), coll, mat=mats['rubber'])
    add_bevel(fo, 0.4, 2)
    return [ob, lo, so, fo]


def build(coll, mats, **kw):
    objs = []
    shrouds = []
    impellers = []
    for side, tag in [(-1, 'L'), (1, 'R')]:
        sh, path = shroud(side, mats, coll, 'Blower_Shroud_' + tag)
        shrouds.append(sh)
        objs.append(sh)
        root, kids = impeller(side, mats, coll, 'Impeller_' + tag)
        objs.append(root)
        impellers.append((root, kids))
        objs.append(motor(side, mats, coll, 'Blower_Motor_' + tag))
    br = bridge(mats, coll)
    objs += br
    for o in objs:
        o['part'] = 'Blowers'
    return dict(objects=objs, shroud=shrouds + [br[0]], impellers=impellers)
