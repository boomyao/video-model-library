# Materials for the v2/v3 car (procedural only).
import bpy, math
import lib_rog as L


def _bump_noise(g, scale, strength, dist=0.0005, coord='Object'):
    tc = g.n('ShaderNodeTexCoord')
    nz = g.n('ShaderNodeTexNoise', {'Scale': scale, 'Detail': 6.0, 'Roughness': 0.55})
    g.link(tc.outputs[coord], nz.inputs['Vector'])
    bp = g.n('ShaderNodeBump', {'Strength': strength, 'Distance': dist})
    g.link(nz.outputs['Fac'], bp.inputs['Height'])
    return bp


def paint(name='CAR_paint', base=(0.80, 0.80, 0.78)):
    """Ano White: a soft satin white base under a glossy clear coat. The coat gives the long crisp highlight lines of
    strip lights; the base keeps the body reading white (not chrome) away from them."""
    m, g, out = L.new_material(name)
    p = L.principled(g, Base_Color=(*base, 1), Roughness=0.30, Specular_IOR_Level=0.45, Coat_Weight=1.0,
                     Coat_Roughness=0.018, Coat_IOR=1.52, Coat_Tint=(1.0, 1.0, 1.0, 1.0))
    g.link(p, out.inputs['Surface'])
    return m


def satin(name, c=0.018, rough=0.38, coat=0.4):
    m, g, out = L.new_material(name)
    p = L.principled(g, Base_Color=(c, c, c * 1.05, 1), Roughness=rough, Coat_Weight=coat, Coat_Roughness=0.15)
    g.link(p, out.inputs['Surface'])
    return m


def gloss_black(name='CAR_gloss_black'):
    m, g, out = L.new_material(name)
    p = L.principled(g, Base_Color=(0.008, 0.008, 0.009, 1), Roughness=0.12, Coat_Weight=1.0, Coat_Roughness=0.02)
    g.link(p, out.inputs['Surface'])
    return m


GLASS_GOLD = (1.0, 0.70, 0.32)      # colour of the gold coating's reflection
GLASS_R0, GLASS_R90 = 0.16, 0.80     # share of the gold mirror layer head-on / at grazing angles
GLASS_TINT = (0.84, 0.76, 0.60)      # transmission tint per face (two faces per pane)


def glass(name='CAR_glass'):
    """Gold Glazed: a gold-coated glass bubble. A thin gold mirror layer reflects GLASS_R0 head-on and far more toward
    grazing angles, so the canopy reads as a closed, gold-sheened bubble from every side (its curved edges turn to gold
    mirror); the rest passes through bronze-tinted, so the lit seat and tanks still show where the angle allows. A
    black ceramic frit band (mesh attribute 'frit', 0..1, set by car2) borders each pane: a crisp dark edge between the
    glass and the white body, like a real car's glazing. Shadow rays pass the clear part with the same tint (the cabin
    stays lit) and stop at the frit."""
    m, g, out = L.new_material(name)
    clear = L.principled(g, Base_Color=(*GLASS_TINT, 1), Roughness=0.0, IOR=1.52, Transmission_Weight=1.0,
                         Specular_IOR_Level=0.5)
    gold = L.principled(g, Base_Color=(*GLASS_GOLD, 1), Metallic=1.0, Roughness=0.03)
    lw = g.n('ShaderNodeLayerWeight', {'Blend': 0.5})
    fr = g.math('POWER', lw.outputs['Facing'], 3.0)
    fac = g.math('MULTIPLY_ADD', fr, GLASS_R90 - GLASS_R0, GLASS_R0)
    coat = g.n('ShaderNodeMixShader')
    g.link(fac, coat.inputs['Fac'])
    g.link(clear.outputs[0], coat.inputs[1])
    g.link(gold.outputs[0], coat.inputs[2])
    frit_attr = g.n('ShaderNodeAttribute', attribute_type='GEOMETRY', attribute_name='frit')
    frit = L.principled(g, Base_Color=(0.004, 0.004, 0.005, 1), Roughness=0.18, Coat_Weight=1.0, Coat_Roughness=0.01,
                        Coat_IOR=1.52)
    surf = g.n('ShaderNodeMixShader')
    g.link(frit_attr.outputs['Fac'], surf.inputs['Fac'])
    g.link(coat.outputs[0], surf.inputs[1])
    g.link(frit.outputs[0], surf.inputs[2])
    tr = g.n('ShaderNodeBsdfTransparent', {'Color': (GLASS_TINT[0] * 0.92, GLASS_TINT[1] * 0.92, GLASS_TINT[2] * 0.92, 1)})
    dark = g.n('ShaderNodeBsdfDiffuse', {'Color': (0.0, 0.0, 0.0, 1)})
    sh = g.n('ShaderNodeMixShader')
    g.link(frit_attr.outputs['Fac'], sh.inputs['Fac'])
    g.link(tr.outputs[0], sh.inputs[1])
    g.link(dark.outputs[0], sh.inputs[2])
    lp = g.n('ShaderNodeLightPath')
    mix = g.n('ShaderNodeMixShader')
    g.link(lp.outputs['Is Shadow Ray'], mix.inputs['Fac'])
    g.link(surf.outputs[0], mix.inputs[1])
    g.link(sh.outputs[0], mix.inputs[2])
    g.link(mix.outputs[0], out.inputs['Surface'])
    return m


