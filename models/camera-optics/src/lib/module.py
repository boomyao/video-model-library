"""The camera module around the hero lens (group B; other groups import it read-only).

The real patent lens (lens.py: Largan US10302915B2, embodiment 1, elements L1..L8, scaled, never reshaped) inside an
ILLUSTRATIVE voice-coil-motor camera module: black barrel with spacers and a rear retainer, carrier, copper coil,
four magnets, top and bottom stainless leaf springs, shield can, black base holding a square IR-cut filter, the image
sensor (iridescent pixel area, gold bond wires) on a green-grey board with a flex tail. Only the elements are data;
every other part has believable proportions but is not a real part (2D tags it 示意). The IR-cut filter keeps the
patent's thickness, glass and position (0.3 mm, nd 1.517, 6.675..6.975 mm behind the L1 vertex) but is a square
plate in the base, not lens.py's round disc.

    import module as MO
    m = MO.Module(scale=0.01, mag=1.0, cut=True, name="vcm")      # table-top cutaway of the patent module
    m.root.location = (0, 0, 0.1)                                   # metres, in the parent's space
    m.focus(0.30)          # stack 0.30 mm (real) toward the object, as when focusing at 10 cm
    m.current(1.0, phase)  # coil glows blue (current), phase in turns moves the pattern round the coil
    m.shift(0.05, 0.0)     # lens-shift stabilisation, real mm

INTERFACE (stable from 2026-10-30; group B only adds, never changes):

  Module(scale=0.001, mag=1.0, cut=False, name="cam", parts=None, parent=None, seg=128, stroke=0.45, clear=0.0)
      scale   Blender units per real millimetre (0.001 = real size, 0.01 = magnified table-top)
      mag     optical magnification of the patent design: 1.0 = the patent lens (f 5.38 mm, 7.2 mm from the L1
              vertex to the image, ~1/1.8-inch sensor); 1.4 = the same design scaled for a 1/1.28-inch sensor
              (10.08 mm). The whole module is sized in proportion: every dimension in this file is for mag 1.
      cut     True keeps the half y >= 0 (module-local) and closes every cut with a section face on y = 0, facing a
              camera at -y: the same convention as lens.py. Section faces of black parts are black, the coil shows
              its wire ends, the sensor and board their layers.
      parts   None (everything) or an iterable of names from PARTS: build only those
      parent  an object (e.g. a phone's root empty): the root is parented to it, with the module's frame in the
              parent's space (set m.root.location in the parent's units)
      stroke  free travel above the carrier at rest, mm at mag 1 (the can's top plate sits that far above the top
              spring). 0.45 = believable; a shot that shows the travel magnified passes more (e.g. 1.05)
      clear   extra sideways clearance round the moving group, mm at mag 1 (magnets, can, its top hole, the corner
              posts and the base move out by it), for a shot that shows the stabilisation shift magnified
  m.root      empty. Module frame = lens.py's frame: origin on the optical axis at the L1 front vertex (focus at
              infinity), optical axis along local -Z (light travels toward -z), x/y across; the meridional plane
              of the trace is x-z. Units inside are Blender units = real mm * scale (the same numbers lens.py makes).
  m.ois       child of root: shifts the whole moving group in x/y (lens-shift stabilisation); see shift()
  m.mover     child of ois: the focusing group: barrel, L1..L8, spacers, retainer, carrier, coil; see focus()
  m.obj       dict name -> object: "L1".."L8", "barrel", "retainer", "spacer_12", "spacer_23", ... (between L1/L2
              etc.; only the gaps that hold one), "carrier", "coil", "magnet_px", "magnet_nx", "magnet_py",
              "magnet_ny" (the one at -y is not built when cut), "spring_top", "spring_bottom", "housing", "frame" (the
              four corner posts that clamp the springs' outer pads), "base",
              "ir_filter", "sensor", "pixels" (the pixel area, a face on the die), "pads", "wires", "board",
              "parts_smd", "flex"
  m.groups    dict name -> list of objects: "lens" (L1..L8), "spacers" (spacers + retainer), "moving", "fixed",
              "vcm" (carrier, coil, magnets, springs, housing), "sensor" (sensor, pads, wires, board, smd, flex)
  m.Z         dict of heights along the axis, real mm (not scaled, not magnified twice: already * mag),
              0 = L1 vertex at rest, negative toward the sensor: "lip_top", "vertex", "housing_top", "spring_top",
              "carrier_top", "coil_top", "coil_bottom", "carrier_bottom", "magnet_top", "magnet_bottom",
              "base_top", "ir_top", "ir_bottom", "image" (sensor surface = image plane), "board_top",
              "board_bottom", "barrel_bottom"
  m.R         dict of radii / half sizes, real mm: "aperture" (front lip hole), "nose" (barrel front part),
              "barrel_rear", "carrier", "coil_outer", "housing" (half side of the square can), "board_x0" (board
              extends from -board_x0 to +housing), "board_y" (half), "sensor_x", "sensor_y" (half sizes of the die),
              "active_x", "active_y" (half sizes of the pixel area), "ir_x", "ir_y"
  m.focus(dz)           move the focusing group toward the object by dz real mm (positive = away from the sensor,
                        as when focusing closer); the leaf springs bend with it. Returns dz.
  m.shift(dx, dy)       move the focusing group sideways (real mm, module x/y), springs follow
  m.current(k, phase=0) coil glow 0..1 in the film's current colour (shotkit.BLUE); phase in turns moves the bright
                        bands round the winding (the direction the current flows)
  m.point(name)         world Vector (metres) of a named point, for ctx.anchor(..., lambda: m.point("carrier_top")):
                        any key of m.Z on the axis (moving ones follow the mover: "vertex", "lip_top",
                        "carrier_top", "coil_top", "coil_bottom", "carrier_bottom", "barrel_bottom"), plus
                        "housing_edge_top" (top of the can at its +x edge) and "carrier_edge_top" (carrier top
                        flange at its +x edge)
  m.local(x, y, z)      world Vector of a point given in module mm (real, x/y across, z along the axis as in m.Z)
  m.set_visible(names_or_objects, on)   show/hide parts (render visibility)

  focus_travel(f_mm, s_mm) -> f*f/(s-f): thin-lens travel from infinity to an object at s (both mm)
  F_MM = 5.38 (patent focal length; times mag for a scaled module), IMG = 7.2 (vertex to image, times mag)
"""
import math

import bpy
import bmesh
from mathutils import Vector

import lens as LN

F_MM = 5.38
IMG = 7.2
PARTS = ("lens", "barrel", "spacers", "carrier", "coil", "magnets", "springs", "housing", "base", "ir_filter",
         "sensor", "board", "flex")

