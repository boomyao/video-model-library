"""The phone (group B; other groups import it read-only): a generic flagship, no logos, no brand design.

Body 152 x 72 x 8.75 mm (the iPhone 18 Pro's thickness, which the narration names; the footprint and the design are
generic): frosted back glass (fine grain), bead-blasted aluminium frame with flat sides, black front glass. A round
camera island (40 mm, metal ring with a polished chamfer, a dark glass top with a fine concentric finish) whose
heights are the iPhone 18 Pro's dimensional drawing (研究/摄像头/事实核查.md §17): back plate to camera plateau
2.78 mm, plateau to rear camera glass 2.11 mm, 4.89 mm in all, 13.64 mm total at the lens. It carries three lenses
(main, ultra-wide, periscope telephoto, all with their cover glass 2.11 mm above the plateau), a flash and a small
sensor window. Under the main window sits
module.py's module with the patent lens at x 1.40 (a 1/1.28-inch sensor, 10.1 mm from the first vertex to the
sensor), standing on its board just above the midframe: the stack is taller than the body is thick, and that is the
bump. Everything except the patent lens is ILLUSTRATIVE (believable, not a real phone): 2D tags it 示意.

    import phone as PH
    p = PH.Phone(scale=0.001)                       # whole phone, main module inside, real size
    p.root.location = (0, 0, 0)                     # metres; the phone lies on its front face at z = 0
    p = PH.Phone(cut="main", internals=True)        # cut lengthwise through the main camera (S310)
    p.set_xray(0.6)                                 # island turning translucent (needs xray=True)

INTERFACE (stable from 2026-10-30; group B only adds, never changes):

  Phone(scale=0.001, cut=None, internals=False, modules=True, xray=False, color="graphite", name="phone",
        main_mag=1.4, seg=128)
      scale      Blender units per real mm (0.001 = real size; 0.01 works too)
      cut        None, "main", "tele" or a number y (mm): cut lengthwise (plane y = const through the camera) and
                 keep the half y >= cut, section faces facing a camera at -y (the lens.py convention, so the main
                 module and its lens are cut in the same plane). Parts wholly on the far side are not built.
      internals  True adds what a cut shows inside: display, aluminium midframe, battery (electrode layers in the
                 section), logic board with shields. Off for exterior shots (cheaper).
      modules    True: the main module (module.Module, mag main_mag, x 1.40 by default), a simple ultra-wide
                 module and a light baffle under the tele window (the periscope itself is built by the shot).
      xray       True prepares the island and the back glass around it for set_xray()
      color      "graphite" (default), "titanium", "mist" (light grey-blue): back glass and frame colour
  p.root         empty: phone frame. Origin at the centre of the front face (the face it lies on); +x along the
                 length toward the camera end, +y across (the island's tele side), +z out of the back. The back
                 glass is at z = T. Move / turn the phone with p.root (metres, radians).
  p.L, p.W, p.T  152, 72, 8.75 (mm)
  p.island       dict: cx, cy, r (mm, plan), top (plateau top, mm above the front face), h (2.78, above the back)
  p.lens         dict "main" / "ultrawide" / "tele" -> dict(x, y, top, r_out, r_win, win_bottom) in phone mm
                 (top = cover glass top, mm above the front face)
  p.flash        dict(x, y, r)
  p.main         the main camera's module.Module (or None); its root sits at the L1 vertex,
                 p.main_vertex = (x, y, z) phone mm. p.main.focus() etc. work as in module.py.
  p.obj          dict name -> object: "frame", "back_glass", "front_glass", "buttons", "deco_ring", "deco_glass",
                 "bezel_main", "bezel_ultrawide", "bezel_tele", "window_*", "mask_*", "flash", "flash_ring",
                 "dot", plus with internals "display", "midframe", "battery", "board", "shields", and with modules
                 "uw_barrel", "uw_lens", "uw_can", "tele_baffle"
  p.groups       "body", "island", "internals", "modules"(simple ones; p.main.groups for the main module)
  p.Z            heights, mm above the front face: "front" 0, "back" T, "plateau" (island top), "bump_top" (main
                 cover glass top = T + 4.89), "side_top" (ultra-wide / tele cover glass top, the same height),
                 "display_top", "midframe_top", "board_top"
  p.local(x, y, z)   world Vector (metres) of a point in phone mm
  p.point(name)      world Vector of a named point (for anchors): "bump_top" (centre of the main cover glass top),
                     "bump_base" (back glass at the island's foot, on the phone's centre line, nearest the bottom
                     end), "plateau_edge" (top of the island's ring above bump_base), "body_top" / "body_bottom"
                     (back glass top / front face, 3 mm in front of the island's foot, in the cut plane when cut),
                     "island_centre" (plateau top centre)
  p.set_xray(k, wipe=None)  0..1: island (ring, glass top, bezels, windows, flash) and the back glass over the
                     island's footprint fade to clear ghost glass so the modules inside show. wipe=None fades
                     everything together; a number 0..1 is the height of the fade front (1 = all of it): the X-ray
                     descends from the top of the bump toward the front face as wipe grows.
"""
import math

