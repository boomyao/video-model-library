import math
import re
import bpy
import numpy as np
from mathutils import geometry as mgeom, Vector
from . import dims as D
from .util import MM, mesh_np, obj, recalc_normals, points_mesh, MeshAccum, rounded_rect_2d, circle_2d, add_bevel, add_smooth_mod
from .plan import PlanLoop
from .gn import holes_boolean_group


def section_profile():
    t, tt = D.WALL_T, D.TOP_T
    Rt, Rti, rb, rbi = D.TOP_FILLET, D.TOP_FILLET_IN, D.BOT_FILLET, D.BOT_FILLET_IN
    zb, zt = D.Z_HB, D.Z_TOP
    pts = []
    d_cap = Rt + 2.5
    pts.append((d_cap, zt))
    for a in np.linspace(0, 90, 13):
        r = math.radians(a)
        pts.append((Rt - Rt * math.sin(r), zt - Rt + Rt * math.cos(r)))
    z_hi = zt - Rt
    z_lo = zb + rb
    nwall = max(2, int((z_hi - z_lo) / 1.5))
    for z in np.linspace(z_hi, z_lo, nwall + 1)[1:]:
        pts.append((0.0, z))
    for a in np.linspace(0, 90, 7)[1:]:
        r = math.radians(a)
        pts.append((rb - rb * math.cos(r), zb + rb - rb * math.sin(r)))
    pts.append((t - rbi, zb))
    for a in np.linspace(0, 90, 5)[1:]:
        r = math.radians(a)
        pts.append((t - rbi + rbi * math.sin(r), zb + rbi - rbi * math.cos(r)))
    z_lo2 = zb + rbi
    z_hi2 = zt - tt - Rti
    nwall2 = max(2, int((z_hi2 - z_lo2) / 1.5))
    for z in np.linspace(z_lo2, z_hi2, nwall2 + 1)[1:]:
        pts.append((t, z))
    for a in np.linspace(0, 90, 7)[1:]:
        r = math.radians(a)
        pts.append((t + Rti - Rti * math.cos(r), zt - tt - Rti + Rti * math.sin(r)))
    d_cap_i = t + Rti + 1.5
    pts.append((d_cap_i, zt - tt))
    return np.array(pts), d_cap, d_cap_i


def build_shell(plan, name='Housing'):
    s = plan.sample_adaptive(ds_flat=1.2, ds_curve=0.5)
    P, Nn = plan.eval(s)
    prof, d_cap, d_cap_i = section_profile()
    n = len(s)
    m = len(prof)
    verts = np.zeros((m, n, 3))
    for j, (d, z) in enumerate(prof):
        verts[j, :, 0] = P[:, 0] - d * Nn[:, 0]
        verts[j, :, 1] = P[:, 1] - d * Nn[:, 1]
        verts[j, :, 2] = z
    V = verts.reshape(-1, 3)
    faces = []
    for j in range(m - 1):
        a = j * n
        b = (j + 1) * n
        for i in range(n):
            i2 = (i + 1) % n
            faces.append((a + i, a + i2, b + i2, b + i))
    faces.append(tuple(range(0, n)))
    faces.append(tuple(range((m - 1) * n, m * n)))
    me = mesh_np(name, V * MM, faces)
    recalc_normals(me)
    return me


def grille_points(plan):
    pitch, rowp = D.GRILLE_PITCH, D.GRILLE_ROW
    flat_half = D.HALF - D.CORNER_R
    ss = np.linspace(flat_half, flat_half + 70, 2000)
    P, Nn = plan.eval(-ss)
    ang = np.degrees(np.arctan2(Nn[:, 0], Nn[:, 1]))
    corner_end = ss[np.argmax(np.abs(ang) > 89.9)]
    corner_len = corner_end - flat_half
    s_max = flat_half + D.GRILLE_WRAP * corner_len
    nrows = int(math.floor((D.GRILLE_Z1 - D.GRILLE_Z0) / rowp)) + 1
    z0 = D.GRILLE_Z0 + ((D.GRILLE_Z1 - D.GRILLE_Z0) - (nrows - 1) * rowp) / 2
    pts = []
    dirs = []
    for k in range(nrows):
        z = z0 + k * rowp
        off = 0.5 * pitch if k % 2 else 0.0
        kmax = int(math.floor((s_max - off) / pitch))
        kmin = int(math.ceil((-s_max - off) / pitch))
        sv = off + np.arange(kmin, kmax + 1) * pitch
        sv = sv[np.abs(sv) <= s_max - 0.0]
        Pp, Np = plan.eval(-sv)
        mid = D.WALL_T * 0.5
        for (x, y), (nx, ny) in zip(Pp, Np):
            pts.append((x - mid * nx, y - mid * ny, z))
            dirs.append((-nx, -ny, 0.0))
    return np.array(pts), np.array(dirs), s_max