# ------------------------------------------------------------------ dimensions (mm at mag 1, z toward the image)
# barrel bore: steps between elements, never narrower toward the rear (elements go in from the rear)
BORE = [(0.113, 2.134), (2.838, 2.359), (3.435, 3.511), (4.733, 4.143)]     # (z where it starts, radius)
BARREL_REAR = 5.60
LIP_TOP = -0.10
NOSE_R = 2.60
MID_R = 3.80
REAR_R = 4.45
APERTURE_R = 1.93
CARRIER = dict(z_top=3.06, z_bot=5.72, r_in_top=3.86, r_tube_in=4.45, r_tube_out=4.78, r_flange=5.15,
               flange=0.24)
COIL = dict(r0=4.80, r1=5.12, z0=3.33, z1=5.45)
MAGNET = dict(r_in=5.24, x_out=5.66, half_deg=22.0, z0=3.25, z1=5.55)
HOUSING = dict(half=5.85, wall=0.15, plate=0.15, z_bot=5.76, hole=2.80, corner=0.55)   # top: from the stroke
SPRING = dict(t=0.04, z_top=3.02, z_bot=5.72, ring=(4.48, 5.06), w=0.10)
BASE = dict(z_top=5.76, z_bot=7.45)
IR = dict(z0=6.675, z1=6.975, hx=4.30, hy=3.50, nd=1.517)
SENSOR = dict(z0=7.20, z1=7.45, hx=4.10, hy=3.30, ax=3.56, ay=2.67)      # die; active area 7.12 x 5.34 (4:3)
BOARD = dict(z0=7.45, z1=7.85, x0=-8.0, x1=6.25, hy=6.10)
WIRE_MM = 0.025


def focus_travel(f_mm, s_mm):
    return f_mm * f_mm / (s_mm - f_mm)


# ------------------------------------------------------------------ materials (shared by name)
def _mat(name, **kw):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    for k, v in kw.items():
        b.inputs[k].default_value = v
    return m


def _noise_bump(m, scale, strength, distance):
    """Fine grain: object-space noise into the Principled normal."""
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 3.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def black_plastic(S, name="mo_black"):
    """Matte black LCP / PC: barrel, carrier, base, spacers."""
    key = "%s_%g" % (name, S)
    m = bpy.data.materials.get(key)
    if m:
        return m
    m = _mat(key, **{"Base Color": (0.016, 0.016, 0.018, 1), "Roughness": 0.42, "Specular IOR Level": 0.45})
    return _noise_bump(m, 1.0 / (0.04 * S), 0.25, 0.004 * S)


def black_section(S):
    key = "mo_black_cut_%g" % S
    m = bpy.data.materials.get(key)
    if m:
        return m
    m = _mat(key, **{"Base Color": (0.045, 0.045, 0.05, 1), "Roughness": 0.34, "Specular IOR Level": 0.5})
    return _noise_bump(m, 1.0 / (0.02 * S), 0.15, 0.002 * S)


def metal(name, color, rough, S, grain=0.0, aniso=0.0):
    key = "%s_%g" % (name, S)
    m = bpy.data.materials.get(key)
    if m:
        return m
    m = _mat(key, **{"Base Color": (*color, 1), "Metallic": 1.0, "Roughness": rough, "Anisotropic": aniso})
    if grain:
        _noise_bump(m, 1.0 / (0.03 * S), grain, 0.003 * S)
    return m


def copper(S, section=False):
    """Enamelled copper winding. Outer surface: one groove per turn (wire 0.04 mm at mag 1); section: wire ends.
    An emission in the current colour is driven by the node named CURRENT (value) and PHASE (value)."""
    key = "mo_copper%s_%g" % ("_cut" if section else "", S)
    m = bpy.data.materials.get(key)
    if m:
        return m
    m = _mat(key, **{"Base Color": (0.93, 0.56, 0.38, 1), "Metallic": 1.0, "Roughness": 0.3,
                     "Coat Weight": 0.6, "Coat Roughness": 0.12, "Coat Tint": (1.0, 0.82, 0.62, 1)})
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    pitch = 0.042 * S

    def math_node(op, a=None, bval=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        if a is not None:
            if isinstance(a, (int, float)):
                n.inputs[0].default_value = a
            else:
                nt.links.new(a, n.inputs[0])
        if bval is not None:
            if isinstance(bval, (int, float)):
                n.inputs[1].default_value = bval
            else:
                nt.links.new(bval, n.inputs[1])
        return n
    if not section:
        # grooves along z: |sin(pi z / pitch)| -> bump
        k = math_node("MULTIPLY", sep.outputs["Z"], math.pi / pitch)
        s = math_node("SINE", k.outputs[0])
        a = math_node("ABSOLUTE", s.outputs[0])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.6
        bump.inputs["Distance"].default_value = 0.012 * S
        nt.links.new(a.outputs[0], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    else:
        # wire ends on the cut (plane y = 0): a grid of round copper dots in dark varnish, x/z in pitch cells
        fx = math_node("FRACT", math_node("DIVIDE", sep.outputs["X"], pitch).outputs[0])
        fz = math_node("FRACT", math_node("DIVIDE", sep.outputs["Z"], pitch).outputs[0])
        dx = math_node("SUBTRACT", fx.outputs[0], 0.5)
        dz = math_node("SUBTRACT", fz.outputs[0], 0.5)
        r2 = math_node("ADD", math_node("MULTIPLY", dx.outputs[0], dx.outputs[0]).outputs[0],
                       math_node("MULTIPLY", dz.outputs[0], dz.outputs[0]).outputs[0])
        dot = math_node("LESS_THAN", r2.outputs[0], 0.17)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs["A"].default_value = (0.05, 0.025, 0.012, 1)
        mix.inputs["B"].default_value = (0.95, 0.58, 0.40, 1)
        nt.links.new(dot.outputs[0], mix.inputs["Factor"])
        nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
        rough = math_node("SUBTRACT", 0.55, math_node("MULTIPLY", dot.outputs[0], 0.35).outputs[0])
        nt.links.new(rough.outputs[0], b.inputs["Roughness"])
        met = math_node("MULTIPLY", dot.outputs[0], 1.0)
        nt.links.new(met.outputs[0], b.inputs["Metallic"])
        b.inputs["Coat Weight"].default_value = 0.0
    # current: emission = CURRENT * (0.45 + 0.55 * band), band = 0.5 + 0.5 sin(3 * angle - 2 pi PHASE)
    cur = nt.nodes.new("ShaderNodeValue")
    cur.name = "CURRENT"
    cur.outputs[0].default_value = 0.0
    ph = nt.nodes.new("ShaderNodeValue")
    ph.name = "PHASE"
    ph.outputs[0].default_value = 0.0
    ang = math_node("ARCTAN2", sep.outputs["Y"], sep.outputs["X"])
    a3 = math_node("MULTIPLY", ang.outputs[0], 3.0)
    p2 = math_node("MULTIPLY", ph.outputs[0], 2 * math.pi)
    sn = math_node("SINE", math_node("SUBTRACT", a3.outputs[0], p2.outputs[0]).outputs[0])
    band = math_node("MULTIPLY_ADD", sn.outputs[0], 0.275)
    band.inputs[2].default_value = 0.725
    e = math_node("MULTIPLY", band.outputs[0], cur.outputs[0])
    e2 = math_node("MULTIPLY", e.outputs[0], 1.3)
    b.inputs["Emission Color"].default_value = (0.159, 0.651, 1.0, 1)
    nt.links.new(e2.outputs[0], b.inputs["Emission Strength"])
    return m


def ir_glass(S):
    key = "mo_irglass_%g" % S
    m = bpy.data.materials.get(key)
    if m:
        return m
    return _mat(key, **{"Base Color": (0.93, 0.97, 0.98, 1), "Roughness": 0.0, "Transmission Weight": 1.0,
                        "IOR": IR["nd"], "Thin Film Thickness": 430.0, "Thin Film IOR": 2.1})


def sensor_active(S):
    """The pixel area: dark silicon under a microlens grid; iridescent sheen from a thin film whose thickness drifts
    across the die (no visible grid at film resolution: the real one is 1 um)."""
    key = "mo_pixels_%g" % S
    m = bpy.data.materials.get(key)
    if m:
        return m
    m = _mat(key, **{"Base Color": (0.012, 0.014, 0.024, 1), "Metallic": 0.35, "Roughness": 0.14,
                     "Specular IOR Level": 0.7, "Thin Film IOR": 1.55})
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.0 / (3.0 * S)
    nz.inputs["Detail"].default_value = 1.0
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 380.0
    mr.inputs["To Max"].default_value = 720.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], b.inputs["Thin Film Thickness"])
    return m


