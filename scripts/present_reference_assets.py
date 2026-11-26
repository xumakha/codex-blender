"""Create the pack contact sheet, docs and a Studio project with the user's references."""
import html
import json
from pathlib import Path
from codex_blender.config import ROOT,assets_dir
from codex_blender.models import SceneSpec
from codex_blender.studio import Draft,create_project,read_project,save_project,ensure_idle

root=assets_dir()
folder=root/'generated'/'inventor-toy-v1'
data=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
assets={entry['slug']:entry for entry in data['assets']}
assert len(assets)==32
order=['inventor-cheer','inventor-smile','inventor-surprised','building-ten-floors','building-cutaway','elevator-shaft',
       'cabin-open','cabin-closed','pulley-assembly','electric-motor','counterweight','steel-cable',
       'floor-module','floor-cutaway','stair-flight','balcony','arched-entry','arched-window','stone-wall','tiled-floor','balcony-rail','water-tank',
       'sofa','desk-lamp','potted-plant','toolbox','wrench','screwdriver','wood-crate','blueprint-scroll','direction-sign','call-buttons']
cards=[]
for slug in order:
    entry=assets[slug]
    image=(root/entry['path']).with_suffix('.png').as_uri()
    cards.append(f'<article><img src="{image}" alt=""><h2>{html.escape(entry["name"])}</h2><p>{html.escape(slug)}</p></article>')
swatches=''.join(f'<i style="background:{v}"></i>' for k,v in data['palette'].items() if k in ['skin','cream','shirt','gold','copper','leather','hair','blue','steel','green'])
markup='''<!doctype html><html lang="vi"><meta charset="utf-8"><title>Toy Inventor — Blender asset kit</title><style>
*{box-sizing:border-box}body{margin:0;padding:55px;background:#f0e5dc;color:#493429;font-family:'Segoe UI',sans-serif;width:1920px}
header{display:flex;align-items:end;justify-content:space-between;margin-bottom:32px;border-bottom:2px solid #d2b99b;padding-bottom:25px}
h1{font-size:48px;margin:0;letter-spacing:-1.5px}header p{font-size:20px;margin:10px 0 0;color:#86624d}.swatches{display:flex;gap:8px}.swatches i{display:block;width:32px;height:32px;border-radius:7px;border:1px solid #0001}
main{display:grid;grid-template-columns:repeat(6,1fr);gap:17px}article{background:#f9f3ed;border-radius:15px;overflow:hidden;border:1px solid #d9c7b4;min-width:0}
img{width:100%;aspect-ratio:1;object-fit:contain;display:block}h2{font-size:17px;line-height:1.4;margin:13px 14px 5px;font-weight:650;min-height:48px}article p{font-size:13px;color:#9a795f;margin:0 14px 15px}
footer{font-size:18px;display:flex;justify-content:space-between;margin-top:30px;color:#927356}footer span{font-size:16px}
</style><header><div><h1>TOY INVENTOR / ASSET KIT</h1><p>32 mô hình 3D dựng bằng Blender · Nhân vật, kiến trúc, cơ khí & đạo cụ</p></div><div class="swatches">'''+swatches+'</div></header><main>'+''.join(cards)+'''</main><footer>GLB + BLEND + PNG<span>Tham khảo 4 ảnh mỹ thuật do người dùng cung cấp · Gốc giữa đáy · Mặt trước −Y · Z lên</span></footer></html>'''
run=ROOT/'outputs'/'inventor-toy-kit'
(run/'catalog.html').write_text(markup,encoding='utf-8')
doc='''# Toy Inventor — Bộ assets tham khảo

32 mô hình mesh dựng bằng Blender theo bốn ảnh tham khảo người dùng cung cấp: khối bo tròn, kính xanh, vàng mật ong, kem và nâu, nhân vật có kính phi công và ba lô bản vẽ.

Mỗi asset có `.glb` tự chứa, `.blend` chỉnh sửa được, `.png` thumbnail và `.asset.json` cho Studio. GLB giữ chất liệu và tên mesh. Tất cả là mô hình tĩnh; nhân vật chưa có rig hay blendshape. Biểu cảm/tư thế được cung cấp thành ba GLB riêng. Các cánh cửa, puly và đối trọng có tên riêng trong file Blender để dựng chuyển động tiếp.

Gốc tọa độ nằm giữa đáy, mặt trước hướng -Y và Z lên. Kích thước thật ghi trong manifest và mô tả từng asset; dùng các kích thước này khi đặt tỷ lệ cảnh. Tầng nhà lặp theo Z=2.3. Để giải thích chuyển động cơ khí, dùng cabin/puly/cáp/đối trọng riêng thay vì di chuyển toàn bộ giếng thang lắp sẵn.

Ảnh tham khảo gốc được giữ tại `references/inventor-toy-v1/`. Không có ảnh tham khảo nào được dùng làm mặt phẳng giả mô hình hay texture thay cho mesh. Bảng màu ở `manifest.json`.

## Danh sách

'''
for slug in order:
    entry=assets[slug]
    doc+=f'- **{entry["name"]}** — `{slug}.glb`, kích thước {entry["dimensions"]}.\n'
