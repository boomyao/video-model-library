import math
import bpy
import bmesh
import numpy as np
from mathutils import Vector, Matrix

MM = 0.001


def col(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent if parent is not None else bpy.context.scene.collection).children.link(c)
    return c


def link_to(ob, collection):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    collection.objects.link(ob)
    return ob


def mesh_np(name, verts, faces):
    verts = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
    if isinstance(faces, np.ndarray) and faces.ndim == 2:
        sizes = np.full(len(faces), faces.shape[1], dtype=np.int32)
        flat = faces.astype(np.int32).ravel()
    else:
        sizes = np.array([len(f) for f in faces], dtype=np.int32)
        flat = np.fromiter((i for f in faces for i in f), dtype=np.int32, count=int(sizes.sum()))
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set('co', verts.astype(np.float32).ravel())
    me.loops.add(len(flat))
    me.loops.foreach_set('vertex_index', flat)
    me.polygons.add(len(sizes))
    starts = np.zeros(len(sizes), dtype=np.int32)
    if len(sizes) > 1:
        starts[1:] = np.cumsum(sizes)[:-1]
    me.polygons.foreach_set('loop_start', starts)
    me.update(calc_edges=True)
    if len(sizes):
        me.shade_flat()
    return me


def points_mesh(name, pts, attrs=None):
    pts = np.asarray(pts, dtype=np.float32).reshape(-1, 3)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(pts))
    me.vertices.foreach_set('co', pts.ravel())
    if attrs:
        for an, (atype, vals) in attrs.items():
            a = me.attributes.new(an, atype, 'POINT')
            key = 'vector' if atype == 'FLOAT_VECTOR' else 'value'
            a.data.foreach_set(key, np.asarray(vals, dtype=np.float32).ravel())
    me.update()
    return me


def obj(name, data, collection, loc=(0, 0, 0), mat=None):
    ob = bpy.data.objects.new(name, data)
    ob.location = loc
    collection.objects.link(ob)
    if mat is not None and data is not None and hasattr(data, 'materials'):
        if isinstance(mat, (list, tuple)):
            for m in mat:
                data.materials.append(m)
        else:
            data.materials.append(mat)
    return ob


def recalc_normals(me, flip=False):
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if flip:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()


def smooth_by_angle_group():
    ng = bpy.data.node_groups.get('MS_SmoothByAngle')
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new('MS_SmoothByAngle', 'GeometryNodeTree')
    ng.is_modifier = True
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    s = ng.interface.new_socket('Angle', in_out='INPUT', socket_type='NodeSocketFloat')
    s.default_value = math.radians(30)
    s.subtype = 'ANGLE'
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes
    L = ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    ea = N.new('GeometryNodeInputMeshEdgeAngle')
    cmp_ = N.new('FunctionNodeCompare')
    cmp_.data_type = 'FLOAT'
    cmp_.operation = 'LESS_THAN'
    ssf = N.new('GeometryNodeSetShadeSmooth')
    ssf.domain = 'FACE'
    sse = N.new('GeometryNodeSetShadeSmooth')
    sse.domain = 'EDGE'
    L.new(gi.outputs['Geometry'], ssf.inputs['Mesh'])
    ssf.inputs['Shade Smooth'].default_value = True
    L.new(ea.outputs['Unsigned Angle'], cmp_.inputs[0])
    L.new(gi.outputs['Angle'], cmp_.inputs[1])
    L.new(ssf.outputs['Mesh'], sse.inputs['Mesh'])
    L.new(cmp_.outputs['Result'], sse.inputs['Shade Smooth'])
    L.new(sse.outputs['Mesh'], go.inputs['Geometry'])
    return ng


def add_smooth_mod(ob, angle_deg=30.0):
    m = ob.modifiers.new('SmoothByAngle', 'NODES')
    m.node_group = smooth_by_angle_group()
    for item in m.node_group.interface.items_tree:
        if getattr(item, 'name', '') == 'Angle' and item.in_out == 'INPUT':
            m[item.identifier] = math.radians(angle_deg)
    return m


