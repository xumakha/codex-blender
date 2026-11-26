"""Exercise the actual Blender -> PNG/.blend -> H.264 path (requires Blender/bpy)."""
import json
from pathlib import Path
import subprocess
import sys
import time
import imageio_ffmpeg
from codex_blender.models import SceneSpec
from codex_blender.jobs import submit, status

spec = SceneSpec.model_validate_json(Path("examples/product.json").read_text(encoding="utf-8"))
spec.width, spec.height, spec.duration, spec.fps = 320, 180, 1, 4
for obj in spec.objects:
    for key in obj.keyframes:
        key.time = key.time / 3
spec = SceneSpec.model_validate(spec.model_dump())
job = submit(spec, "video")
print(f"Smoke job: {job['id']}", flush=True)
deadline = time.monotonic() + 240
while time.monotonic() < deadline:
    result = status(job["id"])
    if result["state"] == "failed":
        raise RuntimeError(json.dumps(result, indent=2))
    if result["state"] == "completed":
        break
    time.sleep(1)
else:
    raise TimeoutError("Smoke job did not finish in 240 seconds")
video = result["artifacts"]["video.mp4"]
decode = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", video, "-f", "null", "-"], capture_output=True)
if decode.returncode:
    raise RuntimeError(decode.stderr.decode(errors="replace"))
assert Path(result["artifacts"]["scene.blend"]).stat().st_size > 1000
assert Path(result["artifacts"]["preview.png"]).stat().st_size > 1000
print(json.dumps(result, indent=2))
