# Cabin and cold-gas system of the stunt car (car2), built to be taken apart in shot 3 (bullet time). Car-local frame as in car2.py:
# origin on the road at mid-wheelbase, +X forward, +Y left, +Z up.
# Layout (script v2, fact table): one driver's seat on the left; the 400 L tank lies in the passenger seat; the 200 L
# tank lies across the car behind the seats. Both are carbon-wrapped pressure vessels (COPV): a filament-wound cylinder
# with domed ends, a metal boss with the valve at one pole and a blind boss at the other, steel straps on rubber,
# cradles to the floor. Opaque they are gloss-black wound carbon (ref m044); in bullet time the whole composite wall turns
# clear (glassy, faint winding lines) so the packed molecules read from every side; bosses, straps and cradles stay
# solid (object property 'reveal' 0..1).
# Each tank valve is a machined block on the boss (solenoid on top, gauge on the end, bolted flanges); in bullet time
# its body turns clear and shows the bore, the ball and the molecules squeezing through it.
# Plumbing is illustrative (示意). The main line (400 L tank -> front-right lift nozzle, the pair firing at the freeze) is
# a 108 mm tube, oversized on purpose so the stream reads from the orbit camera; a reducer takes it down to a 51 mm
# line into the nozzle's own feed elbow. The 200 L tank feeds the rear-right lift nozzle through a 51 mm line. Both
# flow lines turn into clear tubes in bullet time (mesh attribute 'arc' 0..1 from the valve to the nozzle; object
# property 'reveal'). A thinner steel network feeds the other eight nozzles from a valve block behind the seat.
# Cabin: a racing seat in three parts (cushion, backrest, headrest on posts, each on its own carbon shell), a
# dashboard (cross-car beam, dash top with an instrument hood over the display, the yoke's column clamped to the beam).
# Hardware metals are satin (roughness >= 0.32): polished metal behind the bullet-time X-ray rendered as
# salt-and-pepper grain that the denoiser kept (review r3, f222).
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
import lib_rog as L
import car2 as C

# ---------------------------------------------------------------- layout
TANKS = {
    # outer radius, cylinder length, dome depth; the valve sits on the pole at -axis
    'big': dict(center=Vector((0.0, -0.36, 0.56)), axis=Vector((1, 0, 0)), up=Vector((0, 0, 1)),
                r=0.335, cyl=1.02, dome=0.21),
    'rear': dict(center=Vector((-1.26, 0.0, 0.53)), axis=Vector((0, 1, 0)), up=Vector((0, 0, 1)),
                 r=0.30, cyl=0.56, dome=0.185),
}
WALL = 0.020          # composite wall
LINER = 0.004         # (kept for other modules; the wall is modelled as one layer)
BOSS_R = 0.060
BLIND_R = 0.042
PIPE_R = 0.0255       # the 51 mm flow lines (the 200 L line, the last part of the main line)
PIPE_IN = 0.0215
PIPE_R_SMALL = 0.016  # the rest of the network
R_FAT = 0.054         # the main line: 108 mm clear tube (示意), ~20 px at 7 m from the orbit camera
R_FAT_IN = 0.049
BORE_IN = 0.026       # valve bore (the molecules pass in single file)
BEND_R = 0.15
FLOOR_Z = 0.20
Z_RUN = 0.42          # (older car) height of the runs along the sills, above the nozzle tops
Y_RUN = 0.78          # the side runs to the front lift nozzles: between the tank cradle/strap and the sill
Y_MAIN, Z_MAIN = -0.80, 0.42   # the main line's long run beside the 400 L tank (clear of its straps and of the sill)
X_RED = (0.54, 0.62)  # reducer 108 -> 51 mm before the nozzle
DUCT_CLEAR = 0.645    # lines to the rear lift nozzles come down just outboard of the fan ducts (|y| 0.604)
Z_OVER_DUCT = 0.475   # ... after crossing over them (duct top 0.444)
VALVES = {'big': dict(len=0.17, wy=0.15, hz=0.16), 'rear': dict(len=0.12, wy=0.11, hz=0.10)}
VALVE = VALVES['big']                     # (legacy name)
VALVE_SIDE = {'big': -1.0, 'rear': 1.0}   # flow outlet on the valve body's local -y (big: outboard) / +y (rear: rearward)
MANIFOLD = dict(center=Vector((-0.80, 0.10, 0.25)), size=Vector((0.12, 0.22, 0.09)))
REAR_BLOCK = dict(center=Vector((-1.80, 0.0, 0.64)), size=Vector((0.10, 0.20, 0.07)))
NOSE_BLOCK = dict(center=Vector((1.86, 0.0, 0.34)), size=Vector((0.08, 0.14, 0.06)))
FIREWALL = dict(x=0.975, z0=0.20, z1=0.42, hy=0.81)
FLOW_LINES = ('flow_big', 'flow_rear')
# legacy: angular cut-away wedges of the rejected version (no longer cut; kept so old callers still import)
CUT = {'big': (math.radians(136.0), math.radians(55.0)), 'rear': (math.radians(80.0), math.radians(55.0))}


def floor_top(x):
    """Height of the top of the car's floor surface at station x (the floor rises toward the tail)."""
    try:
        return float(L.pchip(C.KX, [p[1] for p in C.K_FLOOR], [x])[0]) + 0.009
    except Exception:
        return FLOOR_Z


def body_half_width(x, z0, z1):
    """Smallest half-width of the body's outer section at station x between heights z0 and z1."""
    try:
        half, _ = C.profile_at(x)
    except Exception:
        return 0.85
    ws = [float(p[0]) for p in half if z0 <= float(p[1]) <= z1]
    return min(ws) if ws else 0.85


def tank_frame(nm):
    """Matrix (car-local) of a tank: its local +x is the axis, +z its 'up'."""
    t = TANKS[nm]
    x = t['axis'].normalized()
    z = (t['up'] - x * t['up'].dot(x)).normalized()
    y = z.cross(x)
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = t['center']
    return M


def tank_profile(nm, inset=0.0, n_dome=18):
    """Outer (or inset) meridian of a tank in its local frame: list of (x, rho) from the valve pole to the blind pole."""
    t = TANKS[nm]
    r, h, d = t['r'], t['cyl'] / 2, t['dome']
    out = []
    t0 = math.acos(min(1.0, (BOSS_R + inset * 0.6) / r))
    for k in range(n_dome + 1):
        a = t0 * (1 - k / n_dome)
        out.append((-h - d * math.sin(a), r * math.cos(a)))
    for k in range(1, 8):
        out.append((-h + 2 * h * k / 8, r))
    t1 = math.acos(min(1.0, (BLIND_R + inset * 0.6) / r))
    for k in range(1, n_dome + 1):
        a = t1 * k / n_dome
        out.append((h + d * math.sin(a), r * math.cos(a)))
    if inset > 0:
        P = np.array(out)
        res = []
        for i in range(len(P)):
            a = P[max(i - 1, 0)]
            b = P[min(i + 1, len(P) - 1)]
            tg = b - a
            nrm = np.array([-tg[1], tg[0]])
            nrm /= np.linalg.norm(nrm) + 1e-12
            if nrm[1] < 0:
                nrm = -nrm
            res.append(tuple(P[i] - nrm * inset))
        out = res
    return out


def pole_x(nm):
    """Tank-local x of the valve pole (where the boss sits) and of the blind pole."""
    t = TANKS[nm]
    h, d = t['cyl'] / 2, t['dome']
    return -(h + d * math.sin(math.acos(BOSS_R / t['r']))), h + d * math.sin(math.acos(BLIND_R / t['r']))


def neck_point(nm):
    """Tank-local point just inside the valve boss where the gas leaves the tank (on the axis)."""
    xp, _ = pole_x(nm)
    return Vector((xp + 0.045, 0.0, 0.0))


def _valve_geom(nm):
    """Tank-local valve layout: (x at the boss face, x of the chamber centre, half width, half height, side)."""
    v = VALVES[nm]
    x_pole, _ = pole_x(nm)
    xv = x_pole - 0.034
    return xv, xv - v['len'] / 2, v['wy'] / 2, v['hz'] / 2, VALVE_SIDE[nm]


