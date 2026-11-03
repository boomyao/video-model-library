"""Shot kit: timing, rendering, anchors and the house look shared by every 3D shot of the film.

A shot lives in 画面/shots/Sxxx.py and defines

    def setup(ctx):            # build the scene once
        ...
        def at_frame(t, f):    # t = seconds since the shot started (30 fps plates), f = frame index from 0
            ...
        return at_frame

and is run through 画面/run.py (see there for the command line). Units: builders take millimetres,
Blender units are metres (MM = 0.001). World: x to the right, +y away from the user (toward the keyboard),
z up; the trackpad glass top is at z = Z_TOP mm, its centre at x = y = 0.
"""
import glob
import hashlib
import json
import math
import os
import re
import sys

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

import stamps

MM = 0.001
FPS = 30            # plates are rendered at 30 fps and conformed to the 60 fps film; a shot script may say FPS = 60
                    # (run.py sets it here before the shot is built) when its camera travels and has to stay smooth
HANDLE = 0.5        # seconds rendered past the end of the shot (it keeps playing under the crossfade)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
TIMELINE = os.path.join(ROOT, "timeline.json")

# colours that carry meaning, scene-linear (sRGB #FFB454, #6FD3FF, #A99BFF)
AMBER = (1.0, 0.457, 0.089)
BLUE = (0.159, 0.651, 1.0)
VIOLET = (0.397, 0.328, 1.0)
# world colour that comes out as the film's 2D background #0B0D10 through AgX "Medium High Contrast" (see NOTES.md)
BG_WORLD = (0.01057, 0.01172, 0.01423)

PUNCT = r"[\s，。、：；？！“”‘’（）《》·—…,.:;?!\"'()\-]"
DIGITS = "零一二三四五六七八九"


def argval(name, default=None):
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if name in argv:
        i = argv.index(name)
        return argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else True
    return default


# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ramp(t, t0, t1):
    """0 before t0, 1 after t1, linear in between."""
    if t1 == t0:
        return 1.0 if t >= t1 else 0.0
    return clamp((t - t0) / (t1 - t0))


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    return 1 - (1 - clamp(x)) ** 3


def ease_in(x):
    return clamp(x) ** 3


def ease_io(x):
    x = clamp(x)
    return 4 * x * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def lerp(a, b, k):
    return a + (b - a) * k


def vlerp(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(len(a)))


def ring(x, freq, decay):
    """Damped oscillation after an impulse at x = 0."""
    return 0.0 if x < 0 else math.exp(-decay * x) * math.sin(2 * math.pi * freq * x)


def click_step(x, rise=0.004, hold=0.012, fall=0.03):
    """Shape of the plate's sideways step over time x (s): quick out, short hold, spring back. Peak 1."""
    if x <= 0:
        return 0.0
    if x < rise:
        return smooth(x / rise)
    if x < rise + hold:
        return 1.0
    return max(0.0, 1.0 - smooth((x - rise - hold) / fall))


# ------------------------------------------------------------------ the clock
class Clock:
    """Narration anchors, same grammar as remotion/src/lib/time.ts:
    "3.04" line start · "3.04>" line end · "3.04@通电" word start · "3.04@通电>" word end · optional "+0.4"/"-0.2"."""

    asked = {}          # anchor -> film seconds: every moment anyone asked for in this run (see stamps.py)

    def __init__(self, path=TIMELINE):
        self.tl = json.load(open(path, encoding="utf8"))
        self.lines = {l["id"]: l for l in self.tl["lines"]}
        self.shots = {s["id"]: s for s in self.tl["shots"]}

    @staticmethod
    def _norm(s):
        s = re.sub(PUNCT, "", s)
        s = re.sub(r"\d", lambda m: DIGITS[int(m.group(0))], s)
        return s.lower()

    def abs(self, anchor):
        if isinstance(anchor, (int, float)):
            return float(anchor)
        m = re.match(r"^(\d+\.\d+)(?:@([^>+\-]+))?(>)?([+-]\d+(?:\.\d+)?)?$", anchor.strip())
        if not m:
            raise ValueError("bad anchor %r" % anchor)
        line = self.lines[m.group(1)]
        off = float(m.group(4)) if m.group(4) else 0.0
        if not m.group(2):
            t = (line["end"] if m.group(3) else line["start"]) + off
        else:
            want = self._norm(m.group(2))
            cs = "".join(c[0] for c in line["chars"])
            i = cs.find(want)
            if i < 0:
                raise ValueError("%r not in line %s: %s" % (m.group(2), m.group(1), line["text"]))
            t = (line["chars"][i + len(want) - 1][2] if m.group(3) else line["chars"][i][1]) + off
        Clock.asked[anchor.strip()] = t
        return t


