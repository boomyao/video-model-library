import math
import numpy as np
from . import dims as D
from .util import (MM, obj, MeshAccum, add_bevel, add_smooth_mod, rounded_rect_2d, circle_2d, slab_from_loops,
                   fillet_polyline, sweep_section_along_path3d, fillet_path3d, mesh_np, recalc_normals)
from .soc import Z0 as SOC_Z0, SUB_T, INT_T, DIE_T

PED_Z0 = SOC_Z0 + SUB_T + INT_T + DIE_T + 0.06
PED_Z1 = 44.0
BASE_Z1 = 47.0


def fin_stack(acc, count, t, x0=-D.FIN_X / 2, x1=D.FIN_X / 2, y0=D.FIN_Y0, depth=D.FIN_DEPTH, z0=BASE_Z1, z1=D.FIN_Z1):
    pitch = (x1 - x0) / count
    for i in range(count):
        xa = x0 + i * pitch
        fl = pitch - 0.1
        prof = [(xa, z0), (xa + fl, z0), (xa + fl, z0 + t), (xa + t, z0 + t), (xa + t, z1 - t), (xa + fl, z1 - t),
                (xa + fl, z1), (xa, z1)]
        n = len(prof)
        va = [(x, y0, z) for x, z in prof]
        vb = [(x, y0 + depth, z) for x, z in prof]
        verts = np.array(va + vb)
        faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((k, k + n, k2 + n, k2))
        acc.add(verts, faces)
    return pitch


def end_plates(acc, x0=-D.FIN_X / 2, x1=D.FIN_X / 2, z0=BASE_Z1, z1=D.FIN_Z1):
    for x in (x0 - 0.45, x1 + 0.45):
        acc.add_box((x, D.FIN_Y0 + D.FIN_DEPTH / 2, (z0 + z1) / 2), (0.9, D.FIN_DEPTH + 0.6, z1 - z0 + 0.4))


MOUNTS = [(-80.0, -80.0), (80.0, -80.0), (-89.0, 70.0), (89.0, 70.0)]


