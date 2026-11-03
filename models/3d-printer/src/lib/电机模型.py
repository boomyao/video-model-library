# -*- coding: utf-8 -*-
"""切开的 1.8° 混合式步进电机。结构按真实的来，运动只有转子一个刚体，每帧转一下就行。

真实结构（出处见 画面/素材出处.md）：
    转子 50 齿，齿距 7.2°；前后两段齿错开半个齿距（3.6°），中间夹一块轴向磁铁。
    定子 8 极，每极 6 个小齿，齿距也是 7.2°。45° = 6.25 个齿距，所以相邻两极相对转子差 1/4 齿距，转一步 1.8° 就换一对极对齐。
    相邻的极分属两相：A 相 0° 90° 180° 270°，B 相 45° 135° 225° 315°。

    局部坐标：Z 是轴，前端面（轴伸出来那面）朝 +Z，和 machine.stepper 一样：局部原点在前端面中心，机身向 -Z。
    切法：前盖拿掉；φ=WEDGE（默认 135°，一个角的方向）两边各 45° 的扇形整个切掉，切面穿过 90° 和 180° 两极的中线。

    m = 电机模型.Motor(parent=None, wedge=135.0, cap_rear=True)
    m.set(theta=度, theta_c=度)    # 转子角、凹槽角
    m.coil(a, b)                   # 两相线圈的亮度（0..1）
    m.crown_light(亮度, 扫过比例)   # 凹槽的亮度和“画一圈”的进度
    m.bead_light(亮度)             # 红珠
"""
import math

import numpy as np
import bpy

import machine
import studio
from machine import make_mesh, revolve, rounded, _offset_poly

N_R = 50
PITCH = 360.0 / N_R             # 转子齿距，度
STEP = PITCH / 4                # 一整步，度
R_TIP = 12.5                    # 转子外径 25 mm，配 54 g·cm² 的 40 mm 电机算出来差不多
TOOTH_D = 0.72
R_ROOT = R_TIP - TOOTH_D
GAP = 0.10                      # 气隙，真实 0.05 到 0.1
R_BORE = R_TIP + GAP
S_TOOTH_D = 0.60
R_FACE = R_BORE + S_TOOTH_D
R_YOKE = 19.0
ARM_HALF = 2.75
TEETH_PER_POLE = 6
Z_FACE = 0.0                    # 前端面（前盖的外面）
Z_TOP = -8.0                    # 铁芯顶面（前盖拿掉后露出来）
Z_STACK0 = -26.2
Z_MAG1, Z_MAG0 = -15.7, -18.5
Z_REAR_IN = -30.0               # 后盖内腔底面
Z_BACK = -34.0
A_SQ = 42.3
K_FIRST = 43                    # 被涂红的那个齿的编号。θ=0 时它在 3.6+43×7.2 = 313.2°，正好在切开区的对面

# 凹槽：半管截面，沿圆周按势能起伏。θc=0 时波谷对准转子齿（3.6° + k×7.2°）
CROWN_R = 12.56
CROWN_RHO = 0.24
CROWN_A = 0.33                  # 波谷到波峰的高度差是 2A
CROWN_Z0 = Z_TOP + 0.03 + CROWN_RHO
BEAD_R = 0.19


def crown_z(dphi_deg):
    """dphi：相对波谷的角度（度）。返回半管中线高度。势能是正弦的，真实的力矩-角度曲线就是这样。"""
    return CROWN_Z0 + CROWN_A * (1.0 - np.cos(np.radians(dphi_deg) * N_R))


def bead_z(dphi_deg):
    return crown_z(dphi_deg) - (CROWN_RHO - BEAD_R)


# ---------- 材料 ----------
def lam(name, base=0.30, rough=0.40, metal=1.0, bump=0.035, sheet=0.35):
    """硅钢片：一片片叠起来。局部 Z 是轴。每片的反光还略有不同，这比凹凸更像真的。"""
    m = studio._cached(name)
    if m:
        return m
    m, nt, b = studio._mat(name)
    b.inputs['Metallic'].default_value = metal
    objco = nt.nodes.new('ShaderNodeTexCoord').outputs['Object']
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(objco, sep.inputs[0])
    # 片号
    k = studio._math(nt, 'FLOOR', studio._math(nt, 'DIVIDE', sep.outputs['Z'], sheet))
    wn = nt.nodes.new('ShaderNodeTexWhiteNoise')
    wn.noise_dimensions = '1D'
    nt.links.new(k, wn.inputs['W'])
    # 片与片的缝：离片边越近越暗、越糙
    fr = studio._math(nt, 'FRACT', studio._math(nt, 'DIVIDE', sep.outputs['Z'], sheet))
    seam = studio._math(nt, 'ABSOLUTE', studio._math(nt, 'SUBTRACT', fr, 0.5))
    seam = studio._ramp(nt, seam, 0.0, 1.0, lo=0.44, hi=0.5)
    tone = studio._mix_val(nt, wn.outputs['Value'], base * 0.90, base * 1.08)
    col = studio._math(nt, 'MULTIPLY', tone, studio._mix_val(nt, seam, 1.0, 0.45))
    nt.links.new(col, b.inputs['Base Color'])
    nt.links.new(studio._mix_val(nt, wn.outputs['Value'], rough - 0.03, rough + 0.04), b.inputs['Roughness'])
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Distance'].default_value = bump
    nt.links.new(studio._math(nt, 'SUBTRACT', 1.0, seam), bp.inputs['Height'])
    nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return m


