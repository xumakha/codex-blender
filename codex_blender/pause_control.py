"""File-based render checkpoints, also importable inside Blender."""
import time


def checkpoint(path):
    requested = path / ".pause-requested"
    acknowledged = path / ".paused"
    if not requested.exists():
        return
    acknowledged.touch()
    try:
        while requested.exists():
            time.sleep(.2)
    finally:
        acknowledged.unlink(missing_ok=True)
