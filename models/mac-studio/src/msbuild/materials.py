import bpy

_cache = {}


def _tree(mat):
    if mat.node_tree is None:
        mat.use_nodes = True
    return mat.node_tree


def srgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def principled(name, base=(0.8, 0.8, 0.8), metallic=0.0, rough=0.5, spec=0.5, ior=1.5,
               coat=0.0, coat_rough=0.03, aniso=0.0, thin_film=0.0, thin_film_ior=1.45,
               emission=None, emission_strength=0.0, spec_tint=None):
    if name in _cache:
        return _cache[name]
    m = bpy.data.materials.new(name)
    nt = _tree(m)
    p = nt.nodes.get('Principled BSDF')
    if len(base) == 3:
        base = tuple(base) + (1.0,)
    p.inputs['Base Color'].default_value = base
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = rough
    p.inputs['Specular IOR Level'].default_value = spec
    p.inputs['IOR'].default_value = ior
    p.inputs['Coat Weight'].default_value = coat
    p.inputs['Coat Roughness'].default_value = coat_rough
    p.inputs['Anisotropic'].default_value = aniso
    p.inputs['Thin Film Thickness'].default_value = thin_film
    p.inputs['Thin Film IOR'].default_value = thin_film_ior
    if spec_tint is not None:
        p.inputs['Specular Tint'].default_value = tuple(spec_tint) + (1.0,)
    if emission is not None:
        p.inputs['Emission Color'].default_value = tuple(emission) + (1.0,)
        p.inputs['Emission Strength'].default_value = emission_strength
    m.diffuse_color = base
    if emission is None:
        _glow_nodes(nt, p)
    _cache[name] = m
    return m


def _glow_nodes(nt, p, gain=1.0):
    N = nt.nodes
    L = nt.links
    ag = N.new('ShaderNodeAttribute')
    ag.attribute_type = 'OBJECT'
    ag.attribute_name = 'glow'
    ac = N.new('ShaderNodeAttribute')
    ac.attribute_type = 'OBJECT'
    ac.attribute_name = 'glow_color'
    mul = N.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = gain
    L.new(ag.outputs['Fac'], mul.inputs[0])
    L.new(ac.outputs['Color'], p.inputs['Emission Color'])
    L.new(mul.outputs['Value'], p.inputs['Emission Strength'])


def add_xray(m, color=(0.62, 0.8, 1.0)):
    nt = m.node_tree
    N = nt.nodes
    L = nt.links
    out = N.get('Material Output')
    src = out.inputs['Surface'].links[0].from_socket
    ax = N.new('ShaderNodeAttribute')
    ax.attribute_type = 'OBJECT'
    ax.attribute_name = 'xray'
    lw = N.new('ShaderNodeLayerWeight')
    lw.inputs['Blend'].default_value = 0.35
    pw = N.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = 2.2
    L.new(lw.outputs['Facing'], pw.inputs[0])
    tr = N.new('ShaderNodeBsdfTransparent')
    em = N.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = tuple(color) + (1.0,)
    sc = N.new('ShaderNodeMath')
    sc.operation = 'MULTIPLY_ADD'
    sc.inputs[1].default_value = 1.6
    sc.inputs[2].default_value = 0.03
    L.new(pw.outputs['Value'], sc.inputs[0])
    L.new(sc.outputs['Value'], em.inputs['Strength'])
    add = N.new('ShaderNodeAddShader')
    L.new(tr.outputs['BSDF'], add.inputs[0])
    L.new(em.outputs['Emission'], add.inputs[1])
    mx = N.new('ShaderNodeMixShader')
    L.new(ax.outputs['Fac'], mx.inputs['Fac'])
    L.new(src, mx.inputs[1])
    L.new(add.outputs['Shader'], mx.inputs[2])
    L.new(mx.outputs['Shader'], out.inputs['Surface'])
    return m


