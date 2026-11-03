import math
import bpy
import numpy as np
from . import dims as D
from .util import MM, mesh_np, obj, points_mesh, revolve_profile, recalc_normals, MeshAccum
from .materials import srgb

CYAN = srgb('#5ac8fa')[:3]
AMBER = srgb('#ff9f43')[:3]
GOLD = srgb('#ffd58a')[:3]
VIOLET = srgb('#9aa7ff')[:3]


def _sock(ng, name, io, st, default=None, minv=None, maxv=None, subtype=None):
    s = ng.interface.new_socket(name, in_out=io, socket_type=st)
    if default is not None:
        s.default_value = default
    if minv is not None:
        s.min_value = minv
    if maxv is not None:
        s.max_value = maxv
    if subtype:
        s.subtype = subtype
    return s


def frame_time_value(nt, fps=30.0):
    v = nt.nodes.new('ShaderNodeValue')
    v.label = 'time_s'
    fc = v.outputs[0].driver_add('default_value')
    fc.driver.type = 'SCRIPTED'
    fc.driver.expression = 'frame / %g' % fps
    return v


def streak_mesh(name, segs=10, rings=12):
    verts = []
    sz = []
    for j in range(rings + 1):
        t = j / rings
        z = -1.0 + t
        r = math.sin(math.pi * min(1.0, t * 1.15)) ** 0.6 if t < 0.999 else 0.0
        r = max(r, 0.0)
        for i in range(segs):
            a = 2 * math.pi * i / segs
            verts.append((r * math.cos(a), r * math.sin(a), z))
            sz.append(t)
    faces = []
    for j in range(rings):
        for i in range(segs):
            i2 = (i + 1) % segs
            faces.append((j * segs + i, j * segs + i2, (j + 1) * segs + i2, (j + 1) * segs + i))
    me = mesh_np(name, np.array(verts), faces)
    a = me.attributes.new('sz', 'FLOAT', 'POINT')
    a.data.foreach_set('value', np.array(sz, dtype=np.float32))
    for p in me.polygons:
        p.use_smooth = True
    return me


def fx_emit_material(name, color, strength=6.0, attr_u='sz', pulse=False, tail_power=1.6, soft=True):
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    N = nt.nodes
    L = nt.links
    for n in list(N):
        N.remove(n)
    out = N.new('ShaderNodeOutputMaterial')
    a = N.new('ShaderNodeAttribute')
    a.attribute_type = 'GEOMETRY'
    a.attribute_name = attr_u
    pw = N.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = tail_power
    L.new(a.outputs['Fac'], pw.inputs[0])
    alpha = pw.outputs['Value']
    if pulse:
        tv = frame_time_value(nt)
        ph = N.new('ShaderNodeAttribute')
        ph.attribute_type = 'GEOMETRY'
        ph.attribute_name = 'phase'
        sp = N.new('ShaderNodeMath')
        sp.operation = 'MULTIPLY'
        sp.inputs[1].default_value = 1.6
        L.new(tv.outputs[0], sp.inputs[0])
        s1 = N.new('ShaderNodeMath')
        s1.operation = 'ADD'
        L.new(sp.outputs[0], s1.inputs[0])
        L.new(ph.outputs['Fac'], s1.inputs[1])
        s2 = N.new('ShaderNodeMath')
        s2.operation = 'SUBTRACT'
        L.new(s1.outputs[0], s2.inputs[0])
        L.new(a.outputs['Fac'], s2.inputs[1])
        fr = N.new('ShaderNodeMath')
        fr.operation = 'FRACT'
        L.new(s2.outputs[0], fr.inputs[0])
        pk = N.new('ShaderNodeMapRange')
        pk.interpolation_type = 'SMOOTHSTEP'
        pk.inputs['From Min'].default_value = 0.75
        pk.inputs['From Max'].default_value = 1.0
        pk.inputs['To Min'].default_value = 0.25
        pk.inputs['To Max'].default_value = 1.0
        L.new(fr.outputs[0], pk.inputs['Value'])
        mm = N.new('ShaderNodeMath')
        mm.operation = 'MULTIPLY'
        L.new(alpha, mm.inputs[0])
        L.new(pk.outputs['Result'], mm.inputs[1])
        alpha = mm.outputs['Value']
    col_mix = N.new('ShaderNodeMix')
    col_mix.data_type = 'RGBA'
    col_mix.inputs['A'].default_value = tuple(color) + (1.0,)
    col_mix.inputs['B'].default_value = tuple(AMBER) + (1.0,)
    ht = N.new('ShaderNodeAttribute')
    ht.attribute_type = 'GEOMETRY'
    ht.attribute_name = 'hotmix'
    L.new(ht.outputs['Fac'], col_mix.inputs['Factor'])
    em = N.new('ShaderNodeEmission')
    L.new(col_mix.outputs['Result'], em.inputs['Color'])
    gs = N.new('ShaderNodeAttribute')
    gs.attribute_type = 'GEOMETRY'
    gs.attribute_name = 'gain'
    gm = N.new('ShaderNodeMath')
    gm.operation = 'MULTIPLY'
    gm.inputs[1].default_value = strength
    L.new(alpha, gm.inputs[0])
    st = N.new('ShaderNodeMath')
    st.operation = 'MULTIPLY'
    L.new(gm.outputs[0], st.inputs[0])
    L.new(gs.outputs['Fac'], st.inputs[1])
    L.new(st.outputs[0], em.inputs['Strength'])
    tr = N.new('ShaderNodeBsdfTransparent')
    add = N.new('ShaderNodeAddShader')
    L.new(tr.outputs['BSDF'], add.inputs[0])
    L.new(em.outputs['Emission'], add.inputs[1])
    L.new(add.outputs['Shader'], out.inputs['Surface'])
    return m