def add_bevel(ob, width_mm, segments=3, angle_deg=30.0, smooth=True):
    b = ob.modifiers.new('Bevel', 'BEVEL')
    b.width = width_mm * MM
    b.segments = segments
    b.limit_method = 'ANGLE'
    b.angle_limit = math.radians(angle_deg)
    b.use_clamp_overlap = True
    b.miter_outer = 'MITER_ARC'
    if smooth:
        add_smooth_mod(ob, angle_deg)
    return b


def box_verts_faces(cx, cy, cz, sx, sy, sz):
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    v = np.array([[-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
                  [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz]]) + np.array([cx, cy, cz])
    f = np.array([[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])
    return v, f


def revolve_profile(profile_rz, segments, close_start_pole=False, close_end_pole=False, phase=0.0):
    prof = np.asarray(profile_rz, dtype=np.float64)
    a = np.linspace(0, 2 * np.pi, segments, endpoint=False) + phase
    ca, sa = np.cos(a), np.sin(a)
    verts = []
    rings = []
    idx = 0
    for j, (r, z) in enumerate(prof):
        if r < 1e-9:
            verts.append(np.array([[0.0, 0.0, z]]))
            rings.append(('pole', idx))
            idx += 1
        else:
            ring = np.stack([r * ca, r * sa, np.full(segments, z)], 1)
            verts.append(ring)
            rings.append(('ring', idx))
            idx += segments
    faces = []
    for j in range(len(prof) - 1):
        ta, ia = rings[j]
        tb, ib = rings[j + 1]
        for i in range(segments):
            i2 = (i + 1) % segments
            if ta == 'ring' and tb == 'ring':
                faces.append((ia + i, ia + i2, ib + i2, ib + i))
            elif ta == 'pole' and tb == 'ring':
                faces.append((ia, ib + i2, ib + i))
            elif ta == 'ring' and tb == 'pole':
                faces.append((ia + i, ia + i2, ib))
    return np.vstack(verts), faces, rings


def fillet_polyline(pts, radii, arc_seg=8):
    pts = [np.array(p, dtype=np.float64) for p in pts]
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        r = radii[k] if k < len(radii) else 0.0
        p0, p1, p2 = pts[k - 1], pts[k], pts[k + 1]
        if r <= 0:
            out.append(p1)
            continue
        u1 = p1 - p0
        u1 /= np.linalg.norm(u1)
        u2 = p2 - p1
        u2 /= np.linalg.norm(u2)
        cosang = np.clip(np.dot(u1, u2), -1, 1)
        theta = math.acos(cosang)
        if theta < 1e-6:
            out.append(p1)
            continue
        L = r * math.tan(theta / 2)
        t1 = p1 - u1 * L
        t2 = p1 + u2 * L
        cross = u1[0] * u2[1] - u1[1] * u2[0]
        n1 = np.array([-u1[1], u1[0]]) if cross > 0 else np.array([u1[1], -u1[0]])
        c = t1 + n1 * r
        a0 = math.atan2(t1[1] - c[1], t1[0] - c[0])
        a1 = math.atan2(t2[1] - c[1], t2[0] - c[0])
        da = a1 - a0
        if cross > 0 and da < 0:
            da += 2 * math.pi
        if cross < 0 and da > 0:
            da -= 2 * math.pi
        n = max(2, int(arc_seg * abs(da) / (math.pi / 2)) + 1)
        for i in range(n + 1):
            a = a0 + da * i / n
            out.append(c + r * np.array([math.cos(a), math.sin(a)]))
    out.append(pts[-1])
    res = [out[0]]
    for p in out[1:]:
        if np.linalg.norm(p - res[-1]) > 1e-7:
            res.append(p)
    return np.array(res)


def rounded_rect_2d(w, h, r, seg=8):
    r = min(r, w / 2 - 1e-6, h / 2 - 1e-6) if r > 0 else 0
    pts = []
    if r <= 0:
        return np.array([[w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2], [-w / 2, -h / 2]])
    corners = [(w / 2 - r, -h / 2 + r, -90), (w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180)]
    for cx, cy, a0 in corners:
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    out = [pts[0]]
    for p in pts[1:]:
        if math.dist(p, out[-1]) > 1e-7:
            out.append(p)
    if math.dist(out[0], out[-1]) < 1e-7:
        out.pop()
    return np.array(out)


def circle_2d(r, n=32, phase=0.0):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False) + phase
    return np.stack([r * np.cos(a), r * np.sin(a)], 1)


def polygon_area(p):
    x, y = p[:, 0], p[:, 1]
    return 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)