class Ctx:
    def __init__(self, shot_id, res=(1920, 1080), samples=64):
        self.id = shot_id
        self.clock = Clock()
        self.shot = self.clock.shots[shot_id]
        self.start, self.end = self.shot["start"], self.shot["end"]
        self.dur = self.end - self.start
        self.n = int(math.ceil((self.dur + HANDLE) * FPS))
        self.res = res
        self.scene = setup_render(res, samples)
        self.scene.frame_start, self.scene.frame_end = 0, self.n - 1
        self.scene.render.fps = FPS
        self._anchors = {}
        self.cam = None

    def at(self, anchor):
        """Narration anchor -> seconds since this shot started."""
        return self.clock.abs(anchor) - self.start

    def line(self, lid):
        return self.clock.abs(lid) - self.start, self.clock.abs(lid + ">") - self.start

    # ---- anchors: named points whose screen position is exported for the 2D overlays
    def anchor(self, name, where):
        """where: an object (its origin), a tuple in mm (world), or a callable returning a world Vector in metres."""
        self._anchors[name] = where

    def anchors_now(self):
        sc, cam = self.scene, self.scene.camera
        bpy.context.view_layer.update()
        out = {}
        for name, w in self._anchors.items():
            if callable(w):
                p = Vector(w())
            elif isinstance(w, (tuple, list)):
                p = Vector(w) * MM
            else:
                p = w.matrix_world.translation.copy()
            v = world_to_camera_view(sc, cam, p)
            x, y = v.x * self.res[0], (1 - v.y) * self.res[1]
            vis = 1 if (0 <= v.x <= 1 and 0 <= v.y <= 1 and v.z > 0) else 0
            out[name] = [round(x, 1), round(y, 1), vis]
        return out


# ------------------------------------------------------------------ render settings (the house defaults)
def setup_render(res, samples=64):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    want = "METAL" if sys.platform == "darwin" else "OPTIX"
    prefs.compute_device_type = want
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == want
    c = sc.cycles
    c.device = "GPU"
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.02
    c.adaptive_min_samples = 16
    c.use_denoising = True
    try:
        c.denoiser = "OPENIMAGEDENOISE"
        c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
        c.denoising_prefilter = "ACCURATE"
        c.denoising_use_gpu = True
    except Exception as e:                      # older builds: keep the default
        print("denoise settings:", e)
    c.max_bounces = 8
    c.diffuse_bounces = 3
    c.glossy_bounces = 4
    c.transmission_bounces = 8
    c.transparent_max_bounces = 32
    c.seed = 7
    c.use_animated_seed = False
    c.sample_clamp_indirect = 8.0
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.use_motion_blur = False
    sc.render.use_persistent_data = not bool(argval("--no-persist"))   # keep static geometry between frames
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"
    sc.render.image_settings.compression = 15
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*BG_WORLD, 1)
    bg.inputs["Strength"].default_value = 1.0
    sc.world = w
    return sc


def world_color(rgb, strength=1.0):
    bg = bpy.context.scene.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*rgb, 1)
    bg.inputs["Strength"].default_value = strength


# ------------------------------------------------------------------ small builders
def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = Vector(loc) * MM
    if parent:
        e.parent = parent
    return e


