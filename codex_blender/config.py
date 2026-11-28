import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
OUTPUTS = ROOT / "outputs"
DATA = ROOT / "studio-data"


def elevenlabs_command() -> list[str]:
    explicit = os.environ.get('ELEVENLABS_CLI_PATH')
    if explicit:
        if not Path(explicit).is_file():
            raise ValueError('ELEVENLABS_CLI_PATH không trỏ tới file CLI hợp lệ.')
        return [explicit]
    local = DATA / 'tools/elevenlabs/node_modules/@elevenlabs'
    if os.name == 'nt':
        binary = local / 'cli-win32-x64/elevenlabs.exe'
        if binary.is_file():
            return [str(binary)]
    found = shutil.which('elevenlabs.exe' if os.name == 'nt' else 'elevenlabs')
    if found:
        return [found]
    launcher = local / 'cli/bin/cli.js'
    node = shutil.which('node')
    if launcher.is_file() and node:
        return [node, str(launcher)]
    raise RuntimeError('Chưa cài ElevenLabs CLI. Chạy npm install --prefix studio-data/tools/elevenlabs @elevenlabs/cli@1.14.2 trong thư mục dự án.')


def source_revision() -> str:
    """Fingerprint app code so the launcher can detect a stale in-memory server."""
    package = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(package.rglob('*')):
        if path.is_file() and path.suffix in {'.py','.js','.css','.html'}:
            digest.update(path.relative_to(package).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def codex_command() -> list[str]:
    explicit = os.environ.get("CODEX_PATH")
    executable = explicit or shutil.which("codex.exe" if os.name == "nt" else "codex") or shutil.which("codex.cmd")
    if not executable and os.name == "nt":
        candidates = sorted((Path.home() / ".vscode" / "extensions").glob(
            "openai.chatgpt-*/bin/windows-*/codex.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            executable = str(candidates[0])
    if not executable:
        raise RuntimeError("Codex CLI not found. Install Codex CLI or set CODEX_PATH.")
    if Path(executable).suffix.lower() == ".cmd":
        entry = Path(executable).parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        node = shutil.which("node")
        if not entry.is_file() or not node:
            raise RuntimeError("The npm Codex installation requires Node.js and codex.js.")
        return [node, str(entry)]
    return [str(executable)]


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


class ModelAssetError(ValueError):
    """A model or image used by the scene cannot be loaded."""


def validate_assets(spec, root: Path | None = None, *, geometry=True):
    extensions = {"model": {".glb", ".gltf", ".obj"}, "image": {".png", ".jpg", ".jpeg"}}
    objects = list(spec.objects) + [obj for shot in spec.shots for obj in shot.objects]
    inspected = set()
    for obj in objects if geometry else ():
        if obj.asset:
            try:
                path = asset_path(obj.asset, root)
                if obj.kind not in extensions or path.suffix.lower() not in extensions[obj.kind]:
                    raise ValueError("Unsupported asset type for object")
                if path.suffix.lower() in {".gltf", ".obj"}:
                    raise ValueError("Use self-contained .glb models (convert glTF/OBJ in Blender first)")
                if obj.kind == 'model' and path not in inspected:
                    validate_glb(path)
                    inspected.add(path)
            except (OSError, ValueError) as exc:
                raise ModelAssetError(f'{obj.name}: {exc}') from exc
    if spec.audio:
        if asset_path(spec.audio, root).suffix.lower() not in {".wav", ".mp3", ".ogg", ".m4a"}:
            raise ValueError("Audio must be wav, mp3, ogg or m4a")
    if spec.font and asset_path(spec.font, root).suffix.lower() not in {".ttf", ".otf"}:
        raise ValueError("Font must be ttf or otf")
    for name in (spec.voice_audio, spec.music):
        if name and asset_path(name, root).suffix.lower() not in {".wav", ".mp3", ".ogg", ".m4a"}:
            raise ValueError("Voice/music must be wav, mp3, ogg or m4a")
    for cue in spec.music_cues:
        if cue.audio and asset_path(cue.audio, root).suffix.lower() not in {'.wav','.mp3','.ogg','.m4a'}:
            raise ValueError('Music cues must reference supported audio files')
    for shot in spec.shots:
        for cue in shot.narration:
            if cue.audio and asset_path(cue.audio, root).suffix.lower() not in {".wav", ".mp3", ".ogg", ".m4a"}:
                raise ValueError("Narration must use an audio file")
    for effect in spec.effects:
        if effect.audio:
            asset_path(effect.audio, root)


def validate_glb(path):
    """Validate the container and allow only embedded resources."""
    try:
        with path.open('rb') as stream:
            magic, version, size, json_size, kind = struct.unpack('<4sIII4s', stream.read(20))
            if (magic, version, kind) != (b'glTF', 2, b'JSON') or size != path.stat().st_size:
                raise ValueError('Invalid GLB header')
            limit = int(os.environ.get('CODEX_BLENDER_GLB_JSON_BUDGET', '32000000'))
            if not 0 < json_size <= min(size - 20, limit):
                raise ValueError('Invalid GLB metadata size')
            document = json.loads(stream.read(json_size))
        if not isinstance(document, dict) or not document.get('meshes'):
            raise ValueError('GLB has no mesh')
        for item in document.get('buffers', []) + document.get('images', []):
            uri = item.get('uri')
            if uri is not None and (not isinstance(uri, str) or not uri.startswith('data:')):
                raise ValueError('GLB must embed all buffers and images')
    except (OSError, ValueError, struct.error, AttributeError, TypeError) as exc:
        raise ValueError(f'{path.name}: {exc}') from exc
