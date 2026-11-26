import importlib.util
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
OUTPUTS = ROOT / "outputs"
DATA = ROOT / "studio-data"


def assets_dir() -> Path:
    import json
    settings = DATA / "settings.json"
    if settings.exists():
        return Path(json.loads(settings.read_text(encoding="utf-8"))["assets_directory"]).resolve()
    return ASSETS


def asset_path(value: str, root: Path | None = None) -> Path:
    root = (root or assets_dir()).resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Assets must be inside the configured assets directory")
    if not path.is_file():
        raise ValueError(f"Asset does not exist: {value}")
    return path


def blender_command() -> list[str]:
    explicit = os.environ.get("BLENDER_PATH")
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise ValueError("BLENDER_PATH must point to the Blender executable")
        return [str(path), "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1", "--python"]
    found = shutil.which("blender")
    candidates = sorted(Path("C:/Program Files/Blender Foundation").glob("Blender */blender.exe"), reverse=True)
    if found or candidates:
        return [found or str(candidates[0]), "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1", "--python"]
    # Optional headless Blender Python wheel, useful on machines without the GUI app.
    if importlib.util.find_spec("bpy"):
        import sys
        return [sys.executable]
    raise RuntimeError("Blender not found. Install Blender and set BLENDER_PATH, or install bpy in .venv.")


def validate_assets(spec, root: Path | None = None):
    extensions = {"model": {".glb", ".gltf", ".obj"}, "image": {".png", ".jpg", ".jpeg"}}
    for obj in spec.objects:
        if obj.asset:
            path = asset_path(obj.asset, root)
            if obj.kind not in extensions or path.suffix.lower() not in extensions[obj.kind]:
                raise ValueError("Unsupported asset type for object")
            # GLB is self-contained; glTF/OBJ may reference sibling resources.
            if path.suffix.lower() in {".gltf", ".obj"}:
                raise ValueError("Use self-contained .glb models (convert glTF/OBJ in Blender first)")
    if spec.audio:
        if asset_path(spec.audio, root).suffix.lower() not in {".wav", ".mp3", ".ogg", ".m4a"}:
            raise ValueError("Audio must be wav, mp3, ogg or m4a")
    if spec.font and asset_path(spec.font, root).suffix.lower() not in {".ttf", ".otf"}:
        raise ValueError("Font must be ttf or otf")
    for name in (spec.voice_audio, spec.music):
        if name and asset_path(name, root).suffix.lower() not in {".wav", ".mp3", ".ogg", ".m4a"}:
            raise ValueError("Voice/music must be wav, mp3, ogg or m4a")
