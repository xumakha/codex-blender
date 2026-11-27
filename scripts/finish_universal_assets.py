"""Validate every new GLB, make a browsable catalog and package the two-sheet library."""
from collections import Counter
import html
import json
from pathlib import Path
import struct
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codex_blender.config import ROOT, assets_dir
from scripts import finish_story_world as F

PACK='universal-interior-v1'
ROOT_ASSETS=assets_dir()
FOLDER=ROOT_ASSETS/'generated'/PACK
RUN=ROOT/'outputs'/PACK
RUN.mkdir(parents=True,exist_ok=True)


def main():
    data=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))
    assert len(data['assets'])==180,len(data['assets'])
    # The shared exporter preserves named meshes and editable Blender modifiers.
    for item in data['assets']:
        item['description']=item['description'].replace('Bộ Story World','Bộ Universal Core & Interior')
        metadata={key:value for key,value in item.items() if key not in {'slug','path'}}
        (ROOT_ASSETS/item['path']).with_suffix('.asset.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    (FOLDER/'manifest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    F.RUN=RUN;F.ROOT_ASSETS=ROOT_ASSETS
    F.validate(data)
    counts=Counter(item['category'] for item in data['assets'])
    sections=[]
    for group,title in data['groups'].items():
        cards=[]
        for item in data['assets']:
            if item['category']!=group:continue
            slug=item['slug'];name=html.escape(item['name'])
            cards.append(f'<article data-name="{html.escape(name+" "+slug,quote=True)}"><img src="{slug}.png" loading="lazy" alt="{name}"><h3>{name}</h3><small>{slug}</small><p>{item["mesh_objects"]} meshes · '+
                ' × '.join(str(round(v,2)) for v in item['dimensions'])+f' m</p><nav><a href="{slug}.glb" download>GLB</a><a href="{slug}.blend" download>BLEND</a></nav></article>')
        if cards:sections.append(f'<section id="{group}"><h2>{html.escape(title)} <small>{len(cards)}</small></h2><div class="grid">'+''.join(cards)+'</div></section>')
    document='''<!doctype html><html lang="vi"><meta charset="utf-8"><title>Universal Core & Interior — 180 assets</title><style>
*{box-sizing:border-box}body{margin:0;padding:38px;background:#f4ebe3;color:#503a2f;font:15px Segoe UI,Arial,sans-serif}h1{font-size:44px;letter-spacing:-1.5px;margin:8px 0}p{line-height:1.7}header{border-bottom:2px solid #d8c2ae;padding-bottom:26px}header>small{letter-spacing:3px}input{padding:13px 16px;background:#fffaf5;border:1px solid #d6bfaa;border-radius:10px;min-width:320px;font:inherit}.grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:16px}article{background:#fffaf5;border:1px solid #ddcbb9;border-radius:12px;overflow:hidden;padding-bottom:14px}article img{display:block;width:100%;aspect-ratio:1;object-fit:contain}article h3,article small,article p,article nav{margin:10px 13px}h3{font-size:15px;min-height:36px}article small{font-size:11px;color:#96785f}article p{font-size:11px;color:#96785f}nav{display:flex;gap:8px;flex-wrap:wrap}a{color:#795136;text-decoration:none;border:1px solid #d7bfa9;border-radius:20px;padding:6px 12px;font-size:12px}section{padding-top:20px}h2{font-size:25px}h2 small{color:#b38c67;font-size:16px}aside{margin:32px 0;padding:20px;border:1px solid #ddcbb9;border-radius:12px;max-width:1100px}aside p{margin:6px 0}@media(max-width:1100px){.grid{grid-template-columns:repeat(4,1fr)}}@media(max-width:650px){.grid{grid-template-columns:repeat(2,1fr)}body{padding:16px}h1{font-size:30px}}
</style><header><small>BLENDER / REUSABLE MODULAR LIBRARY</small><h1>Universal Core & Interior</h1><p>180 asset từ hai ảnh tham khảo · GLB + BLEND + PNG · Vật liệu và tỷ lệ thống nhất</p><input id="search" placeholder="Tìm tên hoặc mã asset…"><p>Mở Studio → Thư viện assets → tìm <b>universal-interior-v1</b>. Các mục có nhãn Interior là đồ nội thất; Core là bộ phận để lắp ghép.</p></header>'''+''.join(sections)+'''<aside><h2>Hướng dẫn sử dụng</h2><p>GLB dùng trong Studio. BLEND giữ mesh rời, tên bộ phận và modifier để chỉnh tiếp trong Blender. Gốc ở giữa đáy, Z hướng lên, mặt trước −Y, đơn vị mét.</p><p>Các mô hình là diễn giải 3D theo ảnh, có giản lược chi tiết. Mô hình tĩnh; không kèm rig nhân vật hoặc animation. Ống và khớp nối có lỗ rỗng. Đồ bếp, cửa, bánh xe và đồ nội thất gồm nhiều mesh để chỉnh sửa.</p><p>Các mục Example và Room là bảy diorama lắp sẵn. Hai ảnh gốc được lưu trong references/universal-interior-v1.</p></aside><script>document.querySelector('#search').oninput=e=>{const q=e.target.value.toLocaleLowerCase();document.querySelectorAll('article').forEach(a=>a.hidden=!a.dataset.name.toLocaleLowerCase().includes(q));document.querySelectorAll('section').forEach(s=>s.hidden=![...s.querySelectorAll('article')].some(a=>!a.hidden))}</script></html>'''
    (FOLDER/'catalog.html').write_text(document,encoding='utf-8')
    (RUN/'summary.json').write_text(json.dumps({'count':len(data['assets']),'groups':dict(counts),'folder':str(FOLDER)},ensure_ascii=False,indent=2),encoding='utf-8')
    (FOLDER/'README.txt').write_text('Universal Core & Interior — 180 native Blender assets.\n'
        'Browse catalog.html. Import GLB into Frame Studio or open BLEND to edit named meshes.\n'
        'Static models, no animation or character skeleton. Z up, front -Y, meters, origin floor-center.\n'
        'Reference-inspired interpretations, simplified details. Existing Story World library is preserved.\n',encoding='utf-8')
    zip_path=RUN/'Universal-Core-Interior-180-assets.zip'
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
        for folder in (FOLDER,ROOT_ASSETS/'references'/PACK):
            for path in sorted(folder.rglob('*')):
                if path.is_file():archive.write(path,path.relative_to(ROOT_ASSETS))
    with zipfile.ZipFile(zip_path) as archive:assert archive.testzip() is None
    print('VERIFIED',len(data['assets']),'ASSETS',zip_path,flush=True)


if __name__=='__main__':main()