FRONT_PORTS = [
    dict(name='USBC_F1', x=-66.5, shape='stadium', w=2.6, h=8.34, kind='usbc'),
    dict(name='USBC_F2', x=-51.5, shape='stadium', w=2.6, h=8.34, kind='usbc'),
    dict(name='SDXC', x=-24.6, shape='rrect', w=26.8, h=2.5, r=0.9, kind='sd'),
    dict(name='LED', x=65.5, shape='circle', w=1.6, h=1.6, kind='led'),
]

REAR_PORTS = [
    dict(name='TB5_1', u=32.0, shape='stadium', w=2.6, h=8.34, kind='usbc'),
    dict(name='TB5_2', u=41.0, shape='stadium', w=2.6, h=8.34, kind='usbc'),
    dict(name='TB5_3', u=50.0, shape='stadium', w=2.6, h=8.34, kind='usbc'),
    dict(name='TB5_4', u=59.0, shape='stadium', w=2.6, h=8.34, kind='usbc'),
    dict(name='RJ45', u=76.0, shape='rj45', w=11.8, h=9.6, r=0.6, kind='rj45'),
    dict(name='AC', u=94.5, shape='circle', w=12.6, h=12.6, kind='ac'),
    dict(name='USBA_1', u=111.5, shape='rrect', w=5.2, h=12.6, r=0.5, kind='usba'),
    dict(name='USBA_2', u=120.5, shape='rrect', w=5.2, h=12.6, r=0.5, kind='usba'),
    dict(name='HDMI', u=137.0, shape='hdmi', w=15.0, h=5.7, kind='hdmi'),
    dict(name='JACK', u=153.0, shape='circle', w=5.2, h=5.2, kind='jack'),
    dict(name='POWER', u=168.0, shape='circle', w=10.3, h=10.3, kind='power'),
]


def port_outline(p):
    sh = p['shape']
    w, h = p['w'], p['h']
    if sh == 'stadium':
        return rounded_rect_2d(w, h, min(w, h) / 2 - 1e-4, seg=10)
    if sh == 'rrect':
        return rounded_rect_2d(w, h, p.get('r', 0.5), seg=6)
    if sh == 'circle':
        n = 48 if w > 4 else 24
        return circle_2d(w / 2, n)
    if sh == 'hdmi':
        tw, bw, hh = w, w - 3.6, h
        ch = 1.9
        pts = [(-tw / 2, hh / 2), (-tw / 2, hh / 2 - (hh - ch)), (-bw / 2, -hh / 2), (bw / 2, -hh / 2),
               (tw / 2, hh / 2 - (hh - ch)), (tw / 2, hh / 2)]
        return np.array(pts[::-1])
    if sh == 'rj45':
        o = rounded_rect_2d(w, h, p.get('r', 0.5), seg=4)
        return o
    raise ValueError(sh)


def port_frame(p):
    if 'x' in p:
        xc = p['x']
        return lambda u, v, w: (xc + u, -D.HALF + w, D.PORT_Z + v)
    xc = D.HALF - p['u']
    return lambda u, v, w: (xc - u, D.HALF - w, D.PORT_Z + v)


def prism_local(outline, w0, w1, fmap):
    o = np.asarray(outline)
    n = len(o)
    v0 = [fmap(u, v, w0) for u, v in o]
    v1 = [fmap(u, v, w1) for u, v in o]
    verts = np.array(v0 + v1)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        i2 = (i + 1) % n
        faces.append((i, i2, n + i2, n + i))
    return verts, faces


