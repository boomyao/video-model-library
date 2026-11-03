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
import build_macstudio
sys.argv=['blender','--','--out',str(out/'start.blend')]
build_macstudio.main()
from msbuild import state
save(out,render=a.render,keep_camera=True)
state.apply_shot('exploded')
save(out,'exploded',render=a.render,keep_camera=True)
state.apply_shot('cutaway')
save(out,'cutaway',render=a.render,keep_camera=True)
