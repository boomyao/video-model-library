import os
import sys
import time
import argparse

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
for _k in [k for k in sys.modules if k == 'msbuild' or k.startswith('msbuild.')]:
    del sys.modules[_k]

from msbuild import materials, housing, foot, lights, cameras, explode, cutaway, state, util
from msbuild import psu, frame, board, soc, thermal, blowers, antennas, showcase, fx
from msbuild.util import col


def collections():
    names = ['Exterior_Housing', 'Rear_Grille', 'Foot_Base', 'PSU', 'Internal_Frame', 'Logic_Board',
             'SoC_Package', 'Thermal_Ultra', 'Thermal_Max', 'Blowers', 'Antennas_Ports',
             'Lights_Dark', 'Lights_Light', 'Lights_Extra_Foot', 'Lights_Extra_Cut', 'Lights_Extra_Thermal',
             'Lights_Extra_Chip', 'Lights_Extra_Blower', 'Cameras', 'Rig',
             'Showcase_Thermal', 'Showcase_Chip', 'Showcase_Blower', 'Showcase_FootSection', 'FX']
    C = {n: col(n) for n in names}
    C['SoC_Ultra_Variant'] = col('SoC_Ultra_Variant', C['SoC_Package'])
    C['SoC_Max_Variant'] = col('SoC_Max_Variant', C['SoC_Package'])
    return C


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(HERE, 'macstudio_base.blend'))
    ap.add_argument('--shot', default='hero')
    a = ap.parse_args(argv)
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = 'MacStudio'
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'MILLIMETERS'
    scene.unit_settings.scale_length = 1.0
    C = collections()
    mats = materials.get_all()

    ctrl, XP = explode.build(C['Rig'])
    H = housing.build(C['Exterior_Housing'], C['Antennas_Ports'], mats, os.path.join(HERE, 'assets'))
    util.link_to(H['grille_pts'], C['Rear_Grille'])
    grille_proxy = housing.grille_proxy(C['Rear_Grille'], H['plan'])
    F = foot.build(C['Foot_Base'], mats)
    P = psu.build(C['PSU'], mats)
    FR = frame.build(C['Internal_Frame'], mats)
    B = board.build(C['Logic_Board'], mats)
    S = soc.build(C['SoC_Ultra_Variant'], C['SoC_Max_Variant'], mats)
    TU = thermal.build(C['Thermal_Ultra'], mats, variant='ultra')
    TM = thermal.build(C['Thermal_Max'], mats, variant='max')
    BL = blowers.build(C['Blowers'], mats)
    AN = antennas.build(C['Antennas_Ports'], mats)

    explode.parent([H['housing'], H['logo'], grille_proxy] + H['inserts'] + AN['housing_mounted'], XP['XP_Housing'])
    explode.parent([F['cover']], XP['XP_Cover'])
    explode.parent([F['ring']], XP['XP_Ring'])
    explode.parent(P['objects'], XP['XP_PSU'])
    explode.parent(FR['objects'], XP['XP_Frame'])
    explode.parent(B['objects'] + S['objects'] + AN['board_mounted'], XP['XP_Board'])
    explode.parent(TU['objects'] + TM['objects'], XP['XP_Thermal'])
    explode.parent(BL['objects'], XP['XP_Blowers'])

    cut = cutaway.build_cutters(C['Rig'])
    for o in [H['housing'], H['logo'], F['cover'], F['ring']]:
        cutaway.add_cut(o, cut['front'], 'front')
    slabs = ['Logic_Board_PCB', 'Internal_Frame', 'Internal_Frame_Plate', 'TU_Module_Sheet', 'TM_Module_Sheet',
             'TU_Vapor_Chamber', 'TU_VC_Seam']
    for o in B['objects'] + FR['objects'] + TU['objects'] + TM['objects']:
        if o.name in slabs:
            cutaway.add_cut(o, cut['board'], 'board', solver='EXACT')
        elif o.name.startswith(('Board_', 'SSD_', 'Internal_Frame_Screws', 'TU_Spring', 'TM_Clamp', 'TU_Screws', 'TM_Screws',
                                'TU_Mount_Screws', 'TM_Mount_Screws')):
            cutaway.add_clip(o, 'board')
    for o in BL['shroud']:
        cutaway.add_cut(o, cut['blower_top'], 'blower_top', solver='EXACT')
        if o.name in ('Blower_Shroud_L', 'Blower_Bridge'):
            cutaway.add_cut(o, cut['blower_side'], 'blower_side', solver='EXACT')

    DK = lights.build_dark(C['Lights_Dark'])
    LT = lights.build_light(C['Lights_Light'])
    lights.build_foot_extra(C['Lights_Extra_Foot'], DK)
    lights.build_extras(C)
    cameras.build(C['Cameras'])
    showcase.build(C, mats)
    FXO = fx.build_base_fx(C, mats, F['cover'], F['pts'])

    for o in C['Rig'].objects:
        if o.type == 'MESH':
            o.hide_render = True

    root = bpy.data.objects.new('PRODUCT_ROOT', None)
    root.empty_display_type = 'CUBE'
    root.empty_display_size = 0.1
    root.location = (0.0, 0.0, 0.0475)
    C['Rig'].objects.link(root)
    bpy.context.view_layer.update()
    root['note'] = 'parent of the whole assembled product (explode layers, FX, hole points, cutters); pivot = product centre'
    inv = root.matrix_world.inverted()
    attach = list(XP.values()) + list(cut.values()) + [F['pts'], H['grille_pts'], FXO['inner_glow'], FXO['hole_streaks'],
                                                       FXO['bore_glow']]
    for o in attach:
        if o.parent is None:
            o.parent = root
            o.matrix_parent_inverse = inv

    state.apply_shot(a.shot)
    scene['build_seconds'] = round(time.time() - t0, 2)
    scene['build_script'] = 'build_macstudio.py'
    bpy.ops.wm.save_as_mainfile(filepath=a.out, compress=True)
    print('BUILD_OK', a.out, round(time.time() - t0, 1), 's')


if __name__ == '__main__':
    main()
