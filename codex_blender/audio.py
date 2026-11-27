"""FFmpeg audio mixing and optional online text-to-speech."""
import asyncio
import hashlib
import json
import os
import re
import ssl
from pathlib import Path
import subprocess
import urllib.error
import urllib.request
import uuid
import imageio_ffmpeg

from .config import asset_path

ELEVENLABS_VOICE_ID = "gb30mYs9RQJGV3jqCOM2"
ELEVENLABS_MODEL = "eleven_flash_v2_5"

VOICES = [
    {"id": "vi-VN-NamMinhNeural", "name": "Nam Minh", "language": "Tiếng Việt", "gender": "Nam"},
    {"id": "vi-VN-HoaiMyNeural", "name": "Hoài My", "language": "Tiếng Việt", "gender": "Nữ"},
    {"id": "en-US-GuyNeural", "name": "Guy", "language": "English", "gender": "Nam"},
    {"id": "en-US-JennyNeural", "name": "Jenny", "language": "English", "gender": "Nữ"},
    {"id": ELEVENLABS_VOICE_ID, "name": "ElevenLabs · gb30mYs9RQJGV3jqCOM2",
     "language": "Đa ngôn ngữ (có tiếng Việt)", "gender": "", "provider": "elevenlabs",
     "requires_api_key": True},
]


async def synthesize(text, voice, rate, destination):
    if voice not in {v["id"] for v in VOICES}:
        raise ValueError("Giọng đọc không hợp lệ")
    if not -50 <= rate <= 100 or not text.strip() or len(text) > 15000:
        raise ValueError("Kiểm tra lời đọc (tối đa 15000 ký tự) và tốc độ giọng đọc")
    if voice == ELEVENLABS_VOICE_ID:
        await asyncio.to_thread(synthesize_elevenlabs, text, voice, rate, Path(destination))
        return
    import edge_tts
    import importlib
    # Retain certificate verification while also trusting the operating system's
    # certificate store (needed for managed Windows network certificates).
    module = importlib.import_module("edge_tts.communicate")
    module._SSL_CTX.load_default_certs()
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


def synthesize_elevenlabs(text, voice, rate, destination):
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Chưa cấu hình ELEVENLABS_API_KEY. Hãy đặt biến môi trường rồi khởi động lại server Studio.")
    request = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
        data=json.dumps({"text": text, "model_id": ELEVENLABS_MODEL}).encode("utf-8"),
        headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        method="POST",
    )
    source = destination.with_name(f"{destination.stem}.{uuid.uuid4().hex}.partial.mp3")
    adjusted = source.with_name(source.stem + ".rate.mp3")
    try:
        # Use the system trust store; keep the key only in the HTTPS request header.
        with urllib.request.urlopen(request, timeout=120, context=ssl.create_default_context()) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"audio/mpeg", "audio/mp3", "application/octet-stream"}:
                raise RuntimeError("ElevenLabs không trả về file âm thanh hợp lệ")
            with source.open("wb") as output:
                while chunk := response.read(64 * 1024):
                    output.write(chunk)
        if not source.stat().st_size:
            raise RuntimeError("ElevenLabs trả về file âm thanh rỗng")
        if rate:
            # Preserve the full Studio speed range without clamping provider settings.
            result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-y',
                '-i', str(source), '-af', f'atempo={1 + rate / 100:.4f}', str(adjusted)],
                capture_output=True, timeout=120)
            if result.returncode or not adjusted.exists() or not adjusted.stat().st_size:
                raise RuntimeError("Không điều chỉnh được tốc độ giọng ElevenLabs")
            adjusted.replace(destination)
        else:
            source.replace(destination)
    except urllib.error.HTTPError as exc:
        messages = {
            401: "API key ElevenLabs không hợp lệ hoặc đã hết hạn",
            403: "API key ElevenLabs không có quyền dùng giọng này hoặc đã hết hạn mức",
            404: "Không tìm thấy giọng ElevenLabs; kiểm tra quyền truy cập voice ID trong tài khoản",
            429: "ElevenLabs đang giới hạn yêu cầu hoặc tài khoản đã hết hạn mức",
        }
        raise RuntimeError(messages.get(exc.code, f"ElevenLabs trả về lỗi HTTP {exc.code}")) from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("Không kết nối được ElevenLabs. Kiểm tra Internet và thử lại.") from None
    finally:
        source.unlink(missing_ok=True)
        adjusted.unlink(missing_ok=True)


def audio_duration(path):
    result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-i', str(path), '-f', 'null', '-'],
                            capture_output=True, text=True, timeout=120)
    match = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', result.stderr)
    if result.returncode or not match:
        raise RuntimeError("Không đọc được thời lượng file giọng nói")
    return int(match[1])*3600+int(match[2])*60+float(match[3])


def fit_speech(source, destination, seconds):
    duration = audio_duration(source)
    speed = max(1, duration / seconds)
    if speed > 1.35:
        raise ValueError(f"Lời đọc dài {duration:.1f}s nhưng chỉ có {seconds:.1f}s trong cảnh; cần sửa mốc hoặc rút lời đọc, không tự cắt mất nội dung")
    # Pad shorter speech with silence; modest speedup fits exact slots without truncating words.
    filters = f"atempo={speed:.8f},apad,atrim=duration={seconds},aresample=48000"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-y', '-i', str(source),
                    '-af', filters, '-c:a', 'pcm_s16le', str(destination)], check=True, timeout=120)


