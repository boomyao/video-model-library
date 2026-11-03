# -*- coding: utf-8 -*-
"""通用造型的打印机：横梁、光杆、滑块、喷头、齿形带、皮带轮、步进电机、打印床。不复刻任何产品，没有标志。

    import machine
    m = machine.Machine()                    # 先调 studio.setup()。可选参数：travel（X 行程，默认 256）、bed、y_rails、sock（硅胶套）、bed_size
    m.pose(x=40, y=0, z=0.2)                 # 喷嘴在打印坐标里的位置（床中心为原点，床面 z=0）
    m.pose(x=40, motor_x=40.15)              # 电机已经走到 40.15，喷头还在 40：皮带按差值拉长（做皮带拉长的镜头）
    cube_obj.parent = m.bed                  # 方块放到床上，跟着床走

坐标：X 向右，Y 向后，Z 向上，单位 mm。喷嘴尖在 (x, y, z)。z_mode='bed'（默认）床往下沉，'gantry' 横梁往上抬；
y_mode='gantry'（默认）横梁带喷头走 Y，'bed' 床带打印件走 Y。

主要物体：m.gantry（横梁组）、m.carriage（滑块和喷头）、m.bed（床）、m.belt（皮带）、m.pulley_motor、m.pulley_idler。
都是普通物体，可以再加偏移（比如喷头被敲得抖动：m.pose(...) 之后 m.carriage.location.z += ...）。
单独要零件时直接调用：machine.nozzle(parent)、machine.hotend(parent)、machine.stepper(parent)、machine.pulley(name, parent)。

运动相关的常量：m.x_min、m.x_max（滑块顶到端板时的喷嘴 x）、machine.RP（皮带轮节圆半径）、machine.PITCH（齿距）、m.belt.strain_front（电机到夹子这段皮带的应变）。
没有做的：机架、立柱、Z 丝杆、床的支撑结构。需要时另外加。
"""
import math

import numpy as np
import bpy
from mathutils import Matrix

import studio

PITCH = 2.0                 # GT2 齿距
N_TEETH = 20
RP = N_TEETH * PITCH / (2 * math.pi)   # 节圆半径 6.366
PLD = 0.254                 # 节线到齿根面的距离
TOOTH_H = 0.75              # 齿高
BELT_BACK = 0.376           # 节线到带背的距离
BELT_W = 6.0


# ---------- 网格工具 ----------
def _link(ob, parent=None):
    bpy.context.scene.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def weighted_normals(me, V, faces_flat, counts):
    """按面积加权的顶点法向：大平面保持平，小倒角负责过渡。比默认的平滑干净得多。"""
    n = np.zeros((len(V), 3), np.float64)
    # 按边数分组处理，速度快
    counts = np.asarray(counts)
    faces_flat = np.asarray(faces_flat)
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
    for c in np.unique(counts):
        idx = np.nonzero(counts == c)[0]
        loop = starts[idx][:, None] + np.arange(c)[None, :]
        f = faces_flat[loop]
        p = V[f]
        # Newell 法向，长度就是两倍面积
        q = np.roll(p, -1, axis=1)
        fn = np.cross(p, q).sum(axis=1)
        for j in range(c):
            np.add.at(n, f[:, j], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = n / np.maximum(ln, 1e-12)
    me.normals_split_custom_set_from_vertices(n.astype(np.float32).tolist())


def make_mesh(name, V, faces, mat=None, parent=None, loc=None, smooth=True, attrs=None):
    """V: (N,3)；faces: 四边形 (M,4) 数组或任意边数的列表。"""
    V = np.asarray(V, np.float32)
    if isinstance(faces, np.ndarray):
        counts = np.full(len(faces), faces.shape[1], np.int32)
        flat = faces.ravel().astype(np.int32)
    else:
        counts = np.array([len(f) for f in faces], np.int32)
        flat = np.array([i for f in faces for i in f], np.int32)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V))
    me.vertices.foreach_set('co', V.ravel())
    me.loops.add(len(flat))
    me.loops.foreach_set('vertex_index', flat)
    me.polygons.add(len(counts))
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]]).astype(np.int32)
    me.polygons.foreach_set('loop_start', starts)
    me.update(calc_edges=True)
    if smooth:
        me.shade_smooth()
        weighted_normals(me, V.astype(np.float64), flat, counts)
    if attrs:
        for k, arr in attrs.items():
            a = me.attributes.new(k, 'FLOAT', 'POINT')
            a.data.foreach_set('value', np.asarray(arr, np.float32))
    if mat is not None:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    _link(ob, parent)
    if loc is not None:
        ob.location = loc
    return ob


def rounded(points, radius=0.3, n=3, closed=False):
    """折线的拐角倒圆。radius 可以是数或列表（逐点）。"""
    pts = [np.array(p, float) for p in points]
    m = len(pts)
    out = []
    for i in range(m):
        if not closed and (i == 0 or i == m - 1):
            out.append(tuple(pts[i]))
            continue
        a, b, c = pts[(i - 1) % m], pts[i], pts[(i + 1) % m]
        r = radius[i] if isinstance(radius, (list, tuple)) else radius
        u = a - b
        v = c - b
        lu, lv = np.linalg.norm(u), np.linalg.norm(v)
        if r <= 0 or lu < 1e-9 or lv < 1e-9:
            out.append(tuple(b))
            continue
        u, v = u / lu, v / lv
        cosang = float(np.clip(np.dot(u, v), -1, 1))
        ang = math.acos(cosang)
        if ang > math.pi - 1e-3:
            out.append(tuple(b))
            continue
        d = r / math.tan(ang / 2)
        d = min(d, lu * 0.49, lv * 0.49)
        r2 = d * math.tan(ang / 2)
        center = b + (u + v) / np.linalg.norm(u + v) * (r2 / math.sin(ang / 2))
        p0 = b + u * d
        p1 = b + v * d
        a0 = math.atan2(*(p0 - center)[::-1])
        a1 = math.atan2(*(p1 - center)[::-1])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for t in np.linspace(0, 1, n + 1):
            ai = a0 + da * t
            out.append((center[0] + r2 * math.cos(ai), center[1] + r2 * math.sin(ai)))
    return out