def material(name, **kw):
    """Principled material; keyword names are the socket names, e.g. material("x", **{"Base Color": (..), "Roughness": .3})."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    for k, v in kw.items():
        b.inputs[k].default_value = v
    return m


def glow(name, color=BLUE, strength=4.0):
    """Pure emitter for the meaning colours (amber / blue / violet). Animate .strength through set_glow()."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.name = "EMIT"
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.name = "FADE"
    mix.inputs["Fac"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def set_glow(mat, strength=None, alpha=None, color=None):
    nt = mat.node_tree
    if strength is not None:
        nt.nodes["EMIT"].inputs["Strength"].default_value = strength
    if alpha is not None:
        nt.nodes["FADE"].inputs["Fac"].default_value = clamp(alpha)
    if color is not None:
        nt.nodes["EMIT"].inputs["Color"].default_value = (*color, 1)


def add_emission(mat, color, strength=0.0):
    """Give an existing Principled material an emission you can animate: returns a setter f(strength)."""
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = strength

    def setter(s, col=None):
        b.inputs["Emission Strength"].default_value = s
        if col is not None:
            b.inputs["Emission Color"].default_value = (*col, 1)
    return setter


def area(name, loc, target, size, energy, color=(1, 1, 1), size_y=None, spread=180.0):
    """Area light. loc / target / size in mm, energy in watts."""
    li = bpy.data.lights.new(name, "AREA")
    li.energy = energy
    li.color = color
    li.shape = "RECTANGLE" if size_y else "SQUARE"
    li.size = size * MM
    if size_y:
        li.size_y = size_y * MM
    li.spread = math.radians(spread)
    ob = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = Vector(loc) * MM
    d = Vector(target) * MM - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


def floor(z=-12.0, size=6000.0, color=(0.006, 0.006, 0.007), rough=0.22):
    """Glossy near-black stage floor at height z (mm)."""
    m = material("stage_floor", **{"Base Color": (*color, 1), "Roughness": rough, "Coat Weight": 0.2, "Coat Roughness": 0.08})
    bpy.ops.mesh.primitive_plane_add(size=size * MM, location=(0, 0, z * MM))
    ob = bpy.context.active_object
    ob.data.materials.append(m)
    return ob


# ------------------------------------------------------------------ camera
class Rig:
    """A camera you place every frame by what it should frame.

        rig = Rig(ctx, lens=100, fstop=11)
        rig.frame(target=(x, y, z), direction=(dx, dy, dz), width=60, focus=None)   # all mm

    target: the point at the centre of the picture. direction: from the target toward the camera.
    width: how many millimetres of the world fill the frame horizontally at the target's distance.
    """

    def __init__(self, ctx, lens=85.0, fstop=None, sensor=36.0, clip=(0.002, 50.0)):
        cam = bpy.data.cameras.new("cam")
        cam.lens = lens
        cam.sensor_width = sensor
        cam.clip_start, cam.clip_end = clip
        self.ob = bpy.data.objects.new("cam", cam)
        bpy.context.scene.collection.objects.link(self.ob)
        self.focus = bpy.data.objects.new("focus", None)
        bpy.context.scene.collection.objects.link(self.focus)
        if fstop:
            cam.dof.use_dof = True
            cam.dof.aperture_fstop = fstop
            cam.dof.focus_object = self.focus
        ctx.scene.camera = self.ob
        ctx.cam = self.ob
        self.cam = cam

    def frame(self, target, direction, width, focus=None, lens=None, fstop=None, roll=0.0):
        if lens:
            self.cam.lens = lens
        if fstop:
            self.cam.dof.aperture_fstop = fstop
        dist = width * self.cam.lens / self.cam.sensor_width
        loc = Vector(target) + Vector(direction).normalized() * dist
        self.ob.location = loc * MM
        d = (Vector(target) - loc)
        q = d.to_track_quat("-Z", "Y" if abs(d.normalized().z) < 0.999 else "Y")
        self.ob.rotation_euler = q.to_euler()
        if roll:
            self.ob.rotation_euler.rotate_axis("Z", math.radians(roll))
        self.focus.location = Vector(focus if focus else target) * MM

    def place(self, loc, look, lens=None, focus=None, fstop=None, roll=0.0):
        """Put the camera at loc (mm), aimed at look (mm). For moves that are drawn as a path of positions."""
        if lens:
            self.cam.lens = lens
        if fstop:
            self.cam.dof.aperture_fstop = fstop
        self.ob.location = Vector(loc) * MM
        d = Vector(look) - Vector(loc)
        self.ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        if roll:
            self.ob.rotation_euler.rotate_axis("Z", math.radians(roll))
        self.focus.location = Vector(focus if focus else look) * MM

    def ortho(self, target, direction, width, up="Y"):
        """Orthographic framing, for schematic views."""
        self.cam.type = "ORTHO"
        self.cam.ortho_scale = width * MM
        loc = Vector(target) + Vector(direction).normalized() * 500.0
        self.ob.location = loc * MM
        d = (Vector(target) - loc)
        self.ob.rotation_euler = d.to_track_quat("-Z", up).to_euler()
        self.focus.location = Vector(target) * MM


# ------------------------------------------------------------------ the render loop
def _key_camera(ctx, at_frame, f):
    """Key the camera's pose at f - 0.5, f and f + 0.5 (linear), which is what Cycles reads for motion blur."""
    cam = ctx.scene.camera
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    prev = None
    for df in (-0.5, 0.0, 0.5):
        at_frame((f + df) / FPS, f)
        if prev is not None:
            e = cam.rotation_euler.copy()
            e.make_compatible(prev)
            cam.rotation_euler = e
        prev = cam.rotation_euler.copy()
        cam.keyframe_insert("location", frame=f + df)
        cam.keyframe_insert("rotation_euler", frame=f + df)


def _signature(ctx, names):
    """The code a shot's frames depend on: its script, what that borrows from shots/, the modules of lib/ it has
    loaded (call this after setup) and the options of the run. The timing is kept beside it, see stamps.py."""
    paths = [os.path.join(ROOT, "shots", n + ".py") for n in set(names)]
    paths += [getattr(m, "__file__", None) or "" for m in list(sys.modules.values())]
    opts = stamps.options(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    ctx._sig_in = (ROOT, paths, opts)
    return stamps.code_signature(ROOT, paths, opts)


def _old_stamp_ok(ctx, old, outdir, name):
    """A stamp from before stamps.py. Its signature is recomputed the old way, with the run's options and with the
    extra ones named in --stamp-alts "+camblur|+camblur +blur-f1 112" (the run that made the frames may have had
    them; + stands for --). With --adopt, frames whose
    signature can no longer be recomputed are kept if nothing has moved since and every frame is newer than the code
    it depends on. Returns the options the frames were made with, or None."""
    root, paths, opts = ctx._sig_in
    if old.get("v") == 2 or abs(old.get("start", -1e9) - ctx.start) > 1e-3 or old.get("n") != ctx.n:
        return None
    alts = [opts] + [opts + " " + a.strip().replace("+", "--") for a in str(argval("--stamp-alts", "")).split("|") if a.strip()]
    for o in alts:
        if stamps.legacy_signature(root, paths, o, ctx.start, ctx.n) == old.get("sig"):
            return o
    frames = glob.glob(os.path.join(outdir, name + "_[0-9][0-9][0-9][0-9].png"))
    if argval("--adopt") and len(frames) == ctx.n:
        code = [os.path.getmtime(p) for rel, p in stamps._files(root, paths) if rel != os.path.join("lib", "shotkit.py")]
        if max(code) < min(os.path.getmtime(p) for p in frames):
            return opts
    return None


def run(shot_id, setup):
    res = tuple(int(v) for v in str(argval("--res", "1920x1080")).split("x"))
    samples = int(argval("--samples", "64"))
    if argval("--draft"):
        res = (res[0] // 2, res[1] // 2)
        samples = min(samples, 24)
    name = str(argval("--module", shot_id))            # a sub-shot (--shot S109 --module S109b) keeps its own files
    # drafts go to their own folder: a half-size frame left under the production name would be skipped on resume
    outdir = argval("--out", os.path.join(ROOT, "out", name + ("_draft" if argval("--draft") else "")))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ctx = Ctx(shot_id, res, samples)
    if argval("--thr"):
        ctx.scene.cycles.adaptive_threshold = float(argval("--thr"))
    at_frame = setup(ctx)
    assert ctx.scene.camera is not None, "the shot did not set a camera"
    os.makedirs(outdir, exist_ok=True)
    still = argval("--still")
    # Frames of an earlier run are reused only while nothing they depend on has changed (a preview once mixed frames
    # of two timings: the shot had been moved and the old frames were taken for finished ones).
    sig, old = _signature(ctx, (shot_id, name)), stamps.read(outdir)
    fresh, why = stamps.check(old, sig, FPS, ctx.start, ctx.dur, ctx.n, ctx.clock.abs)
    mine = [os.path.join(outdir, x) for x in os.listdir(outdir) if re.match(re.escape(name) + r"_\d{4}\.png$", x)]
    if not fresh and old and old.get("v") != 2:
        made_with = _old_stamp_ok(ctx, old, outdir, name)
        if made_with is not None:                      # an old stamp that still holds: rewrite it in the new form
            root, paths, opts = ctx._sig_in
            stamps.write(outdir, stamps.make(stamps.code_signature(root, paths, made_with), FPS, ctx.start, ctx.dur,
                                             ctx.n, made_with, Clock.asked))
            fresh = made_with == opts                  # frames made with other options are not this run's frames
            why = "old stamp renewed; the frames were made with: " + made_with
    if argval("--stamp-only"):
        print("STAMP %s: %s (%s)" % (name, "fresh" if fresh else "stale", why), flush=True)
        return
    if not still and not argval("--anchors-only"):
        if not fresh:
            if mine:
                print("STALE: the frames in %s are not what this run would render (%s); rendering them again" % (outdir, why), flush=True)
            for p in mine:                              # gone first: a run that stops half way must not leave old
                os.remove(p)                            # frames behind under a new stamp
            stamps.write(outdir, stamps.make(sig, FPS, ctx.start, ctx.dur, ctx.n, ctx._sig_in[2], Clock.asked))
        else:
            for p in mine:                              # the shot got a frame or two shorter
                if int(p[-8:-4]) >= ctx.n:
                    os.remove(p)
    if still:
        frames = [int(v) for v in str(still).split(",")]
    else:
        frames = list(range(int(argval("--f0", 0)), int(argval("--f1", ctx.n - 1)) + 1))
    frames = [f for f in frames if 0 <= f < ctx.n]
    anchors_only = bool(argval("--anchors-only"))
    if anchors_only:
        frames = list(range(ctx.n))
    # motion blur for fast camera moves: --camblur [shutter, default 0.5] keys the camera half a frame either side of
    # each frame so that Cycles can blur it (everything is posed by hand here, there are no f-curves otherwise).
    # --blur-f0 / --blur-f1 limit it to a range of frames. Only the camera blurs, not the objects.
    cb = argval("--camblur")
    shutter = 0.0 if (not cb or anchors_only) else (0.5 if cb is True else float(cb))
    bf0, bf1 = int(argval("--blur-f0", "0")), int(argval("--blur-f1", "999999"))
    apath = os.path.join(ROOT, "anchors", name + ".json")
    rec = {}
    if os.path.exists(apath) and not anchors_only:
        old = json.load(open(apath, encoding="utf8"))
        if old.get("n") == ctx.n and old.get("width") == 1920:
            rec = {fr["f"]: fr["anchors"] for fr in old["frames"]}
    print("SHOT %s: %.2f s -> %d frames at %d fps; rendering %d frame(s) at %dx%d, %d spp"
          % (shot_id, ctx.dur, ctx.n, FPS, 0 if anchors_only else len(frames), res[0], res[1], samples), flush=True)
    for f in frames:
        path = os.path.join(outdir, "%s_%04d.png" % (name, f))
        done = fresh and os.path.exists(path) and not still and not anchors_only
        if done and (not ctx._anchors or f in rec):
            continue
        ctx.scene.frame_set(f)
        blurred = shutter > 0 and bf0 <= f <= bf1 and not done
        ctx.scene.camera.animation_data_clear()
        if blurred:
            _key_camera(ctx, at_frame, f)
        at_frame(f / FPS, f)
        ctx.scene.render.use_motion_blur = blurred
        ctx.scene.render.motion_blur_shutter = shutter or 0.5
        if ctx._anchors:
            a = ctx.anchors_now()
            sx, sy = 1920.0 / res[0], 1080.0 / res[1]
            rec[f] = {k: [round(v[0] * sx, 1), round(v[1] * sy, 1), v[2]] for k, v in a.items()}
        if anchors_only or done:                       # a resumed frame still needs its anchors
            continue
        ctx.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print("WROTE", path, flush=True)
    if ctx._anchors and (anchors_only or not still):
        os.makedirs(os.path.dirname(apath), exist_ok=True)
        json.dump({"fps": FPS, "width": 1920, "height": 1080, "shot": name, "n": ctx.n,
                   "frames": [{"f": f, "anchors": rec[f]} for f in sorted(rec)]},
                  open(apath, "w", encoding="utf8"))
        print("ANCHORS", apath, len(rec), "frames", flush=True)
