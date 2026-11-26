import json
import os
import subprocess
import sys
import traceback
import imageio_ffmpeg
import psutil

from .config import ROOT, ASSETS, blender_command, asset_path
from .jobs import job_path, write_json


def main():
    path = job_path(sys.argv[1])
    data = json.loads((path / "status.json").read_text(encoding="utf-8"))
    data.update(pid=os.getpid(), process_created=psutil.Process().create_time())

    def update(**values):
        data.update(values)
        write_json(path / "status.json", data)

    try:
        update(state="rendering")
        command = blender_command() + [str(ROOT / "codex_blender" / "render_scene.py"), "--", str(path / "scene.json"), str(ASSETS), data["mode"]]
        env = os.environ.copy()
        # Keep Blender's user configuration and extension cache local to this job.
        for key, directory in (("BLENDER_USER_RESOURCES", "blender-user"), ("BLENDER_USER_CONFIG", "blender-user/config"), ("BLENDER_USER_EXTENSIONS", "blender-user/extensions")):
            local = path / directory
            local.mkdir(parents=True, exist_ok=True)
            env[key] = str(local)
        subprocess.run(command, check=True, cwd=ROOT, timeout=7200, env=env)
        if not (path / "preview.png").exists() or not (path / "scene.blend").exists():
            raise RuntimeError("Blender exited without writing the expected artifacts")
        if data["mode"] == "video":
            update(state="encoding")
            spec = json.loads((path / "scene.json").read_text(encoding="utf-8"))
            command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-framerate", str(spec["fps"]), "-start_number", "1", "-i", str(path / "frames" / "frame_%04d.png")]
            if spec["audio"]:
                command += ["-i", str(asset_path(spec["audio"])), "-map", "0:v:0", "-map", "1:a:0", "-af", "apad", "-c:a", "aac"]
            command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-t", str(max(1, round(spec["duration"] * spec["fps"])) / spec["fps"]), str(path / "video.mp4")]
            subprocess.run(command, check=True, timeout=1800)
            if not (path / "video.mp4").is_file() or (path / "video.mp4").stat().st_size == 0:
                raise RuntimeError("Video encoding produced no output")
        update(state="completed")
    except Exception as exc:
        traceback.print_exc()
        update(state="failed", error=str(exc))


if __name__ == "__main__":
    main()
