"""Artifact checks shared by the Blender process and its parent worker."""


def complete_png(path):
    try:
        with path.open('rb') as image:
            if image.read(8) != b'\x89PNG\r\n\x1a\n':
                return False
            image.seek(-12, 2)
            return image.read() == b'\x00\x00\x00\x00IEND\xaeB`\x82'
    except (OSError, ValueError):
        return False


def complete_blend(path):
    try:
        with path.open('rb') as blend:
            return blend.read(7) == b'BLENDER' and path.stat().st_size > 12
    except OSError:
        return False
