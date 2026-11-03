import math
import numpy as np
from . import dims as D
from .util import MM, obj, MeshAccum, add_bevel, add_smooth_mod, rounded_rect_2d, slab_from_loops
from .board import cap_field

Z0 = D.BOARD_Z + D.BOARD_T + 0.25
SUB_T = 1.3
INT_T = 0.32
DIE_T = 0.72
MEM_T = 1.05


def package(coll, mats, prefix, pairs, sub_w, sub_h, die_w, die_h, mem_rows, mem_w, mem_h, mem_n):
    sx, sy = D.SOC_CENTER
    objs = []
    sub = MeshAccum()
    v, f = slab_from_loops(rounded_rect_2d(sub_w, sub_h, 1.0, 4) + np.array([sx, sy]), [], Z0, Z0 + SUB_T)
    sub.add(v, f)
    o = obj(prefix + '_Substrate', sub.build(prefix + '_Substrate'), coll, mat=mats['substrate'])
    add_bevel(o, 0.12, 2)
    objs.append(o)
    zs = Z0 + SUB_T
    seam_fusion = 0.16
    seam_ultra = 0.55
    block_w = 2 * die_w + seam_fusion
    block_h = pairs * die_h + (pairs - 1) * seam_ultra
    itp = MeshAccum()
    v, f = slab_from_loops(rounded_rect_2d(block_w + 1.0, block_h + 1.0, 0.4, 3) + np.array([sx, sy]), [], zs, zs + INT_T)
    itp.add(v, f)
    o = obj(prefix + '_Interposer', itp.build(prefix + '_Interposer'), coll, mat=mats['steel_dark'])
    add_bevel(o, 0.06, 2)
    objs.append(o)
    zi = zs + INT_T
    names = ['A', 'B']
    die_objs = []
    for p in range(pairs):
        cy = sy - block_h / 2 + die_h / 2 + p * (die_h + seam_ultra)
        for j, k in enumerate((-1, 1)):
            cx = sx + k * (die_w + seam_fusion) / 2
            dm = MeshAccum()
            v, f = slab_from_loops(rounded_rect_2d(die_w, die_h, 0.12, 2) + np.array([cx, cy]), [], zi, zi + DIE_T)
            dm.add(v, f)
            dn = '%s_Die_%s%d' % (prefix, names[p], j + 1)
            o = obj(dn, dm.build(dn), coll, mat=mats['si'])
            add_bevel(o, 0.05, 2)
            o['die_center_mm'] = (cx, cy, zi + DIE_T)
            o['note'] = 'schematic layout: each M5 Max = 2 dies joined (fusion seam); Ultra = 2 x M5 Max joined by UltraFusion seam'
            objs.append(o)
            die_objs.append(o)
        sm = MeshAccum()
        sm.add_box((sx, cy, zi + DIE_T * 0.55), (seam_fusion * 0.8, die_h - 0.6, DIE_T * 0.9))
        sn = '%s_Seam_Fusion_%s' % (prefix, names[p])
        so = obj(sn, sm.build(sn), coll, mat=mats['seam'])
        so['seam_center_mm'] = (sx, cy, zi + DIE_T)
        objs.append(so)
    if pairs > 1:
        br = MeshAccum()
        br.add_box((sx, sy, zi + DIE_T * 0.5), (block_w - 1.2, seam_ultra * 0.75, DIE_T * 0.85))
        bn = prefix + '_Seam_UltraFusion'
        o = obj(bn, br.build(bn), coll, mat=mats['seam'])
        o['seam_center_mm'] = (sx, sy, zi + DIE_T)
        objs.append(o)
    gap = 1.6
    row_w = mem_n * mem_w + (mem_n - 1) * gap
    mi = 0
    for side in (-1, 1):
        if side == -1 and mem_rows == 1:
            continue
        cy = sy + side * (block_h / 2 + 1.8 + mem_h / 2)
        for i in range(mem_n):
            cx = sx - row_w / 2 + mem_w / 2 + i * (mem_w + gap)
            mm_ = MeshAccum()
            v, f = slab_from_loops(rounded_rect_2d(mem_w, mem_h, 0.3, 2) + np.array([cx, cy]), [], zs, zs + MEM_T)
            mm_.add(v, f)
            mi += 1
            mn = '%s_Memory_%d' % (prefix, mi)
            o = obj(mn, mm_.build(mn), coll, mat=mats['chip'])
            add_bevel(o, 0.08, 2)
            o['mem_center_mm'] = (cx, cy, zs + MEM_T)
            objs.append(o)
    body = MeshAccum()
    ends = MeshAccum()
    hw, hh = sub_w / 2, sub_h / 2
    rects = [(sx - hw + 0.8, sy - hh + 0.8, sx + hw - 0.8, sy - hh + 3.0), (sx - hw + 0.8, sy + hh - 3.0, sx + hw - 0.8, sy + hh - 0.8),
             (sx - hw + 0.8, sy - hh + 0.8, sx - hw + 2.6, sy + hh - 0.8), (sx + hw - 2.6, sy - hh + 0.8, sx + hw - 0.8, sy + hh - 0.8)]
    cap_field(body, ends, rects, 140 if pairs > 1 else 90, zs, seed=11 + pairs,
              sizes=((1.0, 0.5, 0.45), (0.6, 0.3, 0.3)))
    rects2 = [(sx - block_w / 2 - 0.2, sy - block_h / 2 - 1.6, sx + block_w / 2 + 0.2, sy - block_h / 2 - 0.7),
              (sx - block_w / 2 - 0.2, sy + block_h / 2 + 0.7, sx + block_w / 2 + 0.2, sy + block_h / 2 + 1.6),
              (sx - block_w / 2 - 2.2, sy - block_h / 2, sx - block_w / 2 - 0.7, sy + block_h / 2),
              (sx + block_w / 2 + 0.7, sy - block_h / 2, sx + block_w / 2 + 2.2, sy + block_h / 2)]
    cap_field(body, ends, rects2, 90 if pairs > 1 else 50, zs, seed=21 + pairs, sizes=((0.6, 0.3, 0.3), (0.4, 0.2, 0.2)))
    objs.append(obj(prefix + '_Caps', body.build(prefix + '_Caps', recalc=False), coll, mat=mats['cap']))
    objs.append(obj(prefix + '_Cap_Terminals', ends.build(prefix + '_Cap_Terminals', recalc=False), coll, mat=mats['tin']))
    for o in objs:
        o['part'] = 'SoC_Package'
        o['variant'] = prefix
    top = zi + DIE_T
    return objs, top