def flow_group():
    ng = bpy.data.node_groups.get('MS_FlowParticles')
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new('MS_FlowParticles', 'GeometryNodeTree')
    ng.is_modifier = True
    _sock(ng, 'Geometry', 'INPUT', 'NodeSocketGeometry')
    _sock(ng, 'Curves', 'INPUT', 'NodeSocketObject')
    _sock(ng, 'Streak', 'INPUT', 'NodeSocketObject')
    _sock(ng, 'Material', 'INPUT', 'NodeSocketMaterial')
    _sock(ng, 'Time Offset', 'INPUT', 'NodeSocketFloat', 0.0)
    _sock(ng, 'Speed', 'INPUT', 'NodeSocketFloat', 1.0)
    _sock(ng, 'Reveal', 'INPUT', 'NodeSocketFloat', 1.0)
    _sock(ng, 'Reveal Soft', 'INPUT', 'NodeSocketFloat', 0.04)
    _sock(ng, 'Length', 'INPUT', 'NodeSocketFloat', 0.012)
    _sock(ng, 'Radius', 'INPUT', 'NodeSocketFloat', 0.00035)
    _sock(ng, 'Gain', 'INPUT', 'NodeSocketFloat', 1.0)
    _sock(ng, 'Fade In', 'INPUT', 'NodeSocketFloat', 0.06)
    _sock(ng, 'Fade Out', 'INPUT', 'NodeSocketFloat', 0.1)
    _sock(ng, 'Hot Stretch', 'INPUT', 'NodeSocketFloat', 0.0)
    _sock(ng, 'Hot Gain', 'INPUT', 'NodeSocketFloat', 1.0)
    _sock(ng, 'Geometry', 'OUTPUT', 'NodeSocketGeometry')
    N = ng.nodes
    L = ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')

    def node(t, **props):
        n = N.new(t)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def math_(op, a=None, b=None, c=None):
        n = node('ShaderNodeMath', operation=op)
        for i, x in enumerate((a, b, c)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L.new(x, n.inputs[i])
        return n.outputs[0]

    def attr(name, dt='FLOAT'):
        n = node('GeometryNodeInputNamedAttribute', data_type=dt)
        n.inputs['Name'].default_value = name
        return n.outputs['Attribute']

    st = node('GeometryNodeInputSceneTime')
    t = math_('MULTIPLY_ADD', st.outputs['Seconds'], gi.outputs['Speed'], gi.outputs['Time Offset'])
    u = math_('FRACT', math_('MULTIPLY_ADD', attr('spd'), t, attr('phase')))
    oc = node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    L.new(gi.outputs['Curves'], oc.inputs['Object'])
    sc = node('GeometryNodeSampleCurve', use_all_curves=False)
    sc.mode = 'FACTOR'
    L.new(oc.outputs['Geometry'], sc.inputs['Curves'])
    L.new(u, sc.inputs['Factor'])
    L.new(attr('cidx', 'INT'), sc.inputs['Curve Index'])
    sp = node('GeometryNodeSetPosition')
    L.new(gi.outputs['Geometry'], sp.inputs['Geometry'])
    L.new(sc.outputs['Position'], sp.inputs['Position'])
    fin = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
    fin.inputs['From Min'].default_value = 0.0
    L.new(gi.outputs['Fade In'], fin.inputs['From Max'])
    L.new(u, fin.inputs['Value'])
    fout = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
    L.new(math_('SUBTRACT', 1.0, gi.outputs['Fade Out']), fout.inputs['From Min'])
    fout.inputs['From Max'].default_value = 1.0
    fout.inputs['To Min'].default_value = 1.0
    fout.inputs['To Max'].default_value = 0.0
    L.new(u, fout.inputs['Value'])
    rv = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
    L.new(gi.outputs['Reveal'], rv.inputs['From Min'])
    L.new(math_('SUBTRACT', gi.outputs['Reveal'], gi.outputs['Reveal Soft']), rv.inputs['From Max'])
    L.new(u, rv.inputs['Value'])
    env = math_('MULTIPLY', math_('MULTIPLY', fin.outputs['Result'], fout.outputs['Result']), rv.outputs['Result'])
    env = math_('MULTIPLY', env, attr('size'))
    ar = node('FunctionNodeAlignRotationToVector', axis='Z')
    L.new(sc.outputs['Tangent'], ar.inputs['Vector'])
    os_ = node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    L.new(gi.outputs['Streak'], os_.inputs['Object'])
    rad = math_('MULTIPLY', gi.outputs['Radius'], env)
    hv = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
    L.new(attr('h0'), hv.inputs['From Min'])
    L.new(attr('h1'), hv.inputs['From Max'])
    L.new(u, hv.inputs['Value'])
    lng = math_('MULTIPLY', math_('MULTIPLY', gi.outputs['Length'], env),
                math_('MULTIPLY_ADD', gi.outputs['Hot Stretch'], hv.outputs['Result'], 1.0))
    cx = node('ShaderNodeCombineXYZ')
    L.new(rad, cx.inputs['X'])
    L.new(rad, cx.inputs['Y'])
    L.new(lng, cx.inputs['Z'])
    gt = math_('GREATER_THAN', env, 0.001)
    iop = node('GeometryNodeInstanceOnPoints')
    L.new(sp.outputs['Geometry'], iop.inputs['Points'])
    L.new(gt, iop.inputs['Selection'])
    L.new(os_.outputs['Geometry'], iop.inputs['Instance'])
    L.new(ar.outputs['Rotation'], iop.inputs['Rotation'])
    L.new(cx.outputs['Vector'], iop.inputs['Scale'])
    s1 = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='INSTANCE')
    s1.inputs['Name'].default_value = 'hotmix'
    L.new(iop.outputs['Instances'], s1.inputs['Geometry'])
    L.new(hv.outputs['Result'], s1.inputs['Value'])
    s2 = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='INSTANCE')
    s2.inputs['Name'].default_value = 'gain'
    L.new(s1.outputs['Geometry'], s2.inputs['Geometry'])
    hg = math_('MULTIPLY_ADD', math_('SUBTRACT', gi.outputs['Hot Gain'], 1.0), hv.outputs['Result'], 1.0)
    L.new(math_('MULTIPLY', math_('MULTIPLY', gi.outputs['Gain'], attr('bright')), hg), s2.inputs['Value'])
    s3 = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='INSTANCE')
    s3.inputs['Name'].default_value = 'phase'
    L.new(s2.outputs['Geometry'], s3.inputs['Geometry'])
    L.new(attr('phase'), s3.inputs['Value'])
    rz = node('GeometryNodeRealizeInstances')
    L.new(s3.outputs['Geometry'], rz.inputs['Geometry'])
    sm = node('GeometryNodeSetMaterial')
    L.new(rz.outputs['Geometry'], sm.inputs['Geometry'])
    L.new(gi.outputs['Material'], sm.inputs['Material'])
    L.new(sm.outputs['Geometry'], go.inputs['Geometry'])
    return ng


def set_inputs(mod, **vals):
    for item in mod.node_group.interface.items_tree:
        if getattr(item, 'in_out', None) == 'INPUT' and item.name.replace(' ', '_').lower() in vals:
            mod[item.identifier] = vals[item.name.replace(' ', '_').lower()]


def input_id(mod, name):
    for item in mod.node_group.interface.items_tree:
        if getattr(item, 'in_out', None) == 'INPUT' and item.name == name:
            return item.identifier
    return None


def curves_object(name, coll, paths_m):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    for p in paths_m:
        sp = cu.splines.new('POLY')
        sp.points.add(len(p) - 1)
        for i, (x, y, z) in enumerate(p):
            sp.points[i].co = (x, y, z, 1.0)
    ob = bpy.data.objects.new(name, cu)
    coll.objects.link(ob)
    ob.hide_render = True
    ob.hide_viewport = True
    return ob