def revolve(name, rows, seg=64, mat=None, parent=None, loc=None, close_bottom=True, close_top=True, attrs_fn=None):
    """旋成体，轴是 Z。rows 是从下到上的 (r, z)，r 可以是函数 r(theta)（做六角面）。

    rows 里放 None 表示这里断开一条折痕（上下两段各自平滑）。
    """
    th = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    strips = []
    cur = []
    for r in rows:
        if r is None:
            strips.append(cur)
            cur = []
        else:
            cur.append(r)
    strips.append(cur)
    V = []
    F = []
    nv = 0
    for si, st in enumerate(strips):
        n = len(st)
        for r, z in st:
            rr = r(th) if callable(r) else np.full(seg, float(r))
            V.append(np.column_stack([rr * np.cos(th), rr * np.sin(th), np.full(seg, float(z))]))
        for i in range(n - 1):
            for j in range(seg):
                a = nv + i * seg + j
                b = nv + i * seg + (j + 1) % seg
                c = nv + (i + 1) * seg + (j + 1) % seg
                d = nv + (i + 1) * seg + j
                F.append((a, b, c, d))
        if si == 0 and close_bottom:
            F.append(tuple(nv + (seg - 1 - j) for j in range(seg)))
        if si == len(strips) - 1 and close_top:
            F.append(tuple(nv + (n - 1) * seg + j for j in range(seg)))
        nv += n * seg
    return make_mesh(name, np.concatenate(V), F, mat, parent, loc)


def _offset_poly(P, d):
    """多边形（逆时针）向内缩 d。"""
    prev = np.roll(P, 1, axis=0)
    nxt = np.roll(P, -1, axis=0)
    a = P - prev
    b = nxt - P
    a = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-9)
    b = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-9)
    na = np.column_stack([-a[:, 1], a[:, 0]])
    nb = np.column_stack([-b[:, 1], b[:, 0]])
    m = na + nb
    m = m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)
    k = 1.0 / np.maximum((m * na).sum(axis=1), 0.35)
    return P + m * (d * k)[:, None]


def extrude(name, poly, length, bevel=0.3, bevel_seg=3, mat=None, parent=None, mode='z', loc=None):
    """多边形拉伸，两端带倒角。poly 逆时针，在局部 XY 平面，沿 +Z 拉 length。

    mode 把局部轴换到世界：'z' 不变；'x'：拉伸沿 +X，poly 的 (u,v) → (y,z)；'y'：拉伸沿 +Y，poly 的 (u,v) → (z,x)。
    """
    P = np.array(poly, float)
    area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    if area < 0:
        P = P[::-1]
    n = len(P)
    rows = []
    if bevel > 0:
        ang = np.linspace(0, math.pi / 2, bevel_seg + 1)
        for a in ang:
            rows.append((_offset_poly(P, bevel * (1 - math.sin(a))), bevel * (1 - math.cos(a))))
        for a in ang[::-1]:
            rows.append((_offset_poly(P, bevel * (1 - math.sin(a))), length - bevel * (1 - math.cos(a))))
    else:
        rows = [(P, 0.0), (P, length)]
    V = []
    for q, z in rows:
        V.append(np.column_stack([q, np.full(n, z)]))
    V = np.concatenate(V)
    F = []
    m = len(rows)
    F.append(tuple(n - 1 - j for j in range(n)))
    for i in range(m - 1):
        for j in range(n):
            jn = (j + 1) % n
            F.append((i * n + j, i * n + jn, (i + 1) * n + jn, (i + 1) * n + j))
    F.append(tuple((m - 1) * n + j for j in range(n)))
    if mode == 'x':
        V = V[:, [2, 0, 1]]
    elif mode == 'y':
        V = V[:, [1, 2, 0]]
    return make_mesh(name, V, F, mat, parent, loc)


def rect(w, h, r=0.0, n=3, cx=0.0, cy=0.0):
    """矩形多边形（中心在 cx,cy），r 是圆角。"""
    p = [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]
    return rounded(p, r, n, closed=True) if r > 0 else p


def box(name, x0, x1, y0, y1, z0, z1, bevel=0.3, r=0.0, mat=None, parent=None):
    """轴对齐的盒子，边带倒角；r 是竖直四角的圆角。"""
    poly = rect(x1 - x0, y1 - y0, r, 4)
    ob = extrude(name, poly, z1 - z0, bevel=bevel, mat=mat, parent=parent)
    ob.location = ((x0 + x1) / 2, (y0 + y1) / 2, z0)
    return ob


