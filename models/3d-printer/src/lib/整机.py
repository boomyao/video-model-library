# -*- coding: utf-8 -*-
"""整台打印机：在 machine.Machine（横梁、喷头、皮带、床）外面加上机架和其余零件。只加不改 machine.py。

    import 整机
    w = 整机.整机()                      # 先调 studio.setup()。参数：spool（料盘）、chains（拖链）、light（机内顶灯）
    w.pose(x=40, y=0, z=0.6)            # 同 machine.Machine.pose；另外更新拖链、PTFE 管、热床线、Z 丝杆转角
    w.pose(x=.., y=.., z=.., follow=(x2, y2))   # 拖链和 PTFE 管跟着 (x2, y2) 走（延时里喷头乱跳时给一个平滑过的位置，管子不抖）
    w.m                                 # 里面的 machine.Machine：w.m.bed、w.m.carriage、w.m.hot、w.m.nozzle_world() 照旧

坐标和 machine.py 一样：1 单位 = 1 mm，喷嘴尖在 (x, y, 0)，床面在 z = -z（床往下沉），床中心是原点。
机架（黑色阳极氧化铝型材，棱上有磨损）：四根立柱在 (±245, ±225)，顶框 z 106..150，底框 z -330..-290，两侧中梁 z 14..54 托着 Y 光杆。
  正面没有中梁和低处的横梁，从正面 3/4 看进去，床和打印件不被挡。
Z 轴：两侧各一根 T8 丝杆（x=±175, y=0，四头，导程 8）和两根光杆（x=±175, y=±70）。丝杆下端接电机，床由两侧支臂托着，往下沉。
其他：X、Y 两条拖链（一节一节的，跟着走）、右侧料盘（红色丝）、料盘出来的丝经顶框导向进 PTFE 管弯到喷头、热床线、底部电源盒和脚垫。
没有做的：外壳面板、屏幕、任何标志和品牌外观。

主要物体：w.frame（机架的父物体）、w.zscrews（两根丝杆）、w.spool、w.ptfe（Tube，.obj 是管子）、w.chain_x、w.chain_y。
"""
import math

import numpy as np
import bpy
from mathutils import Matrix, Vector

import studio
import machine
from machine import box, extrude, revolve, rounded, rect, make_mesh, socket_screw, stepper, hex_r, clip_hex

PX, PY = 245.0, 225.0           # 立柱中心
Z_TOP0, Z_TOP1 = 106.0, 150.0   # 顶框（角件高度）
Z_BOT0, Z_BOT1 = -330.0, -290.0 # 底框
Z_MID0, Z_MID1 = 14.0, 54.0     # 两侧中梁
ZX = 175.0                      # Z 轴所在的 x
LEAD = 8.0                      # 丝杆导程
SCREW_Y = 0.0
ROD_Y = 70.0
GUIDE = (250.0, 70.0, 160.0)    # PTFE 管的导向座（顶框右侧上面）


