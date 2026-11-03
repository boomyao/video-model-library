import bpy
from mathutils import Vector
from .shots import SHOTS, orbit


def build(coll):
    cams = {}
    for name, sh in SHOTS.items():
        c = sh['cam']
        cd = bpy.data.cameras.new('CAM_' + name)
        cd.lens = c['lens']
        cd.sensor_fit = 'HORIZONTAL'
        cd.sensor_width = 36.0
        cd.clip_start = 0.005
        cd.clip_end = 50.0
        cd.shift_y = c.get('shift_y', 0.0)
        cd.shift_x = c.get('shift_x', 0.0)
        ob = bpy.data.objects.new('CAM_' + name, cd)
        coll.objects.link(ob)
        loc = orbit(c['target'], c['dist'], c['az'], c['el'])
        ob.location = loc
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = (Vector(c['target']) - Vector(loc)).to_track_quat('-Z', 'Y')
        foc = bpy.data.objects.new('FOCUS_' + name, None)
        foc.empty_display_type = 'SPHERE'
        foc.empty_display_size = 0.004
        foc.location = c.get('focus', c['target'])
        coll.objects.link(foc)
        cd.dof.use_dof = c.get('fstop') is not None
        cd.dof.focus_object = foc
        if c.get('fstop'):
            cd.dof.aperture_fstop = c['fstop']
            cd.dof.aperture_blades = 7
            cd.dof.aperture_rotation = 0.2
        cams[name] = ob
    return cams
