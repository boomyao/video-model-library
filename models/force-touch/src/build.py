"""Run: blender -b --factory-startup --disable-autoexec --python build.py -- --out DIR [--render]"""
from pathlib import Path
import sys, argparse
import bpy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE/'lib'))
sys.path.insert(0,str(HERE.parents[2]/'tools'))
from release_scene import save
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--render',action='store_true')
a=p.parse_args(args);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system='METRIC'
import module
m=module.build_module(gap=.3,floor=False)
for f,d in [(1,0),(12,0),(15,.12),(20,0),(48,0)]:
    m.shift(d);m.plate.keyframe_insert(data_path='location',frame=f)
bpy.context.scene.frame_end=48;bpy.context.scene.render.fps=24
bpy.context.scene.frame_set(1)
save(out,render=a.render,direction=(.7,-1.4,2.0))
