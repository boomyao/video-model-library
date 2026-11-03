import bpy
from .shots import SHOTS, ASSEMBLY
from . import cutaway
from .gn import set_mod_input

SHOWCASES = ['Showcase_Thermal', 'Showcase_Chip', 'Showcase_Blower', 'Showcase_FootSection']


def find_layer_collection(lc, name):
    if lc.collection.name == name:
        return lc
    for ch in lc.children:
        r = find_layer_collection(ch, name)
        if r is not None:
            return r
    return None


def set_excluded(name, excluded, view_layer=None):
    vl = view_layer or bpy.context.view_layer
    lc = find_layer_collection(vl.layer_collection, name)
    if lc is not None:
        lc.exclude = excluded


def setup_render(scene, samples=512, res=(1920, 1080), percent=100):
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = percent
    scene.render.film_transparent = False
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.008
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
        scene.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
        scene.cycles.denoising_prefilter = 'ACCURATE'
        scene.cycles.denoising_use_gpu = True
    except Exception:
        pass
    scene.cycles.max_bounces = 16
    scene.cycles.diffuse_bounces = 6
    scene.cycles.glossy_bounces = 10
    scene.cycles.transmission_bounces = 8
    scene.cycles.transparent_max_bounces = 8
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.cycles.sample_clamp_indirect = 8.0
    scene.cycles.blur_glossy = 0.5
    scene.view_settings.view_transform = 'AgX'
    from .lights import LOOK
    scene.view_settings.look = LOOK
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.display_settings.display_device = 'sRGB'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '16'
    scene.render.use_persistent_data = False


def apply_shot(name, scene=None):
    scene = scene or bpy.context.scene
    sh = SHOTS[name]
    show = sh.get('show', 'assembly')
    for c in ASSEMBLY:
        set_excluded(c, show != 'assembly')
    for c in SHOWCASES:
        set_excluded(c, True)
    if show == 'showcase_thermal':
        set_excluded('Showcase_Thermal', False)
    elif show == 'showcase_chip':
        set_excluded('Showcase_Chip', False)
    elif show == 'showcase_blower':
        set_excluded('Showcase_Blower', False)
    var = sh.get('variant', 'ultra')
    if show == 'assembly':
        set_excluded('Thermal_Ultra', var == 'max')
        set_excluded('Thermal_Max', var != 'max')
    if show == 'assembly':
        set_excluded('SoC_Max_Variant', var != 'max')
        set_excluded('SoC_Ultra_Variant', var == 'max')
    else:
        set_excluded('SoC_Max_Variant', True)
        set_excluded('SoC_Ultra_Variant', True)
    rig = sh.get('rig', 'dark')
    set_excluded('Lights_Dark', rig != 'dark')
    set_excluded('Lights_Light', rig != 'light')
    extra = sh.get('extra_lights', [])
    if isinstance(extra, str):
        extra = [extra]
    for key in ('foot', 'cut', 'thermal', 'chip', 'blower'):
        set_excluded('Lights_Extra_' + key.capitalize(), key not in extra)
    all_hidden = set()
    for other in SHOTS.values():
        all_hidden.update(other.get('hide', []))
    for n in all_hidden:
        o = bpy.data.objects.get(n)
        if o is not None:
            o.hide_render = n in sh.get('hide', [])
    w = bpy.data.worlds.get('World_Dark' if rig == 'dark' else 'World_Light')
    if w is not None:
        scene.world = w
    ctrl = bpy.data.objects.get('EXPLODE_CTRL')
    if ctrl is not None:
        ctrl['explode'] = float(sh.get('explode', 0.0))
    cutaway.set_cuts(sh.get('cut', []))
    cov = bpy.data.objects.get('Bottom_Cover')
    if cov is not None:
        for m in cov.modifiers:
            if m.type == 'NODES' and m.name == 'Angled_Holes':
                set_mod_input(m, 'Hole Segments', int(sh.get('hole_segments', 16)))
    cam = bpy.data.objects.get('CAM_' + name)
    if cam is not None:
        scene.camera = cam
    setup_render(scene, samples=sh.get('samples', 512))
    bpy.context.view_layer.update()
    return sh
