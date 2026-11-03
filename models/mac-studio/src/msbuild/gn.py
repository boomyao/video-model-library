import math
import bpy


def _sock(ng, name, in_out, stype, default=None, minv=None, maxv=None, subtype=None):
    s = ng.interface.new_socket(name, in_out=in_out, socket_type=stype)
    if default is not None:
        s.default_value = default
    if minv is not None:
        s.min_value = minv
    if maxv is not None:
        s.max_value = maxv
    if subtype is not None:
        s.subtype = subtype
    return s


def holes_boolean_group(name, points_obj, bore_mat, extra_cutter=None, radius_mm=0.5, depth_mm=5.0,
                        segments=16, smooth_angle_deg=30.0, attr='dir'):
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.is_modifier = True
    _sock(ng, 'Geometry', 'INPUT', 'NodeSocketGeometry')
    _sock(ng, 'Hole Segments', 'INPUT', 'NodeSocketInt', segments, 3, 128)
    _sock(ng, 'Hole Radius', 'INPUT', 'NodeSocketFloat', radius_mm * 0.001, 0.0)
    _sock(ng, 'Hole Depth', 'INPUT', 'NodeSocketFloat', depth_mm * 0.001, 0.0)
    _sock(ng, 'Enable Holes', 'INPUT', 'NodeSocketBool', True)
    _sock(ng, 'Smooth Angle', 'INPUT', 'NodeSocketFloat', math.radians(smooth_angle_deg), 0.0, math.pi, 'ANGLE')
    _sock(ng, 'Geometry', 'OUTPUT', 'NodeSocketGeometry')
    N = ng.nodes
    L = ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    oi = N.new('GeometryNodeObjectInfo')
    oi.transform_space = 'ORIGINAL'
    oi.inputs['Object'].default_value = points_obj
    na = N.new('GeometryNodeInputNamedAttribute')
    na.data_type = 'FLOAT_VECTOR'
    na.inputs['Name'].default_value = attr
    ar = N.new('FunctionNodeAlignRotationToVector')
    ar.axis = 'Z'
    L.new(na.outputs['Attribute'], ar.inputs['Vector'])
    cyl = N.new('GeometryNodeMeshCylinder')
    cyl.fill_type = 'NGON'
    L.new(gi.outputs['Hole Segments'], cyl.inputs['Vertices'])
    L.new(gi.outputs['Hole Radius'], cyl.inputs['Radius'])
    L.new(gi.outputs['Hole Depth'], cyl.inputs['Depth'])
    sm = N.new('GeometryNodeSetMaterial')
    sm.inputs['Material'].default_value = bore_mat
    L.new(cyl.outputs['Mesh'], sm.inputs['Geometry'])
    iop = N.new('GeometryNodeInstanceOnPoints')
    L.new(oi.outputs['Geometry'], iop.inputs['Points'])
    L.new(sm.outputs['Geometry'], iop.inputs['Instance'])
    L.new(ar.outputs['Rotation'], iop.inputs['Rotation'])
    L.new(gi.outputs['Enable Holes'], iop.inputs['Selection'])
    rz = N.new('GeometryNodeRealizeInstances')
    L.new(iop.outputs['Instances'], rz.inputs['Geometry'])
    mb = N.new('GeometryNodeMeshBoolean')
    mb.operation = 'DIFFERENCE'
    mb.solver = 'MANIFOLD'
    L.new(gi.outputs['Geometry'], mb.inputs['Mesh 1'])
    L.new(rz.outputs['Geometry'], mb.inputs['Mesh 2'])
    if extra_cutter is not None:
        oi2 = N.new('GeometryNodeObjectInfo')
        oi2.transform_space = 'ORIGINAL'
        oi2.inputs['Object'].default_value = extra_cutter
        L.new(oi2.outputs['Geometry'], mb.inputs['Mesh 2'])
    ea = N.new('GeometryNodeInputMeshEdgeAngle')
    cmp_ = N.new('FunctionNodeCompare')
    cmp_.data_type = 'FLOAT'
    cmp_.operation = 'LESS_THAN'
    L.new(ea.outputs['Unsigned Angle'], cmp_.inputs[0])
    L.new(gi.outputs['Smooth Angle'], cmp_.inputs[1])
    ssf = N.new('GeometryNodeSetShadeSmooth')
    ssf.domain = 'FACE'
    ssf.inputs['Shade Smooth'].default_value = True
    sse = N.new('GeometryNodeSetShadeSmooth')
    sse.domain = 'EDGE'
    L.new(mb.outputs['Mesh'], ssf.inputs['Mesh'])
    L.new(ssf.outputs['Mesh'], sse.inputs['Mesh'])
    L.new(cmp_.outputs['Result'], sse.inputs['Shade Smooth'])
    L.new(sse.outputs['Mesh'], go.inputs['Geometry'])
    return ng


def set_mod_input(mod, name, value):
    for item in mod.node_group.interface.items_tree:
        if getattr(item, 'item_type', 'SOCKET') == 'SOCKET' and item.in_out == 'INPUT' and item.name == name:
            mod[item.identifier] = value
            return True
    return False
