"""Exercise Library First with a real screenplay and Blender preview."""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codex_blender import studio,jobs
from codex_blender.config import ROOT,assets_dir,validate_assets

RUN=ROOT/'outputs'/'library-first-smoke'
RUN.mkdir(parents=True,exist_ok=True)
studio.DATA=RUN/'data'
draft=studio.Draft(title='QA Library First',prompt='Một bánh răng vàng quay tròn trên bệ lắp từ hai khối lập phương màu kem. Không có nhân vật hoặc vật trang trí. Video 2 giây, 6 fps, khung ngang 320x180. Camera cố định, chỉ có một nhạc nền từ đầu tới cuối.',
                  width=320,height=180,fps=6,samples=4,asset_generation_mode='library_first')
project=studio.create_project(draft);pid=project['id']
(RUN/'project-id.txt').write_text(pid,encoding='ascii')
print('PLANNING',pid,flush=True)
studio.plan_scene(pid,draft,assets_dir())
project=studio.read_project(pid)
if project['state']!='ready':raise RuntimeError(project.get('error'))
assert project['generation']['shot'] == len(project['draft']['scene']['shots'])
scene=studio.scene_for_render(studio.Draft.model_validate(project['draft']))
validate_assets(scene,assets_dir())
used=sorted({o.asset for s in scene.shots for o in s.objects if o.kind=='model'})
print('REUSED',used,flush=True)
job=jobs.submit(scene,'preview',assets_dir())
print('RENDER',job['id'],flush=True)
deadline=time.monotonic()+180
while time.monotonic()<deadline:
    status=jobs.status(job['id'])
    if status['state'] in ('completed','failed'):break
    time.sleep(1)
assert status['state']=='completed',status
(RUN/'result.json').write_text(json.dumps({'passed':True,'project':pid,'job':job['id'],'used_assets':used,'preview':status['artifacts']['preview.png']},indent=2),encoding='utf-8')
print('PASS',status['artifacts']['preview.png'],flush=True)
