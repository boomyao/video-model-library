import math

ASSEMBLY = ['Exterior_Housing', 'Rear_Grille', 'Foot_Base', 'PSU', 'Internal_Frame', 'Logic_Board',
            'SoC_Package', 'Thermal_Ultra', 'Thermal_Max', 'Blowers', 'Antennas_Ports']


def orbit(target, dist, az_deg, el_deg):
    az = math.radians(az_deg)
    el = math.radians(el_deg)
    return (target[0] + dist * math.sin(az) * math.cos(el),
            target[1] - dist * math.cos(az) * math.cos(el),
            target[2] + dist * math.sin(el))


SHOTS = {
    'hero': dict(
        cam=dict(target=(0.0, 0.0, 0.043), dist=1.34, az=-34.0, el=16.0, lens=85.0, fstop=11.0, shift_y=0.03),
        rig='dark', variant='ultra', explode=0.0, cut=[], show='assembly', samples=512),
    'foot_macro': dict(
        cam=dict(target=(0.0405, -0.0705, 0.0045), dist=0.095, az=-5.0, el=-30.0, lens=100.0, fstop=9.0,
                 focus=(0.0405, -0.0705, 0.0045)),
        rig='dark', variant='ultra', explode=0.0, cut=[], show='assembly', samples=768, hole_segments=40,
        extra_lights=['foot'], hide=['Floor_Dark']),
    'exploded': dict(
        cam=dict(target=(0.0, 0.0, 0.250), dist=1.50, az=-32.0, el=14.0, lens=50.0, fstop=16.0),
        rig='dark', variant='ultra', explode=1.0, cut=[], show='assembly', samples=384, extra_lights=['cut']),
    'cutaway': dict(
        cam=dict(target=(0.0, 0.004, 0.044), dist=0.92, az=-24.0, el=24.0, lens=70.0, fstop=11.0),
        rig='dark', variant='ultra', explode=0.0, cut=['front', 'blower_top', 'board'], show='assembly', samples=512,
        extra_lights=['cut']),
    'blower': dict(
        cam=dict(target=(-0.046, -0.004, 0.0175), dist=0.33, az=-20.0, el=16.0, lens=100.0, fstop=6.3,
                 focus=(-0.048, -0.022, 0.0175)),
        rig='dark', variant='ultra', explode=0.0, cut=['blower_side'], show='showcase_blower', samples=512,
        extra_lights=['blower']),
    'chip': dict(
        cam=dict(target=(0.0, 0.0, 0.0012), dist=0.27, az=-24.0, el=33.0, lens=100.0, fstop=8.0,
                 focus=(0.0, -0.004, 0.0018)),
        rig='dark', variant='ultra', explode=0.0, cut=[], show='showcase_chip', samples=768, extra_lights=['chip']),
    'thermal_compare': dict(
        cam=dict(target=(0.0, 0.03, 0.022), dist=0.92, az=-22.0, el=27.0, lens=70.0, fstop=16.0),
        rig='dark', variant='both', explode=0.0, cut=[], show='showcase_thermal', samples=512,
        extra_lights=['thermal'], hide=['TU_Module_Sheet', 'TM_Module_Sheet', 'TU_Mount_Screws', 'TM_Mount_Screws']),
    'hero_light': dict(
        cam=dict(target=(0.0, 0.0, 0.041), dist=1.18, az=-34.0, el=16.0, lens=85.0, fstop=11.0, shift_y=0.025),
        rig='light', variant='ultra', explode=0.0, cut=[], show='assembly', samples=384),
}
