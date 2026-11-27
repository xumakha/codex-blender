"""Run VoiceStudio's installed OmniVoice GGUF engine without its desktop backend."""
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import wave

import imageio_ffmpeg

from .captions import timing_path

# Loading two models at once exhausts memory on smaller GPUs.
LOCK = threading.Lock()
FILES = ('executable', 'model', 'codec', 'reference_audio', 'reference_text')


def settings(record):
    local = record.get('local', {})
    if not isinstance(local, dict) or any(
        not isinstance(local.get(key), str) or not Path(local[key]).is_file() for key in FILES
    ):
        raise RuntimeError('Thiếu bộ tạo giọng hoặc file mẫu VoiceStudio trên máy. Kiểm tra ổ đĩa đã cài VoiceStudio.')
    if local.get('backend') not in {'Vulkan0', 'CPU'}:
        raise RuntimeError('Cấu hình thiết bị tạo giọng VoiceStudio không hợp lệ.')
    return local


def synthesize(text, voice, rate, destination):
    from .voice_clones import records
    record = next((item for item in records() if item.get('voice_id') == voice
                   and item.get('provider') == 'voicestudio' and item.get('state') == 'ready'), None)
    if record is None:
        raise ValueError('Giọng clone VoiceStudio chưa sẵn sàng.')
    local = settings(record)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Keep scratch files beside the installed reference, including on drive D.
    scratch = Path(local['reference_audio']).parent / 'temp'
    scratch.mkdir(exist_ok=True)
    partial = None
    try:
        with LOCK, tempfile.TemporaryDirectory(prefix='tts-', dir=scratch) as folder:
            wav = Path(folder) / 'speech.wav'
            env = os.environ.copy()
            env['GGML_BACKEND'] = local['backend']
            env['TEMP'] = env['TMP'] = folder
            result = subprocess.run([
                local['executable'], '--model', local['model'], '--codec', local['codec'],
                '--ref-wav', local['reference_audio'], '--ref-text', local['reference_text'],
                '--lang', 'Vietnamese', '--steps', '16', '--seed', '42', '-o', str(wav),
            ], input=text, capture_output=True, text=True, encoding='utf-8', errors='replace',
                cwd=Path(local['executable']).parent, env=env,
                timeout=max(300, min(3600, len(text)*3)),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if result.returncode:
                diagnostic = (result.stdout + result.stderr).lower()
                if any(token in diagnostic for token in ('outofdevicememory', 'failed to allocate', 'out of memory')):
                    raise RuntimeError('VoiceStudio thiếu RAM hoặc bộ nhớ GPU. Đóng ứng dụng đang dùng GPU rồi thử lại.')
                raise RuntimeError('Bộ tạo giọng VoiceStudio chưa tạo được âm thanh. Kiểm tra model và thiết bị trên máy.')
            try:
                with wave.open(str(wav), 'rb') as audio:
                    if audio.getnframes() < audio.getframerate() / 10:
                        raise ValueError('Empty audio')
            except (OSError, EOFError, wave.Error, ValueError):
                raise RuntimeError('VoiceStudio trả về file âm thanh rỗng hoặc không hợp lệ.') from None
            # Convert on the destination volume, then replace atomically. Failed
            # runs preserve existing audio and cannot leave playable partials.
            with tempfile.NamedTemporaryFile(prefix='.local-voice-', suffix='.mp3',
                                             dir=destination.parent, delete=False) as output:
                partial = Path(output.name)
            converted = subprocess.run([
                imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-y', '-i', str(wav),
                '-af', f'atempo={1+rate/100:.4f}', '-codec:a', 'libmp3lame', '-b:a', '128k', str(partial),
            ], capture_output=True, timeout=120)
            if converted.returncode or not partial.stat().st_size:
                raise RuntimeError('Không chuyển đổi được âm thanh VoiceStudio sang MP3.')
            partial.replace(destination)
            # This engine supplies no word alignment. Let captions use their
            # explicitly marked estimated timing; never reuse stale alignment.
            timing_path(destination).unlink(missing_ok=True)
    except subprocess.TimeoutExpired:
        raise RuntimeError('VoiceStudio xử lý giọng quá lâu. Thử đoạn ngắn hơn hoặc giải phóng bộ nhớ máy.') from None
    except OSError:
        raise RuntimeError('Không chạy được bộ tạo giọng VoiceStudio. Kiểm tra ổ đĩa và quyền ghi file.') from None
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)
