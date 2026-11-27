"""Find a local font with Vietnamese glyphs and copy it into the asset library."""
import os
from pathlib import Path
import shutil
import struct
import threading
import uuid

from .config import asset_path

LOCK = threading.Lock()
VIETNAMESE = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzĂăÂâĐđÊêÔôƠơƯư' + ''.join(map(chr, range(0x1EA0, 0x1EFA)))


def supports_vietnamese(path):
    try:
        data = Path(path).read_bytes()
        u16 = lambda offset: struct.unpack_from('>H', data, offset)[0]
        u32 = lambda offset: struct.unpack_from('>I', data, offset)[0]
        tables = {data[12+i*16:16+i*16]: u32(20+i*16) for i in range(u16(4))}
        cmap = tables[b'cmap']
        supported = set()
        needed = set(map(ord, VIETNAMESE))
        for index in range(u16(cmap+2)):
            platform, encoding, offset = struct.unpack_from('>HHI', data, cmap+4+index*8)
            if platform != 0 and (platform != 3 or encoding not in {1, 10}):
                continue
            start = cmap+offset
            fmt = u16(start)
            if fmt == 12:
                for group in range(u32(start+12)):
                    first, last, glyph = struct.unpack_from('>III', data, start+16+group*12)
                    supported.update(cp for cp in needed if first <= cp <= last and glyph+cp-first != 0)
            elif fmt == 4:
                count = u16(start+6)//2
                for segment in range(count):
                    last = u16(start+14+segment*2)
                    first = u16(start+16+count*2+segment*2)
                    delta = u16(start+16+count*4+segment*2)
                    address = start+16+count*6+segment*2
                    offset = u16(address)
                    for cp in needed:
                        if first <= cp <= last:
                            glyph = u16(address+offset+(cp-first)*2) if offset else cp
                            if glyph and (glyph+delta) % 65536:
                                supported.add(cp)
        return needed <= supported
    except (OSError, KeyError, IndexError, struct.error):
        return False


def ensure_font(root, preferred=None):
    if preferred:
        if not supports_vietnamese(asset_path(preferred, root)):
            raise ValueError('Font đã chọn thiếu ký tự tiếng Việt. Chọn font TTF/OTF hỗ trợ đầy đủ dấu.')
        return preferred
    with LOCK:
        for path in sorted((root/'fonts').glob('*')):
            if path.suffix.lower() in {'.ttf', '.otf'} and supports_vietnamese(path):
                return path.relative_to(root).as_posix()
        system = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts'
        candidates = [system/'arial.ttf', system/'segoeui.ttf',
                      Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                      Path('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf')]
        for source in candidates:
            if supports_vietnamese(source):
                folder = root/'fonts'
                folder.mkdir(parents=True, exist_ok=True)
                target = folder/('studio-vietnamese-'+source.name)
                partial = target.with_name(target.name+'.'+uuid.uuid4().hex+'.partial')
                try:
                    shutil.copyfile(source, partial)
                    partial.replace(target)
                finally:
                    partial.unlink(missing_ok=True)
                return target.relative_to(root).as_posix()
    raise ValueError('Chưa tìm thấy font tiếng Việt trên máy. Thêm font TTF/OTF hỗ trợ tiếng Việt vào thư viện.')
