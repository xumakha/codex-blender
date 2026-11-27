import asyncio
from email.message import Message
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from codex_blender import audio, config, credentials


class AudioResponse(io.BytesIO):
    def __init__(self, content=b'ID3-audio', content_type='audio/mpeg'):
        super().__init__(content)
        self.headers=Message()
        self.headers['Content-Type']=content_type


class ElevenLabsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for module,name,value in [(config,'DATA',self.root/'data'),(credentials,'ENV_FILE',self.root/'.env'),
                                  (audio,'elevenlabs_command',lambda:['elevenlabs-test'])]:
            item=patch.object(module,name,value);item.start();self.addCleanup(item.stop)
        item=patch.dict(os.environ,{'ELEVENLABS_API_KEY':'test-secret'})
        item.start();self.addCleanup(item.stop)

    def synthesize(self, destination, text='Xin chào!', rate=0):
        return asyncio.run(audio.synthesize(text,audio.ELEVENLABS_VOICE_ID,rate,destination))

    def success(self,command,**kwargs):
        Path(command[command.index('--output')+1]).write_bytes(b'ID3-audio')
        return subprocess.CompletedProcess(command,0,'','')

    def failure(self,code=402,reason='paid_plan_required'):
        return subprocess.CompletedProcess([],1,json.dumps({'error':{'code':code,'reason':reason,
            'message':'never echo test-secret','details':{'detail':{'code':reason}}}}),'')

    def test_selected_voice_uses_cli_stdin_and_secret_only_in_environment(self):
        destination=self.root/'voice.mp3'
        with patch.object(audio.subprocess,'run',side_effect=self.success) as run:
            self.synthesize(destination)
        command=run.call_args.args[0]
        self.assertEqual(command[:3],['elevenlabs-test','text-to-speech','convert'])
        self.assertIn(audio.ELEVENLABS_VOICE_ID,command)
        self.assertEqual(json.loads(run.call_args.kwargs['input']),{'text':'Xin chào!','model_id':audio.ELEVENLABS_MODEL})
        self.assertEqual(run.call_args.kwargs['env']['ELEVENLABS_API_KEY'],'test-secret')
        self.assertNotIn('test-secret',' '.join(command))
        self.assertIn('--no-retry',command)
        self.assertEqual(destination.read_bytes(),b'ID3-audio')

    def test_new_project_key_replaces_old_settings_key_and_later_save_overrides(self):
        credentials.save_elevenlabs('old-key')
        credentials.ENV_FILE.write_text('ELEVENLABS_API_KEY=sk_project-key\n')
        os.utime(credentials.ENV_FILE,(2000000000,2000000000))
        self.assertEqual(credentials.elevenlabs_key(),'sk_project-key')
        self.assertEqual(credentials.status()['source'],'project-env')
        self.assertNotIn('sk_project-key',json.dumps(credentials.status()))
        credentials.save_elevenlabs('new-settings-key')
        os.utime(config.DATA/'credentials.json',(2000000001,2000000001))
        self.assertEqual(credentials.elevenlabs_key(),'new-settings-key')
        credentials.delete_elevenlabs()
        self.assertEqual(credentials.elevenlabs_key(),'sk_project-key')

    def test_missing_or_dashboard_id_key_fails_before_cli(self):
        for key in ['', 'a'*64]:
            with patch.dict(os.environ,{'ELEVENLABS_API_KEY':key}),patch.object(audio.subprocess,'run') as run:
                with self.assertRaises(ValueError):self.synthesize(self.root/'voice.mp3')
                run.assert_not_called()

    def test_paid_voice_and_exhausted_credit_errors_are_distinct_and_safe(self):
        for reason,message in [('paid_plan_required','gói Free'),('quota_exceeded','hạn mức'),
                               ('insufficient_credits','hạn mức'),('missing_permissions','quyền')]:
            destination=self.root/'voice.mp3';destination.write_bytes(b'existing')
            with patch.object(audio.subprocess,'run',return_value=self.failure(reason=reason)):
                with self.assertRaisesRegex(RuntimeError,message) as raised:self.synthesize(destination)
            self.assertNotIn('test-secret',str(raised.exception))
            self.assertEqual(destination.read_bytes(),b'existing')
            self.assertEqual(list(self.root.glob('*.partial.mp3')),[])

    def test_http_error_helper_understands_paid_plan(self):
        error=HTTPError('https://api.elevenlabs.io',402,'Error',{},io.BytesIO(b'{"detail":{"code":"paid_plan_required"}}'))
        self.assertIn('gói Free',audio.elevenlabs_error(error))

    def test_empty_audio_and_unstructured_failures_do_not_replace_existing_audio(self):
        destination=self.root/'voice.mp3';destination.write_bytes(b'existing')
        for result in [subprocess.CompletedProcess([],0,'',''),subprocess.CompletedProcess([],1,'test-secret','test-secret')]:
            with patch.object(audio.subprocess,'run',return_value=result):
                with self.assertRaises(RuntimeError) as raised:self.synthesize(destination)
                self.assertNotIn('test-secret',str(raised.exception))
            self.assertEqual(destination.read_bytes(),b'existing')

    def test_timeout_is_sanitized(self):
        with patch.object(audio.subprocess,'run',side_effect=subprocess.TimeoutExpired(['secret-command'],120)):
            with self.assertRaisesRegex(RuntimeError,'quá lâu') as raised:self.synthesize(self.root/'voice.mp3')
            self.assertNotIn('secret-command',str(raised.exception))

    def test_speed_adjustment_preserves_selected_rate(self):
        destination=self.root/'voice.mp3'
        def run(command,**kwargs):
            if command[0]=='elevenlabs-test':return self.success(command,**kwargs)
            self.assertIn('atempo=1.4000',command)
            Path(command[-1]).write_bytes(b'adjusted')
            return subprocess.CompletedProcess(command,0)
        with patch.object(audio.subprocess,'run',side_effect=run),patch.object(audio.imageio_ffmpeg,'get_ffmpeg_exe',return_value='ffmpeg'):
            self.synthesize(destination,rate=40)
        self.assertEqual(destination.read_bytes(),b'adjusted')
        self.assertEqual(list(self.root.glob('*.mp3')),[destination])

    def test_voice_and_text_validation_prevents_cli_requests(self):
        with patch.object(audio.subprocess,'run') as run:
            for text,rate in [('',0),('Hi',101),('Hi',-51),('x'*15001,0)]:
                with self.assertRaises(ValueError):self.synthesize(self.root/'voice.mp3',text=text,rate=rate)
            with self.assertRaises(ValueError):asyncio.run(audio.synthesize('Hi','unknown',0,self.root/'voice.mp3'))
            run.assert_not_called()