def build_port_cutters(coll, mats):
    acc = MeshAccum()
    for p in FRONT_PORTS + REAR_PORTS:
        fmap = port_frame(p)
        v, f = prism_local(port_outline(p), -1.5, D.WALL_T + 1.2, fmap)
        acc.add(v, f)
        if p['kind'] == 'rj45':
            v, f = prism_local(rounded_rect_2d(6.2, 2.4, 0.3, 3) + np.array([0, -p['h'] / 2 - 0.9]), -1.5, D.WALL_T + 1.2, fmap)
            acc.add(v, f)
    me = acc.build('CUT_Ports')
    ob = obj('CUT_Ports', me, coll, mat=mats['al'])
    ob.hide_render = True
    ob.hide_viewport = True
    ob.display_type = 'WIRE'
    return ob


def build_port_inserts(coll, mats, ports=None, suffix=''):
    acc = MeshAccum()
    gold = MeshAccum()
    alu = MeshAccum()
    pins = MeshAccum()
    t = D.WALL_T
    for p in (ports if ports is not None else FRONT_PORTS + REAR_PORTS):
        fmap = port_frame(p)
        k = p['kind']
        o = port_outline(p)
        if k in ('usbc', 'sd', 'usba', 'hdmi', 'rj45', 'jack', 'ac'):
            depth = {'usbc': 7.2, 'sd': 9.0, 'usba': 12.0, 'hdmi': 9.0, 'rj45': 14.0, 'jack': 12.0, 'ac': 9.0}[k]
            n = len(o)
            v0 = [fmap(u, v, t - 0.05) for u, v in o]
            v1 = [fmap(u, v, t + depth) for u, v in o]
            verts = np.array(v0 + v1)
            faces = [tuple(range(n, 2 * n))]
            for i in range(n):
                i2 = (i + 1) % n
                faces.append((i, i2, n + i2, n + i))
            acc.add(verts, faces)
            if k == 'rj45':
                o2 = rounded_rect_2d(6.2, 2.4, 0.3, 3) + np.array([0, -p['h'] / 2 - 0.9])
                v, f = prism_local(o2, t - 0.05, t + 4.0, fmap)
                acc.add(v, f)
        if k == 'usbc':
            v, f = prism_local(rounded_rect_2d(0.7, 6.6, 0.2, 3), 2.2, 7.0, fmap)
            acc.add(v, f)
            for su in (-1, 1):
                v, f = prism_local(rounded_rect_2d(0.04, 5.4, 0.0), 2.6, 5.0, lambda u, vv, w, su=su: fmap(u + su * 0.37, vv, w))
                gold.add(v, f)
        elif k == 'usba':
            v, f = prism_local(rounded_rect_2d(1.9, 11.0, 0.2, 3), 2.4, 11.0, lambda u, vv, w: fmap(u + 1.0, vv, w))
            acc.add(v, f)
            for j in range(4):
                v, f = prism_local(rounded_rect_2d(0.05, 1.2, 0.0), 4.0, 8.5, lambda u, vv, w, j=j: fmap(u + 0.03 - 0.0, vv - 4.1 + j * 2.5, w))
                gold.add(v, f)
        elif k == 'hdmi':
            v, f = prism_local(rounded_rect_2d(11.0, 0.9, 0.2, 3), 2.6, 8.0, lambda u, vv, w: fmap(u, vv + 0.4, w))
            acc.add(v, f)
            v, f = prism_local(rounded_rect_2d(9.6, 0.05, 0.0), 3.0, 7.0, lambda u, vv, w: fmap(u, vv + 0.87, w))
            gold.add(v, f)
        elif k == 'rj45':
            for j in range(8):
                v, f = prism_local(rounded_rect_2d(0.35, 0.35, 0.0), 6.0, 13.0, lambda u, vv, w, j=j: fmap(u - 4.45 + j * 1.27, vv + 3.2, w))
                gold.add(v, f)
        elif k == 'ac':
            cl = []
            for a in (90, 210, 330):
                c = np.array([math.cos(math.radians(a)), math.sin(math.radians(a))]) * 2.4
                cl.append(c)
            for c in cl:
                v, f = prism_local(circle_2d(2.9, 24) + c, t + 2.0, t + 8.9, fmap)
                acc.add(v, f)
            for c in (np.array([-1.9, -0.6]), np.array([1.9, -0.6])):
                v, f = prism_local(circle_2d(0.65, 12) + c, t + 0.8, t + 2.1, fmap)
                pins.add(v, f)
        elif k == 'jack':
            v, f = prism_local(circle_2d(1.9, 24), t + 0.3, t + 12.0, fmap)
            acc.add(v, f)
        elif k == 'power':
            v, f = prism_local(circle_2d(4.8, 64), 0.35, t + 1.5, fmap)
            alu.add(v, f)
            v, f = prism_local(circle_2d(5.3, 48), t + 1.5, t + 2.5, fmap)
            acc.add(v, f)
        elif k == 'led':
            v, f = prism_local(circle_2d(0.78, 24), 0.08, t + 1.0, fmap)
            pins.add(v, f)
    out = []
    if acc.v:
        o1 = obj('Port_Inserts' + suffix, acc.build('Port_Inserts' + suffix), coll, mat=mats['plastic'])
        add_smooth_mod(o1, 35)
        out.append(o1)
    if gold.v:
        out.append(obj('Port_Contacts' + suffix, gold.build('Port_Contacts' + suffix), coll, mat=mats['gold']))
    if alu.v:
        o3 = obj('Power_Button', alu.build('Power_Button'), coll, mat=mats['al'])
        add_smooth_mod(o3, 35)
        out.append(o3)
    if pins.v:
        out.append(obj('Port_Pins' + suffix, pins.build('Port_Pins' + suffix), coll, mat=mats['steel']))
    return out


