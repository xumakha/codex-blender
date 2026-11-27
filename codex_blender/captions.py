"""Word timing sidecars and compact, animated ASS captions."""
import json
import math
from pathlib import Path
import re
import struct
import unicodedata
from .jobs import write_json


def timing_path(audio):
    return Path(str(audio) + '.words.json')


def save_words(audio, words):
    write_json(timing_path(audio), words)


def load_words(audio):
    try:
        words = json.loads(timing_path(audio).read_text(encoding='utf-8'))
        if not isinstance(words, list) or not all(
            isinstance(w['text'], str) and math.isfinite(w['start']) and math.isfinite(w['end'])
            and 0 <= w['start'] < w['end'] for w in words
        ):
            return []
        if any(b['start'] < a['start'] for a, b in zip(words,words[1:])):
            return []
        return words
    except (OSError, ValueError, KeyError, TypeError):
        return []


def alignment_words(alignment):
    chars = alignment.get('characters', [])
    starts = alignment.get('character_start_times_seconds', [])
    ends = alignment.get('character_end_times_seconds', [])
    if not (len(chars) == len(starts) == len(ends)):
        raise ValueError('Invalid ElevenLabs character alignment')
    words, text, start, end = [], '', 0, 0
    for char, a, b in zip(chars, starts, ends):
        if char.isspace():
            if text and end > start:
                words.append({'text': text, 'start': start, 'end': end})
            text = ''
        else:
            if not text:
                start = a
            text += char
            end = b
    if text and end > start:
        words.append({'text': text, 'start': start, 'end': end})
    return words


def retime_words(source, destination, speed):
    words = load_words(source)
    if words:
        save_words(destination, [{**w, 'start': w['start']/speed, 'end': w['end']/speed} for w in words])


def word_events(text, start, end, words=None):
    """Use provider timing; legacy/uploaded audio falls back to weighted text timing."""
    tokens = list(re.finditer(r'\S+', text))
    if not tokens or end <= start:
        return []
    if words:
        # Some providers emit more than one token per boundary. Keep the caption
        # compact even in that case, while retaining the boundary's spoken window.
        words = [event for word in words for event in word_events(
            word['text'],word['start'],word['end'])]
    normalize = lambda value: re.sub(r'\W', '', unicodedata.normalize('NFC',value)).casefold()
    if words and len(words) == len(tokens) and all(normalize(w['text']) == normalize(t[0]) for w,t in zip(words,tokens)):
        result = []
        for index, word in enumerate(words):
            a = start + word['start']
            # Hold briefly through the inter-word gap, but never through a long pause.
            next_start = words[index+1]['start'] if index+1 < len(words) else word['end']+.1
            b = start + min(next_start, word['end']+.15)
            if a < end and b > a:
                result.append({'text': tokens[index][0], 'start': a, 'end': min(end, b), 'timing': 'provider'})
        return result
    weights = [max(1, len(re.sub(r'\W', '', token[0]))) + (2 if token[0][-1:] in '.,!?;:' else 0) for token in tokens]
    total, cursor, result = sum(weights), start, []
    for token, weight in zip(tokens, weights):
        finish = cursor + (end-start)*weight/total
        result.append({'text': token[0], 'start': cursor, 'end': min(end, finish), 'timing': 'estimated'})
        cursor = finish
    return result


def font_family(path):
    """Read the font family from a TTF/OTF name table for libass font selection."""
    data = Path(path).read_bytes()
    count = struct.unpack_from('>H', data, 4)[0]
    for index in range(count):
        tag, _, offset, _ = struct.unpack_from('>4sIII', data, 12+16*index)
        if tag != b'name':
            continue
        _, entries, storage = struct.unpack_from('>HHH', data, offset)
        names = []
        for entry in range(entries):
            platform, _, language, name, length, relative = struct.unpack_from('>6H', data, offset+6+12*entry)
            if name == 1:
                value = data[offset+storage+relative:offset+storage+relative+length]
                family = value.decode('utf-16-be' if platform in (0, 3) else 'mac_roman', errors='replace')
                names.append((platform == 3 and language == 1033, family))
        if names:
            return max(names)[1].replace(',', ' ')
    return 'Arial'


def ass_time(seconds):
    value = max(0, round(seconds*100))
    hours, value = divmod(value, 360000)
    minutes, value = divmod(value, 6000)
    secs, cents = divmod(value, 100)
    return f'{hours}:{minutes:02d}:{secs:02d}.{cents:02d}'


def write_ass(path, events, width, height, family):
    size = max(16, round(width/19))
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{family},{size},&H00FFFFFF,&H00FFFFFF,&H00141414,&H80000000,-1,0,0,0,100,100,0,0,1,{max(1.5,width/400):.2f},1,5,20,20,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    lines = [header]
    for event in events:
        start, end = event['start'], event['end']
        if ass_time(end) <= ass_time(start):
            continue
        # Escape ASS controls so user text stays literal.
        text = event['text'].replace('\\', '\uFF3C').replace('{', '\uFF5B').replace('}', '\uFF5D')
        span = max(10, round((end-start)*1000))
        peak, settle = min(65, span//3), min(155, span*2//3)
        # Keep exceptionally long words inside the title-safe area, including overshoot.
        scale = min(100, 80*width/max(1, len(text)*size*.65*1.12))
        tags = (f'{{\\pos({width/2:.1f},{height*.82:.1f})\\fscx{scale*.84:.1f}\\fscy84'
                f'\\t(0,{peak},\\fscx{scale*1.12:.1f}\\fscy112)'
                f'\\t({peak},{settle},\\fscx{scale:.1f}\\fscy100)\\fad(15,{min(45,span//5)})}}')
        lines.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},Word,,0,0,0,,{tags}{text}\n')
    Path(path).write_text(''.join(lines), encoding='utf-8')