def pcb(S):
    key = "mo_pcb_%g" % S
    m = bpy.data.materials.get(key)
    if m:
        return m
    m = _mat(key, **{"Base Color": (0.030, 0.055, 0.042, 1), "Roughness": 0.38, "Coat Weight": 0.5,
                     "Coat Roughness": 0.18})
    return _noise_bump(m, 1.0 / (0.06 * S), 0.12, 0.003 * S)


def pcb_section(S):
    """Board cut: FR4 with copper layers (stripes along z)."""
    key = "mo_pcb_cut_%g" % S
    m = bpy.data.materials.get(key)
    if m:
        return m
    m = _mat(key, **{"Base Color": (0.25, 0.22, 0.13, 1), "Roughness": 0.5})
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 1.0 / (0.065 * S)
    fr = nt.nodes.new("ShaderNodeMath")
    fr.operation = "FRACT"
    lt = nt.nodes.new("ShaderNodeMath")
    lt.operation = "LESS_THAN"
    lt.inputs[1].default_value = 0.22
    nt.links.new(sep.outputs["Z"], mul.inputs[0])
    nt.links.new(mul.outputs[0], fr.inputs[0])
    nt.links.new(fr.outputs[0], lt.inputs[0])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (0.20, 0.18, 0.10, 1)
    mix.inputs["B"].default_value = (0.95, 0.55, 0.35, 1)
    nt.links.new(lt.outputs[0], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    nt.links.new(lt.outputs[0], b.inputs["Metallic"])
    return m


def flex_mat(S):
    key = "mo_flex_%g" % S
    m = bpy.data.materials.get(key)
    if m:
        return m
    return _mat(key, **{"Base Color": (0.55, 0.26, 0.05, 1), "Roughness": 0.25, "Coat Weight": 0.6,
                        "Coat Roughness": 0.1, "Subsurface Weight": 0.0})


def ghost_shader(nt, edge=0.014, gloss=0.015):
    """X-ray ghost for a material's node tree: transparent, faint neutral-white edges (silhouettes) and a trace of
    reflection; returns the shader socket. No colour: in this film blue means current, amber light."""
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.88, 0.91, 0.95, 1)
    em.inputs["Strength"].default_value = edge
    gl = nt.nodes.new("ShaderNodeBsdfGlossy")
    gl.inputs["Roughness"].default_value = 0.1
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs["Facing"], inv.inputs[1])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    pw.inputs[1].default_value = 6.0
    nt.links.new(inv.outputs[0], pw.inputs[0])            # (1 - facing)^6: 1 at grazing edges
    mix_e = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(pw.outputs[0], mix_e.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix_e.inputs[1])
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tr.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], mix_e.inputs[2])
    g = nt.nodes.new("ShaderNodeMixShader")
    g.inputs["Fac"].default_value = gloss
    nt.links.new(mix_e.outputs[0], g.inputs[1])
    nt.links.new(gl.outputs[0], g.inputs[2])
    return g.outputs[0]


# ------------------------------------------------------------------ geometry helpers (all in module mm)
def _fillet(poly, rf, n=3):
    """Round every corner of a closed polygon [(u, v)] with radius rf (clamped to a third of the shorter edge)."""
    out = []
    m = len(poly)
    for i in range(m):
        p0, p1, p2 = Vector(poly[i - 1]), Vector(poly[i]), Vector(poly[(i + 1) % m])
        a, b = (p0 - p1), (p2 - p1)
        la, lb = a.length, b.length
        if la < 1e-9 or lb < 1e-9:
            continue
        a.normalize()
        b.normalize()
        cosang = max(-1.0, min(1.0, a.dot(b)))
        ang = math.acos(cosang)
        if ang > math.radians(175) or rf <= 0:
            out.append(tuple(p1))
            continue
        t = rf / math.tan(ang / 2)
        t = min(t, la / 3, lb / 3)
        r = t * math.tan(ang / 2)
        q0, q2 = p1 + a * t, p1 + b * t
        bis = (a + b).normalized()
        c = p1 + bis * (r / math.sin(ang / 2))
        v0, v2 = q0 - c, q2 - c
        a0 = math.atan2(v0.y, v0.x)
        a2 = math.atan2(v2.y, v2.x)
        da = a2 - a0
        while da > math.pi:
            da -= 2 * math.pi
        while da < -math.pi:
            da += 2 * math.pi
        for k in range(n + 1):
            aa = a0 + da * k / n
            out.append((c.x + r * math.cos(aa), c.y + r * math.sin(aa)))
    return out


def _finish(me, smooth_angle=35.0):
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-9)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.validate()
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(smooth_angle))


def _new_object(name, me, mats, parent=None):
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for mt in mats:
        ob.data.materials.append(mt)
    if parent is not None:
        ob.parent = parent
    return ob


