"""Prompt contracts and checks between screenplay, animation and rendering."""
import hashlib
import json
import re
from .geometry import expand_objects, descendants, recipe_instances

DIRECTOR_REVISION = 8


def signature(draft):
    values = {key: getattr(draft, key) for key in (
        "prompt", "references", "fps", "width", "height",
        "voice_mode", "voice_id", "narration", "rate", "music", "font", "subtitles")}
    values['_director_revision'] = DIRECTOR_REVISION
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def prompt_contract(prompt):
    def seconds(parts):
        a, b, c = parts
        return int(a)*60+int(b) if c is None else int(a)*3600+int(b)*60+int(c)
    clock = r"(\d{1,2}):(\d{2})(?::(\d{2}))?"
    intervals = []
    for match in re.finditer(clock+r"\s*[–—-]\s*"+clock, prompt):
        interval = (seconds(match.groups()[:3]), seconds(match.groups()[3:]))
        if interval not in intervals:
            intervals.append(interval)
    # Only a continuous screenplay is treated as a hard timeline contract.
    cursor = 0
    for start, end in intervals:
        if start != cursor or end <= start:
            intervals = []
            break
        cursor = end
    speech_matches = list(re.finditer(r'(?:Lời đọc|Lời thoại|Thuyết minh|Narration|Dialogue)\s*\**\s*:\**\s*[“"](.+?)[”"]', prompt, re.I | re.S))
    speech = [match[1] for match in speech_matches]
    speech_windows = []
    for match in speech_matches:
        tail = prompt[match.end():].split('\n',1)[0]
        window = re.search(r'(?:từ|from)\s*(\d+(?:[.,]\d+)?)\s*(?:giây|seconds?|s)?\s*(?:đến|tới|to|[–-])\s*(\d+(?:[.,]\d+)?)',tail,re.I)
        if window:
            speech_windows.append((match[1],float(window[1].replace(',','.')),float(window[2].replace(',','.'))))
    number = r'\d+(?:[.,]\d+)?'
    unit = r'giây|seconds?|secs?|s\b|phút|minutes?|mins?'
    label = r'(?:thời lượng|duration|video\s+(?:dài|of))[^\d\n]{0,20}'
    explicit = re.search(label+rf'(?P<lower>{number})\s*(?:(?P<lower_unit>{unit})\s*)?'
        +rf'(?:[–—−-]|đến|tới|to)\s*(?P<upper>{number})\s*(?P<unit>{unit})', prompt, re.I)
    duration, duration_range = None, None
    def to_seconds(value, units):
        return float(value.replace(',', '.')) * (60 if units.lower().startswith(('phút','min')) else 1)
    if explicit:
        duration_range = (to_seconds(explicit['lower'], explicit['lower_unit'] or explicit['unit']),
                          to_seconds(explicit['upper'], explicit['unit']))
    else:
        explicit = re.search(label+rf'({number})\s*({unit})', prompt, re.I)
        if explicit:
            duration = to_seconds(explicit[1], explicit[2])
    request = prompt.split('\n\n',1)[0][:500]
    excerpt = re.search(r'(?:tạo|dựng|render|xuất|make|create)[^\n]{0,50}?(?:thử|preview|test|đoạn|clip)[^\d\n]{0,20}(\d+(?:[.,]\d+)?)\s*(giây|seconds?|s\b|phút|minutes?)', request, re.I)
    # A screenplay's declared duration owns the full video. An old preview prefix
    # must not silently discard its timeline and dialogue.
    if excerpt and explicit is None:
        seconds = float(excerpt[1].replace(',','.')) * (60 if excerpt[2].lower().startswith(('phút','min')) else 1)
        if re.search(r'thử|preview|test',request,re.I) or (intervals and intervals[-1][1]>seconds+.01):
            return {'scope':'excerpt','duration':seconds,'duration_range':None,'intervals':[(0,seconds)],
                    'source_intervals':intervals,'speech':[],'speech_windows':[],
                    'scope_request':request}
    return {"scope":"full", "intervals": intervals, "duration": intervals[-1][1] if intervals else duration,
            "duration_range":duration_range, "speech": speech, "speech_windows": speech_windows}


