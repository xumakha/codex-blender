"""Local provider credentials, never included in project or bootstrap responses."""
import json
import os
import re
import threading

from . import config
from .jobs import write_json

LOCK = threading.Lock()
ENV_FILE = config.ROOT / '.env'
KEY_ID_WARNING = 'Đây là ID của API key, không phải secret key. Tạo mới hoặc xoay (rotate) key trên ElevenLabs rồi sao chép toàn bộ key bắt đầu bằng sk_.'


def key_format_warning(value):
    # The provider returns api_key_id_used_as_api_key for these dashboard IDs.
    return KEY_ID_WARNING if re.fullmatch(r'[0-9a-fA-F]{64}', value) else None


def elevenlabs_credential():
    from dotenv import dotenv_values
    project_key = (dotenv_values(ENV_FILE, interpolate=False).get('ELEVENLABS_API_KEY') or '').strip() if ENV_FILE.is_file() else ''
    path = config.DATA / 'credentials.json'
    if path.is_file():
        key = json.loads(path.read_text(encoding='utf-8')).get('elevenlabs_api_key', '')
        # A new CLI sign-in replaces an older saved key; an explicit later save
        # in Settings can override it without changing the project's env file.
        if key and (not project_key or path.stat().st_mtime_ns > ENV_FILE.stat().st_mtime_ns):
            return key, 'saved'
    if project_key:
        return project_key, 'project-env'
    return os.environ.get('ELEVENLABS_API_KEY', '').strip(), 'environment'


def elevenlabs_key():
    return elevenlabs_credential()[0]


def status():
    key, source = elevenlabs_credential()
    warning = key_format_warning(key)
    result = {'configured': bool(key) and not warning,
              'saved': (config.DATA / 'credentials.json').is_file(), 'source': source}
    if warning:
        result['warning'] = warning
    return result


def save_elevenlabs(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024 or any(c.isspace() for c in value.strip()):
        raise ValueError('API key không hợp lệ. Hãy dán key không chứa khoảng trắng.')
    if key_format_warning(value.strip()):
        raise ValueError(KEY_ID_WARNING)
    with LOCK:
        config.DATA.mkdir(parents=True, exist_ok=True)
        write_json(config.DATA / 'credentials.json', {'elevenlabs_api_key': value.strip()})
    return status()


def delete_elevenlabs():
    with LOCK:
        (config.DATA / 'credentials.json').unlink(missing_ok=True)
    return status()
