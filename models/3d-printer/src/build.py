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
import studio,machine,整机,电机模型
studio.setup(samples=32)
w=整机.整机(light=False);w.pose(x=0,y=0,z=50)
save(out,render=a.render,direction=(1,-1.8,1))
studio.setup(samples=32)
m=machine.Machine();m.pose(x=25,y=0,z=10)
save(out,'gantry',render=False,direction=(.8,-1.5,1.2))
studio.setup(samples=32)
m=电机模型.Motor()
save(out,'stepper-cutaway',render=a.render,direction=(-.9,1.3,1.2))