def build(coll_u, coll_m, mats):
    u, top_u = package(coll_u, mats, 'SoC_M5Ultra', pairs=2, sub_w=62.0, sub_h=66.0, die_w=15.4, die_h=12.6,
                       mem_rows=2, mem_w=11.6, mem_h=13.4, mem_n=4)
    m, top_m = package(coll_m, mats, 'SoC_M5Max', pairs=1, sub_w=50.0, sub_h=36.0, die_w=15.4, die_h=12.6,
                       mem_rows=2, mem_w=10.6, mem_h=9.0, mem_n=2)
    sx, sy = D.SOC_CENTER
    acc = MeshAccum()
    v, f = slab_from_loops(rounded_rect_2d(15.4, 12.6, 0.12, 2), [], 0.0, DIE_T)
    acc.add(v, f)
    dc = obj('Die_Closeup', acc.build('Die_Closeup'), coll_u, mat=mats['si_close'])
    dc.location = ((sx - 40.0) * MM, sy * MM, (Z0 + SUB_T + INT_T) * MM)
    add_bevel(dc, 0.05, 2)
    dc.hide_render = True
    dc.hide_viewport = True
    dc['purpose'] = 'single-die close-up material demo; unhide for die macro shots'
    return dict(objects=u + m + [dc], top_ultra=top_u, top_max=top_m)