def _svg_tokens(d):
    return re.findall(r'[MmLlHhVvCcSsQqTtZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?', d)


def parse_svg_path(d, bez_seg=24):
    toks = _svg_tokens(d)
    i = 0
    loops = []
    cur = None
    pos = np.array([0.0, 0.0])
    start = pos.copy()
    last_c2 = None
    cmd = None

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v

    def cubic(p0, p1, p2, p3):
        ts = np.linspace(0, 1, bez_seg + 1)[1:]
        for tt in ts:
            mt = 1 - tt
            cur.append(mt ** 3 * p0 + 3 * mt * mt * tt * p1 + 3 * mt * tt * tt * p2 + tt ** 3 * p3)

    while i < len(toks):
        tk = toks[i]
        if re.match(r'[A-Za-z]', tk):
            cmd = tk
            i += 1
            if cmd in 'Zz':
                if cur is not None and len(cur) > 2:
                    loops.append(np.array(cur))
                cur = None
                pos = start.copy()
                last_c2 = None
                continue
        rel = cmd.islower()
        C = cmd.upper()
        base = pos if rel else np.array([0.0, 0.0])
        if C == 'M':
            p = np.array([num(), num()]) + base
            if cur is not None and len(cur) > 2:
                loops.append(np.array(cur))
            cur = [p]
            pos = p
            start = p.copy()
            cmd = 'l' if rel else 'L'
            last_c2 = None
        elif C == 'L':
            p = np.array([num(), num()]) + base
            cur.append(p)
            pos = p
            last_c2 = None
        elif C == 'H':
            x = num() + (pos[0] if rel else 0)
            p = np.array([x, pos[1]])
            cur.append(p)
            pos = p
            last_c2 = None
        elif C == 'V':
            y = num() + (pos[1] if rel else 0)
            p = np.array([pos[0], y])
            cur.append(p)
            pos = p
            last_c2 = None
        elif C == 'C':
            p1 = np.array([num(), num()]) + base
            p2 = np.array([num(), num()]) + base
            p3 = np.array([num(), num()]) + base
            cubic(pos, p1, p2, p3)
            last_c2 = p2
            pos = p3
        elif C == 'S':
            p1 = 2 * pos - last_c2 if last_c2 is not None else pos.copy()
            p2 = np.array([num(), num()]) + base
            p3 = np.array([num(), num()]) + base
            cubic(pos, p1, p2, p3)
            last_c2 = p2
            pos = p3
        else:
            raise ValueError('unsupported svg cmd ' + cmd)
    if cur is not None and len(cur) > 2:
        loops.append(np.array(cur))
    return loops