def headglass(name='CAR_headglass'):
    """Smoked lens over the headlight slit: dark, very glossy."""
    m, g, out = L.new_material(name)
    p = L.principled(g, Base_Color=(0.025, 0.026, 0.03, 1), Roughness=0.04, Coat_Weight=1.0, Coat_Roughness=0.01,
                     Specular_IOR_Level=0.6)
    g.link(p, out.inputs['Surface'])
    return m


def metal(name, c=(0.75, 0.75, 0.76), rough=0.22):
    m, g, out = L.new_material(name)
    p = L.principled(g, Base_Color=(*c, 1), Metallic=1.0, Roughness=rough)
    g.link(p, out.inputs['Surface'])
    return m


TREAD_PITCHES = 48        # lateral grooves round the tyre (a whole number: no seam)


def rubber(name='CAR_tyre'):
    """Matte tyre rubber with a directional tread. The tyre is a lathe round its object y axis: the tread is where the
    object-space normal is radial. Lateral grooves sweep back from the centre rib in a shallow V (TREAD_PITCHES round
    the tyre), the outer shoulder blocks are offset half a pitch; grooves are recessed (bump) and darker. The
    sidewall is a slightly smoother, lighter rubber with a fine grain. No sharp highlights: rough, low specular,
    a faint dusty sheen at grazing angles."""
    m, g, out = L.new_material(name)
    tc = g.n('ShaderNodeTexCoord')
    x, y, z = g.sep(tc.outputs['Object'])
    nx, ny, nz = g.sep(tc.outputs['Normal'])
    tread = g.maprange(g.math('ABSOLUTE', ny), 0.30, 0.60, 1.0, 0.0)          # 1 on the crown, 0 on the sidewall
    ay = g.math('ABSOLUTE', y)
    th = g.math('ARCTAN2', z, x)
    u = g.math('MULTIPLY_ADD', th, TREAD_PITCHES / (2 * math.pi), g.math('MULTIPLY', ay, 3.4))
    f1 = g.math('FRACT', u)
    lat = g.maprange(f1, 0.11, 0.17, 1.0, 0.0)                                 # V grooves between rib and shoulder
    band = g.math('MULTIPLY', g.maprange(ay, 0.030, 0.040, 0.0, 1.0), g.maprange(ay, 0.118, 0.126, 1.0, 0.0))
    f2 = g.math('FRACT', g.math('ADD', g.math('MULTIPLY', th, TREAD_PITCHES / (2 * math.pi)), 0.5))
    sh = g.math('MULTIPLY', g.maprange(f2, 0.12, 0.20, 1.0, 0.0), g.maprange(ay, 0.098, 0.106, 0.0, 1.0))
    groove = g.math('MULTIPLY', g.math('MAXIMUM', g.math('MULTIPLY', lat, band), sh), tread)
    nz_ = g.n('ShaderNodeTexNoise', {'Scale': 420.0, 'Detail': 3.0, 'Roughness': 0.6})
    g.link(tc.outputs['Object'], nz_.inputs['Vector'])
    height = g.math('SUBTRACT', g.math('MULTIPLY', nz_.outputs['Fac'], 0.06), groove)
    bp = g.n('ShaderNodeBump', {'Strength': 0.9, 'Distance': 0.0035})
    g.link(height, bp.inputs['Height'])
    base = g.mixrgb(tread, (0.034, 0.034, 0.036, 1), (0.030, 0.030, 0.031, 1))
    col = g.mixrgb(groove, base, (0.010, 0.010, 0.011, 1))
    rough = g.math('ADD', g.maprange(tread, 0.0, 1.0, 0.74, 0.84), g.math('MULTIPLY', groove, 0.12))
    p = L.principled(g, Roughness=0.8, Specular_IOR_Level=0.30, Sheen_Weight=0.25, Sheen_Roughness=0.5,
                     Sheen_Tint=(0.5, 0.5, 0.52, 1))
    g.link(col, p.inputs['Base Color'])
    g.link(rough, p.inputs['Roughness'])
    g.link(bp.outputs['Normal'], p.inputs['Normal'])
    g.link(p, out.inputs['Surface'])
    return m


