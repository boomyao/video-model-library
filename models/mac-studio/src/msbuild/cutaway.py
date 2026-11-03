import bpy
import numpy as np
from . import dims as D
from .util import MM, mesh_np, obj, recalc_normals

Y_CUT = -4.0
Y_CUT_BOARD = -38.0
Z_BLOWER_CUT = 71.0
Z_LID = D.Z_TOP - 4.6


def _l_prism(name, coll, yz_outline, x0, x1):
    p = np.asarray(yz_outline, dtype=np.float64)
    n = len(p)
    v0 = np.column_stack([np.full(n, x0), p[:, 0], p[:, 1]])
    v1 = np.column_stack([np.full(n, x1), p[:, 0], p[:, 1]])
    verts = np.vstack([v0, v1])
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        i2 = (i + 1) % n
        faces.append((i, i2, n + i2, n + i))
    me = mesh_np(name, verts * MM, faces)
    recalc_normals(me)
    ob = obj(name, me, coll)
    ob.display_type = 'WIRE'
    ob.hide_render = True
    ob.hide_viewport = True
    return ob


def build_cutters(coll):
    big = 400.0
    front = _l_prism('CUTTER_front', coll,
                     [(-big, -50.0), (Y_CUT, -50.0), (Y_CUT, Z_LID), (big, Z_LID), (big, 300.0), (-big, 300.0)],
                     -big, big)
    btop = _l_prism('CUTTER_blower_top', coll,
                    [(-big, Z_BLOWER_CUT), (big, Z_BLOWER_CUT), (big, 300.0), (-big, 300.0)], -big, big)
    bside = _l_prism('CUTTER_blower_side', coll,
                     [(-big, -50.0), (D.BLOWER_CY - 6.0, -50.0), (D.BLOWER_CY - 6.0, 300.0), (-big, 300.0)],
                     -big, -0.5)
    board = _l_prism('CUTTER_board', coll,
                     [(-big, -50.0), (Y_CUT_BOARD, -50.0), (Y_CUT_BOARD, 300.0), (-big, 300.0)], -big, big)
    return dict(front=front, blower_top=btop, blower_side=bside, board=board)


def clip_group():
    ng = bpy.data.node_groups.get('MS_ClipY')
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new('MS_ClipY', 'GeometryNodeTree')
    ng.is_modifier = True
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    s = ng.interface.new_socket('Y', in_out='INPUT', socket_type='NodeSocketFloat')
    s.default_value = Y_CUT_BOARD * MM
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes
    L = ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    pos = N.new('GeometryNodeInputPosition')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(pos.outputs['Position'], sep.inputs['Vector'])
    cmp_ = N.new('FunctionNodeCompare')
    cmp_.data_type = 'FLOAT'
    cmp_.operation = 'LESS_THAN'
    L.new(sep.outputs['Y'], cmp_.inputs[0])
    L.new(gi.outputs['Y'], cmp_.inputs[1])
    dg = N.new('GeometryNodeDeleteGeometry')
    dg.domain = 'FACE'
    L.new(gi.outputs['Geometry'], dg.inputs['Geometry'])
    L.new(cmp_.outputs['Result'], dg.inputs['Selection'])
    L.new(dg.outputs['Geometry'], go.inputs['Geometry'])
    return ng


def add_clip(ob, key):
    m = ob.modifiers.new('CUT_' + key, 'NODES')
    m.node_group = clip_group()
    m.show_viewport = False
    m.show_render = False
    return m


def add_cut(ob, cutter, key, solver='MANIFOLD'):
    m = ob.modifiers.new('CUT_' + key, 'BOOLEAN')
    m.operation = 'DIFFERENCE'
    m.solver = solver
    m.operand_type = 'OBJECT'
    m.object = cutter
    m.material_mode = 'INDEX'
    if solver == 'EXACT':
        m.use_self = True
        m.use_hole_tolerant = True
    m.show_viewport = False
    m.show_render = False
    return m


def set_cuts(active_keys):
    for ob in bpy.data.objects:
        for m in ob.modifiers:
            if m.type in ('BOOLEAN', 'NODES') and m.name.startswith('CUT_'):
                on = m.name[4:] in active_keys
                m.show_viewport = on
                m.show_render = on
        tag = ob.get('hide_in_cut')
        if tag is not None:
            hidden = tag in active_keys
            ob.hide_render = hidden
            ob.hide_viewport = hidden
