import math
import numpy as np
from . import dims as D
from .util import MM, obj, MeshAccum, add_bevel, add_smooth_mod, rounded_rect_2d, circle_2d, slab_from_loops
from .plan import PlanLoop

ZB0 = D.BOARD_Z
ZB1 = D.BOARD_Z + D.BOARD_T


def cap_field(acc_body, acc_end, rects, count, z_face, down=False, seed=1, sizes=((1.0, 0.5, 0.5), (0.6, 0.3, 0.3), (1.6, 0.8, 0.8)), avoid=()):
    rng = np.random.default_rng(seed)
    placed = 0
    tries = 0
    while placed < count and tries < count * 20:
        tries += 1
        rx0, ry0, rx1, ry1 = rects[rng.integers(len(rects))]
        x = rng.uniform(rx0, rx1)
        y = rng.uniform(ry0, ry1)
        if any(ax0 <= x <= ax1 and ay0 <= y <= ay1 for (ax0, ay0, ax1, ay1) in avoid):
            continue
        L, W, H = sizes[rng.integers(len(sizes))]
        rot = rng.random() < 0.5
        zc = z_face - H / 2 if down else z_face + H / 2
        e = L * 0.22
        if rot:
            acc_body.add_box((x, y, zc), (W, L - 2 * e, H))
            acc_end.add_box((x, y - (L - e) / 2, zc), (W * 1.02, e, H * 1.02))
            acc_end.add_box((x, y + (L - e) / 2, zc), (W * 1.02, e, H * 1.02))
        else:
            acc_body.add_box((x, y, zc), (L - 2 * e, W, H))
            acc_end.add_box((x - (L - e) / 2, y, zc), (e, W * 1.02, H * 1.02))
            acc_end.add_box((x + (L - e) / 2, y, zc), (e, W * 1.02, H * 1.02))
        placed += 1


def board_outline(plan):
    s = plan.sample_adaptive(ds_flat=3.0, ds_curve=1.0)
    P, Nn = plan.eval(s)
    return P - 6.0 * Nn