def cover_paint(name='CAR_cover'):
    """Plain stunt-car wheel cover (fact S10): mid-grey satin paint under a soft clear coat, clearly darker than the
    white body (as the stunt car's covers in m072), never a white disc or a black mirror."""
    m, g, out = L.new_material(name)
    p = L.principled(g, Base_Color=(0.17, 0.172, 0.178, 1), Metallic=0.2, Roughness=0.42, Coat_Weight=0.5,
                     Coat_Roughness=0.12)
    g.link(p, out.inputs['Surface'])
    return m


def brushed(name, c, rough=0.24, aniso=0.55):
    """Brushed metal, the grain running round the part's own x axis (object space): the rear nozzle bezels."""
    m, g, out = L.new_material(name)
    tg = g.n('ShaderNodeTangent', direction_type='RADIAL', axis='X')
    p = L.principled(g, Base_Color=(*c, 1), Metallic=1.0, Roughness=rough, Anisotropic=aniso)
    g.link(tg.outputs['Tangent'], p.inputs['Tangent'])
    g.link(p, out.inputs['Surface'])
    return m


def plate_lit(name='CAR_plate'):
    """Plain white plate under its lamp: a satin white face that also glows softly (lit from the lamp above it, the
    glow fading toward the bottom edge), so it reads at night like a real lit plate."""
    m, g, out = L.new_material(name)
    tc = g.n('ShaderNodeTexCoord')
    gx, gy, gz = g.sep(tc.outputs['Generated'])
    glow = g.maprange(gz, 0.0, 1.0, 0.75, 1.15)
    v = g.value(2.6, 'strength')
    p = L.principled(g, Base_Color=(0.86, 0.86, 0.84, 1), Roughness=0.42, Specular_IOR_Level=0.4,
                     Emission_Color=(1.0, 0.98, 0.95, 1))
    g.link(g.math('MULTIPLY', glow, v.outputs[0]), p.inputs['Emission Strength'])
    g.link(p, out.inputs['Surface'])
    return m


