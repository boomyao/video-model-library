"""Portable Blender packaging helpers. Original code: MIT, boomyao, 2026."""
from pathlib import Path
import json, math
import bpy
from mathutils import Vector

def _layers(layer):
    yield layer
    for c in layer.children: yield from _layers(c)

def organize():
    scene=bpy.context.scene
    excluded={l.name:l.exclude for l in _layers(bpy.context.view_layer.layer_collection)}
    roots=list(scene.collection.children)
    asset=bpy.data.collections.new('ASSET');scene.collection.children.link(asset)
    studio=bpy.data.collections.new('STUDIO');scene.collection.children.link(studio)
    for c in roots:
        parent=studio if c.name.startswith(('Lights','Cameras')) else asset
        scene.collection.children.unlink(c);parent.children.link(c)
    for o in list(scene.collection.objects):
        (studio if o.type in {'LIGHT','CAMERA'} else asset).objects.link(o)
        scene.collection.objects.unlink(o)
    for l in _layers(bpy.context.view_layer.layer_collection):
        if l.name in excluded:l.exclude=excluded[l.name]
    bpy.context.view_layer.update()
    return asset,studio

def frame_scene(asset,studio,direction=(1,-1.6,1.05)):
    scene=bpy.context.scene
    pts=[]
    for o in asset.all_objects:
        if o.type=='MESH' and not o.hide_render and o.visible_get():
            pts.extend(o.matrix_world@Vector(p) for p in o.bound_box)
    if not pts:raise RuntimeError('No visible mesh bounds')
    lo=Vector([min(v[i] for v in pts) for i in range(3)])
    hi=Vector([max(v[i] for v in pts) for i in range(3)])
    center=(lo+hi)/2;span=max(hi-lo)
    for o in list(studio.all_objects):bpy.data.objects.remove(o,do_unlink=True)
    cam=bpy.data.objects.new('Preview_Camera',bpy.data.cameras.new('Preview_Camera'));studio.objects.link(cam)
    cam.location=center+Vector(direction).normalized()*span*3
    cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
    right=cam.rotation_euler.to_quaternion()@Vector((1,0,0))
    up=cam.rotation_euler.to_quaternion()@Vector((0,1,0))
    px=[(p-center).dot(right) for p in pts];py=[(p-center).dot(up) for p in pts]
    cam.data.type='ORTHO'
    cam.data.ortho_scale=max(max(px)-min(px),(max(py)-min(py))*1.5)*1.16
    cam.data.clip_end=max(100,span*20)
    cam.data.clip_start=max(0.00001,span/10000);scene.camera=cam
    for name,offset,power,color in [
        ('Key',(-1.5,-2,2.5),150,(1,.94,.86)),
        ('Fill',(2,-.5,1.1),100,(.78,.87,1)),
        ('Rim',(0,2,2),180,(1,1,1))]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power*span*span;data.shape='DISK';data.size=span*1.4
        data.color=color
        ob=bpy.data.objects.new(name,data);studio.objects.link(ob)
        ob.location=center+Vector(offset)*span;ob.rotation_euler=(center-ob.location).to_track_quat('-Z','Y').to_euler()
    world=bpy.data.worlds.new('Release_Studio');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(.12,.15,.20,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
    scene.world=world
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active;space.region_3d.view_distance=span*2
                space.region_3d.view_location=center;space.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
                space.clip_start=cam.data.clip_start;space.clip_end=cam.data.clip_end

def save(out,name='start',render=False,keep_camera=False,direction=(1,-1.6,1.05)):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    scene=bpy.context.scene
    asset=bpy.data.collections.get('ASSET')
    if asset is None:asset,studio=organize()
    else:studio=bpy.data.collections['STUDIO']
    if not keep_camera:frame_scene(asset,studio,direction)
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32
    scene.cycles.use_denoising=True;scene.cycles.use_adaptive_sampling=True
    scene.cycles.adaptive_threshold=.06
    scene.render.resolution_x=960;scene.render.resolution_y=640;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
    scene['asset_author']='boomyao';scene['model_license']='CC-BY-4.0; see SOURCES.txt for third-party exceptions'
    scene['source_repository']='https://github.com/boomyao/video-model-library'
    # Do not ship embedded scripts or runtime frame callbacks.
    for t in list(bpy.data.texts):bpy.data.texts.remove(t)
    bpy.app.handlers.frame_change_pre.clear();bpy.app.handlers.frame_change_post.clear()
    hidden=[]
    for layer in _layers(bpy.context.view_layer.layer_collection):
        if layer.exclude:
            c=layer.collection;hidden.append((c,c.hide_render,c.hide_viewport))
            c.hide_render=True;c.hide_viewport=True
    bpy.ops.file.pack_all()
    scene.render.filepath='//renders/'+name
    bpy.ops.wm.save_as_mainfile(filepath=str((out/(name+'.blend')).resolve()),compress=True)
    if render:
        scene.render.filepath=str((out/(name+'.png')).resolve())
        bpy.ops.render.render(write_still=True)
    info={'blender':bpy.app.version_string,'objects':len(scene.objects),
          'meshes':len([o for o in scene.objects if o.type=='MESH']),
          'materials':len(bpy.data.materials),'units':scene.unit_settings.scale_length,
          'external_images':[i.filepath for i in bpy.data.images if i.source=='FILE' and not i.packed_file]}
    (out/(name+'-build.json')).write_text(json.dumps(info,indent=2),encoding='utf-8')
    scene.render.filepath='//renders/'+name
    for c,hr,hv in hidden:c.hide_render=hr;c.hide_viewport=hv
    print('RELEASE_SAVED',name,info,flush=True)
