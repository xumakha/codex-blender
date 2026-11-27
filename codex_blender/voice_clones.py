"""Persistent custom voice registrations and CLI cloning of user-provided samples."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import uuid

from . import config
from .credentials import elevenlabs_key
from .jobs import write_json

LOCK = threading.RLock()


def records():
    path=config.DATA/'voice-clones.json'
    with LOCK:
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []


def options():
    return [{'id':item.get('voice_id') or 'clone:'+item['id'], 'name':item['name'],
             'language':'Tiếng Việt', 'gender':'', 'provider':item.get('provider','elevenlabs'),
             'requires_api_key':item.get('provider','elevenlabs')=='elevenlabs',
             'disabled':item['state']!='ready', 'status':item['state'], 'status_message':item.get('error','')}
            for item in records()]


def save(item):
    with LOCK:
        values=records()
        values=[value for value in values if value['id']!=item['id']]+[item]
        config.DATA.mkdir(parents=True,exist_ok=True)
        write_json(config.DATA/'voice-clones.json',values)


def create(sample, name):
    name=name.strip()
    if not name or len(name)>100:raise ValueError('Tên giọng cần từ 1 đến 100 ký tự.')
    sample=Path(sample).resolve()
    if not sample.is_file() or sample.suffix.lower() not in {'.mp3','.wav','.m4a','.ogg'}:
        raise ValueError('Chọn file mẫu giọng MP3/WAV/M4A/OGG có sẵn.')
    key=elevenlabs_key()
    if not key:raise ValueError('Đăng nhập ElevenLabs CLI hoặc cấu hình API key trước khi clone.')
    command=config.elevenlabs_command()
    previous=next((item for item in records() if item['name'].casefold()==name.casefold()),None)
    if previous and previous.get('voice_id'):
        return previous
    item=previous or {'id':uuid.uuid4().hex,'name':name,'voice_id':None}
    folder=config.DATA/'voice-samples'
    folder.mkdir(parents=True,exist_ok=True)
    stored=folder/(item['id']+sample.suffix.lower())
    if stored.resolve()!=sample:shutil.copyfile(sample,stored)
    item.update(sample=str(stored),state='pending',error='Chưa hoàn tất tạo giọng clone.')
    save(item)
    env=os.environ.copy()
    env['ELEVENLABS_API_KEY']=key
    try:
        result=subprocess.run(command+['voices','ivc','create','--name',name,'--files',str(stored),
            '--description','Vietnamese narrative voice from a user-provided recording',
            '--no-retry','--format','json'],capture_output=True,text=True,encoding='utf-8',
            cwd=config.ROOT,env=env,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:payload=json.loads(result.stdout)
        except ValueError:payload={}
        if result.returncode or not isinstance(payload,dict) or not payload.get('voice_id'):
            from .audio import elevenlabs_cli_error
            error=payload.get('error',{}) if isinstance(payload,dict) else {}
            if error.get('reason')=='paid_plan_required':
                raise RuntimeError('Tài khoản ElevenLabs hiện chưa có quyền Instant Voice Cloning. Giọng chưa được tạo.')
            raise RuntimeError(elevenlabs_cli_error(result))
        item.update(voice_id=payload['voice_id'],state='verification' if payload.get('requires_verification') else 'ready',
                    error='ElevenLabs yêu cầu xác minh giọng trước khi sử dụng.' if payload.get('requires_verification') else '')
        save(item)
        return item
    except (OSError,subprocess.TimeoutExpired):
        item.update(error='Chưa hoàn tất kết nối ElevenLabs CLI để tạo clone. File mẫu được giữ lại.')
        save(item)
        raise RuntimeError(item['error']) from None
    except RuntimeError as exc:
        item.update(error=str(exc))
        save(item)
        raise


def main():
    parser=argparse.ArgumentParser(description='Create and register a voice clone for Studio')
    parser.add_argument('--name',required=True)
    parser.add_argument('--sample',required=True,type=Path)
    args=parser.parse_args()
    try:
        item=create(args.sample,args.name)
        print(json.dumps({'name':item['name'],'state':item['state'],'voice_id':item['voice_id']},ensure_ascii=True))
    except (ValueError,RuntimeError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=True))
        raise SystemExit(1)


if __name__=='__main__':main()