def check_contract(plan, contract):
    bounds = contract.get('duration_range')
    if bounds and (bounds[0] > bounds[1] or not bounds[0]-.01 <= plan.duration <= bounds[1]+.01):
        raise ValueError(f"Video phải dài trong khoảng {bounds[0]}–{bounds[1]} giây theo prompt, AI trả về {plan.duration} giây")
    if contract['duration'] is not None and abs(plan.duration - contract['duration']) > .01:
        raise ValueError(f"Timeline phải dài {contract['duration']} giây theo prompt, AI trả về {plan.duration} giây")
    boundaries = {round(shot.start, 3) for shot in plan.shots} | {round(plan.duration, 3)}
    if any(start not in boundaries or end not in boundaries for start, end in contract['intervals']):
        raise ValueError("Phân cảnh AI chưa giữ đúng các mốc thời gian trong prompt")
    normalize = lambda text: ' '.join(text.split()).strip('“”" ')
    actual = normalize(' '.join(cue.text for shot in plan.shots for cue in shot.narration))
    cursor = 0
    for text in contract['speech']:
        found = actual.find(normalize(text), cursor)
        if found < 0:
            raise ValueError("AI bỏ sót hoặc thay đổi lời thoại được trích nguyên văn trong prompt")
        cursor = found + len(normalize(text))
    for text, start, end in contract.get('speech_windows', []):
        if not any(normalize(cue.text)==normalize(text) and abs(cue.start-start)<.01 and abs(cue.end-end)<.01 for shot in plan.shots for cue in shot.narration):
            raise ValueError("AI chưa giữ đúng mốc bắt đầu/kết thúc lời thoại trong prompt")
    if plan.unsupported:
        raise ValueError("Chưa thể dựng đầy đủ yêu cầu: " + '; '.join(plan.unsupported))


def check_elements(brief, design):
    if not brief.elements:
        return
    templates = [obj.model_dump(mode='json') for obj in design.objects]
    expanded = expand_objects(templates)
    names = {obj.name for obj in design.objects}
    physical_elements = [element for element in brief.elements if element.construction!='overlay']
    requirements = {element.id:element for element in physical_elements}
    bindings = {binding.element_id:binding for binding in design.element_bindings}
    if len(requirements)!=len(physical_elements) or len(bindings)!=len(design.element_bindings) or set(bindings)!=set(requirements):
        raise ValueError(f'Cảnh {brief.title}: mỗi yếu tố trong prompt cần một đối chiếu mô hình riêng')
    element_objects = {}
    for identifier, element in requirements.items():
        binding = bindings[identifier]
        references = set(binding.objects) | {name for part in binding.parts for name in part.objects}
        if not references <= names:
            raise ValueError(f'{element.label}: mô hình tham chiếu đối tượng không tồn tại')
        element_objects[identifier] = descendants(templates,binding.objects)
        if element.rigged and not any(rig.root in element_objects[identifier]
                and any(bone.objects for bone in rig.bones) for rig in design.rigs):
            raise ValueError(f'{element.label}: cần rig xương thật với geometry gắn vào bone')
        instances = recipe_instances(templates,binding.objects)
        if element.construction=='geometry' and any(obj['kind'] in ('image','model') for obj in expanded if obj['name'].split('__R',1)[0] in element_objects[identifier]):
            raise ValueError(f'{element.label}: phải dựng bằng hình khối Blender; không dùng ảnh hoặc mô hình đóng cứng thay thế')
        if element.construction!='image' and len(instances)<element.count:
            raise ValueError(f'{element.label}: chưa dựng đủ {element.count} đối tượng theo prompt')
        parts = {part.part:part for part in binding.parts}
        if len(parts)!=len(binding.parts) or set(parts)!={part.name for part in element.parts}:
            raise ValueError(f'{element.label}: thiếu bộ phận hình khối đã mô tả trong prompt')
        used = set()
        for requirement in element.parts:
            refs = set(parts[requirement.name].objects)
            if not refs <= element_objects[identifier]:
                raise ValueError(f'{element.label}: bộ phận phải thuộc đúng mô hình')
            instances = recipe_instances(templates,refs,parts=True)
            instance_names = {obj['name'] for obj in instances}
            if len(instances)<requirement.count or used & instance_names:
                raise ValueError(f'{element.label}: cần dựng riêng và đủ số lượng bộ phận {requirement.name}')
            used |= instance_names
    for action in design.bindings:
        if not action.elements or not set(action.elements)<=set(requirements):
            raise ValueError(f'Cảnh {brief.title}: hành động phải xác định đúng nhân vật/đạo cụ thực hiện')
        allowed = set().union(*(element_objects[name] for name in action.elements))
        if not set(action.objects)<=allowed:
            raise ValueError(f'Cảnh {brief.title}: không thể chuyển động đối tượng khác thay cho chủ thể của hành động')


