"""Reimport and inspect every expansion model; make an offline catalog and archive."""
from collections import Counter
import html
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codex_blender.config import ROOT,assets_dir
from scripts import finish_story_world as F
from scripts import build_expansion_assets as E

PACK=E.PACK
ASSET_ROOT=assets_dir()
FOLDER=ASSET_ROOT/'generated'/PACK
RUN=ROOT/'outputs'/PACK

def main():
    RUN.mkdir(parents=True,exist_ok=True)
    data=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))
    assert {a['slug'] for a in data['assets']}==set(E.ASSETS),'Incomplete registry'
    F.RUN=RUN;F.ROOT_ASSETS=ASSET_ROOT;F.validate(data)
    # Existing exact matches are reused. Their original names and sidecars stay intact.
    reused=[]
    for pack in ('story-world-v1','universal-interior-v1'):
        previous=json.loads((ASSET_ROOT/'generated'/pack/'manifest.json').read_text(encoding='utf-8'))
        for item in previous['assets']:
            # The old primitive sheet is a useful assembly kit, included as the base library.
            path=ASSET_ROOT/item['path']
            for ext in ('.glb','.blend','.png','.asset.json'):assert path.with_suffix(ext).is_file()
            reused.append({**item,'reuse_from':pack})
    coverage={'new_pack':PACK,'new_count':len(data['assets']),'base_library_count':len(reused),
              'interior_reference':'376e0ba1-e6e2-4ab4-aa57-1e3b45f04f11.png',
              'interior_reuse_from':'universal-interior-v1',
              'note':'New sheets are interpreted as editable stylized geometry. Existing full-body characters, vehicles, tools, interiors and landscape props are reused. Turnaround views share one model. Expression assets are head busts. Static meshes, no animation or skeleton.',
              'base_library':reused}
    (FOLDER/'coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2),encoding='utf-8')
    sections=[]
    for group,title in data['groups'].items():
        cards=[]
        for item in data['assets']:
            if item['category']!=group:continue
            slug=item['slug'];name=html.escape(item['name']);description='Biểu cảm dạng tượng đầu / Head bust' if group=='expressions' else 'Editable mesh · Static model'
            cards.append(f'<article data-name="{html.escape(name+" "+slug,quote=True)}"><img src="{slug}.png" alt="{name}"><h3>{name}</h3><small>{slug}</small><p>{description}</p><nav><a href="{slug}.glb" download>GLB</a><a href="{slug}.blend" download>BLEND</a></nav></article>')
        sections.append(f'<section id="{group}"><h2>{html.escape(title)} <small>{len(cards)}</small></h2><div class="grid">'+''.join(cards)+'</div></section>')
    document='''<!doctype html><html lang="vi"><meta charset="utf-8"><title>Universal Expansion</title><style>
*{box-sizing:border-box}body{margin:0;padding:32px;background:#f3ebe4;color:#50392e;font:15px Segoe UI,Arial}h1{font-size:42px;margin:8px 0}p{line-height:1.6}header{padding-bottom:24px;border-bottom:1px solid #cdb6a1}.grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:15px}article{border:1px solid #d5beaa;background:#fffaf6;border-radius:12px;overflow:hidden;padding-bottom:12px}article img{width:100%;aspect-ratio:1;object-fit:contain}article h3,article small,article p,article nav{margin:10px 12px}article small,article p{font-size:11px;color:#90745e}h3{font-size:14px}h2{margin-top:36px}h2 small{color:#ac8b70}nav{display:flex;gap:9px}a{color:#795135}input{padding:12px;border:1px solid #cfb9a6;border-radius:8px;font:inherit;width:340px}aside{padding:22px 0;max-width:1000px}@media(max-width:900px){.grid{grid-template-columns:repeat(3,1fr)}}
</style><header><small>BLENDER · MODULAR · REUSABLE</small><h1>Universal Expansion</h1>'''+f'<p>{len(data["assets"])} asset mới · GLB + BLEND + PNG · {len(reused)} asset có sẵn trong hai bộ nền được giữ nguyên.</p>'+'''<p>Mở Studio → Thư viện assets → tìm <b>universal-expansion-v2</b>.</p><p>Biểu cảm là các mẫu tượng đầu. Nhân vật toàn thân và ảnh nội thất dùng lại bộ đã có. Mô hình tĩnh, chưa kèm rig hoặc animation. Các ảnh nhiều góc nhìn được thể hiện bằng một mô hình 3D.</p><input id="search" placeholder="Tìm tên hoặc mã asset…"><p>Bộ nền: <a href="../story-world-v1/catalog.html">Story World</a> · <a href="../universal-interior-v1/catalog.html">Core & Interior</a></p></header>'''+''.join(sections)+'''<aside><p>GLB dùng trong Studio; BLEND giữ các mesh có tên và modifier để chỉnh sửa. Gốc tọa độ giữa đáy, Z hướng lên, mặt trước −Y; đơn vị mét. Màu và hình khối dựa theo ảnh tham khảo, có giản lược chi tiết. Hiệu ứng là các hình khối tĩnh để dựng hoặc tạo chuyển động tiếp.</p><p>ZIP chứa toàn bộ bộ bổ sung, hai bộ nền, ảnh tham khảo và bảng coverage.json. Không cần texture ngoài.</p></aside><script>document.querySelector('#search').oninput=e=>{let q=e.target.value.toLowerCase();document.querySelectorAll('article').forEach(a=>a.hidden=!a.dataset.name.toLowerCase().includes(q));document.querySelectorAll('section').forEach(s=>s.hidden=![...s.querySelectorAll('article')].some(a=>!a.hidden))}</script></html>'''
    (FOLDER/'catalog.html').write_text(document,encoding='utf-8')
    (FOLDER/'README.txt').write_text(f'Universal Expansion: {len(data["assets"])} new native assets.\nTwo base packs ({len(reused)} models) included and reused, not duplicated in Studio.\nOpen catalog.html. Import GLB or edit BLEND. No external textures.\nZ up, front -Y, meters, floor-centered origins. Static models, no rig or animation.\nExpressions are head busts. Multi-angle turnaround pictures share one 3D model.\nReference-inspired simplified geometry. See coverage.json for existing base assets.\n',encoding='utf-8')
    (RUN/'summary.json').write_text(json.dumps({'new_assets':len(data['assets']),'base_library':len(reused),'groups':dict(Counter(a['category'] for a in data['assets']))},ensure_ascii=False,indent=2),encoding='utf-8')
    zip_path=RUN/f'Universal-Expansion-{len(data["assets"])}-new-assets.zip'
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as archive:
        for pack in (PACK,'story-world-v1','universal-interior-v1'):
            for kind in ('generated','references'):
                folder=ASSET_ROOT/kind/pack
                for path in sorted(folder.rglob('*')):
                    if path.is_file() and path.suffix!='.blend1':archive.write(path,path.relative_to(ASSET_ROOT))
    with zipfile.ZipFile(zip_path) as archive:assert archive.testzip() is None
    print('VERIFIED',len(data['assets']),'NEW ASSETS',zip_path,flush=True)

if __name__=='__main__':main()