class MeshAccum:
    def __init__(self):
        self.v = []
        self.f = []
        self.n = 0
        self.mi = []

    def add(self, verts, faces, mat_index=0):
        verts = np.asarray(verts, dtype=np.float64).reshape(-1, 3)
        for fc in faces:
            self.f.append(tuple(int(i) + self.n for i in fc))
            self.mi.append(mat_index)
        self.v.append(verts)
        self.n += len(verts)

    def add_box(self, c, s, mat_index=0):
        v, f = box_verts_faces(c[0], c[1], c[2], s[0], s[1], s[2])
        self.add(v, f.tolist(), mat_index)

    def add_cyl(self, c, r, h, n=24, axis='Z', mat_index=0, r_top=None):
        rt = r if r_top is None else r_top
        a = np.linspace(0, 2 * np.pi, n, endpoint=False)
        b = np.column_stack([r * np.cos(a), r * np.sin(a), np.full(n, -h / 2)])
        t = np.column_stack([rt * np.cos(a), rt * np.sin(a), np.full(n, h / 2)])
        v = np.vstack([b, t])
        if axis == 'X':
            v = v[:, [2, 0, 1]]
        elif axis == 'Y':
            v = v[:, [0, 2, 1]]
        v = v + np.asarray(c)
        f = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
        for i in range(n):
            i2 = (i + 1) % n
            f.append((i, i2, n + i2, n + i))
        self.add(v, f, mat_index)

    def build(self, name, scale=MM, recalc=True):
        if not self.v:
            return mesh_np(name, np.zeros((0, 3)), [])
        me = mesh_np(name, np.vstack(self.v) * scale, self.f)
        if len(set(self.mi)) > 1:
            me.polygons.foreach_set('material_index', np.array(self.mi, dtype=np.int32))
        if recalc:
            recalc_normals(me)
        return me


def offset_polyline(pts, d, closed=True):
    p = np.asarray(pts, dtype=np.float64)
    n = len(p)
    out = np.zeros_like(p)
    for i in range(n):
        if closed:
            a = p[i - 1]
            c = p[(i + 1) % n]
        else:
            a = p[max(i - 1, 0)]
            c = p[min(i + 1, n - 1)]
        b = p[i]
        t1 = b - a
        t2 = c - b
        if np.linalg.norm(t1) < 1e-12:
            t1 = t2
        if np.linalg.norm(t2) < 1e-12:
            t2 = t1
        t1 = t1 / np.linalg.norm(t1)
        t2 = t2 / np.linalg.norm(t2)
        n1 = np.array([t1[1], -t1[0]])
        n2 = np.array([t2[1], -t2[0]])
        nm = n1 + n2
        nn = np.linalg.norm(nm)
        if nn < 1e-9:
            nm = n1
        else:
            nm = nm / nn
        cosh = max(0.2, float(np.dot(nm, n1)))
        out[i] = b + nm * d / cosh
    return out


