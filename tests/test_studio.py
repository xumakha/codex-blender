import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from starlette.testclient import TestClient

from codex_blender import config, studio, library, jobs, audio
from codex_blender.models import SceneSpec, VideoPlan, ShotDesign
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
        p=studio.create_project(studio.Draft(prompt='Hộp xanh',references=['reference.png'],voice_id=audio.ELEVENLABS_VOICE_ID))
        captured={}
        def fake_run(cmd,**kwargs):
            captured['cmd']=cmd;captured['task']=kwargs['input']
            output=Path(cmd[cmd.index('-o')+1])
            if output.name.startswith('screenplay-'):
                value=VideoPlan(title='Box',duration=12,style='Studio',shots=[{'title':'Rotate','start':0,'end':12,'setting':'Studio','actions':['Rotate the box'],'elements':[{'id':'box','label':'Box','source':'Hộp xanh','role':'prop','appearance':'Blue box'}]}])
            else:
                value=ShotDesign(objects=[{'name':'box','kind':'cube','keyframes':[{'time':12,'rotation':[0,0,90]}]}],bindings=[{'action_index':0,'objects':['box'],'elements':['box'],'start':0,'end':12}],element_bindings=[{'element_id':'box','objects':['box']}])
            output.write_text(value.model_dump_json(),encoding='utf-8')
            class Result:returncode=0
            return Result()
        # Use an actual-shaped npm path so Windows command construction remains exercised.
        exe=str(Path('C:/Users/thanh/AppData/Roaming/npm/codex.cmd'))
        with patch.object(studio.shutil,'which',side_effect=lambda n:exe if 'codex' in n else 'node'),patch.object(studio.subprocess,'run',side_effect=fake_run),patch.object(studio,'render_project') as render:
            studio.plan_scene(p['id'],studio.Draft.model_validate(p['draft']),self.assets,auto_render=True)
            render.assert_called_once_with(p['id'],'video')
        saved=studio.read_project(p['id'])
        self.assertEqual(saved['state'],'ready',saved.get('error'))
        self.assertIn(str(image),captured['cmd'])
        self.assertIn('art-direction references',captured['task'])
        self.assertEqual(saved['draft']['scene']['shots'][0]['objects'][0]['name'],'box')
        self.assertEqual(saved['draft']['duration'],12)
        task=json.loads(captured['task'].split('INPUT:\n',1)[1])
        self.assertEqual(task['preferred_voice_id'],audio.ELEVENLABS_VOICE_ID)
        self.assertIn(audio.ELEVENLABS_VOICE_ID,{voice['id'] for voice in task['voices']})
        self.assertNotIn('duration',task)
        self.assertNotIn('script',task)
        rendered=studio.scene_for_render(studio.Draft.model_validate(saved['draft']))
        self.assertEqual(rendered.duration,12)
        self.assertEqual(rendered.shots[0].objects[0].keyframes[0].time,12)

    def test_legacy_script_merges_without_losing_content(self):
        draft=studio.Draft(prompt='Idea',script='Full script')
        self.assertEqual(draft.prompt,'Idea\n\nFull script')
        self.assertEqual(draft.script,'')
        self.assertEqual(studio.Draft.model_validate(draft.model_dump()).prompt,draft.prompt)
        long_draft=studio.Draft(prompt='a'*20000,script='b'*50000)
        SceneSpec(prompt=long_draft.prompt,objects=[{'name':'box','kind':'cube'}])

    def test_plan_endpoint_requests_automatic_video_render(self):
        p=studio.create_project(studio.Draft(prompt='A moving box'))
        with patch.object(studio.POOL,'submit') as submit:
            response=self.client.post('/api/projects/'+p['id']+'/plan',json={'auto_render':True})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['state'],'planning')
        self.assertTrue(submit.call_args.args[-2])

    def test_elevenlabs_voice_is_listed_saved_and_available_for_preview(self):
        voices=self.client.get('/api/bootstrap').json()['voices']
        selected=next(voice for voice in voices if voice['id']==audio.ELEVENLABS_VOICE_ID)
        self.assertEqual(selected['provider'],'elevenlabs')
        p=studio.create_project()
        draft=p['draft'];draft['voice_id']=audio.ELEVENLABS_VOICE_ID
        saved=self.client.put('/api/projects/'+p['id'],json=draft)
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(self.client.get('/api/projects/'+p['id']).json()['draft']['voice_id'],audio.ELEVENLABS_VOICE_ID)
        with patch.dict(os.environ,{'ELEVENLABS_API_KEY':''}):
            response=self.client.post('/api/voice-preview',json={'voice':audio.ELEVENLABS_VOICE_ID,'text':'Xin chào!'})
        self.assertEqual(response.status_code,400)
        self.assertIn('ELEVENLABS_API_KEY',response.json()['error'])

    def test_retime_and_audio_configuration(self):
        scene=SceneSpec(duration=5,objects=[{'name':'box','kind':'cube','keyframes':[{'time':5,'rotation':[0,0,90]}]}])
        draft=studio.Draft(scene=scene,duration=10,voice_mode='upload',voice_file='voice.wav',music='music.wav',voice_volume=.8,music_volume=.15)
        result=studio.scene_for_render(draft)
        self.assertEqual(result.objects[0].keyframes[0].time,10)
        self.assertEqual(result.voice_audio,'voice.wav')
        self.assertEqual(result.music,'music.wav')
        self.assertEqual(result.music_volume,.15)

    def test_retry_endpoint_uses_saved_job_without_replanning(self):
        p=studio.create_project(studio.Draft(prompt='Keep this prompt'))
        studio.save_project(p['id'],current_job='a'*32,jobs=['a'*32])
        failed={'id':'a'*32,'state':'failed','mode':'video'}
        with patch.object(studio,'status',return_value=failed),patch.object(studio,'retry') as retry:
            response=self.client.post('/api/projects/'+p['id']+'/retry',json={})
        self.assertEqual(response.status_code,200,response.text)
        retry.assert_called_once_with('a'*32)
        self.assertEqual(response.json()['draft']['prompt'],'Keep this prompt')

    def test_structured_output_preserves_title_property(self):
        schema=studio.strict_schema(SceneSpec.model_json_schema())
        self.assertIn('title',schema['properties'])
        self.assertIn('title',schema['required'])
        self.assertNotIn('prefixItems',schema['$defs']['Camera']['properties']['location'])

    def test_pause_resume_api_and_paused_project_remains_busy(self):
        p=studio.create_project()
        jid='d'*32
        path=self.root/'jobs'/jid
        path.mkdir(parents=True)
        jobs.write_json(path/'status.json',{'id':jid,'state':'rendering','mode':'video','frames_total':120})
        studio.save_project(p['id'],current_job=jid,jobs=[jid],state='ready')
        with patch.object(jobs,'OUTPUTS',path.parent):
            url='/api/projects/'+p['id']
            response=self.client.post(url+'/control/pause',json={})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['job']['state'],'pausing')
            (path/'.paused').touch()
            self.assertEqual(self.client.get(url).json()['job']['state'],'paused')
            self.assertEqual(self.client.put(url,json=p['draft']).status_code,400)
            self.assertEqual(self.client.post(url+'/render',json={'mode':'video'}).status_code,400)
            response=self.client.post(url+'/control/resume',json={})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['job']['state'],'rendering')
            self.assertEqual(self.client.post(url+'/control/unknown',json={}).status_code,400)

    def test_settings_do_not_retarget_existing_jobs(self):
        with patch.object(jobs,'OUTPUTS',self.root/'jobs'),patch.object(jobs,'blender_command',return_value=['blender']),patch.object(jobs.subprocess,'Popen'):
            result=jobs.submit(SceneSpec(objects=[{'name':'box','kind':'cube'}]))
            old=Path(result['output_directory'])/'status.json'
            self.assertEqual(json.loads(old.read_text())['assets_directory'],str(self.assets))
            other=self.root/'new-assets';other.mkdir();library.set_directory(str(other))
            self.assertEqual(json.loads(old.read_text())['assets_directory'],str(self.assets))


if __name__=='__main__':unittest.main()
