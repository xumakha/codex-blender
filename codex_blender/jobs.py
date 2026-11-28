import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone

from .config import ROOT, ASSETS, OUTPUTS, blender_command, validate_assets, assets_dir
from .models import SceneSpec
from .render_timing import remaining_seconds
from .render_artifacts import complete_blend, complete_png

LOCK = threading.RLock()


def write_json(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def job_path(job_id):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise ValueError("Invalid job ID")
    path = OUTPUTS / job_id
    if not (path / "status.json").exists():
        raise ValueError("Job not found")
    return path


def status(job_id):
    path = job_path(job_id)
    data = json.loads((path / "status.json").read_text(encoding="utf-8"))
    data["frames_rendered"] = len(list((path / "frames").glob("frame_*.png")))
    data["artifacts"] = {name: str(path / name) for name in ("scene.json", "scene.blend", "preview.png", "video.mp4", "render.log", "exported-assets.json") if (path / name).exists()}
    if data['state'] == 'completed':
        video = path / 'video.mp4'
        try:
            valid_video = data.get('mode') != 'video' or video.stat().st_size > 0
        except OSError:
            valid_video = False
        if not (valid_video and complete_png(path / 'preview.png') and complete_blend(path / 'scene.blend')):
            data.update(state='failed', error='Kết quả render thiếu hoặc hỏng. Có thể tiếp tục từ các khung hình đã lưu.')
    # Detect interrupted worker rather than presenting a stale running status forever.
    if data["state"] in {"queued", "rendering", "encoding"} and data.get("pid"):
        import psutil
        try:
            process = psutil.Process(data["pid"])
            alive = abs(process.create_time() - data["process_created"]) < 1 and process.is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            alive = False
        if not alive:
            data["state"] = "failed"
            data["error"] = f"Render đã bị ngắt ở {data['frames_rendered']}/{data['frames_total']} khung hình. Bấm Tiếp tục render để dựng các khung còn thiếu; xem render.log để kiểm tra chi tiết."
    if data["state"] in {"queued", "rendering"} and (path / ".pause-requested").exists():
        data["state"] = "paused" if (path / ".paused").exists() else "pausing"
    data['eta_seconds'] = None
    if data.get('mode') == 'video':
        if data['state'] == 'completed':
            data['eta_seconds'] = 0
        elif data['state'] == 'rendering':
            data['eta_seconds'] = remaining_seconds(path, max(0, data['frames_total'] - data['frames_rendered']))
    return data


def control(job_id, action):
    with LOCK:
        current = status(job_id)
        path = job_path(job_id)
        if action == "pause":
            if current["state"] not in {"queued", "rendering", "pausing", "paused"}:
                raise ValueError("Chỉ tạm dừng khi đang chờ hoặc đang render")
            (path / ".pause-requested").touch()
        elif action == "resume":
            if current["state"] not in {"pausing", "paused"}:
                raise ValueError("Tác vụ chưa được tạm dừng")
            (path / ".pause-requested").unlink(missing_ok=True)
        else:
            raise ValueError("Thao tác render không hợp lệ")
        return status(job_id)


def submit(spec: SceneSpec, mode="preview", asset_root=None):
    if mode not in {"preview", "video"}:
        raise ValueError("Mode must be preview or video")
    asset_root = asset_root or assets_dir()
    if not spec.font and (spec.captions or spec.subtitles or any(
        obj.kind == 'text' for obj in list(spec.objects)+[obj for shot in spec.shots for obj in shot.objects]
    )):
        from .fonts import ensure_font
        spec.font = ensure_font(asset_root)
    validate_assets(spec, asset_root)
    blender_command()  # Fail before allocating a job if Blender is missing.
    job_id = uuid.uuid4().hex
    path = OUTPUTS / job_id
    path.mkdir(parents=True)
    write_json(path / "scene.json", spec.model_dump(mode="json"))
    data = {"id": job_id, "state": "queued", "mode": mode, "title": spec.title, "assets_directory": str(asset_root),
            "created": datetime.now(timezone.utc).isoformat(), "frames_total": max(1, round(spec.duration * spec.fps)) if mode == "video" else 1}
    write_json(path / "status.json", data)
    launch_worker(path, data)
    return {**data, "output_directory": str(path), "next": "Poll video_job_status with this id"}


def launch_worker(path, data, resume=False):
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
    try:
        with (path / "render.log").open("a" if resume else "w", encoding="utf-8") as log:
            if resume:
                log.write("\n--- Resuming interrupted render; keeping completed frames ---\n")
                log.flush()
            subprocess.Popen([sys.executable, "-u", "-m", "codex_blender.worker", data["id"]], cwd=ROOT,
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                             creationflags=flags, start_new_session=os.name != "nt")
    except Exception as exc:
        data.update(state="failed", error=str(exc))
        write_json(path / "status.json", data)
        raise


def retry(job_id):
    with LOCK:
        current = status(job_id)
        if current["state"] != "failed":
            raise ValueError("Chỉ tiếp tục job render đã thất bại hoặc bị ngắt")
        path = job_path(job_id)
        data = json.loads((path / "status.json").read_text(encoding="utf-8"))
        spec = SceneSpec.model_validate_json((path / "scene.json").read_text(encoding="utf-8"))
        validate_assets(spec, Path(data.get("assets_directory", str(ASSETS))),
                        geometry=not complete_blend(path / 'scene.blend'))
        blender_command()
        for key in ("pid", "process_created", "error"):
            data.pop(key, None)
        for name in (".pause-requested", ".paused"):
            (path / name).unlink(missing_ok=True)
        (path / 'render-timing.json').unlink(missing_ok=True)
        data.update(state="queued", resumed=datetime.now(timezone.utc).isoformat())
        write_json(path / "status.json", data)
        launch_worker(path, data, resume=True)
        return status(job_id)
