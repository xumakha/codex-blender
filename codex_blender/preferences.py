"""Only explicit user setting changes update these durable defaults, never AI output."""
import json
import threading
from . import library
from .jobs import write_json

LOCK=threading.RLock()
VIDEO_FIELDS={'fps','width','height','samples','font','music','music_volume','voice_mode','voice_id',
              'voice_file','rate','voice_volume','duck_music'}
UI_FIELDS={'aspect','resolution','assetgen-mode','assetgen-limit','assetgen-style'}

def read():
    with LOCK:
        path=library.DATA/'preferences.json'
        if not path.exists():return {'video':{},'ui':{}}
        return json.loads(path.read_text(encoding='utf-8'))

def save(changes):
    from .studio import Draft
    if not isinstance(changes,dict) or set(changes)-{'video','ui'}:raise ValueError('Cài đặt không hợp lệ')
    video=changes.get('video',{});ui=changes.get('ui',{})
    if not isinstance(video,dict) or set(video)-VIDEO_FIELDS:raise ValueError('Chỉ lưu các lựa chọn cài đặt video')
    if not isinstance(ui,dict) or set(ui)-UI_FIELDS:raise ValueError('Cài đặt giao diện không hợp lệ')
    with LOCK:
        value=read();merged={**value['video'],**video}
        validated=Draft.model_validate(merged).model_dump(mode='json')
        value['video']={key:validated[key] for key in merged}
        value['ui'].update(ui)
        allowed={'aspect':{'9:16','16:9','1:1'},'resolution':{'draft','hd','full','custom'},
                 'assetgen-mode':{'single','multiple'},'assetgen-limit':{'5','10','20','40'}}
        for key,val in value['ui'].items():
            if not isinstance(val,str) or len(val)>1000 or (key in allowed and val not in allowed[key]):raise ValueError('Giá trị cài đặt không hợp lệ')
        library.DATA.mkdir(parents=True,exist_ok=True)
        write_json(library.DATA/'preferences.json',value)
        return value

def new_draft(values=None):
    from .studio import Draft
    return Draft.model_validate({**read()['video'],**(values or {})})
