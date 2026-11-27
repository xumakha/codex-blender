"""Validate every GLB, build an offline catalog and create reusable scene templates."""
import argparse
from collections import Counter
import html
import json
import os
from pathlib import Path
import struct
import math

from codex_blender.config import ROOT,assets_dir
from codex_blender.models import SceneSpec

PACK='story-world-v1'
RUN=ROOT/'outputs'/PACK
ROOT_ASSETS=assets_dir()
FOLDER=ROOT_ASSETS/'generated'/PACK


def validate(data):
    os.environ['BLENDER_USER_RESOURCES']=str(RUN/'blender-user')
    import bpy
    from mathutils import Vector
    report=[]
    for entry in data['assets']:
        path=ROOT_ASSETS/entry['path']
        for suffix in ('.glb','.blend','.png','.asset.json'):
            assert path.with_suffix(suffix).stat().st_size>100,(entry['slug'],suffix)
        content=path.read_bytes()
        magic,version,size=struct.unpack_from('<4sII',content)
        assert magic==b'glTF' and version==2 and size==len(content)
        length,chunk=struct.unpack_from('<I4s',content,12)
        assert chunk==b'JSON'
        gltf=json.loads(content[20:20+length])
        assert gltf.get('meshes') and not gltf.get('images')
        assert not any(b.get('uri') for b in gltf.get('buffers',[]))
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path))
        bpy.context.view_layer.update()
        meshes=[obj for obj in bpy.context.scene.objects if obj.type=='MESH']
        points=[obj.matrix_world@Vector(corner) for obj in meshes for corner in obj.bound_box]
        lo=[min(p[i] for p in points) for i in range(3)]
        hi=[max(p[i] for p in points) for i in range(3)]
        dims=[hi[i]-lo[i] for i in range(3)]
        assert abs(lo[2])<.02,(entry['slug'],'floor',lo)
        assert max(abs(dims[i]-entry['dimensions'][i]) for i in range(3))<.035,(entry['slug'],dims,entry['dimensions'])
        assert abs(lo[0]+hi[0])<.03 and abs(lo[1]+hi[1])<.03,(entry['slug'],'origin')
        report.append({'slug':entry['slug'],'meshes':len(meshes),'bytes':len(content),'passed':True})
        print('PASS',entry['slug'],flush=True)
    (RUN/'validation.json').write_text(json.dumps({'passed':True,'count':len(report),'assets':report},indent=2),encoding='utf-8')


