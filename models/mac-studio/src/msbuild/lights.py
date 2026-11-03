import math
import os
import bpy
import numpy as np
from mathutils import Vector
from .util import MM, obj, col, mesh_np, recalc_normals
from .materials import srgb

LOOK = 'AgX - Medium High Contrast'
BG_INNER = '#16181c'
BG_OUTER = '#0b0c0e'


def _ocio_processor(look):
    import PyOpenColorIO as OCIO
    cfgp = os.path.join(bpy.utils.resource_path('LOCAL'), 'datafiles', 'colormanagement', 'config.ocio')
    cfg = OCIO.Config.CreateFromFile(cfgp)
    grp = OCIO.GroupTransform()
    if look and look != 'None':
        lt = OCIO.LookTransform()
        lt.setSrc('Linear Rec.709')
        lt.setDst('Linear Rec.709')
        lt.setLooks(look)
        grp.appendTransform(lt)
    dv = OCIO.DisplayViewTransform()
    dv.setSrc('Linear Rec.709')
    dv.setDisplay('sRGB')
    dv.setView('AgX')
    grp.appendTransform(dv)
    return cfg.getProcessor(grp).getDefaultCPUProcessor()


CALIBRATED = {
    ('AgX - Medium High Contrast', '#16181c'): (0.019399, 0.020666, 0.024954),
    ('AgX - Medium High Contrast', '#0b0c0e'): (0.009161, 0.010716, 0.012497),
}


def display_to_scene_linear(hexcol, look=LOOK):
    if (look, hexcol.lower()) in CALIBRATED:
        return CALIBRATED[(look, hexcol.lower())]
    h = hexcol.lstrip('#')
    target = np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])
    try:
        proc = _ocio_processor(look)
    except Exception:
        return tuple(srgb(hexcol)[:3])
    x = np.maximum(np.array(srgb(hexcol)[:3]), 1e-5)
    for _ in range(80):
        out = np.array(proc.applyRGB([float(v) for v in x]))
        err = target - out
        if np.max(np.abs(err)) < 2e-4:
            break
        x = x * np.exp(np.clip((np.log(np.maximum(target, 1e-4)) - np.log(np.maximum(out, 1e-4))) * 1.6, -2, 2))
        x = np.maximum(x, 1e-7)
    return tuple(float(v) for v in x)


def bg_gradient_group(inner_lin, outer_lin, name='MS_BG_Gradient', center=(0.5, 0.62), radius=1.2):
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    ng.interface.new_socket('Color', in_out='OUTPUT', socket_type='NodeSocketColor')
    N = ng.nodes
    L = ng.links
    go = N.new('NodeGroupOutput')
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(tc.outputs['Window'], sep.inputs['Vector'])
    dx = N.new('ShaderNodeMath')
    dx.operation = 'SUBTRACT'
    dx.inputs[1].default_value = center[0]
    L.new(sep.outputs['X'], dx.inputs[0])
    dxs = N.new('ShaderNodeMath')
    dxs.operation = 'MULTIPLY'
    dxs.inputs[1].default_value = 1920.0 / 1080.0
    L.new(dx.outputs['Value'], dxs.inputs[0])
    dy = N.new('ShaderNodeMath')
    dy.operation = 'SUBTRACT'
    dy.inputs[1].default_value = center[1]
    L.new(sep.outputs['Y'], dy.inputs[0])
    cmb = N.new('ShaderNodeCombineXYZ')
    L.new(dxs.outputs['Value'], cmb.inputs['X'])
    L.new(dy.outputs['Value'], cmb.inputs['Y'])
    ln = N.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    L.new(cmb.outputs['Vector'], ln.inputs[0])
    mr = N.new('ShaderNodeMapRange')
    mr.interpolation_type = 'SMOOTHSTEP'
    mr.inputs['From Min'].default_value = 0.0
    mr.inputs['From Max'].default_value = radius
    L.new(ln.outputs['Value'], mr.inputs['Value'])
    mix = N.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['A'].default_value = tuple(inner_lin) + (1.0,)
    mix.inputs['B'].default_value = tuple(outer_lin) + (1.0,)
    L.new(mr.outputs['Result'], mix.inputs['Factor'])
    gain = N.new('ShaderNodeValue')
    gain.name = 'BG_GAIN'
    gain.label = 'BG_GAIN'
    gain.outputs[0].default_value = 1.0
    mg = N.new('ShaderNodeVectorMath')
    mg.operation = 'SCALE'
    L.new(mix.outputs['Result'], mg.inputs[0])
    L.new(gain.outputs[0], mg.inputs['Scale'])
    L.new(mg.outputs['Vector'], go.inputs['Color'])
    return ng


