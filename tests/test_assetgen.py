import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from starlette.testclient import TestClient

from codex_blender import assetgen, config, library, studio
from codex_blender.webapp import app


class AssetGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.assets = self.root/'assets'
        self.assets.mkdir()
        (self.assets/'reference.png').write_bytes(b'reference')
        for module, name, value in [(config,'DATA',self.root/'data'),(studio,'DATA',self.root/'data'),
                                    (library,'DATA',self.root/'data'),(config,'ASSETS',self.assets)]:
            item = patch.object(module,name,value)
            item.start()
            self.addCleanup(item.stop)
        self.client = TestClient(app,headers={'X-Studio-Request':'1'})
        self.addCleanup(self.client.close)

    def start(self, **options):
        with patch.object(studio.POOL,'submit') as pool:
            response=self.client.post('/api/asset-generations',json={'name':'Robot','references':['reference.png'],**options})
        self.assertEqual(response.status_code,202,response.text)
        pool.assert_called_once()
        return response.json(),pool.call_args.args

    def test_start_uses_images_and_stays_out_of_video_projects(self):
        job,args=self.start()
        self.assertEqual(job['stage'],'planning')
        self.assertEqual(args[2].references,['reference.png'])
        self.assertEqual(args[3],self.assets)
        self.assertEqual(self.client.get('/api/projects').json(),[])
        self.assertEqual(len(self.client.get('/api/asset-generations').json()),1)
        blocked=self.client.post('/api/asset-generations',json={'name':'Second','references':['reference.png']})
        self.assertEqual(blocked.status_code,400)

    def test_invalid_input_and_paths_are_rejected(self):
        for body in [{'name':'No image','references':[]},{'name':'Escape','references':['../other.png']},
                     {'name':'Too many','references':['reference.png']*5},{'name':' ','references':['reference.png']}]:
            self.assertEqual(self.client.post('/api/asset-generations',json=body).status_code,400)
        self.assertEqual(self.client.post('/api/asset-generations',json={'name':'x','references':['reference.png']},headers={'Origin':'https://example.com'}).status_code,403)

    def test_image_planes_and_empty_geometry_cannot_pass(self):
        for objects in [[{'name':'photo','kind':'image','asset':'reference.png'}],[{'name':'group','kind':'empty'}]]:
            with self.assertRaises(ValueError):
                assetgen.validate_design(assetgen.AssetDesign(objects=objects))

    def test_full_pipeline_exports_native_objects_and_registers_catalog(self):
        job,args=self.start()
        design=assetgen.AssetDesign(description='Robot xanh',objects=[{'name':'body','kind':'cube'}])
        blend=self.root/'scene.blend'
        blend.write_bytes(b'blend')
        render={'id':'a'*32,'state':'completed','artifacts':{'scene.blend':str(blend)}}
        def export(command,**kwargs):
            options=json.loads(Path(command[-1]).read_text())
            self.assertEqual(options['names'],['body'])
            Path(options['output']).write_bytes(b'glTF'+b'0'*20)
            Path(options['output']).with_suffix('.png').write_bytes(b'png')
        with patch.object(assetgen,'call_planner',return_value=design) as planner,patch.object(assetgen,'submit',return_value=render), \
             patch.object(assetgen,'status',return_value=render),patch.object(studio,'status',return_value=render), \
             patch.object(assetgen.subprocess,'run',side_effect=export):
            assetgen.run(*args[1:])
            result=assetgen.public(job['id'])
        self.assertEqual(result['stage'],'completed',result.get('error'))
        self.assertEqual(planner.call_args.args[1].references,['reference.png'])
        self.assertEqual(library.catalog(self.assets)[0]['name'],'Robot')
        with patch.object(studio,'status',return_value=render):
            self.assertTrue(assetgen.artifact(job['id'],'model.glb').is_file())
            with self.assertRaises(ValueError):assetgen.artifact(job['id'],'credentials.json')

    def test_planning_error_is_visible_and_persistent(self):
        job,args=self.start()
        with patch.object(assetgen,'call_planner',side_effect=RuntimeError('Planner unavailable')):
            assetgen.run(*args[1:])
        result=self.client.get('/api/asset-generations/'+job['id']).json()
        self.assertEqual(result['stage'],'failed')
        self.assertIn('Planner unavailable',result['error'])

    def test_multiple_requires_one_image_and_valid_limit(self):
        for options in [{'references':['reference.png']*2}, {'max_assets':0}, {'max_assets':41}, {'mode':'unknown'}]:
            body={'name':'Sheet','references':['reference.png'],'mode':'multiple',**options}
            self.assertEqual(self.client.post('/api/asset-generations',json=body).status_code,400)

    def test_multiple_exports_distinct_assets_and_downloads(self):
        job,args=self.start(mode='multiple',max_assets=5)
        self.assertEqual(job['stage'],'inventory')
        inventory=assetgen.AssetInventory(items=[
            {'id':'chair','name':'Chair','prompt':'Left wooden chair'},
            {'id':'table','name':'Table','prompt':'Right wooden table'}],notes='Two objects')
        design=assetgen.AssetDesign(objects=[{'name':'body','kind':'cube'}])
        renders=[{'id':letter*32,'state':'completed','artifacts':{'scene.blend':str(self.root/'scene.blend')}} for letter in 'ab']
        current={'render':None}
        def submit(*args):
            current['render']=renders.pop(0)
            return current['render']
        def export(command,**kwargs):
            output=Path(json.loads(Path(command[-1]).read_text())['output'])
            output.write_bytes(b'glTF'+b'0'*20)
            output.with_suffix('.png').write_bytes(b'png')
        with patch.object(assetgen,'call_planner',side_effect=[inventory,design,design]) as planner, \
             patch.object(assetgen,'submit',side_effect=submit), \
             patch.object(assetgen,'status',side_effect=lambda _:current['render']), \
             patch.object(studio,'status',side_effect=lambda _:current['render']), \
             patch.object(assetgen.subprocess,'run',side_effect=export):
            assetgen.run(*args[1:])
        result=self.client.get('/api/asset-generations/'+job['id']).json()
        self.assertEqual(result['state'],'ready',result['error'])
        self.assertEqual([i['state'] for i in result['items']],['completed','completed'])
        self.assertEqual(len({i['result']['path'] for i in result['items']}),2)
        self.assertEqual(len({i['result']['job_id'] for i in result['items']}),2)
        self.assertEqual({a['name'] for a in library.catalog(self.assets) if a['kind']=='model'},{'Chair','Table'})
        self.assertIn('Left wooden chair',planner.call_args_list[1].args[1].prompt)
        self.assertIn('Right wooden table',planner.call_args_list[2].args[1].prompt)
        for item in result['items']:
            for name in ['model.glb','preview.png']:
                response=self.client.get(f"/api/asset-generations/{job['id']}/items/{item['id']}/files/{name}")
                self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get(f"/api/asset-generations/{job['id']}/items/missing/files/model.glb").status_code,400)

    def test_multiple_keeps_success_when_another_item_fails(self):
        job,args=self.start(mode='multiple')
        inventory=assetgen.AssetInventory(items=[{'id':name,'name':name,'prompt':name} for name in ['chair','table']])
        success={'path':'generated/chair.glb','name':'chair','root':str(self.assets),'job_id':'a'*32}
        with patch.object(assetgen,'call_planner',return_value=inventory), \
             patch.object(assetgen,'build_one',side_effect=[RuntimeError('Bad geometry'),success]):
            assetgen.run(*args[1:])
        result=assetgen.public(job['id'])
        self.assertEqual(result['state'],'ready')
        self.assertEqual([i['state'] for i in result['items']],['failed','completed'])
        self.assertIn('Bad geometry',result['items'][0]['error'])
        self.assertEqual(result['items'][1]['result'],success)
        self.assertIn('1/2',result['error'])

    def test_multiple_inventory_rejects_duplicates_and_over_limit(self):
        for index,items in enumerate([
            [{'id':'chair','name':name,'prompt':'chair'} for name in ['Chair','Duplicate']],
            [{'id':name,'name':'Chair','prompt':'chair'} for name in ['left','right']],
            [{'id':name,'name':name,'prompt':name} for name in ['chair','table']]]):
            job,args=self.start(mode='multiple',max_assets=1 if index==2 else 5)
            with patch.object(assetgen,'call_planner',return_value=assetgen.AssetInventory(items=items)), \
                 patch.object(assetgen,'build_one') as build:
                assetgen.run(*args[1:])
            self.assertEqual(assetgen.public(job['id'])['state'],'error')
            build.assert_not_called()