async def synthesize_cues(scene, root):
    folder = root / 'voices'
    folder.mkdir(exist_ok=True)
    for shot in scene.shots:
        for cue in shot.narration:
            if cue.audio:
                continue
            digest = hashlib.sha256(f'{cue.voice_id}|{cue.rate}|{cue.text}'.encode()).hexdigest()[:24]
            source = folder / f'cue-{digest}.mp3'
            if not source.exists() or not source.stat().st_size:
                await synthesize(cue.text, cue.voice_id, cue.rate, source)
            destination = folder / f'cue-{digest}-{round((cue.end-cue.start)*1000)}.wav'
            if not destination.exists() or not destination.stat().st_size:
                await asyncio.to_thread(fit_speech, source, destination, cue.end-cue.start)
            cue.audio = destination.relative_to(root).as_posix()


def encode_video(path, spec, root):
    duration = max(1, round(spec["duration"] * spec["fps"])) / spec["fps"]
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-framerate", str(spec["fps"]), "-start_number", "1", "-i", str(path / "frames" / "frame_%04d.png")]
    cues = [cue for shot in spec.get('shots', []) for cue in shot.get('narration', [])]
    if any(not cue.get('audio') for cue in cues):
        raise ValueError("Lời thoại trong timeline chưa được tạo thành âm thanh")
    voice = bool(spec.get("voice_audio") or cues)
    music = spec.get("music") or spec.get("audio")
    voices = []
    if spec.get('voice_audio'):
        voices.append((spec['voice_audio'], 0, duration))
    voices += [(cue['audio'], cue['start'], cue['end']-cue['start']) for cue in cues]
    for path_name, _, _ in voices:
        cmd += ['-i', str(asset_path(path_name, root))]
    effects = spec.get('effects', [])
    if any(not effect.get('audio') for effect in effects):
        raise ValueError("Hiệu ứng âm thanh chưa được tạo theo timeline")
    for effect in effects:
        cmd += ['-i',str(asset_path(effect['audio'],root))]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(asset_path(music, root))]
    graph = []
    voice_gain = spec.get("voice_volume", 1)
    music_gain = spec.get("music_volume", .2) if spec.get("music") else (spec.get("music_volume", .2) if voice else 1)
    if voice:
        for index, (_, start, window) in enumerate(voices, 1):
            graph += [f"[{index}:a]aresample=48000,apad,atrim=duration={window},asetpts=PTS-STARTPTS,volume={voice_gain},adelay={round(start*1000)}:all=1[v{index}]"]
        if len(voices) == 1:
            graph += ['[v1]anull[v]']
        else:
            graph += [''.join(f'[v{i}]' for i in range(1,len(voices)+1))+f'amix=inputs={len(voices)}:duration=longest:normalize=0[v]']
    if music:
        index = len(voices)+len(effects)+1
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
    if effects:
        has_mix = bool(voice or music)
        if has_mix:
            graph[-1] = graph[-1].replace('[a]', '[base]')
        for index, effect in enumerate(effects):
            graph += [f"[{len(voices)+index+1}:a]aresample=48000,atrim=duration={effect['end']-effect['start']},asetpts=PTS-STARTPTS,volume={effect['volume']},adelay={round(effect['start']*1000)}:all=1[e{index}]"]
        inputs = ('[base]' if has_mix else '')+''.join(f'[e{i}]' for i in range(len(effects)))
        graph += [inputs+f'amix=inputs={len(effects)+int(has_mix)}:duration=longest:normalize=0,alimiter=limit=0.95[a]']
    if graph:
        cmd += ["-filter_complex", ";".join(graph), "-map", "0:v:0", "-map", "[a]", "-c:a", "aac"]
    if spec.get("subtitles") or (spec.get('captions') and cues):
        if not spec.get("font"):
            raise ValueError("Chọn font TTF/OTF để xuất phụ đề tiếng Việt")
        import shutil
        shutil.copyfile(asset_path(spec["font"], root), path / "subtitle-font.ttf")
        size = max(16, round(spec["width"] / 25))
        captions = [(spec['subtitles'], None, None)] if spec.get('subtitles') else [(cue['text'], cue['start'], cue['end']) for cue in cues]
        filters = []
        import textwrap
        for index, (text, start, end) in enumerate(captions):
            name = f'caption-{index:03d}.txt'
            (path/name).write_text('\n'.join(textwrap.wrap(text, width=max(12, round(spec['width']/(size*.55))))), encoding='utf-8')
            enable = f":enable='gte(t,{start})*lt(t,{end})'" if start is not None else ''
            filters.append(f"drawtext=fontfile=subtitle-font.ttf:textfile={name}:expansion=none:fontsize={size}:fontcolor=white:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h*0.82"+enable)
        cmd += ['-vf', ','.join(filters)]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-t", str(duration), str(path / "video.mp4")]
    subprocess.run(cmd, cwd=path, check=True, timeout=1800)
