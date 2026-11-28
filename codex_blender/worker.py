import json
import os
import subprocess
import sys
import traceback
import time
from pathlib import Path
import imageio_ffmpeg
import psutil

from .config import ROOT, ASSETS, blender_command, asset_path
from .jobs import job_path, write_json
from .audio import encode_video
from .pause_control import checkpoint
from .render_artifacts import complete_png, complete_blend


def main():
    path = job_path(sys.argv[1])
    data = json.loads((path / "status.json").read_text(encoding="utf-8"))
    root = Path(data.get("assets_directory", str(ASSETS)))
    data.update(pid=os.getpid(), process_created=psutil.Process().create_time())

    def update(**values):
        data.update(values)
        write_json(path / "status.json", data)

    try:
        print(f"Render worker {os.getpid()} started for {data['id']}", flush=True)
        update(state="rendering")
        checkpoint(path)
        command = blender_command() + [str(ROOT / "codex_blender" / "render_scene.py"), "--", str(path / "scene.json"), str(root), data["mode"]]
        env = os.environ.copy()
        # Keep Blender's user configuration and extension cache local to this job.
        for key, directory in (("BLENDER_USER_RESOURCES", "blender-user"), ("BLENDER_USER_CONFIG", "blender-user/config"), ("BLENDER_USER_EXTENSIONS", "blender-user/extensions")):
            local = path / directory
            local.mkdir(parents=True, exist_ok=True)
            env[key] = str(local)
        # Paused time must not consume the render timeout.
        with subprocess.Popen(command, cwd=ROOT, env=env) as renderer:
            active_seconds = 0
            last = time.monotonic()
            try:
                timeout = max(1, int(os.environ.get('CODEX_BLENDER_RENDER_TIMEOUT', '7200')))
                while renderer.poll() is None:
                    time.sleep(.2)
                    now = time.monotonic()
                    if not (path / ".paused").exists():
                        active_seconds += now - last
                    last = now
                    if active_seconds > timeout:
                        raise subprocess.TimeoutExpired(command, timeout)
                if renderer.returncode:
                    raise subprocess.CalledProcessError(renderer.returncode, command)
            except BaseException:
                renderer.kill()
                renderer.wait()
                raise
        checkpoint(path)
        if not complete_png(path / 'preview.png') or not complete_blend(path / 'scene.blend'):
            raise RuntimeError("Blender exited without writing the expected artifacts")
        try:
            with (path / 'render.log').open(encoding='utf-8', errors='replace') as log:
                warnings = [line.strip() for line in log if line.startswith(
                    ('WARNING: asset cache', 'WARNING: could not write asset cache'))]
            if warnings:
                update(warnings=list(dict.fromkeys(warnings))[-30:])
        except OSError:
            pass
        if data["mode"] == "video":
            missing = [frame for frame in range(1, data["frames_total"] + 1)
                       if not complete_png(path / 'frames' / f'frame_{frame:04d}.png')]
            if missing:
                raise RuntimeError(f"Blender did not render {len(missing)} required frames")
            update(state="encoding")
            spec = json.loads((path / "scene.json").read_text(encoding="utf-8"))
            encode_video(path, spec, root)
            if not (path / "video.mp4").is_file() or (path / "video.mp4").stat().st_size == 0:
                raise RuntimeError("Video encoding produced no output")
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-xerror',
                            '-i', str(path / 'video.mp4'), '-map', '0:v:0', '-frames:v', '1',
                            '-f', 'null', '-'], check=True, timeout=60)
        update(state="completed")
        print("Render completed successfully", flush=True)
    except Exception as exc:
        traceback.print_exc()
        update(state="failed", error=str(exc))
    finally:
        for name in (".pause-requested", ".paused"):
            (path / name).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