def _bevel_bump(nt, p, bevel_mm=0.0, bump_scale=0.0, bump_strength=0.0, bump_dist_mm=0.02, rough_var=None):
    N = nt.nodes
    L = nt.links
    normal_src = None
    if bevel_mm > 0:
        bv = N.new('ShaderNodeBevel')
        bv.samples = 8
        bv.inputs['Radius'].default_value = bevel_mm * 0.001
        normal_src = bv.outputs['Normal']
    if bump_scale > 0:
        tc = N.new('ShaderNodeTexCoord')
        nz = N.new('ShaderNodeTexNoise')
        nz.noise_dimensions = '3D'
        nz.inputs['Scale'].default_value = bump_scale
        nz.inputs['Detail'].default_value = 2.0
        nz.inputs['Roughness'].default_value = 0.6
        L.new(tc.outputs['Object'], nz.inputs['Vector'])
        bp = N.new('ShaderNodeBump')
        bp.inputs['Strength'].default_value = bump_strength
        bp.inputs['Distance'].default_value = bump_dist_mm * 0.001
        L.new(nz.outputs['Fac'], bp.inputs['Height'])
        if normal_src is not None:
            L.new(normal_src, bp.inputs['Normal'])
        normal_src = bp.outputs['Normal']
        if rough_var is not None:
            nz2 = N.new('ShaderNodeTexNoise')
            nz2.inputs['Scale'].default_value = rough_var[2]
            nz2.inputs['Detail'].default_value = 3.0
            L.new(tc.outputs['Object'], nz2.inputs['Vector'])
            mr = N.new('ShaderNodeMapRange')
            mr.inputs['To Min'].default_value = rough_var[0]
            mr.inputs['To Max'].default_value = rough_var[1]
            L.new(nz2.outputs['Fac'], mr.inputs['Value'])
            L.new(mr.outputs['Result'], p.inputs['Roughness'])
    if normal_src is not None:
        L.new(normal_src, p.inputs['Normal'])


def aluminium_bead():
    name = 'MS_Al_BeadBlast'
    if name in _cache:
        return _cache[name]
    m = principled(name, base=(0.78, 0.785, 0.795), metallic=1.0, rough=0.4, spec=0.5)
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    _bevel_bump(nt, p, bevel_mm=0.22, bump_scale=14000.0, bump_strength=0.05, bump_dist_mm=0.008,
                rough_var=(0.385, 0.415, 900.0))
    return m


def aluminium_drilled():
    name = 'MS_Al_Drilled'
    if name in _cache:
        return _cache[name]
    m = principled(name, base=(0.86, 0.865, 0.87), metallic=1.0, rough=0.2, spec=0.5, aniso=0.5)
    nt = m.node_tree
    N = nt.nodes
    L = nt.links
    p = N.get('Principled BSDF')
    _bevel_bump(nt, p, bevel_mm=0.06)
    ad = N.new('ShaderNodeAttribute')
    ad.attribute_type = 'OBJECT'
    ad.attribute_name = 'bore_dark'
    mc = N.new('ShaderNodeMix')
    mc.data_type = 'RGBA'
    mc.inputs['A'].default_value = (0.86, 0.865, 0.87, 1.0)
    mc.inputs['B'].default_value = (0.06, 0.062, 0.066, 1.0)
    L.new(ad.outputs['Fac'], mc.inputs['Factor'])
    L.new(mc.outputs['Result'], p.inputs['Base Color'])
    mr = N.new('ShaderNodeMapRange')
    mr.inputs['To Min'].default_value = 0.2
    mr.inputs['To Max'].default_value = 0.55
    L.new(ad.outputs['Fac'], mr.inputs['Value'])
    L.new(mr.outputs['Result'], p.inputs['Roughness'])
    return m


def aluminium_section():
    name = 'MS_Al_Section'
    if name in _cache:
        return _cache[name]
    m = principled(name, base=(0.84, 0.845, 0.85), metallic=1.0, rough=0.22, spec=0.5)
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    _bevel_bump(nt, p, bevel_mm=0.12, bump_scale=3000.0, bump_strength=0.03, bump_dist_mm=0.01)
    return m


def seam_mat():
    return principled('MS_Seam_Bridge', base=(0.05, 0.05, 0.06), metallic=0.6, rough=0.3, spec=0.5)


def logo_black():
    return principled('MS_Logo_GlossBlack', base=(0.0015, 0.0015, 0.002), metallic=0.0, rough=0.07,
                      spec=0.5, coat=0.0)


def black_plastic():
    name = 'MS_Black_Plastic'
    if name in _cache:
        return _cache[name]
    m = principled(name, base=(0.016, 0.016, 0.018), rough=0.42, spec=0.5)
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    _bevel_bump(nt, p, bevel_mm=0.2, bump_scale=2500.0, bump_strength=0.04, bump_dist_mm=0.01)
    return m


def black_satin():
    return principled('MS_Black_Satin', base=(0.012, 0.012, 0.014), rough=0.32, spec=0.5)


def black_rubber():
    return principled('MS_Black_Polymer', base=(0.016, 0.016, 0.017), rough=0.62, spec=0.35)


def black_paint_metal():
    name = 'MS_Black_PaintedSteel'
    if name in _cache:
        return _cache[name]
    m = principled(name, base=(0.02, 0.02, 0.022), metallic=0.0, rough=0.42, spec=0.5, coat=0.15, coat_rough=0.3)
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    _bevel_bump(nt, p, bevel_mm=0.15)
    return m


