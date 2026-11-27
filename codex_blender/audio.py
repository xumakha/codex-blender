"""FFmpeg audio mixing and optional online text-to-speech."""
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import urllib.error
import uuid
import imageio_ffmpeg

from .config import asset_path, elevenlabs_command, ROOT

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


def voice_options():
    from .voice_clones import options
    return VOICES + options()


async def synthesize(text, voice, rate, destination, word_timing=False):
    selected=next((item for item in voice_options() if item['id']==voice),None)
    if selected is None:
        raise ValueError("Giọng đọc không hợp lệ")
    if selected.get('disabled'):
        raise ValueError(selected.get('status_message') or 'Giọng clone chưa sẵn sàng sử dụng.')
    if not -50 <= rate <= 100 or not text.strip() or len(text) > 15000:
        raise ValueError("Kiểm tra lời đọc (tối đa 15000 ký tự) và tốc độ giọng đọc")
    if selected.get('provider') == 'elevenlabs':
        await asyncio.to_thread(synthesize_elevenlabs, text, voice, rate, Path(destination), word_timing)
        return
    if selected.get('provider') == 'voicestudio':
        from .local_voice import synthesize as synthesize_local
        await asyncio.to_thread(synthesize_local, text, voice, rate, Path(destination))
        return
    import edge_tts
    import aiohttp
    import importlib
    # Retain certificate verification while also trusting the operating system's
    # certificate store (needed for managed Windows network certificates).
    module = importlib.import_module("edge_tts.communicate")
    module._SSL_CTX.load_default_certs()
    destination = Path(destination)
    partial = destination.with_name(destination.stem+'.'+uuid.uuid4().hex+".partial.mp3")
    metadata = partial.with_suffix('.metadata.jsonl')
    async def connect():
        for attempt in range(5):
            partial.unlink(missing_ok=True)
            metadata.unlink(missing_ok=True)
            try:
                # Each retry needs a new Communicate instance: its stream can
                # only be consumed once. Keep the selected voice and full text.
                await asyncio.wait_for(edge_tts.Communicate(text, voice, rate=f"{rate:+d}%",
                    boundary='WordBoundary' if word_timing else 'SentenceBoundary').save(
                    str(partial),str(metadata) if word_timing else None),timeout=40)
                if not partial.is_file() or not partial.stat().st_size:
                    raise edge_tts.exceptions.NoAudioReceived('Empty audio')
                return
            except (edge_tts.exceptions.NoAudioReceived,edge_tts.exceptions.WebSocketError,
                    aiohttp.ClientError,TimeoutError) as exc:
                if isinstance(exc,aiohttp.ClientResponseError) and exc.status not in {429,500,502,503,504}:
                    raise RuntimeError(f'Microsoft Edge từ chối yêu cầu giọng {selected["name"]} (HTTP {exc.status}).') from None
                if attempt==4:
                    raise RuntimeError(f'Microsoft Edge chưa trả về âm thanh cho giọng {selected["name"]} sau 5 lần kết nối. Hãy thử lại sau.') from None
                await asyncio.sleep(2**attempt)
    try:
        await asyncio.wait_for(connect(),timeout=120)
        words=[]
        if word_timing:
            from .captions import save_words
            for line in metadata.read_text(encoding='utf-8').splitlines():
                item = json.loads(line)
                if item['type'] == 'WordBoundary':
                    words.append({'text': item['text'], 'start': item['offset']/1e7,
                                  'end': (item['offset']+item['duration'])/1e7})
        partial.replace(destination)
        if word_timing:save_words(destination, words)
    except TimeoutError:
        raise RuntimeError(f'Microsoft Edge xử lý giọng {selected["name"]} quá lâu. Hãy thử lại sau.') from None
    finally:
        partial.unlink(missing_ok=True)
        metadata.unlink(missing_ok=True)