def _link(ob, parent=None):
    bpy.context.scene.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def empty(name, parent=None, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    _link(e, parent)
    e.location = loc
    return e


def slot_profile(w, h, n_w=None, n_h=None):
    """铝型材截面（逆时针，(u,v)），w×h。每 20 mm 一道槽：20×40 长边两道、短边一道；40×40 每边两道。"""
    n_w = n_w if n_w is not None else max(1, int(round(w / 20)))
    n_h = n_h if n_h is not None else max(1, int(round(h / 20)))
    op, lip, wide, depth = 6.0, 1.8, 9.0, 6.1

    def side(a, b, n):
        a, b = np.array(a, float), np.array(b, float)
        L = np.linalg.norm(b - a)
        d = (b - a) / L
        nn = np.array([-d[1], d[0]])
        out = [tuple(a)]
        for k in range(n):
            c = a + d * (L * (k + 0.5) / n)
            for u, v in ((-op / 2, 0), (-op / 2, lip), (-wide / 2, lip + 0.1), (-wide / 2, lip + 1.7), (-op / 2 + 0.2, depth), (op / 2 - 0.2, depth),
                         (wide / 2, lip + 1.7), (wide / 2, lip + 0.1), (op / 2, lip), (op / 2, 0)):
                out.append(tuple(c + d * u + nn * v))
        return out
    y, z = w / 2, h / 2
    pts = []
    pts += side((-y, -z), (y, -z), n_w)
    pts += side((y, -z), (y, z), n_h)
    pts += side((y, z), (-y, z), n_w)
    pts += side((-y, z), (-y, -z), n_h)
    return rounded(pts, 0.35, 1, closed=True)


def 型材(name, axis, start, length, a=40.0, b=40.0, mat=None, parent=None, bevel=0.4):
    """沿 axis（'x' / 'y' / 'z'）的铝型材，start 是起点处截面中心。a、b 是截面在另外两个轴（按 x、y、z 顺序）上的尺寸。"""
    if axis == 'z':
        ob = extrude(name, slot_profile(a, b), length, bevel=bevel, bevel_seg=2, mat=mat, parent=parent, mode='z')
    elif axis == 'x':
        ob = extrude(name, slot_profile(a, b), length, bevel=bevel, bevel_seg=2, mat=mat, parent=parent, mode='x')     # (u,v)→(y,z)
    else:
        ob = extrude(name, slot_profile(b, a), length, bevel=bevel, bevel_seg=2, mat=mat, parent=parent, mode='y')     # (u,v)→(z,x)
    ob.location = start
    return ob


def tri_mesh(name, V, T, mat=None, parent=None, smooth=False):
    return make_mesh(name, np.asarray(V, float), [tuple(t) for t in T], mat, parent, smooth=smooth)


def plate_with_holes(name, outer, holes, thick, mat=None, parent=None, axis='z'):
    """带孔的平板：outer、holes 是 (u,v) 多边形，沿 axis 拉 thick（局部 0..thick）。孔壁、上下面都有。"""
    from mathutils.geometry import tessellate_polygon
    loops = [list(outer)] + [list(h) for h in holes]
    V = []
    F = []
    base = 0
    flat = []
    for lp in loops:
        flat.append([(p[0], p[1], 0.0) for p in lp])
    tris = tessellate_polygon(flat)
    allp = [p for lp in loops for p in lp]
    n = len(allp)
    for (u, v) in allp:
        V.append((u, v, 0.0))
    for (u, v) in allp:
        V.append((u, v, thick))
    for t in tris:
        F.append((t[2], t[1], t[0]))
        F.append((t[0] + n, t[1] + n, t[2] + n))
    off = 0
    for li, lp in enumerate(loops):
        m = len(lp)
        P = np.array(lp, float)
        area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
        ccw = area > 0
        want_ccw = li == 0
        for j in range(m):
            a, b = off + j, off + (j + 1) % m
            if ccw == want_ccw:
                F.append((a, b, b + n, a + n))
            else:
                F.append((b, a, a + n, b + n))
        off += m
    V = np.array(V, float)
    if axis == 'x':
        V = V[:, [2, 0, 1]]
    elif axis == 'y':
        V = V[:, [1, 2, 0]]
    return make_mesh(name, V, F, mat, parent, smooth=False)


def circle(cx, cy, r, n=24, start=0.0):
    a = start + np.linspace(0, 2 * math.pi, n, endpoint=False)
    return [(cx + r * math.cos(t), cy + r * math.sin(t)) for t in a]


# ---------------------------------------------------------------- 可更新的管子
class Tube:
    """沿 Catmull-Rom 曲线的圆管，顶点数固定，update(pts) 每帧改形状。管子、线缆、管里的丝都用它。"""

    def __init__(self, name, n_ctrl, radius, seg=12, sub=14, mat=None, parent=None, inner=None):
        self.n = (n_ctrl - 1) * sub + 1
        self.sub = sub
        self.seg = seg
        self.radius = radius
        F = []
        for i in range(self.n - 1):
            for j in range(seg):
                jn = (j + 1) % seg
                F.append((i * seg + j, i * seg + jn, (i + 1) * seg + jn, (i + 1) * seg + j))
        F.append(tuple(seg - 1 - j for j in range(seg)))
        F.append(tuple((self.n - 1) * seg + j for j in range(seg)))
        self.F = np.array([f for f in F if len(f) == 4], np.int32)
        self.caps = [f for f in F if len(f) != 4]
        V = np.zeros((self.n * seg, 3))
        V[:, 0] = np.arange(self.n * seg) * 1e-3
        self.obj = make_mesh(name, V, [tuple(f) for f in self.F] + self.caps, mat, parent, smooth=True)
        # u 沿管长（mm），v 绕一圈
        self.obj.data.uv_layers.new(name='UV')
        self.th = np.linspace(0, 2 * math.pi, seg, endpoint=False)

    def curve(self, pts):
        P = np.array(pts, float)
        Q = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
        C = []
        for i in range(1, len(Q) - 2):
            for t in np.linspace(0, 1, self.sub, endpoint=False):
                a, b, c, d = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
                C.append(0.5 * ((2 * b) + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (3 * b - a - 3 * c + d) * t ** 3))
        C.append(P[-1])
        return np.array(C)

    def update(self, pts):
        C = self.curve(pts)
        T = np.gradient(C, axis=0)
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
        u = np.cross(T[0], (0.0, 0.0, 1.0))
        if np.linalg.norm(u) < 1e-3:
            u = np.cross(T[0], (1.0, 0.0, 0.0))
        u /= np.linalg.norm(u)
        V = np.empty((self.n, self.seg, 3))
        for i in range(self.n):
            u = u - T[i] * np.dot(u, T[i])
            u /= max(np.linalg.norm(u), 1e-9)
            w = np.cross(T[i], u)
            V[i] = C[i] + self.radius * (np.outer(np.cos(self.th), u) + np.outer(np.sin(self.th), w))
        V = V.reshape(-1, 3)
        me = self.obj.data
        me.vertices.foreach_set('co', V.astype(np.float32).ravel())
        flat = np.concatenate([self.F.ravel()] + [np.array(c) for c in self.caps])
        counts = np.array([4] * len(self.F) + [len(c) for c in self.caps])
        machine.weighted_normals(me, V, flat, counts)
        # UV
        s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
        uvs = []
        for i in range(self.n - 1):
            for j in range(self.seg):
                jn = j + 1
                uvs += [(s[i], j / self.seg * 6), (s[i], jn / self.seg * 6), (s[i + 1], jn / self.seg * 6), (s[i + 1], j / self.seg * 6)]
        uvs += [(0, 0)] * sum(len(c) for c in self.caps)
        me.uv_layers['UV'].uv.foreach_set('vector', np.array(uvs, np.float32).ravel())
        me.update()
        return C


# ---------------------------------------------------------------- 拖链
def _chain_link_collection(name, w=15.0, h=11.0, pitch=16.0):
    """一节拖链：两块圆角侧板 + 上下两根横杆。局部 x 沿链，y 横向，z 是链弯曲平面里的法向。"""
    coll = bpy.data.collections.get(name)
    if coll:
        return coll
    coll = bpy.data.collections.new(name)
    mat = studio._cached('拖链') or _plastic_black('拖链')
    parts = []
    t = 1.6
    for sy in (-1, 1):
        prof = rect(h, pitch + 3.0, 3.6, 4)      # mode='y'：(u,v)→(z,x)
        ob = extrude(name + '_侧板', prof, t, bevel=0.35, bevel_seg=1, mat=mat, mode='y')
        ob.location = (0, sy * (w / 2) - (t if sy > 0 else 0), 0)
        parts.append(ob)
        # 侧板上的铰接凸台
        rows = [(0.01, 0), (2.2, 0), (2.2, 0.7), (0.01, 0.7)]
        hb = revolve(name + '_铰', rows, seg=16, mat=mat)
        hb.rotation_mode = 'XYZ'
        hb.rotation_euler = (-sy * math.pi / 2, 0, 0)
        hb.location = (pitch / 2, sy * (w / 2 + (0 if sy < 0 else 0)), 0)
        parts.append(hb)
    for sz in (-1, 1):
        ob = box(name + '_横杆', -2.0, 2.0, -w / 2 + 1.0, w / 2 - 1.0, sz * h / 2 - (1.6 if sz > 0 else 0), sz * h / 2 + (0 if sz > 0 else 1.6), bevel=0.3, mat=mat)
        parts.append(ob)
    for ob in parts:
        bpy.context.scene.collection.objects.unlink(ob)
        coll.objects.link(ob)
    return coll


def _plastic_black(name, rough=0.48, base=(0.014, 0.014, 0.015)):
    m, nt, b = studio._mat(name)
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = 0.5
    studio._micro_bump(nt, b, scale=9.0, dist=0.01)
    return m


class Chain:
    """拖链：一端固定，一端跟着动。两段直的加一个半圆弯，弯在 up 方向。

    fixed：固定端位置；d：固定端出发的方向（单位向量，链沿它铺）；up：弯起来的方向；R：弯曲半径；length：链总长。
    update(moving_coord)：动端在 d 方向上的坐标（相对固定端的距离，可以是负的）。
    """

    def __init__(self, name, fixed, d, up, R, length, parent=None, pitch=16.0):
        self.fixed = np.array(fixed, float)
        self.d = np.array(d, float) / np.linalg.norm(d)
        self.up = np.array(up, float) / np.linalg.norm(up)
        self.side = np.cross(self.up, self.d)
        self.R, self.L, self.pitch = R, length, pitch
        self.n = int(length / pitch)
        coll = _chain_link_collection('拖链节', pitch=pitch)
        self.links = []
        for i in range(self.n):
            e = bpy.data.objects.new(f'{name}{i:02d}', None)
            e.instance_type = 'COLLECTION'
            e.instance_collection = coll
            _link(e, parent)
            e.rotation_mode = 'QUATERNION'
            self.links.append(e)

    def point(self, s, m):
        """弧长 s 处的位置和切向。m 是动端坐标。"""
        R = self.R
        b = (self.L - math.pi * R + m) / 2.0           # 弯在 d 方向上的位置
        b = max(b, max(m, 0.0))
        if s <= b:
            p = self.fixed + self.d * s
            t = self.d
            nrm = self.up
        elif s <= b + math.pi * R:
            a = (s - b) / R
            c = self.fixed + self.d * b + self.up * R
            p = c + self.d * (R * math.sin(a)) - self.up * (R * math.cos(a))
            t = self.d * math.cos(a) + self.up * math.sin(a)
            nrm = -(self.d * math.sin(a)) + self.up * math.cos(a)
            nrm = c - p
            nrm /= np.linalg.norm(nrm)
        else:
            s2 = s - b - math.pi * R
            p = self.fixed + self.d * (b - s2) + self.up * (2 * R)
            t = -self.d
            nrm = -self.up
        return p, t, nrm

    def update(self, m):
        for i, e in enumerate(self.links):
            s = (i + 0.5) * self.pitch
            p, t, nrm = self.point(s, m)
            x = t / np.linalg.norm(t)
            z = nrm - x * np.dot(nrm, x)
            z /= np.linalg.norm(z)
            y = np.cross(z, x)
            M = Matrix(((x[0], y[0], z[0]), (x[1], y[1], z[1]), (x[2], y[2], z[2])))
            e.location = Vector(p)
            e.rotation_quaternion = M.to_quaternion()


# ---------------------------------------------------------------- 材料
def frame_metal():
    return studio.black_anodized(name='机架型材', rough=0.40, wear=0.6)


def ptfe_mat(name='PTFE管'):
    m = studio._cached(name)
    if m:
        return m
    m, nt, b = studio._mat(name)
    b.inputs['Base Color'].default_value = (0.80, 0.80, 0.78, 1)
    b.inputs['Roughness'].default_value = 0.42
    b.inputs['Transmission Weight'].default_value = 0.72
    b.inputs['IOR'].default_value = 1.35
    b.inputs['Subsurface Weight'].default_value = 0.0
    return m


def red_plastic_simple(name='红色丝'):
    """管子里和空中那段丝：和打印件同一种 PLA，只是不需要沿线的 UV 细节。"""
    m = studio._cached(name)
    if m:
        return m
    m, nt, b = studio._mat(name)
    base = studio.srgb(studio.RED_HEX)
    if bpy.context.scene.view_settings.view_transform == 'Khronos PBR Neutral':
        base = studio._pbr_neutral_inverse(base)
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Roughness'].default_value = 0.30
    b.inputs['Subsurface Weight'].default_value = 1.0
    b.inputs['Subsurface Radius'].default_value = (1.0, 0.22, 0.10)
    b.inputs['Subsurface Scale'].default_value = 0.19
    return m


def spool_wind_mat(name='料盘丝'):
    """绕在料盘上的红色丝：沿轴向一圈一圈的细纹（1.75 mm 一圈），表面有一点交错。局部 Z 是轴。"""
    m = studio._cached(name)
    if m:
        return m
    m, nt, b = studio._mat(name)
    base = studio.srgb(studio.RED_HEX)
    if bpy.context.scene.view_settings.view_transform == 'Khronos PBR Neutral':
        base = studio._pbr_neutral_inverse(base)
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Subsurface Weight'].default_value = 1.0
    b.inputs['Subsurface Radius'].default_value = (1.0, 0.22, 0.10)
    b.inputs['Subsurface Scale'].default_value = 0.19
    z, objco = studio._object_axis(nt, 'Z')
    w = nt.nodes.new('ShaderNodeTexWave')
    w.wave_type = 'BANDS'
    w.bands_direction = 'Z'
    w.wave_profile = 'SIN'
    w.inputs['Scale'].default_value = 1.0 / 1.75 * 0.5 / math.pi * 2 * math.pi / 1.0
    w.inputs['Distortion'].default_value = 1.2
    w.inputs['Detail'].default_value = 1.0
    nt.links.new(objco, w.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Distance'].default_value = 0.25
    nt.links.new(w.outputs['Fac'], bp.inputs['Height'])
    nt.links.new(bp.outputs[0], b.inputs['Normal'])
    nt.links.new(studio._mix_val(nt, w.outputs['Fac'], 0.22, 0.45), b.inputs['Roughness'])
    return m


# ---------------------------------------------------------------- 整机
class 整机:
    """见文件头。"""

    def __init__(self, spool=True, chains=True, light=True, sock=True, bed_size=236.0):
        self.m = machine.Machine(travel=256.0, bed=True, y_rails=True, z_mode='bed', y_mode='gantry', sock=sock, bed_size=bed_size)
        m = self.m
        self.parts = {}
        # machine.py 给单独横梁镜头做的那根往下垂的电机线，整机里会穿过侧梁，换成进拖链的线
        for ob in m.gantry.children_recursive:
            if ob.name.startswith('电机线'):
                ob.hide_render = True
                ob.hide_viewport = True
        self.frame = empty('机架', m.root)
        self._frame()
        self._yrail_supports()
        self._zaxis()
        self._bed_extras()
        self._base()
        if spool:
            self._spool()
        self._ptfe()
        self.chain_x = self.chain_y = None
        if chains:
            self._chains()
        self._bed_cable()
        if light:
            self._chamber_light()
        self.pose(0.0, 0.0, 0.0)

    # ----- 机架 -----
    def _frame(self):
        f = self.frame
        mat = frame_metal()
        corner = studio.black_anodized(name='角件', rough=0.52, wear=0.85)
        c = 22.0
        # 立柱
        for sx in (-1, 1):
            for sy in (-1, 1):
                型材('立柱', 'z', (sx * PX, sy * PY, Z_BOT1 + 4.0), Z_TOP0 - (Z_BOT1 + 4.0), mat=mat, parent=f)
        # 顶框、底框：沿 X 的前后两根，沿 Y 的左右两根，接在角件之间
        for z0, z1 in ((Z_TOP0 + 4.0, Z_TOP1), (Z_BOT0, Z_BOT1)):
            zc = (z0 + z1) / 2
            for sy in (-1, 1):
                型材('横梁X', 'x', (-PX + c, sy * PY, zc), 2 * (PX - c), 40, 40, mat=mat, parent=f)
            for sx in (-1, 1):
                型材('横梁Y', 'y', (sx * PX, -PY + c, zc), 2 * (PY - c), 40, 40, mat=mat, parent=f)
        # 两侧中梁（托 Y 光杆），20×40 竖放
        for sx in (-1, 1):
            型材('中梁', 'y', (sx * PX, -PY + 20.0, (Z_MID0 + Z_MID1) / 2), 2 * (PY - 20.0), 20, 40, mat=mat, parent=f)
            for sy in (-1, 1):
                # 中梁和立柱之间的 L 形角码
                y0 = sy * (PY - 20.0)
                for zz in (Z_MID0 - 3.0, Z_MID1 + 0.0):
                    box('角码', sx * PX - 9, sx * PX + 9, min(y0, y0 - sy * 22), max(y0, y0 - sy * 22), zz, zz + 3.0, bevel=0.4, mat=corner, parent=f)
        # 角件：三向铸铝角件，比型材大一圈，带三颗螺钉
        for sx in (-1, 1):
            for sy in (-1, 1):
                for z0, z1 in ((Z_TOP0, Z_TOP1 + 2.0), (Z_BOT0 - 2.0, Z_BOT1 + 4.0)):
                    box('角件', sx * PX - c, sx * PX + c, sy * PY - c, sy * PY + c, z0, z1, bevel=2.2, r=2.0, mat=corner, parent=f)
                    zc = (z0 + z1) / 2
                    s = socket_screw('角件螺钉', f, d=5.0)
                    s.rotation_mode = 'XYZ'
                    s.rotation_euler = (0, sx * math.pi / 2, 0)
                    s.location = (sx * (PX + c), sy * PY, zc)
                    s = socket_screw('角件螺钉', f, d=5.0)
                    s.rotation_mode = 'XYZ'
                    s.rotation_euler = (-sy * math.pi / 2, 0, 0)
                    s.location = (sx * PX, sy * (PY + c), zc)
                    s = socket_screw('角件螺钉', f, d=5.0)
                    s.location = (sx * PX, sy * PY, z1 if z1 > 0 else z0)
                    if z1 < 0:
                        s.rotation_mode = 'XYZ'
                        s.rotation_euler = (math.pi, 0, 0)
        # 立柱和横梁接头处的盖帽螺钉（装饰）、型材上的 T 形螺母头
        for sx in (-1, 1):
            for y in (-150.0, -60.0, 60.0, 150.0):
                s = socket_screw('中梁螺钉', f, d=4.0)
                s.rotation_mode = 'XYZ'
                s.rotation_euler = (0, sx * math.pi / 2, 0)
                s.location = (sx * (PX + 10.0), y, Z_MID1 - 10.0)

    def _yrail_supports(self):
        """Y 光杆两端的支座，坐在中梁内侧。"""
        f = self.frame
        blk = studio.black_anodized(name='光杆座', rough=0.45, wear=0.7)
        rail_z = 42.0
        for sx in (-1, 1):
            xr = sx * (self.m.L / 2 + 13.0)
            for sy in (-1, 1):
                y0 = sy * 200.0
                x0, x1 = sorted((xr - sx * 11.0, sx * (PX - 10.0)))
                box('光杆座', x0, x1, min(y0, sy * 186.0), max(y0, sy * 186.0), Z_MID0 + 8.0, rail_z + 10.0, bevel=0.8, r=1.0, mat=blk, parent=f)
                s = socket_screw('光杆座螺钉', f, d=3.0)
                s.location = (xr, sy * 193.0, rail_z + 10.0)

    # ----- Z 轴 -----
    def _zaxis(self):
        f = self.frame
        rod = studio.steel(name='Z光杆', rough=0.14)
        scr = studio.steel(name='丝杆', rough=0.24)
        blk = studio.black_anodized(name='Z支座', rough=0.45, wear=0.7)
        z_lo = Z_BOT1 + 6.0
        z_hi = Z_MID0 + 6.0
        self.zscrews = []
        for sx in (-1, 1):
            x = sx * ZX
            # 底部横梁（沿 Y），电机和光杆座坐在上面
            型材('Z底梁', 'y', (x, -PY + 20.0, (Z_BOT0 + Z_BOT1) / 2), 2 * (PY - 20.0), 40, 40, mat=frame_metal(), parent=f)
            # 顶部支架：从中梁伸进来，压住光杆和丝杆上端
            x0, x1 = sorted((x - sx * 18.0, sx * (PX - 10.0)))
            box('Z顶支架', x0, x1, -ROD_Y - 16.0, ROD_Y + 16.0, z_hi, z_hi + 10.0, bevel=0.8, r=3.0, mat=blk, parent=f)
            for sy in (-1, 1):
                y = sy * ROD_Y
                rows = rounded([(0.01, z_lo), (5.0, z_lo), (5.0, z_hi + 10.0), (0.01, z_hi + 10.0)], [0, 0.4, 0.4, 0], 2)
                revolve('Z光杆', rows, seg=40, mat=rod, parent=f, loc=(x, y, 0))
                # 下面的光杆座（SK10 那样的）
                box('光杆底座', x - 16, x + 16, y - 8, y + 8, Z_BOT1, Z_BOT1 + 22.0, bevel=0.6, r=1.5, mat=blk, parent=f)
                s = socket_screw('光杆座螺钉', f, d=3.0)
                s.rotation_mode = 'XYZ'
                s.rotation_euler = (-sy * math.pi / 2 if False else math.pi / 2, 0, 0)
                s.location = (x, y - 8.0, Z_BOT1 + 14.0)
            # 电机：面朝上
            mot = empty('Z电机', f, (x, SCREW_Y, -250.0))
            stepper(mot, name='Z电机', length=34.0)
            box('Z电机座', x - 24, x + 24, SCREW_Y - 24, SCREW_Y + 24, Z_BOT1, -284.0, bevel=0.6, r=2.0, mat=blk, parent=f)
            # 联轴器
            cpl = studio.aluminium_turned(name='联轴器', rough=0.30)
            rows = rounded([(0.01, -248.0), (9.5, -248.0), (9.5, -223.0), (0.01, -223.0)], [0, 0.6, 0.6, 0], 2)
            revolve('联轴器', rows, seg=48, mat=cpl, parent=f, loc=(x, SCREW_Y, 0))
            # 丝杆：四头 T8，真的螺旋纹
            holder = empty('丝杆', f, (x, SCREW_Y, 0))
            holder.rotation_mode = 'XYZ'
            self.zscrews.append(holder)
            self._leadscrew(holder, -223.0, z_hi + 10.0, scr)
            # 上端轴承
            rows = [(4.2, z_hi + 10.0), (11.0, z_hi + 10.0), (11.0, z_hi + 15.0), (4.2, z_hi + 15.0)]
            revolve('丝杆轴承', rows, seg=40, mat=studio.steel(name='轴承外圈', rough=0.3), parent=f, loc=(x, SCREW_Y, 0), close_bottom=False, close_top=False)

    def _leadscrew(self, parent, z0, z1, mat):
        r0, depth, pitch = 3.55, 0.75, 2.0
        rows = [(0.01, z0), (r0, z0)]
        zs = np.arange(z0 + 0.4, z1 - 0.4, pitch / 8)

        def prof(u):
            u = u - np.floor(u)
            tri = np.clip(np.minimum(u, 1 - u) * 4.0 - 0.4, 0, 1)
            return tri
        for z in zs:
            rows.append((lambda th, z=z: r0 + depth * prof((z + LEAD * th / (2 * math.pi)) / pitch), z))
        rows += [(r0, z1), (0.01, z1)]
        return revolve('丝杆螺纹', rows, seg=28, mat=mat, parent=parent)

    # ----- 床的支撑 -----
    def _bed_extras(self):
        b = self.m.bed
        blk = studio.black_anodized(name='床支臂', rough=0.42, wear=0.6)
        s2 = self.m.bed_size / 2
        # 床下面两根沿 Y 的型材和一根横的
        for sx in (-1, 1):
            型材('床架', 'y', (sx * 80.0, -s2 + 6.0, -27.0), 2 * s2 - 12.0, 20, 40, mat=frame_metal(), parent=b)
        型材('床架横', 'x', (-70.0, s2 - 30.0, -27.0), 140.0, 20, 40, mat=frame_metal(), parent=b)
        # 两侧支臂：伸到 Z 轴，抱住光杆，丝杆螺母在中间
        for sx in (-1, 1):
            x = sx * ZX
            x0, x1 = sorted((sx * 70.0, x + sx * 16.0))
            box('床支臂', x0, x1, -ROD_Y - 18.0, ROD_Y + 18.0, -20.0, -12.0, bevel=0.8, r=4.0, mat=blk, parent=b)
            for sy in (-1, 1):
                rows = rounded([(5.2, -44.0), (10.5, -44.0), (10.5, -12.0), (5.2, -12.0)], [0, 0.8, 0.8, 0], 2)
                revolve('直线轴承座', rows, seg=40, mat=blk, parent=b, loc=(x, sy * ROD_Y, 0), close_bottom=False, close_top=False)
            nut = studio.brass(name='丝杆螺母', wear=0.0, residue=None)
            rows = rounded([(4.1, -36.0), (7.0, -36.0), (7.0, -22.0), (11.0, -22.0), (11.0, -20.0), (4.1, -20.0)], [0, 0.3, 0.2, 0.3, 0.3, 0], 2)
            revolve('丝杆螺母', rows, seg=48, mat=nut, parent=b, loc=(x, SCREW_Y, 0), close_bottom=False, close_top=False)
        # 调平：四角的滚花螺母和弹簧
        spring = studio.steel(name='弹簧', rough=0.3)
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = sx * (s2 - 12.0), sy * (s2 - 12.0)
                pts = []
                for k in range(80):
                    a = k / 79 * 2 * math.pi * 4.5
                    pts.append((x + 4.0 * math.cos(a), y + 4.0 * math.sin(a), -6.5 - 9.0 * k / 79))
                machine.tube('调平弹簧', pts, 0.55, 8, spring, b, sub=2)
                kn = studio.aluminium(name='滚花螺母', rough=0.42, base=(0.62, 0.62, 0.63))
                rows = [(1.6, -22.0), (clip_hex(7.6, hex_r(14.0, 0.1)), -22.0), (lambda th: 7.0 + 0.35 * np.sign(np.sin(th * 18)), -21.6), (lambda th: 7.0 + 0.35 * np.sign(np.sin(th * 18)), -16.8), (6.0, -16.4), (1.6, -16.4)]
                revolve('滚花螺母', rows, seg=72, mat=kn, parent=b, loc=(x, y, 0))
                sc = socket_screw('床角螺钉', b, d=3.0)
                sc.location = (x, y, 0.02)
                sc.scale = (1, 1, 0.15)
        # 加热垫（床板下面）
        heat = studio.silicone(name='加热垫')
        extrude('加热垫', rect(2 * s2 - 20, 2 * s2 - 20, 6.0, 3), 1.2, bevel=0.3, bevel_seg=1, mat=heat, parent=b).location = (0, 0, -6.9)

    # ----- 底座 -----
    def _base(self):
        f = self.frame
        panel = _plastic_black('底板', rough=0.62, base=(0.010, 0.010, 0.011))
        extrude('底板', rect(2 * PX - 20, 2 * PY - 20, 4, 3), 3.0, bevel=0.5, mat=panel, parent=f).location = (0, 0, Z_BOT0 + 8.0)
        # 电源盒：后部，带散热孔
        box_mat = studio.black_anodized(name='电源盒', rough=0.5, wear=0.4)
        box('电源盒', -130.0, 60.0, 120.0, 205.0, Z_BOT1 - 6.0, Z_BOT1 + 52.0, bevel=1.5, r=3.0, mat=box_mat, parent=f)
        for i in range(14):
            x = -120.0 + i * 12.0
            box('散热孔', x, x + 6.0, 119.2, 121.0, Z_BOT1 + 10.0, Z_BOT1 + 40.0, bevel=0.6, r=2.0, mat=studio.wire(name='孔黑', color=(0.002, 0.002, 0.002)), parent=f)
        # 脚垫
        rub = studio.rubber(name='脚垫')
        for sx in (-1, 1):
            for sy in (-1, 1):
                rows = rounded([(0.01, Z_BOT0 - 16.0), (17.0, Z_BOT0 - 16.0), (15.0, Z_BOT0 - 2.0), (0.01, Z_BOT0 - 2.0)], [0, 1.5, 1.0, 0], 2)
                revolve('脚垫', rows, seg=40, mat=rub, parent=f, loc=(sx * PX, sy * PY, 0))

    # ----- 料盘 -----
    def _spool(self):
        f = self.frame
        sp = empty('料盘', f, (PX + 92.0, 40.0, -70.0))
        sp.rotation_mode = 'XYZ'
        sp.rotation_euler = (0, math.pi / 2, 0)        # 局部 Z → 世界 X，料盘轴沿 X
        self.spool = sp
        fl = _plastic_black('料盘侧板', rough=0.34, base=(0.020, 0.020, 0.022))
        outer = circle(0, 0, 100.0, 96)
        holes = [circle(62.0 * math.cos(a), 62.0 * math.sin(a), 15.0, 28) for a in np.linspace(0, 2 * math.pi, 6, endpoint=False) + 0.3]
        holes.append(circle(0, 0, 27.5, 40))
        for z in (-34.0, 31.0):
            ob = plate_with_holes('料盘侧板', outer, holes, 3.0, mat=fl, parent=sp)
            ob.location = (0, 0, z)
        hub = _plastic_black('料盘芯', rough=0.6, base=(0.05, 0.045, 0.04))
        rows = [(27.5, -31.0), (48.0, -31.0), (48.0, 31.0), (27.5, 31.0)]
        revolve('料盘芯', rows, seg=96, mat=hub, parent=sp, close_bottom=False, close_top=False)
        rows = rounded([(48.0, -30.6), (86.0, -30.6), (86.6, -20.0), (86.0, 0.0), (86.6, 20.0), (86.0, 30.6), (48.0, 30.6)], [0, 1.2, 0, 0, 0, 1.2, 0], 2)
        self.spool_wind = revolve('料盘丝', rows, seg=192, mat=spool_wind_mat(), parent=sp, close_bottom=False, close_top=False)
        # 料盘架：从右侧中梁伸出来的一根杆
        arm_mat = studio.black_anodized(name='料盘架', rough=0.45, wear=0.7)
        rows = rounded([(0.01, 0.0), (13.0, 0.0), (13.0, 96.0), (0.01, 96.0)], [0, 0.6, 0.6, 0], 2)
        arm = revolve('料盘轴', rows, seg=48, mat=arm_mat, parent=f)
        arm.rotation_mode = 'XYZ'
        arm.rotation_euler = (0, math.pi / 2, 0)
        arm.location = (PX + 20.0, 40.0, -70.0)
        box('料盘架座', PX + 10.0, PX + 22.0, 10.0, 70.0, -100.0, Z_MID0 + 10.0, bevel=1.0, r=3.0, mat=arm_mat, parent=f)

    # ----- PTFE 管 -----
    def _ptfe(self):
        f = self.frame
        self.ptfe = Tube('PTFE管', 6, 2.0, seg=14, sub=16, mat=ptfe_mat(), parent=None)
        self.ptfe_fil = Tube('管里的丝', 6, 0.875, seg=8, sub=16, mat=red_plastic_simple(), parent=None)
        # 料盘到导向座之间露在外面的一段丝
        self.air_fil = Tube('空中的丝', 3, 0.875, seg=8, sub=12, mat=red_plastic_simple(), parent=None)
        g = GUIDE
        self.air_fil.update([(PX + 92.0 + 0.0, 40.0 + 0.0, -70.0 + 86.4), ((PX + 92.0 + g[0]) / 2 + 20, (40.0 + g[1]) / 2, (16.4 + g[2]) / 2), (g[0], g[1], g[2] - 10.0)])
        blk = studio.black_anodized(name='导向座', rough=0.45, wear=0.7)
        box('导向座', g[0] - 14.0, g[0] + 14.0, g[1] - 10.0, g[1] + 10.0, Z_TOP1, g[2] - 2.0, bevel=0.8, r=2.0, mat=blk, parent=f)
        rows = rounded([(2.1, g[2] - 2.0), (4.5, g[2] - 2.0), (4.5, g[2] + 6.0), (2.1, g[2] + 6.0)], [0, 0.4, 0.4, 0], 2)
        revolve('管接头', rows, seg=32, mat=studio.steel(name='管接头', rough=0.3), parent=f, loc=(g[0], g[1], 0), close_bottom=False, close_top=False)

    def _ptfe_pts(self, hx, hy):
        """喷头顶上进管的点 → 往上 → 拱过横梁 → 导向座。"""
        top = 63.5
        g = np.array(GUIDE)
        h = np.array([hx, hy, top])
        mid = (h + g) / 2
        span = np.linalg.norm((g - h)[:2])
        return [tuple(h), tuple(h + (0, 0, 45.0)), tuple(mid + (0, -10.0, 48.0 + 0.05 * span)), tuple(g + (-34.0, -8.0, 48.0)), tuple(g + (-6.0, 0, 26.0)), tuple(g + (0, 0, 6.0))]

    # ----- 拖链 -----
    def _chains(self):
        g = self.m.gantry
        # X：横梁上面，固定在左边，动端接滑块顶
        self.chain_x = Chain('X拖链', fixed=(-150.0, 53.0, 112.0), d=(1, 0, 0), up=(0, 0, 1), R=16.0, length=352.0, parent=g)
        tray = studio.black_anodized(name='拖链托板', rough=0.45, wear=0.6)
        box('X拖链托板', -152.0, 150.0, 44.0, 62.0, 104.0, 106.0, bevel=0.3, mat=tray, parent=g)
        box('X拖链接头', -10.0, 10.0, 22.0, 60.0, 136.0, 139.0, bevel=0.4, mat=tray, parent=self.m.carriage)
        box('X拖链接头竖', -10.0, 10.0, 22.0, 28.0, 117.0, 139.0, bevel=0.4, mat=tray, parent=self.m.carriage)
        # Y：左侧中梁上面，固定在后面，动端接横梁左端
        self.chain_y = Chain('Y拖链', fixed=(-PX, 210.0, Z_MID1 + 6.0), d=(0, -1, 0), up=(0, 0, 1), R=18.0, length=420.0, parent=self.frame)
        arm = studio.black_anodized(name='拖链支架', rough=0.45, wear=0.7)
        L = self.m.L
        box('Y拖链支架', -PX - 10.0, -L / 2 + 2.0, 30.0, 42.0, 112.0, 118.0, bevel=0.5, mat=arm, parent=g)
        box('Y拖链支架竖', -PX - 10.0, -PX + 10.0, 30.0, 42.0, Z_MID1 + 6.0 + 36.0 + 6.0, 118.0, bevel=0.5, mat=arm, parent=g)
        # 电机线：从 X 电机后面出来，进拖链
        mx, bz = self.m.motor_x, self.m.belt_z
        machine.tube('X电机线', [(mx, 74.0, bz - 21.2), (mx - 2, 78.0, bz - 26), (mx - 10, 70.0, bz + 6), (mx - 22, 52.0, 112.0), (-150.0, 53.0, 114.0)], 1.6, 10,
                     studio.wire(name='电机线2', color=(0.010, 0.010, 0.011)), g, sub=10)

    def _bed_cable(self):
        self.bed_cable = Tube('热床线', 5, 3.2, seg=12, sub=12, mat=studio.wire(name='热床线', color=(0.012, 0.012, 0.013)), parent=None)

    def _chamber_light(self):
        """机内顶灯：顶框前梁下面一条灯，往下照床（相机看不到灯本身）。"""
        li = studio.area_light('机内顶灯', (0.0, -PY + 30.0, Z_TOP0 - 2.0), (0.0, -20.0, -200.0), 380.0, 0.9, studio.blackbody(5200), size_y=14.0)
        li.visible_camera = False
        self.chamber = li
        bar = studio.wire(name='灯条壳', color=(0.03, 0.03, 0.032))
        box('灯条', -200.0, 200.0, -PY + 22.0, -PY + 36.0, Z_TOP0 - 4.0, Z_TOP0, bevel=0.6, mat=bar, parent=self.frame)

    # ----- 摆位 -----
    def pose(self, x=None, y=None, z=None, motor_x=None, shake=None, follow=None):
        m = self.m
        m.pose(x=x, y=y, z=z, motor_x=motor_x, shake=shake)
        p = m._p
        fx, fy = (p['x'], p['y']) if follow is None else follow
        # 丝杆转角：床下沉 z，丝杆转 z / 导程 圈
        for i, s in enumerate(self.zscrews):
            s.rotation_euler = (0, 0, (1 if i == 0 else -1) * 2 * math.pi * p['z'] / LEAD)
        if self.chain_x is not None:
            self.chain_x.update(fx - (-150.0))
            self.chain_y.update(-(fy + 36.0) + 210.0)
        self.ptfe.update(self._ptfe_pts(fx, fy))
        self.ptfe_fil.update(self._ptfe_pts(fx, fy))
        bz = -p['z']
        self.bed_cable.update([(-100.0, 110.0, bz - 8.0), (-104.0, 140.0, bz - 30.0), (-110.0, 175.0, (bz - 30.0 + Z_BOT1 + 60.0) / 2), (-112.0, 190.0, Z_BOT1 + 70.0), (-110.0, 195.0, Z_BOT1 + 52.0)])