def build(coll, mats, **kw):
    plan = PlanLoop()
    objs = []
    outl = board_outline(plan)
    holes = []
    for (x, y) in [(-80.0, -80.0), (80.0, -80.0), (-89.0, 70.0), (89.0, 70.0)]:
        holes.append(circle_2d(2.4, 20) + np.array([x, y]))
    acc = MeshAccum()
    v, f = slab_from_loops(outl, holes, ZB0, ZB1)
    acc.add(v, f)
    pcb = obj('Logic_Board_PCB', acc.build('Logic_Board_PCB'), coll, mat=mats['pcb'])
    add_bevel(pcb, 0.25, 2)
    objs.append(pcb)

    ind = MeshAccum()
    sx, sy = D.SOC_CENTER
    for side in (-1, 1):
        for col in range(2):
            for row in range(8):
                x = sx + side * (41.0 + col * 7.0)
                y = sy - 30.0 + row * 7.2
                ind.add_box((x, y, ZB1 + 1.6), (5.6, 5.6, 3.2))
    for k in range(6):
        ind.add_box((-30.0 + k * 12.0, -62.0, ZB1 + 1.4), (8.0, 8.0, 2.8))
    o = obj('Board_Inductors', ind.build('Board_Inductors'), coll, mat=mats['ferrite'])
    add_bevel(o, 0.35, 2)
    objs.append(o)

    chips = MeshAccum()
    for (x, y, w, h, t) in [(-56, -40, 7, 7, 0.9), (-56, 30, 7, 7, 0.9), (56, -40, 7, 7, 0.9), (56, 30, 7, 7, 0.9),
                            (-20, 40, 9, 6, 0.8), (20, 40, 9, 6, 0.8), (-62, -64, 10, 10, 1.0), (40, -76, 6, 6, 0.8),
                            (-40, -76, 6, 6, 0.8), (0, 52, 12, 8, 1.1), (66, 52, 8, 8, 1.0), (-66, 52, 8, 8, 1.0)]:
        chips.add_box((x, y, ZB1 + t / 2), (w, h, t))
    o = obj('Board_ICs', chips.build('Board_ICs'), coll, mat=mats['chip'])
    add_bevel(o, 0.15, 2)
    objs.append(o)

    conn = MeshAccum()
    for (x, y, w, h, t) in [(-14, 70, 7, 3.4, 2.4), (14, 70, 7, 3.4, 2.4),
                            (-70, 80, 14, 4, 2.6), (-40, 80, 18, 4, 2.6), (-8, 80, 12, 4, 2.6), (24, 80, 16, 4, 2.6),
                            (60, 80, 14, 4, 2.6), (-50, -84, 14, 4, 2.6), (20, -84, 14, 4, 2.6)]:
        conn.add_box((x, y, ZB1 + t / 2), (w, h, t))
    o = obj('Board_Connectors', conn.build('Board_Connectors'), coll, mat=mats['satin'])
    add_bevel(o, 0.2, 2)
    objs.append(o)

    coin = MeshAccum()
    v, f = slab_from_loops(rounded_rect_2d(24.0, 24.0, 5.0, 6) + np.array([64.0, -60.0]), [], ZB1, ZB1 + 3.4)
    coin.add(v, f)
    o = obj('Board_CoinCell_Cover', coin.build('Board_CoinCell_Cover'), coll, mat=mats['paint'])
    add_bevel(o, 0.4, 2)
    objs.append(o)

    ant = MeshAccum()
    ant.add_box((80.0, 0.0, ZB1 + 2.0), (6.0, 64.0, 4.0))
    o = obj('Board_Antenna1_Carrier', ant.build('Board_Antenna1_Carrier'), coll, mat=mats['plastic'])
    add_bevel(o, 0.4, 2)
    objs.append(o)
    antg = MeshAccum()
    for k in range(5):
        antg.add_box((83.06, -26.0 + k * 13.0, ZB1 + 2.0), (0.1, 10.0, 2.6))
    objs.append(obj('Board_Antenna1_Gold', antg.build('Board_Antenna1_Gold'), coll, mat=mats['gold_flex']))

    body = MeshAccum()
    ends = MeshAccum()
    small = ((1.0, 0.5, 0.5), (0.6, 0.3, 0.3))
    top_rects = [(sx - 37, sy - 40, sx + 37, sy - 36), (sx - 37, sy + 36, sx + 37, sy + 40),
                 (sx - 38, sy - 36, sx - 35, sy + 36), (sx + 35, sy - 36, sx + 38, sy + 36),
                 (sx - 60, sy - 34, sx - 57, sy + 26), (sx + 57, sy - 34, sx + 60, sy + 26),
                 (-70, -50, -60, -30), (60, -46, 70, -34), (-30, -52, 30, -48), (-28, 48, 28, 50),
                 (-26, 60, 26, 63), (44, 60, 76, 63), (-76, 60, -44, 63)]
    cap_field(body, ends, top_rects, 420, ZB1, seed=3, sizes=small)
    under_rects = [(sx - 34, sy - 16, sx - 25, sy + 16), (sx + 25, sy - 16, sx + 34, sy + 16),
                   (sx - 20, sy - 22, sx + 20, sy - 19), (sx - 20, sy + 19, sx + 20, sy + 22),
                   (sx - 62, sy - 18, sx - 52, sy + 18), (sx + 52, sy - 18, sx + 62, sy + 18),
                   (-30, -78, 22, -74), (-78, 40, -40, 46), (20, 44, 50, 50), (66, -10, 74, 30)]
    cap_field(body, ends, under_rects, 380, ZB0, down=True, seed=9, sizes=small)
    o = obj('Board_Caps', body.build('Board_Caps', recalc=False), coll, mat=mats['cap'])
    objs.append(o)
    o = obj('Board_Cap_Terminals', ends.build('Board_Cap_Terminals', recalc=False), coll, mat=mats['tin'])
    objs.append(o)

    spring = MeshAccum()
    zs1 = ZB0 - 0.15
    for dy in (-27.0, 27.0):
        v, f = slab_from_loops(rounded_rect_2d(98.0, 11.0, 5.0, 6) + np.array([sx, sy + dy]), [], zs1 - 1.3, zs1)
        spring.add(v, f)
        for dx in (-49.0, 49.0):
            v, f = slab_from_loops(circle_2d(6.2, 40) + np.array([sx + dx, sy + dy]), [], zs1 - 2.6, zs1)
            spring.add(v, f)
    v, f = slab_from_loops(rounded_rect_2d(44.0, 50.0, 4.0, 4) + np.array([sx, sy]), [], zs1 - 1.6, zs1)
    spring.add(v, f)
    for k in range(13):
        x = sx - 18.0 + k * 3.0
        spring.add_box((x, sy, zs1 - 1.6 - 1.4), (1.6, 34.0, 2.8))
    for dx in (-9.0, 9.0):
        spring.add_box((sx + dx, sy, zs1 - 1.0), (6.0, 60.0, 1.6))
    o = obj('Board_Spring_Backplate', spring.build('Board_Spring_Backplate'), coll, mat=mats['paint'])
    add_bevel(o, 0.3, 2)
    objs.append(o)
    sc = MeshAccum()
    for dy in (-27.0, 27.0):
        for dx in (-49.0, 49.0):
            sc.add_cyl((sx + dx, sy + dy, zs1 - 3.2), 3.0, 1.4, n=32)
    o = obj('Board_Screws', sc.build('Board_Screws'), coll, mat=mats['steel'])
    add_bevel(o, 0.35, 2)
    objs.append(o)

    ssd = MeshAccum()
    ssd_chips = MeshAccum()
    ssd_gold = MeshAccum()
    for (cx, cy, rot) in [(48.0, -61.0, 0), (-62.0, 6.0, 1)]:
        def P(x, y):
            return (cx + x, cy + y) if rot == 0 else (cx - y, cy + x)
        zt = ZB0 - 2.4
        o2 = rounded_rect_2d(50.0, 30.0, 1.5, 3)
        if rot:
            o2 = o2[:, ::-1] * np.array([-1, 1])
        v, f = slab_from_loops(o2 + np.array([cx, cy]), [], zt - 0.8, zt)
        ssd.add(v, f)
        for (x, y, w, h) in [(-12.0, 0.0, 14.0, 18.0), (5.0, 0.0, 14.0, 18.0)]:
            px, py = P(x, y)
            ww, hh = (w, h) if rot == 0 else (h, w)
            ssd_chips.add_box((px, py, zt - 0.8 - 0.65), (ww, hh, 1.3))
        px, py = P(19.5, 0.0)
        ww, hh = (8.0, 9.0) if rot == 0 else (9.0, 8.0)
        ssd_chips.add_box((px, py, zt - 0.8 - 0.5), (ww, hh, 1.0))
        px, py = P(-23.0, 0.0)
        ww, hh = (3.0, 22.0) if rot == 0 else (22.0, 3.0)
        ssd.add_box((px, py, zt + 0.9), (ww, hh, 1.8))
        px, py = P(23.6, 0.0)
        ssd_gold.add_cyl((px, py, zt - 0.85), 1.6, 0.4, n=20)
    o = obj('SSD_Modules', ssd.build('SSD_Modules'), coll, mat=mats['pcb'])
    add_bevel(o, 0.15, 2)
    objs.append(o)
    o = obj('SSD_NAND', ssd_chips.build('SSD_NAND'), coll, mat=mats['chip'])
    add_bevel(o, 0.15, 2)
    objs.append(o)
    objs.append(obj('SSD_Screws', ssd_gold.build('SSD_Screws'), coll, mat=mats['steel']))
    for o in objs:
        o['part'] = 'Logic_Board'
    return dict(objects=objs)
