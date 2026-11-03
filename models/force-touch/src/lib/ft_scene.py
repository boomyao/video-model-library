"""Force Touch trackpad (12-inch MacBook, 2015) — look-dev scene, first pass.

Geometry is measured from:
  - iFixit Retina MacBook 2015 teardown, step 21 photo (straight-on underside), step 19/20 photos
  - Apple's own March 2015 renders (trackpad_internals / internals_trackpad / trackpad_top)
Units: millimetres in code, converted to metres for Blender.

Run:  Blender -b --factory-startup -P ft_scene.py -- --out /path/frame.png [--res 1920x1080] [--samples 96] [--shot hero]
"""
import bpy, bmesh, math, sys, os
from mathutils import Vector, Euler

MM = 0.001


def argval(name, default=None):
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if name in argv:
        return argv[argv.index(name) + 1]
    return default


# --------------------------------------------------------------------------- materials
def principled(name, **kw):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    for k, v in kw.items():
        b.inputs[k].default_value = v
    return m, b


def add_bump(m, b, scale, strength, detail=2.0, distance=0.00002):
    nt = m.node_tree
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = detail
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return tex


def make_materials():
    M = {}
    M["alu"], b = principled("alu", **{"Base Color": (0.78, 0.78, 0.79, 1), "Metallic": 1.0, "Roughness": 0.36})
    add_bump(M["alu"], b, 9000, 0.12)
    M["glass_face"], b = principled("glass_face", **{"Base Color": (0.70, 0.70, 0.71, 1), "Metallic": 0.85,
                                                     "Roughness": 0.30, "Coat Weight": 0.25, "Coat Roughness": 0.12})
    M["glass_edge"], b = principled("glass_edge", **{"Base Color": (0.85, 0.90, 0.92, 1), "Roughness": 0.08,
                                                     "Transmission Weight": 0.85, "IOR": 1.5})
    M["plate"], b = principled("plate", **{"Base Color": (0.30, 0.285, 0.27, 1), "Metallic": 0.9, "Roughness": 0.42})
    add_bump(M["plate"], b, 300, 0.05, detail=6)
    M["pcb"], b = principled("pcb", **{"Base Color": (0.012, 0.012, 0.016, 1), "Roughness": 0.38,
                                       "Coat Weight": 0.4, "Coat Roughness": 0.25})
    M["chip"], b = principled("chip", **{"Base Color": (0.035, 0.035, 0.038, 1), "Roughness": 0.55})
    M["gold"], b = principled("gold", **{"Base Color": (0.95, 0.72, 0.32, 1), "Metallic": 1.0, "Roughness": 0.25})
    M["black"], b = principled("black", **{"Base Color": (0.018, 0.018, 0.02, 1), "Roughness": 0.48,
                                           "Coat Weight": 0.15, "Coat Roughness": 0.3})
    M["foam"], b = principled("foam", **{"Base Color": (0.03, 0.03, 0.032, 1), "Roughness": 0.9})
    M["copper"], b = principled("copper", **{"Base Color": (0.93, 0.47, 0.25, 1), "Metallic": 1.0, "Roughness": 0.24,
                                             "Coat Weight": 0.6, "Coat Roughness": 0.12})
    M["steel"], b = principled("steel", **{"Base Color": (0.62, 0.62, 0.64, 1), "Metallic": 1.0, "Roughness": 0.28,
                                           "Anisotropic": 0.6})
    M["core"], b = principled("core", **{"Base Color": (0.16, 0.16, 0.17, 1), "Metallic": 1.0, "Roughness": 0.42})
    M["spring"], b = principled("spring", **{"Base Color": (0.74, 0.74, 0.75, 1), "Metallic": 1.0, "Roughness": 0.33})
    add_bump(M["spring"], b, 2500, 0.08)
    M["kapton"], b = principled("kapton", **{"Base Color": (0.88, 0.47, 0.06, 1), "Roughness": 0.3,
                                             "Coat Weight": 0.5, "Coat Roughness": 0.1})
    # strain-gauge serpentine: fine gold stripes on kapton
    nt = M["kapton"].node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = 4200.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[1].position = 0.55
    ramp.color_ramp.elements[0].color = (0.80, 0.40, 0.04, 1)
    ramp.color_ramp.elements[1].color = (0.93, 0.70, 0.22, 1)
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    M["gel"], b = principled("gel", **{"Base Color": (0.9, 0.9, 0.9, 1), "Roughness": 0.22,
                                       "Transmission Weight": 0.9, "IOR": 1.41})
    M["ivory"], b = principled("ivory", **{"Base Color": (0.72, 0.70, 0.62, 1), "Roughness": 0.4})
    M["label"], b = principled("label", **{"Base Color": (0.86, 0.86, 0.86, 1), "Roughness": 0.5})
    M["padmark"], b = principled("padmark", **{"Base Color": (0.20, 0.19, 0.18, 1), "Metallic": 0.6, "Roughness": 0.55})
    M["flex"], b = principled("flex", **{"Base Color": (0.03, 0.03, 0.033, 1), "Roughness": 0.33,
                                         "Coat Weight": 0.5, "Coat Roughness": 0.15})
    M["floor"], b = principled("floor", **{"Base Color": (0.006, 0.006, 0.007, 1), "Roughness": 0.22,
                                           "Coat Weight": 0.2, "Coat Roughness": 0.08})
    return M