def elevenlabs_error(error):
    """Translate provider error codes without exposing raw responses or credentials."""
    try:
        detail = json.loads(error.read(65536)).get('detail', {})
        codes = [detail.get('status'), detail.get('code')] if isinstance(detail,dict) else []
    except (OSError, ValueError, TypeError, AttributeError):
        codes = []
    return elevenlabs_message(codes, error.code)


def elevenlabs_message(codes, status=None):
    from .credentials import KEY_ID_WARNING
    messages = {
        'api_key_id_used_as_api_key': KEY_ID_WARNING,
        'invalid_api_key': 'API key ElevenLabs không hợp lệ. Nhập lại secret key trong Cài đặt → ElevenLabs.',
        'missing_api_key': 'Chưa có API key ElevenLabs. Nhập secret key trong Cài đặt → ElevenLabs.',
        'quota_exceeded': 'Tài khoản ElevenLabs không đủ hạn mức để tạo đoạn voice này.',
        'insufficient_credits': 'Tài khoản ElevenLabs không đủ hạn mức để tạo đoạn voice này.',
        'paid_plan_required': 'Giọng ElevenLabs này là giọng thư viện, không dùng được qua API/CLI với gói Free. Cần tài khoản có quyền dùng giọng này; đổi CLI không bỏ được giới hạn gói.',
        'missing_permissions': 'Key ElevenLabs chưa có quyền tạo giọng. Kết nối lại bằng CLI hoặc kiểm tra quyền Text to Speech của key.',
        'voice_not_found': 'Không tìm thấy giọng ElevenLabs đã chọn. Kiểm tra voice ID và quyền truy cập trong tài khoản.',
        'voice_access_denied': 'API key ElevenLabs chưa có quyền dùng giọng đã chọn.',
        'model_access_denied': 'API key ElevenLabs chưa có quyền dùng model giọng đọc này.',
        'max_character_limit_exceeded': 'Lời đọc vượt giới hạn của ElevenLabs. Chia lời đọc thành các đoạn ngắn hơn.',
        'text_too_long': 'Lời đọc vượt giới hạn của ElevenLabs. Chia lời đọc thành các đoạn ngắn hơn.',
        'unsupported_model': 'Model ElevenLabs không hỗ trợ yêu cầu giọng đọc này.',
        'invalid_voice_id': 'Voice ID ElevenLabs không hợp lệ.',
        'rate_limit_exceeded': 'ElevenLabs đang giới hạn yêu cầu. Chờ một lát rồi thử lại.',
    }
    for code in codes:
        if isinstance(code,str) and code in messages:
            return messages[code]
    defaults = {
        400: 'ElevenLabs từ chối yêu cầu (HTTP 400). Kiểm tra secret key, voice ID và quyền dùng giọng.',
        401: 'API key ElevenLabs không hợp lệ hoặc đã hết hạn',
        402: 'ElevenLabs yêu cầu quyền sử dụng hoặc gói phù hợp cho giọng này (HTTP 402).',
        403: 'API key ElevenLabs không có quyền dùng giọng này hoặc đã hết hạn mức',
        404: 'Không tìm thấy giọng ElevenLabs; kiểm tra quyền truy cập voice ID trong tài khoản',
        429: 'ElevenLabs đang giới hạn yêu cầu hoặc tài khoản đã hết hạn mức',
    }
    return defaults.get(status, f'ElevenLabs CLI chưa tạo được âm thanh'+(f' (HTTP {status})' if status else '. Kiểm tra kết nối và cấu hình CLI.'))


def elevenlabs_cli_error(result):
    # CLI errors are JSON on stdout. Never echo arbitrary provider messages,
    # subprocess commands or response bodies into the UI or logs.
    for output in (result.stdout, result.stderr):
        try:
            error = json.loads(output).get('error', {})
            detail = error.get('details', {}).get('detail', {})
            codes = [error.get('reason')]
            if isinstance(detail, dict):codes += [detail.get('status'),detail.get('code')]
            return elevenlabs_message(codes, error.get('code'))
        except (ValueError, TypeError, AttributeError):
            continue
    return elevenlabs_message([])