doc+='\nDựng lại bằng `python scripts/build_reference_assets.py`; kiểm tra bằng `python scripts/validate_reference_assets.py`. Chạy với môi trường Python có bpy của dự án.\n'
(folder/'README.md').write_text(doc,encoding='utf-8')
base='generated/inventor-toy-v1/'
def model(name,slug,loc,scale=1):
    return {'name':name,'kind':'model','asset':base+slug+'.glb','location':loc,'scale':[scale,scale,scale]}
scene=SceneSpec(title='Toy Inventor · Phong cách tham khảo',duration=5,fps=24,width=720,height=1280,samples=16,
    prompt='Cảnh trưng bày nhân vật nhà phát minh và hệ thống thang máy, cùng phong cách đồ chơi 3D bo tròn vàng–nâu–kem.',
    camera={'location':[8,-14,7],'target':[0,0,2.3],'lens':48,'end_location':[7.6,-13.5,7]},background='#EFE5DF',floor='#EFE5DF',
    objects=[model('NhaPhatMinh','inventor-cheer',[-1.1,-.75,0]),model('GiengThang','elevator-shaft',[1.0,.5,0],.48),
             model('ToaNha','building-ten-floors',[-2.3,1.7,0],.12),model('HopDungCu','toolbox',[-2.0,-1.1,0],.6),
             model('ChauCay','potted-plant',[2.4,-.4,0],.65),model('ThungGo','wood-crate',[2.2,1.8,0],.8)])
references=[p.relative_to(root).as_posix() for p in sorted((root/'references'/'inventor-toy-v1').glob('*.png'))]
style='Đồ chơi 3D bo tròn, tỷ lệ chibi, cạnh bevel rõ, chất liệu nhựa/đất sét mờ. Bảng màu: da đào #FFC18C, áo vàng #FFCF65, kem #F2D5AC, gỗ nâu #956044, da nâu #774A38, tóc đen #292733, kính xanh #4D91C4, điểm nhấn vàng #E9A62E. Ánh sáng studio mềm, nền kem, bóng tiếp xúc tự nhiên. Giữ nguyên thiết kế nhân vật và chất liệu của GLB; ưu tiên tái sử dụng các asset inventor-toy-v1.'
draft=Draft(title=scene.title,prompt=scene.prompt,style=style,references=references,selected_assets=[base+slug+'.glb' for slug in order],scene=scene,duration=5,fps=24,width=720,height=1280)
project_record=run/'studio-project.json'
if project_record.exists():
    previous=read_project(json.loads(project_record.read_text(encoding='utf-8'))['id'])
    ensure_idle(previous)
    saved=save_project(previous['id'],draft=draft.model_dump(mode='json'),state='ready',error=None)
else:
    saved=create_project(draft)
(run/'studio-project.json').write_text(json.dumps({'id':saved['id'],'title':saved['draft']['title']},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'project':saved['id'],'asset_count':len(assets),'folder':str(folder),'catalog_html':str(run/'catalog.html')},ensure_ascii=False,indent=2))