# --------------------------------------------------------------------------- geometry helpers
def rrect_pts(x0, y0, x1, y1, r, seg=8):
    r = max(0.0, min(r, (x1 - x0) / 2 - 1e-6, (y1 - y0) / 2 - 1e-6))
    pts = []
    for cx, cy, a0 in ((x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def prism(name, pts, z0, z1, mat, bevel=0.0, parent=None, holes=None):
    """Extrude a 2D outline (mm) between z0 and z1 (mm). Optional bevel on top/bottom rims."""
    bm = bmesh.new()
    vs = [bm.verts.new((x * MM, y * MM, z0 * MM)) for x, y in pts]
    face = bm.faces.new(vs)
    res = bmesh.ops.extrude_face_region(bm, geom=[face])
    top = [e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, (z1 - z0) * MM))
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        rim = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-9]
        bmesh.ops.bevel(bm, geom=rim, offset=bevel * MM, segments=3, profile=0.6, affect="EDGES")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    smooth_by_angle(ob)
    if parent:
        ob.parent = parent
    return ob


def smooth_by_angle(ob, angle=35):
    me = ob.data
    try:
        me.set_sharp_from_angle(angle=math.radians(angle))
    except Exception:
        mod = ob.modifiers.new("es", "EDGE_SPLIT")
        mod.split_angle = math.radians(angle)


def rbox(name, x0, y0, x1, y1, z0, z1, mat, r=0.3, bevel=0.08, parent=None, seg=5):
    return prism(name, rrect_pts(x0, y0, x1, y1, r, seg), z0, z1, mat, bevel, parent)


