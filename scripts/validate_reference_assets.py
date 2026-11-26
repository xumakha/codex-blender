"""Validate all generated GLBs by actually importing them back into Blender."""
import json
import os
from pathlib import Path
import struct
import math
from codex_blender.config import ROOT,assets_dir

RUN=ROOT/'outputs'/'inventor-toy-kit'
os.environ['BLENDER_USER_RESOURCES']=str(RUN/'blender-user')
import bpy
from mathutils import Vector

root=assets_dir()
folder=root/'generated'/'inventor-toy-v1'
manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
report=[]
assert len(manifest['assets'])==32, 'The full 32-asset build has not finished'
for entry in manifest['assets']:
    path=root/entry['path']
    for suffix in ('.glb','.blend','.png','.asset.json'):
        assert path.with_suffix(suffix).stat().st_size>100, str(path.with_suffix(suffix))
    data=path.read_bytes()
    magic,version,total=struct.unpack_from('<4sII',data)
    assert magic==b'glTF' and version==2 and total==len(data),str(path)
    length,kind=struct.unpack_from('<I4s',data,12)
    assert kind==b'JSON'
    gltf=json.loads(data[20:20+length])
    assert gltf.get('meshes'),str(path)
    for item in gltf.get('buffers',[])+gltf.get('images',[]):
        assert not item.get('uri') or item['uri'].startswith('data:'),'GLB references an external file'
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    bpy.context.view_layer.update()
    mesh=[obj for obj in bpy.context.scene.objects if obj.type=='MESH']
    assert mesh
    corners=[obj.matrix_world@Vector(p) for obj in mesh for p in obj.bound_box]
    lo=[min(p[i] for p in corners) for i in range(3)]
    hi=[max(p[i] for p in corners) for i in range(3)]
    dims=[hi[i]-lo[i] for i in range(3)]
    assert all(math.isfinite(v) for v in lo+hi)
    assert abs(lo[2])<.015, (entry['slug'],'not floor-centered',lo)
    assert max(abs(dims[i]-entry['dimensions'][i]) for i in range(3))<.025,(entry['slug'],dims,entry['dimensions'])
    report.append({'slug':entry['slug'],'mesh_objects':len(mesh),'dimensions':[round(v,3) for v in dims],'bytes':len(data)})
    print('PASS',entry['slug'],len(mesh),'meshes',flush=True)
result={'passed':True,'count':len(report),'assets':report}
(RUN/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('Validated',len(report),'self-contained GLBs by Blender import',flush=True)
