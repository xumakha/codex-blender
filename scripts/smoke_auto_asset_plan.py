"""Real planner integration: missing icy material must be generated/exported before screenplay."""
import json
from pathlib import Path
import shutil
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codex_blender import studio,jobs
from codex_blender.config import ROOT,assets_dir

run=ROOT/'outputs'/'auto-asset-plan-v2';root=run/'assets';root.mkdir(parents=True,exist_ok=True)
for source,target in [('generated/universal-interior-v1/core-cube.glb','core-cube.glb'),
    ('generated/universal-interior-v1/core-sphere.glb','core-sphere.glb')]:shutil.copyfile(assets_dir()/source,root/target)
studio.DATA=run/'data'
draft=studio.Draft(title='QA Automatic missing ice',prompt='Video 2 giây, 4 fps, khung ngang 320x180. Một khối băng hình lập phương màu xanh trong suốt quay chậm trên bệ ghép từ hai khối lập phương màu kem. Không có người, chữ hoặc vật trang trí. Nếu thư viện thiếu vật liệu băng thì tự tạo từ khối có sẵn, không báo thiếu assets.',width=320,height=180,fps=4,samples=4)
project=studio.create_project(draft);pid=project['id'];print('PLANNING',pid,flush=True)
(run/'project-id.txt').write_text(pid,encoding='ascii')
studio.plan_scene(pid,draft,root)
project=studio.read_project(pid)
assert project['state']=='ready',project.get('error')
preparation=project['asset_preparation'];assert preparation['ready']
generated=list((root/'generated'/'auto-prepared').glob('*/assembly.glb'))
assert generated,'Expected automatic material generation before screenplay'
scene=studio.scene_for_render(studio.Draft.model_validate(project['draft']))
job=jobs.submit(scene,'video',root);deadline=time.monotonic()+180
while time.monotonic()<deadline:
    state=jobs.status(job['id'])
    if state['state'] in ('completed','failed'):break
    time.sleep(1)
assert state['state']=='completed',state
result={'passed':True,'generated_assemblies':len(generated),'video':state['artifacts']['video.mp4'],'project':pid}
(run/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
