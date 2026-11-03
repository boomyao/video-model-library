import bpy
from . import dims as D
from .util import MM
from .thermal import PED_Z1
from .soc import Z0 as SOC_Z0


def instance(name, src, coll, loc, rot_z=0.0):
    e = bpy.data.objects.new(name, None)
    e.instance_type = 'COLLECTION'
    e.instance_collection = src
    e.location = loc
    e.rotation_euler = (0.0, 0.0, rot_z)
    e.empty_display_size = 0.02
    coll.objects.link(e)
    return e


def build(C, mats):
    tz = D.BOARD_Z + D.BOARD_T
    for n in ('Thermal_Ultra', 'Thermal_Max'):
        C[n].instance_offset = (0.0, 4.0 * MM, tz * MM)
    instance('SC_Thermal_Max', C['Thermal_Max'], C['Showcase_Thermal'], (-0.100, 0.0, 0.0))
    instance('SC_Thermal_Ultra', C['Thermal_Ultra'], C['Showcase_Thermal'], (0.100, 0.0, 0.0))
    sx, sy = D.SOC_CENTER
    C['SoC_Ultra_Variant'].instance_offset = (sx * MM, sy * MM, SOC_Z0 * MM)
    C['SoC_Max_Variant'].instance_offset = (sx * MM, sy * MM, SOC_Z0 * MM)
    instance('SC_Chip_Ultra', C['SoC_Ultra_Variant'], C['Showcase_Chip'], (0.0, 0.0, 0.0))
    C['Blowers'].instance_offset = (0.0, D.BLOWER_CY * MM, D.SHROUD_Z0 * MM)
    instance('SC_Blowers', C['Blowers'], C['Showcase_Blower'], (0.0, 0.0, 0.0))
    return True