def slab_from_loops(outer, holes, z0, z1):
    from mathutils import geometry as mg, Vector
    loops = [np.asarray(outer, dtype=np.float64)]
    if polygon_area(loops[0]) < 0:
        loops[0] = loops[0][::-1]
    for h in holes:
        h = np.asarray(h, dtype=np.float64)
        if polygon_area(h) > 0:
            h = h[::-1]
        loops.append(h)
    allv = np.vstack(loops)
    n = len(allv)
    tris = mg.tessellate_polygon([[Vector((x, y, 0)) for x, y in lp] for lp in loops])
    top = np.column_stack([allv, np.full(n, z1)])
    bot = np.column_stack([allv, np.full(n, z0)])
    verts = np.vstack([top, bot])
    faces = [tuple(t) for t in tris]
    faces += [(t[2] + n, t[1] + n, t[0] + n) for t in tris]
    off = 0
    for lp in loops:
        m = len(lp)
        for k in range(m):
            a = off + k
            b = off + (k + 1) % m
            faces.append((a, a + n, b + n, b))
        off += m
    return verts, faces


def sweep_section_along_path2d(path2d, section, z_center, closed=False):
    path = np.asarray(path2d, dtype=np.float64)
    sec = np.asarray(section, dtype=np.float64)
    n = len(path)
    m = len(sec)
    verts = []
    for i in range(n):
        if closed:
            t = path[(i + 1) % n] - path[i - 1]
        else:
            t = path[min(i + 1, n - 1)] - path[max(i - 1, 0)]
        t = t / np.linalg.norm(t)
        nrm = np.array([t[1], -t[0]])
        for (u, v) in sec:
            verts.append((path[i, 0] + nrm[0] * u, path[i, 1] + nrm[1] * u, z_center + v))
    faces = []
    rng = n if closed else n - 1
    for i in range(rng):
        i2 = (i + 1) % n
        for j in range(m):
            j2 = (j + 1) % m
            faces.append((i * m + j, i * m + j2, i2 * m + j2, i2 * m + j))
    if not closed:
        faces.append(tuple(range(m - 1, -1, -1)))
        faces.append(tuple((n - 1) * m + j for j in range(m)))
    return np.array(verts), faces


def sweep_section_along_path3d(path3d, section, up=(0, 0, 1)):
    path = np.asarray(path3d, dtype=np.float64)
    sec = np.asarray(section, dtype=np.float64)
    n = len(path)
    m = len(sec)
    verts = []
    upv = np.array(up, dtype=np.float64)
    prev_b = None
    for i in range(n):
        t = path[min(i + 1, n - 1)] - path[max(i - 1, 0)]
        t = t / np.linalg.norm(t)
        if prev_b is None:
            b = np.cross(t, upv)
            if np.linalg.norm(b) < 1e-6:
                b = np.cross(t, np.array([1.0, 0, 0]))
        else:
            b = prev_b - np.dot(prev_b, t) * t
        b = b / np.linalg.norm(b)
        nn = np.cross(b, t)
        prev_b = b
        for (u, v) in sec:
            verts.append(path[i] + b * u + nn * v)
    faces = []
    for i in range(n - 1):
        for j in range(m):
            j2 = (j + 1) % m
            faces.append((i * m + j, i * m + j2, (i + 1) * m + j2, (i + 1) * m + j))
    faces.append(tuple(range(m - 1, -1, -1)))
    faces.append(tuple((n - 1) * m + j for j in range(m)))
    return np.array(verts), faces


def fillet_path3d(pts, radius, seg=8):
    p = [np.array(x, dtype=np.float64) for x in pts]
    out = [p[0]]
    for k in range(1, len(p) - 1):
        a, b, c = p[k - 1], p[k], p[k + 1]
        u1 = b - a
        u1 /= np.linalg.norm(u1)
        u2 = c - b
        u2 /= np.linalg.norm(u2)
        cosang = np.clip(np.dot(u1, u2), -1, 1)
        th = math.acos(cosang)
        if th < 1e-4:
            out.append(b)
            continue
        L = radius * math.tan(th / 2)
        t1 = b - u1 * L
        t2 = b + u2 * L
        for i in range(seg + 1):
            s = i / seg
            q = (1 - s) ** 2 * t1 + 2 * (1 - s) * s * b + s * s * t2
            out.append(q)
    out.append(p[-1])
    return np.array(out)