def _lathe_section(bm, prof_out, prof_in, a0, a1, seg, closed):
    """Solid shell of revolution about local +x between angles a0..a1 (radians, from +y toward +z).
    closed=True makes a full ring (a1 = a0 + 2 pi) without cut faces."""
    nseg = seg if closed else max(2, seg)
    na = nseg if closed else nseg + 1

    def ring(prof):
        R = []
        for (x, rho) in prof:
            row = []
            for k in range(na):
                a = a0 + (a1 - a0) * k / nseg
                row.append(bm.verts.new((x, rho * math.cos(a), rho * math.sin(a))))
            R.append(row)
        return R
    O = ring(prof_out)
    I = ring(prof_in)
    n = len(prof_out)
    span = range(nseg)
    for i in range(n - 1):
        for k in span:
            j = (k + 1) % na if closed else k + 1
            bm.faces.new((O[i][k], O[i + 1][k], O[i + 1][j], O[i][j]))
            bm.faces.new((I[i][k], I[i][j], I[i + 1][j], I[i + 1][k]))
    for i, flip in ((0, False), (n - 1, True)):
        for k in span:
            j = (k + 1) % na if closed else k + 1
            f = (O[i][k], O[i][j], I[i][j], I[i][k])
            bm.faces.new(f if not flip else f[::-1])
    if not closed:
        for k, flip in ((0, True), (na - 1, False)):
            for i in range(n - 1):
                f = (O[i][k], I[i][k], I[i + 1][k], O[i + 1][k])
                bm.faces.new(f if not flip else f[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def _autosmooth(ob, deg):
    try:
        ob.data.set_sharp_from_angle(angle=math.radians(deg))
    except Exception:
        pass


# ---------------------------------------------------------------- materials (owned here)

def _obj_attr(g, name):
    return g.n('ShaderNodeAttribute', attribute_type='OBJECT', attribute_name=name).outputs['Fac']


def _geo_attr(g, name):
    return g.n('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name=name).outputs['Fac']


def _line(g, t, width):
    """1 on thin lines at the integers of t, 0 between, with soft edges (width in units of the period)."""
    fr = g.math('FRACT', t)
    dist = g.math('SUBTRACT', 0.5, g.math('ABSOLUTE', g.math('SUBTRACT', fr, 0.5)))
    return g.maprange(dist, 0.0, width, 1.0, 0.0, interp='SMOOTHSTEP')


def _active_out(m):
    nt = m.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
    lk = out.inputs['Surface'].links
    return nt, out, (lk[0].from_socket if lk else None)


def clear_shell(g, tint=0.95, rough=0.07, rim=0.3, lines=None, line_amt=0.3, line_rgb=(0.50, 0.51, 0.53)):
    """Glass without refraction (no caustic paths, so no fireflies): transparent, fresnel-weighted gloss, a faint
    white rim so the form reads against the night sky, optional pale fibre lines."""
    tr = g.n('ShaderNodeBsdfTransparent', {'Color': (tint, tint, tint, 1)})
    sh = tr.outputs[0]
    if lines is not None:
        ln = L.principled(g, Base_Color=(*line_rgb, 1), Roughness=0.45)
        mx = g.n('ShaderNodeMixShader')
        g.link(g.math('MULTIPLY', lines, line_amt), mx.inputs['Fac'])
        g.link(sh, mx.inputs[1])
        g.link(ln.outputs[0], mx.inputs[2])
        sh = mx.outputs[0]
    lw = g.n('ShaderNodeLayerWeight', {'Blend': 0.12})
    gl = g.n('ShaderNodeBsdfGlossy', {'Color': (1, 1, 1, 1), 'Roughness': rough})
    mx = g.n('ShaderNodeMixShader')
    g.link(g.math('ADD', 0.03, g.math('MULTIPLY', lw.outputs['Fresnel'], 0.85)), mx.inputs['Fac'])
    g.link(sh, mx.inputs[1])
    g.link(gl.outputs[0], mx.inputs[2])
    sh = mx.outputs[0]
    if rim > 0:
        lw2 = g.n('ShaderNodeLayerWeight', {'Blend': 0.3})
        em = g.n('ShaderNodeEmission', {'Color': (0.90, 0.92, 0.95, 1)})
        g.link(g.math('MULTIPLY', g.math('POWER', lw2.outputs['Facing'], 3.0), rim), em.inputs['Strength'])
        add = g.n('ShaderNodeAddShader')
        g.link(sh, add.inputs[0])
        g.link(em.outputs[0], add.inputs[1])
        sh = add.outputs[0]
    return sh


def _simple_mat(name, rgb, rough=0.5, metal=0.0, coat=0.0, coat_rough=0.1, emit=None):
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m, g, out = L.new_material(name)
    kw = {}
    if emit is not None:
        kw = dict(Emission_Color=(*emit[0], 1), Emission_Strength=emit[1])
    p = L.principled(g, Base_Color=(*rgb, 1), Roughness=rough, Metallic=metal, Coat_Weight=coat,
                     Coat_Roughness=coat_rough, **kw)
    g.link(p, out.inputs['Surface'])
    return m


def hw_materials():
    """Machined hardware of the gas system: satin metals (see the header: no polished metal here)."""
    return dict(
        pipe=_simple_mat('INT_pipe', (0.72, 0.72, 0.74), 0.34, metal=1.0),
        alu=_simple_mat('INT_alu', (0.80, 0.80, 0.82), 0.38, metal=1.0),
        fitting=_simple_mat('INT_fitting', (0.78, 0.78, 0.80), 0.33, metal=1.0),
        steel=_simple_mat('INT_steel', (0.70, 0.70, 0.72), 0.36, metal=1.0),
        boss=_simple_mat('INT_boss', (0.74, 0.74, 0.76), 0.34, metal=1.0),
        black=_simple_mat('INT_black_anod', (0.030, 0.030, 0.034), 0.40, coat=0.35, coat_rough=0.25),
        bracket=_simple_mat('INT_bracket', (0.17, 0.17, 0.18), 0.45, metal=1.0),
        beam=_simple_mat('INT_beam', (0.56, 0.57, 0.59), 0.36, metal=1.0),
        strap=_simple_mat('INT_strap', (0.020, 0.020, 0.022), 0.55, coat=0.2, coat_rough=0.3),
        rubber=_simple_mat('INT_rubber', (0.012, 0.012, 0.013), 0.85),
        gauge=_simple_mat('INT_gauge_face', (0.85, 0.85, 0.83), 0.30),
    )


def _hw_copy(name, base):
    """A private copy of a hardware material (to have a clear-able version of it)."""
    m = bpy.data.materials.get(name)
    if m is not None:
        return m, True
    m = base.copy()
    m.name = name
    return m, False


def _carbon_wound(g):
    """Gloss-black filament-wound carbon (tank object space, +x on the axis; object properties 'tankr' and 'tow').
    Two helical tow families at +-TOW_DEG from the hoop direction cross in a diamond pattern; on each diamond the
    fibres of the family lying on top set the anisotropic sheen (tangent along the fibres) and a slightly different
    tone, so the highlight breaks into the winding pattern even from across the car. A clear resin coat on top gives
    the crisp mirror reflection of m044."""
    tc = g.n('ShaderNodeTexCoord')
    x, y, z = g.sep(tc.outputs['Object'])
    r = _obj_attr(g, 'tankr')
    tow = _obj_attr(g, 'tow')
    ang = g.math('ARCTAN2', z, y)
    arc = g.math('MULTIPLY', ang, r)
    a = math.radians(TOW_DEG)
    p1 = g.math('SUBTRACT', g.math('MULTIPLY', x, math.cos(a)), g.math('MULTIPLY', arc, math.sin(a)))
    p2 = g.math('ADD', g.math('MULTIPLY', x, math.cos(a)), g.math('MULTIPLY', arc, math.sin(a)))
    b1 = g.math('FLOOR', g.math('DIVIDE', p1, tow))
    b2 = g.math('FLOOR', g.math('DIVIDE', p2, tow))
    par = g.math('FLOORED_MODULO', g.math('ADD', b1, b2), 2.0)          # 0 / 1: which family is on top
    # tow edges: thin grooves along both families (bump) and a darker seam line
    e1 = _line(g, g.math('DIVIDE', p1, tow), 0.06)
    e2 = _line(g, g.math('DIVIDE', p2, tow), 0.06)
    edge = g.math('MAXIMUM', e1, e2)
    # fibre directions in world space: circumferential (radial tangent about x) mixed with the axis
    tg = g.n('ShaderNodeTangent', direction_type='RADIAL', axis='X')
    ax = g.n('ShaderNodeVectorTransform', vector_type='VECTOR', convert_from='OBJECT', convert_to='WORLD')
    ax.inputs['Vector'].default_value = (1.0, 0.0, 0.0)
    circ = tg.outputs['Tangent']
    axn = g.vmath('NORMALIZE', ax.outputs['Vector'])
    t1 = g.vmath('NORMALIZE', g.vmath('ADD', g.vmath('SCALE', circ, scale=math.cos(a)),
                                      g.vmath('SCALE', axn, scale=math.sin(a))))
    t2 = g.vmath('NORMALIZE', g.vmath('SUBTRACT', g.vmath('SCALE', circ, scale=math.cos(a)),
                                           g.vmath('SCALE', axn, scale=math.sin(a))))
    tmix = g.n('ShaderNodeMix', data_type='VECTOR')
    g.link(par, tmix.inputs['Factor'])
    g.link(t1, tmix.inputs[4])
    g.link(t2, tmix.inputs[5])
    nz = g.n('ShaderNodeTexNoise', {'Scale': 7.0, 'Detail': 2.0})
    g.link(tc.outputs['Object'], nz.inputs['Vector'])
    tone = g.math('MULTIPLY', g.math('ADD', 0.9, g.math('MULTIPLY', par, 0.2)),
                  g.maprange(nz.outputs['Fac'], 0.3, 0.7, 0.9, 1.1))
    tone = g.math('MULTIPLY', tone, g.math('SUBTRACT', 1.0, g.math('MULTIPLY', edge, 0.5)))
    col = g.mixrgb(tone, (0.0, 0.0, 0.0, 1), (0.016, 0.016, 0.018, 1))
    rough = g.maprange(par, 0.0, 1.0, 0.30, 0.36)
    bp = g.n('ShaderNodeBump', {'Strength': 0.15, 'Distance': 0.0005})
    g.link(g.math('SUBTRACT', 1.0, edge), bp.inputs['Height'])
    p = L.principled(g, Metallic=0.0, Specular_IOR_Level=0.32, Anisotropic=0.7, Coat_Weight=1.0,
                     Coat_Roughness=0.02, Coat_IOR=1.5)
    g.link(col, p.inputs['Base Color'])
    g.link(rough, p.inputs['Roughness'])
    g.link(bp.outputs['Normal'], p.inputs['Normal'])
    g.link(tmix.outputs[1], p.inputs['Tangent'])
    return p.outputs[0]


TOW_DEG = 22.0
TOW_W = 0.024         # nominal tow width (m); each tank rounds it to a whole, even number of tows round its girth


def tank_wall_material(mats):
    """Gloss-black wound carbon that turns into a clear glassy shell with faint winding lines. Object properties:
    'reveal' (0 opaque .. 1 clear; a soft front sweeps along the axis from the valve end to the blind end),
    'wipe0'/'wipe1' (object-space x of the two poles), 'cylhalf'/'tankr'/'tow' (pattern), 'help' (helical line
    period of the clear look)."""
    m = bpy.data.materials.get('INT_tank_wall')
    if m is not None:
        return m
    m, g, out = L.new_material('INT_tank_wall')
    src = _carbon_wound(g)
    tc = g.n('ShaderNodeTexCoord')
    x, y, z = g.sep(tc.outputs['Object'])
    w0, w1 = _obj_attr(g, 'wipe0'), _obj_attr(g, 'wipe1')
    w = g.math('DIVIDE', g.math('SUBTRACT', x, w0), g.math('SUBTRACT', w1, w0))
    rev = _obj_attr(g, 'reveal')
    band = 0.10
    front = g.math('SUBTRACT', g.math('MULTIPLY', rev, 1.0 + 2 * band), band)
    clear = g.maprange(w, g.math('SUBTRACT', front, band), g.math('ADD', front, band), 1.0, 0.0, interp='SMOOTHSTEP')
    r = _obj_attr(g, 'tankr')
    ch = _obj_attr(g, 'cylhalf')
    ang = g.math('ARCTAN2', z, y)
    arc = g.math('MULTIPLY', ang, r)
    hoop = _line(g, g.math('DIVIDE', x, 0.045), 0.05)
    a = math.radians(18)
    per = _obj_attr(g, 'help')
    u1 = g.math('ADD', g.math('MULTIPLY', x, math.cos(a)), g.math('MULTIPLY', arc, math.sin(a)))
    u2 = g.math('SUBTRACT', g.math('MULTIPLY', x, math.cos(a)), g.math('MULTIPLY', arc, math.sin(a)))
    hel = g.math('MAXIMUM', _line(g, g.math('DIVIDE', u1, per), 0.05), _line(g, g.math('DIVIDE', u2, per), 0.05))
    dome = g.maprange(g.math('ABSOLUTE', x), g.math('SUBTRACT', ch, 0.01), g.math('ADD', ch, 0.03), 0.0, 1.0)
    lines = g.n('ShaderNodeMix', data_type='FLOAT')
    g.link(dome, lines.inputs['Factor'])
    g.link(g.math('MAXIMUM', g.math('MULTIPLY', hoop, 0.35), g.math('MULTIPLY', hel, 0.6)), lines.inputs['A'])
    g.link(hel, lines.inputs['B'])
    sh = clear_shell(g, tint=0.95, rough=0.07, rim=0.22, lines=lines.outputs['Result'], line_amt=0.16,
                     line_rgb=(0.22, 0.22, 0.24))
    mix = g.n('ShaderNodeMixShader')
    g.link(clear, mix.inputs['Fac'])
    g.link(src, mix.inputs[1])
    g.link(sh, mix.inputs[2])
    # the clearing front: a thin soft glow while it travels
    glow = g.maprange(g.math('ABSOLUTE', g.math('SUBTRACT', w, front)), 0.0, band * 0.6, 1.0, 0.0, interp='SMOOTHSTEP')
    em = g.n('ShaderNodeEmission', {'Color': (0.92, 0.94, 0.97, 1)})
    g.link(g.math('MULTIPLY', glow, g.math('MULTIPLY', 0.35, g.math('MINIMUM', g.math('MULTIPLY', rev, 20.0), 1.0))),
           em.inputs['Strength'])
    add = g.n('ShaderNodeAddShader')
    g.link(mix.outputs[0], add.inputs[0])
    g.link(em.outputs[0], add.inputs[1])
    g.link(add.outputs[0], out.inputs['Surface'])
    return m


def _clearable(m, rim=0.30, tint=0.96, rough=0.05, attr='reveal', arc_front=False):
    """Mix a clear shell into material m, driven by the object property `attr` (or, with arc_front, by a front that
    sweeps along the mesh attribute 'arc')."""
    nt, out, src = _active_out(m)
    g = L.G(nt)
    rev = _obj_attr(g, attr)
    if arc_front:
        arc = _geo_attr(g, 'arc')
        band = 0.08
        front = g.math('SUBTRACT', g.math('MULTIPLY', rev, 1.0 + 2 * band), band)
        fac = g.maprange(arc, g.math('SUBTRACT', front, band), g.math('ADD', front, band), 1.0, 0.0, interp='SMOOTHSTEP')
    else:
        fac = g.maprange(rev, 0.0, 1.0, 0.0, 1.0, interp='SMOOTHSTEP')
    sh = clear_shell(g, tint=tint, rough=rough, rim=rim)
    mix = g.n('ShaderNodeMixShader')
    g.link(fac, mix.inputs['Fac'])
    if src is not None:
        g.link(src, mix.inputs[1])
    g.link(sh, mix.inputs[2])
    g.link(mix.outputs[0], out.inputs['Surface'])
    return m


def pipe_flow_material(mats):
    """Satin steel tube that turns into a clear glass tube from the valve end to the nozzle end (mesh attribute 'arc'
    0..1, object property 'reveal' 0..1 moves the front)."""
    m, done = _hw_copy('INT_flowpipe', hw_materials()['pipe'])
    if done:
        return m
    return _clearable(m, rim=0.42, tint=0.97, rough=0.05, arc_front=True)


def valve_material(mats):
    """Machined (satin) valve body that turns clear (object property 'reveal') so the molecules show passing through."""
    m, done = _hw_copy('INT_valve', hw_materials()['alu'])
    if done:
        return m
    return _clearable(m, rim=0.55, tint=0.96, rough=0.05)


def bore_material():
    """The valve's inner passage: always a clear tube with a bright rim (only seen once the body is clear)."""
    m = bpy.data.materials.get('INT_bore')
    if m is not None:
        return m
    m, g, out = L.new_material('INT_bore')
    g.link(clear_shell(g, tint=0.97, rough=0.05, rim=0.5), out.inputs['Surface'])
    return m


def interior_materials():
    return dict(
        seat_pad=_simple_mat('INT_seat_pad', (0.56, 0.555, 0.54), 0.55),
        seat_insert=_simple_mat('INT_seat_insert', (0.40, 0.395, 0.385), 0.62),
        seat_shell=_simple_mat('INT_seat_shell', (0.030, 0.030, 0.033), 0.32, coat=0.8, coat_rough=0.06),
        harness=_simple_mat('INT_harness', (0.035, 0.035, 0.04), 0.75),
        buckle=_simple_mat('INT_buckle', (0.78, 0.78, 0.80), 0.30, metal=1.0),
        dash=_simple_mat('INT_dash', (0.135, 0.135, 0.145), 0.62, coat=0.15, coat_rough=0.35),
        vent=_simple_mat('INT_vent', (0.010, 0.010, 0.011), 0.55),
        yoke=_simple_mat('INT_yoke', (0.022, 0.022, 0.024), 0.6, coat=0.25, coat_rough=0.3),
        trim=_simple_mat('INT_trim', (0.62, 0.62, 0.64), 0.32, metal=1.0),
        screen=display_material(),
        bezel=_simple_mat('INT_bezel', (0.012, 0.012, 0.014), 0.35, coat=0.6, coat_rough=0.08),
    )


def display_material(name='INT_display', dial_z=0.762):
    """A lit instrument face (object coordinates = car space): a deep blue field, pale ring dials and bar gauges, under
    a glossy black glass, so a display reads as a display through the gold glass and in bullet time."""
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m, g, out = L.new_material(name)
    tc = g.n('ShaderNodeTexCoord')
    x, y, z = g.sep(tc.outputs['Object'])
    # ring dials: one per display, centred by a periodic pattern across the car (every 0.13 m) at mid-height
    yy = g.math('SUBTRACT', g.math('FRACT', g.math('DIVIDE', y, 0.13)), 0.5)
    yy = g.math('MULTIPLY', yy, 0.13)
    zz = g.math('SUBTRACT', z, g.value(dial_z, 'dial_z'))
    r = g.math('SQRT', g.math('ADD', g.math('MULTIPLY', yy, yy), g.math('MULTIPLY', zz, zz)))
    ring = g.math('SUBTRACT', 1.0, g.maprange(g.math('ABSOLUTE', g.math('SUBTRACT', r, 0.026)), 0.0015, 0.0035,
                                              0.0, 1.0))
    bars = g.math('MULTIPLY', g.maprange(g.math('SINE', g.math('MULTIPLY', z, 260.0)), 0.55, 0.75, 0.0, 1.0),
                  g.maprange(g.math('ABSOLUTE', yy), 0.040, 0.044, 0.0, 1.0))
    lit = g.math('MINIMUM', g.math('ADD', ring, g.math('MULTIPLY', bars, 0.6)), 1.0)
    col = g.mixrgb(lit, (0.035, 0.10, 0.24, 1.0), (0.70, 0.86, 1.0, 1.0))
    p = L.principled(g, Base_Color=(0.004, 0.004, 0.005, 1), Roughness=0.06, Coat_Weight=1.0, Coat_Roughness=0.02,
                     Emission_Strength=1.6)
    g.link(col, p.inputs['Emission Color'])
    g.link(p, out.inputs['Surface'])
    return m


# ---------------------------------------------------------------- tanks

def build_tank(col, mats, nm):
    """Returns dict: shell (the whole composite wall: one closed solid, origin at the tank centre, local +x on the
    axis), wedge (legacy empty stand-in), boss, valve_body, valve_bore, valve_ball, solenoid, gauge, bolts, straps,
    strap_liner, saddles."""
    hw = hw_materials()
    t = TANKS[nm]
    M = tank_frame(nm)
    objs = {}
    prof_o = tank_profile(nm)
    prof_i = tank_profile(nm, inset=WALL)
    bm = bmesh.new()
    _lathe_section(bm, prof_o, prof_i, 0.0, 2 * math.pi, 128, closed=True)
    ob = L.bm_obj(f'RS2_tank_{nm}', bm, col, smooth=True, mat=tank_wall_material(mats))
    ob.matrix_world = M
    ob['cylhalf'] = t['cyl'] / 2
    ob['tankr'] = t['r']
    ob['wipe0'] = float(prof_o[0][0])
    ob['wipe1'] = float(prof_o[-1][0])
    circ = 2 * math.pi * t['r'] * math.sin(math.radians(18))
    ob['help'] = circ / max(1, round(circ / 0.065))          # whole number of helical lines round the tank: no seam
    girth = 2 * math.pi * t['r'] * math.sin(math.radians(TOW_DEG))
    n_tow = max(2, 2 * round(girth / TOW_W / 2))             # even: the diamond checker closes round the girth
    ob['tow'] = girth / n_tow
    ob['reveal'] = 0.0
    _autosmooth(ob, 30)
    objs['shell'] = ob
    me = bpy.data.meshes.new(f'RS2_tankwedge_{nm}')
    wob = bpy.data.objects.new(f'RS2_tankwedge_{nm}', me)
    col.objects.link(wob)
    wob.matrix_world = M
    wob.hide_render = True
    objs['wedge'] = wob
    # polar boss and blind boss
    x_pole, x_b = pole_x(nm)
    bm = bmesh.new()
    L.bm_lathe(bm, [(0.0, x_pole + 0.03), (BOSS_R + 0.022, x_pole + 0.03), (BOSS_R + 0.022, x_pole + 0.012),
                    (BOSS_R, x_pole + 0.006), (BOSS_R, x_pole - 0.028), (BOSS_R - 0.006, x_pole - 0.034),
                    (0.034, x_pole - 0.034), (0.0, x_pole - 0.034)], (0, 0, 0), (1, 0, 0), seg=48)
    L.bm_lathe(bm, [(0.0, x_b - 0.02), (BLIND_R + 0.016, x_b - 0.02), (BLIND_R + 0.016, x_b - 0.006),
                    (BLIND_R, x_b), (BLIND_R, x_b + 0.016), (BLIND_R - 0.006, x_b + 0.022), (0.0, x_b + 0.022)],
               (0, 0, 0), (1, 0, 0), seg=40)
    bo = L.bm_obj(f'RS2_boss_{nm}', bm, col, smooth=True, mat=hw['boss'])
    bo.matrix_world = M
    _autosmooth(bo, 35)
    objs['boss'] = bo
    objs.update(build_valve(col, nm, M))
    # straps on rubber, saddles to the floor
    xs = (-0.30 * t['cyl'], 0.30 * t['cyl'])
    bm_s, bm_r = bmesh.new(), bmesh.new()
    for xx in xs:
        L.bm_lathe(bm_r, [(t['r'] + 0.0005, xx - 0.024), (t['r'] + 0.005, xx - 0.022), (t['r'] + 0.005, xx + 0.022),
                          (t['r'] + 0.0005, xx + 0.024)], (0, 0, 0), (1, 0, 0), seg=96)
        L.bm_lathe(bm_s, [(t['r'] + 0.0045, xx - 0.021), (t['r'] + 0.0095, xx - 0.020), (t['r'] + 0.0095, xx + 0.020),
                          (t['r'] + 0.0045, xx + 0.021)], (0, 0, 0), (1, 0, 0), seg=96)
        for s in (1, -1):
            L.bm_box(bm_s, (xx, s * (t['r'] + 0.022), -0.02), (0.040, 0.030, 0.050))
    st = L.bm_obj(f'RS2_straps_{nm}', bm_s, col, smooth=True, mat=hw['strap'])
    rb = L.bm_obj(f'RS2_strapliner_{nm}', bm_r, col, smooth=True, mat=hw['rubber'])
    for o in (st, rb):
        o.matrix_world = M
        _autosmooth(o, 40)
    objs['straps'] = st
    objs['strap_liner'] = rb
    bm = bmesh.new()
    zc = t['center'].z
    for xx in xs:
        a0, a1 = math.radians(205), math.radians(335)
        n = 20
        rin, rout = t['r'] + 0.0098, t['r'] + 0.022
        verts_in, verts_out = [], []
        for k in range(n + 1):
            a = a0 + (a1 - a0) * k / n
            verts_in.append((rin * math.cos(a), rin * math.sin(a)))
            verts_out.append((rout * math.cos(a), rout * math.sin(a)))
        vi0 = [bm.verts.new((xx - 0.022, yy, zz)) for (yy, zz) in verts_in]
        vi1 = [bm.verts.new((xx + 0.022, yy, zz)) for (yy, zz) in verts_in]
        vo0 = [bm.verts.new((xx - 0.022, yy, zz)) for (yy, zz) in verts_out]
        vo1 = [bm.verts.new((xx + 0.022, yy, zz)) for (yy, zz) in verts_out]
        for k in range(n):
            bm.faces.new((vi0[k], vi1[k], vi1[k + 1], vi0[k + 1]))
            bm.faces.new((vo0[k + 1], vo1[k + 1], vo1[k], vo0[k]))
            bm.faces.new((vi0[k + 1], vo0[k + 1], vo0[k], vi0[k]))
            bm.faces.new((vi1[k], vo1[k], vo1[k + 1], vi1[k + 1]))
        for k in (0, n):
            f = (vi0[k], vo0[k], vo1[k], vi1[k])
            bm.faces.new(f if k == n else f[::-1])
        for k in (0, n):
            yy, zz = verts_out[k]
            ym = 0.5 * (yy + verts_in[k][0])
            car_x = (M @ Vector((xx, ym, 0.0))).x
            zf = floor_top(car_x) - zc            # foot on the floor at this station
            L.bm_box(bm, (xx, ym, 0.5 * (zz + zf + 0.008)), (0.044, 0.026, max(zz - zf - 0.008, 0.01)))
            L.bm_box(bm, (xx, ym, zf + 0.004), (0.07, 0.07, 0.008))
    sd = L.bm_obj(f'RS2_cradles_{nm}', bm, col, mat=hw['bracket'])
    sd.matrix_world = M
    _autosmooth(sd, 30)
    objs['saddles'] = sd
    return objs


def _box_chamfer(bm, c, size, ch):
    """Box with chamfered edges and corners (an octagon-section prism capped by chamfered faces)."""
    sx, sy, sz = [s * 0.5 for s in size]
    pts = []
    for X in (-1, 1):
        for Y in (-1, 1):
            for Z in (-1, 1):
                for (dx, dy, dz) in ((ch, 0, 0), (0, ch, 0), (0, 0, ch)):
                    pts.append(Vector((c[0] + X * (sx - dx), c[1] + Y * (sy - dy), c[2] + Z * (sz - dz))))
    # convex hull of the 24 points gives the chamfered box
    vs = [bm.verts.new(p) for p in pts]
    res = bmesh.ops.convex_hull(bm, input=vs)
    inner = [v for v in res.get('geom_interior', []) if isinstance(v, bmesh.types.BMVert)]
    if inner:
        bmesh.ops.delete(bm, geom=inner, context='VERTS')
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def build_valve(col, nm, M):
    """Valve on the tank boss (tank-local frame M): machined block with a bore from the boss to a ball in the middle,
    the flow port on one side face (the 400 L valve also feeds the valve block on the other), the solenoid actuator on
    top, a gauge and a hand knob on the end face, flange and cap bolts. The body turns clear in bullet time
    ('reveal'); the bore and the ball are then seen inside it, with the molecules passing through."""
    hw = hw_materials()
    xv, xc, hwy, hhz, side = _valve_geom(nm)
    v = VALVES[nm]
    vl = v['len']
    objs = {}
    bm = bmesh.new()
    _box_chamfer(bm, (xc, 0.0, 0.0), (vl, 2 * hwy, 2 * hhz), min(0.016, 0.12 * vl))
    vb = L.bm_obj(f'RS2_valvebody_{nm}', bm, col, mat=valve_material(None))
    vb.matrix_world = M
    vb['reveal'] = 0.0
    objs['valve_body'] = vb
    # the inner passage (clear) and the ball with its seats (solid)
    bm = bmesh.new()
    path = fillet_route([Vector((xv + 0.004, 0, 0)), Vector((xc, 0, 0)), Vector((xc, side * (hwy - 0.004), 0))],
                        rb=0.035, step=0.006, arc_deg=6.0)
    _tube_arc(bm, path, BORE_IN + 0.002, seg=24, caps=False)
    bo = L.bm_obj(f'RS2_valvebore_{nm}', bm, col, smooth=True, mat=bore_material())
    bo.matrix_world = M
    objs['valve_bore'] = bo
    bm = bmesh.new()
    rb_ = BORE_IN + 0.004
    # ball (400 L valve): a sphere with a through bore, turned open (its bore along the flow), on its stem
    xb = xc + 0.057 if nm == 'big' else xc + 0.03
    if nm == 'big':
        hl, ro = 0.017, rb_ + 0.016
        prof = [(rb_, -hl)]
        for k in range(1, 8):
            a = -math.asin(hl / ro) + 2 * math.asin(hl / ro) * k / 8
            prof.append((ro * math.cos(a), ro * math.sin(a)))
        prof.append((rb_, hl))
        L.bm_lathe(bm, prof, (xb, 0, 0), (1, 0, 0), seg=40)
        L.bm_lathe(bm, [(rb_, hl), (rb_, -hl)], (xb, 0, 0), (1, 0, 0), seg=40)
        L.bm_tube_along(bm, [Vector((xb, 0, ro - 0.004)), Vector((xb, 0, hhz))], 0.007, seg=12)
    else:
        L.bm_tube_along(bm, [Vector((xb, 0, BORE_IN + 0.004)), Vector((xb, 0, hhz))], 0.006, seg=12)
    ball = L.bm_obj(f'RS2_valveball_{nm}', bm, col, smooth=True, mat=hw['steel'])
    ball.matrix_world = M
    _autosmooth(ball, 40)
    objs['valve_ball'] = ball
    # actuator on top: hex bonnet, solenoid coil, cap
    bm = bmesh.new()
    top = Vector((xb, 0.0, hhz))
    L.bm_lathe(bm, [(0.026, 0.0), (0.026, 0.016)], top, (0, 0, 1), seg=6, close_start=True, close_end=True)
    L.bm_lathe(bm, [(0.0, 0.016), (0.034, 0.016), (0.036, 0.020), (0.036, 0.074), (0.032, 0.080), (0.016, 0.082),
                    (0.016, 0.094), (0.0, 0.094)], top, (0, 0, 1), seg=40)
    so = L.bm_obj(f'RS2_solenoid_{nm}', bm, col, smooth=True, mat=hw['black'])
    so.matrix_world = M
    _autosmooth(so, 35)
    objs['solenoid'] = so
    # gauge (dial facing out of the end face) and hand knob
    bm = bmesh.new()
    xe = xv - vl
    g0 = Vector((xe, 0.0, 0.25 * hhz))
    L.bm_lathe(bm, [(0.0, 0.0), (0.008, 0.0), (0.008, 0.010), (0.030, 0.012), (0.030, 0.030), (0.024, 0.032),
                    (0.0, 0.032)], g0, (-1, 0, 0), seg=32)
    k0 = Vector((xe, 0.0, -0.45 * hhz))
    L.bm_lathe(bm, [(0.0, 0.0), (0.007, 0.0), (0.007, 0.010), (0.018, 0.011), (0.018, 0.022), (0.0, 0.024)],
               k0, (-1, 0, 0), seg=24)
    # cap bolts on the top face and flange bolts round the boss
    for dx in (-0.36 * vl, 0.36 * vl):
        for dy in (-0.7 * hwy, 0.7 * hwy):
            L.bm_lathe(bm, [(0.0, 0.0), (0.008, 0.0), (0.008, 0.006), (0.0, 0.007)], Vector((xc + dx, dy, hhz)),
                       (0, 0, 1), seg=6)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        p = Vector((xv - 0.006, 0.055 * math.cos(a), 0.055 * math.sin(a)))
        if abs(p.y) < hwy - 0.008 and abs(p.z) < hhz - 0.008:
            L.bm_lathe(bm, [(0.0, 0.0), (0.007, 0.0), (0.007, 0.006), (0.0, 0.007)], p + Vector((-0.0, 0, 0)),
                       (-1, 0, 0), seg=6)
    ga = L.bm_obj(f'RS2_gauge_{nm}', bm, col, smooth=True, mat=hw['steel'])
    ga.matrix_world = M
    _autosmooth(ga, 40)
    objs['gauge'] = ga
    return objs


# ---------------------------------------------------------------- the driver's seat: cushion, backrest, headrest
# Three upholstered parts, each on its own dark carbon shell (ref m048.0: light grey upholstery): a cushion with side
# bolsters on a pan, a reclined backrest with deep bolsters, a separate headrest on two posts above it; a four-point
# harness and a buckle; rails and a pedestal on the floor.
SEAT_Y = 0.36
SEAT_FRONT = np.array([0.17, 0.375])
SEAT_CREASE = np.array([-0.30, 0.315])
SEAT_RECLINE = math.radians(22.0)
SEAT_BACK_LEN = 0.70
CUSH_END = 0.86          # the cushion pad ends short of the crease: a visible gap to the backrest
_CUSH = dict(t=[0.0, 0.5, 1.0], W=[0.235, 0.248, 0.252], B=[0.045, 0.070, 0.085], bw=[0.080, 0.085, 0.090],
             D=[0.010, 0.012, 0.012], T=[0.085, 0.092, 0.092])
BACK_S = (0.045, 0.50)   # backrest pad, along the back axis (m from the crease)
HEAD_S = (0.555, 0.705)  # headrest pad
_BACK = dict(t=[0.0, 0.35, 0.70, 1.0], W=[0.250, 0.262, 0.252, 0.222], B=[0.095, 0.125, 0.110, 0.055],
             bw=[0.090, 0.100, 0.100, 0.080], D=[0.012, 0.015, 0.012, 0.008], T=[0.070, 0.070, 0.066, 0.062])
_HEAD = dict(W=0.135, T=0.075, B=0.012, bw=0.05, D=0.0)


def _seat_axes():
    d = SEAT_CREASE - SEAT_FRONT
    d = d / np.linalg.norm(d)
    n_c = np.array([d[1], -d[0]])                 # cushion normal (up, toward the occupant)
    if n_c[1] < 0:
        n_c = -n_c
    up = np.array([-math.sin(SEAT_RECLINE), math.cos(SEAT_RECLINE)])
    n_b = np.array([math.cos(SEAT_RECLINE), math.sin(SEAT_RECLINE)])   # backrest normal (forward)
    c_end = SEAT_FRONT + (SEAT_CREASE - SEAT_FRONT) * CUSH_END
    b0 = SEAT_CREASE - up * 0.03
    return d, n_c, up, n_b, c_end, b0


def _seat_params(keys, t):
    xs = keys['t']
    tt = min(max(t, 0.0), 1.0)
    return {k: float(L.pchip(xs, keys[k], [tt])[0]) for k in ('W', 'B', 'bw', 'D', 'T')}


def _top_v(u, p):
    """Height of the upholstered (occupant-side) surface above the seat's reference line at lateral offset u."""
    W, B, bw, D = p['W'], p['B'], p['bw'], p['D']
    a = abs(u)
    flat = max(W - bw, 1e-4)
    if a <= flat:
        return -D * (1 - (a / flat) ** 2)
    t = min((a - flat) / bw, 1.0)
    s = t * t * (3 - 2 * t)
    return B * s ** 0.85


def _pad_loop(p):
    """Closed cross-section of a pad (u lateral, v toward the occupant): flat back at v = -T, rounded sides, raised
    bolsters, a slightly dished centre. Returns (points, flags: 1 for points on the centre insert)."""
    W, B, bw, T = p['W'], p['B'], p['bw'], p['T']
    flat = W - bw
    r = min(0.022, 0.3 * T)
    top_us = [W - 0.06 * bw, W - 0.25 * bw, W - 0.5 * bw, W - 0.75 * bw, flat, 0.62 * flat, 0.25 * flat]
    right = [(0.25 * W, -T), (0.6 * W, -T), (W - r, -T), (W - 0.3 * r, -T + 0.3 * r), (W, -T + r),
             (W + 0.004, 0.25 * (B - T)), (W + 0.002, 0.65 * B - 0.004)]
    right += [(u, _top_v(u, p)) for u in top_us]
    loop = [(0.0, -T)] + right + [(0.0, _top_v(0.0, p))] + [(-u, v) for (u, v) in reversed(right)]
    flags = [0] + [0] * len(right) + [1] + [0] * len(right)
    # centre insert: the dished top between the bolsters
    for i, (u, v) in enumerate(loop):
        if v > -0.5 * T and abs(u) <= flat + 1e-6:
            flags[i] = 1
    return loop, flags


def _pad(bm, frames, params, mat_pad=0, mat_insert=1, cap=0.012):
    """Loft a pad along a list of frames (P (2d x-z), N (2d normal), T (2d tangent)) with per-frame params."""
    rings, flags = [], None
    for (P, N, Tg), p in zip(frames, params):
        loop, fl = _pad_loop(p)
        flags = fl
        rings.append([bm.verts.new((P[0] + N[0] * v, SEAT_Y + u, P[1] + N[1] * v)) for (u, v) in loop])
    m = len(rings[0])
    for i in range(len(rings) - 1):
        for k in range(m):
            j = (k + 1) % m
            f = bm.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
            f.material_index = mat_insert if (flags[k] and flags[j]) else mat_pad
    for i, sgn in ((0, -1.0), (len(rings) - 1, 1.0)):
        ring = rings[i]
        c = sum((v.co for v in ring), Vector()) / m
        Tg = frames[i][2]
        cv = bm.verts.new(c + Vector((Tg[0], 0.0, Tg[1])) * sgn * cap)
        for k in range(m):
            j = (k + 1) % m
            f = bm.faces.new((ring[k], ring[j], cv))
            f.material_index = mat_pad


def _shell_loop(p, wrap, th):
    """Open U section of a seat shell behind a pad: from one side's bolster (height `wrap` of the side) round the back
    to the other, thickness th outward."""
    W, B, T = p['W'], p['B'], p['T']
    r = min(0.024, 0.3 * T)
    v_top = -T + wrap * (T + 0.6 * B)
    inner = [(W + 0.002, v_top), (W + 0.002, -T + r), (W - 0.3 * r, -T + 0.3 * r - 0.002), (W - r, -T - 0.002),
             (0.5 * W, -T - 0.002), (0.0, -T - 0.002)]
    inner = inner + [(-u, v) for (u, v) in reversed(inner[:-1])]
    outer = []
    for i, (u, v) in enumerate(inner):
        a = inner[max(i - 1, 0)]
        b = inner[min(i + 1, len(inner) - 1)]
        tu, tv = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tu, tv) + 1e-9
        nu, nv = -tv / ln, tu / ln                 # outward (away from the pad) for this winding
        outer.append((u + nu * th, v + nv * th))
    return inner, outer


def _shell(bm, frames, params, wrap=0.75, th=0.012):
    rings = []
    for (P, N, Tg), p in zip(frames, params):
        inner, outer = _shell_loop(p, wrap, th)
        loop = inner + list(reversed(outer))
        rings.append([bm.verts.new((P[0] + N[0] * v, SEAT_Y + u, P[1] + N[1] * v)) for (u, v) in loop])
    m = len(rings[0])
    for i in range(len(rings) - 1):
        for k in range(m):
            j = (k + 1) % m
            bm.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
    n2 = m // 2
    for i in (0, len(rings) - 1):
        r = rings[i]
        for k in range(n2 - 1):
            f = (r[k], r[k + 1], r[m - 2 - k], r[m - 1 - k])
            bm.faces.new(f if i else f[::-1])


def _cush_frames(n):
    d, n_c, up, n_b, c_end, b0 = _seat_axes()
    fr, ps = [], []
    for i in range(n):
        t = i / (n - 1)
        fr.append((SEAT_FRONT + (c_end - SEAT_FRONT) * t, n_c, d))
        ps.append(_seat_params(_CUSH, t))
    return fr, ps


def _back_frames(n, s0, s1, keys=None, head=False):
    d, n_c, up, n_b, c_end, b0 = _seat_axes()
    fr, ps = [], []
    for i in range(n):
        s = s0 + (s1 - s0) * i / (n - 1)
        fr.append((b0 + up * s, n_b, up))
        if head:
            p = dict(_HEAD)
            # rounded top and bottom of the headrest: the section narrows and thins near both ends
            e = abs(2 * i / (n - 1) - 1)
            k = math.sqrt(max(1 - e ** 4, 0.0))
            p['W'] = _HEAD['W'] * (0.72 + 0.28 * k)
            p['T'] = _HEAD['T'] * (0.70 + 0.30 * k)
            p['B'] = _HEAD['B'] * k
            ps.append(p)
        else:
            ps.append(_seat_params(_BACK, (s - BACK_S[0]) / (BACK_S[1] - BACK_S[0])))
    return fr, ps


def seat_surface(part, t, u, lift=0.0):
    """Point and normal on the upholstered (occupant) surface: part 'cushion' (t 0 front .. 1 rear) or 'back'
    (t 0 bottom .. 1 top of the backrest pad), u lateral offset from the seat centre line."""
    d, n_c, up, n_b, c_end, b0 = _seat_axes()
    if part == 'back':
        p = _seat_params(_BACK, t)
        P = b0 + up * (BACK_S[0] + (BACK_S[1] - BACK_S[0]) * t)
        N = n_b
    else:
        p = _seat_params(_CUSH, t)
        P = SEAT_FRONT + (c_end - SEAT_FRONT) * t
        N = n_c
    v = _top_v(u, p) + lift
    return Vector((P[0] + N[0] * v, SEAT_Y + u, P[1] + N[1] * v)), Vector((N[0], 0.0, N[1]))


def _ribbon(bm, pts, nrms, half_w, th):
    """Flat strap along points lying on a surface (normals given), thickness th below the given points."""
    n = len(pts)
    top, bot = [], []
    for i in range(n):
        tg = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        wv = tg.cross(nrms[i]).normalized()
        for lst, off in ((top, 0.0), (bot, -th)):
            base = pts[i] + nrms[i] * off
            lst.append((bm.verts.new(base + wv * half_w), bm.verts.new(base - wv * half_w)))
    for i in range(n - 1):
        a0, a1 = top[i]
        b0, b1 = top[i + 1]
        c0, c1 = bot[i]
        d0, d1 = bot[i + 1]
        bm.faces.new((a0, b0, b1, a1))
        bm.faces.new((c1, d1, d0, c0))
        bm.faces.new((a0, c0, d0, b0))
        bm.faces.new((b1, d1, c1, a1))
    for i, flip in ((0, False), (n - 1, True)):
        a0, a1 = top[i]
        c0, c1 = bot[i]
        f = (a0, a1, c1, c0)
        bm.faces.new(f[::-1] if flip else f)


def build_seat(col, mats):
    im = interior_materials()
    hw = hw_materials()
    out = []
    # upholstered pads: cushion, backrest, headrest (one object each, pad + centre insert)
    pads = []
    for nm, (fr, ps) in (('RS2_seat_cushion', _cush_frames(18)),
                         ('RS2_seat', _back_frames(26, *BACK_S)),
                         ('RS2_seat_head', _back_frames(12, *HEAD_S, head=True))):
        bm = bmesh.new()
        _pad(bm, fr, ps)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        ob = L.bm_obj(nm, bm, col, smooth=True, mat=[im['seat_pad'], im['seat_insert']])
        sub = ob.modifiers.new('sub', 'SUBSURF')
        sub.levels = 1
        sub.render_levels = 2
        pads.append(ob)
    # carbon shells: pan under the cushion, shell behind the backrest (wrapping the bolsters), headrest shell
    bm = bmesh.new()
    fr, ps = _cush_frames(14)
    _shell(bm, fr, ps, wrap=0.55, th=0.012)
    fr, ps = _back_frames(20, BACK_S[0] - 0.035, BACK_S[1] + 0.012)
    _shell(bm, fr, ps, wrap=0.92, th=0.013)
    fr, ps = _back_frames(10, HEAD_S[0] + 0.004, HEAD_S[1] - 0.004, head=True)
    _shell(bm, fr, ps, wrap=0.7, th=0.010)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    shell = L.bm_obj('RS2_seat_shell', bm, col, smooth=True, mat=im['seat_shell'])
    _autosmooth(shell, 50)
    # headrest posts (between the backrest shell and the headrest)
    d, n_c, up, n_b, c_end, b0 = _seat_axes()
    bm = bmesh.new()
    for s in (1, -1):
        v_mid = -0.5 * _HEAD['T']
        pa = b0 + up * (BACK_S[1] - 0.03) + n_b * v_mid
        pb = b0 + up * (HEAD_S[0] + 0.03) + n_b * v_mid
        L.bm_tube_along(bm, [Vector((pa[0], SEAT_Y + s * 0.075, pa[1])), Vector((pb[0], SEAT_Y + s * 0.075, pb[1]))],
                        0.008, seg=12)
    posts = L.bm_obj('RS2_seat_posts', bm, col, smooth=True, mat=hw['steel'])
    # four-point harness: shoulder straps from the top of the backrest down to the buckle, lap straps from the hips,
    # a crotch strap from the cushion
    lift, hw_, th = 0.011, 0.024, 0.004
    bm = bmesh.new()
    buckle_t = 0.50
    for s in (1, -1):
        pts, nrs = [], []
        for k in range(13):
            q = 0.98 - (0.98 - 0.02) * k / 12
            u = s * (0.096 - 0.025 * k / 12)
            p, nn = seat_surface('back', q, u, lift)
            pts.append(p)
            nrs.append(nn)
        for k in range(6):
            tt = 0.97 - (0.97 - (buckle_t + 0.05)) * k / 5
            u = s * (0.071 - 0.05 * k / 5)
            p, nn = seat_surface('cushion', tt, u, lift)
            pts.append(p)
            nrs.append(nn)
        _ribbon(bm, pts, nrs, hw_, th)
        pts, nrs = [], []
        for k in range(7):
            tt = 0.92 - (0.92 - (buckle_t + 0.03)) * k / 6
            u = s * (0.190 - 0.160 * k / 6)
            p, nn = seat_surface('cushion', tt, u, lift)
            pts.append(p)
            nrs.append(nn)
        _ribbon(bm, pts, nrs, hw_, th)
    pts, nrs = [], []
    for k in range(5):
        tt = 0.22 + (buckle_t - 0.05 - 0.22) * k / 4
        p, nn = seat_surface('cushion', tt, 0.0, lift)
        pts.append(p)
        nrs.append(nn)
    _ribbon(bm, pts, nrs, hw_ * 0.9, th)
    har = L.bm_obj('RS2_harness', bm, col, smooth=False, mat=im['harness'])
    bm = bmesh.new()
    p, nn = seat_surface('cushion', buckle_t, 0.0, lift)
    L.bm_lathe(bm, [(0.0, 0.0), (0.040, 0.0), (0.044, 0.004), (0.044, 0.010), (0.036, 0.014), (0.014, 0.016),
                    (0.0, 0.018)], p - nn * 0.002, nn, seg=40)
    buck = L.bm_obj('RS2_buckle', bm, col, smooth=True, mat=im['buckle'])
    _autosmooth(buck, 35)
    # base: two rails on the floor and a pedestal under the pan
    bm = bmesh.new()
    z_rail = FLOOR_Z + 0.018
    for s in (1, -1):
        L.bm_box(bm, (-0.06, SEAT_Y + s * 0.17, FLOOR_Z + 0.009), (0.52, 0.03, 0.018))
        for tt in (0.18, 0.82):
            pc = SEAT_FRONT + (c_end - SEAT_FRONT) * tt
            pp = _seat_params(_CUSH, tt)
            z_under = pc[1] - n_c[1] * (pp['T'] + 0.012) - 0.004
            xb = pc[0] - n_c[0] * (pp['T'] + 0.012)
            if z_under > z_rail + 0.004:
                L.bm_box(bm, (xb, SEAT_Y + s * 0.17, 0.5 * (z_rail + z_under)), (0.05, 0.026, z_under - z_rail))
    base = L.bm_obj('RS2_seatbase', bm, col, mat=hw['bracket'])
    return pads[1:2] + [base, har, buck] + [pads[0], pads[2], shell, posts]


# ---------------------------------------------------------------- dashboard and yoke (ref m008.4)
# A steel cross-car beam between the A-pillars carries a thin dash top (dark, soft rear lip with a satin trim strip)
# that runs the full width under the windshield (on the passenger side it stops short of the 400 L tank's dome); an
# instrument hood (binnacle) over a display in front of the driver; the yoke's column runs under the dash to a clamp
# on the beam. The space under the dash stays open, so the beam and the column read from below and from the nose.
BEAM = dict(x=0.90, z=0.56, r=0.032, hy=0.945)
DASH = dict(x_rear=0.690, x_rear_pass=0.800, x_front=1.140, z_rear=0.705, z_front=0.752, th=0.034, hy=0.80)


def _dash_rear_x(y):
    """Rear edge of the dash top at lateral position y: forward on the passenger side (the tank dome), back on the
    driver's side, a smooth step around the centre line."""
    k = min(max((y - 0.00) / 0.16, 0.0), 1.0)
    k = k * k * (3 - 2 * k)
    return DASH['x_rear_pass'] + (DASH['x_rear'] - DASH['x_rear_pass']) * k


def _dash_top_z(x, y):
    """Height of the dash top at (x, y) (same curve as _dash_section)."""
    xr = _dash_rear_x(y)
    th = DASH['th']
    t = (x - xr - 0.5 * th) / max(DASH['x_front'] - xr - 0.5 * th, 1e-6)
    t = min(max(t, 0.0), 1.0)
    return DASH['z_rear'] + 0.5 * th + (DASH['z_front'] - DASH['z_rear']) * t + 0.008 * math.sin(math.pi * t)


def _dash_section(y, nb=10):
    """(x, z) loop of the dash top at y: the rounded rear lip, the top, the front edge under the windshield, the
    underside. Returns (points, index range of the rear lip)."""
    xr = _dash_rear_x(y)
    xf, zr, zf, th = DASH['x_front'], DASH['z_rear'], DASH['z_front'], DASH['th']
    # gentle end taper of the thickness near the doors
    e = min(1.0, max(0.0, (abs(y) - (DASH['hy'] - 0.10)) / 0.10))
    th = th * (1 - 0.35 * e)
    pts = []
    for k in range(nb + 1):                         # rear lip: half circle from the underside round to the top
        a = -math.pi / 2 - math.pi * k / nb
        pts.append((xr + 0.5 * th * math.cos(a) + 0.5 * th, zr + 0.5 * th * math.sin(a)))
    lip = (0, nb)
    for k in range(1, 6):                           # top: rear lip -> front, slightly crowned
        t = k / 6
        x = xr + 0.5 * th + (xf - xr - 0.5 * th) * t
        z = zr + 0.5 * th + (zf - zr) * t + 0.008 * math.sin(math.pi * t)
        pts.append((x, z))
    pts.append((xf, zf + 0.004))
    pts.append((xf + 0.004, zf - 0.010))
    pts.append((xf, zf - th + 0.004))
    for k in range(1, 5):                           # underside back to the lip
        t = k / 5
        x = xf + (xr + 0.5 * th - xf) * t
        z = zf - th + (zr - 0.5 * th - (zf - th)) * t
        pts.append((x, z))
    return pts, lip


def build_cabin(col, mats):
    im = interior_materials()
    hw = hw_materials()
    objs = []
    # dash top: loft across the car
    ys = list(np.linspace(-DASH['hy'], DASH['hy'], 33))
    bm = bmesh.new()
    bm_t = bmesh.new()
    rings = []
    for y in ys:
        pts, lip = _dash_section(y)
        rings.append([bm.verts.new((x, y, z)) for (x, z) in pts])
    m = len(rings[0])
    for i in range(len(rings) - 1):
        for k in range(m):
            j = (k + 1) % m
            bm.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
    for i in (0, len(rings) - 1):
        ring = rings[i]
        c = sum((v.co for v in ring), Vector()) / m
        cv = bm.verts.new(c + Vector((0, math.copysign(0.004, ys[i]), 0)))
        for k in range(m):
            j = (k + 1) % m
            f = (ring[k], ring[j], cv)
            bm.faces.new(f if i else f[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    dash = L.bm_obj('RS2_dash', bm, col, smooth=True, mat=im['dash'])
    _autosmooth(dash, 40)
    objs.append(dash)
    # padded roll along the rear lip in the seats' leather (the dash's outline reads as a light band from above and
    # through the gold glass), with a satin piping where it meets the dash top
    ys_p = list(np.linspace(-DASH['hy'] + 0.07, DASH['hy'] - 0.07, 57))
    bm_p = bmesh.new()
    prow = []
    nseg = 18
    for i, y in enumerate(ys_p):
        xr = _dash_rear_x(y)
        k_end = min(i, len(ys_p) - 1 - i)
        s_end = (0.45, 0.78, 0.94)[k_end] if k_end < 3 else 1.0
        cx, cz = xr + 0.006, DASH['z_rear'] + 0.004
        prow.append([bm_p.verts.new((cx + 0.024 * s_end * math.cos(2 * math.pi * k / nseg), y,
                                     cz + 0.026 * s_end * math.sin(2 * math.pi * k / nseg))) for k in range(nseg)])
    for i in range(len(prow) - 1):
        for k in range(nseg):
            j = (k + 1) % nseg
            bm_p.faces.new((prow[i][k], prow[i][j], prow[i + 1][j], prow[i + 1][k]))
    bm_p.faces.new(list(reversed(prow[0])))
    bm_p.faces.new(prow[-1])
    bmesh.ops.recalc_face_normals(bm_p, faces=bm_p.faces)
    pad = L.bm_obj('RS2_dashpad', bm_p, col, smooth=True, mat=im['seat_pad'])
    objs.append(pad)
    # defrost vents along the front edge and two round face vents at the ends: dark slots that break up the top
    bm_v = bmesh.new()
    for (yv0, yv1) in ((-0.62, -0.20), (0.06, 0.52)):
        n = 12
        for i in range(n):
            ya = yv0 + (yv1 - yv0) * i / n + 0.004
            yb = yv0 + (yv1 - yv0) * (i + 1) / n - 0.004
            xv = DASH['x_front'] - 0.075
            zv = _dash_top_z(xv, 0.5 * (ya + yb)) + 0.001
            L.bm_box(bm_v, (xv, 0.5 * (ya + yb), zv), (0.045, yb - ya, 0.004))
    for sy in (1, -1):
        yv = sy * (DASH['hy'] - 0.13)
        xv = _dash_rear_x(yv) + 0.07
        L.bm_lathe(bm_v, [(0.0, 0.0), (0.034, 0.0), (0.034, 0.006), (0.028, 0.008), (0.0, 0.008)],
                   (xv, yv, _dash_top_z(xv, yv) - 0.003), (0, 0, 1), seg=24, close_start=True)
    vent = L.bm_obj('RS2_dashvents', bm_v, col, mat=im['vent'])
    objs.append(vent)
    pts = []
    for y in np.linspace(-DASH['hy'] + 0.10, DASH['hy'] - 0.10, 40):
        xr = _dash_rear_x(y)
        pts.append(Vector((xr + 0.018, y, DASH['z_rear'] + 0.0265)))
    L.bm_tube_along(bm_t, pts, 0.0035, seg=8)
    # instrument hood (binnacle) over the display: a curved visor with side cheeks
    y0, y1 = SEAT_Y - 0.17, SEAT_Y + 0.17
    bm_h = bmesh.new()
    hood_rings = []
    vis = [(0.805, 0.732), (0.760, 0.790), (0.700, 0.808), (0.640, 0.802), (0.620, 0.790), (0.628, 0.782),
           (0.645, 0.792), (0.700, 0.796), (0.755, 0.779), (0.795, 0.730)]
    nyh = 15
    for i in range(nyh):
        y = y0 + (y1 - y0) * i / (nyh - 1)
        e = abs(2 * i / (nyh - 1) - 1)
        drop = 0.03 * e ** 3                         # the visor's ends curve down onto the dash
        hood_rings.append([bm_h.verts.new((x + 0.01 * e ** 2, y, z - drop)) for (x, z) in vis])
    mh = len(vis)
    for i in range(nyh - 1):
        for k in range(mh):
            j = (k + 1) % mh
            bm_h.faces.new((hood_rings[i][k], hood_rings[i][j], hood_rings[i + 1][j], hood_rings[i + 1][k]))
    for i in (0, nyh - 1):
        f = bm_h.faces.new(hood_rings[i] if i else list(reversed(hood_rings[i])))
    bmesh.ops.recalc_face_normals(bm_h, faces=bm_h.faces)
    hood = L.bm_obj('RS2_binnacle', bm_h, col, smooth=True, mat=im['dash'])
    _autosmooth(hood, 35)
    sub = hood.modifiers.new('sub', 'SUBSURF')
    sub.levels = 1
    sub.render_levels = 1
    objs.append(hood)
    # display under the hood, tilted toward the driver
    bm = bmesh.new()
    a = Vector((0.660, 0.0, 0.784))
    b = Vector((0.700, 0.0, 0.735))
    for yy0, yy1 in ((y0 + 0.025, y1 - 0.025),):
        vs = [bm.verts.new(p) for p in (a + Vector((0, yy0, 0)), b + Vector((0, yy0, 0)), b + Vector((0, yy1, 0)),
                                        a + Vector((0, yy1, 0)))]
        bm.faces.new(vs)
    # a frame round the display
    scr = L.bm_obj('RS2_screen', bm, col, mat=im['screen'])
    objs.append(scr)
    # centre touchscreen standing on the dash, tilted back toward the cabin, on a short stalk
    yc, wc, hc, tc = 0.02, 0.26, 0.15, 0.010
    tilt = math.radians(18)
    up = Vector((math.sin(tilt), 0.0, math.cos(tilt)))
    nrm = Vector((-math.cos(tilt), 0.0, math.sin(tilt)))            # the face looks back and up
    b0 = Vector((0.842, yc, 0.756))
    bm = bmesh.new()
    corners = [b0 + Vector((0, -0.5 * wc, 0)), b0 + Vector((0, 0.5 * wc, 0)),
               b0 + Vector((0, 0.5 * wc, 0)) + up * hc, b0 + Vector((0, -0.5 * wc, 0)) + up * hc]
    front = [bm.verts.new(c + nrm * 0.5 * tc) for c in corners]
    back = [bm.verts.new(c - nrm * 0.5 * tc) for c in corners]
    face = bm.faces.new(front[::-1])
    face.material_index = 1
    bm.faces.new(back)
    for k in range(4):
        j = (k + 1) % 4
        bm.faces.new((front[k], front[j], back[j], back[k]))
    # stalk from the dash top to the back of the screen
    sc0 = b0 + up * 0.35 * hc - nrm * 0.5 * tc
    L.bm_tube_along(bm, [sc0, sc0 + Vector((0.02, 0.0, -0.05))], 0.012, seg=10)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    cscr = L.bm_obj('RS2_centrescreen', bm, col, mat=im['bezel'])
    cscr.data.materials.append(display_material('INT_display_c', 0.830))
    objs.append(cscr)
    # cross-car beam with its end plates (bolted to the A-pillar structure) and two dash brackets
    bx, bz, br, bhy = BEAM['x'], BEAM['z'], BEAM['r'], BEAM['hy']
    bmb = bmesh.new()
    L.bm_tube_along(bmb, [Vector((bx, -bhy, bz)), Vector((bx, bhy, bz))], br, seg=24)
    for s in (1, -1):
        L.bm_box(bmb, (bx, s * (bhy + 0.006), bz), (0.12, 0.012, 0.13))
        L.bm_box(bmb, (bx - 0.03, s * 0.55, 0.5 * (bz + br + DASH['z_front'] - 0.03)), (0.018, 0.05,
                 DASH['z_front'] - 0.03 - bz - br + 0.004))
    L.bm_box(bmb, (bx - 0.03, 0.04, 0.5 * (bz + br + DASH['z_front'] - 0.03)), (0.018, 0.05,
             DASH['z_front'] - 0.03 - bz - br + 0.004))
    beam = L.bm_obj('RS2_dashbeam', bmb, col, smooth=True, mat=hw['beam'])
    _autosmooth(beam, 40)
    objs.append(beam)
    trim = L.bm_obj('RS2_dashtrim', bm_t, col, smooth=True, mat=im['trim'])
    objs.append(trim)
    # yoke: squared-off rim (flat top), two spokes to a round hub, the column under the dash to a clamp on the beam
    th_ = math.radians(20)
    cen = Vector((0.50, SEAT_Y, 0.715))
    up_d = Vector((math.sin(th_), 0.0, math.cos(th_)))
    col_d = Vector((math.cos(th_), 0.0, -math.sin(th_)))       # from the driver toward the dash

    def yk(u, v, w=0.0):
        return cen + Vector((0, u, 0)) + up_d * v + col_d * w
    pts = []
    a_, b_, n_ = 0.170, 0.108, 4.0
    for k in range(72):
        ang = 2 * math.pi * k / 72
        cu, sv = math.cos(ang), math.sin(ang)
        u = a_ * math.copysign(abs(cu) ** (2 / n_), cu)
        v = b_ * math.copysign(abs(sv) ** (2 / n_), sv)
        v = min(v, 0.086)
        pts.append(yk(u, v))
    bm = bmesh.new()
    _tube_closed(bm, pts, 0.017, seg=14)
    for s in (1, -1):
        L.bm_tube_along(bm, [yk(s * 0.05, -0.004, 0.006), yk(s * 0.162, 0.0, 0.0)], 0.012, seg=12)
    yoke = L.bm_obj('RS2_yoke', bm, col, smooth=True, mat=im['yoke'])
    _autosmooth(yoke, 50)
    objs.append(yoke)
    bm = bmesh.new()
    L.bm_lathe(bm, [(0.0, -0.022), (0.050, -0.022), (0.058, -0.010), (0.058, 0.012), (0.046, 0.024), (0.0, 0.026)],
               yk(0.0, 0.0, 0.004), col_d, seg=40)
    # column shroud, then the bare column to the beam clamp
    L.bm_lathe(bm, [(0.030, 0.0), (0.046, 0.05), (0.046, 0.13), (0.040, 0.15), (0.030, 0.15)], yk(0.0, 0.0, 0.03),
               col_d, seg=24, close_start=True, close_end=True)
    w_end = (BEAM['x'] - 0.045 - cen.x) / col_d.x
    L.bm_tube_along(bm, [yk(0.0, 0.0, 0.17), yk(0.0, 0.0, w_end)], 0.020, seg=16)
    hub = L.bm_obj('RS2_yokehub', bm, col, smooth=True, mat=mats.get('dark_metal', im['trim']))
    _autosmooth(hub, 40)
    objs.append(hub)
    # clamp: a block on the column end bolted to a bracket round the beam
    bm = bmesh.new()
    pe = yk(0.0, 0.0, w_end)
    L.bm_box(bm, (0.5 * (pe.x + bx), SEAT_Y, 0.5 * (pe.z + bz)), (abs(bx - pe.x) + 0.05, 0.07, abs(pe.z - bz) + 0.05))
    clamp = L.bm_obj('RS2_columnclamp', bm, col, mat=hw['bracket'])
    bv = clamp.modifiers.new('bv', 'BEVEL')
    bv.width = 0.006
    bv.segments = 2
    objs.append(clamp)
    # firewall behind the front wheels, low enough to see the 400 L tank's dome over it from the nose
    bm = bmesh.new()
    fw_ = FIREWALL
    L.bm_box(bm, (fw_['x'], 0.0, 0.5 * (fw_['z0'] + fw_['z1'])), (0.018, 2 * fw_['hy'], fw_['z1'] - fw_['z0']))
    L.bm_box(bm, (fw_['x'] - 0.02, 0.0, fw_['z1'] - 0.006), (0.04, 2 * fw_['hy'], 0.012))
    fw = L.bm_obj('RS2_firewall', bm, col, mat=mats['under'])
    objs.append(fw)
    return objs


def _tube_closed(bm, pts, r, seg=12):
    pts = [Vector(p) for p in pts]
    n = len(pts)
    tangents = [(pts[(i + 1) % n] - pts[(i - 1) % n]).normalized() for i in range(n)]
    x = tangents[0].orthogonal().normalized()
    rings = []
    for i in range(n):
        t = tangents[i]
        x = (x - t * x.dot(t)).normalized()
        y = t.cross(x)
        rings.append([bm.verts.new(pts[i] + (x * math.cos(2 * math.pi * k / seg) + y * math.sin(2 * math.pi * k / seg)) * r)
                      for k in range(seg)])
    # parallel transport does not close the loop exactly: find the ring rotation that matches best
    first, last = rings[0], rings[-1]
    best, shift = 1e9, 0
    for sft in range(seg):
        dsum = sum((last[(k + sft) % seg].co - first[k].co).length for k in range(seg))
        if dsum < best:
            best, shift = dsum, sft
    for i in range(n):
        a, b = rings[i], rings[(i + 1) % n]
        off = shift if i == n - 1 else 0
        for k in range(seg):
            j = (k + 1) % seg
            if i == n - 1:
                bm.faces.new((a[(k + off) % seg], a[(j + off) % seg], b[j], b[k]))
            else:
                bm.faces.new((a[k], a[j], b[j], b[k]))


# ---------------------------------------------------------------- plumbing

def fillet_route(points, rb=BEND_R, step=0.02, arc_deg=8.0):
    """Polyline through waypoints with circular bends of radius rb at every corner, sampled densely."""
    P = [Vector(p) for p in points]
    out = [P[0].copy()]
    cur = P[0].copy()
    for i in range(1, len(P) - 1):
        a, b, c = P[i - 1], P[i], P[i + 1]
        d1 = (b - a).normalized()
        d2 = (c - b).normalized()
        cosang = max(-1.0, min(1.0, d1.dot(d2)))
        ang = math.acos(cosang)
        if ang < 1e-3:
            continue
        t = rb * math.tan(ang / 2)
        t = min(t, 0.48 * (b - a).length, 0.48 * (c - b).length)
        r_eff = t / math.tan(ang / 2)
        A = b - d1 * t
        B = b + d2 * t
        seg_len = (A - cur).length
        n = max(1, int(seg_len / step))
        for k in range(1, n + 1):
            out.append(cur.lerp(A, k / n))
        m = (d2 - d1).normalized()
        cen = b + m * (r_eff / math.cos(ang / 2))
        qa = (A - cen).normalized()
        qb = (B - cen).normalized()
        na = max(2, int(math.degrees(ang) / arc_deg))
        for k in range(1, na + 1):
            out.append(cen + qa.slerp(qb, k / na) * r_eff)
        cur = B
    end = P[-1]
    seg_len = (end - cur).length
    n = max(1, int(seg_len / step))
    for k in range(1, n + 1):
        out.append(cur.lerp(end, k / n))
    return out


def valve_port(nm, which='flow'):
    """Car-local point and direction of a valve port: 'flow' (to the firing nozzle) or 'feed' (400 L valve only, to
    the valve block)."""
    M = tank_frame(nm)
    xv, xc, hwy, hhz, side = _valve_geom(nm)
    s = side * (1.0 if which == 'flow' else -1.0)
    p = M @ Vector((xc, s * hwy, 0.0))
    d = (M.to_3x3() @ Vector((0, s, 0))).normalized()
    return p, d


def valve_outlet(nm):
    """(legacy name) the flow port."""
    return valve_port(nm, 'flow')


def valve_passage(nm):
    """Car-local path of the gas through the valve: neck inside the tank -> boss bore -> valve bore -> ball ->
    flow port (dense, the bend filleted like the bore)."""
    M = tank_frame(nm)
    x_pole, _ = pole_x(nm)
    xv, xc, hwy, hhz, side = _valve_geom(nm)
    loc = [neck_point(nm), Vector((x_pole, 0, 0)), Vector((xv, 0, 0))]
    loc += fillet_route([Vector((xv + 0.004, 0, 0)), Vector((xc, 0, 0)), Vector((xc, side * hwy, 0))],
                        rb=0.035, step=0.008, arc_deg=6.0)[1:]
    return [M @ p for p in loc]


def _lift_elbow():
    """True if the car builds its lift nozzles with their own feed pipe (straight up to the inlet, then an elbow toward
    the car's centre): the interior's lines then meet the elbow's open end, arriving outward."""
    try:
        import inspect
        src = inspect.getsource(C.build_nozzles)
    except Exception:
        return False
    return 'inward' in src and '0.175' in src


def _elbow_points(nm):
    """Centre line of a lift nozzle's own feed elbow, from its open end (inboard) to the inlet above the throat."""
    p, d = C.NOZZLES[nm]
    p, d = Vector(p), Vector(d).normalized()
    inlet = p - d * 0.175
    inward = Vector((0.0, -math.copysign(1.0, p.y), 0.0))
    return [inlet - d * 0.05 + inward * 0.07, inlet - d * 0.045 + inward * 0.02, inlet - d * 0.03, inlet]


def nozzle_inlet(nm):
    """(point where the interior's line ends, direction pointing back along that line)."""
    p, d = C.NOZZLES[nm]
    p, d = Vector(p), Vector(d)
    if nm.startswith('lift'):
        if _lift_elbow():
            e = _elbow_points(nm)
            return e[0], (e[0] - e[1]).normalized()        # the elbow's open end; the line comes in from the centre
        return p - d * 0.175, -d           # top of the nozzle tube, pipe arrives from above
    if nm.startswith('nose'):
        return p - d * 0.075, -d
    return p - d * 0.11, -d                # rear: behind the bezel, inside the tail


def nozzle_path(nm):
    """Gas path from the end of the interior's line through the nozzle's own passage to just past its exit."""
    p, d = C.NOZZLES[nm]
    p, d = Vector(p), Vector(d).normalized()
    pre = _elbow_points(nm)[1:] if (nm.startswith('lift') and _lift_elbow()) else []
    return pre + [p - d * 0.06, p + d * 0.004]


def _port(block, face, off=(0.0, 0.0)):
    """Point on a block face: face in ('+x','-x','+y','-y','+z','-z'), offset in the face plane."""
    c, s = block['center'], block['size']
    ax = {'x': 0, 'y': 1, 'z': 2}[face[1]]
    sg = 1.0 if face[0] == '+' else -1.0
    p = c.copy()
    p[ax] += sg * s[ax] / 2
    others = [i for i in range(3) if i != ax]
    p[others[0]] += off[0]
    p[others[1]] += off[1]
    dirn = Vector((0, 0, 0))
    dirn[ax] = sg
    return p, dirn


def pipe_routes():
    """name -> waypoints (car-local), source first. Flow lines: 'flow_big', 'flow_rear'. The rest: 'feed' (400 L
    valve -> valve block), lift_FL, lift_RL, nose_trunk, nose_L/R, rear_trunk, rear_1..4."""
    R = {}
    nfr, _ = nozzle_inlet('lift_FR')
    nrr, _ = nozzle_inlet('lift_RR')
    nfl, _ = nozzle_inlet('lift_FL')
    nrl, _ = nozzle_inlet('lift_RL')
    pb, db = valve_port('big', 'flow')
    pr, dr = valve_port('rear', 'flow')
    pf, df = valve_port('big', 'feed')
    mt = _port(MANIFOLD, '+z', (pf.x - MANIFOLD['center'].x, -0.05))[0]
    R['feed'] = [pf, Vector((pf.x, mt.y, pf.z)), mt]
    m = MANIFOLD
    p0 = _port(m, '+y', (0.03, 0.0))[0]
    p1 = _port(m, '+y', (-0.03, 0.0))[0]
    if _lift_elbow():
        zf = nfr.z
        y_run = Y_RUN
        # main line: outboard from the valve, down beside the tank's rear dome, forward along the long run beside the
        # tank (108 mm), the reducer, then a 51 mm jog into the front-right nozzle's feed elbow (arriving outward)
        R['flow_big'] = [pb, Vector((pb.x, -0.60, pb.z)), Vector((pb.x, Y_MAIN, Z_MAIN)),
                         Vector((X_RED[0], Y_MAIN, Z_MAIN)), Vector((X_RED[1], Y_MAIN, Z_MAIN)),
                         Vector((X_RED[1] + 0.07, Y_MAIN, Z_MAIN)), Vector((nfr.x - 0.05, nfr.y + 0.085, zf)),
                         Vector((nfr.x, nfr.y + 0.085, zf)), nfr]
        # 200 L tank -> rear-right lift nozzle: rearward from the valve above the wheel well's inner wall, over the fan
        # ducts, outboard of them, down and outward into the elbow
        y_d = DUCT_CLEAR
        R['flow_rear'] = [pr, Vector((nrr.x, pr.y, pr.z)), Vector((nrr.x, -y_d, pr.z)), Vector((nrr.x, -y_d, nrr.z)),
                          nrr]
        R['lift_FL'] = [p0, Vector((p0.x, y_run, p0.z)), Vector((p0.x + 0.25, y_run, zf)), Vector((nfl.x, y_run, zf)),
                        nfl]
        y_in = 0.555
        R['lift_RL'] = [p1, Vector((p1.x, y_in, p1.z)), Vector((p1.x - 0.25, y_in, Z_OVER_DUCT)),
                        Vector((nrl.x, y_in, Z_OVER_DUCT)), Vector((nrl.x, y_d, Z_OVER_DUCT)), Vector((nrl.x, y_d, nrl.z)),
                        nrl]
    else:
        R['flow_big'] = [pb, Vector((pb.x, nfr.y, pb.z)), Vector((pb.x + 0.24, nfr.y, Z_RUN)),
                         Vector((nfr.x, nfr.y, Z_RUN)), nfr]
        R['flow_rear'] = [pr, Vector((nrr.x, pr.y, pr.z)), Vector((nrr.x, nrr.y, pr.z)), nrr]
        R['lift_FL'] = [p0, Vector((p0.x, nfl.y, p0.z)), Vector((p0.x + 0.25, nfl.y, Z_RUN)),
                        Vector((nfl.x, nfl.y, Z_RUN)), nfl]
        y_in = 0.555
        R['lift_RL'] = [p1, Vector((p1.x, y_in, p1.z)), Vector((p1.x - 0.25, y_in, Z_RUN)),
                        Vector((nrl.x, y_in, Z_RUN)), Vector((nrl.x, nrl.y, Z_RUN)), nrl]
    y_tun = 0.062
    p2 = _port(m, '+x', (y_tun - m['center'].y, 0.0))[0]
    nb_in = _port(NOSE_BLOCK, '-x')[0]
    R['nose_trunk'] = [p2, Vector((0.84, y_tun, p2.z)), Vector((FIREWALL['x'], 0.03, 0.31)), Vector((1.25, 0.0, nb_in.z)),
                       nb_in]
    for s, tag in ((1, 'L'), (-1, 'R')):
        q = _port(NOSE_BLOCK, '+y' if s > 0 else '-y')[0]
        ni = nozzle_inlet('nose_' + tag)[0]
        R['nose_' + tag] = [q, Vector((q.x, s * 0.40, q.z)), Vector((ni.x - 0.02, s * 0.62, ni.z)), ni]
    p3 = _port(m, '-y', (0.0, 0.0))[0]
    rb_in = _port(REAR_BLOCK, '-y')[0]
    y_tr = -0.46
    R['rear_trunk'] = [p3, Vector((p3.x, y_tr, p3.z)), Vector((rb_in.x, y_tr, p3.z)), Vector((rb_in.x, y_tr, rb_in.z)),
                       rb_in]
    for nm in ('rear_1', 'rear_2', 'rear_3', 'rear_4'):
        y = C.NOZZLES[nm][0][1]
        q = _port(REAR_BLOCK, '-x', (y * 0.3, 0.0))[0]
        ni = nozzle_inlet(nm)[0]
        R[nm] = [q, Vector((q.x - 0.08, q.y, q.z)), Vector((ni.x + 0.10, y, ni.z)), ni]
    return R


def _route_dense(nm, wp):
    """Dense centre line of a route: the main line uses tighter bends near the nozzle (its jog is short)."""
    if nm == 'flow_big' and _lift_elbow():
        a = fillet_route(wp[:6], rb=0.16)
        b = fillet_route(wp[5:], rb=0.05, step=0.01)
        return a + b[1:]
    return fillet_route(wp)


def flow_route_dense(nm):
    """Dense centre line of a flow line: 'flow_big' or 'flow_rear'."""
    return _route_dense(nm, pipe_routes()[nm])


def _arc_lengths(pts):
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + (pts[i] - pts[i - 1]).length)
    return cum


def flow_radii(nm, pts):
    """(outer, inner) tube radius at each dense point of a flow line. The main line is 108 mm from the valve flange
    to the reducer, tapering to 51 mm over the reducer; the 200 L line is 51 mm throughout."""
    if nm != 'flow_big' or not _lift_elbow():
        return [PIPE_R] * len(pts), [PIPE_IN] * len(pts)
    i0 = min(range(len(pts)), key=lambda k: (pts[k] - Vector((X_RED[0], Y_MAIN, Z_MAIN))).length)
    i1 = min(range(len(pts)), key=lambda k: (pts[k] - Vector((X_RED[1], Y_MAIN, Z_MAIN))).length)
    cum = _arc_lengths(pts)
    ro, ri = [], []
    for k in range(len(pts)):
        if k <= i0:
            t = 0.0
        elif k >= i1:
            t = 1.0
        else:
            t = (cum[k] - cum[i0]) / max(cum[i1] - cum[i0], 1e-6)
            t = t * t * (3 - 2 * t)
        ro.append(R_FAT + (PIPE_R - R_FAT) * t)
        ri.append(R_FAT_IN + (PIPE_IN - R_FAT_IN) * t)
    return ro, ri


def gas_path(nm):
    """The gas path of a stream for the molecules: (points, inner radii, index of the nozzle exit): from the neck in
    the tank through the valve, along the flow line and through the nozzle's own passage to just past its exit."""
    line = 'flow_big' if nm == 'big' else 'flow_rear'
    noz = 'lift_FR' if nm == 'big' else 'lift_RR'
    vp = valve_passage(nm)
    dense = flow_route_dense(line)
    ro, ri = flow_radii(line, dense)
    pts = list(vp) + dense[1:]
    rad = [0.020, 0.024] + [BORE_IN] * (len(vp) - 2) + ri[1:]
    # entering the main line: the stream widens over the outlet flange (the first few cm of the 108 mm tube)
    if nm == 'big' and _lift_elbow():
        cum = _arc_lengths(pts)
        s0 = cum[len(vp) - 1]
        for k in range(len(vp) - 1, len(pts)):
            t = (cum[k] - s0) / 0.07
            if t >= 1.0:
                break
            t = max(t, 0.0)
            t = t * t * (3 - 2 * t)
            rad[k] = BORE_IN + (rad[k] - BORE_IN) * t
    tail = nozzle_path(noz)
    pts += tail
    rad += [0.019] * len(tail)
    return pts, rad, len(pts) - 1


def hex_fitting(bm, p, d, r_pipe=PIPE_R):
    """AN-style fitting: hex nut plus a collar, centred on the pipe end p, axis d (pointing into the pipe)."""
    d = Vector(d).normalized()
    af = r_pipe * 1.45
    L.bm_lathe(bm, [(af, 0.0), (af, 0.026)], p, d, seg=6, close_start=True, close_end=True)
    L.bm_lathe(bm, [(r_pipe * 1.18, 0.024), (r_pipe * 1.18, 0.040), (r_pipe * 1.05, 0.046)], p, d, seg=24,
               close_end=True)


def flange(bm, p, d, r_pipe, th=0.018, bolts=6, extra=0.016):
    """Bolted flange on a pipe end at p (axis d into the pipe): a disc with bolt heads."""
    d = Vector(d).normalized()
    rf = r_pipe + extra
    L.bm_lathe(bm, [(r_pipe * 0.98, 0.0), (rf, 0.0), (rf, th), (r_pipe * 1.02, th + 0.004)], p, d, seg=32,
               close_start=False, close_end=False)
    x = d.orthogonal().normalized()
    y = d.cross(x)
    for k in range(bolts):
        a = 2 * math.pi * (k + 0.5) / bolts
        q = p + (x * math.cos(a) + y * math.sin(a)) * (r_pipe + 0.55 * extra) + d * th
        L.bm_lathe(bm, [(0.0, 0.0), (0.0055, 0.0), (0.0055, 0.005), (0.0, 0.006)], q, d, seg=6)


def _tube_arc(bm, pts, r, seg=20, caps=True, arc=None, radii=None):
    """Tube along a polyline (parallel-transported frames); writes the normalised arc length into the float layer
    `arc` if given; per-point radii if given."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    cum = _arc_lengths(pts)
    tot = max(cum[-1], 1e-9)
    tangents = [(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(n)]
    x = tangents[0].orthogonal().normalized()
    rings = []
    for i in range(n):
        t = tangents[i]
        x = (x - t * x.dot(t)).normalized()
        y = t.cross(x)
        ring = []
        rr = radii[i] if radii is not None else r
        for k in range(seg):
            a = 2 * math.pi * k / seg
            v = bm.verts.new(pts[i] + (x * math.cos(a) + y * math.sin(a)) * rr)
            if arc is not None:
                v[arc] = cum[i] / tot
            ring.append(v)
        rings.append(ring)
    for i in range(n - 1):
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
    if caps:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])


def build_plumbing(col, mats):
    hw = hw_materials()
    routes = pipe_routes()
    dense = {nm: _route_dense(nm, wp) for nm, wp in routes.items()}
    bm_p = bmesh.new()
    bm_q = bmesh.new()
    arc = bm_q.verts.layers.float.new('arc')
    bm_f = bmesh.new()
    for nm, pts in dense.items():
        flow = nm in FLOW_LINES
        if flow:
            ro, ri = flow_radii(nm, pts)
            _tube_arc(bm_q, pts, PIPE_R, seg=32 if nm == 'flow_big' else 24, caps=True, arc=arc, radii=ro)
            if ro[0] > PIPE_R + 1e-4:
                flange(bm_f, pts[0], pts[1] - pts[0], ro[0], th=0.016, bolts=6, extra=0.010)
            else:
                hex_fitting(bm_f, pts[0], (pts[1] - pts[0]), ro[0])
            hex_fitting(bm_f, pts[-1], (pts[-2] - pts[-1]), ro[-1])
            if nm == 'flow_big' and _lift_elbow():
                # bolted rings at both ends of the reducer
                for xr in X_RED:
                    k = min(range(len(pts)), key=lambda q: (pts[q] - Vector((xr, Y_MAIN, Z_MAIN))).length)
                    dd = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
                    rr = ro[k]
                    L.bm_lathe(bm_f, [(rr * 0.99, -0.008), (rr + 0.010, -0.008), (rr + 0.010, 0.008),
                                      (rr * 0.99, 0.008)], pts[k], dd, seg=32)
        else:
            _tube_arc(bm_p, pts, PIPE_R_SMALL, seg=16, caps=True)
            hex_fitting(bm_f, pts[0], (pts[1] - pts[0]), PIPE_R_SMALL)
            hex_fitting(bm_f, pts[-1], (pts[-2] - pts[-1]), PIPE_R_SMALL)
    # bulkhead fitting where the nose trunk passes the firewall
    nt = dense['nose_trunk']
    fx = FIREWALL['x']
    i = min(range(len(nt)), key=lambda k: abs(nt[k].x - fx))
    dirn = (nt[min(i + 1, len(nt) - 1)] - nt[max(i - 1, 0)]).normalized()
    for sgn in (1, -1):
        L.bm_lathe(bm_f, [(PIPE_R_SMALL * 1.9, 0.0), (PIPE_R_SMALL * 1.9, 0.008), (PIPE_R_SMALL * 1.3, 0.012),
                          (PIPE_R_SMALL * 1.3, 0.02)], nt[i] + dirn * sgn * 0.011, dirn * sgn, seg=6,
                   close_start=True, close_end=True)
    # pipe clamps holding the main line's long run to the floor
    if _lift_elbow():
        for xc in (-0.35, 0.15):
            p = Vector((xc, Y_MAIN, Z_MAIN))
            L.bm_lathe(bm_f, [(R_FAT + 0.001, -0.012), (R_FAT + 0.009, -0.012), (R_FAT + 0.009, 0.012),
                              (R_FAT + 0.001, 0.012)], p, (1, 0, 0), seg=32)
            zf = floor_top(xc)
            L.bm_box(bm_f, (xc, Y_MAIN, 0.5 * (zf + Z_MAIN - R_FAT - 0.006)), (0.024, 0.03,
                     Z_MAIN - R_FAT - 0.006 - zf))
    pipes = L.bm_obj('RS2_pipes', bm_p, col, smooth=True, mat=hw['pipe'])
    flowp = L.bm_obj('RS2_flowpipes', bm_q, col, smooth=True, mat=pipe_flow_material(mats))
    flowp['reveal'] = 0.0
    fits = L.bm_obj('RS2_fittings', bm_f, col, smooth=False, mat=hw['fitting'])
    _autosmooth(fits, 40)
    # valve block (manifold) behind the seat and the two distribution blocks: machined, chamfered
    bm = bmesh.new()
    for blk in (MANIFOLD, REAR_BLOCK, NOSE_BLOCK):
        _box_chamfer(bm, blk['center'], blk['size'], 0.010)
    blocks = L.bm_obj('RS2_manifolds', bm, col, mat=hw['alu'])
    # on the valve block: a solenoid valve on top, port bosses, cap bolts, two feet to the floor
    bm = bmesh.new()
    c, s = MANIFOLD['center'], MANIFOLD['size']
    for dx in (-0.04, 0.04):
        for dy in (-0.08, 0.08):
            L.bm_lathe(bm, [(0.0, 0.0), (0.009, 0.0), (0.009, 0.007), (0.0, 0.009)],
                       c + Vector((dx, dy, s.z / 2)), (0, 0, 1), seg=6)
    bolts = L.bm_obj('RS2_bolts', bm, col, mat=hw['steel'])
    bm = bmesh.new()
    top = c + Vector((0.0, 0.035, s.z / 2))
    L.bm_lathe(bm, [(0.022, 0.0), (0.022, 0.014)], top, (0, 0, 1), seg=6, close_start=True, close_end=True)
    L.bm_lathe(bm, [(0.0, 0.014), (0.028, 0.014), (0.030, 0.018), (0.030, 0.066), (0.026, 0.072), (0.012, 0.074),
                    (0.012, 0.084), (0.0, 0.084)], top, (0, 0, 1), seg=36)
    zf = floor_top(c.x)
    for dy in (-0.085, 0.085):
        L.bm_box(bm, (c.x, c.y + dy, 0.5 * (zf + c.z - s.z / 2)), (0.09, 0.02, c.z - s.z / 2 - zf))
    msol = L.bm_obj('RS2_manifold_sol', bm, col, smooth=True, mat=hw['black'])
    _autosmooth(msol, 35)
    return dict(pipes=pipes, flowpipes=flowp, fittings=fits, blocks=blocks, bolts=bolts, manifold_sol=msol,
                dense=dense, routes=routes)


def build_all(col, mats):
    out = {}
    out['seat'] = build_seat(col, mats)
    out['cabin'] = build_cabin(col, mats)
    out['tanks'] = {nm: build_tank(col, mats, nm) for nm in TANKS}
    out['plumbing'] = build_plumbing(col, mats)
    return out
