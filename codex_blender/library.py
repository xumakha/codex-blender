"""Fixed-folder asset catalog shared by the web app, MCP and render workers."""
import json
from pathlib import Path
import re
import uuid

from .config import ASSETS, DATA, assets_dir, asset_path
from .jobs import write_json

KINDS = {".png": "image", ".jpg": "image", ".jpeg": "image", ".glb": "model",
         ".wav": "audio", ".mp3": "audio", ".m4a": "audio", ".ogg": "audio", ".ttf": "font", ".otf": "font"}


def settings():
    root = assets_dir()
    return {"assets_directory": str(root), "default_assets_directory": str(ASSETS)}


def set_directory(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.is_dir():
        raise ValueError("Chọn một thư mục có sẵn với đường dẫn tuyệt đối.")
    # Don't silently move or delete anything in the previous library.
    DATA.mkdir(parents=True, exist_ok=True)
    write_json(DATA / "settings.json", {"assets_directory": str(path.resolve())})
    return settings()


def catalog(root=None):
    root = root or assets_dir()
    root.mkdir(parents=True, exist_ok=True)
    result = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in KINDS or not p.resolve().is_relative_to(root.resolve()):
            continue
        if ".partial" in p.name:
            continue
        if p.suffix.lower() == ".png" and p.with_suffix(".glb").exists() and p.with_suffix(".asset.json").exists():
            continue  # The generated thumbnail belongs to its GLB, not a separate asset.
        meta = {}
        sidecar = p.with_suffix(".asset.json")
        if sidecar.exists():
            try:
                meta = json.loads(sidecar.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                pass
        result.append({"path": p.relative_to(root).as_posix(), "name": meta.get("name", p.stem),
                       "kind": KINDS[p.suffix.lower()], "bytes": p.stat().st_size,
                       "source": meta.get("source", "imported"), "description": meta.get("description", ""),
                       "tags": meta.get("tags", []), "preview": meta.get("preview"),
                       "component_of": meta.get("component_of"),
                       "modified": p.stat().st_mtime})
    # Components remain addressable by the renderer/planner, but belong to one
    # library card. Shared assembly previews are thumbnails, not uploaded images.
    paths={item['path'] for item in result}
    previews={item['preview'] for item in result if item.get('preview')}
    for item in result:
        item['internal']=bool(item.get('component_of') in paths or
                              (item['kind']=='image' and item['path'] in previews))
    return result


def upload_path(filename, category):
    if category not in {"references", "models", "voices", "music", "fonts", "images"}:
        raise ValueError("Loại tài nguyên không hợp lệ")
    suffix = Path(filename).suffix.lower()
    valid = {"references": {".png", ".jpg", ".jpeg"}, "models": {".glb"}, "voices": {".wav", ".mp3", ".m4a", ".ogg"},
             "music": {".wav", ".mp3", ".m4a", ".ogg"}, "fonts": {".ttf", ".otf"}, "images": {".png", ".jpg", ".jpeg"}}
    if suffix not in valid[category]:
        raise ValueError("Định dạng file không phù hợp với mục đã chọn")
    stem = re.sub(r"[^\w-]", "-", Path(filename).stem, flags=re.UNICODE)[:70].strip("-") or "asset"
    root = assets_dir()
    path = root / category / f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return root, path
