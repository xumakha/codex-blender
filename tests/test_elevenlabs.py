import asyncio
from email.message import Message
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from codex_blender import audio


class AudioResponse(io.BytesIO):
    def __init__(self, content=b'ID3-audio', content_type='audio/mpeg'):
        super().__init__(content)
        self.headers = Message()
        self.headers['Content-Type'] = content_type


class ElevenLabsTests(unittest.TestCase):
    def synthesize(self, destination, text='Xin chào!', rate=0):
        return asyncio.run(audio.synthesize(text, audio.ELEVENLABS_VOICE_ID, rate, destination))

    def test_selected_voice_calls_elevenlabs_and_saves_audio(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'test-secret'}):
            destination = Path(tmp) / 'voice.mp3'
            with patch.object(audio.urllib.request, 'urlopen', return_value=AudioResponse()) as send:
                self.synthesize(destination)
            request = send.call_args.args[0]
            self.assertEqual(request.method, 'POST')
            self.assertEqual(request.full_url,
                'https://api.elevenlabs.io/v1/text-to-speech/gb30mYs9RQJGV3jqCOM2?output_format=mp3_44100_128')
            self.assertEqual(request.get_header('Xi-api-key'), 'test-secret')
            self.assertEqual(json.loads(request.data), {'text': 'Xin chào!', 'model_id': 'eleven_flash_v2_5'})
            self.assertEqual(destination.read_bytes(), b'ID3-audio')
            self.assertEqual(list(Path(tmp).iterdir()), [destination])

    def test_missing_key_fails_before_network_request(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'ELEVENLABS_API_KEY': ''}), \
                patch.object(audio.urllib.request, 'urlopen') as send:
            with self.assertRaisesRegex(ValueError, 'ELEVENLABS_API_KEY'):
                self.synthesize(Path(tmp) / 'voice.mp3')
            send.assert_not_called()
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_provider_failures_keep_existing_audio_and_hide_response_body(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'test-secret'}):
            destination = Path(tmp) / 'voice.mp3'
            destination.write_bytes(b'existing audio')
            for code in (401, 403, 404, 429, 500):
                error = HTTPError('https://api.elevenlabs.io', code, 'test-secret', {}, io.BytesIO(b'test-secret'))
                with self.subTest(code=code), patch.object(audio.urllib.request, 'urlopen', side_effect=error):
                    with self.assertRaises(RuntimeError) as raised:
                        self.synthesize(destination)
                    self.assertNotIn('test-secret', str(raised.exception))
                    self.assertEqual(destination.read_bytes(), b'existing audio')
                    self.assertEqual(list(Path(tmp).iterdir()), [destination])

    def test_empty_invalid_and_interrupted_responses_are_cleaned_up(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'test-secret'}):
            destination = Path(tmp) / 'voice.mp3'
            for response in (AudioResponse(b''), AudioResponse(b'{"error":true}', 'application/json')):
                with patch.object(audio.urllib.request, 'urlopen', return_value=response):
                    with self.assertRaises(RuntimeError):
                        self.synthesize(destination)
                self.assertEqual(list(Path(tmp).iterdir()), [])
            with patch.object(audio.urllib.request, 'urlopen', side_effect=URLError('network unavailable')):
                with self.assertRaisesRegex(RuntimeError, 'Không kết nối'):
                    self.synthesize(destination)

    def test_speed_adjustment_preserves_selected_rate(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'test-secret'}):
            destination = Path(tmp) / 'voice.mp3'

            def convert(command, **kwargs):
                self.assertIn('atempo=1.4000', command)
                Path(command[-1]).write_bytes(b'adjusted audio')
                return type('Result', (), {'returncode': 0})()

            with patch.object(audio.urllib.request, 'urlopen', return_value=AudioResponse()), \
                    patch.object(audio.imageio_ffmpeg, 'get_ffmpeg_exe', return_value='ffmpeg'), \
                    patch.object(audio.subprocess, 'run', side_effect=convert):
                self.synthesize(destination, rate=40)
            self.assertEqual(destination.read_bytes(), b'adjusted audio')
            self.assertEqual(list(Path(tmp).iterdir()), [destination])

    def test_voice_and_text_validation_prevents_requests(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(audio.urllib.request, 'urlopen') as send:
            for text, rate in (('', 0), ('Hi', 101), ('Hi', -51), ('x' * 15001, 0)):
                with self.assertRaises(ValueError):
                    self.synthesize(Path(tmp) / 'voice.mp3', text=text, rate=rate)
            with self.assertRaises(ValueError):
                asyncio.run(audio.synthesize('Hi', 'unknown-voice', 0, Path(tmp) / 'voice.mp3'))
            send.assert_not_called()