def templates(data):
    folder=FOLDER/'templates';folder.mkdir(exist_ok=True)
    entries={a['slug']:a for a in data['assets']}
    scenes={
      'science':('Khoa học vui',[('character-scientist',[-1.4,-.5,0],1),('blackboard',[1,1.2,0],1),('test-tubes',[.8,-.35,0],1),('robot-arm',[2.2,.2,0],.8),('globe',[-1.6,1.4,0],1)]),
      'mechanics':('Xưởng cơ khí',[('character-worker',[-1.6,-.1,0],1),('small-car',[.4,.2,0],1),('toolbox',[-.5,-1,0],.7),('crane-hook',[2,1,0],1),('gears',[-1.6,1.3,0],1)]),
      'town':('Một ngày ở phố nhỏ',[('small-house',[-3,1,0],1),('shop',[0,1,0],1),('cafe',[3,1,0],1),('character-merchant',[0,-1,0],1),('bench',[2,-1.3,0],1),('streetlamp',[-2,-1.3,0],1)]),
      'interiors':('Chuyện gia đình',[('sofa',[0,1,0],1),('coffee-table',[0,-.45,0],1),('armchair',[2,.2,0],1),('bookcase',[-2,1,0],1),('floor-lamp',[1.5,1.7,0],1),('character-student',[-1.8,-1,0],1)]),
      'nature':('Khám phá thiên nhiên',[('tree-green',[-1.7,1.3,0],1),('tree-blossom',[1.5,1.6,0],1),('bridge',[0,-.15,0],1),('waterfall',[0,1.8,0],1),('flower-bush',[-1.5,-.8,0],1),('character-explorer',[1.4,-.7,0],1)]),
      'adventure':('Hành trình học hỏi',[('character-explorer',[-.8,-.6,0],1),('character-scholar',[.7,-.4,0],1),('watchtower',[2.1,1.6,0],.7),('signpost',[-1.8,.3,0],1),('tree-pine',[-2.0,1.7,0],1),('rocks',[1.9,-.8,0],1)])}
    for slug,(title,objects) in scenes.items():
        corners=[]
        for key,loc,scale in objects:
            dimensions=entries[key]['dimensions']
            corners.extend((loc[0]+x*dimensions[0]*scale/2,loc[1]+y*dimensions[1]*scale/2,loc[2]+z*dimensions[2]*scale)
                           for x in (-1,1) for y in (-1,1) for z in (0,1))
        target=[(min(c[i] for c in corners)+max(c[i] for c in corners))/2 for i in range(3)]
        def normalize(v):
            size=math.sqrt(sum(a*a for a in v));return [a/size for a in v]
        direction=normalize([3,-7,3])
        right=normalize([-direction[1],direction[0],0])
        up=[direction[1]*right[2]-direction[2]*right[1],direction[2]*right[0]-direction[0]*right[2],direction[0]*right[1]-direction[1]*right[0]]
        distance=0
        for corner in corners:
            delta=[corner[i]-target[i] for i in range(3)]
            horizontal=abs(sum(delta[i]*right[i] for i in range(3)))
            vertical=abs(sum(delta[i]*up[i] for i in range(3)))
            depth=sum(delta[i]*direction[i] for i in range(3))
            distance=max(distance,depth+1.12*max(horizontal/(18/52),vertical/(18/52*720/1280)))
        location=[target[i]+direction[i]*(distance+.30) for i in range(3)]
        spec=SceneSpec(title=title,prompt='',duration=5,fps=24,width=1280,height=720,samples=16,
             background='#EFE5DF',floor='#EFE5DF',camera={'location':location,'target':target,'lens':52},
             objects=[{'name':f'Model{i+1}','kind':'model','asset':entries[key]['path'],'location':loc,'scale':[s,s,s]} for i,(key,loc,s) in enumerate(objects)])
        (folder/(slug+'.json')).write_text(spec.model_dump_json(indent=2),encoding='utf-8')