import bpy
from mathutils import Vector

import module as MO

L, W, T = 152.0, 72.0, 8.75
CORNER = 10.0
ISLAND = dict(cx=46.0, cy=0.0, r=20.0, h=2.78)   # iPhone 18 Pro drawing: back plate to camera plateau 2.78 mm
BUMP = 4.89              # back plate to rear camera glass: 2.78 + 2.11 (iPhone 18 Pro drawing, §17)
SIDE_BUMP = BUMP         # the drawing gives one plateau-to-glass height for the cameras
LENSES = {
    "main": dict(x=51.5, y=0.0, r_out=7.2, r_cham=6.75, r_win=5.55, r_bore=4.15, mask=4.05, bump=BUMP),
    "ultrawide": dict(x=39.0, y=-10.5, r_out=5.9, r_cham=5.5, r_win=4.55, r_bore=3.2, mask=2.9, bump=SIDE_BUMP),
    "tele": dict(x=39.0, y=10.5, r_out=5.9, r_cham=5.5, r_win=4.55, r_bore=3.2, mask=2.9, bump=SIDE_BUMP),
}
FLASH = dict(x=30.5, y=0.0, r=2.3)
DOT = dict(x=52.0, y=-13.6, r=1.25)
MIC = dict(x=52.0, y=13.6, r=0.35)
WIN_T = 0.42
GLASS_T = 0.65           # back glass
FRONT_T = 0.50           # front glass
DISPLAY_TOP = 0.82
MIDFRAME = (0.82, 1.32)
BOARD = (1.42, 2.22)
BATTERY = dict(x0=-66.0, x1=12.0, hy=31.0, z0=1.42, z1=T - 0.80)

COLORS = {
    "graphite": dict(glass=(0.040, 0.042, 0.047), frame=(0.30, 0.30, 0.31)),
    "titanium": dict(glass=(0.085, 0.083, 0.080), frame=(0.47, 0.45, 0.43)),
    "mist": dict(glass=(0.20, 0.22, 0.25), frame=(0.62, 0.64, 0.66)),
}


# ------------------------------------------------------------------ materials
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