def build_logo(coll, mats, svg_path):
    txt = open(svg_path).read()
    d = re.search(r'\bd="([^"]+)"', txt).group(1)
    loops = parse_svg_path(d)
    allp = np.vstack(loops)
    mn = allp.min(0)
    mx = allp.max(0)
    sc = D.LOGO_H / (mx[1] - mn[1])
    ctr = (mn + mx) / 2
    acc = MeshAccum()
    z1 = D.Z_TOP + 0.004
    z0 = D.Z_TOP - 0.25
    for lp in loops:
        q = (lp - ctr) * sc
        q[:, 1] *= -1
        keep = [0]
        for k in range(1, len(q)):
            if np.linalg.norm(q[k] - q[keep[-1]]) > 1e-4:
                keep.append(k)
        q = q[keep]
        if np.linalg.norm(q[0] - q[-1]) < 1e-4:
            q = q[:-1]
        from .util import polygon_area
        if polygon_area(q) < 0:
            q = q[::-1]
        n = len(q)
        tris = mgeom.tessellate_polygon([[Vector((x, y, 0)) for x, y in q]])
        top = np.column_stack([q, np.full(n, z1)])
        bot = np.column_stack([q, np.full(n, z0)])
        verts = np.vstack([top, bot])
        faces = [tuple(t) for t in tris]
        faces += [(t[2] + n, t[1] + n, t[0] + n) for t in tris]
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((k, k + n, k2 + n, k2))
        acc.add(verts, faces)
    me = acc.build('Apple_Logo')
    ob = obj('Apple_Logo', me, coll, mat=mats['logo'])
    w = (mx[0] - mn[0]) * sc
    ob['logo_bbox_mm'] = (round(w, 2), D.LOGO_H)
    return ob


def build(coll, ports_coll, mats, assets_dir, quality=None):
    plan = PlanLoop()
    me = build_shell(plan)
    housing = obj('Housing', me, coll, mat=mats['al'])
    pts, dirs, s_max = grille_points(plan)
    gp = points_mesh('PTS_Grille', pts * MM, {'dir': ('FLOAT_VECTOR', dirs)})
    gpo = obj('PTS_Grille', gp, coll)
    gpo.hide_render = True
    gpo.hide_viewport = True
    cut_ports = build_port_cutters(coll, mats)
    ng = holes_boolean_group('GN_Housing_Cuts', gpo, mats['al_drill'], extra_cutter=cut_ports,
                             radius_mm=D.GRILLE_HOLE_D / 2, depth_mm=D.WALL_T + 2.4, segments=12)
    mod = housing.modifiers.new('Holes_Ports', 'NODES')
    mod.node_group = ng
    housing['grille_holes'] = len(pts)
    housing['grille_wrap_s_mm'] = round(float(s_max), 2)
    logo = build_logo(coll, mats, assets_dir + '/apple_logo.svg')
    front = build_port_inserts(ports_coll, mats, FRONT_PORTS, '_Front')
    for o in front:
        o['hide_in_cut'] = 'front'
    rear = build_port_inserts(ports_coll, mats, REAR_PORTS, '_Rear')
    inserts = front + rear
    pb = [o for o in inserts if o.name.startswith('Power_Button')]
    for o in pb:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    return dict(housing=housing, logo=logo, grille_pts=gpo, cut_ports=cut_ports, inserts=inserts, plan=plan)


def grille_proxy(coll, plan):
    pts, dirs, s_max = grille_points(plan)
    ss = np.linspace(-s_max, s_max, 121)
    P, Nn = plan.eval(-ss)
    zs = np.linspace(D.GRILLE_Z0, D.GRILLE_Z1, 9)
    verts = []
    for z in zs:
        for (x, y), (nx, ny) in zip(P, Nn):
            verts.append((x + 0.05 * nx, y + 0.05 * ny, z))
    n = len(ss)
    faces = []
    for j in range(len(zs) - 1):
        for i in range(n - 1):
            a = j * n + i
            b = (j + 1) * n + i
            faces.append((a, a + 1, b + 1, b))
    me = mesh_np('Rear_Grille_FX_Proxy', np.array(verts) * MM, faces)
    ob = obj('Rear_Grille_FX_Proxy', me, coll)
    ob.hide_render = True
    ob.display_type = 'WIRE'
    ob['purpose'] = 'exhaust emitter surface for later airflow/heat FX (outer face of the hex grille region)'
    return ob
