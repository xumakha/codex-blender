import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from codex_blender import jobs
from codex_blender.pause_control import checkpoint


class PauseTests(unittest.TestCase):
    def test_pause_checkpoint_resume_preserves_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / ('a' * 32)
            path.mkdir()
            (path / 'frames').mkdir()
            frame = path / 'frames' / 'frame_0001.png'
            frame.write_bytes(b'completed frame')
            jobs.write_json(path / 'status.json', {
                'id': path.name, 'state': 'rendering', 'mode': 'video', 'frames_total': 10,
            })
            entered = threading.Event()
            finished = threading.Event()

            def render():
                entered.set()
                checkpoint(path)
                finished.set()

            with patch.object(jobs, 'OUTPUTS', root):
                self.assertEqual(jobs.control(path.name, 'pause')['state'], 'pausing')
                thread = threading.Thread(target=render)
                thread.start()
                try:
                    self.assertTrue(entered.wait(2))
                    # Wait for the checkpoint to acknowledge the request.
                    import time
                    deadline = time.monotonic() + 2
                    while not (path / '.paused').exists() and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertEqual(jobs.status(path.name)['state'], 'paused')
                    self.assertFalse(finished.is_set())
                    self.assertEqual(jobs.status(path.name)['frames_rendered'], 1)
                    self.assertEqual(jobs.control(path.name, 'resume')['state'], 'rendering')
                    self.assertTrue(finished.wait(2))
                finally:
                    (path / '.pause-requested').unlink(missing_ok=True)
                    thread.join(3)
                self.assertFalse((path / '.paused').exists())
                self.assertEqual(frame.read_bytes(), b'completed frame')
                self.assertEqual(json.loads((path / 'status.json').read_text())['state'], 'rendering')

    def test_reject_pause_after_render_and_resume_without_pause(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / ('b' * 32)
            path.mkdir()
            with patch.object(jobs, 'OUTPUTS', root):
                for state in ('encoding', 'completed', 'failed'):
                    jobs.write_json(path / 'status.json', {'state': state})
                    with self.assertRaises(ValueError):
                        jobs.control(path.name, 'pause')
                    self.assertFalse((path / '.pause-requested').exists())
                jobs.write_json(path / 'status.json', {'state': 'rendering'})
                with self.assertRaises(ValueError):
                    jobs.control(path.name, 'resume')
                with self.assertRaises(ValueError):
                    jobs.control(path.name, 'unknown')

    def test_dead_paused_worker_is_reported_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / ('c' * 32)
            path.mkdir()
            jobs.write_json(path / 'status.json', {
                'state': 'rendering', 'pid': 123, 'process_created': 0, 'frames_total': 10,
            })
            (path / '.pause-requested').touch()
            (path / '.paused').touch()
            import psutil
            with patch.object(jobs, 'OUTPUTS', root), patch('psutil.Process', side_effect=psutil.NoSuchProcess(123)):
                self.assertEqual(jobs.status(path.name)['state'], 'failed')
