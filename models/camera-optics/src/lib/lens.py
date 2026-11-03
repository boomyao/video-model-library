"""The film's hero asset: a real phone lens (Largan US10302915B2, embodiment 1, 8 plastic elements) built from the
patent prescription, and the rays our own trace sent through it.

Data: 画面/assets/lens_US10302915_e1.json, written by 工具/lens_trace.py (surface vertices, radii, conics, aspheric
coefficients, clear apertures, and meridional ray polylines). Everything here is in the trace's millimetres.

Placement: the optical axis runs along world -Z (light comes from above and lands on the sensor below), the
meridional plane is the world X-Z plane, so rays (trace y -> world x) lie in y = 0. A cutaway removes the half
with y < 0 (the side facing a camera placed at -y) and caps the cut with a section face.

    import lens as LN
    d = LN.load()
    objs = LN.build_stack(d, scale=S, origin=(0, 0, 0), cut=True)          # list of lens objects (+ filter, sensor)
    rays = LN.build_rays(d, scale=S, fields=(0, 0.7, 1.0))                  # list of (curve object, field, pupil)
    LN.grow(rays, k)                                                        # 0..1: draw rays from the front to the image

`scale` = Blender units per millimetre (the shot kit uses MM = 0.001; a magnified table-top set may use 0.01).
"""
import json
import math
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "assets", "lens_US10302915_e1.json"))


def load(path=DATA):
    return json.load(open(path, encoding="utf8"))


def sag(s, r):
    """Surface sag (mm) at height r (mm): conic + even aspheric terms, Largan's convention."""
    z = 0.0
    if s.get("R"):
        c = 1.0 / s["R"]
        z += c * r * r / (1 + math.sqrt(max(0.0, 1 - (1 + s.get("k", 0.0)) * c * c * r * r)))
    for i, a in (s.get("A") or {}).items():
        z += a * r ** int(i)
    return z


def profile(el, n=48, flange=0.22, min_edge=0.08):
    """(r, z) outline of one element, from the front vertex out along the front surface, across the flange, down the
    rim and back in along the rear surface. z grows toward the image (trace convention)."""
    f, b = el["front"], el["back"]
    rout = max(f["ap"], b["ap"]) + flange
    fz = [f["z"] + sag(f, f["ap"] * i / n) for i in range(n + 1)]
    bz = [b["z"] + sag(b, b["ap"] * i / n) for i in range(n + 1)]
    zf_edge, zb_edge = fz[-1], bz[-1]
    if zb_edge - zf_edge < min_edge:          # keep a real rim on strongly curved (gull-wing) elements
        zb_edge = zf_edge + min_edge
    pts = [(f["ap"] * i / n, fz[i]) for i in range(n + 1)]
    pts += [(rout, zf_edge), (rout, zb_edge)]
    pts += [(b["ap"] * i / n, bz[i]) for i in range(n, -1, -1)]
    return pts, rout


def _material(name, ior, kind="lens"):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.92, 0.95, 0.97, 1)
    p.inputs["Roughness"].default_value = 0.0 if kind == "lens" else 0.06
    p.inputs["Transmission Weight"].default_value = 1.0
    p.inputs["IOR"].default_value = ior
    if kind == "lens" and "Thin Film Thickness" in p.inputs:   # anti-reflection coating: violet/green glints
        p.inputs["Thin Film Thickness"].default_value = 320.0
        p.inputs["Thin Film IOR"].default_value = 1.38
    return m


def build_element(el, name, scale=0.001, origin=(0, 0, 0), cut=False, seg=160, mat=None, cap_mat=None):
    """Mesh of revolution for one element. cut=True keeps the half y >= 0 and closes the cut with two section faces."""
    pts, rout = profile(el)
    ox, oy, oz = origin
    a0, a1 = (0.0, math.pi) if cut else (0.0, 2 * math.pi)
    nseg = seg // 2 if cut else seg
    verts, faces = [], []
    npf = len(pts)
    rings = nseg + 1 if cut else nseg
    for k in range(rings):
        a = a0 + (a1 - a0) * k / nseg
        ca, sa = math.cos(a), math.sin(a)
        for (r, z) in pts:
            verts.append((ox + r * ca * scale, oy + r * sa * scale, oz - z * scale))
    for k in range(nseg):
        k2 = (k + 1) % rings
        for i in range(npf - 1):
            faces.append((k * npf + i, k * npf + i + 1, k2 * npf + i + 1, k2 * npf + i))
    me = bpy.data.meshes.new(name)
    if cut:
        # section faces: the profile polygon at a = 0 (x > 0 side) and at a = pi (x < 0 side)
        for k in (0, nseg):
            faces.append(tuple(k * npf + i for i in range(npf)))
    me.from_pydata(verts, [], faces)
    me.validate()
    # both section caps were written with the same vertex order, so one of them faced into the glass and Cycles
    # refracted that half as if light were leaving the plastic (found by group A, 2026-10-30): make all normals
    # consistent and outward
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = len(poly.vertices) == 4
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    mat = mat or _material("lens_%s" % (el.get("nd") or 1.54), el.get("nd") or 1.54)
    ob.data.materials.append(mat)
    if cut:
        cm = cap_mat or _material("lens_cut_%s" % (el.get("nd") or 1.54), el.get("nd") or 1.54, kind="cut")
        ob.data.materials.append(cm)
        for poly in me.polygons:
            if len(poly.vertices) > 4:
                poly.material_index = 1
    ob["rout_mm"] = rout
    return ob


