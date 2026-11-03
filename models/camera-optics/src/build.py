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
import module as MO,lens as LN,phone as PH
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system='METRIC'
reset()
m=MO.Module(scale=.001,cut=False,name='camera')
save(out,render=a.render,direction=(1,-1.6,1.2))
reset()
m=MO.Module(scale=.001,cut=True,name='camera_cut')
save(out,'cutaway',render=a.render,direction=(.6,-2,.7))
reset()
PH.Phone(scale=.001,modules=True,name='phone')
save(out,'phone',render=False,direction=(.6,-1.3,2))
reset()
d=LN.load();LN.build_stack(d,scale=.001,cut=True)
LN.build_rays(d,scale=.001)
save(out,'lens-rays',render=a.render,direction=(.05,-2,.1))
