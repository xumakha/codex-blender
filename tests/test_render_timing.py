import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_blender import jobs, render_timing


class RenderTimingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / ('a' * 32)
        self.path.mkdir()
        (self.path / 'frames').mkdir()
        self.patch = patch.object(jobs, 'OUTPUTS', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def status(self, state='rendering'):
        jobs.write_json(self.path / 'status.json', {'id':self.path.name, 'state':state,
                        'mode':'video', 'frames_total':100})
        return jobs.status(self.path.name)

    def test_estimate_uses_remaining_frames_and_persists_across_polls(self):
        for index in range(10):
            (self.path / 'frames' / f'frame_{index:04d}.png').write_bytes(b'frame')
        render_timing.record_frame(self.path, 2)
        render_timing.record_frame(self.path, 4)
        self.assertEqual(self.status()['eta_seconds'],270)
        self.assertEqual(jobs.status(self.path.name)['eta_seconds'],270)
        (self.path / 'frames' / 'frame_0010.png').write_bytes(b'frame')
        self.assertEqual(jobs.status(self.path.name)['eta_seconds'],267)

    def test_recent_speed_replaces_old_speed(self):
        for _ in range(20):render_timing.record_frame(self.path, 10)
        for _ in range(20):render_timing.record_frame(self.path, 2)
        self.assertEqual(self.status()['eta_seconds'],200)

    def test_no_estimate_before_first_frame_or_for_invalid_timing(self):
        self.assertIsNone(self.status()['eta_seconds'])
        for value in ['broken', 'null', '[0, -1, "bad"]']:
            (self.path / 'render-timing.json').write_text(value)
            self.assertIsNone(self.status()['eta_seconds'])

    def test_pause_failure_queue_encoding_and_completion(self):
        render_timing.record_frame(self.path, 2)
        self.status()
        (self.path / '.pause-requested').touch()
        self.assertIsNone(jobs.status(self.path.name)['eta_seconds'])
        (self.path / '.paused').touch()
        self.assertIsNone(jobs.status(self.path.name)['eta_seconds'])
        (self.path / '.pause-requested').unlink()
        (self.path / '.paused').unlink()
        self.assertEqual(jobs.status(self.path.name)['eta_seconds'],200)
        for state in ['failed','queued','encoding']:
            self.assertIsNone(self.status(state)['eta_seconds'])
        self.assertEqual(self.status('completed')['state'], 'failed')
        (self.path / 'preview.png').write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND\xaeB`\x82')
        (self.path / 'scene.blend').write_bytes(b'BLENDER' + b'\x00' * 16)
        (self.path / 'video.mp4').write_bytes(b'mp4')
        self.assertEqual(self.status('completed')['eta_seconds'],0)

    def test_retry_discards_timings_from_previous_run(self):
        from codex_blender.models import SceneSpec
        spec=SceneSpec(objects=[{'name':'cube','kind':'cube'}])
        jobs.write_json(self.path / 'scene.json', spec.model_dump(mode='json'))
        render_timing.record_frame(self.path, 20)
        self.status('failed')
        with patch.object(jobs,'launch_worker'),patch.object(jobs,'validate_assets'),patch.object(jobs,'blender_command'):
            self.assertIsNone(jobs.retry(self.path.name)['eta_seconds'])
        self.assertFalse((self.path / 'render-timing.json').exists())