def build_stack(d, scale=0.001, origin=(0, 0, 0), cut=False, sensor=True):
    """All elements (8 plastic lenses + the IR-cut filter); optionally a dark sensor slab at the image plane."""
    objs = []
    for i, el in enumerate(d["elements"]):
        nm = "IR_filter" if "IR" in el["name"] else "L%d" % (i + 1)
        objs.append(build_element(el, nm, scale, origin, cut))
    if sensor:
        ox, oy, oz = origin
        r = max(el["back"]["ap"] for el in d["elements"]) * 1.15
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        s = bpy.context.active_object
        s.name = "sensor"
        s.scale = (2 * r * scale, (r if cut else 2 * r) * scale, 0.25 * scale)
        s.location = (ox, oy + (r / 2 * scale if cut else 0), oz - (d["image_z"] + 0.125) * scale)
        m = bpy.data.materials.new("sensor")
        m.use_nodes = True
        p = m.node_tree.nodes["Principled BSDF"]
        p.inputs["Base Color"].default_value = (0.02, 0.022, 0.03, 1)
        p.inputs["Metallic"].default_value = 0.6
        p.inputs["Roughness"].default_value = 0.25
        if "Thin Film Thickness" in p.inputs:
            p.inputs["Thin Film Thickness"].default_value = 500.0
            p.inputs["Thin Film IOR"].default_value = 1.6
        s.data.materials.append(m)
        objs.append(s)
    return objs


def ray_material(name="ray", color=(1.0, 0.86, 0.66), strength=6.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = strength
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], o.inputs[0])
    return m


def build_rays(d, scale=0.001, origin=(0, 0, 0), fields=(0.0, 0.7, 1.0), signs=(1, -1), radius_mm=0.004,
               pre_mm=1.2, mats=None, pupil_every=2, front_mm=0.02):
    """One curve per traced ray (meridional plane, y = 0). pre_mm: how far in front of the first surface a ray starts.
    mats: {abs(field): material}. pupil_every=2 keeps every other of the 15 traced pupil rays. front_mm lifts the rays
    just in front of the section face (toward a camera at -y). Returns [(object, field, pupil)]."""
    ox, oy, oz = origin
    out = []
    for n, r in enumerate(d["rays"]):
        if round((r["pupil"] + 1) * 7) % pupil_every:
            continue
        if abs(r["field"]) not in fields or (r["field"] != 0 and (1 if r["field"] > 0 else -1) not in signs):
            continue
        pts = [list(p) for p in r["pts"]]
        # move the start point to pre_mm in front of the first lens vertex, along the ray
        (z0, y0), (z1, y1) = pts[0], pts[1]
        t = (z1 - (-pre_mm)) / (z1 - z0) if z1 != z0 else 0
        pts[0] = [z1 - (z1 - z0) * t, y1 - (y1 - y0) * t]
        cu = bpy.data.curves.new("ray", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = radius_mm * scale
        cu.bevel_resolution = 2
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for i, (z, y) in enumerate(pts):
            sp.points[i].co = (ox + y * scale, oy - front_mm * scale, oz - z * scale, 1)
        ob = bpy.data.objects.new("ray_%+.2f_%+.2f" % (r["field"], r["pupil"]), cu)
        bpy.context.scene.collection.objects.link(ob)
        m = (mats or {}).get(abs(r["field"])) or ray_material()
        ob.data.materials.append(m)
        out.append((ob, r["field"], r["pupil"]))
    return out


def grow(rays, k, stagger=0.0):
    """Draw every ray from its start up to fraction k (0..1) of its length; stagger delays outer pupil rays a little."""
    for ob, field, pupil in rays:
        kk = max(0.0, min(1.0, (k - stagger * abs(pupil)) / max(1e-6, 1 - stagger)))
        ob.data.bevel_factor_start = 0.0
        ob.data.bevel_factor_end = kk
        ob.hide_render = kk <= 0.0
