import math
import numpy as np
from . import dims as D
from .util import MM, mesh_np, obj, MeshAccum, recalc_normals, add_bevel, add_smooth_mod, rounded_rect_2d, circle_2d, slab_from_loops
from .plan import PlanLoop


def build(coll, mats, **kw):
    plan = PlanLoop()
    s = plan.sample_adaptive(ds_flat=2.0, ds_curve=0.8)
    P, Nn = plan.eval(s)
    d0, d1 = D.WALL_T + 0.5, D.WALL_T + 7.0
    z0, z1 = D.FRAME_Z0 + 0.6, D.FRAME_Z1
    outer = P - d0 * Nn
    inner = P - d1 * Nn
    acc = MeshAccum()
    v, f = slab_from_loops(outer, [inner], z1 - 0.9, z1)
    acc.add(v, f)
    lip_o = P - (d0) * Nn
    lip_i = P - (d0 + 0.9) * Nn
    v, f = slab_from_loops(lip_o, [lip_i], z0, z1 - 0.9)
    acc.add(v, f)
    lip_o2 = P - (d1 - 0.9) * Nn
    v, f = slab_from_loops(lip_o2, [inner], z0 + 1.2, z1 - 0.9)
    acc.add(v, f)
    tabs = []
    for k in range(8):
        a = math.radians(45 * k)
        if k % 2 == 0:
            ss = plan.s_at_point((math.sin(a) * 120, math.cos(a) * 120))
        else:
            ss = plan.s_at_point((math.sin(a) * 200, math.cos(a) * 200))
        pp, nn = plan.eval(np.array([ss]))
        c = pp[0] - (d1 + 3.2) * nn[0]
        tabs.append(c)
        tab = rounded_rect_2d(11.0, 8.0, 2.5, 4)
        ang = math.atan2(nn[0][1], nn[0][0])
        R = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
        o = tab @ R.T + c + nn[0] * 2.0
        v, f = slab_from_loops(o, [circle_2d(1.3, 16) + c], z1 - 0.9, z1)
        acc.add(v, f)
    fr = obj('Internal_Frame', acc.build('Internal_Frame'), coll, mat=mats['paint'])
    add_smooth_mod(fr, 35)
    scr = MeshAccum()
    for c in tabs:
        scr.add_cyl((c[0], c[1], z1 + 0.5), 1.9, 1.0, n=24)
    so = obj('Internal_Frame_Screws', scr.build('Internal_Frame_Screws'), coll, mat=mats['steel_dark'])
    add_bevel(so, 0.25, 2)
    plate = MeshAccum()
    o = rounded_rect_2d(150.0, 142.0, 22.0, 8) + np.array([0.0, -4.0])
    notch = rounded_rect_2d(40.0, 18.0, 4.0, 4) + np.array([0.0, 62.0])
    v, f = slab_from_loops(o, [], z0 - 0.35, z0 - 0.05)
    plate.add(v, f)
    po = obj('Internal_Frame_Plate', plate.build('Internal_Frame_Plate'), coll, mat=mats['rubber'])
    objs = [fr, so, po]
    for o in objs:
        o['part'] = 'Internal_Frame'
    return dict(objects=objs)
