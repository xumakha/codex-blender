import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone

from .config import ROOT, ASSETS, OUTPUTS, blender_command, validate_assets, assets_dir
from .models import SceneSpec


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
    data["artifacts"] = {name: str(path / name) for name in ("scene.json", "scene.blend", "preview.png", "video.mp4", "render.log") if (path / name).exists()}
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
            data["error"] = "Render worker was interrupted; see render.log and submit a new job."
    return data


def submit(spec: SceneSpec, mode="preview", asset_root=None):
    if mode not in {"preview", "video"}:
        raise ValueError("Mode must be preview or video")
    asset_root = asset_root or assets_dir()
    validate_assets(spec, asset_root)
    blender_command()  # Fail before allocating a job if Blender is missing.
    job_id = uuid.uuid4().hex
    path = OUTPUTS / job_id
    path.mkdir(parents=True)
    write_json(path / "scene.json", spec.model_dump(mode="json"))
    data = {"id": job_id, "state": "queued", "mode": mode, "title": spec.title, "assets_directory": str(asset_root),
            "created": datetime.now(timezone.utc).isoformat(), "frames_total": max(1, round(spec.duration * spec.fps)) if mode == "video" else 1}
    write_json(path / "status.json", data)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        with (path / "render.log").open("w", encoding="utf-8") as log:
            subprocess.Popen([sys.executable, "-m", "codex_blender.worker", job_id], cwd=ROOT,
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                             creationflags=flags, start_new_session=os.name != "nt")
    except Exception as exc:
        data.update(state="failed", error=str(exc))
        write_json(path / "status.json", data)
        raise
    return {**data, "output_directory": str(path), "next": "Poll video_job_status with this id"}
