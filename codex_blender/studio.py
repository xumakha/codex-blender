"""Persistent projects and Codex-assisted scene planning for the local Studio."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import uuid

from pydantic import Field, model_validator
from .models import Model, SceneSpec, MAX_DURATION
from .planning import signature, object_names, prompt_contract
from .config import ROOT, DATA, OUTPUTS, assets_dir, asset_path, validate_assets, blender_command
from .jobs import write_json, submit, status, job_path, retry, control
from .library import catalog

POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="studio")
LOCK = threading.RLock()


class Draft(Model):
    title: str = Field(default="Video mới", max_length=200)
    prompt: str = Field(default="", max_length=70002)
    script: str = Field(default="", max_length=50000)
    style: str = Field(default="Hoạt hình 3D studio, hình khối rõ ràng, ánh sáng mềm", max_length=3000)
    references: list[str] = Field(default_factory=list, max_length=4)
    selected_assets: list[str] = Field(default_factory=list, max_length=40)
    duration: float = Field(default=5, ge=.1, le=MAX_DURATION)
    fps: int = Field(default=24, ge=1, le=60)
    width: int = Field(default=540, ge=64, le=3840, multiple_of=2)
    height: int = Field(default=960, ge=64, le=3840, multiple_of=2)
    samples: int = Field(default=16, ge=1, le=256)
    voice_mode: str = Field(default="auto", pattern="^(auto|none|upload|tts)$")
    voice_id: str = "vi-VN-NamMinhNeural"
    voice_file: str | None = None
    narration: str = Field(default="", max_length=100000)
    rate: int = Field(default=0, ge=-50, le=100)
    voice_volume: float = Field(default=1, ge=0, le=2)
    music: str | None = None
    music_volume: float = Field(default=.2, ge=0, le=1)
    duck_music: bool = True
    subtitles: str = Field(default="", max_length=10000)
    font: str | None = None
    scene: SceneSpec | None = None
    source_signature: str | None = None

    @model_validator(mode="before")
    @classmethod
    def merge_legacy_script(cls, value):
        if isinstance(value, dict) and value.get("script"):
            value = dict(value)
            value["prompt"] = "\n\n".join(part for part in (value.get("prompt", ""), value["script"]) if part.strip())
            value["script"] = ""
        return value


def project_path(pid):
    if not re.fullmatch(r"[0-9a-f]{32}", pid):
        raise ValueError("Mã dự án không hợp lệ")
    path = DATA / "projects" / pid
    if not (path / "project.json").exists():
        raise ValueError("Không tìm thấy dự án")
    return path


def read_project(pid):
    with LOCK:
        data = json.loads((project_path(pid) / "project.json").read_text(encoding="utf-8"))
    draft = Draft.model_validate(data['draft'])
    data['scene_current'] = not draft.prompt.strip() or draft.source_signature == signature(draft)
    contract = prompt_contract(draft.prompt)
    data['prompt_timing'] = {key: contract[key] for key in ('duration', 'duration_range', 'intervals')}
    if data.get('screenplay_signature') != signature(draft):
        data['screenplay'] = None
    current = data.get("current_job")
    if current:
        data["job"] = status(current)
        if data["job"]["state"] == "failed":
            data["error"] = data["job"].get("error", "Render thất bại")
    return data


def save_project(pid, **values):
    with LOCK:
        path = project_path(pid) / "project.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(values)
        data["updated"] = datetime.now(timezone.utc).isoformat()
        write_json(path, data)
    return data


def create_project(draft=None):
    draft = draft or Draft()
    if draft.scene and draft.scene.prompt == draft.prompt:
        draft.source_signature = signature(draft)
    pid = uuid.uuid4().hex
    path = DATA / "projects" / pid
    path.mkdir(parents=True)
    now = datetime.now(timezone.utc).isoformat()
    data = {"id": pid, "created": now, "updated": now, "draft": draft.model_dump(mode="json"),
            "state": "idle", "error": None, "jobs": [], "current_job": None}
    write_json(path / "project.json", data)
    return data


def projects():
    result = []
    for p in (DATA / "projects").glob("*/project.json"):
        try:
            if json.loads(p.read_text(encoding="utf-8")).get('kind') == 'asset-generation':
                continue
            value = read_project(p.parent.name)
            result.append({"id": value["id"], "title": value["draft"]["title"], "updated": value["updated"],
                           "state": value.get("job", {}).get("state", value["state"]),
                           "current_job": value.get("current_job"), "has_scene": bool(value["draft"]["scene"])})
        except (ValueError, OSError):
            continue
    return sorted(result, key=lambda v: v["updated"], reverse=True)


def ensure_idle(project):
    if project["state"] in {"planning", "preparing_audio", "exporting"} or project.get("job", {}).get("state") in {"queued", "rendering", "encoding", "pausing", "paused"}:
        raise ValueError("Dự án đang xử lý. Hãy chờ tác vụ hiện tại hoàn tất.")


def strict_schema(schema):
    """Codex structured output requires all object fields, nullable for optional values."""
    if isinstance(schema, dict):
        result = {}
        for k, v in schema.items():
            if k in {"default", "title"}:
                continue
            if k in {"properties", "$defs"}:
                result[k] = {name: strict_schema(child) for name, child in v.items()}
            else:
                result[k] = strict_schema(v)
        if "prefixItems" in result:
            items = result.pop("prefixItems")
            result["items"] = items[0]
        if result.get("type") == "object":
            result["required"] = list(result.get("properties", {}))
            result["additionalProperties"] = False
        return result
    if isinstance(schema, list):
        return [strict_schema(v) for v in schema]
    return schema


def planner_mcp_overrides():
    """Keep planning independent from global MCP/plugin configuration; retain the chosen model."""
    import tomllib
    home = Path(os.environ.get("CODEX_HOME", str(Path.home()/".codex")))
    config = home / "config.toml"
    values = tomllib.loads(config.read_text(encoding="utf-8")) if config.is_file() else {}
    args = ["--ignore-user-config"]
    for key in ("model", "model_reasoning_effort"):
        if key in values:
            args += ["-c", key+"="+json.dumps(values[key])]
    return args


def plan_scene(pid, draft, root, auto_render=False, render_mode="video"):
    from .director import plan_project
    try:
        plan_project(pid, draft, root, auto_render, render_mode)
    except Exception as exc:
        save_project(pid, state="error", error=str(exc), planning_detail=None)


def start_plan(pid, auto_render=False, render_mode="video"):
    with LOCK:
        project = read_project(pid)
        ensure_idle(project)
        draft = Draft.model_validate(project["draft"])
        if not (draft.prompt.strip() or draft.script.strip()):
            raise ValueError("Nhập prompt mô tả video trước khi tạo")
        save_project(pid, state="planning", error=None)
        POOL.submit(plan_scene, pid, draft, assets_dir(), auto_render, render_mode)
    return read_project(pid)


def scene_for_render(draft):
    if not draft.scene:
        raise ValueError("Hãy tạo cảnh bằng AI hoặc nạp cảnh mẫu trước")
    scene = draft.scene.model_copy(deep=True)
    if scene.shots:
        # The compiled screenplay owns its timing, composition and audio.
        scene.samples = draft.samples
        return scene
    factor = draft.duration / scene.duration
    for obj in scene.objects:
        for key in obj.keyframes:
            key.time = min(draft.duration, round(key.time * factor, 5))
    scene.title, scene.duration, scene.fps = draft.title, draft.duration, draft.fps
    scene.width, scene.height, scene.samples = draft.width, draft.height, draft.samples
    scene.voice_audio = draft.voice_file if draft.voice_mode == "upload" else None
    if draft.voice_mode == "upload" and not draft.voice_file:
        raise ValueError("Chọn file voice đã tải lên")
    scene.audio, scene.music, scene.music_volume = None, draft.music, draft.music_volume
    scene.voice_volume, scene.duck_music = draft.voice_volume, draft.duck_music
    scene.subtitles, scene.font = draft.subtitles, draft.font or scene.font
    return SceneSpec.model_validate(scene.model_dump())


def render_project(pid, mode):
    with LOCK:
        project = read_project(pid)
        ensure_idle(project)
        draft = Draft.model_validate(project["draft"])
        if draft.prompt.strip() and draft.source_signature != signature(draft):
            return start_plan(pid, auto_render=True, render_mode=mode)
        scene = scene_for_render(draft)
        root = assets_dir()
        timed_voice = any(shot.narration for shot in scene.shots)
        sound_design = scene.effects or scene.music_style != 'none'
        if mode == "video" and (timed_voice or sound_design or draft.voice_mode == "tts"):
            if not timed_voice and not sound_design and not draft.narration.strip():
                raise ValueError("Nhập lời thuyết minh để tạo voice AI")
            save_project(pid, state="preparing_audio", error=None)
            POOL.submit(prepare_and_render, pid, draft, scene, root, mode)
        else:
            job = submit(scene, mode, root)
            save_project(pid, current_job=job["id"], jobs=project["jobs"]+[job["id"]], state="ready", error=None)
    return read_project(pid)


def prepare_and_render(pid, draft, scene, root, mode):
    import asyncio
    from .audio import synthesize, synthesize_cues
    try:
        from .sounddesign import prepare_sound
        prepare_sound(scene, root)
        if scene.shots:
            asyncio.run(synthesize_cues(scene, root))
        else:
            folder = root / "voices"
            folder.mkdir(exist_ok=True)
            path = folder / f"tts-{uuid.uuid4().hex}.mp3"
            asyncio.run(synthesize(draft.narration, draft.voice_id, draft.rate, path, word_timing=bool(scene.subtitles)))
            scene.voice_audio = path.relative_to(root).as_posix()
        job = submit(scene, mode, root)
        latest = read_project(pid)
        save_project(pid, current_job=job["id"], jobs=latest["jobs"]+[job["id"]], state="ready", error=None)
    except Exception as exc:
        save_project(pid, state="error", error="Chưa tạo được âm thanh đúng timeline: "+str(exc))


def control_render(pid, action):
    with LOCK:
        project = read_project(pid)
        if project["state"] in {"planning", "preparing_audio", "exporting"} or not project.get("current_job"):
            raise ValueError("Dự án chưa có tác vụ render có thể điều khiển")
        control(project["current_job"], action)
        return read_project(pid)


def retry_render(pid):
    with LOCK:
        project = read_project(pid)
        ensure_idle(project)
        if not project.get("current_job"):
            raise ValueError("Dự án chưa có job render để tiếp tục")
        retry(project["current_job"])
        save_project(pid, state="ready", error=None)
    return read_project(pid)


def export_asset(pid, job_id, name, names, description, tags):
    project = read_project(pid)
    ensure_idle(project)
    if job_id not in project["jobs"]:
        raise ValueError("Chỉ lưu asset từ bản render thuộc dự án này")
    info = status(job_id)
    if info["state"] != "completed":
        raise ValueError("Chờ bản render hoàn tất trước khi lưu asset")
    allowed = {name for name, _ in object_names(json.loads((job_path(job_id)/"scene.json").read_text(encoding="utf-8")))}
    if not names or not set(names).issubset(allowed):
        raise ValueError("Chọn ít nhất một đối tượng hợp lệ")
    if not name.strip() or len(name) > 100:
        raise ValueError("Tên asset phải dài từ 1 đến 100 ký tự")
    root = assets_dir()
    path = root / "generated" / (uuid.uuid4().hex+".glb")
    path.parent.mkdir(parents=True, exist_ok=True)
    options = project_path(pid) / f"export-{uuid.uuid4().hex}.json"
    write_json(options, {"blend": info["artifacts"]["scene.blend"], "output": str(path), "names": names})
    save_project(pid, state="exporting", error=None)
    POOL.submit(run_export, pid, options, path, name, description, tags)
    return {"state": "exporting"}


def run_export(pid, options, path, name, description, tags):
    try:
        env = os.environ.copy()
        runtime = project_path(pid) / "blender-user"
        runtime.mkdir(exist_ok=True)
        env["BLENDER_USER_RESOURCES"] = str(runtime)
        with (project_path(pid)/"export.log").open("w",encoding="utf-8") as log:
            subprocess.run(blender_command()+[str(ROOT/"codex_blender"/"export_asset.py"),"--",str(options)],
                           cwd=ROOT, env=env, stdout=log, stderr=log, timeout=300, check=True)
        if not path.is_file():
            raise RuntimeError("Blender không tạo được GLB")
        write_json(path.with_suffix(".asset.json"), {"name": name, "description": description, "tags": tags,
                   "source": "blender", "preview": path.with_suffix(".png").relative_to(path.parent.parent).as_posix()})
        save_project(pid, state="ready", error=None, last_saved_asset=str(path))
    except Exception as exc:
        save_project(pid, state="error", error="Không lưu được asset: "+str(exc))
