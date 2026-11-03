import math
import numpy as np
from . import dims as D
from .util import MM, obj, MeshAccum, add_bevel, add_smooth_mod, rounded_rect_2d, circle_2d, slab_from_loops, revolve_profile

WIN = D.HALF - D.WALL_T


def strip(acc_c, acc_g, wall, a0, a1, z0, z1, segs):
    t = 1.4
    if wall == 'right':
        acc_c.add_box((WIN - t / 2 - 0.1, (a0 + a1) / 2, (z0 + z1) / 2), (t, a1 - a0, z1 - z0))
        L = (a1 - a0 - 2.0) / segs
        for k in range(segs):
            c = a0 + 1.0 + L * (k + 0.5)
            acc_g.add_box((WIN - t - 0.16, c, (z0 + z1) / 2), (0.06, L - 0.8, z1 - z0 - 2.2))
    elif wall == 'left':
        acc_c.add_box((-WIN + t / 2 + 0.1, (a0 + a1) / 2, (z0 + z1) / 2), (t, a1 - a0, z1 - z0))
        L = (a1 - a0 - 2.0) / segs
        for k in range(segs):
            c = a0 + 1.0 + L * (k + 0.5)
            acc_g.add_box((-WIN + t + 0.16, c, (z0 + z1) / 2), (0.06, L - 0.8, z1 - z0 - 2.2))
    elif wall == 'front':
        acc_c.add_box(((a0 + a1) / 2, -WIN + t / 2 + 0.1, (z0 + z1) / 2), (a1 - a0, t, z1 - z0))
        L = (a1 - a0 - 2.0) / segs
        for k in range(segs):
            c = a0 + 1.0 + L * (k + 0.5)
            acc_g.add_box((c, -WIN + t + 0.16, (z0 + z1) / 2), (L - 0.8, 0.06, z1 - z0 - 2.2))


def build(coll, mats, **kw):
    car_side = MeshAccum()
    gold_side = MeshAccum()
    strip(car_side, gold_side, 'right', -30.0, 40.0, 17.0, 27.0, 3)
    strip(car_side, gold_side, 'left', -30.0, 40.0, 17.0, 27.0, 3)
    car_front = MeshAccum()
    gold_front = MeshAccum()
    strip(car_front, gold_front, 'front', 4.0, 56.0, 17.0, 27.0, 2)
    o1 = obj('Antenna_Carriers', car_side.build('Antenna_Carriers'), coll, mat=mats['plastic'])
    add_bevel(o1, 0.3, 2)
    o2 = obj('Antenna_Gold', gold_side.build('Antenna_Gold'), coll, mat=mats['gold_flex'])
    o3 = obj('Antenna_Front_Carrier', car_front.build('Antenna_Front_Carrier'), coll, mat=mats['plastic'])
    add_bevel(o3, 0.3, 2)
    o4 = obj('Antenna_Front_Gold', gold_front.build('Antenna_Front_Gold'), coll, mat=mats['gold_flex'])
    for o in (o3, o4):
        o['hide_in_cut'] = 'front'

    spk = MeshAccum()
    sx, sy = -66.0, 64.0
    prof = [(0.0, 25.0), (13.5, 25.0), (14.5, 26.0), (14.5, 34.0), (13.5, 35.0), (0.0, 35.0)]
    v, f, _ = revolve_profile(prof, 96)
    v[:, 0] += sx
    v[:, 1] += sy
    spk.add(v, f)
    for k in range(2):
        a = math.radians(30 + 180 * k)
        c = np.array([sx, sy]) + 17.0 * np.array([math.cos(a), math.sin(a)])
        v, f = slab_from_loops(rounded_rect_2d(8.0, 6.0, 2.0, 3) + c, [circle_2d(1.1, 12) + c], 33.8, 35.0)
        spk.add(v, f)
    o5 = obj('Speaker', spk.build('Speaker'), coll, mat=mats['plastic'])
    add_smooth_mod(o5, 35)
    mesh = MeshAccum()
    v, f, _ = revolve_profile([(0.0, 24.6), (11.0, 24.6), (11.0, 25.1), (0.0, 25.1)], 96)
    v[:, 0] += sx
    v[:, 1] += sy
    mesh.add(v, f)
    o6 = obj('Speaker_Mesh', mesh.build('Speaker_Mesh'), coll, mat=mats['spk'])

    flex = MeshAccum()
    flex.add_box((D.HALF - 59.0 - 13.0, WIN - 13.5, 24.0), (40.0, 1.0, 22.0))
    flex.add_box((D.HALF - 76.0, WIN - 16.0, 24.0), (16.0, 1.0, 22.0))
    flex.add_box((D.HALF - 125.0, WIN - 15.0, 24.0), (52.0, 1.0, 22.0))
    flex.add_box((D.HALF - 160.0, WIN - 15.0, 24.0), (20.0, 1.0, 22.0))
    o7 = obj('Port_Boards_Rear', flex.build('Port_Boards_Rear'), coll, mat=mats['pcb'])
    add_bevel(o7, 0.2, 2)
    fflex = MeshAccum()
    fflex.add_box((-48.0, -WIN + 10.5, 23.5), (50.0, 1.0, 16.0))
    o8 = obj('Port_Boards_Front', fflex.build('Port_Boards_Front'), coll, mat=mats['pcb'])
    add_bevel(o8, 0.2, 2)
    o8['hide_in_cut'] = 'front'
    housing_mounted = [o1, o2, o3, o4, o5, o6, o7, o8]
    for o in housing_mounted:
        o['part'] = 'Antennas_Ports'
    return dict(housing_mounted=housing_mounted, board_mounted=[])
