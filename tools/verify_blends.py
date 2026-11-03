from pathlib import Path
import bpy,sys,json,shutil
root=Path(sys.argv[sys.argv.index('--')+1]).resolve()
report=[]
for path in sorted(root.glob('*/*.blend')):
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    sc=bpy.context.scene
    meshes=[o for o in sc.objects if o.type=='MESH']
    errors=[]
    if not meshes:errors.append('no meshes')
    if not bpy.data.collections.get('ASSET'):errors.append('missing ASSET')
    if not sc.camera:errors.append('missing camera')
    if bpy.data.libraries:errors.append('linked libraries')
    for im in bpy.data.images:
        if im.source=='FILE' and not im.packed_file:errors.append('unpacked image: '+im.name)
    for f in bpy.data.fonts:
        if f.filepath and f.filepath!='<builtin>' and not f.packed_file:errors.append('unpacked font: '+f.name)
    if not sc.render.filepath.startswith('//'):errors.append('nonportable render path')
    if len(bpy.data.texts):errors.append('embedded scripts')
    invalid=[d.data_path for o in sc.objects if o.animation_data for d in o.animation_data.drivers if not d.driver.is_valid]
    if invalid:errors.append('invalid drivers: '+str(invalid))
    if 'force-touch' in path.parent.name:
        animated=[o for o in sc.objects if o.animation_data and o.animation_data.action]
        sc.frame_set(1);a=[tuple(o.location) for o in animated]
        sc.frame_set(15);b=[tuple(o.location) for o in animated]
        if a==b:errors.append('press animation did not move')
    # Ensure the collection can also be appended into a fresh scene.
    count=len(meshes)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(path),link=False) as (src,dst):dst.collections=['ASSET']
    for coll in dst.collections:
        if coll:bpy.context.scene.collection.children.link(coll)
    if not list(bpy.context.scene.objects):errors.append('append produced empty asset')
    row={'file':path.parent.name+'/'+path.name,'meshes':count,'append_ok':not errors,'errors':errors}
    report.append(row);print(json.dumps(row),flush=True)
(root/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
if any(r['errors'] for r in report):raise RuntimeError('Validation failed')
print('ALL_VALID',len(report),flush=True)
