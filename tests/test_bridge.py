import asyncio
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import tempfile

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
