import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from starlette.testclient import TestClient
from codex_blender import preferences,library,studio,config
from codex_blender.webapp import app

class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        for module in (library,studio,config):
            p=patch.object(module,'DATA',self.root);p.start();self.addCleanup(p.stop)
        self.client=TestClient(app,headers={'X-Studio-Request':'1'})

    def test_settings_survive_reopen_and_new_projects(self):
        values={'font':'fonts/user.ttf','music':'music/song.mp3','music_volume':.37,'fps':30,'width':1920,'height':1080,'samples':32}
        response=self.client.post('/api/preferences',json={'video':values,'ui':{'aspect':'16:9','resolution':'full'}})
        self.assertEqual(response.status_code,200,response.text)
        reopened=TestClient(app,headers={'X-Studio-Request':'1'})
        self.assertEqual(reopened.get('/api/preferences').json()['video'],values)
        project=reopened.post('/api/projects',json={}).json()
        for key,val in values.items():self.assertEqual(project['draft'][key],val)
        self.assertEqual(json.loads((self.root/'preferences.json').read_text())['video'],values)

    def test_project_saves_and_ai_updates_do_not_overwrite_user_defaults(self):
        preferences.save({'video':{'fps':30,'font':'my.ttf'}})
        project=self.client.post('/api/projects',json={'draft':{'fps':12}}).json()
        draft=project['draft'];draft['fps']=24;draft['font']='ai.ttf'
        self.assertEqual(self.client.put('/api/projects/'+project['id'],json=draft).status_code,200)
        self.assertEqual(preferences.read()['video'],{'fps':30,'font':'my.ttf'})

    def test_partial_updates_and_clear_are_persisted(self):
        preferences.save({'video':{'font':'old.ttf','music_volume':.4},'ui':{'assetgen-mode':'multiple','assetgen-limit':'10'}})
        preferences.save({'video':{'font':None,'fps':60}})
        self.assertEqual(preferences.read()['video'],{'font':None,'music_volume':.4,'fps':60})
        self.assertEqual(preferences.read()['ui']['assetgen-mode'],'multiple')

    def test_settings_do_not_store_prompt_or_accept_invalid_values(self):
        for body in ({'video':{'prompt':'private content'}},{'video':{'fps':10000}}, {'ui':{'aspect':'bad'}}, {'secret':'value'}):
            self.assertEqual(self.client.post('/api/preferences',json=body).status_code,400)
        self.assertFalse((self.root/'preferences.json').exists())

    def test_library_directory_changes_preserve_preferences(self):
        preferences.save({'video':{'fps':30}})
        folder=self.root/'assets';folder.mkdir()
        library.set_directory(str(folder))
        self.assertEqual(preferences.read()['video']['fps'],30)

if __name__=='__main__':unittest.main()