def flow_system(name, coll, paths_mm, per_path=6, speed_mm_s=60.0, size_range=(0.7, 1.3), heat_u=None,
                seed=1, length_mm=12.0, radius_mm=0.35, gain=1.0, color=CYAN, strength=6.0, bright_range=(0.6, 1.0),
                material=None):
    rng = np.random.default_rng(seed)
    paths_m = []
    lengths = []
    for p in paths_mm:
        p = np.asarray(p, dtype=np.float64)
        paths_m.append(p * MM)
        lengths.append(float(np.sum(np.linalg.norm(np.diff(p, axis=0), axis=1))))
    cu = curves_object(name + '_Paths', coll, paths_m)
    n = len(paths_mm) * per_path
    cidx = np.repeat(np.arange(len(paths_mm)), per_path)
    phase = rng.random(n)
    spd = np.array([speed_mm_s / lengths[c] for c in cidx]) * rng.uniform(0.85, 1.15, n)
    size = rng.uniform(*size_range, n)
    bright = rng.uniform(*bright_range, n)
    if heat_u is None:
        h0 = np.full(n, 5.0)
        h1 = np.full(n, 6.0)
    else:
        h0 = np.array([heat_u[c][0] for c in cidx])
        h1 = np.array([heat_u[c][1] for c in cidx])
    me = points_mesh(name, np.zeros((n, 3)), {
        'phase': ('FLOAT', phase), 'spd': ('FLOAT', spd), 'size': ('FLOAT', size), 'bright': ('FLOAT', bright),
        'h0': ('FLOAT', h0), 'h1': ('FLOAT', h1)})
    a = me.attributes.new('cidx', 'INT', 'POINT')
    a.data.foreach_set('value', cidx.astype(np.int32))
    ob = obj(name, me, coll)
    st = bpy.data.objects.get('FX_Streak_Unit')
    if st is None:
        st = obj('FX_Streak_Unit', streak_mesh('FX_Streak_Unit'), coll)
        st.hide_render = True
        st.hide_viewport = True
    mat = material or fx_emit_material('MS_FX_Air_' + name, color, strength=strength)
    mod = ob.modifiers.new('Flow', 'NODES')
    mod.node_group = flow_group()
    mod[input_id(mod, 'Curves')] = cu
    mod[input_id(mod, 'Streak')] = st
    mod[input_id(mod, 'Material')] = mat
    mod[input_id(mod, 'Length')] = length_mm * MM
    mod[input_id(mod, 'Radius')] = radius_mm * MM
    mod[input_id(mod, 'Gain')] = gain
    ob['fx'] = 'flow'
    return ob, cu, mod


def hole_streak_group():
    ng = bpy.data.node_groups.get('MS_HoleStreaks')
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new('MS_HoleStreaks', 'GeometryNodeTree')
    ng.is_modifier = True
    _sock(ng, 'Geometry', 'INPUT', 'NodeSocketGeometry')
    _sock(ng, 'Points', 'INPUT', 'NodeSocketObject')
    _sock(ng, 'Streak', 'INPUT', 'NodeSocketObject')
    _sock(ng, 'Material', 'INPUT', 'NodeSocketMaterial')
    _sock(ng, 'Reveal Deg', 'INPUT', 'NodeSocketFloat', 360.0)
    _sock(ng, 'Reveal Soft Deg', 'INPUT', 'NodeSocketFloat', 25.0)
    _sock(ng, 'Start Deg', 'INPUT', 'NodeSocketFloat', 0.0)
    _sock(ng, 'Length', 'INPUT', 'NodeSocketFloat', 0.007)
    _sock(ng, 'Radius', 'INPUT', 'NodeSocketFloat', 0.00028)
    _sock(ng, 'Offset', 'INPUT', 'NodeSocketFloat', 0.0025)
    _sock(ng, 'Every Nth', 'INPUT', 'NodeSocketInt', 1, 1, 64)
    _sock(ng, 'Geometry', 'OUTPUT', 'NodeSocketGeometry')
    N = ng.nodes
    L = ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')

    def node(t, **props):
        n = N.new(t)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def math_(op, a=None, b=None, c=None):
        n = node('ShaderNodeMath', operation=op)
        for i, x in enumerate((a, b, c)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L.new(x, n.inputs[i])
        return n.outputs[0]

    oi = node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    L.new(gi.outputs['Points'], oi.inputs['Object'])
    nd = node('GeometryNodeInputNamedAttribute', data_type='FLOAT_VECTOR')
    nd.inputs['Name'].default_value = 'dir'
    pos = node('GeometryNodeInputPosition')
    sep = node('ShaderNodeSeparateXYZ')
    L.new(pos.outputs['Position'], sep.inputs['Vector'])
    ang = math_('DEGREES', math_('ARCTAN2', sep.outputs['Y'], sep.outputs['X']))
    rel = math_('FLOORED_MODULO', math_('SUBTRACT', math_('ADD', ang, 720.0), gi.outputs['Start Deg']), 360.0)
    rv = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
    L.new(gi.outputs['Reveal Deg'], rv.inputs['From Min'])
    L.new(math_('SUBTRACT', gi.outputs['Reveal Deg'], gi.outputs['Reveal Soft Deg']), rv.inputs['From Max'])
    L.new(rel, rv.inputs['Value'])
    idx = node('GeometryNodeInputIndex')
    md = math_('FLOORED_MODULO', idx.outputs['Index'], gi.outputs['Every Nth'])
    keep = math_('LESS_THAN', md, 0.5)
    env = math_('MULTIPLY', rv.outputs['Result'], keep)
    sp = node('GeometryNodeSetPosition')
    L.new(oi.outputs['Geometry'], sp.inputs['Geometry'])
    vs = node('ShaderNodeVectorMath', operation='SCALE')
    L.new(nd.outputs['Attribute'], vs.inputs[0])
    L.new(gi.outputs['Offset'], vs.inputs['Scale'])
    L.new(vs.outputs['Vector'], sp.inputs['Offset'])
    ar = node('FunctionNodeAlignRotationToVector', axis='Z')
    L.new(nd.outputs['Attribute'], ar.inputs['Vector'])
    os_ = node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    L.new(gi.outputs['Streak'], os_.inputs['Object'])
    cx = node('ShaderNodeCombineXYZ')
    rr = math_('MULTIPLY', gi.outputs['Radius'], env)
    L.new(rr, cx.inputs['X'])
    L.new(rr, cx.inputs['Y'])
    L.new(math_('MULTIPLY', gi.outputs['Length'], math_('POWER', env, 0.5)), cx.inputs['Z'])
    iop = node('GeometryNodeInstanceOnPoints')
    L.new(sp.outputs['Geometry'], iop.inputs['Points'])
    L.new(math_('GREATER_THAN', env, 0.002), iop.inputs['Selection'])
    L.new(os_.outputs['Geometry'], iop.inputs['Instance'])
    L.new(ar.outputs['Rotation'], iop.inputs['Rotation'])
    L.new(cx.outputs['Vector'], iop.inputs['Scale'])
    rnd = node('FunctionNodeRandomValue', data_type='FLOAT')
    s1 = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='INSTANCE')
    s1.inputs['Name'].default_value = 'phase'
    L.new(iop.outputs['Instances'], s1.inputs['Geometry'])
    L.new(rnd.outputs[1], s1.inputs['Value'])
    s2 = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='INSTANCE')
    s2.inputs['Name'].default_value = 'gain'
    L.new(s1.outputs['Geometry'], s2.inputs['Geometry'])
    L.new(env, s2.inputs['Value'])
    rz = node('GeometryNodeRealizeInstances')
    L.new(s2.outputs['Geometry'], rz.inputs['Geometry'])
    sm = node('GeometryNodeSetMaterial')
    L.new(rz.outputs['Geometry'], sm.inputs['Geometry'])
    L.new(gi.outputs['Material'], sm.inputs['Material'])
    L.new(sm.outputs['Geometry'], go.inputs['Geometry'])
    return ng


