"""Save the prior elevator sample's character and building as reusable Blender assets."""
import json
from pathlib import Path
import time
from codex_blender import studio, library
from codex_blender.models import SceneSpec
from codex_blender.jobs import status

jid='5e1f99ad796c4ee58e7a84d285749ebe'
old=status(jid)
scene=SceneSpec.model_validate_json(Path(old['artifacts']['scene.json']).read_text(encoding='utf-8'))
names=[o.name for o in scene.objects]
start=next(i for i,name in enumerate(names) if name.startswith('Shoe'))
entries=[('Nhà phát minh áo vàng',names[start:],'Nhân vật hoạt hình 3D tóc đen ngắn, sơ mi vàng nhạt, quần nâu, giày đen; tư thế chỉ tay lên cao. GLB tĩnh, gốc giữa đáy.', ['nhân vật','khoa học','hoạt hình']),
         ('Tòa nhà 10 tầng cắt lớp',names[:start],'Mô hình kiến trúc 10 tầng xanh nhạt, cửa sổ, cầu thang gỗ và mái kem; mặt trước mở để quan sát bên trong. GLB tĩnh, gốc giữa đáy.', ['kiến trúc','cầu thang','khoa học'])]
existing={a['name'] for a in library.catalog()}
project=studio.create_project(studio.Draft(title='Ngôi nhà 10 tầng · Thư viện mẫu',prompt=scene.prompt,script=scene.content,scene=scene,duration=5,width=540,height=960,font=scene.font,music=scene.audio))
studio.save_project(project['id'],current_job=jid,jobs=[jid])
for name,names,description,tags in entries:
    if name in existing:
        print('Already saved:',name,flush=True)
        continue
    studio.export_asset(project['id'],jid,name,names,description,tags)
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        data=studio.read_project(project['id'])
        if data['state']=='error':raise RuntimeError(data['error'])
        if data['state']=='ready':break
        time.sleep(1)
    else:raise TimeoutError('Asset export timed out')
    print(json.dumps({'name':name,'path':data['last_saved_asset']},ensure_ascii=False),flush=True)
print('Project:',project['id'])
