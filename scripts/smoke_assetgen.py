"""Exercise Blender preview -> normalized GLB -> catalog. --live also calls Codex with an image."""
import argparse
import json
from pathlib import Path
import shutil
import struct
from unittest.mock import patch

from codex_blender import assetgen, config, studio, library
from codex_blender.jobs import submit,status
import time


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--batch',action='store_true')
    args=parser.parse_args()
    root=config.OUTPUTS/('assetgen-live-smoke' if args.live else 'assetgen-smoke')
    if args.batch:root=root.with_name(root.name+'-batch')
    assets=root/'assets'
    assets.mkdir(parents=True,exist_ok=True)
    # Build the reference from a fixed synthetic scene. Never choose an existing
    # user render or upload for a test that may send an image to Codex.
    design=assetgen.AssetDesign(objects=[
        {'name':'BlueCube','kind':'cube','scale':[.65,.65,.65],'location':[0,0,1.5],'color':'#4F8CFF'},
        {'name':'GoldRing','kind':'torus','location':[0,0,1.5],'rotation':[65,0,0],'color':'#F1BB49','metallic':.8}],description='Blue cube and gold ring')
    reference_job=submit(assetgen.make_scene(design,'Synthetic asset test reference'),'preview',assets)
    deadline=time.monotonic()+120
    while True:
        reference=status(reference_job['id'])
        if reference['state']=='completed':break
        if reference['state']=='failed' or time.monotonic()>deadline:raise RuntimeError('Synthetic reference render failed')
        time.sleep(1)
    shutil.copyfile(reference['artifacts']['preview.png'],assets/'reference.png')
    with patch.object(config,'DATA',root/'data'),patch.object(studio,'DATA',root/'data'),patch.object(config,'ASSETS',assets):
        draft=studio.Draft(title='Asset smoke test',prompt='Rebuild the blue cube and gold ring visible in this image as one reusable static asset. Exclude text and background.',references=['reference.png'],voice_mode='none')
        if args.batch:draft.prompt='Rebuild the blue cube and gold ring as two separate reusable assets. Exclude text and background.'
        project=studio.create_project(draft)
        studio.save_project(project['id'],kind='asset-generation',state='planning',asset_stage='planning',asset_root=str(assets),asset_mode='multiple' if args.batch else 'single',asset_limit=2)
        print('Project:',project['id'], 'live planner:',args.live,flush=True)
        if args.live:
            assetgen.run(project['id'],draft,assets)
        else:
            inventory=assetgen.AssetInventory(items=[{'id':name,'name':name,'prompt':name} for name in ['cube','ring']])
            designs=[assetgen.AssetDesign(objects=[obj]) for obj in design.objects]
            with patch.object(assetgen,'call_planner',side_effect=[inventory,*designs] if args.batch else [design]):
                assetgen.run(project['id'],draft,assets)
        result=assetgen.public(project['id'])
        if result['stage']!='completed':
            raise RuntimeError(json.dumps(result))
        items=result['items'] if args.batch else [{'id':None,'result':result['result']}]
        assert len(items)==(2 if args.batch else 1)
        for item in items:
            assert item['result'],item
            glb=assetgen.artifact(project['id'],'model.glb',item['id'])
            data=glb.read_bytes()
            assert data[:4]==b'glTF'
            length=struct.unpack_from('<I',data,12)[0]
            document=json.loads(data[20:20+length])
            assert document.get('meshes')
            assert not document.get('images'), 'Expected native geometry, no image billboard'
            assert not document.get('animations')
            assert any(a['path']==item['result']['path'] for a in library.catalog(assets))
            assert assetgen.artifact(project['id'],'preview.png',item['id']).stat().st_size>100
            print(json.dumps({'passed':True,'model':str(glb),'meshes':len(document['meshes'])}))


if __name__=='__main__':
    main()