def pcb_black():
    name = 'MS_PCB_Black'
    if name in _cache:
        return _cache[name]
    m = principled(name, base=(0.014, 0.015, 0.016), rough=0.34, spec=0.5, coat=0.3, coat_rough=0.25)
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    _bevel_bump(nt, p, bevel_mm=0.08, bump_scale=600.0, bump_strength=0.025, bump_dist_mm=0.02)
    return m


def chip_black():
    return principled('MS_Chip_Epoxy', base=(0.012, 0.012, 0.013), rough=0.38, spec=0.5)


def copper():
    name = 'MS_Copper'
    if name in _cache:
        return _cache[name]
    m = principled(name, base=(0.955, 0.6, 0.47), metallic=1.0, rough=0.26, spec=0.5)
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    _bevel_bump(nt, p, bevel_mm=0.1, bump_scale=1500.0, bump_strength=0.03, bump_dist_mm=0.01,
                rough_var=(0.22, 0.32, 120.0))
    return m


def copper_polished():
    name = 'MS_Copper_Polished'
    if name in _cache:
        return _cache[name]
    m = principled(name, base=(0.96, 0.63, 0.5), metallic=1.0, rough=0.12, spec=0.5)
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    _bevel_bump(nt, p, bevel_mm=0.15)
    return m


def al_fin():
    name = 'MS_Al_Fin'
    if name in _cache:
        return _cache[name]
    m = principled(name, base=(0.9, 0.905, 0.91), metallic=1.0, rough=0.24, spec=0.5)
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    _bevel_bump(nt, p, bevel_mm=0.08, bump_scale=1500.0, bump_strength=0.02, bump_dist_mm=0.01,
                rough_var=(0.2, 0.3, 120.0))
    return m


def al_plain():
    return principled('MS_Al_Sheet', base=(0.85, 0.855, 0.86), metallic=1.0, rough=0.3, spec=0.5)


def al_anodized_dark():
    return principled('MS_Al_Anodized_Dark', base=(0.11, 0.112, 0.118), metallic=1.0, rough=0.38, spec=0.5)


def gold():
    return principled('MS_Gold', base=(1.0, 0.76, 0.33), metallic=1.0, rough=0.3, spec=0.5)


def gold_flex():
    return principled('MS_Antenna_Gold', base=(0.98, 0.72, 0.3), metallic=1.0, rough=0.38, spec=0.5)


def steel():
    return principled('MS_Steel', base=(0.62, 0.62, 0.63), metallic=1.0, rough=0.28, spec=0.5)


def steel_dark():
    return principled('MS_Steel_Dark', base=(0.09, 0.09, 0.1), metallic=0.7, rough=0.4, spec=0.5)


def tin():
    return principled('MS_Tin', base=(0.78, 0.78, 0.79), metallic=1.0, rough=0.25, spec=0.5)


def silicon_mirror():
    return principled('MS_Silicon_Mirror', base=(0.02, 0.022, 0.03), metallic=0.0, rough=0.035,
                      spec=1.0, ior=3.9, thin_film=380.0, thin_film_ior=1.46)


def silicon_closeup():
    name = 'MS_Silicon_DieCloseup'
    if name in _cache:
        return _cache[name]
    m = principled(name, base=(0.018, 0.02, 0.028), metallic=0.0, rough=0.04, spec=1.0, ior=3.9,
                   thin_film=380.0, thin_film_ior=1.46)
    nt = m.node_tree
    N = nt.nodes
    L = nt.links
    p = N.get('Principled BSDF')
    tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping')
    L.new(tc.outputs['Object'], mp.inputs['Vector'])
    mp.inputs['Scale'].default_value = (1000.0, 1000.0, 1000.0)
    vor = N.new('ShaderNodeTexVoronoi')
    vor.voronoi_dimensions = '2D'
    vor.distance = 'CHEBYCHEV'
    vor.inputs['Scale'].default_value = 0.45
    L.new(mp.outputs['Vector'], vor.inputs['Vector'])
    vor2 = N.new('ShaderNodeTexVoronoi')
    vor2.voronoi_dimensions = '2D'
    vor2.distance = 'CHEBYCHEV'
    vor2.inputs['Scale'].default_value = 3.2
    L.new(mp.outputs['Vector'], vor2.inputs['Vector'])
    brick = N.new('ShaderNodeTexBrick')
    brick.inputs['Scale'].default_value = 6.0
    brick.inputs['Mortar Size'].default_value = 0.01
    brick.inputs['Brick Width'].default_value = 0.35
    brick.inputs['Row Height'].default_value = 0.12
    L.new(mp.outputs['Vector'], brick.inputs['Vector'])
    mix1 = N.new('ShaderNodeMix')
    mix1.data_type = 'FLOAT'
    mix1.inputs['Factor'].default_value = 0.5
    L.new(vor.outputs['Color'], mix1.inputs['A'])
    L.new(vor2.outputs['Color'], mix1.inputs['B'])
    mr = N.new('ShaderNodeMapRange')
    mr.inputs['To Min'].default_value = 0.025
    mr.inputs['To Max'].default_value = 0.07
    L.new(mix1.outputs['Result'], mr.inputs['Value'])
    L.new(mr.outputs['Result'], p.inputs['Roughness'])
    tf = N.new('ShaderNodeMapRange')
    tf.inputs['To Min'].default_value = 300.0
    tf.inputs['To Max'].default_value = 520.0
    L.new(vor2.outputs['Distance'], tf.inputs['Value'])
    L.new(tf.outputs['Result'], p.inputs['Thin Film Thickness'])
    bp = N.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 0.05
    bp.inputs['Distance'].default_value = 0.000005
    L.new(brick.outputs['Fac'], bp.inputs['Height'])
    L.new(bp.outputs['Normal'], p.inputs['Normal'])
    return m