def revolve(name, prof, S, cut=False, seg=128, mat=None, cap=None, parent=None, smooth_angle=35.0):
    """Solid of revolution about the local z axis from a closed profile [(r, z)] in module mm with z toward the
    image (world z = -z). cut=True: half (y >= 0) with section faces (material slot 1)."""
    a0, a1 = 0.0, (math.pi if cut else 2 * math.pi)
    nseg = max(8, seg // 2) if cut else seg
    rings = nseg + 1 if cut else nseg
    npf = len(prof)
    verts, faces = [], []
    for k in range(rings):
        a = a0 + (a1 - a0) * k / nseg
        ca, sa = math.cos(a), math.sin(a)
        for (r, z) in prof:
            verts.append((r * ca * S, r * sa * S, -z * S))
    for k in range(nseg):
        k2 = (k + 1) % rings
        for i in range(npf):
            i2 = (i + 1) % npf
            faces.append((k * npf + i, k * npf + i2, k2 * npf + i2, k2 * npf + i))
    capfaces = []
    if cut:
        for k in (0, nseg):
            capfaces.append(len(faces))
            faces.append(tuple(k * npf + i for i in range(npf)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    if cut:
        for fi in capfaces:
            me.polygons[fi].material_index = 1
    _finish(me, smooth_angle)
    return _new_object(name, me, [mat, cap or mat] if cut else [mat], parent)


def prism(name, plan, z0, z1, S, mat=None, parent=None, smooth_angle=35.0):
    """Extrude a closed plan polygon [(x, y)] (module mm) between axial heights z0 and z1 (toward the image)."""
    n = len(plan)
    verts = [(x * S, y * S, -z0 * S) for x, y in plan] + [(x * S, y * S, -z1 * S) for x, y in plan]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    _finish(me, smooth_angle)
    return _new_object(name, me, [mat] if mat else [], parent)


def rrect(hx, hy, r, n=6, cx=0.0, cy=0.0):
    """Rounded rectangle polygon (counter-clockwise), half sizes hx, hy, corner radius r."""
    r = min(r, hx - 1e-6, hy - 1e-6)
    pts = []
    for (sx, sy, a0) in ((1, 1, 0.0), (-1, 1, 90.0), (-1, -1, 180.0), (1, -1, 270.0)):
        ccx, ccy = cx + sx * (hx - r), cy + sy * (hy - r)
        for k in range(n + 1):
            a = math.radians(a0 + 90.0 * k / n)
            pts.append((ccx + r * math.cos(a), ccy + r * math.sin(a)))
    return pts


def circle(r, n=64, cx=0.0, cy=0.0):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def boolean(ob, cutter, op="DIFFERENCE", transfer=False):
    """Apply a boolean (exact) to ob in place; the cutter is left alone."""
    mod = ob.modifiers.new("b", "BOOLEAN")
    mod.object = cutter
    mod.operation = op
    mod.solver = "EXACT"
    if transfer:
        mod.material_mode = "TRANSFER"
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.remove(mod)
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    _clean_slots(me)
    return ob


def _clean_slots(me):
    """Faces that landed on an empty material slot (from a cutter without materials) take slot 0; empty slots go."""
    slots = list(me.materials)
    if not any(m is None for m in slots):
        return
    keep = [i for i, m in enumerate(slots) if m is not None]
    remap = {old: new for new, old in enumerate(keep)}
    idx = [remap.get(p.material_index, 0) for p in me.polygons]
    while len(me.materials):
        me.materials.pop()
    for i in keep:
        me.materials.append(slots[i])
    for p, i in zip(me.polygons, idx):
        p.material_index = i


def box_cutter(xmin, xmax, ymin, ymax, zmin, zmax, mat=None, name="cutter"):
    """An axis-aligned box in Blender units (already scaled), for booleans; delete it after use."""
    verts = [(x, y, z) for x in (xmin, xmax) for y in (ymin, ymax) for z in (zmin, zmax)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    _finish(me, 10.0)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    return ob


def cut_half(ob, cap_mat, y0=0.0, big=1.0):
    """Keep the half y >= y0 (in the object's space, which must coincide with the world while building) and give
    the new section faces cap_mat. y0 / big in Blender units."""
    c = box_cutter(-big, big, y0 - big, y0, -big, big, mat=cap_mat)
    boolean(ob, c, transfer=True)
    me = c.data
    bpy.data.objects.remove(c)
    bpy.data.meshes.remove(me)
    _finish(ob.data, 35.0)
    return ob


def bevel(ob, width, segments=2, angle=40.0, material=-1):
    """Apply a bevel modifier (width in Blender units) in place."""
    mod = ob.modifiers.new("bv", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle)
    mod.harden_normals = False
    mod.material = material
    mod.use_clamp_overlap = True
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.remove(mod)
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(35.0))
    return ob


# ------------------------------------------------------------------ the module
class Module:
    def __init__(self, scale=0.001, mag=1.0, cut=False, name="cam", parts=None, parent=None, seg=128, stroke=0.45,
                 clear=0.0):
        self.scale, self.mag, self.cut, self.name, self.stroke, self.clear = scale, mag, cut, name, stroke, clear
        S = self.S = scale * mag                   # Blender units per module mm (mag-1 drawing mm)
        want = set(PARTS if parts is None else parts)
        self.obj, self.groups = {}, {k: [] for k in ("lens", "spacers", "moving", "fixed", "vcm", "sensor")}
        self._springs = []
        self._coil_mats = []
        self._dz = 0.0
        self._dxy = (0.0, 0.0)
        sc = bpy.context.scene.collection

        def empty(nm, par):
            e = bpy.data.objects.new(nm, None)
            sc.objects.link(e)
            e.empty_display_size = 2.0 * S
            if par is not None:
                e.parent = par
            return e
        self.root = empty(name + "_root", None)
        self.ois = empty(name + "_ois", self.root)
        self.mover = empty(name + "_mover", self.ois)

        d = LN.load()
        self.data = d
        els = d["elements"][:8]
        blk, blk_cut = black_plastic(S), black_section(S)

        def keep(nm, ob, moving, groups=()):
            self.obj[nm] = ob
            ob.parent = self.mover if moving else self.root
            self.groups["moving" if moving else "fixed"].append(ob)
            for g in groups:
                self.groups[g].append(ob)
            return ob

        def maybe_cut(ob, cap):
            if cut:
                cut_half(ob, cap, 0.0, 40.0 * S)
            return ob

        # ---- the elements: lens.py, scaled by mag, never reshaped
        if "lens" in want:
            for i, el in enumerate(els):
                ob = LN.build_element(el, "%s_L%d" % (name, i + 1), scale=S, origin=(0, 0, 0), cut=cut, seg=160)
                keep("L%d" % (i + 1), ob, True, ("lens",))

        # ---- barrel
        if "barrel" in want:
            prof = [(2.02, LIP_TOP), (APERTURE_R, 0.113)]
            for j, (z, r) in enumerate(BORE):
                z_next = BORE[j + 1][0] if j + 1 < len(BORE) else BARREL_REAR
                prof += [(r, z), (r, z_next)]
            prof += [(REAR_R, BARREL_REAR), (REAR_R, 4.60), (MID_R, 4.50), (MID_R, 3.40), (NOSE_R, 3.10),
                     (NOSE_R, -0.02), (NOSE_R - 0.08, LIP_TOP)]
            # profile order: inner side front -> rear, then outer side rear -> front
            prof = _dedupe(prof)
            ob = revolve(name + "_barrel", _fillet(prof, 0.025, 2), S, cut, seg, blk, blk_cut)
            keep("barrel", ob, True)

        # ---- spacers between elements and the rear retainer
        if "spacers" in want:
            geo = [_element_geo(el) for el in els]
            for i in range(len(els) - 1):
                g0, g1 = geo[i], geo[i + 1]
                z0, z1 = g0["zb"], g1["zf"]
                if z1 - z0 < 0.005:
                    continue
                r_in = max(g0["apb"], g1["apf"]) + 0.02
                zs = [z for z, _ in BORE]
                # the spacer sits where the bore is wide enough for its inner edge
                za = z0
                while _bore(za + 1e-6) <= r_in + 0.03 and za < z1:
                    nxt = [z for z in zs if z > za + 1e-6]
                    if not nxt or nxt[0] >= z1:
                        za = z1
                        break
                    za = nxt[0]
                if z1 - za < 0.005:
                    continue
                rb = _bore(za + 1e-6) - 0.004
                poly = [(r_in, za), (rb, za)]
                # follow a bore step inside the gap
                for z, r in BORE:
                    if za + 1e-6 < z < z1 - 1e-6:
                        poly += [(rb, z), (r - 0.004, z)]
                        rb = r - 0.004
                if g1["rout"] < rb - 0.03:       # a sleeve round the rim of the next element
                    poly += [(rb, g1["zb"]), (g1["rout"] + 0.004, g1["zb"]), (g1["rout"] + 0.004, z1)]
                else:
                    poly += [(rb, z1)]
                poly += [(r_in, z1)]
                ob = revolve("%s_spacer_%d%d" % (name, i + 1, i + 2), _dedupe(poly), S, cut, seg, blk, blk_cut)
                keep("spacer_%d%d" % (i + 1, i + 2), ob, True, ("spacers",))
            g8 = geo[-1]
            poly = [(g8["apb"] + 0.02, g8["zb"]), (_bore(g8["zb"]) - 0.004, g8["zb"]),
                    (_bore(g8["zb"]) - 0.004, BARREL_REAR - 0.05), (g8["apb"] + 0.02, BARREL_REAR - 0.05)]
            ob = revolve(name + "_retainer", poly, S, cut, seg, blk, blk_cut)
            keep("retainer", ob, True, ("spacers",))

        # ---- carrier with the coil wound on it
        c = CARRIER
        if "carrier" in want:
            prof = [(c["r_in_top"], c["z_top"]), (c["r_flange"], c["z_top"]), (c["r_flange"], c["z_top"] + c["flange"]),
                    (c["r_tube_out"], c["z_top"] + c["flange"]), (c["r_tube_out"], c["z_bot"] - c["flange"]),
                    (c["r_flange"], c["z_bot"] - c["flange"]), (c["r_flange"], c["z_bot"]), (c["r_tube_in"], c["z_bot"]),
                    (c["r_tube_in"], c["z_top"] + c["flange"] + 0.1), (c["r_in_top"], c["z_top"] + c["flange"] + 0.1)]
            ob = revolve(name + "_carrier", _fillet(prof, 0.03, 2), S, cut, seg, blk, blk_cut)
            keep("carrier", ob, True, ("vcm",))
        if "coil" in want:
            k = COIL
            prof = [(k["r0"], k["z0"]), (k["r1"], k["z0"]), (k["r1"], k["z1"]), (k["r0"], k["z1"])]
            cm, cmc = copper(S), copper(S, section=True)
            ob = revolve(name + "_coil", _fillet(prof, 0.06, 3), S, cut, max(seg, 160), cm, cmc)
            keep("coil", ob, True, ("vcm",))
            self._coil_mats = [cm, cmc]

        # ---- four magnets, fixed in the can
        if "magnets" in want:
            g = dict(MAGNET, r_in=MAGNET["r_in"] + clear, x_out=MAGNET["x_out"] + clear)
            mg = metal("mo_nickel", (0.74, 0.72, 0.68), 0.24, S, grain=0.2)
            arc = [(g["r_in"] * math.cos(math.radians(a)), g["r_in"] * math.sin(math.radians(a)))
                   for a in [-g["half_deg"] + 2 * g["half_deg"] * i / 16 for i in range(17)]]
            ys = g["r_in"] * math.sin(math.radians(g["half_deg"]))
            plan0 = arc + [(g["x_out"], ys), (g["x_out"], -ys)]
            plan0 = _fillet(plan0, 0.05, 2)
            for tag, ang in (("px", 0.0), ("py", 90.0), ("nx", 180.0), ("ny", 270.0)):
                if cut and tag == "ny":
                    continue
                ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                plan = [(x * ca - y * sa, x * sa + y * ca) for x, y in plan0]
                ob = prism("%s_magnet_%s" % (name, tag), plan, g["z0"], g["z1"], S, mg)
                bevel(ob, 0.03 * S, 2)
                if cut and tag in ("px", "nx"):          # NdFeB under its nickel plating
                    cut_half(ob, metal("mo_ndfeb", (0.24, 0.24, 0.26), 0.42, S), 0.0, 40.0 * S)
                keep("magnet_" + tag, ob, False, ("vcm",))

        # ---- leaf springs (top and bottom), bend with the carrier
        if "springs" in want:
            st = metal("mo_spring", (0.62, 0.62, 0.64), 0.16, S, aniso=0.4)
            for tag, zc, flip in (("top", SPRING["z_top"], 1.0), ("bottom", SPRING["z_bot"], -1.0)):
                ob, base, wts = _spring(name + "_spring_" + tag, zc, SPRING["t"], S, cut, st, flip)
                keep("spring_" + tag, ob, False, ("vcm",))
                self._springs.append((ob, base, wts))

        # ---- the shield can
        h = dict(HOUSING, half=HOUSING["half"] + clear, hole=HOUSING["hole"] + clear)
        self._half = h["half"]
        z_under = SPRING["z_top"] - stroke                 # underside of the can's top plate
        self._z_can = z_can = z_under - h["plate"]
        if "housing" in want:
            can = metal("mo_can", (0.70, 0.70, 0.72), 0.3, S, grain=0.25)
            outer = prism(name + "_housing", rrect(h["half"], h["half"], h["corner"], 6), z_can, h["z_bot"], S, can)
            inner = prism("tmp", rrect(h["half"] - h["wall"], h["half"] - h["wall"], max(0.05, h["corner"] - h["wall"]), 6),
                          z_under, h["z_bot"] + 0.5, S)
            hole = prism("tmp2", circle(h["hole"], 96), z_can - 0.5, z_under + 0.05, S)
            boolean(outer, inner)
            boolean(outer, hole)
            for t in (inner, hole):
                me = t.data
                bpy.data.objects.remove(t)
                bpy.data.meshes.remove(me)
            bevel(outer, 0.03 * S, 2)
            maybe_cut(outer, metal("mo_can_cut", (0.80, 0.80, 0.82), 0.18, S))
            keep("housing", outer, False, ("vcm",))
            # corner posts (black): from the plate down to the top spring's pads, and from under them to the base
            posts = []
            for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
                if cut and sy < 0:
                    continue
                pl = rrect(0.70, 0.70, 0.12, 3, cx=sx * (4.95 + clear), cy=sy * (4.95 + clear))
                for z0, z1 in ((z_under, SPRING["z_top"]), (SPRING["z_top"] + SPRING["t"], SPRING["z_bot"])):
                    ob = prism("tmp_post", pl, z0, z1, S)
                    posts.append(ob)
            fr = _join(name + "_frame", posts, blk)
            bevel(fr, 0.025 * S, 2)
            keep("frame", fr, False, ("vcm",))

        # ---- the base with its IR-cut filter
        if "base" in want:
            b = BASE
            ob = prism(name + "_base", rrect(h["half"], h["half"], HOUSING["corner"], 6), b["z_top"], b["z_bot"], S, blk)
            win1 = prism("tmp", rrect(IR["hx"] + 0.05, IR["hy"] + 0.05, 0.1, 3), b["z_top"] - 0.5, IR["z1"], S)
            win2 = prism("tmp2", rrect(SENSOR["ax"] + 0.35, SENSOR["ay"] + 0.45, 0.1, 3), IR["z1"] - 0.01, b["z_bot"] + 0.5, S)
            win3 = prism("tmp3", rrect(SENSOR["hx"] + 0.45, SENSOR["hy"] + 0.45, 0.1, 3), IR["z1"] + 0.10, b["z_bot"] + 0.5, S)
            for t in (win1, win2, win3):
                boolean(ob, t)
                me = t.data
                bpy.data.objects.remove(t)
                bpy.data.meshes.remove(me)
            bevel(ob, 0.03 * S, 2)
            maybe_cut(ob, blk_cut)
            keep("base", ob, False)
        if "ir_filter" in want:
            ob = prism(name + "_ir_filter", rrect(IR["hx"], IR["hy"], 0.08, 3), IR["z0"], IR["z1"], S, ir_glass(S))
            bevel(ob, 0.015 * S, 2)
            maybe_cut(ob, ir_glass(S))
            keep("ir_filter", ob, False)

        # ---- sensor on its board
        if "sensor" in want:
            s = SENSOR
            ob = prism(name + "_sensor", [(s["hx"], s["hy"]), (-s["hx"], s["hy"]), (-s["hx"], -s["hy"]), (s["hx"], -s["hy"])],
                       s["z0"], s["z1"], S, metal("mo_die", (0.30, 0.31, 0.34), 0.35, S))
            bevel(ob, 0.01 * S, 1, angle=60.0)
            maybe_cut(ob, metal("mo_die_cut", (0.22, 0.22, 0.25), 0.3, S))
            keep("sensor", ob, False, ("sensor",))
            # the pixel area: a face just on the die's top, exactly 7.12 x 5.34 mm (times mag)
            y0 = 0.0 if cut else -s["ay"]
            zz = -(s["z0"] - 0.0015) * S
            me = bpy.data.meshes.new(name + "_pixels")
            me.from_pydata([(s["ax"] * S, y0 * S, zz), (s["ax"] * S, s["ay"] * S, zz), (-s["ax"] * S, s["ay"] * S, zz),
                            (-s["ax"] * S, y0 * S, zz)], [], [(0, 1, 2, 3)])
            me.validate()
            px = _new_object(name + "_pixels", me, [sensor_active(S)])
            keep("pixels", px, False, ("sensor",))
            # gold bond pads and wires along the long edges
            gold = metal("mo_gold", (1.0, 0.74, 0.32), 0.22, S)
            pads, wires = _bond(name, s, BOARD, S, cut, gold)
            keep("pads", pads, False, ("sensor",))
            keep("wires", wires, False, ("sensor",))
        if "board" in want:
            bd = BOARD
            ob = prism(name + "_board", rrect((bd["x1"] - bd["x0"]) / 2, bd["hy"], 0.3, 4, cx=(bd["x1"] + bd["x0"]) / 2),
                       bd["z0"], bd["z1"], S, pcb(S))
            bevel(ob, 0.04 * S, 2)
            maybe_cut(ob, pcb_section(S))
            keep("board", ob, False, ("sensor",))
            smd = _smd(name, bd, S, cut)
            if smd:
                keep("parts_smd", smd, False, ("sensor",))
        if "flex" in want:
            bd = BOARD
            ob = prism(name + "_flex", rrect(3.5, 2.2, 0.4, 4, cx=bd["x0"] - 3.3, cy=0.0), bd["z1"] - 0.16, bd["z1"] - 0.04, S,
                       flex_mat(S))
            maybe_cut(ob, flex_mat(S))
            keep("flex", ob, False, ("sensor",))

        # ---- numbers for the shots (real mm, already * mag), axis 0 = L1 vertex at rest, negative toward the sensor
        M = mag
        self.Z = {
            "lip_top": -LIP_TOP * M, "vertex": 0.0,
            "housing_top": -z_can * M, "spring_top": -SPRING["z_top"] * M,
            "carrier_top": -CARRIER["z_top"] * M, "coil_top": -COIL["z0"] * M, "coil_bottom": -COIL["z1"] * M,
            "carrier_bottom": -CARRIER["z_bot"] * M, "magnet_top": -MAGNET["z0"] * M,
            "magnet_bottom": -MAGNET["z1"] * M, "base_top": -BASE["z_top"] * M, "ir_top": -IR["z0"] * M,
            "ir_bottom": -IR["z1"] * M, "image": -SENSOR["z0"] * M, "board_top": -BOARD["z0"] * M,
            "board_bottom": -BOARD["z1"] * M, "barrel_bottom": -BARREL_REAR * M,
        }
        self.R = {"aperture": APERTURE_R * M, "nose": NOSE_R * M, "barrel_rear": REAR_R * M,
                  "carrier": CARRIER["r_flange"] * M, "coil_outer": COIL["r1"] * M, "housing": h["half"] * M,
                  "board_x0": -BOARD["x0"] * M, "board_y": BOARD["hy"] * M, "sensor_x": SENSOR["hx"] * M,
                  "sensor_y": SENSOR["hy"] * M, "active_x": SENSOR["ax"] * M, "active_y": SENSOR["ay"] * M,
                  "ir_x": IR["hx"] * M, "ir_y": IR["hy"] * M}
        self.focal = F_MM * M
        if parent is not None:
            self.root.parent = parent

    # ---------------------------------------------------------------- motion
    def focus(self, dz):
        """Stack toward the object by dz real mm."""
        self._dz = dz
        self.mover.location = (0.0, 0.0, dz * self.scale)
        self._bend()
        return dz

    def shift(self, dx, dy):
        self._dxy = (dx, dy)
        self.ois.location = (dx * self.scale, dy * self.scale, 0.0)
        self._bend()

    def _bend(self):
        dz, (dx, dy) = self._dz * self.scale, self._dxy
        dx, dy = dx * self.scale, dy * self.scale
        for ob, base, wts in self._springs:
            me = ob.data
            co = [0.0] * (3 * len(base))
            for i, ((x, y, z), w) in enumerate(zip(base, wts)):
                co[3 * i], co[3 * i + 1], co[3 * i + 2] = x + w * dx, y + w * dy, z + w * dz
            me.vertices.foreach_set("co", co)
            me.update()

    def current(self, k, phase=0.0):
        for m in self._coil_mats:
            nt = m.node_tree
            nt.nodes["CURRENT"].outputs[0].default_value = max(0.0, k)
            nt.nodes["PHASE"].outputs[0].default_value = phase

    def set_visible(self, items, on):
        for it in items:
            ob = self.obj.get(it) if isinstance(it, str) else it
            if ob is not None:
                ob.hide_render = not on
                ob.hide_viewport = not on

    # ---------------------------------------------------------------- points for anchors
    MOVING = ("vertex", "lip_top", "carrier_top", "coil_top", "coil_bottom", "carrier_bottom", "barrel_bottom",
              "spring_top")

    def local(self, x, y, z, moving=False):
        bpy.context.view_layer.update()
        ob = self.mover if moving else self.root
        return ob.matrix_world @ Vector((x * self.scale, y * self.scale, z * self.scale))

    def point(self, name):
        if name == "housing_edge_top":
            return self.local(self.R["housing"], 0.0, self.Z["housing_top"])
        if name == "carrier_edge_top":
            return self.local(self.R["carrier"], 0.0, self.Z["carrier_top"], moving=True)
        return self.local(0.0, 0.0, self.Z[name], moving=name in self.MOVING)


# ------------------------------------------------------------------ part builders
def _dedupe(poly, eps=1e-6):
    out = []
    for p in poly:
        if not out or (abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps):
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < eps and abs(out[0][1] - out[-1][1]) < eps:
        out.pop()
    return out


def _bore(z):
    r = BORE[0][1]
    for zz, rr in BORE:
        if z >= zz:
            r = rr
    return r


def _join(name, obs, mat):
    """Merge several mesh objects (built in the same space) into one new object."""
    verts, faces = [], []
    for ob in obs:
        o = len(verts)
        verts += [tuple(v.co) for v in ob.data.vertices]
        faces += [tuple(o + i for i in p.vertices) for p in ob.data.polygons]
        me = ob.data
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    _finish(me, 35.0)
    return _new_object(name, me, [mat])


def _element_geo(el):
    """Rim geometry of one element as lens.py builds it (front / back flange heights, radii)."""
    pts, rout = LN.profile(el)
    f, b = el["front"], el["back"]
    zf = f["z"] + LN.sag(f, f["ap"])
    zb = max(b["z"] + LN.sag(b, b["ap"]), zf + 0.08)
    return dict(zf=zf, zb=zb, rout=rout, apf=f["ap"], apb=b["ap"])


def _strip(centre, w):
    """Quads of a strip of width w along a centre polyline [(x, y)]: returns (verts2d, quads, s_along)."""
    n = len(centre)
    verts, quads, s = [], [], [0.0]
    for i in range(1, n):
        s.append(s[-1] + math.dist(centre[i], centre[i - 1]))
    for i in range(n):
        p = Vector(centre[i])
        if i == 0:
            t = Vector(centre[1]) - p
        elif i == n - 1:
            t = p - Vector(centre[i - 1])
        else:
            t1 = (p - Vector(centre[i - 1])).normalized()
            t2 = (Vector(centre[i + 1]) - p).normalized()
            t = t1 + t2
            if t.length < 1e-6:
                t = t2
        t.normalize()
        nrm = Vector((-t.y, t.x))
        verts += [tuple(p + nrm * (w / 2)), tuple(p - nrm * (w / 2))]
    for i in range(n - 1):
        quads.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    return verts, quads, s


def _spring(name, zc, t, S, cut, mat, flip):
    """Flat stainless leaf spring: inner ring on the carrier, four serpentine arms, four pads clamped at the can's
    corners. Returns (object, base coordinates, weights: 1 = moves with the carrier, 0 = fixed)."""
    r0, r1 = SPRING["ring"]
    w = SPRING["w"]
    verts, faces, wts = [], [], []

    def add(v2, quads, wt):
        o = len(verts)
        for (x, y), ww in zip(v2, wt):
            verts.append((x, y))
            wts.append(ww)
        for q in quads:
            faces.append(tuple(o + i for i in q))
    # inner ring
    a0, a1 = (0.0, math.pi) if cut else (0.0, 2 * math.pi)
    nseg = 48 if cut else 96
    npt = nseg + 1 if cut else nseg
    ring_v, ring_q = [], []
    for k in range(npt):
        a = a0 + (a1 - a0) * k / nseg
        ring_v += [(r1 * math.cos(a), r1 * math.sin(a)), (r0 * math.cos(a), r0 * math.sin(a))]
    for k in range(nseg):
        k2 = (k + 1) % npt
        ring_q.append((2 * k, 2 * k2, 2 * k2 + 1, 2 * k + 1))
    add(ring_v, ring_q, [1.0] * len(ring_v))

    def P(r, deg):
        return (r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg)))
    ra, rb, rc = 5.33, 5.61, 5.89
    for k in range(4):
        base_deg = 90.0 * k
        if cut and not (0.0 <= (base_deg + 20.0) % 360.0 <= 180.0 and 0.0 <= (base_deg + 45.0) % 360.0 <= 180.0):
            continue
        cl = [P(r1 - 0.01, base_deg + 20.0), P(ra, base_deg + 20.0)]
        cl += [P(ra, base_deg + 20.0 + 16.0 * i / 12) for i in range(1, 13)]
        cen = Vector(P((ra + rb) / 2, base_deg + 36.0))
        rad = (rb - ra) / 2
        u = Vector(P(1.0, base_deg + 36.0))          # radial unit
        tng = Vector((-u.y, u.x))                    # +phi direction
        for i in range(1, 8):
            a = math.pi * i / 8
            p = cen - u * rad * math.cos(a) + tng * rad * math.sin(a)
            cl.append(tuple(p))
        cl += [P(rb, base_deg + 36.0 - 10.0 * i / 8) for i in range(0, 9)]
        cen = Vector(P((rb + rc) / 2, base_deg + 26.0))
        u = Vector(P(1.0, base_deg + 26.0))
        tng = Vector((-u.y, u.x))
        rad = (rc - rb) / 2
        for i in range(1, 8):
            a = math.pi * i / 8
            p = cen - u * rad * math.cos(a) - tng * rad * math.sin(a)
            cl.append(tuple(p))
        cl += [P(rc, base_deg + 26.0 + 19.0 * i / 14) for i in range(0, 15)]
        cl += [P(6.35, base_deg + 45.0)]
        v2, q, s = _strip(cl, w)
        L = s[-1]
        wt = []
        for i in range(len(cl)):
            f = s[i] / L
            ww = 1.0 - (f * f * (3 - 2 * f))
            wt += [ww, ww]
        add(v2, q, wt)
        # pad at the corner, fixed
        c = Vector(P(6.85, base_deg + 45.0))
        pad = [tuple(c + Vector(dv)) for dv in ((0.55, 0.55), (-0.55, 0.55), (-0.55, -0.55), (0.55, -0.55))]
        add(pad, [(0, 1, 2, 3)], [0.0] * 4)
    # extrude
    zt = -zc * S
    zb = -(zc + t) * S
    v3 = [(x * S, y * S, zt) for x, y in verts] + [(x * S, y * S, zb) for x, y in verts]
    n = len(verts)
    f3 = list(faces) + [tuple(n + i for i in reversed(f)) for f in faces]
    # side walls along boundary edges
    from collections import Counter
    cnt = Counter()
    for f in faces:
        for i in range(len(f)):
            e = tuple(sorted((f[i], f[(i + 1) % len(f)])))
            cnt[e] += 1
    for f in faces:
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            if cnt[tuple(sorted((a, b)))] == 1:
                f3.append((b, a, n + a, n + b))
    me = bpy.data.meshes.new(name)
    me.from_pydata(v3, [], f3)
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.shade_flat()
    ob = _new_object(name, me, [mat])
    base = [tuple(v.co) for v in me.vertices]
    weights = wts + wts
    return ob, base, weights


def _bond(name, s, bd, S, cut, gold):
    """Bond pads on the die border and gold wires arching to the board, along both long edges (x)."""
    pads_v, pads_f = [], []
    curves = bpy.data.curves.new(name + "_wires", "CURVE")
    curves.dimensions = "3D"
    curves.bevel_depth = WIRE_MM / 2 * S
    curves.bevel_resolution = 2
    n = 22
    for side in (1, -1):
        y_die = side * (s["hy"] - 0.18)
        y_board = side * (s["hy"] + 0.32)
        if cut and side < 0:
            continue
        for i in range(n):
            x = -s["ax"] + 0.2 + (2 * s["ax"] - 0.4) * i / (n - 1)
            for (yc, zc, hs) in ((y_die, s["z0"], 0.06), (y_board, bd["z0"], 0.08)):
                o = len(pads_v)
                z = -(zc - 0.004) * S
                for dx, dy in ((hs, hs), (-hs, hs), (-hs, -hs), (hs, -hs)):
                    pads_v.append(((x + dx) * S, (yc + dy) * S, z))
                pads_f.append((o, o + 1, o + 2, o + 3))
            sp = curves.splines.new("BEZIER")
            sp.bezier_points.add(1)
            p0 = Vector((x * S, y_die * S, -(s["z0"] - 0.01) * S))
            p1 = Vector((x * S, y_board * S, -(bd["z0"] - 0.01) * S))
            h = 0.22 * S
            sp.bezier_points[0].co = p0
            sp.bezier_points[0].handle_left = p0
            sp.bezier_points[0].handle_right = p0 + Vector((0, 0, h * 1.3))
            sp.bezier_points[1].co = p1
            sp.bezier_points[1].handle_left = p1 + Vector((0, -side * 0.08 * S, h * 0.9))
            sp.bezier_points[1].handle_right = p1
    me = bpy.data.meshes.new(name + "_pads")
    me.from_pydata(pads_v, [], pads_f)
    me.validate()
    pads = _new_object(name + "_pads", me, [gold])
    wires = _new_object(name + "_wires", curves, [gold])
    return pads, wires


def _smd(name, bd, S, cut):
    """A few capacitors and a small IC on the board strip beside the base (the -x side)."""
    cer = _mat("mo_ceramic", **{"Base Color": (0.42, 0.33, 0.22, 1), "Roughness": 0.45})
    tin = metal("mo_tin", (0.80, 0.80, 0.80), 0.3, S)
    ic = _mat("mo_ic", **{"Base Color": (0.02, 0.02, 0.022, 1), "Roughness": 0.35})
    verts, faces, mats = [], [], []

    def cube(x0, x1, y0, y1, z0, z1, mi):
        o = len(verts)
        for x in (x0, x1):
            for y in (y0, y1):
                for z in (z0, z1):
                    verts.append((x * S, y * S, -z * S))
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            faces.append(tuple(o + i for i in f))
            mats.append(mi)
    z = bd["z0"]
    xs = (-7.6, -7.0, -6.4)
    for j, y in enumerate((-4.5, -3.0, -1.5, 1.5, 3.0, 4.5)):
        if cut and y < 0:
            continue
        x = xs[j % 3]
        cube(x - 0.15, x + 0.15, y - 0.3, y - 0.2, z - 0.3, z, 1)
        cube(x - 0.15, x + 0.15, y - 0.2, y + 0.2, z - 0.3, z, 0)
        cube(x - 0.15, x + 0.15, y + 0.2, y + 0.3, z - 0.3, z, 1)
    cube(-7.8, -6.6, -0.7 if not cut else 0.05, 0.7, z - 0.35, z, 2)
    if not verts:
        return None
    me = bpy.data.meshes.new(name + "_smd")
    me.from_pydata(verts, [], faces)
    for p, mi in zip(me.polygons, mats):
        p.material_index = mi
    _finish(me, 20.0)
    return _new_object(name + "_smd", me, [cer, tin, ic])