def _bump(m, feature_mm, strength, dist_mm, scale, kind="noise"):
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tx = nt.nodes.new("ShaderNodeTexNoise")
    tx.inputs["Scale"].default_value = 1.0 / (feature_mm * scale)
    tx.inputs["Detail"].default_value = 4.0
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = strength
    bp.inputs["Distance"].default_value = dist_mm * scale
    nt.links.new(tc.outputs["Object"], tx.inputs["Vector"])
    nt.links.new(tx.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def mats(scale, color="graphite"):
    """All phone materials for this scale and colour (created once, then shared)."""
    key = "%s_%g" % (color, scale)
    c = COLORS[color]
    M = {}
    M["glass"] = bpy.data.materials.get("ph_backglass_" + key) or _bump(
        _mat("ph_backglass_" + key, **{"Base Color": (*c["glass"], 1), "Roughness": 0.40, "Specular IOR Level": 0.55,
                                         "Coat Weight": 0.15, "Coat Roughness": 0.35}), 0.012, 0.35, 0.002, scale)
    M["glass_cut"] = _mat("ph_glass_cut_" + key, **{"Base Color": (0.020, 0.032, 0.028, 1), "Roughness": 0.05,
                                                    "Coat Weight": 1.0, "Coat Roughness": 0.03})
    M["frame"] = bpy.data.materials.get("ph_frame_" + key) or _bump(
        _mat("ph_frame_" + key, **{"Base Color": (*c["frame"], 1), "Metallic": 1.0, "Roughness": 0.36}),
        0.010, 0.25, 0.002, scale)
    M["frame_polish"] = _mat("ph_frame_polish_" + key, **{"Base Color": (*[min(1, v * 1.5) for v in c["frame"]], 1),
                                                           "Metallic": 1.0, "Roughness": 0.08})
    M["alu_cut"] = _mat("ph_alu_cut_%g" % scale, **{"Base Color": (0.82, 0.82, 0.83, 1), "Metallic": 1.0,
                                                    "Roughness": 0.34})
    M["front"] = _mat("ph_front_%g" % scale, **{"Base Color": (0.004, 0.004, 0.005, 1), "Roughness": 0.04,
                                                "Coat Weight": 1.0, "Coat Roughness": 0.02})
    M["front_cut"] = _mat("ph_front_cut_%g" % scale, **{"Base Color": (0.010, 0.016, 0.014, 1), "Roughness": 0.05})
    M["deco_glass"] = _concentric(_mat("ph_decoglass_" + key, **{
        "Base Color": (*[v * 0.55 for v in c["glass"]], 1), "Roughness": 0.16, "Anisotropic": 0.85,
        "Coat Weight": 1.0, "Coat Roughness": 0.03, "Specular IOR Level": 0.6}))
    M["steel"] = _mat("ph_steel_%g" % scale, **{"Base Color": (0.62, 0.62, 0.63, 1), "Metallic": 1.0, "Roughness": 0.22})
    M["polish"] = _mat("ph_polish_%g" % scale, **{"Base Color": (0.86, 0.86, 0.87, 1), "Metallic": 1.0, "Roughness": 0.035})
    M["ceramic"] = _mat("ph_ceramic_%g" % scale, **{"Base Color": (0.006, 0.006, 0.007, 1), "Roughness": 0.09,
                                                    "Coat Weight": 1.0, "Coat Roughness": 0.05})
    M["sapphire"] = _mat("ph_sapphire_%g" % scale, **{"Base Color": (0.97, 0.98, 1.0, 1), "Roughness": 0.0,
                                                      "Transmission Weight": 1.0, "IOR": 1.77,
                                                      "Thin Film Thickness": 360.0, "Thin Film IOR": 1.38})
    M["mask"] = _mat("ph_mask_%g" % scale, **{"Base Color": (0.003, 0.003, 0.003, 1), "Roughness": 0.25})
    M["diffuser"] = _fresnel_rings(_mat("ph_diffuser_%g" % scale, **{
        "Base Color": (0.80, 0.78, 0.70, 1), "Roughness": 0.35, "Subsurface Weight": 0.4,
        "Subsurface Radius": (0.4, 0.4, 0.3), "Subsurface Scale": 0.5 * scale, "Coat Weight": 1.0,
        "Coat Roughness": 0.05}), scale)
    M["black"] = MO.black_plastic(scale)
    M["black_cut"] = MO.black_section(scale)
    M["oled"] = _layers("ph_oled_%g" % scale, scale, [(0.010, 0.010, 0.012), (0.60, 0.36, 0.20), (0.03, 0.03, 0.035)],
                        [0.10, 0.04, 0.18], metal_layers=(1,))
    M["battery"] = _bump(_mat("ph_battery_%g" % scale, **{"Base Color": (0.028, 0.032, 0.040, 1), "Roughness": 0.45,
                                                         "Coat Weight": 0.4, "Coat Roughness": 0.2}), 1.5, 0.15, 0.03, scale)
    M["battery_cut"] = _layers("ph_battery_cut_%g" % scale, scale,
                               [(0.55, 0.32, 0.18), (0.16, 0.16, 0.17), (0.70, 0.70, 0.72), (0.10, 0.10, 0.11)],
                               [0.012, 0.060, 0.016, 0.060], metal_layers=(0, 2))
    M["pcb"] = MO.pcb(scale)
    M["pcb_cut"] = MO.pcb_section(scale)
    M["can"] = MO.metal("ph_can", (0.66, 0.66, 0.68), 0.28, scale, grain=0.2)
    M["can_cut"] = MO.metal("ph_can_cut", (0.80, 0.80, 0.82), 0.18, scale)
    M["dark_glass"] = _mat("ph_darkglass_%g" % scale, **{"Base Color": (0.01, 0.011, 0.013, 1), "Roughness": 0.02,
                                                         "Coat Weight": 1.0, "Thin Film Thickness": 300.0,
                                                         "Thin Film IOR": 1.38})
    return M


def _concentric(m):
    """Fine concentric (CD-like) finish: anisotropic reflection with tangents round the object's own z axis."""
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tg = nt.nodes.new("ShaderNodeTangent")
    tg.direction_type = "RADIAL"
    tg.axis = "Z"
    nt.links.new(tg.outputs["Tangent"], b.inputs["Tangent"])
    return m


def _fresnel_rings(m, scale):
    """Flash diffuser: a Fresnel-lens pattern of rings round the object's origin (bump)."""
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.wave_type = "RINGS"
    wv.rings_direction = "Z"
    wv.inputs["Scale"].default_value = 1.0 / (0.25 * scale)
    wv.inputs["Distortion"].default_value = 0.0
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.25
    bp.inputs["Distance"].default_value = 0.01 * scale
    nt.links.new(tc.outputs["Object"], wv.inputs["Vector"])
    nt.links.new(wv.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def _layers(name, scale, colors, thick, metal_layers=()):
    """Section material: horizontal layers (along z) of the given colours and thicknesses (mm), repeating."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = _mat(name, **{"Roughness": 0.4})
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    period = sum(thick)
    div = nt.nodes.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = period * scale
    fr = nt.nodes.new("ShaderNodeMath")
    fr.operation = "FRACT"
    nt.links.new(sep.outputs["Z"], div.inputs[0])
    nt.links.new(div.outputs[0], fr.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    acc = 0.0
    met = nt.nodes.new("ShaderNodeValToRGB")
    met.color_ramp.interpolation = "CONSTANT"
    mels = met.color_ramp.elements
    for i, (col, th) in enumerate(zip(colors, thick)):
        if i == 0:
            els[0].position, els[0].color = 0.0, (*col, 1)
            mels[0].position = 0.0
            mels[0].color = (1, 1, 1, 1) if i in metal_layers else (0, 0, 0, 1)
            if len(els) > 1:
                els.remove(els[1])
                mels.remove(mels[1])
        else:
            e = els.new(acc / period)
            e.color = (*col, 1)
            me = mels.new(acc / period)
            me.color = (1, 1, 1, 1) if i in metal_layers else (0, 0, 0, 1)
        acc += th
    nt.links.new(fr.outputs[0], ramp.inputs["Fac"])
    nt.links.new(fr.outputs[0], met.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(met.outputs["Color"], b.inputs["Metallic"])
    return m


# ------------------------------------------------------------------ geometry helpers (phone mm, z up)
def _rev(name, prof, S, cx, cy, mats_list, edge_mat=None, seg=128, own_origin=False):
    """Solid of revolution round the vertical line through (cx, cy). prof: closed polygon [(r, z)] with z up
    (phone mm). edge_mat: material index per profile edge (edge i runs from prof[i] to prof[i+1])."""
    n = len(prof)
    ox, oy = (0.0, 0.0) if own_origin else (cx, cy)
    verts, faces, fm = [], [], []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        ca, sa = math.cos(a), math.sin(a)
        for (r, z) in prof:
            verts.append(((ox + r * ca) * S, (oy + r * sa) * S, z * S))
    for k in range(seg):
        k2 = (k + 1) % seg
        for i in range(n):
            i2 = (i + 1) % n
            faces.append((k * n + i, k * n + i2, k2 * n + i2, k2 * n + i))
            fm.append(edge_mat[i] if edge_mat else 0)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    for p, mi in zip(me.polygons, fm):
        p.material_index = mi
    MO._finish(me, 35.0)
    ob = MO._new_object(name, me, mats_list)
    if own_origin:
        ob.location = (cx * S, cy * S, 0.0)
    return ob


def _slab(name, plan, z0, z1, S, mat, own=None):
    """Prism from a plan polygon [(x, y)] between heights z0 < z1 (phone mm, z up). own=(cx, cy): object origin
    there (vertices relative)."""
    ox, oy = own if own else (0.0, 0.0)
    pl = [(x - ox, y - oy) for x, y in plan]
    ob = MO.prism(name, pl, -z1, -z0, S, mat)        # module.prism takes z toward -world
    if own:
        ob.location = (ox * S, oy * S, 0.0)
    return ob


def _disc(r, n=96, cx=0.0, cy=0.0):
    return MO.circle(r, n, cx, cy)


def _cut_tool(xmin, xmax, ymin, ymax, zmin, zmax, S, name="tool"):
    return MO.box_cutter(xmin * S, xmax * S, ymin * S, ymax * S, zmin * S, zmax * S, name=name)


def _cyl_tool(cx, cy, r, z0, z1, S, n=96):
    return _slab("tool", _disc(r, n, cx, cy), z0, z1, S, None)


def _subtract(ob, tools):
    """Booleans work in world space: tools are built in phone coordinates at the origin, like every part."""
    for t in tools:
        MO.boolean(ob, t)
        me = t.data
        bpy.data.objects.remove(t)
        bpy.data.meshes.remove(me)
    return ob


# ------------------------------------------------------------------ the phone
class Phone:
    def __init__(self, scale=0.001, cut=None, internals=False, modules=True, xray=False, color="graphite",
                 name="phone", main_mag=1.4, seg=128):
        self.scale, self.name = scale, name
        S = scale
        self.L, self.W, self.T = L, W, T
        self.island = dict(ISLAND, top=T + ISLAND["h"])
        self.flash = dict(FLASH)
        self.y_cut = None if cut is None else (LENSES[cut]["y"] if isinstance(cut, str) else float(cut))
        M = self.M = mats(S, color)
        self.obj, self.groups = {}, {"body": [], "island": [], "internals": [], "modules": []}
        self._xray = []
        sc = bpy.context.scene.collection
        self.root = bpy.data.objects.new(name + "_root", None)
        sc.objects.link(self.root)
        self.root.empty_display_size = 20 * S

        def keep(nm, ob, group, cap=None, xr=False):
            """Register, cut if needed (cap = material of the section faces), parent to the root."""
            if self.y_cut is not None:
                ob = self._apply_cut(ob, cap)
                if ob is None:
                    return None
            ob.parent = self.root
            self.obj[nm] = ob
            self.groups[group].append(ob)
            if xr:
                self._xray.append(ob)
            return ob

        ic = self.island
        cx, cy, R = ic["cx"], ic["cy"], ic["r"]
        # ---- body
        fr = _slab(name + "_frame", MO.rrect(L / 2, W / 2, CORNER, 12), 0.15, T - 0.15, S, M["frame"])
        _subtract(fr, [_slab("tool", MO.rrect(L / 2 - 1.4, W / 2 - 1.4, CORNER - 1.4, 12), -1, T + 1, S, None)])
        MO.bevel(fr, 0.42 * S, 4, angle=30.0)
        keep("frame", fr, "body", M["alu_cut"])
        bg = _slab(name + "_back_glass", MO.rrect(L / 2 - 1.45, W / 2 - 1.45, CORNER - 1.45, 12), T - GLASS_T, T, S, M["glass"])
        _subtract(bg, [_cyl_tool(cx, cy, R + 0.05, T - 2, T + 1, S, 160)])
        MO.bevel(bg, 0.28 * S, 4, angle=30.0)
        keep("back_glass", bg, "body", M["glass_cut"], xr=True)
        fg = _slab(name + "_front_glass", MO.rrect(L / 2 - 1.45, W / 2 - 1.45, CORNER - 1.45, 12), 0.0, FRONT_T, S, M["front"])
        MO.bevel(fg, 0.22 * S, 3, angle=30.0)
        keep("front_glass", fg, "body", M["front_cut"])
        btn = []
        for x0, x1 in ((10.0, 20.0), (27.0, 45.0)):
            b = _slab("btn", MO.rrect((x1 - x0) / 2, 0.42, 0.3, 4, cx=(x0 + x1) / 2, cy=-W / 2 - 0.15), 3.0, 5.3, S, M["frame"])
            MO.bevel(b, 0.2 * S, 3, angle=30.0)
            btn.append(b)
        bt = MO._join(name + "_buttons", btn, M["frame"])
        keep("buttons", bt, "body", M["alu_cut"])

        # ---- island: ring, glass top, bezels, windows, masks, flash, dot
        H = ISLAND["h"]
        prof = [(18.6, T - GLASS_T), (20.0, T - GLASS_T), (20.0, T + H - 0.48), (19.52, T + H), (18.8, T + H),
                (18.8, T + H - 0.55), (18.2, T + H - 0.55), (18.2, T + H - 0.9), (18.6, T + H - 0.9)]
        em = [0, 0, 1, 0, 0, 0, 0, 0, 0]
        ring = _rev(name + "_deco_ring", prof, S, cx, cy, [M["frame"], M["frame_polish"]], em, seg=192)
        keep("deco_ring", ring, "island", M["alu_cut"], xr=True)
        dg = _slab(name + "_deco_glass", _disc(18.75, 192, cx, cy), T + H - 0.55, T + H - 0.05, S, M["deco_glass"],
                   own=(cx, cy))
        tools = [_cyl_tool(l["x"], l["y"], l["r_out"] + 0.05, T, T + 4, S, 128) for l in LENSES.values()]
        tools += [_cyl_tool(FLASH["x"], FLASH["y"], FLASH["r"] + 0.3, T, T + 4, S),
                  _cyl_tool(DOT["x"], DOT["y"], DOT["r"] + 0.05, T, T + 4, S),
                  _cyl_tool(MIC["x"], MIC["y"], MIC["r"], T, T + 4, S, 24)]
        _subtract(dg, tools)
        MO.bevel(dg, 0.08 * S, 2, angle=30.0)
        keep("deco_glass", dg, "island", M["glass_cut"], xr=True)
        self.lens = {}
        for key, l in LENSES.items():
            top = T + l["bump"]
            wb = top - WIN_T
            bot = T + H - 0.85
            prof = [(l["r_bore"], bot), (l["r_out"] - 0.2, bot), (l["r_out"] - 0.2, T + H - 0.58), (l["r_out"], T + H - 0.58),
                    (l["r_out"], top - 0.42), (l["r_cham"], top), (l["r_win"] + 0.03, top), (l["r_win"] + 0.03, wb - 0.02),
                    (l["r_bore"], wb - 0.02)]
            em = [0, 0, 0, 1, 2, 3, 0, 0, 0]
            bz = _rev("%s_bezel_%s" % (name, key), prof, S, l["x"], l["y"], [M["steel"], M["steel"], M["polish"], M["ceramic"]],
                      em, seg=160)
            keep("bezel_" + key, bz, "island", M["can_cut"], xr=True)
            w = _slab("%s_window_%s" % (name, key), _disc(l["r_win"], 128, l["x"], l["y"]), wb, top, S, M["sapphire"])
            MO.bevel(w, 0.06 * S, 2, angle=30.0)
            keep("window_" + key, w, "island", M["sapphire"], xr=True)
            mk = _rev("%s_mask_%s" % (name, key), [(l["mask"], wb - 0.018), (l["r_win"], wb - 0.018), (l["r_win"], wb - 0.002),
                                                  (l["mask"], wb - 0.002)], S, l["x"], l["y"], [M["mask"]], seg=128)
            keep("mask_" + key, mk, "island", M["mask"], xr=True)
            self.lens[key] = dict(x=l["x"], y=l["y"], top=top, r_out=l["r_out"], r_win=l["r_win"], win_bottom=wb)
        fl = _slab(name + "_flash", _disc(FLASH["r"], 96, FLASH["x"], FLASH["y"]), T + H - 0.5, T + H - 0.06, S, M["diffuser"],
                   own=(FLASH["x"], FLASH["y"]))
        MO.bevel(fl, 0.05 * S, 2, angle=30.0)
        keep("flash", fl, "island", M["diffuser"], xr=True)
        flr = _rev(name + "_flash_ring", [(FLASH["r"], T + H - 0.7), (FLASH["r"] + 0.28, T + H - 0.7),
                                          (FLASH["r"] + 0.28, T + H - 0.04), (FLASH["r"], T + H - 0.04)],
                   S, FLASH["x"], FLASH["y"], [M["polish"]], seg=96)
        keep("flash_ring", flr, "island", M["can_cut"], xr=True)
        dt = _slab(name + "_dot", _disc(DOT["r"], 64, DOT["x"], DOT["y"]), T + H - 0.5, T + H - 0.06, S, M["dark_glass"])
        MO.bevel(dt, 0.05 * S, 2, angle=30.0)
        keep("dot", dt, "island", M["dark_glass"], xr=True)

        # ---- internals
        if internals:
            dp = _slab(name + "_display", MO.rrect(L / 2 - 1.5, W / 2 - 1.5, CORNER - 1.5, 12), FRONT_T, DISPLAY_TOP, S, M["oled"])
            keep("display", dp, "internals", M["oled"])
            mf = _slab(name + "_midframe", MO.rrect(L / 2 - 1.38, W / 2 - 1.38, CORNER - 1.38, 12), MIDFRAME[0], MIDFRAME[1], S,
                       M["frame"])
            # the main module's board rests just above the midframe (no cutout needed at 8.75 mm)
            MO.bevel(mf, 0.1 * S, 2, angle=30.0)
            keep("midframe", mf, "internals", M["alu_cut"])
            bt = _slab(name + "_battery", MO.rrect((BATTERY["x1"] - BATTERY["x0"]) / 2, BATTERY["hy"], 4.0, 8,
                                                   cx=(BATTERY["x1"] + BATTERY["x0"]) / 2), BATTERY["z0"], BATTERY["z1"], S,
                       M["battery"])
            MO.bevel(bt, 0.9 * S, 4, angle=30.0)
            keep("battery", bt, "internals", M["battery_cut"])
            bd = _slab(name + "_board", MO.rrect((71.4 - 14.5) / 2, 31.0, 3.0, 6, cx=(71.4 + 14.5) / 2), BOARD[0], BOARD[1], S,
                       M["pcb"])
            _subtract(bd, [_slab("tool", MO.rrect(10.6, 9.2, 0.8, 4, cx=LENSES["main"]["x"] - 1.75, cy=0.0), -1, 3, S, None)])
            MO.bevel(bd, 0.08 * S, 2, angle=30.0)
            keep("board", bd, "internals", M["pcb_cut"])
            sh = []
            for (x0, x1, y0, y1, h) in ((62.5, 70.0, -26.0, -6.0, 1.1), (17.0, 33.0, -28.0, -17.0, 0.9),
                                        (17.0, 29.0, 16.0, 28.0, 1.0), (62.5, 70.5, 9.0, 27.0, 1.2), (44.0, 60.0, 19.0, 28.5, 0.8),
                                        (44.0, 60.0, -28.5, -19.0, 0.8)):
                b = _slab("sh", MO.rrect((x1 - x0) / 2, (y1 - y0) / 2, 0.6, 4, cx=(x0 + x1) / 2, cy=(y0 + y1) / 2),
                          BOARD[1], BOARD[1] + h, S, M["can"])
                MO.bevel(b, 0.1 * S, 2, angle=30.0)
                sh.append(b)
            keep("shields", MO._join(name + "_shields", sh, M["can"]), "internals", M["can_cut"])

        # ---- modules
        self.main = None
        l = LENSES["main"]
        gap = 0.45 * main_mag + 0.05                          # the stroke of the focusing motor, plus a little
        self.main_vertex = (l["x"], l["y"], T + l["bump"] - WIN_T - gap - MO.LIP_TOP * -main_mag)
        if modules:
            cut_main = self.y_cut is not None and abs(self.y_cut - l["y"]) < 1e-6
            far = self.y_cut is not None and self.y_cut > l["y"] + MO.HOUSING["half"] * main_mag
            if self.y_cut is None or cut_main or not far:
                if self.y_cut is not None and not cut_main:
                    raise ValueError("a cut that crosses the main module off its axis is not supported")
                parts = [p for p in MO.PARTS if p != "flex"]          # the flex tail would run into the midframe
                self.main = MO.Module(scale=S, mag=main_mag, cut=cut_main, name=name + "_main", parent=self.root, seg=seg,
                                      parts=parts)
                vx, vy, vz = self.main_vertex
                self.main.root.location = (vx * S, vy * S, vz * S)
            self._simple_modules(S, M, keep)

        self.Z = {"front": 0.0, "back": T, "plateau": T + ISLAND["h"], "bump_top": T + BUMP, "side_top": T + SIDE_BUMP,
                  "display_top": DISPLAY_TOP, "midframe_top": MIDFRAME[1], "board_top": BOARD[1]}
        if xray:
            self._install_xray()

    # ---------------------------------------------------------------- simple modules: ultra-wide, tele baffle
    def _simple_modules(self, S, M, keep):
        T_ = T
        u = LENSES["ultrawide"]
        top_n = T_ + u["bump"] - WIN_T - 0.35
        b = _rev(self.name + "_uw_barrel", [(1.55, T_ + 1.2), (2.35, T_ + 1.2), (2.35, top_n - 0.05), (2.25, top_n),
                                           (1.55, top_n)], S, u["x"], u["y"], [M["black"]], seg=96)
        keep("uw_barrel", b, "modules", M["black_cut"])
        # a generic front element seen through the window (illustrative: the ultra-wide's own design is not ours)
        prof = [(0.0, top_n - 0.30)] + [(1.55 * i / 12, top_n - 0.30 + 0.55 * (1 - (i / 12) ** 2) ** 0.5 * 0 + 0.42 * (1 - (i / 12) ** 2))
                                         for i in range(1, 13)] + [(1.55, top_n - 0.55), (0.0, top_n - 0.6)]
        ln = _rev(self.name + "_uw_lens", prof, S, u["x"], u["y"], [M["dark_glass"]], seg=96)
        keep("uw_lens", ln, "modules", M["dark_glass"])
        can = _slab(self.name + "_uw_can", MO.rrect(4.0, 4.0, 0.5, 4, cx=u["x"], cy=u["y"]), BOARD[1], T_ + 0.5, S, M["can"])
        _subtract(can, [_cyl_tool(u["x"], u["y"], 2.4, T_ - 0.2, T_ + 2, S)])
        MO.bevel(can, 0.08 * S, 2, angle=30.0)
        keep("uw_can", can, "modules", M["can_cut"])
        t = LENSES["tele"]
        bf = _rev(self.name + "_tele_baffle", [(2.05, T_ - 0.75), (2.6, T_ - 0.75), (2.6, T_ + t["bump"] - WIN_T - 0.3),
                                              (2.05, T_ + t["bump"] - WIN_T - 0.3)], S, t["x"], t["y"], [M["black"]], seg=96)
        keep("tele_baffle", bf, "modules", M["black_cut"])

    # ---------------------------------------------------------------- the lengthwise cut
    def _apply_cut(self, ob, cap):
        """Keep the part of ob with y >= y_cut (phone mm). Objects with their own origin are handled too."""
        y0 = self.y_cut
        S = self.scale
        ys = [(ob.matrix_basis @ v.co).y for v in ob.data.vertices] if ob.type == "MESH" else [0.0]
        lo, hi = min(ys) / S, max(ys) / S
        if hi <= y0 + 1e-6:
            me = ob.data
            bpy.data.objects.remove(ob)
            if me.users == 0:
                bpy.data.meshes.remove(me)
            return None
        if lo >= y0 - 1e-6:
            return ob
        c = _cut_tool(-200, 200, y0 - 200, y0, -100, 100, S)
        if cap is not None:
            c.data.materials.append(cap)
        MO.boolean(ob, c, transfer=cap is not None)
        me = c.data
        bpy.data.objects.remove(c)
        bpy.data.meshes.remove(me)
        MO._finish(ob.data, 35.0)
        return ob

    # ---------------------------------------------------------------- x-ray
    def _install_xray(self):
        """Each x-ray object gets its own copies of its materials with a ghost mix in front of the output: the
        island's own parts all of it, the back glass only over the island's footprint (radial mask)."""
        S = self.scale
        ic = self.island
        self._xr_nodes = []
        for ob in self._xray:
            off = ob.location / S                              # object origin in phone mm
            centre = Vector((ic["cx"] - off.x, ic["cy"] - off.y, 0.0))
            radial = ob is self.obj.get("back_glass")
            for i, m in enumerate(ob.data.materials):
                if m is None:
                    continue
                mm = m.copy()
                ob.data.materials[i] = mm
                self._xr_nodes.append(_ghost(mm, S, centre, ic["r"] + 0.3, ic["r"] + 2.5 if radial else None,
                                             T + BUMP, -0.5))
        self.set_xray(0.0)

    def set_xray(self, k, wipe=None):
        for nodes in getattr(self, "_xr_nodes", []):
            nodes["K"].outputs[0].default_value = max(0.0, min(1.0, k))
            nodes["W"].outputs[0].default_value = 2.0 if wipe is None else wipe

    # ---------------------------------------------------------------- points
    def local(self, x, y, z):
        bpy.context.view_layer.update()
        return self.root.matrix_world @ Vector((x * self.scale, y * self.scale, z * self.scale))

    def point(self, name):
        ic = self.island
        yc = self.y_cut if self.y_cut is not None else 0.0
        l = LENSES["main"]
        foot = ic["cx"] - ic["r"]
        if name == "bump_top":
            return self.local(l["x"], l["y"], T + BUMP)
        if name == "bump_base":
            return self.local(foot, ic["cy"], T)
        if name == "plateau_edge":
            return self.local(foot, ic["cy"], T + ISLAND["h"])
        if name == "body_top":
            return self.local(foot - 3.0, yc, T)
        if name == "body_bottom":
            return self.local(foot - 3.0, yc, 0.0)
        if name == "island_centre":
            return self.local(ic["cx"], ic["cy"], T + ISLAND["h"])
        raise KeyError(name)


def _ghost(m, S, centre, r0, r1, z_top, z_bot):
    """Mix(original, ghost glass) in front of the material output. Ghost amount = K * radial mask * wipe mask, where
    the radial mask is 1 inside r0 and 0 beyond r1 (mm round centre, object space) when r1 is given, and the wipe
    lets the fade front come down from z_top (wipe W = 0) to z_bot (W = 1)."""
    nt = m.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    src = out.inputs["Surface"].links[0].from_socket
    tc = nt.nodes.new("ShaderNodeTexCoord")
    kv = nt.nodes.new("ShaderNodeValue")
    kv.name = "XR_K"
    wv = nt.nodes.new("ShaderNodeValue")
    wv.name = "XR_W"

    def node(op, a, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    amount = kv.outputs[0]
    if r1 is not None:
        dx = node("SUBTRACT", sep.outputs["X"], centre.x * S)
        dy = node("SUBTRACT", sep.outputs["Y"], centre.y * S)
        rr = node("SQRT", node("ADD", node("MULTIPLY", dx, dx), node("MULTIPLY", dy, dy)))
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = r1 * S
        mr.inputs["From Max"].default_value = r0 * S
        mr.inputs["To Min"].default_value = 0.0
        mr.inputs["To Max"].default_value = 1.0
        mr.interpolation_type = "SMOOTHSTEP"
        nt.links.new(rr, mr.inputs["Value"])
        amount = node("MULTIPLY", amount, mr.outputs["Result"])
    # wipe: the front comes down from z_top (W = 0) to z_bot (W = 1); above the front a point is ghost, below it
    # not yet (a soft edge of 0.8 mm)
    soft = 0.8
    zf = node("SUBTRACT", z_top * S, node("MULTIPLY", wv.outputs[0], (z_top - z_bot) * S))
    w = node("DIVIDE", node("SUBTRACT", sep.outputs["Z"], zf), soft * S)
    wcl = nt.nodes.new("ShaderNodeClamp")
    nt.links.new(node("ADD", w, 1.0), wcl.inputs["Value"])
    amount = node("MULTIPLY", amount, wcl.outputs[0])
    # the ghost: x-ray glass (transparent, faint neutral edges)
    gsock = MO.ghost_shader(nt)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(amount, mix.inputs["Fac"])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(gsock, mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return {"K": kv, "W": wv}
