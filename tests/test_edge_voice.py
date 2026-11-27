import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import edge_tts
from codex_blender import audio, captions


class EdgeVoiceTests(unittest.TestCase):
    def test_reconnects_same_voice_without_reusing_partial_audio_or_timestamps(self):
        calls=[]
        class Communicate:
            def __init__(self,text,voice,**kwargs):
                calls.append((text,voice,kwargs))
                self.attempt=len(calls)
            async def save(self,audio_file,metadata_file):
                # Failed streams must not be concatenated into the retry.
                assert not Path(audio_file).exists()
                assert not Path(metadata_file).exists()
                Path(audio_file).write_bytes(b'partial' if self.attempt<3 else b'complete')
                Path(metadata_file).write_text(json.dumps({'type':'WordBoundary','text':'Xin',
                    'offset':1000000,'duration':2000000}),encoding='utf-8')
                if self.attempt<3:raise edge_tts.exceptions.NoAudioReceived('temporary failure')
        with tempfile.TemporaryDirectory() as tmp,patch('edge_tts.Communicate',Communicate), \
             patch.object(audio.asyncio,'sleep',new_callable=AsyncMock) as sleep:
            destination=Path(tmp)/'voice.mp3'
            asyncio.run(audio.synthesize('Xin chào!','vi-VN-NamMinhNeural',20,destination,word_timing=True))
            self.assertEqual(len(calls),3)
            self.assertTrue(all(text=='Xin chào!' and voice=='vi-VN-NamMinhNeural' and
                                kwargs=={'rate':'+20%','boundary':'WordBoundary'} for text,voice,kwargs in calls))
            self.assertEqual(destination.read_bytes(),b'complete')
            self.assertEqual(captions.load_words(destination),[{'text':'Xin','start':.1,'end':.3}])
            self.assertEqual(sleep.await_count,2)
            self.assertFalse(list(Path(tmp).glob('*.partial.*')))

    def test_persistent_failure_preserves_existing_audio_and_cleans_temporary_files(self):
        calls=[]
        class Communicate:
            def __init__(self,*args,**kwargs):calls.append(kwargs)
            async def save(self,audio_file,metadata_file):
                Path(audio_file).write_bytes(b'incomplete')
                raise edge_tts.exceptions.NoAudioReceived('untrusted response')
        with tempfile.TemporaryDirectory() as tmp,patch('edge_tts.Communicate',Communicate), \
             patch.object(audio.asyncio,'sleep',new_callable=AsyncMock):
            destination=Path(tmp)/'voice.mp3';destination.write_bytes(b'existing')
            with self.assertRaisesRegex(RuntimeError,'Nam Minh.*5 lần') as raised:
                asyncio.run(audio.synthesize('Xin chào!','vi-VN-NamMinhNeural',0,destination))
            self.assertNotIn('untrusted response',str(raised.exception))
            self.assertEqual(destination.read_bytes(),b'existing')
            self.assertEqual(list(Path(tmp).iterdir()),[destination])
            self.assertEqual(len(calls),5)
            self.assertTrue(all(kwargs['boundary']=='SentenceBoundary' for kwargs in calls))

    def test_empty_audio_is_retried_and_timeouts_can_recover(self):
        calls=[]
        class Communicate:
            def __init__(self,*args,**kwargs):calls.append(1);self.attempt=len(calls)
            async def save(self,audio_file,metadata_file):
                if self.attempt==1:raise TimeoutError('temporary timeout')
                Path(audio_file).write_bytes(b'' if self.attempt==2 else b'complete')
        with tempfile.TemporaryDirectory() as tmp,patch('edge_tts.Communicate',Communicate), \
             patch.object(audio.asyncio,'sleep',new_callable=AsyncMock):
            destination=Path(tmp)/'voice.mp3'
            asyncio.run(audio.synthesize('Xin chào!','vi-VN-NamMinhNeural',0,destination))
            self.assertEqual(destination.read_bytes(),b'complete')
            self.assertEqual(len(calls),3)
