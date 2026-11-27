import asyncio
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave
from unittest.mock import patch

from codex_blender import audio, captions, config, local_voice, voice_clones


class LocalVoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        data = patch.object(config, 'DATA', self.root / 'data')
        data.start()
        self.addCleanup(data.stop)
        local = {'backend': 'Vulkan0'}
        for key in local_voice.FILES:
            path = self.root / (key + ' sample')
            path.write_bytes(b'reference')
            local[key] = str(path)
        self.record = {'id': 'tuan-anh', 'voice_id': 'local:tuan-anh', 'name': 'Tuấn Anh',
                       'state': 'ready', 'provider': 'voicestudio', 'local': local}
        voice_clones.save(self.record)
        self.destination = self.root / 'output' / 'speech.mp3'
        self.calls = []

    def run_engine(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if '-o' in command:
            with wave.open(command[command.index('-o')+1], 'wb') as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(24000)
                output.writeframes(b'\0\1'*24000)
        else:
            Path(command[-1]).write_bytes(b'converted MP3')
        return subprocess.CompletedProcess(command, 0, '', '')

    def test_registered_voice_routes_offline_and_hides_local_paths(self):
        option = voice_clones.options()[0]
        self.assertEqual(option['provider'], 'voicestudio')
        self.assertFalse(option['requires_api_key'])
        self.assertFalse(option['disabled'])
        self.assertNotIn('local', option)
        with patch.object(local_voice.subprocess, 'run', side_effect=self.run_engine), \
             patch.object(audio, 'synthesize_elevenlabs') as elevenlabs:
            asyncio.run(audio.synthesize('Xin chào!', option['id'], 100, self.destination, word_timing=True))
        elevenlabs.assert_not_called()
        self.assertEqual(self.destination.read_bytes(), b'converted MP3')
        native, kwargs = self.calls[0]
        self.assertEqual(kwargs['input'], 'Xin chào!')
        self.assertEqual(kwargs['encoding'], 'utf-8')
        self.assertEqual(kwargs['env']['GGML_BACKEND'], 'Vulkan0')
        self.assertEqual(native[native.index('--ref-text')+1], self.record['local']['reference_text'])
        self.assertIn('atempo=2.0000', self.calls[1][0])
        self.assertEqual(list((self.root/'temp').iterdir()), [])

    def test_failed_generation_preserves_existing_audio_and_timing(self):
        self.destination.parent.mkdir()
        self.destination.write_bytes(b'original')
        captions.save_words(self.destination, [{'text':'old','start':0,'end':1}])
        result = subprocess.CompletedProcess([], 1, '', 'vk::ErrorOutOfDeviceMemory private diagnostic')
        with patch.object(local_voice.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(RuntimeError, 'thiếu RAM') as error:
                local_voice.synthesize('Xin chào', 'local:tuan-anh', 0, self.destination)
        self.assertNotIn('private diagnostic', str(error.exception))
        self.assertEqual(self.destination.read_bytes(), b'original')
        self.assertTrue(captions.load_words(self.destination))
        self.assertEqual(list((self.root/'temp').iterdir()), [])

    def test_success_removes_stale_alignment_instead_of_fabricating_timestamps(self):
        self.destination.parent.mkdir()
        captions.save_words(self.destination, [{'text':'old','start':0,'end':1}])
        with patch.object(local_voice.subprocess, 'run', side_effect=self.run_engine):
            local_voice.synthesize('Xin chào', 'local:tuan-anh', -50, self.destination)
        self.assertFalse(captions.timing_path(self.destination).exists())
        self.assertIn('atempo=0.5000', self.calls[1][0])

    def test_bad_wav_cannot_be_reported_as_success(self):
        with patch.object(local_voice.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')):
            with self.assertRaisesRegex(RuntimeError, 'không hợp lệ'):
                local_voice.synthesize('Xin chào', 'local:tuan-anh', 0, self.destination)
        self.assertFalse(self.destination.exists())

    def test_conversion_failure_does_not_replace_existing_audio(self):
        self.destination.parent.mkdir()
        self.destination.write_bytes(b'original')
        def run(command, **kwargs):
            if '-o' in command:
                return self.run_engine(command, **kwargs)
            Path(command[-1]).write_bytes(b'partial MP3')
            return subprocess.CompletedProcess(command, 1)
        with patch.object(local_voice.subprocess, 'run', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'MP3'):
                local_voice.synthesize('Xin chào', 'local:tuan-anh', 0, self.destination)
        self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])
        self.assertEqual(self.destination.read_bytes(), b'original')

    def test_missing_reference_does_not_launch_engine(self):
        Path(self.record['local']['reference_text']).unlink()
        with patch.object(local_voice.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'Thiếu'):
                local_voice.synthesize('Xin chào', 'local:tuan-anh', 0, self.destination)
        run.assert_not_called()