def tube(name, pts, radius, seg=10, mat=None, parent=None, sub=12):
    """沿 Catmull-Rom 曲线的圆管，做线缆用。"""
    P = np.array(pts, float)
    Q = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    C = []
    for i in range(1, len(Q) - 2):
        for t in np.linspace(0, 1, sub, endpoint=False):
            a, b, c, d = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
            C.append(0.5 * ((2 * b) + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (3 * b - a - 3 * c + d) * t ** 3))
    C.append(P[-1])
    C = np.array(C)
    T = np.gradient(C, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    up = np.array([0.0, 0.0, 1.0])
    V = []
    u = np.cross(T[0], up)
    if np.linalg.norm(u) < 1e-3:
        u = np.cross(T[0], (1, 0, 0))
    u /= np.linalg.norm(u)
    th = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    for i in range(len(C)):
        u = u - T[i] * np.dot(u, T[i])
        u /= max(np.linalg.norm(u), 1e-9)
        w = np.cross(T[i], u)
        V.append(C[i] + radius * (np.outer(np.cos(th), u) + np.outer(np.sin(th), w)))
    V = np.concatenate(V)
    F = []
    n = len(C)
    for i in range(n - 1):
        for j in range(seg):
            jn = (j + 1) % seg
            F.append((i * seg + j, i * seg + jn, (i + 1) * seg + jn, (i + 1) * seg + j))
    F.append(tuple(seg - 1 - j for j in range(seg)))
    F.append(tuple((n - 1) * seg + j for j in range(seg)))
    return make_mesh(name, V, F, mat, parent)


def hex_r(af, rot=0.0):
    """对边宽 af 的正六边形，极坐标下的半径函数。"""
    a = af / 2

    def fn(th):
        t = (th - rot) % (math.pi / 3) - math.pi / 6
        return a / np.cos(t)
    return fn


def clip_hex(r, hexfn):
    """半径 r 和六角取小：真实的六角件就是这样车出来的，倒角处自然有弧线。"""
    return lambda th: np.minimum(np.full_like(th, r), hexfn(th))


# ---------- 零件 ----------
def nozzle(parent=None, name='喷嘴', mat=None):
    """黄铜喷嘴。尖端在局部 z=0，轴向上：尖端平面 φ1.1，中间是 φ0.4 的孔；一小段圆柱；半角约 40° 的短圆锥；对边 7 的六角。"""
    mat = mat or studio.brass()
    h = hex_r(7.0)
    rows = []
    # 孔内
    rows += [(0.01, 1.3), (0.2, 1.3), None, (0.2, 1.3), (0.2, 0.03)]
    # 孔口小倒角、尖端平面、外缘小圆角
    rows += [(0.225, 0.0), (0.50, 0.0), (0.54, 0.012), (0.56, 0.05)]
    rows.append(None)
    # 尖端的小圆柱，然后是短圆锥
    cone = [(0.56, 0.05), (0.56, 0.30), (0.62, 0.38), (3.2, 3.45), (3.36, 3.62), (3.55, 3.85)]
    zs = np.linspace(0, 1, 14)
    for i in range(len(cone) - 1):
        for t in zs[:-1]:
            rows.append((cone[i][0] + (cone[i + 1][0] - cone[i][0]) * t, cone[i][1] + (cone[i + 1][1] - cone[i][1]) * t))
    rows.append(cone[-1])
    # 六角：两端车 30° 倒角，棱上自然出现弧线
    corner = 7.0 / 2 / math.cos(math.pi / 6)
    z0, z1 = cone[-1][1], 6.9
    chamfer = corner - 3.5 + 0.08
    for t in np.linspace(0, 1, 28)[1:]:
        rows.append((clip_hex(cone[-1][0] + (corner + 0.02 - cone[-1][0]) * t, h), z0 + chamfer * 0.6 * t))
    for z in np.linspace(z0 + chamfer * 0.6, z1 - chamfer * 0.6, 6)[1:-1]:
        rows.append((clip_hex(corner + 0.02, h), z))
    for t in np.linspace(1, 0, 28):
        rows.append((clip_hex(3.55 + (corner + 0.02 - 3.55) * t, h), z1 - chamfer * 0.6 * t))
    rows.append(None)
    # 上面的螺纹段（大部分藏在加热块里）
    rows += [(3.0, z1), (3.0, 11.8)]
    return revolve(name, rows, seg=384, mat=mat, parent=parent, close_bottom=True, close_top=True)


def socket_screw(name, parent, d=3.0, loc=(0, 0, 0), rot=None, mat=None, length=0.0):
    """内六角圆柱头螺钉，头朝局部 +Z。loc 是头底面中心。"""
    mat = mat or studio.black_oxide()
    rh = d * 0.84
    hh = d
    sock = hex_r(d * 0.83)
    rows = []
    if length > 0:
        rows += [(d / 2, -length), (d / 2, 0), None]
    rows += rounded([(rh, 0.0), (rh, hh), (sock(np.array([0.0]))[0], hh)], [0, 0.18, 0], 3)[:-1]
    rows += [(sock, hh), (sock, hh - d * 0.55), (0.01, hh - d * 0.62)]
    ob = revolve(name, rows, seg=36, mat=mat, parent=parent, loc=loc)
    if rot is not None:
        ob.rotation_mode = 'XYZ'
        ob.rotation_euler = rot
    return ob


def belt_tooth(phase):
    """齿形：phase 是相对最近齿中心的位置（单位：齿距，-0.5..0.5）。返回 0（齿根）到 1（齿顶）。"""
    x = np.abs(phase)
    a, b = 0.17, 0.34        # 齿顶半宽、齿根半宽
    t = np.clip((b - x) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def pulley(name, parent=None, mat=None, hub=True):
    """GT2 20 齿皮带轮。轴是局部 Z，齿段中心在 z=0。grooves 在 phi=k*18° 处。"""
    mat = mat or studio.aluminium_turned()
    tw = BELT_W + 1.0
    fl = 1.0
    r_flange = 8.0
    r_od = RP - PLD
    z0, z1 = -tw / 2, tw / 2

    def tooth_r(depth):
        def fn(th):
            phase = th / (2 * math.pi / N_TEETH)
            phase = phase - np.round(phase)
            return r_od - depth * belt_tooth(phase * 0.96)
        return fn
    seg = 24 * N_TEETH
    # 齿段
    rows = []
    rows.append((tooth_r(TOOTH_H + 0.01), z0))
    rows.append((tooth_r(TOOTH_H + 0.01), z1))
    teeth = revolve(name + '_齿', rows, seg=seg, mat=mat, parent=parent, close_bottom=False, close_top=False)
    # 两边的挡边和轮毂
    prof = []
    if hub:
        prof += [(2.5, z0 - fl - 8.0), (r_flange, z0 - fl - 8.0), (r_flange, z0 - fl - 1.5), (r_flange - 1.0, z0 - fl - 1.0), (r_flange, z0 - fl - 0.5)]
        rad = [0, 0.25, 0.1, 0.1, 0]
    else:
        prof += [(2.5, z0 - fl), (r_flange, z0 - fl)]
        rad = [0, 0.2]
    prof += [(r_flange, z0), (r_od - 0.2, z0)]
    rad += [0.15, 0]
    b = rounded(prof, rad, 3)
    body0 = revolve(name + '_轮毂', b, seg=96, mat=mat, parent=teeth, close_bottom=False, close_top=False)
    t = rounded([(r_od - 0.2, z1), (r_flange, z1), (r_flange, z1 + fl), (2.5, z1 + fl)], [0, 0.15, 0.2, 0], 3)
    body1 = revolve(name + '_挡边', t, seg=96, mat=mat, parent=teeth, close_bottom=False, close_top=False)
    if hub:
        # 轮毂上的顶丝
        for ang in (0.0, math.pi / 2):
            s = socket_screw(name + '_顶丝', teeth, d=2.6, mat=studio.black_oxide())
            s.scale = (1, 1, 0.5)
            zh = z0 - fl - 4.8
            s.rotation_mode = 'XYZ'
            s.rotation_euler = (0, math.pi / 2, ang)
            s.location = (7.3 * math.cos(ang), 7.3 * math.sin(ang), zh)
    return teeth


def stepper(parent=None, name='步进电机', length=34.0):
    """NEMA17 尺寸的步进电机。局部原点在前端面中心，轴朝局部 +Z，机身向 -Z。没有标签和标志。"""
    a = 42.3
    cap = studio.aluminium(name='电机端盖', rough=0.46, base=(0.30, 0.30, 0.31))
    stack_mat = studio.lamination()
    chamfer = 3.2

    def outline(w, c, r=0.5):
        p = [(-w / 2 + c, -w / 2), (w / 2 - c, -w / 2), (w / 2, -w / 2 + c), (w / 2, w / 2 - c),
             (w / 2 - c, w / 2), (-w / 2 + c, w / 2), (-w / 2, w / 2 - c), (-w / 2, -w / 2 + c)]
        return rounded(p, r, 3, closed=True)
    hc = 7.8            # 前后端盖厚
    front = extrude(name + '_前盖', outline(a, 2.2, 0.6), hc, bevel=0.5, mat=cap, parent=parent)
    front.location = (0, 0, -hc)
    stack_len = length - 2 * hc
    stack = extrude(name + '_铁芯', outline(a - 0.15, chamfer + 1.0, 0.3), stack_len, bevel=0.08, bevel_seg=1, mat=stack_mat, parent=parent)
    stack.location = (0, 0, -hc - stack_len)
    rear = extrude(name + '_后盖', outline(a, 2.2, 0.6), hc, bevel=0.5, mat=cap, parent=parent)
    rear.location = (0, 0, -length)
    # 前端凸台和轴
    boss = rounded([(0.1, 0.0), (11.0, 0.0), (11.0, 2.0), (2.8, 2.0)], [0, 0.0, 0.25, 0], 3)
    revolve(name + '_凸台', boss, seg=96, mat=studio.aluminium(name='电机凸台'), parent=parent, close_bottom=False)
    shaft_rows = rounded([(2.5, -1.0), (2.5, 15.2), (0.01, 15.2)], [0, 0.25, 0], 3)
    revolve(name + '_轴', shaft_rows, seg=48, mat=studio.steel(name='电机轴'), parent=parent)
    # 四角螺孔
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * 15.5, sy * 15.5
            rows = [(0.01, -2.5), (1.5, -2.5), (1.5, 0.02), (1.7, 0.02)]
            revolve(name + '_孔', rows, seg=24, mat=studio.black_oxide(), parent=parent, loc=(x, y, -0.0), close_bottom=False, close_top=True)
            # 后盖长螺钉头
            sc = socket_screw(name + '_后螺钉', parent, d=3.0, mat=studio.black_oxide())
            sc.location = (x, y, -length)
            sc.rotation_mode = 'XYZ'
            sc.rotation_euler = (math.pi, 0, 0)
    # 顶面一张标签：只有成行的灰块，读不出字，也没有任何标志
    box(name + '_标签', -15.5, 15.5, 21.12, 21.3, -29.5, -6.5, bevel=0.03, mat=studio.label(), parent=parent)
    # 后盖接插件，白色塑料，不带任何字
    plug = box(name + '_插座', -8, 8, -21.4, -15.5, -length - 0.0, -length + 6.0, bevel=0.3, mat=studio.nylon_white(), parent=parent)
    return stack


def hotend(parent, name='喷头', sock=True):
    """局部原点是喷嘴尖，向上依次是喷嘴、加热块（默认包硅胶套）、喉管、散热器、卡槽。"""
    objs = {}
    objs['nozzle'] = nozzle(parent, name + '_喷嘴')
    # 加热块：喷嘴在块的右侧，加热棒在左侧。喷嘴六角和块之间留 1 mm（热紧后的真实间隙）
    z_b0, z_b1 = 7.9, 19.4
    alu = studio.aluminium(name='加热块', rough=0.52)
    block = box(name + '_加热块', -16.5, 6.5, -5.5, 5.5, z_b0, z_b1, bevel=0.35, mat=alu, parent=parent)
    objs['block'] = block
    # 加热棒（沿 Y）
    heater = studio.steel(name='加热棒', rough=0.32)
    rows = rounded([(0.01, 0), (3.0, 0), (3.0, 13.0 if sock else 16.0), (0.01, 13.0 if sock else 16.0)], [0, 0.3, 0.3, 0], 3)
    hc = revolve(name + '_加热棒', rows, seg=48, mat=heater, parent=parent)
    hc.rotation_mode = 'XYZ'
    hc.rotation_euler = (math.pi / 2, 0, 0)
    hc.location = (-10.5, 8.0, 13.6)
    if sock:
        # 硅胶套：把加热块包起来，只露出喷嘴
        sk = extrude(name + '_硅胶套', rect(25.0, 13.2, 2.4, 5), 13.2, bevel=1.1, bevel_seg=4, mat=studio.silicone(), parent=parent)
        sk.location = (-5.0, 0.0, z_b0 - 0.8)
    # 喉管（细钢管）和散热器
    rows = [(1.45, z_b1 - 0.5), (1.45, z_b1 + 3.2)]
    revolve(name + '_喉管', rows, seg=32, mat=studio.steel(name='喉管', rough=0.28), parent=parent, close_bottom=False, close_top=False)
    rows = rounded([(0.5, z_b1 + 2.4), (3.4, z_b1 + 2.4), (3.4, z_b1 + 4.0)], [0, 0.2, 0], 2)
    revolve(name + '_喉管台肩', rows, seg=32, mat=studio.steel(name='喉管台肩', rough=0.28), parent=parent, close_top=False)
    # 散热片
    z = z_b1 + 3.5
    fin_mat = studio.aluminium(name='散热片', rough=0.34)
    core = 6.6
    fin_r = 11.0
    fins = 11
    pitch = 2.45
    t_fin = 1.05
    cur = z
    pts = [(3.0, cur)]
    for i in range(fins):
        pts += [(fin_r, cur), (fin_r, cur + t_fin)]
        cur += t_fin
        if i < fins - 1:
            pts += [(core, cur), (core, cur + pitch - t_fin)]
            cur += pitch - t_fin
    # 上段的圆柱和卡槽
    z_top = cur
    pts += [(8.0, z_top), (8.0, z_top + 3.7), (6.0, z_top + 3.7), (6.0, z_top + 9.3), (8.0, z_top + 9.3), (8.0, z_top + 12.7), (2.0, z_top + 12.7)]
    prof = rounded(pts, 0.22, 2)
    objs['sink'] = revolve(name + '_散热器', prof, seg=96, mat=fin_mat, parent=parent, close_bottom=True, close_top=True)
    objs['z_top'] = z_top + 12.7
    # 线缆：加热棒和测温的线都从块的背面出来，沿散热器后面上去，从正面看不到
    wire = studio.wire(name='线缆')
    for i, dz in enumerate((1.0, -1.0)):
        tube(name + f'_加热线{i}', [(-10.5, 8.5, 13.6 + dz * 0.9), (-11.5, 13, 14.3 + dz), (-14 + dz, 20, 26), (-13 + dz, 23.5, 44), (-13 + dz, 24, 60)],
             0.55, 8, wire, parent)
    wire2 = studio.wire(name='测温线', color=(0.75, 0.75, 0.72))
    for i, dz in enumerate((1.0, -1.0)):
        tube(name + f'_测温线{i}', [(-2.0 + dz * 0.5, 6.0, 11.3), (-2.5 + dz * 0.5, 12, 13.3), (-7 + dz * 0.5, 19, 25), (-9 + dz * 0.5, 23.5, 44), (-9 + dz * 0.5, 24, 60)],
             0.28, 6, wire2, parent)
    return objs


class Belt:
    """闭合的齿形带，绕在电机轮和惰轮上。update 时按电机和滑块的位置重算每个齿的位置，顶点数不变。

    弧长 s：从电机轮顶部切点出发，沿上边向 +X，绕惰轮，沿下边回来，绕电机轮回到起点。
    材料坐标 q：皮带本身的刻度，齿中心在 q = k × 齿距。不拉长时 q = s - x。
    """

    def __init__(self, parent, x_m, x_i, z0, y0, mat=None, samples_per_tooth=16, name='皮带'):
        self.x_m, self.x_i, self.z0, self.y0 = x_m, x_i, z0, y0
        self.Lstr = x_i - x_m
        self.L = 2 * self.Lstr + 2 * math.pi * RP
        self.shake = (0.0, 0.0)     # 上、下两段皮带中点的横向抖动（mm，竖直方向），update 时生效
        self.n_teeth = int(round(self.L / PITCH))
        if abs(self.n_teeth * PITCH - self.L) > 1e-6:
            raise ValueError('两轮间距必须是整数毫米，皮带才是整数个齿')
        self.ns = samples_per_tooth * self.n_teeth
        self.q = np.arange(self.ns) * PITCH / samples_per_tooth
        phase = self.q / PITCH - np.round(self.q / PITCH)
        self.h_in = -PLD - TOOTH_H * belt_tooth(phase)
        self.h_out = np.full(self.ns, BELT_BACK)
        # 每个 q 处四个面的顶点各两份（齿面、带背、两个侧面分别平滑）
        ns = self.ns
        idx = lambda part, i, side: part * 2 * ns + (i % ns) * 2 + side
        F = []
        for i in range(ns):
            # 带背（外面）：法向朝外
            F.append((idx(0, i, 0), idx(0, i + 1, 0), idx(0, i + 1, 1), idx(0, i, 1)))
            # 齿面（里面）
            F.append((idx(1, i, 1), idx(1, i + 1, 1), idx(1, i + 1, 0), idx(1, i, 0)))
            # y- 侧面（side 0 是外缘，1 是内缘）
            F.append((idx(2, i, 1), idx(2, i + 1, 1), idx(2, i + 1, 0), idx(2, i, 0)))
            # y+ 侧面
            F.append((idx(3, i, 0), idx(3, i + 1, 0), idx(3, i + 1, 1), idx(3, i, 1)))
        self.F = np.array(F, np.int32)
        self.nv = 4 * 2 * ns
        self.mat = mat or studio.rubber()
        V = self._verts(0.0, 0.0)
        ob = make_mesh(name, V, self.F, self.mat, parent, smooth=True)
        self.obj = ob
        # 属性：0 带背，1 齿面，2 侧面；UV：u 沿带长，v 横向
        part = np.concatenate([np.zeros(2 * ns), np.ones(2 * ns), np.full(4 * ns, 2.0)])
        a = ob.data.attributes.new('belt_part', 'FLOAT', 'POINT')
        a.data.foreach_set('value', part.astype(np.float32))
        uv = ob.data.uv_layers.new(name='UV')
        u = np.tile(np.repeat(self.q, 2), 4).astype(np.float32)
        # v：带背、齿面用横向位置；侧面用厚度方向位置
        hgt = np.empty(2 * ns, np.float32)
        hgt[0::2] = self.h_out
        hgt[1::2] = self.h_in
        vv = np.concatenate([np.tile([0.0, BELT_W], ns), np.tile([0.0, BELT_W], ns), hgt, hgt]).astype(np.float32)
        per_v = np.column_stack([u, vv])
        uv.uv.foreach_set('vector', per_v[self.F.ravel()].ravel())
        self.update(0.0, 0.0)

    def _world(self, s, h):
        """弧长 s、离节线 h（向外为正）→ (x, z)。"""
        Lstr, x_m, x_i, z0 = self.Lstr, self.x_m, self.x_i, self.z0
        s = np.mod(s, self.L)
        x = np.empty_like(s)
        z = np.empty_like(s)
        arc = math.pi * RP
        m1 = s < Lstr
        m2 = (s >= Lstr) & (s < Lstr + arc)
        m3 = (s >= Lstr + arc) & (s < 2 * Lstr + arc)
        m4 = s >= 2 * Lstr + arc
        x[m1] = x_m + s[m1]
        z[m1] = z0 + RP + h[m1]
        a = (s[m2] - Lstr) / RP
        x[m2] = x_i + (RP + h[m2]) * np.sin(a)
        z[m2] = z0 + (RP + h[m2]) * np.cos(a)
        x[m3] = x_i - (s[m3] - Lstr - arc)
        z[m3] = z0 - RP - h[m3]
        a = (s[m4] - (2 * Lstr + arc)) / RP
        x[m4] = x_m - (RP + h[m4]) * np.sin(a)
        z[m4] = z0 - (RP + h[m4]) * np.cos(a)
        return x, z

    def _map(self, carriage_x, motor_x):
        """q → s。皮带在夹子处被滑块固定，在电机轮切点处由电机决定，两段各自均匀拉伸。"""
        L = self.L
        s_c = carriage_x - self.x_m
        q_a = -motor_x
        q_c = s_c - carriage_x
        span = q_c - q_a                 # 电机切点到夹子这段皮带的材料长度
        rel = np.mod(self.q - q_a, L)
        s = np.where(rel < span, rel * s_c / span, s_c + (rel - span) * (L - s_c) / (L - span))
        self.q_motor = q_a
        # 惰轮切点 s=Lstr 处的材料坐标
        self.q_idler = q_c + (self.Lstr - s_c) * (L - span) / (L - s_c)
        self.strain_front = s_c / span - 1.0
        return s

    def _verts(self, carriage_x, motor_x):
        s = self._map(carriage_x, motor_x)
        xo, zo = self._world(s, self.h_out)
        xi, zi = self._world(s, self.h_in)
        if self.shake[0] or self.shake[1]:
            sm = np.mod(s, self.L)
            sc = carriage_x - self.x_m
            arc = math.pi * RP
            dz = np.zeros_like(sm)
            top_a = sm < sc                                     # 电机到皮带夹
            top_b = (sm >= sc) & (sm < self.Lstr)               # 皮带夹到惰轮
            low = (sm >= self.Lstr + arc) & (sm < 2 * self.Lstr + arc)
            dz[top_a] = self.shake[0] * np.sin(math.pi * sm[top_a] / max(sc, 1.0))
            dz[top_b] = -self.shake[0] * 0.6 * np.sin(math.pi * (sm[top_b] - sc) / max(self.Lstr - sc, 1.0))
            dz[low] = self.shake[1] * np.sin(math.pi * (sm[low] - self.Lstr - arc) / self.Lstr)
            zo = zo + dz
            zi = zi + dz
        y0, y1 = self.y0 - BELT_W / 2, self.y0 + BELT_W / 2
        ns = self.ns
        V = np.empty((self.nv, 3), np.float32)
        P = np.empty((2 * ns, 3), np.float32)
        P[0::2] = np.column_stack([xo, np.full(ns, y0), zo])
        P[1::2] = np.column_stack([xo, np.full(ns, y1), zo])
        V[0:2 * ns] = P
        P = np.empty((2 * ns, 3), np.float32)
        P[0::2] = np.column_stack([xi, np.full(ns, y0), zi])
        P[1::2] = np.column_stack([xi, np.full(ns, y1), zi])
        V[2 * ns:4 * ns] = P
        P = np.empty((2 * ns, 3), np.float32)
        P[0::2] = np.column_stack([xo, np.full(ns, y0), zo])
        P[1::2] = np.column_stack([xi, np.full(ns, y0), zi])
        V[4 * ns:6 * ns] = P
        P = np.empty((2 * ns, 3), np.float32)
        P[0::2] = np.column_stack([xo, np.full(ns, y1), zo])
        P[1::2] = np.column_stack([xi, np.full(ns, y1), zi])
        V[6 * ns:8 * ns] = P
        return V

    def update(self, carriage_x, motor_x):
        V = self._verts(carriage_x, motor_x)
        me = self.obj.data
        me.vertices.foreach_set('co', V.ravel())
        counts = np.full(len(self.F), 4)
        weighted_normals(me, V.astype(np.float64), self.F.ravel(), counts)
        me.update()


class Machine:
    """见文件头。"""

    def __init__(self, travel=256.0, bed=True, y_rails=True, z_mode='bed', y_mode='gantry', sock=True, bed_size=236.0):
        self.z_mode, self.y_mode = z_mode, y_mode
        self.sock = sock
        self.bed_size = bed_size
        self.root = bpy.data.objects.new('机器', None)
        _link(self.root)
        self.gantry = bpy.data.objects.new('横梁组', None)
        _link(self.gantry, self.root)
        self.carriage = bpy.data.objects.new('滑块', None)
        _link(self.carriage, self.gantry)
        self.bed = bpy.data.objects.new('床', None)
        _link(self.bed, self.root)
        L = travel + 84.0        # 两块端板外侧之间的长度
        L = float(int(L / 2) * 2)
        self.L = L
        # 滑块恰好顶到两端端板时的喷嘴 x（轴承外端离中心 29.5 mm），做“抵住”就走到这里
        self.x_min = -L / 2 + 10 + 29.5
        self.x_max = L / 2 - 10 - 29.5
        self.rod_z = (62.0, 106.0)
        self.belt_z = 84.0
        self.rod_y = 32.0
        self.motor_x = -L / 2 - 32.0      # 电机在左端板外侧，正面、顶面、左侧都不挡
        self.idler_x = L / 2 - 30.0
        self._build_gantry(L, y_rails)
        self._build_carriage()
        if bed:
            self._build_bed()
        self.pose(0.0, 0.0, 0.0)

    # ----- 横梁组 -----
    def _build_gantry(self, L, y_rails):
        g = self.gantry
        rod_mat = studio.steel(name='光杆', rough=0.13)
        for i, z in enumerate(self.rod_z):
            rows = rounded([(0.01, 0), (4.0, 0), (4.0, L - 12.0), (0.01, L - 12.0)], [0, 0.3, 0.3, 0], 3)
            r = revolve(f'光杆{i}', rows, seg=64, mat=rod_mat, parent=g)
            r.rotation_mode = 'XYZ'
            r.rotation_euler = (0, math.pi / 2, 0)
            r.location = (-L / 2 + 6.0, self.rod_y, z)
        # 横梁：20×40 铝型材（y 方向 20，z 方向 40）
        beam_mat = studio.aluminium(name='铝型材', rough=0.56, base=(0.56, 0.56, 0.57))
        bx0, bx1 = -L / 2 + 10.0, L / 2 - 10.0
        beam = extrude('横梁', tslot_profile(20.0, 40.0), bx1 - bx0, bevel=0.25, bevel_seg=2, mat=beam_mat, parent=g, mode='x')
        beam.location = (bx0, 53.0, self.belt_z)
        self.beam = beam
        # 两端的端板
        plate_mat = studio.aluminium(name='端板', rough=0.52)
        black = studio.black_anodized()
        for sx in (-1, 1):
            x0, x1 = (-L / 2, -L / 2 + 10) if sx < 0 else (L / 2 - 10, L / 2)
            if sx < 0:
                # 左端板是一个朝前开口的 C 形，皮带从开口穿出去，绕到电机轮上
                box('端板上', x0, x1, 18.0, 66.0, self.belt_z + 12.0, 118.0, bevel=0.6, r=3.0, mat=black, parent=g)
                box('端板下', x0, x1, 18.0, 66.0, 50.0, self.belt_z - 12.0, bevel=0.6, r=3.0, mat=black, parent=g)
                box('端板背', x0, x1, 40.0, 66.0, self.belt_z - 13.0, self.belt_z + 13.0, bevel=0.3, mat=black, parent=g)
            else:
                box('端板右', x0, x1, 18.0, 66.0, 50.0, 118.0, bevel=0.6, r=3.0, mat=black, parent=g)
            # 压住光杆的螺钉
            for z in self.rod_z:
                for dy in (-9, 9):
                    s = socket_screw('端板螺钉', g, d=3.0)
                    s.rotation_mode = 'XYZ'
                    s.rotation_euler = (0, sx * math.pi / 2, 0)
                    s.location = (x1 if sx > 0 else x0, self.rod_y + dy, z)
        # 两条支臂把电机吊在左端板外面，电机轮和机身都露在外面
        for sz in (-1, 1):
            zc = self.belt_z + sz * 15.5
            box('电机支臂', self.motor_x + 6.0, -L / 2 + 0.2, 40.0, 43.0, zc - 4.0, zc + 4.0, bevel=0.3, r=1.0, mat=black, parent=g)
        motor_holder = bpy.data.objects.new('电机', None)
        _link(motor_holder, g)
        motor_holder.location = (self.motor_x, 43.0, self.belt_z)
        motor_holder.rotation_mode = 'XYZ'
        motor_holder.rotation_euler = (math.pi / 2, 0, 0)     # 局部 +Z → 世界 -Y（轴朝前）
        self.motor = stepper(motor_holder)
        for sx in (-1, 1):
            for sz in (-1, 1):
                s = socket_screw('电机螺钉', g, d=3.0)
                s.scale = (1, 1, 0.8)
                s.rotation_mode = 'XYZ'
                s.rotation_euler = (math.pi / 2, 0, 0)
                s.location = (self.motor_x + sx * 15.5, 40.0 if sx > 0 else 43.0, self.belt_z + sz * 15.5)
        # 电机线：一束黑色套管，从后盖的插座出来，往左下垂到画外
        mx, bz = self.motor_x, self.belt_z
        tube('电机线', [(mx, 72.0, bz - 21.2), (mx - 1, 74.0, bz - 27), (mx - 9, 71.0, bz - 40), (mx - 26, 62.0, bz - 58), (mx - 48, 46.0, bz - 92),
                     (mx - 62, 30.0, bz - 150), (mx - 70, 18.0, bz - 240)], 1.45, 10, studio.wire(name='电机线', color=(0.010, 0.010, 0.011)), g, sub=10)
        # 皮带轮：轮的局部 Z 指向世界 -Y，φ 从 +X 向 +Z 为正
        self.pulley_motor = pulley('电机轮', g, hub=True)
        self.pulley_motor.location = (self.motor_x, self.rod_y, self.belt_z)
        self.pulley_motor.rotation_mode = 'ZYX'
        self.pulley_idler = pulley('惰轮', g, hub=False)
        self.pulley_idler.location = (self.idler_x, self.rod_y, self.belt_z)
        self.pulley_idler.rotation_mode = 'ZYX'
        # 惰轮的轴、螺母和支架
        rows = rounded([(0.01, -11.0), (2.5, -11.0), (2.5, 9.0)], [0, 0.2, 0], 2)
        axle = revolve('惰轮轴', rows, seg=32, mat=studio.steel(name='惰轮轴', rough=0.25), parent=g, close_top=False)
        axle.rotation_mode = 'XYZ'
        axle.rotation_euler = (math.pi / 2, 0, 0)
        axle.location = (self.idler_x, self.rod_y, self.belt_z)
        ib = box('惰轮支架', self.idler_x - 9.0, L / 2 - 10.0, 40.0, 43.0, self.belt_z - 12.0, self.belt_z + 12.0, bevel=0.3, mat=plate_mat, parent=g)
        nut = revolve('惰轮螺母', [(2.5, 0.0), (clip_hex(4.0, hex_r(8.0)), 0.25), (clip_hex(4.7, hex_r(8.0)), 0.8), (clip_hex(4.7, hex_r(8.0)), 3.0), (clip_hex(4.0, hex_r(8.0)), 3.55), (2.5, 3.8)],
                      seg=48, mat=studio.steel(name='螺母', rough=0.3), parent=g, close_bottom=False, close_top=True)
        nut.rotation_mode = 'XYZ'
        nut.rotation_euler = (math.pi / 2, 0, 0)
        nut.location = (self.idler_x, self.rod_y - 5.6, self.belt_z)
        # 皮带
        self.belt = Belt(g, self.motor_x, self.idler_x, self.belt_z, self.rod_y)
        if y_rails:
            rail_z = 50.0 - 8.0
            for sx in (-1, 1):
                x = sx * (L / 2 + 13.0)
                rows = rounded([(0.01, 0), (4.0, 0), (4.0, L + 40.0), (0.01, L + 40.0)], [0, 0.3, 0.3, 0], 3)
                r = revolve(f'Y导轨{sx}', rows, seg=64, mat=rod_mat, parent=self.root)
                r.rotation_mode = 'XYZ'
                r.rotation_euler = (-math.pi / 2, 0, 0)
                r.location = (x, -L / 2 - 20.0, rail_z)
                # 导轨上的滑块，跟着横梁走
                box(f'Y滑块{sx}', min(x - 9.0, sx * L / 2), max(x + 9.0, sx * L / 2), 18.0, 66.0, rail_z - 9.0, rail_z + 9.0, bevel=0.5, mat=black, parent=g)

    # ----- 滑块和喷头 -----
    def _build_carriage(self):
        c = self.carriage
        anod = studio.black_anodized(name='滑块板')
        # 前板：z 从 38 到 120，x ±32
        # 铣削件：3 mm 底板，前面一圈外框和两道横筋，中间是减重槽
        # extrude(mode='y') 把 (u,v) 映射到 (z,x)，所以 rect 先写 z 向的高、再写 x 向的宽
        wx, z0, z1 = 28.0, 44.0, 118.0
        zc = (z0 + z1) / 2
        base = extrude('滑块底板', rect(z1 - z0, 2 * wx, 3.0, 4), 3.0, bevel=0.25, mat=anod, parent=c, mode='y')
        base.location = (0, 18.0, zc)
        self.plate = base
        bar = 4.0
        fy0, fy1 = 13.0, 18.2
        box('滑块框左', -wx, -wx + bar, fy0, fy1, z0, z1, bevel=0.4, r=0.8, mat=anod, parent=c)
        box('滑块框右', wx - bar, wx, fy0, fy1, z0, z1, bevel=0.4, r=0.8, mat=anod, parent=c)
        for zb, name in ((z0, '下'), (z1 - bar, '上'), (self.rod_z[0] - 2.5, '中下'), (self.rod_z[1] - 2.5, '中上')):
            th = bar if zb in (z0, z1 - bar) else 5.0
            box('滑块框' + name, -wx + bar * 0.5, wx - bar * 0.5, fy0, fy1, zb, zb + th, bevel=0.4, mat=anod, parent=c)
        # 横筋上的四颗螺钉，压住后面的轴承座
        for sx in (-1, 1):
            for z in self.rod_z:
                s = socket_screw('滑块螺钉', c, d=3.0)
                s.rotation_mode = 'XYZ'
                s.rotation_euler = (math.pi / 2, 0, 0)
                s.location = (sx * 17.0, 13.0, z)
        # 喷头：局部原点就是喷嘴尖
        self.hot = bpy.data.objects.new('喷头', None)
        _link(self.hot, c)
        self.hotend_parts = hotend(self.hot, sock=self.sock)
        z_top = self.hotend_parts['z_top']
        # 卡住散热器顶部的支架（卡槽两半），用两颗螺钉压住
        z_c0 = z_top - 12.7
        hb = box('喷头支架', -15.0, 15.0, -9.5, 13.0, z_c0 + 3.7, z_top + 2.0, bevel=0.5, r=1.5, mat=anod, parent=c)
        for sx in (-1, 1):
            s = socket_screw('支架螺钉', c, d=3.0)
            s.rotation_mode = 'XYZ'
            s.rotation_euler = (math.pi / 2, 0, 0)
            s.location = (sx * 11.0, -9.5, (z_c0 + 3.7 + z_top + 2.0) / 2)
        # 板后面：直线轴承和座
        steel = studio.steel(name='轴承壳', rough=0.22)
        seal = studio.rubber(name='轴承密封')
        bl = anod
        for z, xs in ((self.rod_z[1], (-17.0, 17.0)), (self.rod_z[0], (-17.0, 17.0))):
            for x in xs:
                rows = rounded([(4.2, -12.0), (7.5, -12.0), (7.5, 12.0), (4.2, 12.0)], [0, 0.3, 0.3, 0], 2)
                b = revolve('直线轴承', rows, seg=48, mat=steel, parent=c, close_bottom=False, close_top=False)
                b.rotation_mode = 'XYZ'
                b.rotation_euler = (0, math.pi / 2, 0)
                b.location = (x, self.rod_y, z)
                for sgn in (-1, 1):
                    rows = [(4.05, -0.4), (6.6, -0.4), (6.6, 0.0), (4.05, 0.0)]
                    sl = revolve('轴承密封', rows, seg=32, mat=seal, parent=c, close_bottom=False, close_top=False)
                    sl.rotation_mode = 'XYZ'
                    sl.rotation_euler = (0, sgn * math.pi / 2, 0)
                    sl.location = (x + sgn * 12.05, self.rod_y, z)
                bk = box('轴承座', x - 8.0, x + 8.0, 21.0, 30.0, z - 11.0, z + 11.0, bevel=0.4, mat=bl, parent=c)
        # 皮带夹：夹上边的皮带
        cl = box('皮带夹', -12.0, 12.0, 21.0, 37.0, self.belt_z + 3.8, self.belt_z + 14.0, bevel=0.4, mat=bl, parent=c)
        # 标记点（做皮带拉长时用）：滑块在皮带上的固定位置就是 x
        self.clamp_x = 0.0

    # ----- 床 -----
    def _build_bed(self):
        b = self.bed
        size = self.bed_size
        alu = studio.aluminium(name='床铝板', rough=0.54)
        plate = extrude('床板', rect(size, size, 5.0, 4), 5.0, bevel=0.6, mat=alu, parent=b)
        plate.location = (0, 0, -5.6)
        sheet = extrude('床面', rect(size, size, 5.0, 4), 0.6, bevel=0.08, bevel_seg=1, mat=studio.bed_sheet(), parent=b)
        sheet.location = (0, 0, -0.6)

    # ----- 摆位 -----
    def pose(self, x=None, y=None, z=None, motor_x=None, shake=None):
        """喷嘴移到打印坐标 (x,y,z)。不给的轴保持不动。motor_x 是电机认为的位置，默认等于 x（皮带不拉长）。shake=(上,下) 是皮带的横向抖动。"""
        if not hasattr(self, '_p'):
            self._p = dict(x=0.0, y=0.0, z=0.0)
        p = self._p
        if x is not None:
            p['x'] = float(x)
        if y is not None:
            p['y'] = float(y)
        if z is not None:
            p['z'] = float(z)
        mx = p['x'] if motor_x is None else float(motor_x)
        self.carriage.location = (p['x'], 0.0, 0.0)
        gy = p['y'] if self.y_mode == 'gantry' else 0.0
        by = 0.0 if self.y_mode == 'gantry' else -p['y']
        gz = p['z'] if self.z_mode == 'gantry' else 0.0
        bz = 0.0 if self.z_mode == 'gantry' else -p['z']
        self.gantry.location = (0.0, gy, gz)
        self.bed.location = (0.0, by, bz)
        if shake is not None:
            self.belt.shake = shake
        self.belt.update(p['x'], mx)
        # 皮带轮角度：让齿和皮带的齿啮合
        self.pulley_motor.rotation_euler = (math.pi / 2, 0.0, math.pi / 2 + self.belt.q_motor / RP)
        self.pulley_idler.rotation_euler = (math.pi / 2, 0.0, math.pi / 2 + self.belt.q_idler / RP)

    def add_melt(self, material=None):
        """喷嘴尖下面的一小团熔料：塑料从孔里出来，被压扁，在嘴尖外面鼓成一圈。特写时加上，不挤出时 m.melt.hide_render = True。"""
        h = 0.2                    # 从嘴尖到上一层的距离
        rows = [(0.01, -h), (0.70, -h)]
        for t in np.linspace(0, 1, 9)[1:]:
            rows.append((0.70 - 0.20 * t ** 0.55, -h + h * 1.05 * t))
        rows.append((0.01, 0.01))
        self.melt = revolve('熔料', rows, seg=64, mat=material or studio.plastic(), parent=self.hot)
        me = self.melt.data
        n = len(me.vertices)
        for name, val in (('fresh', 1.0), ('line_rand', 0.5)):
            a = me.attributes.new(name, 'FLOAT', 'POINT')
            a.data.foreach_set('value', np.full(n, val, np.float32))
        return self.melt

    def nozzle_world(self):
        """喷嘴尖的世界坐标。"""
        p = self._p
        gy = p['y'] if self.y_mode == 'gantry' else 0.0
        gz = p['z'] if self.z_mode == 'gantry' else 0.0
        return (p['x'], gy, gz)


def tslot_profile(w, h):
    """铝型材截面（逆时针）：w×h，长边各两道槽，短边一道。"""
    pts = []
    op, lip, wide, depth = 6.0, 1.8, 11.0, 6.1
    if w < 25:
        wide = 9.0

    def side(a, b, slots):
        """从 a 到 b 的一条边，在给定位置开槽。"""
        a, b = np.array(a, float), np.array(b, float)
        d = (b - a) / np.linalg.norm(b - a)
        n = np.array([-d[1], d[0]])      # 向内
        out = [tuple(a)]
        Ls = np.linalg.norm(b - a)
        for s in slots:
            c = a + d * (Ls / 2 + s)
            for u, v in ((-op / 2, 0), (-op / 2, lip), (-wide / 2, lip + 0.1), (-wide / 2, lip + 1.7), (-op / 2 + 0.2, depth), (op / 2 - 0.2, depth),
                         (wide / 2, lip + 1.7), (wide / 2, lip + 0.1), (op / 2, lip), (op / 2, 0)):
                out.append(tuple(c + d * u + n * v))
        return out
    y, z = w / 2, h / 2
    # 坐标 (u,v) = (y,z)。逆时针
    pts += side((-y, -z), (y, -z), [0.0])
    pts += side((y, -z), (y, z), [-h / 4, h / 4])
    pts += side((y, z), (-y, z), [0.0])
    pts += side((-y, z), (-y, -z), [-h / 4, h / 4])
    return rounded(pts, 0.25, 1, closed=True)
