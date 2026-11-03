# -*- coding: utf-8 -*-
"""棚：世界、灯光、材质、相机、渲染设置。1 Blender 单位 = 1 mm。

    import studio
    studio.setup(samples=256)                      # 清空场景，设好渲染、色彩和世界（背景正好是 #08090B）
    studio.camera(studio.orbit((0,0,10), 150, -60, 25), (0,0,10), lens=100, fstop=40)   # 位置、目标、焦距、真实光圈（可选）
    studio.rig(target=(0,0,10), scale=40)          # 标准布光：左上方柔和主光 + 偏冷轮廓光，scale 是主体大小（mm）
    studio.card('反光板', loc, target, w, h, 亮度)   # 只出现在反射里的板，金属和光滑塑料靠它出层次
    studio.floor(0, gloss=0.35)                    # 黑色桌面，往外融进背景（床上的镜头不用它）
    mat = studio.plastic()                         # 红色 PLA；还有 brass / steel / aluminium / black_anodized / rubber / ...

景深按真实光圈算（fstop 就是 f 值）。100 mm 镜头离主体 60 mm、1080p 时，f/56 每离焦 1 mm 糊约 2.5 像素，要看清层纹用 f/80 到 f/110。
显示变换用 Khronos PBR Neutral：照度 1 的受光面在屏幕上就是材质写的颜色（RED_HEX = #C8421F）。它的暗部很陡，桌面、床面稍微反光就发灰。
"""
import math
import os

import numpy as np
import bpy
from mathutils import Vector

VARS = {}       # 渲染.py --var 传进来的
OVERRIDE = {}   # 渲染.py --samples/--res 传进来的


def var(key, default=None, cast=None):
    v = VARS.get(key, default)
    if cast is None and default is not None and key in VARS:
        cast = type(default)
    return cast(v) if cast else v


def srgb(hexcolor):
    """'#C8421F' → 线性 RGB。"""
    h = hexcolor.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c)


BG_HEX = '#08090B'
RED_HEX = '#C8421F'
RED_MARK = '#E5482A'
CYAN_MARK = '#56C8E8'
YELLOW_MARK = '#FFD640'
WHITE_MARK = '#F2F2F2'