def world_dark(bg_group):
    w = bpy.data.worlds.get('World_Dark') or bpy.data.worlds.new('World_Dark')
    if w.node_tree is None:
        w.use_nodes = True
    nt = w.node_tree
    N = nt.nodes
    L = nt.links
    for n in list(N):
        N.remove(n)
    out = N.new('ShaderNodeOutputWorld')
    lp = N.new('ShaderNodeLightPath')
    gnode = N.new('ShaderNodeGroup')
    gnode.node_tree = bg_group
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(tc.outputs['Generated'], sep.inputs['Vector'])
    mr = N.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = -0.2
    mr.inputs['From Max'].default_value = 1.0
    mr.inputs['To Min'].default_value = 0.0004
    mr.inputs['To Max'].default_value = 0.006
    L.new(sep.outputs['Z'], mr.inputs['Value'])
    envc = N.new('ShaderNodeCombineColor')
    L.new(mr.outputs['Result'], envc.inputs[0])
    L.new(mr.outputs['Result'], envc.inputs[1])
    L.new(mr.outputs['Result'], envc.inputs[2])
    mix = N.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    L.new(lp.outputs['Is Camera Ray'], mix.inputs['Factor'])
    L.new(envc.outputs['Color'], mix.inputs['A'])
    L.new(gnode.outputs['Color'], mix.inputs['B'])
    bg = N.new('ShaderNodeBackground')
    L.new(mix.outputs['Result'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
    L.new(bg.outputs['Background'], out.inputs['Surface'])
    return w


def world_light():
    w = bpy.data.worlds.get('World_Light') or bpy.data.worlds.new('World_Light')
    if w.node_tree is None:
        w.use_nodes = True
    nt = w.node_tree
    N = nt.nodes
    L = nt.links
    for n in list(N):
        N.remove(n)
    out = N.new('ShaderNodeOutputWorld')
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(tc.outputs['Generated'], sep.inputs['Vector'])
    mr = N.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = -0.3
    mr.inputs['From Max'].default_value = 1.0
    mr.inputs['To Min'].default_value = 0.03
    mr.inputs['To Max'].default_value = 0.26
    L.new(sep.outputs['Z'], mr.inputs['Value'])
    bg = N.new('ShaderNodeBackground')
    L.new(mr.outputs['Result'], bg.inputs['Strength'])
    bg.inputs['Color'].default_value = (0.9, 0.9, 0.92, 1)
    L.new(bg.outputs['Background'], out.inputs['Surface'])
    return w


def floor_dark_material(bg_group):
    m = bpy.data.materials.get('MS_Floor_Dark')
    if m is not None:
        return m
    m = bpy.data.materials.new('MS_Floor_Dark')
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    N = nt.nodes
    L = nt.links
    p = N.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (0.0015, 0.0016, 0.0018, 1)
    p.inputs['Roughness'].default_value = 0.26
    p.inputs['Specular IOR Level'].default_value = 0.22
    outn = N.get('Material Output')
    tc = N.new('ShaderNodeTexCoord')
    ln = N.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    L.new(tc.outputs['Object'], ln.inputs[0])
    mr = N.new('ShaderNodeMapRange')
    mr.interpolation_type = 'SMOOTHSTEP'
    mr.inputs['From Min'].default_value = 0.12
    mr.inputs['From Max'].default_value = 0.62
    L.new(ln.outputs['Value'], mr.inputs['Value'])
    lp = N.new('ShaderNodeLightPath')
    mul = N.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    L.new(mr.outputs['Result'], mul.inputs[0])
    L.new(lp.outputs['Is Camera Ray'], mul.inputs[1])
    g = N.new('ShaderNodeGroup')
    g.node_tree = bg_group
    em = N.new('ShaderNodeEmission')
    L.new(g.outputs['Color'], em.inputs['Color'])
    em.inputs['Strength'].default_value = 1.0
    em2 = N.new('ShaderNodeEmission')
    L.new(g.outputs['Color'], em2.inputs['Color'])
    m2 = N.new('ShaderNodeMath')
    m2.operation = 'MULTIPLY'
    m2.inputs[1].default_value = 1.0
    L.new(lp.outputs['Is Camera Ray'], m2.inputs[0])
    L.new(m2.outputs['Value'], em2.inputs['Strength'])
    add = N.new('ShaderNodeAddShader')
    L.new(p.outputs['BSDF'], add.inputs[0])
    L.new(em2.outputs['Emission'], add.inputs[1])
    ms = N.new('ShaderNodeMixShader')
    L.new(mul.outputs['Value'], ms.inputs['Fac'])
    L.new(add.outputs['Shader'], ms.inputs[1])
    L.new(em.outputs['Emission'], ms.inputs[2])
    L.new(ms.outputs['Shader'], outn.inputs['Surface'])
    return m


def cyc_black_material():
    m = bpy.data.materials.get('MS_Negative_Fill')
    if m is not None:
        return m
    m = bpy.data.materials.new('MS_Negative_Fill')
    if m.node_tree is None:
        m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (0.004, 0.004, 0.004, 1)
    p.inputs['Roughness'].default_value = 0.9
    p.inputs['Specular IOR Level'].default_value = 0.0
    return m


def cyc_material():
    m = bpy.data.materials.get('MS_Cyc_Light')
    if m is not None:
        return m
    m = bpy.data.materials.new('MS_Cyc_Light')
    if m.node_tree is None:
        m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (0.42, 0.425, 0.43, 1)
    p.inputs['Roughness'].default_value = 0.55
    p.inputs['Specular IOR Level'].default_value = 0.3
    return m


def area(name, coll, size, loc, target, energy, color=(1, 1, 1), shape='RECTANGLE', size_y=None, spread=180.0):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.shape = shape
    ld.size = size
    if size_y is not None:
        ld.size_y = size_y
    ld.energy = energy
    ld.color = color
    ld.spread = math.radians(spread)
    ob = bpy.data.objects.new(name, ld)
    coll.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = d.to_track_quat('-Z', 'Y')
    ob.visible_camera = False
    return ob


def floor_plane(name, coll, mat, size=8.0):
    s = size / 2
    me = mesh_np(name, np.array([[-s, -s, 0], [s, -s, 0], [s, s, 0], [-s, s, 0]]), [(0, 1, 2, 3)])
    ob = obj(name, me, coll, mat=mat)
    return ob


def cyc_mesh(name, coll, mat):
    prof = []
    ys = np.linspace(-3.0, 0.45, 12)
    for y in ys:
        prof.append((y, 0.0))
    R = 0.55
    for a in np.linspace(0, 90, 24)[1:]:
        r = math.radians(a)
        prof.append((0.45 + R * math.sin(r), R - R * math.cos(r)))
    for z in np.linspace(R, 3.0, 10)[1:]:
        prof.append((0.45 + R, z))
    xs = np.linspace(-4.0, 4.0, 9)
    verts = []
    for x in xs:
        for (y, z) in prof:
            verts.append((x, y, z))
    n = len(prof)
    faces = []
    for i in range(len(xs) - 1):
        for j in range(n - 1):
            a = i * n + j
            b = (i + 1) * n + j
            faces.append((a, b, b + 1, a + 1))
    me = mesh_np(name, np.array(verts), faces)
    for p in me.polygons:
        p.use_smooth = True
    ob = obj(name, me, coll, mat=mat)
    return ob


def light_link_exclude(lights, exclude_objs, coll_name):
    lc = bpy.data.collections.get(coll_name) or bpy.data.collections.new(coll_name)
    for o in exclude_objs:
        if o.name not in lc.objects:
            lc.objects.link(o)
    for co in lc.collection_objects:
        try:
            co.light_linking.link_state = 'EXCLUDE'
        except Exception:
            pass
    for l in lights:
        l.light_linking.receiver_collection = lc
    return lc


def build_dark(coll):
    inner = display_to_scene_linear(BG_INNER)
    outer = display_to_scene_linear(BG_OUTER)
    g = bg_gradient_group(inner, outer)
    w = world_dark(g)
    fl = floor_plane('Floor_Dark', coll, floor_dark_material(g), size=400.0)
    tgt = (0, 0, 0.045)
    L = []
    L.append(area('Key_TopLeft', coll, 0.9, (-0.55, -0.5, 0.78), tgt, 7.5, size_y=0.6, color=(1.0, 0.985, 0.97)))
    L.append(area('Top_Soft', coll, 0.7, (0.05, 0.25, 0.85), (0, 0.05, 0.0), 2.6, size_y=0.9, color=(0.97, 0.985, 1.0)))
    L.append(area('Rim_Left', coll, 0.06, (-0.62, 0.30, 0.15), tgt, 1.6, size_y=0.9, color=(0.96, 0.98, 1.0)))
    L.append(area('Rim_Right', coll, 0.06, (0.58, -0.12, 0.16), tgt, 1.4, size_y=0.9, color=(0.96, 0.98, 1.0)))
    L.append(area('Fill_FrontRight', coll, 0.8, (0.75, -0.75, 0.2), tgt, 2.6, size_y=0.35))
    card = gradient_card('Back_Gradient_Card', coll, (0.41, 0.61, 0.56), (0.0, 0.0, 0.045), 1.3, 0.55, 1.45,
                         invert=True)
    lc = light_link_exclude(L + [card], [fl], 'LL_Dark_Floor_Exclude')
    for l in L:
        l['rig'] = 'dark'
    return dict(world=w, floor=fl, lights=L, bg=(inner, outer))


def build_light(coll):
    w = world_light()
    cyc = cyc_mesh('Cyc_Light', coll, cyc_material())
    tgt = (0, 0, 0.045)
    L = []
    L.append(area('L_Top', coll, 1.4, (0.0, 0.1, 1.1), (0, 0, 0), 32.0, size_y=1.4))
    L.append(area('L_Key', coll, 1.0, (-0.9, -0.7, 0.55), tgt, 22.0, size_y=1.0))
    L.append(area('L_Fill', coll, 1.0, (0.9, -0.6, 0.35), tgt, 6.0, size_y=1.0))
    L.append(area('L_Back', coll, 1.6, (0.0, 0.8, 0.6), tgt, 10.0, size_y=0.5))
    neg = floor_plane('L_Negative_Card', coll, cyc_black_material(), size=1.0)
    neg.location = (-0.75, -0.15, 0.35)
    neg.rotation_euler = (0.0, 1.5708, 0.35)
    neg.visible_camera = False
    for l in L:
        l['rig'] = 'light'
    return dict(world=w, cyc=cyc, lights=L)


def build_foot_extra(coll, dark):
    L = []
    L.append(area('Foot_Under_Soft', coll, 0.5, (0.02, -0.25, -0.30), (0.04, -0.07, 0.004), 0.6, size_y=0.5,
                  color=(1.0, 0.99, 0.98)))
    L.append(area('Foot_Bore_Light', coll, 0.05, (0.22, -0.16, -0.10), (0.04, -0.07, 0.004), 1.2, size_y=0.05,
                  color=(1.0, 0.985, 0.96)))
    lc = bpy.data.collections.get('LL_Dark_Floor_Exclude')
    for l in L:
        l['rig'] = 'foot_extra'
        if lc is not None:
            l.light_linking.receiver_collection = lc
    return L


def build_extras(C):
    lc = bpy.data.collections.get('LL_Dark_Floor_Exclude')
    out = {}
    L = []
    L.append(area('Cut_Top', C['Lights_Extra_Cut'], 0.6, (0.05, -0.12, 0.62), (0.0, 0.0, 0.05), 3.2, size_y=0.6,
                  color=(0.98, 0.99, 1.0)))
    L.append(area('Cut_Front', C['Lights_Extra_Cut'], 0.7, (0.25, -0.75, 0.12), (0.0, 0.0, 0.03), 1.6, size_y=0.25,
                  color=(1.0, 0.985, 0.97)))
    out['cut'] = L
    L2 = []
    L2.append(area('Thermal_Behind_Cam', C['Lights_Extra_Thermal'], 0.9, (-0.45, 0.85, 0.55), (0.0, 0.03, 0.02), 6.0,
                   size_y=0.6, color=(1.0, 0.99, 0.98)))
    L2.append(area('Thermal_Side', C['Lights_Extra_Thermal'], 0.5, (0.75, 0.35, 0.25), (0.0, 0.03, 0.02), 2.0,
                   size_y=0.5, color=(0.97, 0.985, 1.0)))
    out['thermal'] = L2
    L3 = []
    L3.append(area('Chip_Key', C['Lights_Extra_Chip'], 0.3, (-0.25, -0.05, 0.35), (0.0, 0.0, 0.0), 0.35, size_y=0.3,
                   color=(1.0, 0.99, 0.98)))
    card = gradient_card('Chip_Gradient_Card', C['Lights_Extra_Chip'], (0.115, 0.27, 0.19), (0.0, 0.0, 0.0), 0.55, 0.32, 0.75)
    if lc is not None:
        card.light_linking.receiver_collection = lc
    out['chip'] = L3
    L4 = []
    tb = (-0.048, 0.0, 0.017)
    L4.append(area('Blower_Rim', C['Lights_Extra_Blower'], 0.05, (-0.12, 0.22, 0.19), tb, 2.6, size_y=0.45,
                   color=(0.95, 0.975, 1.0)))
    L4.append(area('Blower_Rim2', C['Lights_Extra_Blower'], 0.05, (0.10, 0.20, 0.10), tb, 1.4, size_y=0.35,
                   color=(0.95, 0.975, 1.0)))
    L4.append(area('Blower_Key', C['Lights_Extra_Blower'], 0.45, (0.10, -0.22, 0.32), tb, 0.9, size_y=0.45,
                   color=(1.0, 0.99, 0.98)))
    L4.append(area('Blower_Fill', C['Lights_Extra_Blower'], 0.4, (-0.32, -0.30, 0.04), tb, 0.25, size_y=0.25))
    out['blower'] = L4
    for lst in out.values():
        for l in lst:
            l['rig'] = 'extra'
            if lc is not None:
                l.light_linking.receiver_collection = lc
    return out


def gradient_card(name, coll, loc, target, w, h, strength, invert=False):
    mname = 'MS_Gradient_Card' + ('_Inv' if invert else '') + '_' + name
    m = bpy.data.materials.get(mname) or bpy.data.materials.new(mname)
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    N = nt.nodes
    Lk = nt.links
    for n in list(N):
        N.remove(n)
    out = N.new('ShaderNodeOutputMaterial')
    tc = N.new('ShaderNodeTexCoord')
    sep = N.new('ShaderNodeSeparateXYZ')
    Lk.new(tc.outputs['Generated'], sep.inputs['Vector'])
    mr = N.new('ShaderNodeMapRange')
    mr.interpolation_type = 'SMOOTHERSTEP'
    mr.inputs['From Min'].default_value = 0.0
    mr.inputs['From Max'].default_value = 1.0
    mr.inputs['To Min'].default_value = 1.0 if invert else 0.0
    mr.inputs['To Max'].default_value = 0.0 if invert else 1.0
    Lk.new(sep.outputs['Y'], mr.inputs['Value'])
    mx = N.new('ShaderNodeMath')
    mx.operation = 'MULTIPLY'
    Lk.new(mr.outputs['Result'], mx.inputs[0])
    mx.inputs[1].default_value = strength
    em = N.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (1.0, 0.995, 0.99, 1.0)
    Lk.new(mx.outputs['Value'], em.inputs['Strength'])
    Lk.new(em.outputs['Emission'], out.inputs['Surface'])
    me = mesh_np(name, np.array([[-w / 2, -h / 2, 0], [w / 2, -h / 2, 0], [w / 2, h / 2, 0], [-w / 2, h / 2, 0]]), [(0, 1, 2, 3)])
    ob = obj(name, me, coll, mat=m)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = d.to_track_quat('Z', 'Y')
    ob.visible_camera = False
    ob.visible_shadow = False
    ob['rig'] = 'extra'
    return ob