def synthesize_elevenlabs(text, voice, rate, destination, word_timing=False):
    from .credentials import elevenlabs_key
    api_key = elevenlabs_key()
    if not api_key:
        raise ValueError("Chưa cấu hình ELEVENLABS_API_KEY. Vào Cài đặt → ElevenLabs để nhập API key.")
    from .credentials import key_format_warning
    if key_format_warning(api_key):
        raise ValueError(key_format_warning(api_key))
    source = destination.with_name(f"{destination.stem}.{uuid.uuid4().hex}.partial.mp3")
    adjusted = source.with_name(source.stem + ".rate.mp3")
    words = []
    try:
        env = os.environ.copy()
        env['ELEVENLABS_API_KEY'] = api_key
        env['NODE_USE_SYSTEM_CA'] = '1'
        command = elevenlabs_command()+['text-to-speech', 'convert_with_timestamps' if word_timing else 'convert',
            '--voice-id',voice,'--output-format','mp3_44100_128','--no-retry','--format','json','--json','-']
        if not word_timing:command += ['--output',str(source.resolve())]
        result = subprocess.run(command, input=json.dumps({'text':text,'model_id':ELEVENLABS_MODEL},ensure_ascii=False),
            capture_output=True,text=True,encoding='utf-8',timeout=120,cwd=ROOT,env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode:
            raise RuntimeError(elevenlabs_cli_error(result))
        if word_timing:
            import base64
            from .captions import alignment_words
            try:
                payload=json.loads(result.stdout)
                source.write_bytes(base64.b64decode(payload['audio_base64'],validate=True))
                words=alignment_words(payload.get('alignment') or payload.get('normalized_alignment') or {})
            except (ValueError,KeyError,TypeError):
                raise RuntimeError('ElevenLabs CLI trả về dữ liệu âm thanh hoặc mốc từ không hợp lệ') from None
        if not source.is_file() or not source.stat().st_size:
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
        if word_timing:
            from .captions import save_words
            speed = 1+rate/100
            save_words(destination, [{**w, 'start': w['start']/speed, 'end': w['end']/speed} for w in words])
    except subprocess.TimeoutExpired:
        raise RuntimeError('ElevenLabs CLI xử lý quá lâu. Kiểm tra kết nối và thử lại.') from None
    except OSError:
        raise RuntimeError('Không chạy được ElevenLabs CLI. Kiểm tra đường dẫn CLI và quyền ghi file.') from None
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
    from .captions import retime_words
    retime_words(source, destination, speed)


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
                await synthesize(cue.text, cue.voice_id, cue.rate, source, word_timing=scene.captions)
            destination = folder / f'cue-{digest}-{round((cue.end-cue.start)*1000)}.wav'
            if not destination.exists() or not destination.stat().st_size:
                await asyncio.to_thread(fit_speech, source, destination, cue.end-cue.start)
            else:
                from .captions import load_words, retime_words
                if load_words(source) and not load_words(destination):
                    source_duration = await asyncio.to_thread(audio_duration, source)
                    retime_words(source, destination, max(1, source_duration/(cue.end-cue.start)))
            cue.audio = destination.relative_to(root).as_posix()


def encode_video(path, spec, root):
    duration = max(1, round(spec["duration"] * spec["fps"])) / spec["fps"]
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-framerate", str(spec["fps"]), "-start_number", "1", "-i", str(path / "frames" / "frame_%04d.png")]
    cues = [cue for shot in spec.get('shots', []) for cue in shot.get('narration', [])]
    music_only = spec.get('audio_mode') == 'music_only'
    if not music_only and any(not cue.get('audio') for cue in cues):
        raise ValueError("Lời thoại trong timeline chưa được tạo thành âm thanh")
    voice = not music_only and bool(spec.get("voice_audio") or cues)
    music = spec.get("music") or spec.get("audio")
    music_cues = [] if music_only else spec.get('music_cues', [])
    if any(not cue.get('audio') for cue in music_cues):
        raise ValueError('Nhạc từng đoạn chưa được tạo theo timeline')
    tracks = [(cue['audio'], cue['start'], cue['end'], cue['volume']) for cue in music_cues]
    if not tracks and music:
        tracks = [(music, 0, duration, 1)]
    music = bool(tracks)
    voices = []
    if not music_only and spec.get('voice_audio'):
        voices.append((spec['voice_audio'], 0, duration))
    if not music_only:voices += [(cue['audio'], cue['start'], cue['end']-cue['start']) for cue in cues]
    for path_name, _, _ in voices:
        cmd += ['-i', str(asset_path(path_name, root))]
    effects = [] if music_only else spec.get('effects', [])
    if any(not effect.get('audio') for effect in effects):
        raise ValueError("Hiệu ứng âm thanh chưa được tạo theo timeline")
    for effect in effects:
        cmd += ['-i',str(asset_path(effect['audio'],root))]
    for track, _, _, _ in tracks:
        cmd += ["-stream_loop", "-1", "-i", str(asset_path(track, root))]
    graph = []
    voice_gain = spec.get("voice_volume", 1)
    music_gain = spec.get("music_volume", .2) if spec.get("music") or music_cues else (spec.get("music_volume", .2) if voice else 1)
    if voice:
        for index, (_, start, window) in enumerate(voices, 1):
            graph += [f"[{index}:a]aresample=48000,apad,atrim=duration={window},asetpts=PTS-STARTPTS,volume={voice_gain},adelay={round(start*1000)}:all=1[v{index}]"]
        if len(voices) == 1:
            graph += ['[v1]anull[v]']
        else:
            graph += [''.join(f'[v{i}]' for i in range(1,len(voices)+1))+f'amix=inputs={len(voices)}:duration=longest:normalize=0[v]']
    if music:
        for offset, (_, start, end, volume) in enumerate(tracks):
            index = len(voices)+len(effects)+1+offset
            window = end-start
            graph += [f"[{index}:a]aresample=48000,atrim=duration={window},asetpts=PTS-STARTPTS,volume={music_gain*volume},afade=t=in:d={min(.02,window/2)},afade=t=out:st={max(0,window-.1)}:d={min(.1,window/2)},adelay={round(start*1000)}:all=1[m{offset}]"]
        graph += [''.join(f'[m{i}]' for i in range(len(tracks)))+f'amix=inputs={len(tracks)}:duration=longest:normalize=0[m]']
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
        font_dir = path / 'caption-fonts'
        font_dir.mkdir(exist_ok=True)
        subtitle_font = font_dir / 'subtitle-font.ttf'
        shutil.copyfile(asset_path(spec["font"], root), subtitle_font)
        from .captions import load_words, word_events, write_ass, font_family
        captions = [(spec['subtitles'], 0, duration, spec.get('voice_audio'))] if spec.get('subtitles') else [
            (cue['text'], cue['start'], cue['end'], cue.get('audio')) for cue in cues]
        events, estimated = [], False
        for text, start, end, audio in captions:
            words = load_words(asset_path(audio, root)) if audio and not music_only else []
            cue_events = word_events(text, start, end, words)
            estimated = estimated or any(event['timing'] == 'estimated' for event in cue_events)
            events.extend(cue_events)
        write_ass(path/'captions.ass', events, spec['width'], spec['height'], font_family(subtitle_font))
        (path/'caption-timing.json').write_text(json.dumps({'estimated': estimated, 'words': events}, ensure_ascii=False), encoding='utf-8')
        cmd += ['-vf', 'ass=filename=captions.ass:fontsdir=caption-fonts']
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-t", str(duration), str(path / "video.mp4")]
    subprocess.run(cmd, cwd=path, check=True, timeout=1800)
