import asyncio
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_blender import audio, captions
from test_elevenlabs import AudioResponse


class CaptionTests(unittest.TestCase):
    def test_edge_word_boundaries_are_recorded(self):
        class Communicate:
            def __init__(self, *args, **kwargs):
                self.boundary = kwargs['boundary']

            async def save(self, audio_name, metadata_name):
                assert self.boundary == 'WordBoundary'
                Path(audio_name).write_bytes(b'voice')
                Path(metadata_name).write_text(json.dumps({'type':'WordBoundary','text':'Hello',
                                                          'offset':5000000,'duration':4000000}), encoding='utf-8')

        with tempfile.TemporaryDirectory() as tmp, patch('edge_tts.Communicate',Communicate):
            destination = Path(tmp)/'edge.mp3'
            asyncio.run(audio.synthesize('Hello','en-US-GuyNeural',0,destination,word_timing=True))
            self.assertEqual(captions.load_words(destination),[{'text':'Hello','start':.5,'end':.9}])
            self.assertFalse(list(Path(tmp).glob('*.jsonl')))

    def test_provider_boundaries_keep_punctuation_and_clip_to_cue(self):
        words=[{'text':'Xin chào','start':.2,'end':1.2}]
        result=captions.word_events('Xin chào!',5,5.9,words)
        self.assertEqual([w['text'] for w in result],['Xin','chào!'])
        self.assertTrue(all(w['timing']=='provider' for w in result))
        self.assertTrue(all(w['end']<=5.9 for w in result))

    def test_alignment_preserves_accents_and_pauses(self):
        alignment = {'characters': list('Xin chào!'),
                     'character_start_times_seconds': [0,.1,.2,.3,.8,.9,1,1.1,1.2],
                     'character_end_times_seconds': [.1,.2,.3,.4,.9,1,1.1,1.2,1.3]}
        words = captions.alignment_words(alignment)
        self.assertEqual([w['text'] for w in words], ['Xin','chào!'])
        events = captions.word_events('Xin chào!', 6, 9, words)
        self.assertEqual(events[0]['start'],6)
        self.assertAlmostEqual(events[0]['end'],6.45)
        self.assertAlmostEqual(events[1]['start'],6.8)

    def test_fitted_speech_retimes_words_without_stretching_silence(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, destination = Path(tmp)/'source.mp3', Path(tmp)/'fit.wav'
            captions.save_words(source, [{'text':'Hello', 'start':.4,'end':1.2}])
            with patch.object(audio, 'audio_duration', return_value=6), patch.object(audio.subprocess, 'run'), patch.object(audio.imageio_ffmpeg,'get_ffmpeg_exe',return_value='ffmpeg'):
                audio.fit_speech(source, destination, 5)
            result = captions.load_words(destination)
            self.assertAlmostEqual(result[0]['start'],1/3)
            self.assertAlmostEqual(result[0]['end'],1)
            captions.retime_words(source,destination,1)
            self.assertEqual(captions.load_words(destination)[0]['end'],1.2)

    def test_elevenlabs_timestamps_are_saved_at_selected_speed(self):
        payload = {'audio_base64':base64.b64encode(b'ID3-audio').decode(),
                   'alignment':{'characters':list('Hi'), 'character_start_times_seconds':[.2,.4],
                                'character_end_times_seconds':[.4,.8]}}
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)/'voice.mp3'
            def convert(cmd, **kwargs):
                if cmd[0]=='elevenlabs-test':
                    return type('Result',(),{'returncode':0,'stdout':json.dumps(payload),'stderr':''})()
                Path(cmd[-1]).write_bytes(b'adjusted')
                return type('Result',(),{'returncode':0})()
            with patch('codex_blender.credentials.elevenlabs_key',return_value='test-secret'), \
                 patch.object(audio,'elevenlabs_command',return_value=['elevenlabs-test']), \
                 patch.object(audio.subprocess,'run',side_effect=convert), patch.object(audio.imageio_ffmpeg,'get_ffmpeg_exe',return_value='ffmpeg'):
                asyncio.run(audio.synthesize('Hi',audio.ELEVENLABS_VOICE_ID,25,destination,word_timing=True))
            self.assertAlmostEqual(captions.load_words(destination)[0]['start'],.16)
            self.assertAlmostEqual(captions.load_words(destination)[0]['end'],.64)

    def test_ass_uses_single_word_pop_and_escapes_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'captions.ass'
            events = captions.word_events('Xin chào! {test}',1,3)
            captions.write_ass(path,events,720,1280,'Arial')
            result = path.read_text(encoding='utf-8')
            lines = [line for line in result.splitlines() if line.startswith('Dialogue:')]
            self.assertEqual(len(lines),3)
            self.assertNotIn('Xin chào!',result)
            self.assertIn('\\fscy112',result)
            self.assertIn('｛test｝',result)