def brush(name='CAR_brush'):
    """Brush strip at the bottom of the seal: dark bristles (fine vertical streaks)."""
    m, g, out = L.new_material(name)
    tc = g.n('ShaderNodeTexCoord')
    mp = g.n('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (900.0, 900.0, 25.0)
    g.link(tc.outputs['Object'], mp.inputs['Vector'])
    nz = g.n('ShaderNodeTexNoise', {'Scale': 1.0, 'Detail': 2.0})
    g.link(mp.outputs[0], nz.inputs['Vector'])
    bp = g.n('ShaderNodeBump', {'Strength': 0.6, 'Distance': 0.001})
    g.link(nz.outputs['Fac'], bp.inputs['Height'])
    p = L.principled(g, Base_Color=(0.012, 0.012, 0.013, 1), Roughness=0.62)
    g.link(bp, p.inputs['Normal'])
    g.link(p, out.inputs['Surface'])
    return m


def emitter(name, color, strength, lens=(0.02, 0.02, 0.02)):
    """Light source seen through a slightly glossy lens: emission plus a clear coat for reflections."""
    m, g, out = L.new_material(name)
    p = L.principled(g, Base_Color=(*lens, 1), Roughness=0.15, Coat_Weight=1.0, Coat_Roughness=0.01,
                     Emission_Color=(*color, 1), Emission_Strength=strength)
    g.link(p, out.inputs['Surface'])
    v = g.value(strength, 'strength')
    g.link(v, p.inputs['Emission Strength'])
    return m


def plain(name, c, rough=0.5):
    m, g, out = L.new_material(name)
    p = L.principled(g, Base_Color=(*c, 1), Roughness=rough)
    g.link(p, out.inputs['Surface'])
    return m


def make_car_materials():
    M = {}
    M['paint'] = paint()
    M['trim'] = satin('CAR_trim')
    M['gloss_black'] = gloss_black()
    M['glass'] = glass()
    M['headglass'] = headglass()
    M['tyre'] = rubber()
    M['groove'] = plain('CAR_groove', (0.012, 0.012, 0.013), 0.85)
    M['steel'] = metal('CAR_steel', (0.80, 0.80, 0.80), 0.16)
    M['rim'] = metal('CAR_rim', (0.50, 0.50, 0.51), 0.34)          # satin rim lip (no pin-point glints)
    M['dark_metal'] = metal('CAR_dark_metal', (0.10, 0.10, 0.11), 0.35)
    M['lightbar'] = emitter('CAR_lightbar', (0.85, 0.92, 1.0), 25.0)
    M['headlamp'] = emitter('CAR_headlamp', (0.9, 0.95, 1.0), 22.0, lens=(0.05, 0.05, 0.06))
    M['taillight'] = emitter('CAR_taillight', (1.0, 0.0, 0.0), 7.0, lens=(0.12, 0.0, 0.0))
    M['amber'] = emitter('CAR_amber', (1.0, 0.35, 0.02), 4.0)
    M['plate'] = plate_lit()
    M['plate_ink'] = plain('CAR_plate_ink', (0.012, 0.014, 0.022), 0.45)   # characters and the printed border
    M['plate_lamp'] = emitter('CAR_plate_lamp', (1.0, 0.97, 0.92), 30.0, lens=(0.5, 0.5, 0.5))
    M['under'] = plain('CAR_under', (0.035, 0.035, 0.038), 0.6)
    M['diffuser'] = plain('CAR_diffuser', (0.010, 0.010, 0.011), 0.55)   # matte black lower tail (m064)
    M['interior_white'] = plain('CAR_int_white', (0.42, 0.41, 0.39), 0.55)
    M['interior_grey'] = plain('CAR_int_grey', (0.08, 0.08, 0.085), 0.8)
    M['cover'] = cover_paint()
    M['carbon_trim'] = satin('CAR_carbon_trim', 0.022, 0.32, 0.6)
    M['brush'] = brush()
    # satin gold-brass rear nozzle bezels (m064's bright rings); isotropic: an anisotropic brush round the car's axis
    # (the parts' shared origin) sparkled in motion blur instead of reading as clean rings
    M['nozzle'] = metal('CAR_nozzle', (0.95, 0.74, 0.42), 0.26)
    M['nozzle_in'] = metal('CAR_nozzle_in', (0.86, 0.72, 0.50), 0.12)   # polished bore
    M['reflector'] = emitter('CAR_reflector', (0.92, 0.96, 1.0), 6.0, lens=(0.62, 0.63, 0.66))
    return add_hardware_materials(M)


def add_hardware_materials(M):
    M['frame'] = metal('CAR_frame', (0.55, 0.56, 0.58), 0.35)          # light-grey grid bars (S17)
    M['fan'] = metal('CAR_fan', (0.36, 0.37, 0.39), 0.32)             # anodised fan blades and hubs
    M['floorpanel'] = plain('CAR_floorpanel', (0.03, 0.03, 0.032), 0.55)
    M['skirt'] = skirt_rubber()                                       # matte rubber curtain, pleated
    M['tankshell'] = plain('CAR_tankshell', (0.04, 0.04, 0.045), 0.4)   # replaced by the effects shell later
    M['strap'] = satin('CAR_strap', 0.025, 0.45, 0.2)
    M['valve'] = metal('CAR_valve', (0.70, 0.70, 0.72), 0.2)
    M['pipe'] = metal('CAR_pipe', (0.72, 0.72, 0.73), 0.16)
    M['carbon'] = carbon_wound()
    M['tank_cut'] = plain('CAR_tank_cut', (0.055, 0.055, 0.06), 0.55)
    M['liner'] = metal('CAR_liner', (0.80, 0.80, 0.81), 0.30)
    M['boss'] = metal('CAR_boss', (0.76, 0.76, 0.77), 0.24)
    M['solenoid'] = satin('CAR_solenoid', 0.02, 0.30, 0.6)
    M['rubber'] = plain('CAR_rubber', (0.012, 0.012, 0.013), 0.85)
    M['frame_dark'] = metal('CAR_frame_dark', (0.16, 0.16, 0.17), 0.42)
    M['fitting'] = metal('CAR_fitting', (0.80, 0.80, 0.82), 0.12)
    return M


def skirt_rubber(name='CAR_skirt'):
    """Flexible ground seal: near-black matte rubber with soft vertical pleats (bump only), so it reads as a
    curtain, not a rigid box."""
    m, g, out = L.new_material(name)
    tc = g.n('ShaderNodeTexCoord')
    wv = g.n('ShaderNodeTexWave', {'Scale': 9.0, 'Distortion': 1.5, 'Detail': 2.0})
    wv.wave_type = 'BANDS'
    wv.bands_direction = 'X'
    g.link(tc.outputs['Object'], wv.inputs['Vector'])
    wv2 = g.n('ShaderNodeTexWave', {'Scale': 9.0, 'Distortion': 1.5, 'Detail': 2.0})
    wv2.wave_type = 'BANDS'
    wv2.bands_direction = 'Y'
    g.link(tc.outputs['Object'], wv2.inputs['Vector'])
    h = g.math('ADD', wv.outputs['Fac'], wv2.outputs['Fac'])
    bp = g.n('ShaderNodeBump', {'Strength': 0.35, 'Distance': 0.004})
    g.link(h, bp.inputs['Height'])
    p = L.principled(g, Base_Color=(0.016, 0.016, 0.017, 1), Roughness=0.74, Specular_IOR_Level=0.3,
                     Sheen_Weight=0.35, Sheen_Roughness=0.45)
    g.link(bp.outputs['Normal'], p.inputs['Normal'])
    g.link(p, out.inputs['Surface'])
    return m


def carbon_wound(name='CAR_carbon_wound'):
    """Filament-wound carbon under a glossy resin coat, in the tank's object space (+X = its axis).
    Object custom properties 'cylhalf' (half cylinder length) and 'tankr' (radius) set where the domes start.
    Cylinder: hoop tows (6 mm pitch). Domes: +-18 degree helical tows forming the winding diamond pattern.
    The highlight is stretched along the fibres (anisotropic, tangent around the axis)."""
    m, g, out = L.new_material(name)
    tc = g.n('ShaderNodeTexCoord')
    ob_ch = g.n('ShaderNodeAttribute', attribute_type='OBJECT', attribute_name='cylhalf')
    ob_r = g.n('ShaderNodeAttribute', attribute_type='OBJECT', attribute_name='tankr')
    P = tc.outputs['Object']
    x, y, z = g.sep(P)
    ang = g.math('ARCTAN2', z, y)
    # hoop tows
    k_h = 2 * math.pi / 0.006
    hoop = g.math('SINE', g.math('MULTIPLY', x, k_h))
    # helical tows: u = x cos a +- ang r sin a
    a = math.radians(18)
    arc = g.math('MULTIPLY', ang, ob_r.outputs['Fac'])
    u1 = g.math('ADD', g.math('MULTIPLY', x, math.cos(a)), g.math('MULTIPLY', arc, math.sin(a)))
    u2 = g.math('SUBTRACT', g.math('MULTIPLY', x, math.cos(a)), g.math('MULTIPLY', arc, math.sin(a)))
    k_t = 2 * math.pi / 0.024
    s1 = g.math('SINE', g.math('MULTIPLY', u1, k_t))
    s2 = g.math('SINE', g.math('MULTIPLY', u2, k_t))
    diamond = g.math('GREATER_THAN', g.math('MULTIPLY', s1, s2), 0.0)
    # tow edges (thin dark lines where a band changes) for the bump
    e1 = g.math('POWER', g.math('ABSOLUTE', s1), 0.15)
    e2 = g.math('POWER', g.math('ABSOLUTE', s2), 0.15)
    edge_hel = g.math('MULTIPLY', e1, e2)
    edge_hoop = g.math('POWER', g.math('ABSOLUTE', hoop), 0.25)
    # dome mask
    dome = g.maprange(g.math('ABSOLUTE', x), g.math('SUBTRACT', ob_ch.outputs['Fac'], 0.01),
                      g.math('ADD', ob_ch.outputs['Fac'], 0.02), 0.0, 1.0)
    tone_hel = g.math('MULTIPLY_ADD', diamond, 0.55, 0.45)
    tone_hoop = g.math('MULTIPLY_ADD', g.math('GREATER_THAN', hoop, 0.0), 0.25, 0.75)
    tone = g.n('ShaderNodeMix', data_type='FLOAT')
    g.link(dome, tone.inputs['Factor'])
    g.link(tone_hoop, tone.inputs['A'])
    g.link(tone_hel, tone.inputs['B'])
    edge = g.n('ShaderNodeMix', data_type='FLOAT')
    g.link(dome, edge.inputs['Factor'])
    g.link(edge_hoop, edge.inputs['A'])
    g.link(edge_hel, edge.inputs['B'])
    nz = g.n('ShaderNodeTexNoise', {'Scale': 9.0, 'Detail': 2.0})
    g.link(P, nz.inputs['Vector'])
    shade = g.math('MULTIPLY', tone.outputs['Result'], g.maprange(nz.outputs['Fac'], 0.3, 0.7, 0.8, 1.15))
    col = g.mixrgb(shade, (0.008, 0.008, 0.009, 1), (0.040, 0.040, 0.043, 1))
    bp = g.n('ShaderNodeBump', {'Strength': 0.12, 'Distance': 0.0004})
    g.link(edge.outputs['Result'], bp.inputs['Height'])
    tg = g.n('ShaderNodeTangent', direction_type='RADIAL', axis='X')
    rough = g.maprange(tone.outputs['Result'], 0.4, 1.0, 0.42, 0.26)
    p = L.principled(g, Metallic=0.0, Coat_Weight=1.0, Coat_Roughness=0.04, Anisotropic=0.6,
                     Specular_IOR_Level=0.5)
    g.link(col, p.inputs['Base Color'])
    g.link(rough, p.inputs['Roughness'])
    g.link(bp.outputs['Normal'], p.inputs['Normal'])
    g.link(tg.outputs['Tangent'], p.inputs['Tangent'])
    g.link(p, out.inputs['Surface'])
    return m