def face(name, base, rough, scale=60.0, dist=0.0022, metal=1.0):
    """转子和铁芯的端面：最上面那片硅钢片，有很细的颗粒，高光不是一块干净的渐变。"""
    m = studio._cached(name)
    if m:
        return m
    m, nt, b = studio._mat(name)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Base Color'].default_value = (base, base, base * 1.01, 1)
    fac = studio._micro_bump(nt, b, scale=scale, dist=dist)
    nt.links.new(studio._mix_val(nt, fac, rough - 0.05, rough + 0.05), b.inputs['Roughness'])
    return m


def copper(name='铜线'):
    """漆包铜线。通电的亮度从物体颜色的 R 通道读（ob.color），每帧改物体颜色不用重编材质。"""
    m = studio._cached(name)
    if m:
        return m
    m, nt, b = studio._mat(name)
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Base Color'].default_value = (0.86, 0.40, 0.17, 1)
    b.inputs['Roughness'].default_value = 0.34
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    sp = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(oi.outputs['Color'], sp.inputs[0])
    b.inputs['Emission Color'].default_value = (0.95, 0.42, 0.13, 1)
    nt.links.new(studio._math(nt, 'MULTIPLY', sp.outputs[0], 0.26), b.inputs['Emission Strength'])
    return m


def paint(name='红漆', hexc=studio.RED_MARK, rough=0.55):
    m = studio._cached(name)
    if m:
        return m
    m, nt, b = studio._mat(name)
    b.inputs['Base Color'].default_value = (*studio.srgb(hexc), 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = 0.4
    return m


def bead_mat(name='红珠'):
    m = studio._cached(name)
    if m:
        return m
    m, nt, b = studio._mat(name)
    c = studio.srgb(studio.RED_MARK)
    b.inputs['Base Color'].default_value = (*c, 1)
    b.inputs['Roughness'].default_value = 0.22
    b.inputs['Specular IOR Level'].default_value = 0.6
    b.inputs['Emission Color'].default_value = (*c, 1)
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    sp = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(oi.outputs['Color'], sp.inputs[0])
    nt.links.new(studio._math(nt, 'MULTIPLY', sp.outputs[0], 0.55), b.inputs['Emission Strength'])
    return m


def crown_mat(name='凹槽'):
    """半管：亮度低，边缘（掠射角）亮一点，正对着看几乎透明。R 亮度、G 扫过比例。"""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    sp = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(oi.outputs['Color'], sp.inputs[0])
    ang = nt.nodes.new('ShaderNodeAttribute')
    ang.attribute_name = 'ang'
    hg = nt.nodes.new('ShaderNodeAttribute')
    hg.attribute_name = 'hg'
    lay = nt.nodes.new('ShaderNodeLayerWeight')
    lay.inputs['Blend'].default_value = 0.42
    # 边缘系数
    rim = studio._math(nt, 'POWER', lay.outputs['Facing'], 2.2)
    # 波谷亮、波峰暗：眼睛看的是谷
    val = studio._mix_val(nt, hg.outputs['Fac'], 1.0, 0.42)
    # 扫过：ang < sweep 才亮，边界羽化
    sw = studio._math(nt, 'SUBTRACT', sp.outputs[1], ang.outputs['Fac'])
    sw = studio._math(nt, 'MULTIPLY', sw, 40.0, clamp=True)
    alpha = studio._math(nt, 'ADD', studio._math(nt, 'MULTIPLY', rim, 0.85), 0.16)
    alpha = studio._math(nt, 'MULTIPLY', alpha, sw)
    alpha = studio._math(nt, 'MULTIPLY', alpha, studio._math(nt, 'MINIMUM', studio._math(nt, 'MULTIPLY', sp.outputs[0], 4.0), 1.0))
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*studio.srgb(studio.CYAN_MARK), 1)
    nt.links.new(studio._math(nt, 'MULTIPLY', studio._math(nt, 'MULTIPLY', sp.outputs[0], val), 1.0), em.inputs['Strength'])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(alpha, mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return m


# ---------- 轮廓 ----------
def _pol(r, deg):
    a = np.radians(deg)
    return (float(r * np.cos(a)), float(r * np.sin(a)))


def _arc(r, a0, a1, n):
    return [_pol(r, a) for a in np.linspace(a0, a1, n)]


def rotor_outline(offset_deg, tooth_half=1.50, root_half=2.05):
    """50 个齿，齿中心在 offset + k×7.2°（逆时针）。"""
    P = []
    for k in range(N_R):
        c = offset_deg + k * PITCH
        P += [_pol(R_ROOT, c - root_half)]
        P += _arc(R_TIP, c - tooth_half, c + tooth_half, 3)
        P += [_pol(R_ROOT, c + root_half)]
        P += _arc(R_ROOT, c + root_half + 0.45, c + PITCH - root_half - 0.45, 2)
    return P


def pole_profile(alpha):
    """一个极的内缘（φ 从 alpha-22.5° 增加到 alpha+22.5°）：槽底 → 极臂 → 极靴 → 六个小齿 → 对称回来。"""
    half_slot = 22.5
    shoe = 20.4
    th_tip, th_root = 1.50, 1.85
    a_arm = math.degrees(math.asin(ARM_HALF / R_YOKE))
    rot = lambda u, v: (float(v * math.cos(math.radians(alpha)) - u * math.sin(math.radians(alpha))),
                        float(v * math.sin(math.radians(alpha)) + u * math.cos(math.radians(alpha))))
    pts = []
    pts += _arc(R_YOKE, alpha - half_slot, alpha - a_arm - 1.6, 7)
    # 极臂的左边（u<0），靠槽底有圆角
    pts += [rot(-ARM_HALF - 0.32, R_YOKE - 0.06), rot(-ARM_HALF, R_YOKE - 0.45), rot(-ARM_HALF, 15.5)]
    # 极靴背面，斜着展开到极靴尖
    u_tip = (R_FACE + 0.95) * math.sin(math.radians(shoe))
    v_tip = (R_FACE + 0.95) * math.cos(math.radians(shoe))
    pts += [rot(-ARM_HALF - 0.25, 15.05), rot(-u_tip, v_tip)]
    # 极靴尖
    pts += _arc(R_FACE, alpha - shoe, alpha - shoe + 0.5, 2)
    centers = [(j - (TEETH_PER_POLE - 1) / 2) * PITCH for j in range(TEETH_PER_POLE)]
    for i, c in enumerate(centers):
        cc = alpha + c
        if i > 0:
            pts += _arc(R_FACE, cc - PITCH + th_root + 0.35, cc - th_root - 0.35, 2)
        pts += [_pol(R_FACE, cc - th_root)]
        pts += _arc(R_BORE, cc - th_tip, cc + th_tip, 3)
        pts += [_pol(R_FACE, cc + th_root)]
    pts += _arc(R_FACE, alpha + shoe - 0.5, alpha + shoe, 2)
    pts += [rot(u_tip, v_tip), rot(ARM_HALF + 0.25, 15.05), rot(ARM_HALF, 15.5), rot(ARM_HALF, R_YOKE - 0.45), rot(ARM_HALF + 0.32, R_YOKE - 0.06)]
    pts += _arc(R_YOKE, alpha + a_arm + 1.6, alpha + half_slot, 7)
    return pts


def square_outline(a, c, r=0.5):
    p = [(-a / 2 + c, -a / 2), (a / 2 - c, -a / 2), (a / 2, -a / 2 + c), (a / 2, a / 2 - c),
         (a / 2 - c, a / 2), (-a / 2 + c, a / 2), (-a / 2, a / 2 - c), (-a / 2, -a / 2 + c)]
    return rounded(p, r, 3, closed=True)


def _square_arc(a, c, phi0, phi1, r=0.5, n=240):
    """方形外框从 φ0 逆时针走到 φ1 的那一段（φ0 < φ1）。沿射线和外框求交，保留所有拐点。"""
    P = np.array(square_outline(a, c, r))
    ang = (np.degrees(np.arctan2(P[:, 1], P[:, 0])) - phi0) % 360.0
    order = np.argsort(ang)
    span = phi1 - phi0
    keep = [tuple(P[i]) for i in order if 1e-6 < ang[i] < span - 1e-6]

    def hit(phi):
        d = np.array([math.cos(math.radians(phi)), math.sin(math.radians(phi))])
        best = None
        for i in range(len(P)):
            p, q = P[i], P[(i + 1) % len(P)]
            e = q - p
            den = d[0] * e[1] - d[1] * e[0]
            if abs(den) < 1e-9:
                continue
            t = (p[0] * e[1] - p[1] * e[0]) / den
            u = (p[0] * d[1] - p[1] * d[0]) / den
            if t > 0 and -1e-9 <= u <= 1 + 1e-9:
                best = t if best is None else min(best, t)
        return tuple(d * best)
    return [hit(phi0)] + keep + [hit(phi1)]


def _orient(P):
    P = np.asarray(P, float)
    area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    return P if area > 0 else P[::-1]


def extrude_ring(name, poly, z0, z1, bevel=0.04, mats=None, side_index=None, parent=None, top_index=0, smooth=True):
    """多边形沿 Z 拉伸，上下带一小圈倒角。mats 是材质列表；side_index(i) 给第 i 条边的侧面选材质。"""
    P = _orient(poly)
    n = len(P)
    rows = [(_offset_poly(P, bevel), z0), (P, z0 + bevel), (P, z1 - bevel), (_offset_poly(P, bevel), z1)] if bevel > 0 else [(P, z0), (P, z1)]
    V = np.concatenate([np.column_stack([q, np.full(n, z)]) for q, z in rows])
    F = [tuple(n - 1 - j for j in range(n))]
    m = len(rows)
    idx = [top_index]
    for i in range(m - 1):
        for j in range(n):
            jn = (j + 1) % n
            F.append((i * n + j, i * n + jn, (i + 1) * n + jn, (i + 1) * n + j))
            idx.append(side_index(j, P) if side_index else 0)
    F.append(tuple((m - 1) * n + j for j in range(n)))
    idx.append(top_index)
    ob = make_mesh(name, V, F, None, parent, smooth=smooth)
    for mt in (mats or []):
        ob.data.materials.append(mt)
    if mats and len(mats) > 1:
        ob.data.polygons.foreach_set('material_index', np.array(idx, np.int32))
    ob.data.update()
    return ob


def tube_mesh(loops, radius, seg=6):
    """一批折线变成圆管，顶点数组。loops 里每个是 (N,3)，closed 标记放在元组第二项。"""
    Vs, Fs = [], []
    nv = 0
    th = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    cs, sn = np.cos(th), np.sin(th)
    for C, closed in loops:
        N = len(C)
        if closed:
            T = np.roll(C, -1, axis=0) - np.roll(C, 1, axis=0)
        else:
            T = np.gradient(C, axis=0)
        T = T / np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
        up = np.array([0.0, 0.0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        U = np.cross(T, np.cross(up, T))
        # 用稳定的参考：线圈的环都在一个平面内，法向不会翻
        ref = np.cross(T[0], T[len(T) // 3] + 1e-6)
        if np.linalg.norm(ref) < 1e-6:
            ref = np.cross(T[0], up)
        ref = ref / np.linalg.norm(ref)
        W = np.tile(ref, (N, 1))
        U = np.cross(W, T)
        U = U / np.maximum(np.linalg.norm(U, axis=1, keepdims=True), 1e-9)
        ring = C[:, None, :] + radius * (cs[None, :, None] * U[:, None, :] + sn[None, :, None] * W[:, None, :])
        Vs.append(ring.reshape(-1, 3))
        a = np.arange(seg)
        b = (a + 1) % seg
        M = N if closed else N - 1
        i0 = np.arange(M)
        i1 = (i0 + 1) % N
        q = np.stack([i0[:, None] * seg + a[None, :], i0[:, None] * seg + b[None, :], i1[:, None] * seg + b[None, :], i1[:, None] * seg + a[None, :]], axis=2)
        Fs.append((q.reshape(-1, 4) + nv).tolist())
        if not closed:
            Fs.append([tuple(nv + seg - 1 - j for j in range(seg)), tuple(nv + (N - 1) * seg + j for j in range(seg))])
        nv += N * seg
    V = np.concatenate(Vs)
    F = [tuple(f) for grp in Fs for f in grp]
    return V, F


def _line(p0, p1, step=1.2):
    """两点之间按 step 切，不含终点。"""
    n = max(1, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / step))
    return [(p0[0] + (p1[0] - p0[0]) * i / n, p0[1] + (p1[1] - p0[1]) * i / n) for i in range(n)]


def _rrect_side(W, zb, zt, Rc, half=None, nc=8):
    """线圈的一匝在 (u,z) 平面里的路径：圆角矩形。half=None 闭合；half=+1 或 -1 只留 u 的那一半（被切开），两头停在 u=0。"""
    pi = math.pi

    def corner(cu, cz, a0, a1, s=1.0):
        return [(s * (cu + Rc * math.cos(a)), cz + Rc * math.sin(a)) for a in np.linspace(a0, a1, nc)]
    if half is None:
        pts = []
        c1 = corner(W - Rc, zt - Rc, 0.0, pi / 2)
        c2 = corner(-W + Rc, zt - Rc, pi / 2, pi)
        c3 = corner(-W + Rc, zb + Rc, pi, 1.5 * pi)
        c4 = corner(W - Rc, zb + Rc, 1.5 * pi, 2 * pi)
        pts += c1 + _line(c1[-1], c2[0])[1:] + c2 + _line(c2[-1], c3[0])[1:] + c3 + _line(c3[-1], c4[0])[1:] + c4 + _line(c4[-1], c1[0])[1:]
        return pts, True
    s = float(half)
    # 从上面中线出发，经过这一侧，到下面中线
    c1 = corner(W - Rc, zt - Rc, pi / 2, 0.0, s)
    c4 = corner(W - Rc, zb + Rc, 2 * pi, 1.5 * pi, s)
    pts = _line((0.0, zt), c1[0], 0.6)
    pts += c1 + _line(c1[-1], c4[0])[1:] + c4 + _line(c4[-1], (0.0, zb), 0.6)[1:] + [(0.0, zb)]
    return pts, False


def coil_loops(alpha, half=None, d=0.40, seed=0):
    """绕在一个极臂上的线圈。alpha：极的方向（度）；half：切开时留 u 的哪一边。"""
    rng = np.random.default_rng(1000 + seed)
    ca, sa = math.cos(math.radians(alpha)), math.sin(math.radians(alpha))
    loops = []
    a0 = ARM_HALF + 0.30       # 第一层线离极臂中线（中间隔着骨架）
    ztop = Z_TOP + 0.42
    zbot = Z_STACK0 - 0.42
    pitch_v = d * 0.97
    n_rows = int((R_YOKE - 0.35 - 15.35) / pitch_v)
    for row in range(n_rows):
        v0 = 15.35 + (row + 0.5) * pitch_v
        # 这个半径上槽有多宽：极中线到槽中线的距离
        umax = v0 * math.tan(math.radians(22.5)) - 0.22
        n_lay = max(1, int((umax - a0) / (d * 0.97)))
        for lay in range(n_lay):
            off = (lay + 0.5) * d * 0.97
            if lay % 2:
                v = v0 + pitch_v * 0.5
            else:
                v = v0
            if v > R_YOKE - 0.3:
                continue
            W = a0 + off + rng.normal(0, 0.012)
            zt = ztop + off + rng.normal(0, 0.012)
            zb = zbot - off + rng.normal(0, 0.012)
            Rc = 0.55 + off * 0.9
            pts, closed = _rrect_side(W, zb, zt, Rc, half)
            pts = np.array(pts)
            # 线不是完全规矩的：沿线有一点很缓的起伏
            arc = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
            vv = v + rng.normal(0, 0.012) + 0.022 * np.sin(arc * 0.31 + rng.uniform(0, 6)) + 0.012 * np.sin(arc * 0.83 + rng.uniform(0, 6))
            C = np.column_stack([vv * ca - pts[:, 0] * sa, vv * sa + pts[:, 0] * ca, pts[:, 1]])
            loops.append((C, closed))
    return loops


class Motor:
    def __init__(self, parent=None, wedge=135.0, name='切开电机', shaft_flat=True, coil_d=0.34):
        self.wedge = wedge
        self.root = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(self.root)
        if parent is not None:
            self.root.parent = parent
        self._mats()
        self._stator(wedge)
        self._coils(wedge, coil_d)
        self._rear(wedge)
        self._rotor(shaft_flat)
        self._crown()
        self.set(0.0, 0.0)
        self.coil(0.0, 0.0)
        self.crown_light(0.0, 0.0)
        self.bead_light(0.0)
        self.show_shaft(False)
        self.show_long(False)

    def _mats(self):
        self.m_stack = lam('定子硅钢', base=0.36, rough=0.38)
        self.m_cut = lam('定子切面', base=0.62, rough=0.30, bump=0.02)
        self.m_wall = lam('定子外壁', base=0.13, rough=0.44, bump=0.05)
        self.m_top = face('定子顶面', base=0.085, rough=0.46, metal=0.7)
        self.m_rface = face('转子端面', base=0.34, rough=0.32)
        self.m_rotor = lam('转子硅钢', base=0.60, rough=0.28, bump=0.03)
        self.m_cu = copper()
        self.m_cap = studio.aluminium(name='电机端盖', rough=0.46, base=(0.30, 0.30, 0.31))
        self.m_black = studio.black_anodized(name='骨架', rough=0.5)

    def _stator(self, wedge):
        phi1 = wedge - 45.0            # 切面 1：φ=90（留下的在 φ 更小那边）
        phi0 = wedge + 45.0            # 切面 2：φ=180（留下的在 φ 更大那边）
        # 外框：从切面 2 逆时针绕到切面 1（走 270°）
        outer = _square_arc(A_SQ - 0.15, 4.2, phi0, phi1 + 360.0, r=0.3)
        # 内缘：φ 从 phi0 增加到 phi1+360，一路是极；在切面处从极中线开始和结束
        inner = []
        poles = [phi0 + 45.0 * k for k in range(7)]    # 7 个完整或半个极（首尾是半极）
        for k, a in enumerate(poles):
            pp = pole_profile(a)
            if k == 0 or k == 6:
                pp_np = np.array(pp)
                ang = (np.degrees(np.arctan2(pp_np[:, 1], pp_np[:, 0])) - a + 180.0) % 360.0 - 180.0
                if k == 0:
                    pp = [p for p, g in zip(pp, ang) if g > 0.01]
                    inner += [_pol(R_FACE, a)]
                    inner += pp
                else:
                    pp = [p for p, g in zip(pp, ang) if g < -0.01]
                    inner += pp
                    inner += [_pol(R_FACE, a)]
            else:
                inner += pp
        # 多边形：外框（逆时针）→ 切面 1 向内 → 内缘（反向）→ 切面 2 向外
        poly = outer + inner[::-1]
        P = np.array(poly)
        nout = len(outer)
        cut_edges = {nout - 1, len(poly) - 1}

        def side(j, Q):
            # 分类：外框 0，切面 1，内缘 2。_orient 没翻转时编号不变
            if j < nout - 1:
                return 0
            if j in cut_edges:
                return 1
            return 2
        ob = extrude_ring('定子', P, Z_STACK0, Z_TOP, bevel=0.035, mats=[self.m_wall, self.m_cut, self.m_stack, self.m_top], side_index=side, parent=self.root, top_index=3)
        self.stator = ob
        # 四角的螺孔（留下的三个角）
        for phi in (45.0, -45.0, -135.0):
            x, y = 15.5 * math.sqrt(2) * math.cos(math.radians(phi)), 15.5 * math.sqrt(2) * math.sin(math.radians(phi))
            if abs(((phi - wedge + 180) % 360) - 180) < 45:
                continue
            revolve('螺孔', [(1.6, Z_TOP + 0.004), (0.01, Z_TOP + 0.004)], seg=24, mat=studio.black_oxide(), parent=self.root, loc=(x, y, 0), close_bottom=False, close_top=False)

    def _coils(self, wedge, d):
        groups = {'A': [], 'B': []}
        bob = {'A': [], 'B': []}
        phi1, phi0 = wedge - 45.0, wedge + 45.0
        for k in range(8):
            a = k * 45.0
            g = 'A' if k % 2 == 0 else 'B'
            da = (a - wedge + 180.0) % 360.0 - 180.0
            if abs(da) < 44.9:
                continue                 # 这个极被切掉了
            half = None
            if abs(abs(da) - 45.0) < 0.1:
                # 切面穿过这个极的中线，留下离切开区远的那一半
                half = 1 if da > 0 else -1
            groups[g] += coil_loops(a, half=half, d=d, seed=k)
            self._bobbin(a, half)
        self.coils = {}
        for g, loops in groups.items():
            V, F = tube_mesh(loops, d * 0.49, seg=6)
            ob = make_mesh('线圈' + g, V, F, self.m_cu, self.root, smooth=True)
            self.coils[g] = ob

    def _bobbin(self, alpha, half):
        """线圈骨架：极臂上下的两片黑色塑料挡板，让铜线不直接贴铁。"""
        ca, sa = math.cos(math.radians(alpha)), math.sin(math.radians(alpha))
        t = 0.40
        for z0, z1 in ((Z_TOP, Z_TOP + t), (Z_STACK0 - t, Z_STACK0)):
            u0 = -ARM_HALF - 0.28 if half != 1 else 0.0
            u1 = ARM_HALF + 0.28 if half != -1 else 0.0
            quad = [(u0, 15.25), (u1, 15.25), (u1, R_YOKE - 0.3), (u0, R_YOKE - 0.3)]
            poly = [(v * ca - u * sa, v * sa + u * ca) for u, v in quad]
            extrude_ring('骨架', poly, z0, z1, bevel=0.05, mats=[self.m_black], parent=self.root)
        # 里外两道挡边
        hi = max(0.25, 2.8)
        for v0, v1, up in ((15.05, 15.3, 1.25), (R_YOKE - 0.35, R_YOKE - 0.12, 2.3)):
            for z0, z1 in ((Z_TOP, Z_TOP + up), (Z_STACK0 - up, Z_STACK0)):
                wid = ARM_HALF + 2.3 if v0 < 16 else ARM_HALF + 3.2
                u0 = -wid if half != 1 else 0.0
                u1 = wid if half != -1 else 0.0
                quad = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
                poly = [(v * ca - u * sa, v * sa + u * ca) for u, v in quad]
                extrude_ring('骨架挡边', poly, z0, z1, bevel=0.04, mats=[self.m_black], parent=self.root)

    def _rear(self, wedge):
        phi1, phi0 = wedge - 45.0, wedge + 45.0
        cap = self.m_cap
        # 后盖底板，整块
        extrude_ring('后盖底', square_outline(A_SQ, 2.2, 0.6), Z_BACK, Z_REAR_IN, bevel=0.45, mats=[cap], parent=self.root)
        # 后盖的四壁：C 形（切开的扇形这边也切掉）
        outer = _square_arc(A_SQ, 2.2, phi0, phi1 + 360.0, r=0.6)
        inner = _square_arc(A_SQ - 4.6, 3.6, phi0, phi1 + 360.0, r=1.2)
        extrude_ring('后盖壁', np.array(outer + inner[::-1]), Z_REAR_IN - 0.01, Z_STACK0 - 0.005, bevel=0.1, mats=[cap], parent=self.root)
        # 中间的轴承座和轴承
        revolve('轴承座', rounded([(0.01, Z_REAR_IN), (7.8, Z_REAR_IN), (7.8, Z_STACK0 - 0.5), (5.6, Z_STACK0 - 0.5), (5.6, Z_STACK0 - 1.6), (0.01, Z_STACK0 - 1.6)], [0, 0.3, 0.2, 0.1, 0, 0], 3),
                seg=96, mat=cap, parent=self.root, close_bottom=False)
        steel = studio.steel(name='轴承', rough=0.2)
        revolve('轴承', [(2.6, Z_STACK0 - 1.55), (5.55, Z_STACK0 - 1.55), (5.55, Z_STACK0 - 0.65), (2.6, Z_STACK0 - 0.65)], seg=64, mat=steel, parent=self.root, close_bottom=False, close_top=False)
        # 接插件
        machine.box('插座', -8, 8, -21.4, -15.5, Z_BACK, Z_BACK + 6.0, bevel=0.3, mat=studio.nylon_white(), parent=self.root)
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = sx * 15.5, sy * 15.5
                sc = machine.socket_screw('后螺钉', self.root, d=3.0, mat=studio.black_oxide())
                sc.location = (x, y, Z_BACK)
                sc.rotation_mode = 'XYZ'
                sc.rotation_euler = (math.pi, 0, 0)

    def _rotor(self, shaft_flat):
        self.rotor = bpy.data.objects.new('转子', None)
        bpy.context.scene.collection.objects.link(self.rotor)
        self.rotor.parent = self.root
        self.rotor.rotation_mode = 'XYZ'
        front = rotor_outline(PITCH / 2)
        rear = rotor_outline(0.0)        # 后段错开半个齿距
        def rs(j, Q):
            return 0
        extrude_ring('转子前段', front, Z_MAG1, Z_TOP, bevel=0.03, mats=[self.m_rotor, self.m_rface], side_index=rs, parent=self.rotor, top_index=1)
        extrude_ring('转子后段', rear, Z_STACK0, Z_MAG0, bevel=0.03, mats=[self.m_rotor], parent=self.rotor)
        # 磁铁：镀镍的环，比转子齿根细一点
        nickel = studio.steel(name='镀镍磁铁', rough=0.20)
        revolve('磁铁', rounded([(4.0, Z_MAG0), (10.9, Z_MAG0), (10.9, Z_MAG1), (4.0, Z_MAG1)], [0, 0.12, 0.12, 0], 3), seg=128, mat=nickel, parent=self.rotor, close_bottom=False, close_top=False)
        # 轴：整根和锯断的两种，按镜头切换。上段带一个削平面，转的时候看得出来
        steel = studio.steel(name='电机轴', rough=0.16)
        rows = rounded([(2.5, Z_STACK0 - 2.0), (2.5, Z_TOP + 1.5), (0.01, Z_TOP + 1.5)], [0, 0.12, 0], 2)
        self.shaft_stub = revolve('轴锯断', rows, seg=64, mat=steel, parent=self.rotor, close_bottom=False)
        rows = [(2.5, Z_STACK0 - 2.0), (2.5, Z_TOP + 7.4), (0.01, Z_TOP + 7.4)]
        s0 = revolve('轴下段', rows, seg=64, mat=steel, parent=self.rotor, close_bottom=False)
        th = np.linspace(0, 2 * math.pi, 96, endpoint=False)
        flat = 2.05
        R = 2.5
        P = np.column_stack([R * np.cos(th), R * np.sin(th)])
        if shaft_flat:
            P[:, 0] = np.minimum(P[:, 0], flat)
        s1 = extrude_ring('轴上段', P, Z_TOP + 7.4, Z_FACE + 15.2, bevel=0.22, mats=[steel], parent=self.rotor)
        self.shaft_full = [s0, s1]
        # 轴上的挡圈和转子端面的台阶
        self.washer = revolve('挡圈', rounded([(2.5, Z_TOP), (4.6, Z_TOP), (4.6, Z_TOP + 0.5), (2.5, Z_TOP + 0.5)], [0, 0.08, 0.08, 0], 2), seg=64, mat=studio.steel(name='垫圈', rough=0.28), parent=self.rotor, close_bottom=False, close_top=False)
        # 红色标记：一个涂红的齿，和端面上一道漆
        rd = paint()
        c = PITCH / 2 + K_FIRST * PITCH
        self.mark_phi = c
        # 只涂这个齿：齿顶面和两侧往下一小段。端面上那道长漆只在看得到整个转子的镜头里用
        tooth = [_pol(R_ROOT + 0.01, c - 2.03), _pol(R_TIP + 0.012, c - 1.53), _pol(R_TIP + 0.012, c), _pol(R_TIP + 0.012, c + 1.53), _pol(R_ROOT + 0.01, c + 2.03)]
        extrude_ring('红齿', tooth, Z_TOP - 1.3, Z_TOP + 0.008, bevel=0.0, mats=[rd], parent=self.rotor)
        ca, sa = math.cos(math.radians(c)), math.sin(math.radians(c))
        wd = 0.15
        stripe = [(r * ca - u * sa, r * sa + u * ca) for r, u in ((4.8, -wd), (R_ROOT + 0.02, -wd), (R_ROOT + 0.02, wd), (4.8, wd))]
        self.stripe_long = extrude_ring('红漆长', stripe, Z_TOP, Z_TOP + 0.008, bevel=0.0, mats=[rd], parent=self.rotor)
        # 红珠：势能曲线上的那个点
        rows = [(BEAD_R * math.sin(a) + 1e-3, BEAD_R * -math.cos(a)) for a in np.linspace(0, math.pi, 20)]
        self.bead = revolve('红珠', rows, seg=32, mat=bead_mat(), parent=self.rotor, close_bottom=False, close_top=False)
        self.bead.location = (CROWN_R * ca, CROWN_R * sa, bead_z(0.0))

    def _crown(self):
        n_phi = N_R * 28
        n_s = 10
        phi = np.linspace(0, 360.0, n_phi, endpoint=False)
        S = np.linspace(0, math.pi, n_s)
        # φ 相对波谷：波谷在 3.6° + k×7.2°
        Zc = crown_z(phi - PITCH / 2)
        V = np.empty((n_phi * n_s, 3))
        ang = np.empty(n_phi * n_s)
        hg = np.empty(n_phi * n_s)
        co, si = np.cos(np.radians(phi)), np.sin(np.radians(phi))
        for j, s in enumerate(S):
            r = CROWN_R + CROWN_RHO * math.cos(s)
            V[j * n_phi:(j + 1) * n_phi, 0] = r * co
            V[j * n_phi:(j + 1) * n_phi, 1] = r * si
            V[j * n_phi:(j + 1) * n_phi, 2] = Zc - CROWN_RHO * math.sin(s)
            # 扫过的起点从红齿的方向开始
            ang[j * n_phi:(j + 1) * n_phi] = ((phi - self.mark_phi) % 360.0) / 360.0
            hg[j * n_phi:(j + 1) * n_phi] = (Zc - CROWN_Z0) / (2 * CROWN_A)
        a = np.arange(n_phi)
        b = (a + 1) % n_phi
        F = []
        for j in range(n_s - 1):
            F.append(np.stack([j * n_phi + a, j * n_phi + b, (j + 1) * n_phi + b, (j + 1) * n_phi + a], axis=1))
        F = np.concatenate(F)
        self.crown = make_mesh('凹槽', V, F, crown_mat(), self.root, attrs=dict(ang=ang, hg=hg))
        self.crown.rotation_mode = 'XYZ'

    # ---------- 每帧 ----------
    def set(self, theta, theta_c):
        """theta：转子角（度），theta_c：凹槽角（度）。"""
        self.rotor.rotation_euler = (0, 0, math.radians(theta))
        self.crown.rotation_euler = (0, 0, math.radians(theta_c))
        self.bead.location.z = float(bead_z(theta - theta_c))

    def coil(self, a, b):
        self.coils['A'].color = (float(a), 0, 0, 1)
        self.coils['B'].color = (float(b), 0, 0, 1)
        self.coils['A'].update_tag(refresh={'OBJECT'})
        self.coils['B'].update_tag(refresh={'OBJECT'})

    def crown_light(self, level, sweep=1.0):
        self.crown.color = (float(level), float(sweep), 0, 1)
        self.crown.update_tag(refresh={'OBJECT'})
        self.crown.hide_render = level <= 1e-4

    def bead_light(self, level):
        self.bead.color = (float(level), 0, 0, 1)
        self.bead.update_tag(refresh={'OBJECT'})
        self.bead.hide_render = level <= 1e-4
        self.bead.scale = (max(level, 1e-3),) * 3

    def show_shaft(self, full):
        self.shaft_stub.hide_render = bool(full)
        for ob in self.shaft_full:
            ob.hide_render = not full

    def show_long(self, on):
        """看得到整个转子的镜头：端面上那道长漆、挡圈和轴都在。特写时这些都拿掉（下面要放曲线，糊的挡圈碍事）。"""
        self.stripe_long.hide_render = not on
        self.washer.hide_render = not on
        if not on:
            self.shaft_stub.hide_render = True
            for ob in self.shaft_full:
                ob.hide_render = True
