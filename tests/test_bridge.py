import asyncio
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import tempfile
import importlib.util
from types import SimpleNamespace

from pydantic import ValidationError
from codex_blender.models import SceneSpec
from codex_blender.config import asset_path
from codex_blender import jobs


class BridgeTests(unittest.TestCase):
    def test_example_and_invalid_timeline(self):
        raw = json.loads(Path("examples/product.json").read_text(encoding="utf-8"))
        self.assertEqual(SceneSpec.model_validate(raw).fps, 24)
        raw["objects"][0]["keyframes"][0]["time"] = 10
        with self.assertRaises(ValidationError):
            SceneSpec.model_validate(raw)

    def test_reject_nonfinite_and_unknown_code(self):
        with self.assertRaises(ValidationError):
            SceneSpec(objects=[{"name": "bad", "kind": "cube", "location": [float("nan"), 0, 0]}])
        with self.assertRaises(ValidationError):
            SceneSpec(objects=[{"name": "bad", "kind": "cube", "python": "print('bad')"}])

    def test_asset_and_job_paths_cannot_escape(self):
        with self.assertRaises(ValueError):
            asset_path("../pyproject.toml")
        with self.assertRaises(ValueError):
            jobs.job_path("../../other")

    def test_failed_launch_records_failed_job(self):
        spec = SceneSpec(objects=[{"name": "box", "kind": "cube"}])
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(jobs, "OUTPUTS", Path(tmp)), patch.object(jobs, "blender_command", return_value=["blender"]), patch.object(jobs.subprocess, "Popen", side_effect=OSError("launch failed")):
                with self.assertRaises(OSError):
                    jobs.submit(spec)
                saved = json.loads(next(Path(tmp).glob("*/status.json")).read_text())
                self.assertEqual(saved["state"], "failed")

    def test_retry_preserves_frames_log_and_original_asset_directory(self):
        spec=SceneSpec(objects=[{"name":"box","kind":"cube"}])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            job=root/('a'*32);job.mkdir()
            assets=root/'assets';assets.mkdir()
            (job/'frames').mkdir()
            frame=job/'frames'/'frame_0001.png';frame.write_bytes(b'completed frame')
            (job/'render.log').write_text('original log\n')
            jobs.write_json(job/'scene.json',spec.model_dump(mode='json'))
            jobs.write_json(job/'status.json',{'id':job.name,'state':'failed','error':'interrupted','pid':99,
                'process_created':0,'mode':'video','frames_total':120,'assets_directory':str(assets)})
            with patch.object(jobs,'OUTPUTS',root),patch.object(jobs,'blender_command',return_value=['blender']),patch.object(jobs.subprocess,'Popen') as launch:
                result=jobs.retry(job.name)
                self.assertEqual(result['state'],'queued')
                self.assertEqual(result['frames_rendered'],1)
                self.assertNotIn('pid',result)
                self.assertNotIn('error',result)
                self.assertEqual(result['assets_directory'],str(assets))
                self.assertEqual(frame.read_bytes(),b'completed frame')
                self.assertIn('original log',(job/'render.log').read_text())
                self.assertEqual(launch.call_count,1)
                # A second click while the replacement worker starts must not launch twice.
                with self.assertRaises(ValueError):jobs.retry(job.name)
                self.assertEqual(launch.call_count,1)

    def test_resume_renders_missing_and_truncated_frames_only(self):
        fake_bpy=SimpleNamespace(ops=SimpleNamespace(render=SimpleNamespace(render=lambda **kw:None)))
        with patch.dict(sys.modules,{'bpy':fake_bpy,'mathutils':SimpleNamespace(Vector=None,Matrix=None)}):
            module_spec=importlib.util.spec_from_file_location('render_resume_test','codex_blender/render_scene.py')
            renderer=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(renderer)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            complete=root/'frame_0001.png'
            complete.write_bytes(b'\x89PNG\r\n\x1a\n'+b'complete'+b'\x00\x00\x00\x00IEND\xaeB`\x82')
            original=complete.read_bytes()
            (root/'frame_0002.png').write_bytes(b'\x89PNG\r\n\x1a\ntruncated')
            rendered=[]
            scene=SimpleNamespace(frame_start=1,frame_end=3,frame_set=rendered.append,render=SimpleNamespace(filepath=''))
            renderer.render_frames(scene,root)
            self.assertEqual(rendered,[2,3])
            self.assertEqual(complete.read_bytes(),original)

    def test_mcp_client_discovers_and_calls_tools(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        async def check():
            params = StdioServerParameters(command=sys.executable, args=["-m", "codex_blender.server"])
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    names = {t.name for t in result.tools}
                    self.assertIn("create_video", names)
                    self.assertIn("video_preview", names)
                    info = await session.call_tool("blender_info", {})
                    self.assertFalse(info.isError)
                    invalid = await session.call_tool("create_video", {"scene": {"objects": [{"name": "bad", "kind": "python"}]}})
                    self.assertTrue(invalid.isError)
        asyncio.run(check())


if __name__ == "__main__":
    unittest.main()