def hole_streaks(coll, pts_obj, name='FX_Hole_Streaks'):
    me = mesh_np(name, np.zeros((0, 3)), [])
    ob = obj(name, me, coll)
    st = bpy.data.objects.get('FX_Streak_Unit')
    if st is None:
        st = obj('FX_Streak_Unit', streak_mesh('FX_Streak_Unit'), coll)
        st.hide_render = True
        st.hide_viewport = True
    mat = fx_emit_material('MS_FX_HoleStreak', CYAN, strength=9.0, pulse=True, tail_power=1.2)
    mod = ob.modifiers.new('HoleStreaks', 'NODES')
    mod.node_group = hole_streak_group()
    mod[input_id(mod, 'Points')] = pts_obj
    mod[input_id(mod, 'Streak')] = st
    mod[input_id(mod, 'Material')] = mat
    ob['fx'] = 'hole_streaks'
    ob['note'] = 'one cyan streak per foot hole along its drill axis; animate modifier input "Reveal Deg" 0->360 to reveal around the ring'
    return ob


def foot_inner_glow(coll):
    prof = [(70.0, 9.45), (89.5, 9.45)]
    v, f, _ = revolve_profile(prof, 256)
    me = mesh_np('FX_Foot_InnerGlow', v * MM, f)
    m = bpy.data.materials.get('MS_FX_InnerGlow') or bpy.data.materials.new('MS_FX_InnerGlow')
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (0.75, 0.9, 1.0, 1.0)
    ag = nt.nodes.new('ShaderNodeAttribute')
    ag.attribute_type = 'OBJECT'
    ag.attribute_name = 'glow'
    nt.links.new(ag.outputs['Fac'], em.inputs['Strength'])
    nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
    ob = obj('FX_Foot_InnerGlow', me, coll, mat=m)
    ob['glow'] = 25.0
    ob['note'] = 'emissive ring inside the foot cavity (under the PSU): makes every angled bore glow from inside; animate ["glow"]'
    return ob


def foot_section(coll, cover, mats, phi_deg=-90.0, half_width_deg=9.0, name='FX_Foot_Section'):
    nrow = D.FOOT_HOLES_PER_ROW
    step = 360.0 / nrow
    phi_c = round(phi_deg / step) * step
    a0 = math.radians(phi_c - half_width_deg)
    a1 = math.radians(phi_c)
    pts = []
    for a in np.linspace(a0, a1, 24):
        pts.append((60.0 * math.cos(a), 60.0 * math.sin(a)))
    for a in np.linspace(a1, a0, 24):
        pts.append((101.0 * math.cos(a), 101.0 * math.sin(a)))
    pts = np.array(pts)
    from .util import slab_from_loops
    v, f = slab_from_loops(pts, [], -2.0, 14.0)
    acc = MeshAccum()
    acc.add(v, f)
    cut_me = acc.build(name + '_Wedge')
    wedge = obj(name + '_Wedge', cut_me, coll, mat=mats['al_section'])
    wedge.hide_render = True
    wedge.hide_viewport = True
    me = mesh_np(name, np.zeros((0, 3)), [])
    ob = obj(name, me, coll)
    ng = bpy.data.node_groups.new('MS_FootSection', 'GeometryNodeTree')
    ng.is_modifier = True
    _sock(ng, 'Geometry', 'INPUT', 'NodeSocketGeometry')
    _sock(ng, 'Geometry', 'OUTPUT', 'NodeSocketGeometry')
    N = ng.nodes
    L = ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    oc = N.new('GeometryNodeObjectInfo')
    oc.transform_space = 'ORIGINAL'
    oc.inputs['Object'].default_value = cover
    ow = N.new('GeometryNodeObjectInfo')
    ow.transform_space = 'ORIGINAL'
    ow.inputs['Object'].default_value = wedge
    mb = N.new('GeometryNodeMeshBoolean')
    mb.operation = 'INTERSECT'
    mb.solver = 'MANIFOLD'
    L.new(oc.outputs['Geometry'], mb.inputs['Mesh 2'])
    L.new(ow.outputs['Geometry'], mb.inputs['Mesh 2'])
    ss = N.new('GeometryNodeSetShadeSmooth')
    ss.domain = 'FACE'
    L.new(mb.outputs['Mesh'], ss.inputs['Mesh'])
    ea = N.new('GeometryNodeInputMeshEdgeAngle')
    cmp_ = N.new('FunctionNodeCompare')
    cmp_.data_type = 'FLOAT'
    cmp_.operation = 'LESS_THAN'
    cmp_.inputs[1].default_value = math.radians(30)
    L.new(ea.outputs['Unsigned Angle'], cmp_.inputs[0])
    se = N.new('GeometryNodeSetShadeSmooth')
    se.domain = 'EDGE'
    L.new(ss.outputs['Mesh'], se.inputs['Mesh'])
    L.new(cmp_.outputs['Result'], se.inputs['Shade Smooth'])
    L.new(se.outputs['Mesh'], go.inputs['Geometry'])
    mod = ob.modifiers.new('Section', 'NODES')
    mod.node_group = ng
    for m in (mats['al'], mats['al_drill'], mats['al_section']):
        ob.data.materials.append(m)
    ob['fx'] = 'foot_section'
    ob['section_phi_deg'] = phi_c
    ob['note'] = 'segment of the machined foot cut on a radial plane through a column of holes: shows the slanted bore channels'
    return ob


