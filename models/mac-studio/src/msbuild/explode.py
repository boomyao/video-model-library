import bpy
from .util import MM

LAYERS = [
    ('XP_Ring', 0.0),
    ('XP_Cover', 44.0),
    ('XP_PSU', 86.0),
    ('XP_Frame', 126.0),
    ('XP_Board', 168.0),
    ('XP_Thermal', 212.0),
    ('XP_Blowers', 287.0),
    ('XP_Housing', 408.0),
]


def build(coll):
    ctrl = bpy.data.objects.new('EXPLODE_CTRL', None)
    ctrl.empty_display_type = 'ARROWS'
    ctrl.empty_display_size = 0.03
    coll.objects.link(ctrl)
    ctrl['explode'] = 0.0
    ui = ctrl.id_properties_ui('explode')
    ui.update(min=0.0, max=1.5, soft_min=0.0, soft_max=1.0, description='0 = assembled, 1 = exploded')
    empties = {}
    for name, off in LAYERS:
        e = bpy.data.objects.new(name, None)
        e.empty_display_type = 'PLAIN_AXES'
        e.empty_display_size = 0.01
        coll.objects.link(e)
        e['explode_offset_mm'] = off
        fc = e.driver_add('location', 2)
        drv = fc.driver
        drv.type = 'SCRIPTED'
        v1 = drv.variables.new()
        v1.name = 'f'
        v1.type = 'SINGLE_PROP'
        v1.targets[0].id_type = 'OBJECT'
        v1.targets[0].id = ctrl
        v1.targets[0].data_path = '["explode"]'
        v2 = drv.variables.new()
        v2.name = 'off'
        v2.type = 'SINGLE_PROP'
        v2.targets[0].id_type = 'OBJECT'
        v2.targets[0].id = e
        v2.targets[0].data_path = '["explode_offset_mm"]'
        drv.expression = 'f * off * 0.001'
        empties[name] = e
    return ctrl, empties


def parent(objs, empty):
    for o in objs:
        if o.parent is None:
            o.parent = empty
            o.matrix_parent_inverse = empty.matrix_world.inverted()