def cyl(name, x, y, z0, z1, rad, mat, parent=None, seg=32, bevel=0.0):
    pts = [(x + rad * math.cos(2 * math.pi * i / seg), y + rad * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    return prism(name, pts, z0, z1, mat, bevel, parent)


def coil(name, x0, x1, y0, y1, z0, z1, mat, wire_r=0.07, pitch=0.155, parent=None):
    """Copper winding. Each turn lies in an XZ plane and the turns stack along Y: the coil is wound
    round a core tooth that points along Y, at the steel rail (iFixit 39841 step 19/21 close-ups:
    the wire runs along the long side of each coil and wraps round its two short ends)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = wire_r * MM
    cu.bevel_resolution = 2
    n = int((y1 - y0) / pitch)
    loop = rrect_pts(x0, z0, x1, z1, min(1.0, (z1 - z0) / 2 - 0.05), 7)
    for i in range(n):
        y = y0 + pitch * (i + 0.5)
        sp = cu.splines.new("POLY")
        sp.points.add(len(loop) - 1)
        for p, (x, z) in zip(sp.points, loop):
            # slight per-turn jitter so windings look hand-laid, not CG-perfect
            j = 0.010 * math.sin(i * 12.9898 + x * 3.1)
            p.co = (x * MM, (y + j) * MM, z * MM, 1)
        sp.use_cyclic_u = True
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    if parent:
        ob.parent = parent
    return ob


def empty(name, parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(e)
    if parent:
        e.parent = parent
    return e


# --------------------------------------------------------------------------- the module (underside up)
COILS = ((-24.0, -16.0), (-15.0, -0.5), (0.5, 15.0), (16.0, 24.0))  # x ranges, mm (measured)


def build_plate(M):
    """Glass + stiffener + sensor/controller board + coil assembly. z=0 is the inner face; +z = into the laptop."""
    root = empty("PLATE")
    prism("glass", rrect_pts(-56.25, -35.0, 56.25, 35.0, 1.5, 10), -1.3, -0.4, M["glass_edge"], 0.1, root)
    prism("glass_coat", rrect_pts(-56.2, -34.95, 56.2, 34.95, 1.5, 10), -1.33, -1.3, M["glass_face"], 0.0, root)
    prism("stiffener", rrect_pts(-55.85, -34.6, 55.85, 34.6, 1.2, 10), -0.4, 0.0, M["plate"], 0.06, root)
    # controller board island
    pcb_pts = [(-35.8, 8.5), (-28.6, 8.5), (-28.6, 11.4), (28.6, 11.4), (28.6, 8.5), (35.8, 8.5), (35.8, 32.9), (-35.8, 32.9)]
    prism("pcb", pcb_pts, -0.05, 0.12, M["pcb"], 0.03, root)
    for sx in (-1, 1):
        rbox(f"fpc_top_{sx}", sx * 28.5 - 6.2, 30.0, sx * 28.5 + 6.2, 34.6, 0.12, 0.95, M["ivory"], 0.2, 0.05, root)
        rbox(f"fpc_top_latch_{sx}", sx * 28.5 - 6.0, 30.2, sx * 28.5 + 6.0, 31.6, 0.95, 1.05, M["black"], 0.1, 0.03, root)
        rbox(f"fpc_side_{sx}", sx * 31.9 - 2.0, 10.9, sx * 31.9 + 2.0, 13.9, 0.12, 0.85, M["black"], 0.15, 0.04, root)
        cyl(f"standoff_{sx}", sx * 9.6, 20.4, 0.12, 0.85, 1.45, M["steel"], root, bevel=0.3)
    for i, (cx, cy, s) in enumerate(((-19.8, 23.0, 6.0), (0.3, 21.6, 6.0), (31.1, 23.4, 6.2), (-31.7, 19.9, 3.0),
                                     (21.5, 21.0, 2.2), (14.8, 24.0, 1.6), (-27.0, 26.5, 1.8))):
        rbox(f"ic_{i}", cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2, 0.12, 0.92, M["chip"], 0.15, 0.05, root)
    rbox("conn_a", -15.3, 26.7, -3.5, 29.4, 0.12, 0.95, M["black"], 0.15, 0.05, root)
    rbox("conn_b", 3.2, 26.6, 15.2, 29.2, 0.12, 0.95, M["black"], 0.15, 0.05, root)
    # passives + gold test pads (pseudo-random but deterministic)
    k = 0
    for i in range(22):
        for j in range(7):
            k += 1
            h = math.sin(k * 127.1) * 43758.5453
            h -= math.floor(h)
            x, y = -34.0 + i * 3.15 + (h - 0.5), 10.0 + j * 3.2 + (h * 7 % 1 - 0.5)
            if 11.0 < y < 18.4 and abs(x) < 28.5:
                continue  # under the coil frame
            if h < 0.30:
                cyl(f"tp_{k}", x, y, 0.12, 0.14, 0.27, M["gold"], root, seg=12)
            elif h < 0.42:
                rbox(f"smd_{k}", x - 0.5, y - 0.25, x + 0.5, y + 0.25, 0.12, 0.55, M["chip"] if h < 0.36 else M["ivory"],
                     0.05, 0.02, root)
    # coil assembly (rides on the plate in the 12-inch MacBook)
    prism("coil_frame", rrect_pts(-27.7, 11.5, 27.7, 17.9, 3.2, 10), 0.12, 2.75, M["black"], 0.12, root)
    for sx in (-1, 1):
        cyl(f"frame_screw_{sx}", sx * 24.8, 15.3, 2.75, 2.95, 1.25, M["black"], root, bevel=0.06)
    # (the white part label that sits here on the real module is left out: without its print it read as a blank sticker)
    rbox("core_spine", -24.6, 4.9, 24.6, 10.4, 0.55, 2.15, M["black"], 0.2, 0.05, root)
    # per coil: steel tooth (pole face looks at the rail, -y), bobbin flange on the rail side, winding
    for i, (a, bx) in enumerate(COILS):
        rbox(f"tooth_{i}", a + 0.75, 3.4, bx - 0.75, 11.2, 0.55, 2.15, M["core"], 0.15, 0.04, root)
        rbox(f"flange_{i}", a + 0.45, 3.55, bx - 0.45, 4.1, 0.0, 1.05, M["black"], 0.12, 0.04, root)
        coil(f"coil_{i}", a + 0.08, bx - 0.08, 4.15, 11.05, 0.2, 2.5, M["copper"], parent=root)
    # bobbin posts between coils on the board side (the winding leads disappear into these)
    for i, px in enumerate((-15.5, 0.0, 15.5)):
        rbox(f"post_{i}", px - 0.75, 10.3, px + 0.75, 11.9, 0.12, 2.62, M["black"], 0.2, 0.05, root)
    for sx in (-1, 1):
        rbox(f"endcap_{sx}", sx * 24.6 - 0.45, 4.0, sx * 24.6 + 0.45, 11.6, 0.12, 2.62, M["black"], 0.2, 0.05, root)
    # foam strip + corner gel-pad footprints
    prism("foam", rrect_pts(-32.4, -21.4, 32.1, -13.0, 4.2, 12), 0.0, 0.45, M["foam"], 0.1, root)
    for sx in (-1, 1):
        for sy, (yr, yt) in ((1, (22.6, 30.6)), (-1, (-19.8, -27.8))):
            prism(f"padmark_{sx}_{sy}", paddle_pts(sx * 43.0, yr, yt, 8.7), 0.0, 0.03, M["padmark"], 0.0, root)
    return root


def paddle_pts(cx, y_root, y_tip, w):
    """A tongue: straight sides, semicircular tip. y_tip beyond y_root in either direction."""
    r = w / 2
    s = 1 if y_tip > y_root else -1
    pts = [(cx - s * r, y_root), (cx + s * r, y_root)]  # root edge
    for i in range(73):                                 # fine enough that the tip stays round in a 4K close-up
        a = math.radians(0 + 180 * i / 72)
        pts.append((cx + s * r * math.cos(a), (y_tip - s * r) + s * r * math.sin(a)))
    return pts if s > 0 else pts


BRACKET_Z = 0.28  # gel-pad thickness: the sheet rides this far above the plate's inner face


def build_bracket(M):
    """H-shaped sensor bracket: fixed to the case; four spring tongues carry the plate. Strain gauges at tongue roots."""
    root = empty("BRACKET")
    t0, t1 = 0.0, 0.45  # sheet thickness
    rbox("spine", -40.0, -4.6, 40.0, 1.3, t0, t1, M["black"], 0.6, 0.04, root)
    # steel rail stands up from the spine, level with the coil pole faces (iFixit 39841 step 19, images 1-3)
    rbox("rail", -26.0, 1.15, 26.0, 2.95, t0, t0 + 2.15, M["steel"], 0.15, 0.06, root)
    for sx in (-1, 1):
        cx = sx * 43.0
        rbox(f"arm_{sx}", cx - 4.5, -17.5, cx + 4.5, 20.3, t0, t1, M["black"], 0.8, 0.04, root)
        for sy, (yr, yt) in ((1, (20.3, 31.0)), (-1, (-17.5, -28.2))):
            prism(f"tongue_{sx}_{sy}", paddle_pts(cx, yr, yt, 8.7), t0, t1 - 0.12, M["spring"], 0.04, root)
            g0, g1 = (yr - 0.6, yr + 3.2) if sy > 0 else (yr - 3.2, yr + 0.6)
            rbox(f"gauge_{sx}_{sy}", cx - 4.2, g0, cx + 4.2, g1, t1 - 0.12, t1 - 0.04, M["kapton"], 0.15, 0.0, root)
            # gel pad on the tongue tip (towards the plate = -z)
            yc = yt - sy * 4.3
            prism(f"gel_{sx}_{sy}", paddle_pts(cx, yc - sy * 3.4, yt - sy * 0.3, 7.6), t0 - 0.28, t0, M["gel"], 0.05, root)
        for yy in (-9.0, 11.8):
            cyl(f"insert_{sx}_{yy}", cx, yy, t0 - 0.2, t1 + 0.35, 1.5, M["steel"], root, bevel=0.1)
            cyl(f"insert_hole_{sx}_{yy}", cx, yy, t1 + 0.35, t1 + 0.36, 0.75, M["black"], root)
    rbox("flex_spine", -38.5, -3.9, 38.5, 0.6, t1, t1 + 0.07, M["flex"], 0.5, 0.0, root)
    for sx in (-1, 1):
        rbox(f"flex_arm_{sx}", sx * 43.0 - 3.6, -17.0, sx * 43.0 + 3.6, 19.8, t1, t1 + 0.07, M["flex"], 0.6, 0.0, root)
    cyl("insert_c", 0.0, -1.6, t0 - 0.2, t1 + 0.35, 1.5, M["steel"], root, bevel=0.1)
    cyl("insert_hole_c", 0.0, -1.6, t1 + 0.35, t1 + 0.36, 0.75, M["black"], root)
    return root


# --------------------------------------------------------------------------- stage
def area(name, loc, target, size, energy, color=(1, 1, 1), size_y=None, spread=math.radians(180)):
    li = bpy.data.lights.new(name, "AREA")
    li.energy = energy
    li.color = color
    li.shape = "RECTANGLE" if size_y else "SQUARE"
    li.size = size
    if size_y:
        li.size_y = size_y
    li.spread = spread
    ob = bpy.data.objects.new(name, li)
    bpy.context.collection.objects.link(ob)
    ob.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


def setup_render(res, samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    want = "METAL" if sys.platform == "darwin" else "OPTIX"   # the 4090 render box runs Linux
    prefs.compute_device_type = want
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == want
    sc.cycles.device = "GPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8
    sc.cycles.transmission_bounces = 8
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    sc.render.image_settings.file_format = "PNG"
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.0, 0.0, 0.0, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    sc.world = w
    return sc


def camera(loc, target, lens, fstop=None, focus=None):
    cam = bpy.data.cameras.new("cam")
    cam.lens = lens
    cam.sensor_width = 36
    cam.clip_start = 0.005
    cam.clip_end = 20
    ob = bpy.data.objects.new("cam", cam)
    bpy.context.collection.objects.link(ob)
    ob.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if fstop:
        cam.dof.use_dof = True
        cam.dof.aperture_fstop = fstop
        cam.dof.focus_distance = (Vector(focus if focus else target) - Vector(loc)).length
    bpy.context.scene.camera = ob
    return ob


def main():
    out = argval("--out", "/tmp/ft_look.png")
    res = tuple(int(v) for v in argval("--res", "1920x1080").split("x"))
    samples = int(argval("--samples", "96"))
    shot = argval("--shot", "hero")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = setup_render(res, samples)
    M = make_materials()

    plate = build_plate(M)
    bracket = build_bracket(M)
    # exploded: bracket hovers above the plate (plate is underside-up)
    lift = float(argval("--lift", "9.0"))
    bracket.location = (0, 0, (BRACKET_Z + lift) * MM)

    # glossy black stage
    bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, -14 * MM))
    floor = bpy.context.active_object
    floor.data.materials.append(M["floor"])

    def v3(key, default):
        s_ = argval(key)
        return tuple(float(x) * MM for x in s_.split(",")) if s_ else tuple(d * MM for d in default)

    E = float(argval("--exp", "1.0"))
    if shot == "hero":
        tgt = v3("--tgt", (2, 4, 4))
        cam = v3("--cam", (150, -215, 105))
        camera(cam, tgt, float(argval("--lens", "70")), fstop=float(argval("--fstop", "16")), focus=v3("--focus", (0, 7, 2)))
        area("key", (-0.12, 0.34, 0.40), tgt, 0.50, 4.0 * E, (1.0, 0.97, 0.93), size_y=0.20)
        area("rim", (0.42, 0.26, 0.09), tgt, 0.34, 4.2 * E, (0.70, 0.83, 1.0), size_y=0.05)
        area("kick", (-0.40, -0.10, 0.05), tgt, 0.24, 1.1 * E, (1.0, 0.76, 0.52), size_y=0.06)
        area("top", (0.0, -0.05, 0.60), tgt, 0.9, 0.9 * E, (0.9, 0.95, 1.0))
        area("cu", (0.03, -0.10, 0.11), (0, 7 * MM, 2 * MM), 0.10, 1.1 * E, (1.0, 0.62, 0.32), size_y=0.03)
    elif shot == "top":
        tgt = (0, 0, 0)
        camera((0, -1 * MM, 420 * MM), tgt, 85)
        area("key", (-0.15, 0.25, 0.5), tgt, 0.6, 6 * E, (1.0, 0.97, 0.93))
        area("fill", (0.3, -0.2, 0.4), tgt, 0.5, 1.5 * E, (0.8, 0.88, 1.0))
    elif shot == "macro":
        tgt = v3("--tgt", (-8, 7.5, 1.6))
        cam = v3("--cam", (-52, -38, 21))
        camera(cam, tgt, float(argval("--lens", "100")), fstop=float(argval("--fstop", "11")), focus=tgt)
        area("key", (-0.05, 0.30, 0.30), tgt, 0.40, 3.4 * E, (1.0, 0.96, 0.92), size_y=0.15)
        area("rim", (0.35, 0.10, 0.06), tgt, 0.25, 2.6 * E, (0.70, 0.83, 1.0), size_y=0.04)
        area("kick", (-0.30, -0.10, 0.04), tgt, 0.2, 0.6 * E, (1.0, 0.75, 0.5), size_y=0.05)
        area("top", (0.0, 0.0, 0.5), tgt, 0.8, 0.5 * E, (0.9, 0.95, 1.0))

    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("WROTE", out)


if __name__ == "__main__":
    main()