def catalog(data):
    groups=data['groups']
    rows=[]
    for group,title in groups.items():
        items=[a for a in data['assets'] if a['category']==group]
        cards=[]
        for entry in items:
            slug=entry['slug']
            cards.append(f'''<article><a href="{slug}.blend"><img src="{slug}.png" alt="{html.escape(entry['name'])}" loading="eager"></a><div><h3>{html.escape(entry['name'])}</h3><p>{slug}</p><small>{' × '.join(str(round(v,2)) for v in entry['dimensions'])} m · {entry['mesh_objects']} meshes</small><nav><a href="{slug}.glb" download>GLB</a><a href="{slug}.blend" download>BLEND</a></nav></div></article>''')
        rows.append(f'<section id="{group}"><header><h2>{html.escape(title)}</h2><span>{len(items)} assets</span></header><div class="grid">'+''.join(cards)+'</div></section>')
    counts=Counter(a['category'] for a in data['assets'])
    header=f'''<div class="hero"><p class="eyebrow">BLENDER / REUSABLE 3D LIBRARY</p><h1>Story World</h1><p>{len(data['assets'])} mô hình · 6 chủ đề · GLB + BLEND + PNG</p><p class="note">Dựng từ hình học Blender theo 6 ảnh tham khảo của bạn. Khối bo tròn, màu sắc đồng bộ, gốc giữa đáy.</p><nav>'''+''.join(f'<a href="#{g}">{html.escape(t)} · {counts[g]}</a>' for g,t in groups.items())+'</nav></div>'
    guide='''<aside><h2>Dùng trong video</h2><p>Mở Frame Studio → Thư viện assets, tìm <b>story-world-v1</b> hoặc tên món → Dùng trong dự án. Trong prompt, yêu cầu dùng đúng mô hình đã chọn và mô tả hành động/camera.</p><p>File GLB dùng để nhập vào cảnh. File BLEND giữ các mesh rời và modifier bo cạnh để chỉnh tiếp. Các mô hình đang ở tư thế tĩnh; nhân vật chưa có rig, biểu cảm chuyển động hay lip-sync. Bánh xe, cánh tay robot, cửa và đồ vật có các mesh được đặt tên để chỉnh/rig trong Blender.</p><p>Đơn vị mét, Z hướng lên, mặt trước −Y. Địa hình và đường có kích thước 2 × 2 m; đặt lặp theo X/Y để mở rộng. Đây là bản diễn giải theo phong cách ảnh, có những chi tiết được đơn giản hóa.</p><p>Thư mục <b>templates/</b> có 6 cảnh JSON để bắt đầu các video khoa học, cơ khí, phố xá, gia đình, thiên nhiên và phiêu lưu. Đường dẫn asset trong JSON tính từ thư viện assets.</p></aside>'''
    document='''<!doctype html><html lang="vi"><meta charset="utf-8"><title>Story World — 3D Asset Library</title><style>
*{box-sizing:border-box}body{margin:0;background:#f2e8df;color:#49372e;font-family:Segoe UI,Arial,sans-serif;padding:48px}a{color:#8c522b;text-decoration:none}h1{font-size:64px;margin:6px 0;letter-spacing:-2px}p{line-height:1.7}.hero{padding-bottom:32px;border-bottom:2px solid #d8c3ae}.eyebrow{letter-spacing:3px;font-size:12px;color:#90735b}.hero>p{font-size:20px}.hero .note{font-size:16px;max-width:900px}nav{display:flex;gap:14px;flex-wrap:wrap}nav a{border:1px solid #ceb698;border-radius:20px;padding:8px 16px;font-size:13px}section{padding-top:35px}section header{display:flex;align-items:center;justify-content:space-between}section h2{font-size:28px}section header span{color:#9c7b62}.grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:18px}article{background:#faf5ef;border:1px solid #e1d1c1;border-radius:14px;overflow:hidden}article img{width:100%;aspect-ratio:1;display:block;object-fit:contain}article>div{padding:13px}h3{font-size:16px;margin:0 0 5px;min-height:23px}article p{font-size:11px;color:#96755e;margin:4px 0}small{font-size:10px;color:#a18a76}article nav{margin-top:12px;gap:6px}article nav a{font-size:10px;padding:5px 9px}aside{margin-top:48px;border-top:2px solid #d8c3ae;padding-top:22px;max-width:1100px}aside p{font-size:15px}footer{margin-top:40px;color:#9e8068;font-size:13px}@media(max-width:1000px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}body{padding:25px}h1{font-size:46px}}@media(max-width:500px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}body{padding:16px}}
</style>'''+header+''.join(rows)+guide+'<footer>STORY WORLD / Native Blender meshes · Reference-inspired stylized interpretation</footer></html>'
    (FOLDER/'catalog.html').write_text(document,encoding='utf-8')
    (RUN/'summary.json').write_text(json.dumps({'count':len(data['assets']),'groups':dict(counts),'folder':str(FOLDER)},ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--skip-validation',action='store_true')
    args=parser.parse_args()
    data=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))
    assert len(data['assets'])==102, len(data['assets'])
    if not args.skip_validation:validate(data)
    templates(data);catalog(data)
    print('READY',len(data['assets']),FOLDER/'catalog.html',flush=True)


if __name__=='__main__':main()
