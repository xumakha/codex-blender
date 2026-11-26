"""Live product smoke test for Codex CLI planning with an image and a reusable GLB."""
import json
from codex_blender import studio, library
from codex_blender.config import assets_dir

assets=library.catalog()
character=next(a['path'] for a in assets if a['name']=='Nhà phát minh áo vàng')
reference=next(a['path'] for a in assets if a['kind']=='image' and a['path'].startswith('references/'))
draft=studio.Draft(title='AI · Nhân vật dùng lại',prompt='Dùng mô hình Nhà phát minh áo vàng có sẵn. Nhân vật xoay toàn thân nhẹ khoảng 15 độ trên nền kem. Camera thấy toàn thân. Không thêm chữ. Chỉ một mô hình, không thêm nhân vật khác.',
    style='Màu sắc và ánh sáng 3D mềm, tham khảo ảnh đính kèm.',references=[reference],selected_assets=[character],duration=1,fps=4,width=160,height=284,samples=2)
project=studio.create_project(draft)
studio.save_project(project['id'],state='planning')
print('Planning project:',project['id'],flush=True)
studio.plan_scene(project['id'],draft,assets_dir())
result=studio.read_project(project['id'])
if result['state']!='ready':raise RuntimeError(result.get('error'))
scene=result['draft']['scene']
assert any(o['asset']==character for o in scene['objects']), 'Planner did not reuse selected model'
print(json.dumps({'passed':True,'project':project['id'],'objects':len(scene['objects']),'reused_model':character,'reference':reference},ensure_ascii=False,indent=2))
