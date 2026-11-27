"""Recent frame timings shared by the Blender process and job status API."""
import json
import math


def samples(path):
    try:
        values = json.loads((path / 'render-timing.json').read_text(encoding='utf-8'))
        return [value for value in values if isinstance(value, (int, float))
                and math.isfinite(value) and value > 0][-20:]
    except (OSError, ValueError, TypeError):
        return []


def record_frame(path, seconds):
    values = samples(path) + [seconds]
    target = path / 'render-timing.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(values[-20:]), encoding='utf-8')
    temporary.replace(target)


def remaining_seconds(path, frames_left):
    values = samples(path)
    if not values or frames_left <= 0:
        return None
    return math.ceil(sum(values) / len(values) * frames_left)