def check_inventory(plan, prompt, library_only=False):
    normalize = lambda value: ' '.join(value.casefold().split())
    original = normalize(prompt)
    reuse_pattern = (
        r'(?:ưu tiên|sử dụng lại|tái sử dụng|dùng lại|reuse|use existing)[^\n.]{0,160}(?:assets?|thư viện|models?)'
        r'|(?:assets?|mô hình)[^\n.]{0,100}(?:có sẵn|trong thư viện|đã có|existing)')
    reuse_allowed = any(re.search(reuse_pattern,line,re.I) and not re.search(
        r'\b(không|never|without|do not|don.t)\b',line,re.I) for line in prompt.splitlines())
    rig_required = any(re.search(r'rig xương|skeletal rig|armature|skeleton rig',line,re.I)
        and not re.search(r'\b(không|without|no)\b',line,re.I) for line in prompt.splitlines())
    for shot in plan.shots:
        if not shot.elements:
            raise ValueError(f'Cảnh {shot.title}: cần liệt kê đầy đủ bối cảnh, nhân vật và đạo cụ từ prompt')
        for element in shot.elements:
            if rig_required and element.role == 'character' and element.construction == 'geometry':
                element.rigged = True
            if normalize(element.source) not in original:
                raise ValueError(f'{element.label}: source phải trích nguyên văn chi tiết trong prompt')
            if element.construction=='asset' and not library_only and not reuse_allowed and not re.search(r'\.glb\b|mô hình có sẵn|asset|reuse|existing model|uploaded model',element.source,re.I):
                raise ValueError(f'{element.label}: prompt không yêu cầu dùng asset; hãy dựng hình khối Blender')
            if element.role=='character' and element.construction=='geometry' and not element.parts:
                raise ValueError(f'{element.label}: cần tách các bộ phận để dựng nhân vật bằng hình khối')
            # A mention of ten floors in a studio/character/stair description does not mean
            # there should be ten studios, people or flights. The building owns this count.
            counts = re.finditer(r'\b(\d+)\s*(?:tầng|floors?)\b',element.source,re.I) if element.role=='setting' and re.search(r'nhà|building|house',element.label,re.I) else []
            for match in counts:
                count = int(match[1])
                if count>1 and count not in [element.count]+[part.count for part in element.parts]:
                    raise ValueError(f'{element.label}: cần khai báo {count} bộ phận theo số lượng trong prompt')


def normalize_inventory(plan):
    # Caption text is generated by the timed audio/caption pipeline, rather than a 3D prop.
    if plan.captions:
        for shot in plan.shots:
            for element in shot.elements:
                if element.role=='graphic' and re.search(r'phụ đề|subtitles?|captions?',element.label,re.I):
                    element.construction='overlay'
    return plan


def moves_during(obj, start, end):
    for prop in ('location', 'rotation', 'scale', 'visible', 'opacity'):
        previous, time = getattr(obj, prop), 0
        for key in sorted(obj.keyframes, key=lambda key: key.time):
            value = getattr(key, prop)
            if value is None:
                continue
            if value != previous and key.time > time and key.time > start and time < end:
                return True
            previous, time = value, key.time
    return False


def check_animation(brief, design):
    if not brief.animate:
        return
    objects = {obj.name: obj for obj in design.objects}
    covered = set()
    for binding in design.bindings:
        if binding.action_index >= len(brief.actions) or not 0 <= binding.start < binding.end <= brief.end-brief.start:
            raise ValueError(f"Cảnh {brief.title}: mốc hành động không hợp lệ")
        if any(name not in objects for name in binding.objects):
            raise ValueError(f"Cảnh {brief.title}: hành động tham chiếu đối tượng không tồn tại")
        animated = any(moves_during(objects[name], binding.start, binding.end) for name in binding.objects)
        for rig in design.rigs:
            bones = {bone.name:bone for bone in rig.bones}
            for bone in rig.bones:
                if not set(bone.objects).intersection(binding.objects):
                    continue
                chain = [bone]
                while chain[-1].parent is not None:
                    chain.append(bones[chain[-1].parent])
                for joint in chain:
                    previous, time = joint.rotation, 0
                    for key in sorted(joint.keyframes, key=lambda key:key.time):
                        if key.rotation != previous and key.time > time and key.time > binding.start and time < binding.end:
                            animated = True
                        previous, time = key.rotation, key.time
        if not animated:
            raise ValueError(f"Cảnh {brief.title}: hành động chưa có chuyển động đối tượng thực sự")
        covered.add(binding.action_index)
    if covered != set(range(len(brief.actions))):
        raise ValueError(f"Cảnh {brief.title}: thiếu chuyển động cho hành động trong prompt; không thể chỉ zoom camera")


def object_names(scene):
    if scene.get('shots'):
        return [(f"S{i+1:02d}_{obj['name']}", shot['title']) for i, shot in enumerate(scene['shots']) for obj in expand_objects(shot['objects'])]
    return [(obj['name'], '') for obj in expand_objects(scene['objects'])]
