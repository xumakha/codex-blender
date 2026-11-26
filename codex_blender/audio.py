"""FFmpeg audio mixing and optional online text-to-speech."""
import asyncio
from pathlib import Path
import subprocess
import imageio_ffmpeg

from .config import asset_path

VOICES = [
    {"id": "vi-VN-NamMinhNeural", "name": "Nam Minh", "language": "Tiếng Việt", "gender": "Nam"},
    {"id": "vi-VN-HoaiMyNeural", "name": "Hoài My", "language": "Tiếng Việt", "gender": "Nữ"},
    {"id": "en-US-GuyNeural", "name": "Guy", "language": "English", "gender": "Nam"},
    {"id": "en-US-JennyNeural", "name": "Jenny", "language": "English", "gender": "Nữ"},
]


async def synthesize(text, voice, rate, destination):
    import edge_tts
    import importlib
    # Retain certificate verification while also trusting the operating system's
    # certificate store (needed for managed Windows network certificates).
    module = importlib.import_module("edge_tts.communicate")
    module._SSL_CTX.load_default_certs()
    if voice not in {v["id"] for v in VOICES}:
        raise ValueError("Giọng đọc không hợp lệ")
    if not -50 <= rate <= 100 or not text.strip() or len(text) > 15000:
        raise ValueError("Kiểm tra lời đọc (tối đa 15000 ký tự) và tốc độ giọng đọc")
    destination = Path(destination)
    partial = destination.with_name(destination.stem+".partial.mp3")
    try:
        await asyncio.wait_for(edge_tts.Communicate(text, voice, rate=f"{rate:+d}%").save(str(partial)), timeout=120)
        if not partial.exists() or not partial.stat().st_size:
            raise RuntimeError("Dịch vụ không trả về âm thanh. Hãy thử lại hoặc dùng file voice có sẵn.")
        partial.replace(destination)
    except edge_tts.exceptions.NoAudioReceived as exc:
        raise RuntimeError("Dịch vụ chưa trả về âm thanh trên kết nối này. Hãy thử lại hoặc dùng file voice có sẵn.") from exc
    finally:
        partial.unlink(missing_ok=True)


def encode_video(path, spec, root):
    duration = max(1, round(spec["duration"] * spec["fps"])) / spec["fps"]
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-framerate", str(spec["fps"]), "-start_number", "1", "-i", str(path / "frames" / "frame_%04d.png")]
    voice = spec.get("voice_audio")
    music = spec.get("music") or spec.get("audio")
    if voice:
        cmd += ["-i", str(asset_path(voice, root))]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(asset_path(music, root))]
    graph = []
    voice_gain = spec.get("voice_volume", 1)
    music_gain = spec.get("music_volume", .2) if spec.get("music") else (spec.get("music_volume", .2) if voice else 1)
    if voice:
        graph += [f"[1:a]aresample=48000,apad,atrim=duration={duration},asetpts=PTS-STARTPTS,volume={voice_gain}[v]"]
    if music:
        index = 2 if voice else 1
        graph += [f"[{index}:a]aresample=48000,atrim=duration={duration},asetpts=PTS-STARTPTS,volume={music_gain},afade=t=out:st={max(0,duration-.5)}:d=0.5[m]"]
    if voice and music:
        if spec.get("duck_music", True):
            graph += ["[v]asplit=2[vout][side]", "[m][side]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=300[ducked]", "[vout][ducked]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[a]"]
        else:
            graph += ["[v][m]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]"]
    elif voice:
        graph += ["[v]alimiter=limit=0.95[a]"]
    elif music:
        graph += ["[m]alimiter=limit=0.95[a]"]
    if graph:
        cmd += ["-filter_complex", ";".join(graph), "-map", "0:v:0", "-map", "[a]", "-c:a", "aac"]
    if spec.get("subtitles"):
        if not spec.get("font"):
            raise ValueError("Chọn font TTF/OTF để xuất phụ đề tiếng Việt")
        import shutil
        (path / "subtitles.txt").write_text(spec["subtitles"], encoding="utf-8")
        shutil.copyfile(asset_path(spec["font"], root), path / "subtitle-font.ttf")
        size = max(16, round(spec["width"] / 25))
        cmd += ["-vf", f"drawtext=fontfile=subtitle-font.ttf:textfile=subtitles.txt:expansion=none:fontsize={size}:fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h*0.82"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-t", str(duration), str(path / "video.mp4")]
    subprocess.run(cmd, cwd=path, check=True, timeout=1800)