def heat_volume(name, coll, center_mm, size_mm, color=AMBER, strength=0.6, rise_mm_s=20.0, scale=60.0):
    acc = MeshAccum()
    acc.add_box(center_mm, size_mm)
    me = acc.build(name)
    m = bpy.data.materials.new('MS_FX_Heat_' + name)
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    N = nt.nodes
    L = nt.links
    for n in list(N):
        N.remove(n)
    out = N.new('ShaderNodeOutputMaterial')
    tc = N.new('ShaderNodeTexCoord')
    tv = frame_time_value(nt)
    mp = N.new('ShaderNodeMapping')
    L.new(tc.outputs['Generated'], mp.inputs['Vector'])
    cxyz = N.new('ShaderNodeCombineXYZ')
    rise = N.new('ShaderNodeMath')
    rise.operation = 'MULTIPLY'
    rise.inputs[1].default_value = -rise_mm_s / max(size_mm[2], 1.0)
    L.new(tv.outputs[0], rise.inputs[0])
    L.new(rise.outputs[0], cxyz.inputs['Z'])
    L.new(cxyz.outputs['Vector'], mp.inputs['Location'])
    nz = N.new('ShaderNodeTexNoise')
    nz.noise_dimensions = '4D'
    nz.inputs['Scale'].default_value = 3.0
    nz.inputs['Detail'].default_value = 4.0
    nz.inputs['Roughness'].default_value = 0.55
    nz.inputs['Distortion'].default_value = 0.6
    L.new(mp.outputs['Vector'], nz.inputs['Vector'])
    w = N.new('ShaderNodeMath')
    w.operation = 'MULTIPLY'
    w.inputs[1].default_value = 0.35
    L.new(tv.outputs[0], w.inputs[0])
    L.new(w.outputs[0], nz.inputs['W'])
    cr = N.new('ShaderNodeMapRange')
    cr.inputs['From Min'].default_value = 0.44
    cr.inputs['From Max'].default_value = 0.76
    L.new(nz.outputs['Fac'], cr.inputs['Value'])
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(tc.outputs['Generated'], sep.inputs['Vector'])
    gz = N.new('ShaderNodeMapRange')
    gz.interpolation_type = 'SMOOTHSTEP'
    gz.inputs['From Min'].default_value = 1.0
    gz.inputs['From Max'].default_value = 0.0
    L.new(sep.outputs['Z'], gz.inputs['Value'])
    gz2 = N.new('ShaderNodeMapRange')
    gz2.interpolation_type = 'SMOOTHSTEP'
    gz2.inputs['From Min'].default_value = 0.0
    gz2.inputs['From Max'].default_value = 0.12
    L.new(sep.outputs['Z'], gz2.inputs['Value'])
    gx = N.new('ShaderNodeMath')
    gx.operation = 'PINGPONG'
    gx.inputs[1].default_value = 0.5
    L.new(sep.outputs['X'], gx.inputs[0])
    gxs = N.new('ShaderNodeMapRange')
    gxs.interpolation_type = 'SMOOTHSTEP'
    gxs.inputs['From Min'].default_value = 0.0
    gxs.inputs['From Max'].default_value = 0.25
    L.new(gx.outputs[0], gxs.inputs['Value'])
    gy = N.new('ShaderNodeMath')
    gy.operation = 'PINGPONG'
    gy.inputs[1].default_value = 0.5
    L.new(sep.outputs['Y'], gy.inputs[0])
    gys = N.new('ShaderNodeMapRange')
    gys.interpolation_type = 'SMOOTHSTEP'
    gys.inputs['From Min'].default_value = 0.0
    gys.inputs['From Max'].default_value = 0.25
    L.new(gy.outputs[0], gys.inputs['Value'])
    prod = cr.outputs['Result']
    for g in (gz.outputs['Result'], gz2.outputs['Result'], gxs.outputs['Result'], gys.outputs['Result']):
        mm_ = N.new('ShaderNodeMath')
        mm_.operation = 'MULTIPLY'
        L.new(prod, mm_.inputs[0])
        L.new(g, mm_.inputs[1])
        prod = mm_.outputs[0]
    ag = N.new('ShaderNodeAttribute')
    ag.attribute_type = 'OBJECT'
    ag.attribute_name = 'glow'
    mm_ = N.new('ShaderNodeMath')
    mm_.operation = 'MULTIPLY'
    L.new(prod, mm_.inputs[0])
    L.new(ag.outputs['Fac'], mm_.inputs[1])
    em = N.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = tuple(color) + (1.0,)
    L.new(mm_.outputs[0], em.inputs['Strength'])
    L.new(em.outputs['Emission'], out.inputs['Volume'])
    ob = obj(name, me, coll, mat=m)
    ob['glow'] = strength
    ob.visible_shadow = False
    ob['fx'] = 'heat_volume'
    return ob





def disk_mesh(name, r=1.0, n=24):
    verts = [(0.0, 0.0, 0.0)] + [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), 0.0) for i in range(n)]
    faces = [(0, i + 1, (i + 1) % n + 1) for i in range(n)]
    me = mesh_np(name, np.array(verts), faces)
    return me


def bore_glow_material():
    m = bpy.data.materials.get('MS_FX_BoreGlow')
    if m is not None:
        return m
    m = bpy.data.materials.new('MS_FX_BoreGlow')
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    N = nt.nodes
    L = nt.links
    for n in list(N):
        N.remove(n)
    out = N.new('ShaderNodeOutputMaterial')
    lw = N.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.5
    inv = N.new('ShaderNodeMath')
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    L.new(lw.outputs['Facing'], inv.inputs[1])
    pw = N.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = 5.0
    L.new(inv.outputs[0], pw.inputs[0])
    ga = N.new('ShaderNodeAttribute')
    ga.attribute_type = 'GEOMETRY'
    ga.attribute_name = 'gain'
    og = N.new('ShaderNodeAttribute')
    og.attribute_type = 'OBJECT'
    og.attribute_name = 'glow'
    m1 = N.new('ShaderNodeMath')
    m1.operation = 'MULTIPLY'
    L.new(pw.outputs[0], m1.inputs[0])
    L.new(ga.outputs['Fac'], m1.inputs[1])
    m2 = N.new('ShaderNodeMath')
    m2.operation = 'MULTIPLY'
    L.new(m1.outputs[0], m2.inputs[0])
    L.new(og.outputs['Fac'], m2.inputs[1])
    em = N.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (0.78, 0.93, 1.0, 1.0)
    L.new(m2.outputs[0], em.inputs['Strength'])
    tr = N.new('ShaderNodeBsdfTransparent')
    add = N.new('ShaderNodeAddShader')
    L.new(tr.outputs['BSDF'], add.inputs[0])
    L.new(em.outputs['Emission'], add.inputs[1])
    L.new(add.outputs['Shader'], out.inputs['Surface'])
    return m


def bore_glow(coll, pts_obj, name='FX_Bore_Glow'):
    me = mesh_np(name, np.zeros((0, 3)), [])
    ob = obj(name, me, coll)
    dk = bpy.data.objects.get('FX_Disk_Unit')
    if dk is None:
        dk = obj('FX_Disk_Unit', disk_mesh('FX_Disk_Unit'), coll)
        dk.hide_render = True
        dk.hide_viewport = True
    mod = ob.modifiers.new('BoreGlow', 'NODES')
    mod.node_group = hole_streak_group()
    mod[input_id(mod, 'Points')] = pts_obj
    mod[input_id(mod, 'Streak')] = dk
    mod[input_id(mod, 'Material')] = bore_glow_material()
    mod[input_id(mod, 'Length')] = 1.0
    mod[input_id(mod, 'Radius')] = 0.00075
    mod[input_id(mod, 'Offset')] = 0.0027
    mod[input_id(mod, 'Reveal Soft Deg')] = 0.001
    ob['glow'] = 40.0
    ob['fx'] = 'bore_glow'
    ob['note'] = 'directional emitter disk at the inner end of every bore, facing out along the drill axis: holes glow only when seen along their (rotating) axis'
    return ob



def build_base_fx(C, mats, cover, pts_obj):
    fxc = C['FX']
    glow = foot_inner_glow(fxc)
    streaks = hole_streaks(fxc, pts_obj)
    bglow = bore_glow(fxc, pts_obj)
    sec = foot_section(C['Showcase_FootSection'], cover, mats)
    for o in (glow, streaks, bglow):
        o.hide_render = True
    return dict(inner_glow=glow, hole_streaks=streaks, bore_glow=bglow, section=sec)


