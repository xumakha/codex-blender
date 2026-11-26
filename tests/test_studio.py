import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from starlette.testclient import TestClient

from codex_blender import config, studio, library, jobs
from codex_blender.models import SceneSpec
from codex_blender.webapp import app

HEADERS={"X-Studio-Request":"1"}


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=config.ROOT/"outputs")
        self.root=Path(self.tmp.name)
        self.assets=self.root/"assets"
        self.assets.mkdir()
        self.data=self.root/"data"
        self.patches=[patch.object(config,"DATA",self.data),patch.object(studio,"DATA",self.data),
                      patch.object(library,"DATA",self.data),patch.object(config,"ASSETS",self.assets),
                      patch.object(library,"ASSETS",self.assets)]
        for item in self.patches:item.start()
        self.client=TestClient(app,headers=HEADERS)

    def tearDown(self):
        self.client.close()
        for item in reversed(self.patches):item.stop()
        # The temporary root is created directly beneath the workspace outputs directory.
        assert self.root.resolve().is_relative_to(config.ROOT.resolve())
        self.tmp.cleanup()

    def test_ui_and_persistent_project(self):
        self.assertEqual(self.client.get('/').status_code,200)
        p=self.client.post('/api/projects',json={}).json()
        draft=p['draft'];draft['title']='Dự án kiểm thử';draft['prompt']='một chiếc hộp xanh'
        saved=self.client.put('/api/projects/'+p['id'],json=draft)
        self.assertEqual(saved.status_code,200)
        self.assertEqual(self.client.get('/api/projects/'+p['id']).json()['draft']['title'],'Dự án kiểm thử')

    def test_library_upload_and_folder_switch(self):
        response=self.client.post('/api/uploads',data={'category':'references'},files={'file':('mood.png',b'png-test','image/png')})
        self.assertEqual(response.status_code,200,response.text)
        name=response.json()['path']
        self.assertEqual(self.client.get('/api/assets/file',params={'path':name}).content,b'png-test')
        self.assertEqual(self.client.get('/api/assets/file',params={'path':'../settings.json'}).status_code,400)
        other=self.root/'other';other.mkdir()
        self.assertEqual(self.client.post('/api/settings',json={'assets_directory':str(other)}).status_code,200)
        self.assertEqual(config.assets_dir(),other)
        self.assertTrue((self.assets/name).exists())
        self.assertEqual(self.client.get('/api/library').json()['assets'],[])

    def test_cross_origin_and_unknown_files_rejected(self):
        self.assertEqual(self.client.post('/api/projects',json={},headers={'Origin':'https://example.com'}).status_code,403)
        plain=TestClient(app)
        self.assertEqual(plain.post('/api/projects',json={}).status_code,403)
        response=self.client.post('/api/uploads',data={'category':'models'},files={'file':('malicious.blend',b'bad')})
        self.assertEqual(response.status_code,400)

    def test_style_references_reach_codex_and_scene_is_persisted(self):
        image=self.assets/'reference.png';image.write_bytes(b'image')
        p=studio.create_project(studio.Draft(prompt='Hộp xanh',references=['reference.png']))
        captured={}
        def fake_run(cmd,**kwargs):
            captured['cmd']=cmd;captured['task']=kwargs['input']
            output=Path(cmd[cmd.index('-o')+1])
            output.write_text(SceneSpec(objects=[{'name':'box','kind':'cube'}]).model_dump_json(),encoding='utf-8')
            class Result:returncode=0
            return Result()
        # Use an actual-shaped npm path so Windows command construction remains exercised.
        exe=str(Path('C:/Users/thanh/AppData/Roaming/npm/codex.cmd'))
        with patch.object(studio.shutil,'which',side_effect=lambda n:exe if 'codex' in n else 'node'),patch.object(studio.subprocess,'run',side_effect=fake_run):
            studio.plan_scene(p['id'],studio.Draft.model_validate(p['draft']),self.assets)
        saved=studio.read_project(p['id'])
        self.assertEqual(saved['state'],'ready',saved.get('error'))
        self.assertIn(str(image),captured['cmd'])
        self.assertIn('art-direction references',captured['task'])
        self.assertEqual(saved['draft']['scene']['objects'][0]['name'],'box')

    def test_retime_and_audio_configuration(self):
        scene=SceneSpec(duration=5,objects=[{'name':'box','kind':'cube','keyframes':[{'time':5,'rotation':[0,0,90]}]}])
        draft=studio.Draft(scene=scene,duration=10,voice_mode='upload',voice_file='voice.wav',music='music.wav',voice_volume=.8,music_volume=.15)
        result=studio.scene_for_render(draft)
        self.assertEqual(result.objects[0].keyframes[0].time,10)
        self.assertEqual(result.voice_audio,'voice.wav')
        self.assertEqual(result.music,'music.wav')
        self.assertEqual(result.music_volume,.15)

    def test_structured_output_preserves_title_property(self):
        schema=studio.strict_schema(SceneSpec.model_json_schema())
        self.assertIn('title',schema['properties'])
        self.assertIn('title',schema['required'])
        self.assertNotIn('prefixItems',schema['$defs']['Camera']['properties']['location'])

    def test_settings_do_not_retarget_existing_jobs(self):
        with patch.object(jobs,'OUTPUTS',self.root/'jobs'),patch.object(jobs,'blender_command',return_value=['blender']),patch.object(jobs.subprocess,'Popen'):
            result=jobs.submit(SceneSpec(objects=[{'name':'box','kind':'cube'}]))
            old=Path(result['output_directory'])/'status.json'
            self.assertEqual(json.loads(old.read_text())['assets_directory'],str(self.assets))
            other=self.root/'new-assets';other.mkdir();library.set_directory(str(other))
            self.assertEqual(json.loads(old.read_text())['assets_directory'],str(self.assets))


if __name__=='__main__':unittest.main()