def build(coll, mats, variant='ultra', **kw):
    sx, sy = D.SOC_CENTER
    P = 'TU_' if variant == 'ultra' else 'TM_'
    objs = []
    if variant == 'ultra':
        ped = MeshAccum()
        v, f = slab_from_loops(rounded_rect_2d(58.0, 62.0, 2.5, 4) + np.array([sx, sy]), [], PED_Z0, PED_Z1)
        ped.add(v, f)
        o = obj(P + 'Copper_Pedestal', ped.build(P + 'Copper_Pedestal'), coll, mat=mats['cu_pol'])
        add_bevel(o, 0.6, 3)
        objs.append(o)
        vc_pts = [(-35.0, sy - 40.0), (35.0, sy - 40.0), (35.0, 56.0), (86.0, 56.0), (86.0, 92.0), (-86.0, 92.0),
                  (-86.0, 56.0), (-35.0, 56.0)]
        vc = fillet_polyline(vc_pts + [vc_pts[0], vc_pts[1]], [0, 5, 4, 4, 3, 3, 4, 4, 5, 0], arc_seg=6)
        vc = vc[1:-1]
        acc = MeshAccum()
        v, f = slab_from_loops(vc, [], PED_Z1, BASE_Z1)
        acc.add(v, f)
        o = obj(P + 'Vapor_Chamber', acc.build(P + 'Vapor_Chamber'), coll, mat=mats['cu'])
        add_bevel(o, 0.7, 3)
        o['note'] = 'M5 Ultra: copper vapor chamber per Tom\'s Hardware (reviewer statement, not teardown-verified)'
        objs.append(o)
        seam = MeshAccum()
        from .util import offset_polyline
        so = offset_polyline(vc, 0.02)
        si = offset_polyline(vc, -0.25)
        v, f = slab_from_loops(so, [si], PED_Z1 + 1.42, PED_Z1 + 1.58)
        seam.add(v, f)
        seam.add_cyl((-80.0, 92.6, PED_Z1 + 1.5), 0.9, 2.4, n=16, axis='Y')
        objs.append(obj(P + 'VC_Seam', seam.build(P + 'VC_Seam'), coll, mat=mats['cu_pol']))
        fins = MeshAccum()
        pitch = fin_stack(fins, D.FIN_COUNT_ULTRA, 0.3)
        end_plates(fins)
        o = obj(P + 'Fin_Stack_Copper', fins.build(P + 'Fin_Stack_Copper', recalc=True), coll, mat=mats['cu'])
        o['fins'] = D.FIN_COUNT_ULTRA
        o['fin_pitch_mm'] = round(pitch, 3)
        o['material'] = 'copper'
        objs.append(o)
        spr = MeshAccum()
        for (dx, dy) in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            a = math.atan2(dy * 34.0, dx * 26.0)
            path = [(sx + dx * 12.0, sy + dy * 12.0, BASE_Z1 + 0.5), (sx + dx * 40.0, sy + dy * 44.0, BASE_Z1 + 0.5)]
            v, f = sweep_section_along_path3d(np.array(path), rounded_rect_2d(9.0, 1.0, 0.2, 2))
            spr.add(v, f)
            spr.add_cyl((sx + dx * 40.0, sy + dy * 44.0, BASE_Z1 + 0.5), 5.0, 1.0, n=32)
        v, f = slab_from_loops(rounded_rect_2d(30.0, 30.0, 6.0, 6) + np.array([sx, sy]), [], BASE_Z1, BASE_Z1 + 1.0)
        spr.add(v, f)
        o = obj(P + 'Spring_Clamp', spr.build(P + 'Spring_Clamp'), coll, mat=mats['steel'])
        add_bevel(o, 0.2, 2)
        objs.append(o)
        clamp_pts = [(sx + dx * 40.0, sy + dy * 44.0) for dx in (-1, 1) for dy in (-1, 1)]
    else:
        ped = MeshAccum()
        v, f = slab_from_loops(rounded_rect_2d(46.0, 40.0, 2.0, 4) + np.array([sx, sy]), [], PED_Z0, PED_Z1)
        ped.add(v, f)
        o = obj(P + 'Copper_Pedestal', ped.build(P + 'Copper_Pedestal'), coll, mat=mats['cu_pol'])
        add_bevel(o, 0.5, 3)
        objs.append(o)
        base = MeshAccum()
        v, f = slab_from_loops(rounded_rect_2d(172.0, 34.0, 3.0, 4) + np.array([0.0, 75.0]), [], PED_Z1, BASE_Z1)
        base.add(v, f)
        o = obj(P + 'Fin_Base_Al', base.build(P + 'Fin_Base_Al'), coll, mat=mats['al_sheet'])
        add_bevel(o, 0.5, 2)
        objs.append(o)
        pipes = MeshAccum()
        sec = rounded_rect_2d(8.4, 2.7, 1.3, 6)
        zc = PED_Z1 + 1.35
        routes = [
            [(sx - 10.5, sy - 16.0, zc), (sx - 10.5, 52.0, zc), (-30.0, 62.0, zc), (-82.0, 62.0, zc)],
            [(sx, sy - 16.0, zc), (sx, 70.0, zc), (sx, 86.0, zc)],
            [(sx + 10.5, sy - 16.0, zc), (sx + 10.5, 52.0, zc), (30.0, 62.0, zc), (82.0, 62.0, zc)],
        ]
        for r in routes:
            pth = fillet_path3d(r, 9.0, 12)
            v, f = sweep_section_along_path3d(pth, sec)
            pipes.add(v, f)
        o = obj(P + 'Heat_Pipes', pipes.build(P + 'Heat_Pipes'), coll, mat=mats['cu'])
        add_smooth_mod(o, 40)
        o['note'] = 'M5 Max: copper heat pipe(s) per Tom\'s Hardware; pipe count/route is illustrative'
        objs.append(o)
        clamp = MeshAccum()
        cl = rounded_rect_2d(44.0, 30.0, 5.0, 6) + np.array([sx, sy - 2.0])
        v, f = slab_from_loops(cl, [], zc + 1.35, zc + 2.5)
        clamp.add(v, f)
        for (dx, dy) in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            path = [(sx + dx * 16.0, sy - 2.0 + dy * 10.0, zc + 1.9), (sx + dx * 34.0, sy - 2.0 + dy * 24.0, zc + 1.9)]
            v, f = sweep_section_along_path3d(np.array(path), rounded_rect_2d(7.0, 1.1, 0.2, 2))
            clamp.add(v, f)
            clamp.add_cyl((sx + dx * 34.0, sy - 2.0 + dy * 24.0, zc + 1.9), 4.4, 1.1, n=32)
        o = obj(P + 'Clamp_Plate', clamp.build(P + 'Clamp_Plate'), coll, mat=mats['al_sheet'])
        add_bevel(o, 0.25, 2)
        objs.append(o)
        fins = MeshAccum()
        pitch = fin_stack(fins, D.FIN_COUNT_MAX, 0.4)
        end_plates(fins)
        o = obj(P + 'Fin_Stack_Aluminium', fins.build(P + 'Fin_Stack_Aluminium'), coll, mat=mats['al_fin'])
        o['fins'] = D.FIN_COUNT_MAX
        o['fin_pitch_mm'] = round(pitch, 3)
        o['material'] = 'aluminium'
        objs.append(o)
        clamp_pts = [(sx + dx * 34.0, sy - 2.0 + dy * 24.0) for dx in (-1, 1) for dy in (-1, 1)]
    acc = MeshAccum()
    u_shape = fillet_polyline([(82.0, 57.0), (89.0, 57.0), (89.0, -88.0), (-89.0, -88.0), (-89.0, 57.0), (-75.0, 57.0),
                               (-75.0, -74.0), (75.0, -74.0), (75.0, 57.0), (82.0, 57.0)],
                              [0, 0, 12, 12, 0, 0, 6, 6, 0, 0], arc_seg=6)[:-1]
    v, f = slab_from_loops(u_shape, [], BASE_Z1 + 0.25, BASE_Z1 + 1.25)
    acc.add(v, f)
    for (x, y) in MOUNTS:
        acc.add_cyl((x, y, (D.BOARD_Z + D.BOARD_T + BASE_Z1 + 1.25) / 2), 2.8, BASE_Z1 + 1.25 - D.BOARD_Z - D.BOARD_T, n=32)
        acc.add_cyl((x, y, BASE_Z1 + 0.75), 5.0, 1.0, n=32)
    o = obj(P + 'Module_Sheet', acc.build(P + 'Module_Sheet'), coll, mat=mats['al_dark'])
    add_bevel(o, 0.35, 2)
    o['note'] = 'thermal module sheet + 4 mounting standoffs (Torx Plus 20IP to housing); outline approximate'
    objs.append(o)
    ms = MeshAccum()
    for (x, y) in MOUNTS:
        ms.add_cyl((x, y, BASE_Z1 + 2.2), 4.0, 1.9, n=32)
    o = obj(P + 'Mount_Screws', ms.build(P + 'Mount_Screws'), coll, mat=mats['steel'])
    add_bevel(o, 0.3, 2)
    objs.append(o)
    scr = MeshAccum()
    for (x, y) in clamp_pts:
        scr.add_cyl((x, y, BASE_Z1 + 1.8), 2.6, 1.6, n=28)
    o = obj(P + 'Screws', scr.build(P + 'Screws'), coll, mat=mats['steel'])
    add_bevel(o, 0.3, 2)
    objs.append(o)
    for o in objs:
        o['part'] = 'Thermal_' + variant
    return dict(objects=objs)
