"""Real Blender export/render proof for generated variants, extracted parts and a new skeleton."""
import copy
import json
from pathlib import Path
import shutil
import struct
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codex_blender import studio,jobs
from codex_blender.config import ROOT,assets_dir
from codex_blender.library import catalog
from codex_blender.asset_preparation import PreparedRequirement,model_inventory,check_models
from codex_blender.asset_generation import GeneratedAssembly,generate_missing,inspect_reference
from codex_blender.models import SceneSpec

RUN=ROOT/'outputs'/'auto-preparation-smoke';RUN.mkdir(parents=True,exist_ok=True)
root=RUN/'assets';root.mkdir(exist_ok=True)
for source,target in [('generated/story-world-v1/character-inventor.glb','inventor.glb'),
    ('generated/universal-interior-v1/interior-fridge.glb','fridge.glb'),
    ('generated/universal-interior-v1/core-cube.glb','core-cube.glb')]:shutil.copyfile(assets_dir()/source,root/target)
studio.DATA=RUN/'data';draft=studio.Draft(prompt='Inventor with rig, opening fridge, transparent cyan ice and a fly. Snow mountain.')
project=studio.create_project(draft);pid=project['id']
character=inspect_reference('inventor.glb',root)['nodes']
arm=[n['name'] for n in character if any(k in n['name'] for k in ('forearm','hand','thumb')) and n['center_z_up'][0]>0]
body=[n['name'] for n in character if n['name'] not in arm]
fridge=inspect_reference('fridge.glb',root)['nodes']
doors=[n['name'] for n in fridge if any(k in n['name'].casefold() for k in ('door','pull','note','magnet'))]
shell=[n['name'] for n in fridge if n['name'] not in doors]
pivot=[.36,-.08,.83]
objects=[{'name':'Hero','kind':'empty','location':[-1.2,0,0],'scale':[.8,.8,.8]},
 {'name':'Body','kind':'model','asset':'inventor.glb','asset_nodes':body,'parent':'Hero','location':[0,0,0]},
 {'name':'Hand','kind':'model','asset':'inventor.glb','asset_nodes':arm,'asset_pivot':pivot,'parent':'Hero','location':pivot},
 {'name':'Fridge','kind':'empty','location':[1.1,.3,0],'scale':[.68,.68,.68]},
 {'name':'Shell','kind':'model','asset':'fridge.glb','asset_nodes':shell,'parent':'Fridge','location':[0,0,0]},
 {'name':'Door','kind':'model','asset':'fridge.glb','asset_nodes':doors,'asset_pivot':[.5,-.36,0],'parent':'Fridge','location':[.5,-.36,0]},
 {'name':'Ice','kind':'model','asset':'core-cube.glb','location':[.35,-.5,.23],'scale':[.45,.45,.45],
  'recolor':'#68D5FF','transmission':.95,'roughness':.08,'metallic':0},
 {'name':'Snow','kind':'cone','location':[.1,.8,.5],'scale':[.35,.35,.5],'color':'#F5F8FF','bevel':.03},
 {'name':'Fly','kind':'empty','location':[0,-.8,1.1],'scale':[.8,.8,.8]},
 {'name':'FlyBody','kind':'sphere','parent':'Fly','location':[0,0,0],'scale':[.09,.13,.09],'color':'#384044'},
 {'name':'FlyWing','kind':'sphere','parent':'Fly','location':[-.11,0,.08],'scale':[.12,.08,.018],
  'color':'#BCEAFF','transmission':.8,'repeat':{'count':2,'offset':[.22,0,0]}}]
rigs=[{'name':'InventorRig','root':'Hero','bones':[
 {'name':'Chest','head':[0,0,.6],'tail':[0,0,1.05],'objects':['Body']},
 {'name':'RightArm','parent':'Chest','head':pivot,'tail':[.46,-.1,1.08],'objects':['Hand']}]}]
design=GeneratedAssembly(reference_assets=['inventor.glb','fridge.glb','core-cube.glb'],
    description='Reference-based generated assembly with separated parts, skeleton and ice material.',ground=False,objects=objects,rigs=rigs)
requirement=PreparedRequirement(id='demo',label='Rig, door, ice and generated details',source=draft.prompt,
    role='prop',reason='Exercise automatic missing asset generation',missing='Generate moving parts, skeleton, ice and new details')
models=model_inventory(catalog(root),root)
def planner(*args):args[-1](design);return design
generate_missing(pid,draft,root,requirement,models,planner)
assert not requirement.missing and requirement.rigs
allowed={a['path'] for a in catalog(root) if a['kind']=='model'};check_models(requirement.objects,allowed,root)
raw=requirement.model_dump(mode='json')
raw['rigs'][0]['bones'][1]['keyframes']=[{'time':1,'rotation':[45,0,0]}]
next(o for o in raw['objects'] if o['name']=='Door')['keyframes']=[{'time':1,'rotation':[0,0,-80]}]
scene=SceneSpec(title='Generated assembly smoke',duration=1,fps=4,width=640,height=360,samples=4,ground=False,
    camera={'location':[3,-6,3],'target':[0,0,.85],'lens':48},objects=raw['objects'],rigs=raw['rigs'],audio_mode='music_only')
job=jobs.submit(scene,'video',root);deadline=time.monotonic()+180
while time.monotonic()<deadline:
    state=jobs.status(job['id'])
    if state['state'] in ('completed','failed'):break
    time.sleep(1)
assert state['state']=='completed',state
result={'passed':True,'generated_components':len([o for o in requirement.objects if o.kind=='model']),
        'rigs':len(requirement.rigs),'video':state['artifacts']['video.mp4'],'job':job['id']}
(RUN/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