# ---------- 场景 ----------
def setup(samples=256, res=(1920, 1080), fps=30, denoise=True, view='Khronos PBR Neutral', look='None'):
    """清空场景，设好单位、渲染器、色彩和世界。"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 0.001
    scene.unit_settings.length_unit = 'MILLIMETERS'
    r = scene.render
    r.engine = 'CYCLES'
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = 100
    r.fps = fps
    r.film_transparent = False
    r.use_persistent_data = True
    r.dither_intensity = 1.0
    c = scene.cycles
    c.device = 'GPU'
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.006
    c.adaptive_min_samples = 32
    c.seed = 1
    c.use_animated_seed = False
    c.use_denoising = denoise
    c.denoiser = 'OPENIMAGEDENOISE'
    c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    c.denoising_prefilter = 'ACCURATE'
    c.denoising_use_gpu = True
    c.max_bounces = 10
    c.diffuse_bounces = 5
    c.glossy_bounces = 6
    c.transmission_bounces = 6
    c.volume_bounces = 0
    c.transparent_max_bounces = 8
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.blur_glossy = 0.3
    c.sample_clamp_indirect = 8.0
    c.sample_clamp_direct = 0.0
    c.light_sampling_threshold = 0.005
    c.texture_limit = 'OFF'
    scene.display_settings.display_device = 'sRGB'
    scene.view_settings.view_transform = view
    scene.view_settings.look = look
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    enable_gpu()
    world()
    return scene


def enable_gpu():
    """渲染机用 OptiX，本机（Mac）用 Metal，都没有就退回 CPU。"""
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for dev in ('OPTIX', 'METAL'):
        try:
            prefs.compute_device_type = dev
        except TypeError:
            continue
        prefs.get_devices()
        found = [d for d in prefs.devices if d.type == dev]
        if found:
            for d in prefs.devices:
                d.use = d.type == dev
            print('[studio] 设备', dev, [d.name for d in found])
            return dev
    bpy.context.scene.cycles.device = 'CPU'
    print('[studio] 没有 GPU，用 CPU')
    return 'CPU'


def apply_override():
    scene = bpy.context.scene
    if 'samples' in OVERRIDE:
        scene.cycles.samples = OVERRIDE['samples']
    if 'res' in OVERRIDE:
        scene.render.resolution_x, scene.render.resolution_y = OVERRIDE['res']


def _pbr_neutral_inverse(rgb):
    """Khronos PBR Neutral 暗部有一个偏移。算出屏幕上要得到 rgb（线性）时世界该发多亮。"""
    m = min(rgb)
    x = math.sqrt(m / 6.25)
    x = min(x, 0.08)
    offset = x - 6.25 * x * x
    return tuple(c + offset for c in rgb)


def world(ambient=0.02, glossy_top=0.10, glossy_bottom=0.008):
    """世界：相机直接看到的是背景色 #08090B；给漫反射一点点环境，给金属反射一个上亮下暗的渐变，
    否则金属在黑棚里只剩一片黑。"""
    w = bpy.data.worlds.new('棚')
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    path = nt.nodes.new('ShaderNodeLightPath')
    view = bpy.context.scene.view_settings.view_transform
    bgc = srgb(BG_HEX)
    if view == 'Khronos PBR Neutral':
        bgc = _pbr_neutral_inverse(bgc)
    # 相机光线 → 背景色；光泽反射 → 渐变；其他 → 低环境
    cam = nt.nodes.new('ShaderNodeRGB')
    cam.outputs[0].default_value = (*bgc, 1)
    amb = nt.nodes.new('ShaderNodeRGB')
    amb.outputs[0].default_value = (ambient, ambient * 1.02, ambient * 1.06, 1)
    tex = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tex.outputs['Generated'], sep.inputs[0])
    rmp = nt.nodes.new('ShaderNodeMapRange')
    rmp.inputs['From Min'].default_value = -0.2
    rmp.inputs['From Max'].default_value = 1.0
    rmp.inputs['To Min'].default_value = glossy_bottom
    rmp.inputs['To Max'].default_value = glossy_top
    rmp.interpolation_type = 'SMOOTHSTEP'
    nt.links.new(sep.outputs['Z'], rmp.inputs['Value'])
    gl = nt.nodes.new('ShaderNodeCombineColor')
    for i, k in enumerate((1.0, 1.02, 1.07)):
        mm = nt.nodes.new('ShaderNodeMath')
        mm.operation = 'MULTIPLY'
        mm.inputs[1].default_value = k
        nt.links.new(rmp.outputs[0], mm.inputs[0])
        nt.links.new(mm.outputs[0], gl.inputs[i])
    mix1 = nt.nodes.new('ShaderNodeMix')
    mix1.data_type = 'RGBA'
    nt.links.new(path.outputs['Is Glossy Ray'], mix1.inputs['Factor'])
    nt.links.new(amb.outputs[0], mix1.inputs['A'])
    nt.links.new(gl.outputs[0], mix1.inputs['B'])
    mix2 = nt.nodes.new('ShaderNodeMix')
    mix2.data_type = 'RGBA'
    nt.links.new(path.outputs['Is Camera Ray'], mix2.inputs['Factor'])
    nt.links.new(mix1.outputs['Result'], mix2.inputs['A'])
    nt.links.new(cam.outputs[0], mix2.inputs['B'])
    nt.links.new(mix2.outputs['Result'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.0
    nt.links.new(bg.outputs[0], out.inputs['Surface'])
    return w


# ---------- 相机 ----------
def look_at(ob, target, roll=0.0):
    loc = Vector(ob.location)
    d = Vector(target) - loc
    q = d.to_track_quat('-Z', 'Y')
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = q
    if roll:
        from mathutils import Quaternion
        ob.rotation_quaternion = q @ Quaternion((0, 0, 1), math.radians(roll))


def camera(loc, target, lens=50.0, sensor=36.0, fstop=None, focus=None, roll=0.0, name='相机'):
    """loc、target 单位 mm。fstop 是真实光圈值（景深按真实尺度算，macro 下很浅）。focus 默认对到 target。"""
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.sensor_width = sensor
    cam.clip_start = 1.0
    cam.clip_end = 100000.0
    ob = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    look_at(ob, target, roll)
    bpy.context.scene.camera = ob
    set_dof(ob, fstop, focus if focus is not None else target)
    return ob


def orbit(target, dist, az, el):
    """以 target 为中心的相机位置。az 是方位角（度，-90 在 -Y 方向，也就是正前方），el 是仰角（度）。"""
    a, e = math.radians(az), math.radians(el)
    return (target[0] + dist * math.cos(e) * math.cos(a), target[1] + dist * math.cos(e) * math.sin(a), target[2] + dist * math.sin(e))


def set_dof(ob, fstop, focus):
    """Cycles 算光圈时不看单位比例：光圈直径 = 焦距(mm)×0.001/f 单位。这里 1 单位 = 1 mm，所以 f 值要乘 0.001。"""
    cam = ob.data
    if fstop is None:
        cam.dof.use_dof = False
        return
    cam.dof.use_dof = True
    cam.dof.aperture_fstop = fstop * 0.001
    cam.dof.aperture_blades = 7
    cam.dof.aperture_rotation = math.radians(15)
    if isinstance(focus, (int, float)):
        cam.dof.focus_distance = focus
    else:
        fwd = (ob.rotation_quaternion @ Vector((0, 0, -1))) if ob.rotation_mode == 'QUATERNION' else (ob.matrix_world.to_3x3() @ Vector((0, 0, -1)))
        cam.dof.focus_distance = max((Vector(focus) - Vector(ob.location)).dot(fwd), 0.1)


# ---------- 灯光 ----------
def area_light(name, loc, target, size, radiance, color=(1, 1, 1), size_y=None, spread=None):
    """矩形面光。radiance 是灯面看起来有多亮（和距离、灯的大小无关），调灯更直观。"""
    li = bpy.data.lights.new(name, 'AREA')
    li.shape = 'RECTANGLE'
    li.size = size
    li.size_y = size_y if size_y is not None else size
    area = li.size * li.size_y
    li.energy = radiance * area * 4.0
    li.color = color
    if spread is not None:
        li.spread = math.radians(spread)
    li.use_shadow = True
    ob = bpy.data.objects.new(name, li)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    look_at(ob, target)
    return ob


def blackbody(k):
    """色温 → 线性 RGB（近似，亮度归一）。"""
    t = k / 100.0
    r = 255 if t <= 66 else 329.698727446 * ((t - 60) ** -0.1332047592)
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * ((t - 60) ** -0.0755148492)
    b = 255 if t >= 66 else (0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)
    c = [min(max(x, 0), 255) / 255 for x in (r, g, b)]
    c = [(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c]
    m = max(c)
    return tuple(x / m for x in c)


def card(name, loc, target, w, h, radiance, color=(1, 1, 1), gradient=None, feather=0.25, one_sided=False):
    """反光板：只出现在反射里（金属靠它出层次），相机看不到，不挡光，也不照亮漫反射。

    gradient=(a,b)：沿 h 方向从 a 到 b 的亮度倍数。feather：四边渐隐的宽度比例，反射里的板边不会是硬线。
    """
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)], [], [(0, 1, 2, 3)])
    me.update()
    uv = me.uv_layers.new(name='UV')
    uv.uv.foreach_set('vector', [0, 0, 1, 0, 1, 1, 0, 1])
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (*color, 1)
    uvn = nt.nodes.new('ShaderNodeUVMap')
    uvn.uv_map = 'UV'
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(uvn.outputs['UV'], sep.inputs[0])
    level = radiance
    if gradient:
        rr = nt.nodes.new('ShaderNodeMapRange')
        rr.interpolation_type = 'SMOOTHSTEP'
        rr.inputs['To Min'].default_value = radiance * gradient[0]
        rr.inputs['To Max'].default_value = radiance * gradient[1]
        nt.links.new(sep.outputs['Y'], rr.inputs['Value'])
        level = rr.outputs[0]

    def edge(v):
        """0 到 1 的坐标 → 四边渐隐。"""
        a = nt.nodes.new('ShaderNodeMapRange')
        a.interpolation_type = 'SMOOTHSTEP'
        a.inputs['From Min'].default_value = 0.0
        a.inputs['From Max'].default_value = max(feather, 1e-3)
        nt.links.new(v, a.inputs['Value'])
        b = nt.nodes.new('ShaderNodeMapRange')
        b.interpolation_type = 'SMOOTHSTEP'
        b.inputs['From Min'].default_value = 1.0
        b.inputs['From Max'].default_value = 1.0 - max(feather, 1e-3)
        nt.links.new(v, b.inputs['Value'])
        return _math(nt, 'MULTIPLY', a.outputs[0], b.outputs[0])
    fall = _math(nt, 'MULTIPLY', edge(sep.outputs['X']), edge(sep.outputs['Y']))
    if one_sided:
        # 只有朝 target 的那一面发光。贴着床放时，床面就不会把它反射出来
        fall = _math(nt, 'MULTIPLY', fall, nt.nodes.new('ShaderNodeNewGeometry').outputs['Backfacing'])
    nt.links.new(_math(nt, 'MULTIPLY', level, fall), em.inputs['Strength'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    look_at(ob, target)
    ob.visible_camera = False
    ob.visible_shadow = False
    ob.visible_diffuse = False
    ob.visible_transmission = False
    ob.visible_volume_scatter = False
    return ob


def rig(target=(0, 0, 0), scale=40.0, key=1.0, rim=1.0, fill=1.0, soft=0.55, key_dir=(-0.75, -0.55, 1.0), rim_dir=(0.8, 1.0, 0.55)):
    """标准布光：主光柔和、左上方；一道偏冷的轮廓光从右后方来；再加一块很暗的补光。

    scale 是主体大小（mm）。灯离主体的距离和灯的大小都随 scale 走，换主体大小不用重调亮度。
    soft 是主光的软硬：灯越小、灯面越亮（照度不变），塑料线上的高光越清楚。1 很软，0.4 偏硬。
    """
    t = Vector(target)
    kd = Vector(key_dir).normalized()
    rd = Vector(rim_dir).normalized()
    out = {}
    out['key'] = area_light('主光', t + kd * scale * 3.2, t, scale * 3.0 * soft, 3.6 * key / (soft * soft), blackbody(6000))
    out['rim'] = area_light('轮廓光', t + rd * scale * 3.5, t, scale * 2.2, 14.0 * rim, blackbody(8000), size_y=scale * 0.7)
    fd = Vector((0.9, -0.8, 0.15)).normalized()
    out['fill'] = area_light('补光', t + fd * scale * 4.0, t, scale * 4.0, 0.35 * fill, blackbody(6500))
    return out


# ---------- 材质 ----------
def _mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs['Surface'])
    return m, nt, b


def _math(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new('ShaderNodeMath')
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _noise(nt, vec=None, scale=1.0, detail=2.0, rough=0.5, w=None):
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = rough
    if vec is not None:
        nt.links.new(vec, n.inputs['Vector'])
    return n.outputs['Fac']


def _mix_val(nt, fac, a, b):
    n = nt.nodes.new('ShaderNodeMix')
    n.data_type = 'FLOAT'
    n.clamp_factor = True
    if isinstance(fac, (int, float)):
        n.inputs['Factor'].default_value = fac
    else:
        nt.links.new(fac, n.inputs['Factor'])
    for key, v in (('A', a), ('B', b)):
        if isinstance(v, (int, float)):
            n.inputs[key].default_value = v
        else:
            nt.links.new(v, n.inputs[key])
    return n.outputs['Result']


def _mix_rgb(nt, fac, a, b, blend='MIX'):
    n = nt.nodes.new('ShaderNodeMix')
    n.data_type = 'RGBA'
    n.blend_type = blend
    n.clamp_factor = True
    if isinstance(fac, (int, float)):
        n.inputs['Factor'].default_value = fac
    else:
        nt.links.new(fac, n.inputs['Factor'])
    for key, v in (('A', a), ('B', b)):
        if isinstance(v, (tuple, list)):
            n.inputs[key].default_value = (*v[:3], 1)
        else:
            nt.links.new(v, n.inputs[key])
    return n.outputs['Result']


def plastic(color=RED_HEX, sss='BURLEY', roughness=0.37, sss_scale=0.19, weight=1.0, bump=1.0, spec=0.55, glow=0.10, name='PLA'):
    """红色哑光 PLA。依赖 cube.py 写的 UV（u 沿线、v 沿截面，单位 mm）和属性 line_rand、fresh。

    fresh=1 的地方（刚挤出来的线）更润、更透。
    """
    m, nt, b = _mat(name)
    b.subsurface_method = sss
    base = srgb(color) if isinstance(color, str) else color
    if bpy.context.scene.view_settings.view_transform == 'Khronos PBR Neutral':
        # 这个显示变换会压暗低的通道。补偿之后，受光面（照度 1）在屏幕上就是约定的颜色
        base = _pbr_neutral_inverse(base)
    uvn = nt.nodes.new('ShaderNodeUVMap')
    uvn.uv_map = 'UV'
    rnd = nt.nodes.new('ShaderNodeAttribute')
    rnd.attribute_name = 'line_rand'
    fresh = nt.nodes.new('ShaderNodeAttribute')
    fresh.attribute_name = 'fresh'
    fr = fresh.outputs['Fac']
    # 把 UV 拉成沿线方向很长的噪声坐标：沿线 0.4 mm 一个起伏，横向 0.03 mm 一个起伏
    def stretched(fu, fv, off):
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (fu, fv, 1)
        nt.links.new(uvn.outputs['UV'], mp.inputs['Vector'])
        add = nt.nodes.new('ShaderNodeVectorMath')
        add.operation = 'ADD'
        nt.links.new(mp.outputs[0], add.inputs[0])
        cmb = nt.nodes.new('ShaderNodeCombineXYZ')
        nt.links.new(_math(nt, 'MULTIPLY', rnd.outputs['Fac'], off), cmb.inputs['Z'])
        nt.links.new(cmb.outputs[0], add.inputs[1])
        return add.outputs[0]
    streak = _noise(nt, stretched(0.9, 26.0, 53.0), detail=2.0, rough=0.5)
    streak2 = _noise(nt, stretched(0.28, 7.0, 91.0), detail=2.0, rough=0.5)
    pore = _noise(nt, stretched(3.0, 3.0, 17.0), detail=1.0, rough=0.5)
    # 粗糙度：基值 + 沿线条纹 + 每根线一点差别；新鲜线很光
    rg = _math(nt, 'ADD', roughness, _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', streak, 0.5), 0.26))
    # 每根线的光泽不一样，真实墙面上有的层亮、有的层暗
    rg = _math(nt, 'ADD', rg, _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', rnd.outputs['Fac'], 0.5), 0.20))
    rg = _mix_val(nt, _math(nt, 'MULTIPLY', fr, 1.6, clamp=True), rg, 0.05)
    nt.links.new(rg, b.inputs['Roughness'])
    # 刚挤出来的线：高光更强、颜色更透，再加一点点暖色自发光（很弱，只为让它在暗处也读得出来）
    nt.links.new(_mix_val(nt, fr, spec, 1.0), b.inputs['Specular IOR Level'])
    b.inputs['Emission Color'].default_value = (1.0, 0.16, 0.03, 1)
    nt.links.new(_math(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', fr, fr), glow), b.inputs['Emission Strength'])
    # 颜色：几乎不变，只有很轻的沿线明暗
    ca = _mix_rgb(nt, _math(nt, 'MULTIPLY', streak2, 0.4), base, tuple(c * 0.90 for c in base))
    cb = _mix_rgb(nt, fr, ca, tuple(min(c * 1.25, 1) for c in base))
    nt.links.new(cb, b.inputs['Base Color'])
    b.inputs['Subsurface Weight'].default_value = weight
    b.inputs['Subsurface Radius'].default_value = (1.0, 0.22, 0.10)
    nt.links.new(_mix_val(nt, fr, sss_scale, sss_scale * 2.0), b.inputs['Subsurface Scale'])
    b.inputs['IOR'].default_value = 1.46
    # 微起伏
    h = _math(nt, 'ADD', _math(nt, 'MULTIPLY', streak, 0.25), _math(nt, 'MULTIPLY', pore, 0.5))
    h = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', streak2, 1.0))
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Distance'].default_value = 0.006 * bump
    bp.inputs['Strength'].default_value = 1.0
    nt.links.new(_mix_val(nt, fr, h, 0.5), bp.inputs['Height'])
    nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return m


def floor(z=0.0, radius=120.0, gloss=0.0, name='桌面'):
    """很暗的桌面：往外融进背景色，看不到地平线。gloss 大于 0 时像黑色亚克力，物体下面有一层淡淡的倒影（0.2 到 0.5 合适）。

    这个显示变换的暗部很敏感，桌面稍微反一点光就发灰，所以默认几乎不反光。
    """
    size = radius * 8
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-size, -size, z), (size, -size, z), (size, size, z), (-size, size, z)], [], [(0, 1, 2, 3)])
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    m, nt, b = _mat(name)
    b.inputs['Base Color'].default_value = (0.0022, 0.0023, 0.0026, 1)
    b.inputs['Roughness'].default_value = 0.22 if gloss > 0 else 0.6
    b.inputs['Specular IOR Level'].default_value = gloss
    tex = nt.nodes.new('ShaderNodeTexCoord')
    vl = nt.nodes.new('ShaderNodeVectorMath')
    vl.operation = 'LENGTH'
    nt.links.new(tex.outputs['Object'], vl.inputs[0])
    rmp = nt.nodes.new('ShaderNodeMapRange')
    rmp.inputs['From Min'].default_value = radius * 0.35
    rmp.inputs['From Max'].default_value = radius
    rmp.interpolation_type = 'SMOOTHSTEP'
    nt.links.new(vl.outputs['Value'], rmp.inputs['Value'])
    em = nt.nodes.new('ShaderNodeEmission')
    bgc = srgb(BG_HEX)
    if bpy.context.scene.view_settings.view_transform == 'Khronos PBR Neutral':
        bgc = _pbr_neutral_inverse(bgc)
    em.inputs['Color'].default_value = (*bgc, 1)
    # 桌面本身就发背景色，受光和反射加在上面。这样没照到的地方正好是背景色，不会比背景还黑
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(b.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    mx = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(rmp.outputs[0], mx.inputs[0])
    nt.links.new(add.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    out = [n for n in nt.nodes if n.bl_idname == 'ShaderNodeOutputMaterial'][0]
    nt.links.new(mx.outputs[0], out.inputs['Surface'])
    me.materials.append(m)
    return ob


def _cached(name):
    return bpy.data.materials.get(name)


def _object_axis(nt, axis='Z'):
    """物体坐标的某一维（车削纹、硅钢片纹用）。"""
    tex = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tex.outputs['Object'], sep.inputs[0])
    return sep.outputs[axis], tex.outputs['Object']


def _micro_bump(nt, b, scale=30.0, dist=0.006, rough_in=None):
    """各向同性的细小起伏：喷砂、磨砂面用。scale 是每毫米多少个起伏。"""
    tex = nt.nodes.new('ShaderNodeTexCoord')
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = 3.0
    n.inputs['Roughness'].default_value = 0.55
    nt.links.new(tex.outputs['Object'], n.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Distance'].default_value = dist
    nt.links.new(n.outputs['Fac'], bp.inputs['Height'])
    nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return n.outputs['Fac']


def _ramp(nt, v, a, b, lo=0.0, hi=1.0):
    """把 v 从 a..b 平滑映射到 lo..hi。"""
    n = nt.nodes.new('ShaderNodeMapRange')
    n.interpolation_type = 'SMOOTHSTEP'
    n.inputs['From Min'].default_value = a
    n.inputs['From Max'].default_value = b
    n.inputs['To Min'].default_value = lo
    n.inputs['To Max'].default_value = hi
    nt.links.new(v, n.inputs['Value'])
    return n.outputs[0]


def brass(name='黄铜', roughness=0.30, wear=1.0, residue=(0.50, 0.045, 0.012)):
    """用过的黄铜喷嘴，对照真实微距（S02、S10）：颜色是发灰的淡黄铜，不是亮金；有划痕、凹痕和一片片烧焦的残留，嘴尖沾着塑料。

    物体局部 Z 是轴，尖端在 z=0，单位 mm。wear=0 是新喷嘴（只有车削纹）。residue 是嘴尖沾的塑料颜色（线性 RGB），None 表示没有。
    """
    m = _cached(name)
    if m:
        return m
    m, nt, b = _mat(name)
    z, objco = _object_axis(nt, 'Z')
    clean, aged = (0.80, 0.67, 0.38), (0.54, 0.45, 0.25)
    if wear <= 0:
        clean, aged = (0.90, 0.72, 0.38), (0.72, 0.56, 0.28)
    tarn = _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', _noise(nt, objco, 0.7, 3.0, 0.55), 0.42), 3.0, clamp=True)
    col = _mix_rgb(nt, tarn, clean, aged)
    rg = _mix_val(nt, tarn, roughness, roughness + 0.14)
    metal = 1.0
    bump_in = None

    def add_bump(height, dist):
        nonlocal bump_in
        bp = nt.nodes.new('ShaderNodeBump')
        bp.inputs['Distance'].default_value = dist
        nt.links.new(height, bp.inputs['Height'])
        if bump_in is not None:
            nt.links.new(bump_in, bp.inputs['Normal'])
        bump_in = bp.outputs[0]

    # 车削细纹：约 55 µm 一道，幅度很小，大了就像车了螺纹
    w = nt.nodes.new('ShaderNodeTexWave')
    w.wave_type = 'BANDS'
    w.bands_direction = 'Z'
    w.wave_profile = 'SIN'
    w.inputs['Scale'].default_value = 5.7
    w.inputs['Distortion'].default_value = 0.6
    w.inputs['Detail'].default_value = 1.0
    w.inputs['Detail Scale'].default_value = 1.0
    nt.links.new(objco, w.inputs['Vector'])
    add_bump(w.outputs['Fac'], 0.0009)
    if wear > 0:
        def stretched(rot, scale):
            mp = nt.nodes.new('ShaderNodeMapping')
            mp.inputs['Rotation'].default_value = rot
            mp.inputs['Scale'].default_value = scale
            nt.links.new(objco, mp.inputs['Vector'])
            return mp.outputs[0]
        # 凹痕：很平缓的起伏，让六角平面上的反射不再是一整块平光
        add_bump(_noise(nt, objco, 0.45, 2.0, 0.5), 0.07 * wear)
        # 划痕：两组细长的噪声，取高处；只在一部分区域有
        s1 = _ramp(nt, _noise(nt, stretched((0.5, 1.0, 0.2), (1.1, 42, 42)), 1.0, 1.0, 0.5), 0.63, 0.70)
        s2 = _ramp(nt, _noise(nt, stretched((1.2, -0.6, 0.8), (0.8, 55, 55)), 1.0, 1.0, 0.5), 0.64, 0.70)
        patch = _ramp(nt, _noise(nt, objco, 0.9, 2.0, 0.5), 0.34, 0.56)
        scr = _math(nt, 'MULTIPLY', _math(nt, 'MAXIMUM', s1, s2), patch)
        scr = _math(nt, 'MULTIPLY', scr, min(wear, 1.0))
        col = _mix_rgb(nt, _math(nt, 'MULTIPLY', scr, 0.35), col, (0.92, 0.84, 0.62))
        rg = _mix_val(nt, _math(nt, 'MULTIPLY', scr, 0.6), rg, 0.18)
        add_bump(_math(nt, 'SUBTRACT', 1.0, scr), 0.0018)
        # 烧焦的残留：一片片的褐色硬壳，六角上多，圆锥上少；再加一些小黑点
        n_crust = _noise(nt, objco, 0.62, 3.5, 0.55)
        thresh = _ramp(nt, z, 2.8, 4.6, 0.63, 0.53)
        crust = _ramp(nt, _math(nt, 'SUBTRACT', n_crust, thresh), 0.0, 0.05)
        vor = nt.nodes.new('ShaderNodeTexVoronoi')
        vor.inputs['Scale'].default_value = 1.4
        nt.links.new(objco, vor.inputs['Vector'])
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(vor.outputs['Color'], sep.inputs[0])
        spot = _math(nt, 'MULTIPLY', _ramp(nt, vor.outputs['Distance'], 0.05, 0.10, 1.0, 0.0), _ramp(nt, sep.outputs[0], 0.72, 0.74))
        dark = _math(nt, 'MAXIMUM', crust, spot)
        dark = _math(nt, 'MULTIPLY', dark, min(wear, 1.0))
        crust_col = _mix_rgb(nt, _ramp(nt, _noise(nt, objco, 2.6, 3.0, 0.55), 0.38, 0.62), (0.022, 0.010, 0.005), (0.20, 0.085, 0.025))
        col = _mix_rgb(nt, dark, col, crust_col)
        rg = _mix_val(nt, dark, rg, 0.34)
        metal = _math(nt, 'SUBTRACT', 1.0, dark, clamp=True)
        add_bump(_math(nt, 'MULTIPLY', dark, _noise(nt, objco, 9.0, 3.0, 0.6)), 0.012)
        add_bump(dark, 0.006)
    if residue is not None and wear > 0:
        # 嘴尖沾的塑料，离尖端越近越多
        thresh2 = _ramp(nt, z, 0.05, 1.5, 0.57, 0.95)
        pm = _ramp(nt, _math(nt, 'SUBTRACT', _noise(nt, objco, 2.0, 4.0, 0.55), thresh2), 0.0, 0.04)
        col = _mix_rgb(nt, pm, col, residue)
        rg = _mix_val(nt, pm, rg, 0.26)
        metal = _math(nt, 'MULTIPLY', metal, _math(nt, 'SUBTRACT', 1.0, pm))
    nt.links.new(col, b.inputs['Base Color'])
    nt.links.new(rg, b.inputs['Roughness'])
    if isinstance(metal, float):
        b.inputs['Metallic'].default_value = metal
    else:
        nt.links.new(metal, b.inputs['Metallic'])
    b.inputs['Anisotropic'].default_value = 0.2
    tan = nt.nodes.new('ShaderNodeTangent')
    tan.direction_type = 'RADIAL'
    tan.axis = 'Z'
    nt.links.new(tan.outputs[0], b.inputs['Tangent'])
    nt.links.new(bump_in, b.inputs['Normal'])
    return m


def silicone(name='硅胶'):
    """加热块的黑色硅胶套。"""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _mat(name)
    b.inputs['Base Color'].default_value = (0.012, 0.012, 0.013, 1)
    b.inputs['Roughness'].default_value = 0.46
    b.inputs['Specular IOR Level'].default_value = 0.5
    _micro_bump(nt, b, scale=5.0, dist=0.02)
    return m


def steel(name='不锈钢', rough=0.16):
    m = _cached(name)
    if m:
        return m
    m, nt, b = _mat(name)
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Base Color'].default_value = (0.78, 0.77, 0.75, 1)
    b.inputs['Roughness'].default_value = rough
    return m


def aluminium(name='铝', rough=0.5, base=(0.80, 0.80, 0.81)):
    """喷砂铝：细小颗粒感。"""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _mat(name)
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Base Color'].default_value = (*base, 1)
    fac = _micro_bump(nt, b, scale=26.0, dist=0.004)
    nt.links.new(_mix_val(nt, fac, rough - 0.06, rough + 0.06), b.inputs['Roughness'])
    return m


def aluminium_turned(name='车削铝', rough=0.24):
    """车削铝：皮带轮用，沿圆周的各向异性高光。局部 Z 是轴。"""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _mat(name)
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Base Color'].default_value = (0.82, 0.82, 0.83, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Anisotropic'].default_value = 0.7
    tan = nt.nodes.new('ShaderNodeTangent')
    tan.direction_type = 'RADIAL'
    tan.axis = 'Z'
    nt.links.new(tan.outputs[0], b.inputs['Tangent'])
    return m


def _stretched(nt, vec, rot, scale):
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = rot
    mp.inputs['Scale'].default_value = scale
    nt.links.new(vec, mp.inputs['Vector'])
    return mp.outputs[0]


def black_anodized(name='黑色阳极氧化', rough=0.42, wear=0.55):
    """黑色阳极氧化铝。wear 控制用旧的程度：棱边磨出金属底色、面上一些细划痕和蹭痕。0 是全新的。"""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _mat(name)
    base = (0.016, 0.016, 0.018)
    b.inputs['Specular IOR Level'].default_value = 0.62
    fac = _micro_bump(nt, b, scale=24.0, dist=0.004)
    rg = _mix_val(nt, fac, rough - 0.05, rough + 0.05)
    col = base
    if wear > 0:
        objco = nt.nodes.new('ShaderNodeTexCoord').outputs['Object']
        # 棱边：比较倒角后的法向和真实法向，只有棱上才不一样；再用噪声打断，磨损不会一圈都有
        bev = nt.nodes.new('ShaderNodeBevel')
        bev.samples = 4
        bev.inputs['Radius'].default_value = 0.55
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        dt = nt.nodes.new('ShaderNodeVectorMath')
        dt.operation = 'DOT_PRODUCT'
        nt.links.new(bev.outputs[0], dt.inputs[0])
        nt.links.new(geo.outputs['Normal'], dt.inputs[1])
        edge = _ramp(nt, _math(nt, 'SUBTRACT', 1.0, dt.outputs['Value']), 0.004, 0.05)
        broken = _ramp(nt, _noise(nt, objco, 0.16, 5.0, 0.62), 0.50, 0.60)
        edge = _math(nt, 'MULTIPLY', edge, broken)
        # 面上的蹭痕：大片一点点发亮，细划痕
        rub = _ramp(nt, _noise(nt, objco, 0.06, 4.0, 0.55), 0.50, 0.72, 0.0, 0.35)
        s1 = _ramp(nt, _noise(nt, _stretched(nt, objco, (0.3, 0.8, 0.2), (0.25, 8, 8)), 1.0, 1.0, 0.5), 0.66, 0.71)
        s2 = _ramp(nt, _noise(nt, _stretched(nt, objco, (1.1, -0.4, 0.9), (0.18, 7, 7)), 1.0, 1.0, 0.5), 0.67, 0.72)
        scr = _math(nt, 'MULTIPLY', _math(nt, 'MAXIMUM', s1, s2), _ramp(nt, _noise(nt, objco, 0.1, 2.0, 0.5), 0.45, 0.62))
        col = _mix_rgb(nt, _math(nt, 'MULTIPLY', rub, 0.10 * wear), base, (0.14, 0.14, 0.15))
        col = _mix_rgb(nt, _math(nt, 'MULTIPLY', scr, 0.22 * wear), col, (0.30, 0.30, 0.32))
        rg = _mix_val(nt, _math(nt, 'MULTIPLY', rub, wear), rg, rough + 0.14)
        metal = _math(nt, 'MULTIPLY', edge, min(wear, 1.0))
        col = _mix_rgb(nt, metal, col, (0.50, 0.50, 0.52))
        rg = _mix_val(nt, metal, rg, 0.34)
        nt.links.new(metal, b.inputs['Metallic'])
    if isinstance(col, tuple):
        b.inputs['Base Color'].default_value = (*col, 1)
    else:
        nt.links.new(col, b.inputs['Base Color'])
    nt.links.new(rg, b.inputs['Roughness'])
    return m


def label(name='标签'):
    """电机上的贴纸：灰白底，几行灰块，远看像印着字，读不出内容。物体坐标，单位 mm。"""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _mat(name)
    paper = (0.26, 0.26, 0.245)
    ink = (0.05, 0.05, 0.055)
    objco = nt.nodes.new('ShaderNodeTexCoord').outputs['Object']
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(objco, sep.inputs[0])
    # 行：沿局部 x 的条带；条带里用拉长的噪声断开成一块一块
    rows = nt.nodes.new('ShaderNodeTexWave')
    rows.wave_type = 'BANDS'
    rows.bands_direction = 'Z'
    rows.wave_profile = 'SAW'
    rows.inputs['Scale'].default_value = 0.16
    rows.inputs['Distortion'].default_value = 0.0
    nt.links.new(objco, rows.inputs['Vector'])
    row = _ramp(nt, rows.outputs['Fac'], 0.48, 0.52, 1.0, 0.0)
    blocks = _ramp(nt, _noise(nt, _stretched(nt, objco, (0, 0, 0), (0.7, 1, 0.25)), 1.0, 2.0, 0.4), 0.40, 0.44)
    ink_mask = _math(nt, 'MULTIPLY', row, blocks)
    # 留白：四周不印
    edge = _math(nt, 'MULTIPLY', _ramp(nt, _math(nt, 'ABSOLUTE', sep.outputs['X']), 13.8, 13.5), _ramp(nt, _math(nt, 'ABSOLUTE', _math(nt, 'SUBTRACT', sep.outputs['Z'], 11.5)), 10.0, 9.7))
    ink_mask = _math(nt, 'MULTIPLY', ink_mask, edge)
    nt.links.new(_mix_rgb(nt, ink_mask, paper, ink), b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.42
    b.inputs['Specular IOR Level'].default_value = 0.4
    return m


def black_oxide(name='发黑钢'):
    """内六角螺钉的发黑钢。"""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _mat(name)
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Base Color'].default_value = (0.05, 0.05, 0.052, 1)
    b.inputs['Roughness'].default_value = 0.34
    return m


def lamination(name='硅钢片'):
    """步进电机铁芯：一片片叠起来的纹。局部 Z 是轴，0.35 mm 一片。"""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _mat(name)
    b.inputs['Metallic'].default_value = 1.0
    b.inputs['Base Color'].default_value = (0.42, 0.42, 0.43, 1)
    b.inputs['Roughness'].default_value = 0.36
    objco = nt.nodes.new('ShaderNodeTexCoord').outputs['Object']
    w = nt.nodes.new('ShaderNodeTexWave')
    w.wave_type = 'BANDS'
    w.bands_direction = 'Z'
    w.wave_profile = 'SIN'
    w.inputs['Scale'].default_value = 0.92
    w.inputs['Distortion'].default_value = 0.0
    nt.links.new(objco, w.inputs['Vector'])
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Distance'].default_value = 0.04
    nt.links.new(w.outputs['Fac'], bp.inputs['Height'])
    nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return m


def rubber(name='橡胶带'):
    """黑色橡胶齿形带。依赖 machine.Belt 写的 UV（u 沿带长）和属性 belt_part：0 带背，1 齿面（尼龙布），2 侧面。"""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _mat(name)
    b.inputs['Base Color'].default_value = (0.011, 0.011, 0.012, 1)
    b.inputs['Roughness'].default_value = 0.52
    b.inputs['Specular IOR Level'].default_value = 0.45
    uvn = nt.nodes.new('ShaderNodeUVMap')
    uvn.uv_map = 'UV'
    part = nt.nodes.new('ShaderNodeAttribute')
    part.attribute_name = 'belt_part'
    # 细纹：尼龙布的织纹（齿面）、带背很细的横纹
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (5.0, 5.0, 1)
    nt.links.new(uvn.outputs['UV'], mp.inputs['Vector'])
    chk = nt.nodes.new('ShaderNodeTexWave')
    chk.wave_type = 'BANDS'
    chk.bands_direction = 'DIAGONAL'
    chk.inputs['Scale'].default_value = 2.0
    chk.inputs['Distortion'].default_value = 1.0
    nt.links.new(mp.outputs[0], chk.inputs['Vector'])
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.inputs['Scale'].default_value = 16.0
    n.inputs['Detail'].default_value = 3.0
    tex = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(tex.outputs['Object'], n.inputs['Vector'])
    # 织纹只在齿面（belt_part = 1），侧面和带背是光一点的橡胶
    mask = _math(nt, 'SUBTRACT', 1.0, _math(nt, 'ABSOLUTE', _math(nt, 'SUBTRACT', part.outputs['Fac'], 1.0)), clamp=True)
    h = _math(nt, 'ADD', _math(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', chk.outputs['Fac'], mask), 0.6), _math(nt, 'MULTIPLY', n.outputs['Fac'], 0.5))
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Distance'].default_value = 0.02
    nt.links.new(h, bp.inputs['Height'])
    nt.links.new(bp.outputs[0], b.inputs['Normal'])
    return m


def nylon_white(name='白色尼龙'):
    m = _cached(name)
    if m:
        return m
    m, nt, b = _mat(name)
    b.inputs['Base Color'].default_value = (0.72, 0.70, 0.64, 1)
    b.inputs['Roughness'].default_value = 0.46
    b.inputs['Subsurface Weight'].default_value = 0.5
    b.inputs['Subsurface Radius'].default_value = (1, 1, 1)
    b.inputs['Subsurface Scale'].default_value = 0.6
    return m


def wire(name='线缆', color=(0.012, 0.012, 0.013)):
    m = _cached(name)
    if m:
        return m
    m, nt, b = _mat(name)
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = 0.38
    return m


def bed_sheet(name='床面'):
    """打印床表面：深色的磨砂涂层板，细密的小颗粒。"""
    m = _cached(name)
    if m:
        return m
    m, nt, b = _mat(name)
    b.inputs['Base Color'].default_value = (0.022, 0.021, 0.021, 1)
    b.inputs['Specular IOR Level'].default_value = 0.55
    fac = _micro_bump(nt, b, scale=7.0, dist=0.03)
    nt.links.new(_mix_val(nt, fac, 0.32, 0.48), b.inputs['Roughness'])
    return m