def substrate():
    name = 'MS_Substrate'
    if name in _cache:
        return _cache[name]
    m = principled(name, base=(0.022, 0.03, 0.026), rough=0.45, spec=0.5, coat=0.4, coat_rough=0.2)
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    _bevel_bump(nt, p, bevel_mm=0.05, bump_scale=900.0, bump_strength=0.02, bump_dist_mm=0.01)
    return m


def cap_body():
    return principled('MS_Cap_Ceramic', base=(0.13, 0.105, 0.075), rough=0.5, spec=0.4)


def ferrite():
    return principled('MS_Inductor', base=(0.035, 0.035, 0.037), rough=0.55, spec=0.4)


def tape_amber():
    return principled('MS_Kapton', base=(0.55, 0.25, 0.02), rough=0.25, spec=0.5, coat=0.5)


def copper_wire():
    name = 'MS_Copper_Wire'
    if name in _cache:
        return _cache[name]
    m = principled(name, base=(0.95, 0.52, 0.32), metallic=1.0, rough=0.18, spec=0.5)
    nt = m.node_tree
    N = nt.nodes
    L = nt.links
    p = N.get('Principled BSDF')
    attr = N.new('ShaderNodeAttribute')
    attr.attribute_name = 'wind'
    attr.attribute_type = 'GEOMETRY'
    wave = N.new('ShaderNodeMath')
    wave.operation = 'SINE'
    mul = N.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = 1.0
    L.new(attr.outputs['Fac'], mul.inputs[0])
    L.new(mul.outputs['Value'], wave.inputs[0])
    ab = N.new('ShaderNodeMath')
    ab.operation = 'ABSOLUTE'
    L.new(wave.outputs['Value'], ab.inputs[0])
    bp = N.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 0.6
    bp.inputs['Distance'].default_value = 0.0003
    L.new(ab.outputs['Value'], bp.inputs['Height'])
    L.new(bp.outputs['Normal'], p.inputs['Normal'])
    return m


def label_grey():
    return principled('MS_Label', base=(0.06, 0.06, 0.065), rough=0.6, spec=0.3)


def led_pipe():
    return principled('MS_LED_Pipe', base=(0.02, 0.02, 0.02), rough=0.15, spec=0.6,
                      emission=(1.0, 0.98, 0.95), emission_strength=0.0)


def speaker_mesh():
    return principled('MS_Speaker_Mesh', base=(0.03, 0.03, 0.032), metallic=0.5, rough=0.5, spec=0.4)


def get_all():
    d = _all()
    for k in ('al', 'al_drill', 'al_section', 'logo'):
        if not d[k].get('xray_added'):
            add_xray(d[k])
            d[k]['xray_added'] = True
    return d


def _all():
    return {
        'al': aluminium_bead(), 'al_drill': aluminium_drilled(), 'al_section': aluminium_section(),
        'logo': logo_black(), 'plastic': black_plastic(), 'satin': black_satin(), 'rubber': black_rubber(),
        'paint': black_paint_metal(), 'pcb': pcb_black(), 'chip': chip_black(), 'cu': copper(),
        'cu_pol': copper_polished(), 'al_fin': al_fin(), 'al_sheet': al_plain(), 'al_dark': al_anodized_dark(), 'gold': gold(),
        'gold_flex': gold_flex(), 'steel': steel(), 'steel_dark': steel_dark(), 'tin': tin(),
        'si': silicon_mirror(), 'si_close': silicon_closeup(), 'substrate': substrate(),
        'cap': cap_body(), 'ferrite': ferrite(), 'kapton': tape_amber(), 'cu_wire': copper_wire(),
        'label': label_grey(), 'led': led_pipe(), 'spk': speaker_mesh(), 'seam': seam_mat(),
    }
