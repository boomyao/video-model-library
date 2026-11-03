# Helpers for the Roadster opening style test (Blender 5.1).
# Everything here is procedural: no external textures, no Tesla frames.
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix, Quaternion

# ---------------------------------------------------------------- scene / objects

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    return sc


def coll(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c


def mesh_obj(name, verts, faces, collection, smooth=False, mat=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate()
    me.update()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    if smooth:
        me.shade_smooth()
    if mat is not None:
        me.materials.append(mat)
    return ob


def bm_obj(name, bm, collection, smooth=False, mat=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.update()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    if smooth:
        me.shade_smooth()
    if mat is not None:
        if isinstance(mat, (list, tuple)):
            for m in mat:
                me.materials.append(m)
        else:
            me.materials.append(mat)
    return ob


def empty(name, collection, loc=(0, 0, 0), size=0.5):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = size
    ob.location = loc
    collection.objects.link(ob)
    return ob


def parent_keep_local(child, parent):
    """Parent so that child's current transform is read in parent space."""
    child.parent = parent
    child.matrix_parent_inverse = Matrix.Identity(4)


def add_attr(me, name, values, kind='FLOAT', domain='POINT'):
    a = me.attributes.new(name=name, type=kind, domain=domain)
    arr = np.asarray(values, dtype=np.float32).ravel() if kind != 'INT' else np.asarray(values, dtype=np.int32).ravel()
    key = {'FLOAT': 'value', 'INT': 'value', 'FLOAT_VECTOR': 'vector', 'FLOAT_COLOR': 'color'}[kind]
    a.data.foreach_set(key, arr)
    return a


def points_obj(name, pts, collection, attrs=None):
    """Mesh made of loose vertices (later turned into points by geometry nodes)."""
    pts = np.asarray(pts, dtype=np.float32).reshape(-1, 3)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(pts))
    me.vertices.foreach_set('co', pts.ravel())
    me.update()
    for k, (kind, vals) in (attrs or {}).items():
        add_attr(me, k, vals, kind)
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob

# ---------------------------------------------------------------- bmesh primitives

def bm_strut(bm, p0, p1, r, seg=6, caps=True):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    if L < 1e-6:
        return
    z = d / L
    x = z.orthogonal().normalized()
    y = z.cross(x)
    r0, r1 = [], []
    for i in range(seg):
        a = 2 * math.pi * (i + 0.5) / seg
        off = (x * math.cos(a) + y * math.sin(a)) * r
        r0.append(bm.verts.new(p0 + off))
        r1.append(bm.verts.new(p1 + off))
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    if caps:
        bm.faces.new(list(reversed(r0)))
        bm.faces.new(r1)


def bm_box(bm, center, size, rot=None):
    c = Vector(center)
    sx, sy, sz = [s * 0.5 for s in size]
    R = rot.to_3x3() if rot is not None else Matrix.Identity(3)
    corners = [Vector((x, y, z)) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
    vs = [bm.verts.new(c + R @ v) for v in corners]
    idx = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for f in idx:
        bm.faces.new([vs[i] for i in f])


def bm_tube_along(bm, pts, r, seg=8, caps=True):
    """Tube following a polyline with parallel-transported frames."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    tangents = []
    for i in range(n):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, n - 1)]
        tangents.append((b - a).normalized())
    x = tangents[0].orthogonal().normalized()
    rings = []
    for i in range(n):
        t = tangents[i]
        x = (x - t * x.dot(t)).normalized()
        y = t.cross(x)
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            ring.append(bm.verts.new(pts[i] + (x * math.cos(a) + y * math.sin(a)) * r))
        rings.append(ring)
    for i in range(n - 1):
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
    if caps:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])


def bm_lathe(bm, profile, axis_origin, axis_dir, seg=32, close_start=False, close_end=False):
    """Revolve a (radius, axial) profile around an axis."""
    o = Vector(axis_origin)
    a = Vector(axis_dir).normalized()
    x = a.orthogonal().normalized()
    y = a.cross(x)
    rings = []
    for (rad, ax) in profile:
        ring = []
        for k in range(seg):
            t = 2 * math.pi * k / seg
            ring.append(bm.verts.new(o + a * ax + (x * math.cos(t) + y * math.sin(t)) * rad))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
    if close_start:
        bm.faces.new(list(reversed(rings[0])))
    if close_end:
        bm.faces.new(rings[-1])
    return rings


def bm_capsule(bm, center, axis, radius, length, seg=32, rings_per_cap=10):
    """Capsule (cylinder with hemispherical ends); length is end to end."""
    half = max(length * 0.5 - radius, 0.0)
    prof = []
    for i in range(rings_per_cap + 1):
        t = -math.pi / 2 + (math.pi / 2) * i / rings_per_cap
        prof.append((radius * math.cos(t) + 1e-5, -half + radius * math.sin(t)))
    for i in range(rings_per_cap + 1):
        t = (math.pi / 2) * i / rings_per_cap
        prof.append((radius * math.cos(t) + 1e-5, half + radius * math.sin(t)))
    return bm_lathe(bm, prof, center, axis, seg=seg, close_start=True, close_end=True)

# ---------------------------------------------------------------- interpolation

def pchip(xs, ys, xq):
    """Monotone cubic interpolation (no overshoot)."""
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    xq = np.asarray(xq, float)
    h = np.diff(xs)
    d = np.diff(ys) / h
    n = len(xs)
    m = np.zeros(n)
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0
        else:
            w1 = 2 * h[i] + h[i - 1]
            w2 = h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    m[0] = d[0]
    m[-1] = d[-1]
    idx = np.clip(np.searchsorted(xs, xq) - 1, 0, n - 2)
    t = (xq - xs[idx]) / h[idx]
    h00 = 2 * t**3 - 3 * t**2 + 1
    h10 = t**3 - 2 * t**2 + t
    h01 = -2 * t**3 + 3 * t**2
    h11 = t**3 - t**2
    return h00 * ys[idx] + h10 * h[idx] * m[idx] + h01 * ys[idx + 1] + h11 * h[idx] * m[idx + 1]


def catmull_chain(pts, counts, prev_pt=None, next_pt=None):
    """Centripetal-ish Catmull-Rom through pts; counts[i] samples on segment i (excluding end)."""
    P = [np.asarray(p, float) for p in pts]
    ext = [P[0] * 2 - P[1] if prev_pt is None else np.asarray(prev_pt, float)] + P + \
          [P[-1] * 2 - P[-2] if next_pt is None else np.asarray(next_pt, float)]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        c = counts[i]
        for k in range(c):
            t = k / c
            t2, t3 = t * t, t * t * t
            v = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append(v)
    out.append(P[-1])
    return out


def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def ease_io(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def look_quat(eye, target, up=(0, 0, 1)):
    """Camera quaternion: -Z looks at target, +Y toward up."""
    eye, target, up = Vector(eye), Vector(target), Vector(up)
    f = (target - eye).normalized()
    r = f.cross(up)
    if r.length < 1e-6:
        r = f.orthogonal()
    r.normalize()
    u = r.cross(f).normalized()
    M = Matrix((r, u, -f)).transposed()
    return M.to_quaternion()


def frame_quat(fwd, up):
    """Object quaternion with +X = fwd and +Z = up (orthonormalised)."""
    f = Vector(fwd).normalized()
    u = Vector(up)
    u = (u - f * u.dot(f)).normalized()
    l = u.cross(f)
    M = Matrix((f, l, u)).transposed()
    return M.to_quaternion()

# ---------------------------------------------------------------- node building

class G:
    """Tiny graph builder for shader / geometry node trees."""

    def __init__(self, nt):
        self.nt = nt
        self.col = 0

    def n(self, typ, inputs=None, loc=None, **props):
        node = self.nt.nodes.new(typ)
        if loc is not None:
            node.location = loc
        else:
            self.col += 1
            node.location = (self.col * 180, 0)
        for k, v in props.items():
            setattr(node, k, v)
        for k, v in (inputs or {}).items():
            self.set(node.inputs[k], v)
        return node

    def set(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        elif isinstance(v, bpy.types.Node):
            self.nt.links.new(v.outputs[0], sock)
        else:
            sock.default_value = v

    def link(self, a, b):
        if isinstance(a, bpy.types.Node):
            a = a.outputs[0]
        self.nt.links.new(a, b)

    def math(self, op, a, b=None, c=None, clamp=False):
        node = self.n('ShaderNodeMath', operation=op, use_clamp=clamp)
        self.set(node.inputs[0], a)
        if b is not None:
            self.set(node.inputs[1], b)
        if c is not None:
            self.set(node.inputs[2], c)
        return node.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        node = self.n('ShaderNodeVectorMath', operation=op)
        self.set(node.inputs[0], a)
        if b is not None:
            self.set(node.inputs[1], b)
        if scale is not None:
            self.set(node.inputs['Scale'], scale)
        return node.outputs['Value'] if op in ('LENGTH', 'DOT_PRODUCT', 'DISTANCE') else node.outputs['Vector']

    def sep(self, v):
        node = self.n('ShaderNodeSeparateXYZ')
        self.set(node.inputs[0], v)
        return node.outputs

    def comb(self, x, y, z):
        node = self.n('ShaderNodeCombineXYZ')
        self.set(node.inputs[0], x)
        self.set(node.inputs[1], y)
        self.set(node.inputs[2], z)
        return node.outputs[0]

    def maprange(self, v, a, b, c, d, clamp=True, interp='LINEAR'):
        node = self.n('ShaderNodeMapRange', clamp=clamp, interpolation_type=interp)
        self.set(node.inputs[0], v)
        self.set(node.inputs[1], a)
        self.set(node.inputs[2], b)
        self.set(node.inputs[3], c)
        self.set(node.inputs[4], d)
        return node.outputs[0]

    def mixrgb(self, fac, a, b, blend='MIX'):
        node = self.n('ShaderNodeMix', data_type='RGBA', blend_type=blend)
        self.set(node.inputs[0], fac)
        self.set(node.inputs[6], a)
        self.set(node.inputs[7], b)
        return node.outputs[2]

    def value(self, v, label=None):
        node = self.n('ShaderNodeValue')
        node.outputs[0].default_value = v
        if label:
            node.label = label
            node.name = label
        return node


def new_material(name):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (1600, 0)
    return m, G(nt), out


def principled(g, **inputs):
    p = g.n('ShaderNodeBsdfPrincipled')
    for k, v in inputs.items():
        g.set(p.inputs[k.replace('_', ' ')], v)
    return p


def new_gn_tree(name, inputs):
    """inputs: list of (name, socket_type, default)"""
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    for (nm, st, dv) in inputs:
        s = ng.interface.new_socket(nm, in_out='INPUT', socket_type=st)
        if dv is not None and hasattr(s, 'default_value'):
            s.default_value = dv
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    g = G(ng)
    gi = g.n('NodeGroupInput', loc=(-400, 0))
    go = g.n('NodeGroupOutput', loc=(3000, 0))
    return ng, g, gi, go


def gn_ident(ng, name):
    for it in ng.interface.items_tree:
        if getattr(it, 'in_out', None) == 'INPUT' and it.name == name:
            return it.identifier
    raise KeyError(name)


def add_gn(ob, ng, **vals):
    mod = ob.modifiers.new(ng.name, 'NODES')
    mod.node_group = ng
    for k, v in vals.items():
        mod[gn_ident(ng, k)] = v
    return mod


def key_gn(ob, mod, name, frame, value):
    ident = gn_ident(mod.node_group, name)
    mod[ident] = value
    ob.keyframe_insert(data_path=f'modifiers["{mod.name}"]["{ident}"]', frame=frame)


def key_hide(ob, frame, hidden):
    ob.hide_render = hidden
    ob.hide_viewport = hidden
    ob.keyframe_insert('hide_render', frame=frame)
    ob.keyframe_insert('hide_viewport', frame=frame)


def visible_only(ob, ranges, f0=1, f1=400):
    """Keyframe hide_render so ob shows only inside the given [a, b] frame ranges."""
    state = None
    for f in range(f0, f1 + 1):
        vis = any(a <= f <= b for (a, b) in ranges)
        if vis != state:
            key_hide(ob, f, not vis)
            state = vis


def key_value_node(sock, frame, value):
    sock.default_value = value
    sock.keyframe_insert('default_value', frame=frame)