def flow_staged_group(nstage=6):
    gname = 'MS_FlowStaged%d' % nstage
    ng = bpy.data.node_groups.get(gname)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(gname, 'GeometryNodeTree')
    ng.is_modifier = True
    _sock(ng, 'Geometry', 'INPUT', 'NodeSocketGeometry')
    _sock(ng, 'Curves', 'INPUT', 'NodeSocketObject')
    _sock(ng, 'Streak', 'INPUT', 'NodeSocketObject')
    _sock(ng, 'Material', 'INPUT', 'NodeSocketMaterial')
    _sock(ng, 'Time Offset', 'INPUT', 'NodeSocketFloat', 0.0)
    _sock(ng, 'Speed', 'INPUT', 'NodeSocketFloat', 1.0)
    _sock(ng, 'Reveal', 'INPUT', 'NodeSocketFloat', float(nstage))
    _sock(ng, 'Reveal Soft', 'INPUT', 'NodeSocketFloat', 0.12)
    _sock(ng, 'Hide Before', 'INPUT', 'NodeSocketFloat', -1.0)
    _sock(ng, 'Length', 'INPUT', 'NodeSocketFloat', 0.012)
    _sock(ng, 'Radius', 'INPUT', 'NodeSocketFloat', 0.00035)
    _sock(ng, 'Gain', 'INPUT', 'NodeSocketFloat', 1.0)
    _sock(ng, 'Fade In', 'INPUT', 'NodeSocketFloat', 0.03)
    _sock(ng, 'Fade Out', 'INPUT', 'NodeSocketFloat', 0.05)
    _sock(ng, 'Hot Stretch', 'INPUT', 'NodeSocketFloat', 0.0)
    _sock(ng, 'Hot Gain', 'INPUT', 'NodeSocketFloat', 1.0)
    _sock(ng, 'Geometry', 'OUTPUT', 'NodeSocketGeometry')
    N = ng.nodes
    L = ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')

    def node(t, **props):
        n = N.new(t)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def math_(op, a=None, b=None, c=None):
        n = node('ShaderNodeMath', operation=op)
        for i, x in enumerate((a, b, c)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L.new(x, n.inputs[i])
        return n.outputs[0]

    def attr(name, dt='FLOAT'):
        n = node('GeometryNodeInputNamedAttribute', data_type=dt)
        n.inputs['Name'].default_value = name
        return n.outputs['Attribute']

    st = node('GeometryNodeInputSceneTime')
    t = math_('MULTIPLY_ADD', st.outputs['Seconds'], gi.outputs['Speed'], gi.outputs['Time Offset'])
    tau = math_('FRACT', math_('MULTIPLY_ADD', attr('spd'), t, attr('phase')))
    s = None
    u = None
    for k in range(nstage):
        mr = node('ShaderNodeMapRange', interpolation_type='LINEAR', clamp=True)
        L.new(attr('c%d' % k), mr.inputs['From Min'])
        L.new(attr('c%d' % (k + 1)), mr.inputs['From Max'])
        L.new(tau, mr.inputs['Value'])
        s = mr.outputs['Result'] if s is None else math_('ADD', s, mr.outputs['Result'])
        db = math_('SUBTRACT', attr('b%d' % (k + 1)), attr('b%d' % k))
        uk = math_('MULTIPLY', mr.outputs['Result'], db)
        u = uk if u is None else math_('ADD', u, uk)
    oc = node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    L.new(gi.outputs['Curves'], oc.inputs['Object'])
    sc = node('GeometryNodeSampleCurve', use_all_curves=False)
    sc.mode = 'FACTOR'
    L.new(oc.outputs['Geometry'], sc.inputs['Curves'])
    L.new(u, sc.inputs['Factor'])
    L.new(attr('cidx', 'INT'), sc.inputs['Curve Index'])
    sp = node('GeometryNodeSetPosition')
    L.new(gi.outputs['Geometry'], sp.inputs['Geometry'])
    L.new(sc.outputs['Position'], sp.inputs['Position'])
    fin = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
    fin.inputs['From Min'].default_value = 0.0
    L.new(gi.outputs['Fade In'], fin.inputs['From Max'])
    L.new(tau, fin.inputs['Value'])
    fout = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
    L.new(math_('SUBTRACT', 1.0, gi.outputs['Fade Out']), fout.inputs['From Min'])
    fout.inputs['From Max'].default_value = 1.0
    fout.inputs['To Min'].default_value = 1.0
    fout.inputs['To Max'].default_value = 0.0
    L.new(tau, fout.inputs['Value'])
    rv = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
    L.new(gi.outputs['Reveal'], rv.inputs['From Min'])
    L.new(math_('SUBTRACT', gi.outputs['Reveal'], gi.outputs['Reveal Soft']), rv.inputs['From Max'])
    L.new(s, rv.inputs['Value'])
    hb = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
    L.new(gi.outputs['Hide Before'], hb.inputs['From Min'])
    L.new(math_('ADD', gi.outputs['Hide Before'], gi.outputs['Reveal Soft']), hb.inputs['From Max'])
    L.new(s, hb.inputs['Value'])
    env = math_('MULTIPLY', math_('MULTIPLY', fin.outputs['Result'], fout.outputs['Result']), rv.outputs['Result'])
    env = math_('MULTIPLY', env, hb.outputs['Result'])
    env = math_('MULTIPLY', env, attr('size'))
    ar = node('FunctionNodeAlignRotationToVector', axis='Z')
    L.new(sc.outputs['Tangent'], ar.inputs['Vector'])
    os_ = node('GeometryNodeObjectInfo', transform_space='ORIGINAL')
    L.new(gi.outputs['Streak'], os_.inputs['Object'])
    rad = math_('MULTIPLY', gi.outputs['Radius'], env)
    hv = node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
    L.new(attr('h0'), hv.inputs['From Min'])
    L.new(attr('h1'), hv.inputs['From Max'])
    L.new(u, hv.inputs['Value'])
    lng = math_('MULTIPLY', math_('MULTIPLY', gi.outputs['Length'], env),
                math_('MULTIPLY_ADD', gi.outputs['Hot Stretch'], hv.outputs['Result'], 1.0))
    cx = node('ShaderNodeCombineXYZ')
    L.new(rad, cx.inputs['X'])
    L.new(rad, cx.inputs['Y'])
    L.new(lng, cx.inputs['Z'])
    iop = node('GeometryNodeInstanceOnPoints')
    L.new(sp.outputs['Geometry'], iop.inputs['Points'])
    L.new(math_('GREATER_THAN', env, 0.001), iop.inputs['Selection'])
    L.new(os_.outputs['Geometry'], iop.inputs['Instance'])
    L.new(ar.outputs['Rotation'], iop.inputs['Rotation'])
    L.new(cx.outputs['Vector'], iop.inputs['Scale'])
    s1 = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='INSTANCE')
    s1.inputs['Name'].default_value = 'hotmix'
    L.new(iop.outputs['Instances'], s1.inputs['Geometry'])
    L.new(hv.outputs['Result'], s1.inputs['Value'])
    s2 = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='INSTANCE')
    s2.inputs['Name'].default_value = 'gain'
    L.new(s1.outputs['Geometry'], s2.inputs['Geometry'])
    hg = math_('MULTIPLY_ADD', math_('SUBTRACT', gi.outputs['Hot Gain'], 1.0), hv.outputs['Result'], 1.0)
    L.new(math_('MULTIPLY', math_('MULTIPLY', gi.outputs['Gain'], attr('bright')), hg), s2.inputs['Value'])
    s3 = node('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='INSTANCE')
    s3.inputs['Name'].default_value = 'phase'
    L.new(s2.outputs['Geometry'], s3.inputs['Geometry'])
    L.new(attr('phase'), s3.inputs['Value'])
    rz = node('GeometryNodeRealizeInstances')
    L.new(s3.outputs['Geometry'], rz.inputs['Geometry'])
    sm = node('GeometryNodeSetMaterial')
    L.new(rz.outputs['Geometry'], sm.inputs['Geometry'])
    L.new(gi.outputs['Material'], sm.inputs['Material'])
    L.new(sm.outputs['Geometry'], go.inputs['Geometry'])
    return ng


def flow_staged_system(name, coll, lines, stage_keys, per_line=8, speed_mm_s=60.0, size_range=(0.75, 1.25),
                       heat_stage=None, heat_span=(0.1, 0.95), seed=1, length_mm=12.0, radius_mm=0.35, gain=1.0,
                       color=CYAN, strength=3.0, bright_range=(0.6, 1.0), material=None, line_speed=None,
                       stage_speed=None):
    rng = np.random.default_rng(seed)
    nst = len(stage_keys)
    paths_m = []
    bounds = []
    tbounds = []
    heat = []
    lengths = []
    durs = []
    sspd = list(stage_speed) if stage_speed is not None else [1.0] * nst
    for ln in lines:
        segs = []
        for k, key in enumerate(stage_keys):
            p = np.asarray(ln[key], dtype=np.float64)
            if segs and np.linalg.norm(p[0] - segs[-1][-1]) < 1e-6:
                p = p[1:]
            segs.append(p)
        lens = []
        prev = None
        for p in segs:
            q = p if prev is None else np.vstack([prev[-1:], p])
            lens.append(float(np.sum(np.linalg.norm(np.diff(q, axis=0), axis=1))) if len(q) > 1 else 0.0)
            prev = p
        tot = sum(lens)
        cum = np.concatenate([[0.0], np.cumsum(lens)]) / tot
        b = [float(x) for x in cum]
        for k in range(1, nst + 1):
            if b[k] <= b[k - 1]:
                b[k] = b[k - 1] + 1e-5
        bounds.append(b)
        tl = [lens[k] / sspd[k] for k in range(nst)]
        tt = sum(tl)
        c = [float(x) for x in np.concatenate([[0.0], np.cumsum(tl)]) / tt]
        for k in range(1, nst + 1):
            if c[k] <= c[k - 1]:
                c[k] = c[k - 1] + 1e-5
        tbounds.append(c)
        durs.append(tt)
        allp = np.vstack(segs)
        paths_m.append(allp * MM)
        lengths.append(tot)
        if heat_stage is not None:
            k = stage_keys.index(heat_stage)
            a0, a1 = b[k], b[k + 1]
            heat.append((a0 + heat_span[0] * (a1 - a0), a0 + heat_span[1] * (a1 - a0)))
        else:
            heat.append((5.0, 6.0))
    cu = curves_object(name + '_Paths', coll, paths_m)
    nl = len(lines)
    n = nl * per_line
    cidx = np.repeat(np.arange(nl), per_line)
    phase = (np.tile(np.arange(per_line), nl) + rng.random(n) * 0.85) / per_line
    sp_line = np.array(line_speed if line_speed is not None else [1.0] * nl)
    spd = np.array([speed_mm_s * sp_line[c] / durs[c] for c in cidx]) * rng.uniform(0.92, 1.08, n)
    size = rng.uniform(*size_range, n)
    bright = rng.uniform(*bright_range, n)
    attrs = {'phase': ('FLOAT', phase), 'spd': ('FLOAT', spd), 'size': ('FLOAT', size), 'bright': ('FLOAT', bright),
             'h0': ('FLOAT', np.array([heat[c][0] for c in cidx])), 'h1': ('FLOAT', np.array([heat[c][1] for c in cidx]))}
    for k in range(nst + 1):
        attrs['b%d' % k] = ('FLOAT', np.array([bounds[c][k] for c in cidx]))
        attrs['c%d' % k] = ('FLOAT', np.array([tbounds[c][k] for c in cidx]))
    me = points_mesh(name, np.zeros((n, 3)), attrs)
    a = me.attributes.new('cidx', 'INT', 'POINT')
    a.data.foreach_set('value', cidx.astype(np.int32))
    ob = obj(name, me, coll)
    st = bpy.data.objects.get('FX_Streak_Unit')
    if st is None:
        st = obj('FX_Streak_Unit', streak_mesh('FX_Streak_Unit'), coll)
        st.hide_render = True
        st.hide_viewport = True
    mat = material or fx_emit_material('MS_FX_Staged_' + name, color, strength=strength)
    mod = ob.modifiers.new('Flow', 'NODES')
    mod.node_group = flow_staged_group(nst)
    mod[input_id(mod, 'Curves')] = cu
    mod[input_id(mod, 'Streak')] = st
    mod[input_id(mod, 'Material')] = mat
    mod[input_id(mod, 'Length')] = length_mm * MM
    mod[input_id(mod, 'Radius')] = radius_mm * MM
    mod[input_id(mod, 'Gain')] = gain
    ob['fx'] = 'flow_staged'
    ob['stages'] = ','.join(stage_keys)
    return ob, cu, mod


def _frames_along(p):
    t = np.gradient(p, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
    n = np.zeros_like(p)
    ref = np.array([0.0, 0.0, 1.0]) if abs(t[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    n0 = np.cross(t[0], ref)
    n0 /= max(np.linalg.norm(n0), 1e-12)
    n[0] = n0
    for i in range(1, len(p)):
        v = n[i - 1] - np.dot(n[i - 1], t[i]) * t[i]
        ln = np.linalg.norm(v)
        if ln < 1e-9:
            v = np.cross(t[i], ref)
            ln = max(np.linalg.norm(v), 1e-12)
        n[i] = v / ln
    b = np.cross(t, n)
    return t, n, b


def tube_mesh_data(paths, radius, sides=6):
    verts = []
    faces = []
    owner = []
    off = 0
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    ca, sa = np.cos(ang), np.sin(ang)
    for li, p in enumerate(paths):
        p = np.asarray(p, dtype=np.float64)
        t, n, b = _frames_along(p)
        m = len(p)
        ring = p[:, None, :] + radius * (ca[None, :, None] * n[:, None, :] + sa[None, :, None] * b[:, None, :])
        verts.append(ring.reshape(-1, 3))
        for i in range(m - 1):
            for k in range(sides):
                k2 = (k + 1) % sides
                faces.append((off + i * sides + k, off + i * sides + k2, off + (i + 1) * sides + k2,
                              off + (i + 1) * sides + k))
        owner.append(np.repeat(np.arange(m), sides) + 0)
        off += m * sides
    return np.vstack(verts), faces, owner


def tube_material(name, color=CYAN, strength=3.0, tail_pow=6.0, base=0.0, hot_color=AMBER, fade_in=0.03,
                  fade_out=0.05):
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    N = nt.nodes
    L = nt.links
    for x in list(N):
        N.remove(x)

    def mth(op, a, b=None, c=None):
        n = N.new('ShaderNodeMath')
        n.operation = op
        for i, x in enumerate((a, b, c)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = x
            else:
                L.new(x, n.inputs[i])
        return n.outputs[0]

    def gattr(nm):
        a = N.new('ShaderNodeAttribute')
        a.attribute_type = 'GEOMETRY'
        a.attribute_name = nm
        return a.outputs['Fac']

    def oattr(nm):
        a = N.new('ShaderNodeAttribute')
        a.attribute_type = 'OBJECT'
        a.attribute_name = nm
        return a.outputs['Fac']

    def mrange(v, f0, f1, t0, t1):
        r = N.new('ShaderNodeMapRange')
        r.interpolation_type = 'SMOOTHSTEP'
        r.clamp = True
        for key, val in (('From Min', f0), ('From Max', f1), ('To Min', t0), ('To Max', t1)):
            if isinstance(val, (int, float)):
                r.inputs[key].default_value = val
            else:
                L.new(val, r.inputs[key])
        L.new(v, r.inputs['Value'])
        return r.outputs['Result']

    out = N.new('ShaderNodeOutputMaterial')
    tv = frame_time_value(nt)
    x = mth('ADD', mth('SUBTRACT', gattr('tk'), mth('MULTIPLY', tv.outputs[0], gattr('lrate'))), gattr('lph'))
    p = mth('FRACT', x)
    dash = mth('MULTIPLY', mth('POWER', p, tail_pow), mrange(p, 0.955, 1.0, 1.0, 0.0))
    core = mth('ADD', mth('MULTIPLY', dash, 1.0 - base), base)
    sv = gattr('sv')
    rv = oattr('reveal')
    soft = 0.12
    mrev = mrange(sv, mth('SUBTRACT', rv, soft), rv, 1.0, 0.0)
    hb = oattr('hide_before')
    mhide = mrange(sv, hb, mth('ADD', hb, soft), 0.0, 1.0)
    tau = gattr('tau')
    ends = mth('MULTIPLY', mrange(tau, 0.0, fade_in, 0.0, 1.0), mrange(tau, 1.0 - fade_out, 1.0, 1.0, 0.0))
    hot = gattr('hot')
    hg = mth('MULTIPLY_ADD', mth('SUBTRACT', oattr('hot_gain'), 1.0), hot, 1.0)
    s = mth('MULTIPLY', core, mrev)
    s = mth('MULTIPLY', s, mhide)
    s = mth('MULTIPLY', s, ends)
    s = mth('MULTIPLY', s, hg)
    s = mth('MULTIPLY', s, gattr('bright'))
    s = mth('MULTIPLY', s, oattr('gain'))
    s = mth('MULTIPLY', s, strength)
    mix = N.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['A'].default_value = tuple(color) + (1.0,)
    mix.inputs['B'].default_value = tuple(hot_color) + (1.0,)
    L.new(hot, mix.inputs['Factor'])
    em = N.new('ShaderNodeEmission')
    L.new(mix.outputs['Result'], em.inputs['Color'])
    L.new(s, em.inputs['Strength'])
    tr = N.new('ShaderNodeBsdfTransparent')
    add = N.new('ShaderNodeAddShader')
    L.new(tr.outputs['BSDF'], add.inputs[0])
    L.new(em.outputs['Emission'], add.inputs[1])
    L.new(add.outputs['Shader'], out.inputs['Surface'])
    return m


def flow_tubes(name, coll, lines, stage_keys, speed_mm_s=80.0, stage_speed=None, dash_mm=60.0, radius_mm=0.2,
               sides=6, heat_stage=None, heat_span=(0.05, 0.9), color=CYAN, strength=3.0, tail_pow=6.0, base=0.0,
               bright_range=(0.7, 1.0), seed=1, fade_in=0.03, fade_out=0.05):
    rng = np.random.default_rng(seed)
    nst = len(stage_keys)
    sspd = list(stage_speed) if stage_speed is not None else [1.0] * nst
    paths = []
    per_pt = []
    for ln in lines:
        segs = []
        for key in stage_keys:
            p = np.asarray(ln[key], dtype=np.float64)
            if segs and np.linalg.norm(p[0] - segs[-1][-1]) < 1e-6:
                p = p[1:]
            segs.append(p)
        allp = np.vstack(segs)
        seg_len = np.linalg.norm(np.diff(allp, axis=0), axis=1)
        cum = np.concatenate([[0.0], np.cumsum(seg_len)])
        tot = cum[-1]
        idx_b = [0]
        acc = 0
        for p in segs:
            acc += len(p)
            idx_b.append(acc - 1)
        idx_b[0] = 0
        lb = [cum[i] for i in idx_b]
        tl = [(lb[k + 1] - lb[k]) / sspd[k] for k in range(nst)]
        tt = sum(tl)
        tb = np.concatenate([[0.0], np.cumsum(tl)])
        sv = np.zeros(len(allp))
        tau_t = np.zeros(len(allp))
        for k in range(nst):
            a0, a1 = lb[k], lb[k + 1]
            msk = (cum >= a0 - 1e-9) & (cum <= a1 + 1e-9)
            fr = (cum[msk] - a0) / max(a1 - a0, 1e-9)
            sv[msk] = k + fr
            tau_t[msk] = tb[k] + fr * (tb[k + 1] - tb[k])
        tau_t /= tt
        if heat_stage is not None:
            k = stage_keys.index(heat_stage)
            h0 = k + heat_span[0]
            h1 = k + heat_span[1]
            hot = np.clip((sv - h0) / (h1 - h0), 0.0, 1.0)
            hot = hot * hot * (3 - 2 * hot)
        else:
            hot = np.zeros(len(allp))
        K = max(1.0, round(tot / dash_mm))
        T = tt / speed_mm_s
        lrate = K / T * rng.uniform(0.94, 1.06)
        lph = rng.random()
        br = rng.uniform(*bright_range)
        paths.append(allp * MM)
        per_pt.append(dict(tk=tau_t * K, tau=tau_t, sv=sv, hot=hot, lrate=np.full(len(allp), lrate),
                           lph=np.full(len(allp), lph), bright=np.full(len(allp), br)))
    v, f, owner = tube_mesh_data(paths, radius_mm * MM, sides)
    me = mesh_np(name, v, f)
    for key in ('tk', 'tau', 'sv', 'hot', 'lrate', 'lph', 'bright'):
        vals = np.concatenate([per_pt[i][key][owner[i]] for i in range(len(paths))]).astype(np.float32)
        a = me.attributes.new(key, 'FLOAT', 'POINT')
        a.data.foreach_set('value', vals)
    for pg in me.polygons:
        pg.use_smooth = True
    mat = tube_material('MS_FX_Tube_' + name, color=color, strength=strength, tail_pow=tail_pow, base=base,
                        fade_in=fade_in, fade_out=fade_out)
    ob = obj(name, me, coll, mat=mat)
    ob['reveal'] = float(nst)
    ob['hide_before'] = -1.0
    ob['gain'] = 1.0
    ob['hot_gain'] = 1.0
    ob.visible_shadow = False
    ob.visible_diffuse = False
    ob.visible_glossy = True
    ob['fx'] = 'flow_tubes'
    ob['stages'] = ','.join(stage_keys)
    return ob
