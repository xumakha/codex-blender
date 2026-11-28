"""Frame sampling for shot reviews and render timing for job status."""
import json
import math


def shot_review_frames(count, fps, bindings):
    """Return preview stills and bounds-check frames on the shot's one-based timeline."""
    stills = {1, (count + 1) // 2, count}
    starts = set()
    action_stills = set()
    for binding in bindings:
        start = min(count, 1 + round(binding['start'] * fps))
        end = min(count, 1 + round(binding['end'] * fps))
        starts.add(start)
        action_stills.update(((start + end) // 2, end))

    # Spend two additional renders on action beats least represented by the baseline stills.
    candidates = action_stills - stills
    for _ in range(min(2, len(candidates))):
        frame = max(candidates, key=lambda candidate: (min(abs(candidate - drawn) for drawn in stills), candidate))
        stills.add(frame)
        candidates.remove(frame)
    return stills, stills | starts | action_stills


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
