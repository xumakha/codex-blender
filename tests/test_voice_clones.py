import asyncio
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from codex_blender import audio, config, voice_clones


class VoiceCloneTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.sample=self.root/'voice sample & narrative.mp3'
        self.sample.write_bytes(b'test sample')
        for module,name,value in [(config,'DATA',self.root/'data'),
                                  (voice_clones,'elevenlabs_key',lambda:'test-secret'),
                                  (config,'elevenlabs_command',lambda:['elevenlabs-test'])]:
            item=patch.object(module,name,value);item.start();self.addCleanup(item.stop)

    def reply(self,payload,code=0):
        return subprocess.CompletedProcess([],code,json.dumps(payload),'')

    def test_success_registers_real_voice_id_and_routes_speech_to_elevenlabs(self):
        with patch.object(voice_clones.subprocess,'run',return_value=self.reply({'voice_id':'custom-voice','requires_verification':False})) as run:
            item=voice_clones.create(self.sample,'Tuấn Anh')
        self.assertEqual(item['state'],'ready')
        command=run.call_args.args[0]
        self.assertEqual(command[command.index('--name')+1],'Tuấn Anh')
        self.assertNotIn('test-secret',' '.join(command))
        self.assertEqual(run.call_args.kwargs['env']['ELEVENLABS_API_KEY'],'test-secret')
        option=next(v for v in audio.voice_options() if v['id']=='custom-voice')
        self.assertFalse(option['disabled'])
        self.assertNotIn('sample',option)
        with patch.object(audio,'synthesize_elevenlabs') as speak:
            asyncio.run(audio.synthesize('Xin chào!','custom-voice',0,self.root/'speech.mp3'))
            self.assertEqual(speak.call_args.args[1],'custom-voice')
        with patch.object(voice_clones.subprocess,'run') as run:
            self.assertEqual(voice_clones.create(self.sample,'Tuấn Anh')['voice_id'],'custom-voice')
            run.assert_not_called()

    def test_failed_clone_keeps_sample_and_disabled_option_without_fake_voice_id(self):
        with patch.object(voice_clones.subprocess,'run',return_value=self.reply({'error':{'reason':'paid_plan_required','code':400}},1)):
            with self.assertRaisesRegex(RuntimeError,'Instant Voice Cloning'):
                voice_clones.create(self.sample,'Tuấn Anh')
        record=voice_clones.records()[0]
        self.assertIsNone(record['voice_id'])
        self.assertEqual(Path(record['sample']).read_bytes(),b'test sample')
        option=voice_clones.options()[0]
        self.assertTrue(option['disabled'])
        self.assertEqual(option['name'],'Tuấn Anh')
        with patch.object(audio,'synthesize_elevenlabs') as speak:
            with self.assertRaisesRegex(ValueError,'Instant Voice Cloning'):
                asyncio.run(audio.synthesize('Hi',option['id'],0,self.root/'speech.mp3'))
            speak.assert_not_called()

    def test_retry_reuses_registration_and_activates_option(self):
        failure=self.reply({'error':{'reason':'paid_plan_required','code':400}},1)
        success=self.reply({'voice_id':'verified-voice'})
        with patch.object(voice_clones.subprocess,'run',side_effect=[failure,success]):
            with self.assertRaises(RuntimeError):voice_clones.create(self.sample,'Tuấn Anh')
            previous=voice_clones.records()[0]
            item=voice_clones.create(Path(previous['sample']),'Tuấn Anh')
        self.assertEqual(len(voice_clones.records()),1)
        self.assertEqual(item['id'],previous['id'])
        self.assertFalse(voice_clones.options()[0]['disabled'])

    def test_verification_is_required_before_using_voice(self):
        with patch.object(voice_clones.subprocess,'run',return_value=self.reply({'voice_id':'needs-verification','requires_verification':True})):
            item=voice_clones.create(self.sample,'Tuấn Anh')
        self.assertEqual(item['state'],'verification')
        self.assertTrue(voice_clones.options()[0]['disabled'])

    def test_provider_failure_never_exposes_response_or_credential(self):
        with patch.object(voice_clones.subprocess,'run',return_value=self.reply({'error':{'message':'test-secret'}},1)):
            with self.assertRaises(RuntimeError):voice_clones.create(self.sample,'Tuấn Anh')
        self.assertNotIn('test-secret',json.dumps(voice_clones.records()))
