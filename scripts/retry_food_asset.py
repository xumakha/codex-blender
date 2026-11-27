"""Retry the failed food preparation using the project's original prompt/library."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codex_blender import studio,director
from codex_blender.config import ROOT,assets_dir
from codex_blender.library import catalog
from codex_blender.asset_preparation import AssetPreparation,model_inventory
from codex_blender.asset_generation import generate_missing,generation_context

if len(sys.argv)!=2:
    raise SystemExit('Usage: python scripts/retry_food_asset.py PROJECT_ID')
pid=sys.argv[1]
project=studio.read_project(pid)
assert project['state']=='error','Do not interfere with active planning'
data=project['asset_preparation']
preparation=AssetPreparation.model_validate({k:data[k] for k in ('requirements','constraints')})
food=next(r for r in preparation.requirements if r.id=='food')
draft=studio.Draft.model_validate(project['draft']);root=assets_dir()
models=model_inventory(catalog(root),root)
compact,details=generation_context(food,models,root)
print('CONTEXT_CHARS',len(json.dumps({'models':compact,'reference_details':details},ensure_ascii=False)),flush=True)
generate_missing(pid,draft,root,food,models,director.call_planner)
data.update(preparation.model_dump(mode='json'))
data['generation_state']='pending'
updates={'asset_preparation':data,'planning_detail':None}
if 'generate-food' in str(project.get('error','')):
    updates.update(state='idle',error=None)
studio.save_project(pid,**updates)
(studio.project_path(pid)/'asset-preparation.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
report={'passed':True,'project':pid,'food_components':len(food.objects),'assets':[o.asset for o in food.objects if o.kind=='model']}
(ROOT/'outputs'/'food-generation-retry.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report),flush=True)
