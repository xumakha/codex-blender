"""Start/reuse the local Studio server and open the browser on Windows."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser
import psutil
from .config import DATA, ROOT, source_revision

URL="http://127.0.0.1:8765"


def server_info():
    try:
        with urllib.request.urlopen(URL+"/api/bootstrap",timeout=2) as response:
            value = json.load(response)
            return value if isinstance(value,dict) and value.get('application')=='frame-studio' else None
    except (OSError, ValueError):
        return None


def ready(revision=None):
    info = server_info()
    return bool(info) and info.get('server_revision') == (revision or source_revision())


def stop_stale_server():
    """Restart only this workspace's managed idle server; never kill a port owner."""
    for path in (DATA/'projects').glob('*/project.json'):
        project = json.loads(path.read_text(encoding='utf-8'))
        if project.get('state') in {'planning','preparing_audio','exporting'}:
            raise RuntimeError('Studio có bản cập nhật. Chờ tác vụ đang xử lý hoàn tất rồi chạy lại start-studio.cmd.')
    try:
        process = psutil.Process(int((DATA/'server.pid').read_text(encoding='ascii')))
        args = process.cmdline()
        if Path(process.cwd()).resolve()!=ROOT.resolve() or 'codex_blender.cli' not in args or 'studio' not in args:
            raise RuntimeError('Không xác minh được server cũ của workspace. Đóng server Studio cũ rồi chạy lại start-studio.cmd.')
        process.terminate()
        process.wait(timeout=10)
    except psutil.NoSuchProcess:
        return
    except (OSError, ValueError, psutil.AccessDenied, psutil.TimeoutExpired) as exc:
        raise RuntimeError('Chưa dừng được Studio cũ. Đóng server cũ rồi chạy lại start-studio.cmd.') from exc


def main():
    DATA.mkdir(parents=True,exist_ok=True)
    revision = source_revision()
    info = server_info()
    if info and info.get('server_revision') != revision:
        print('Updating Frame Studio server...')
        stop_stale_server()
    if not ready(revision):
        flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
        with (DATA/"server.log").open("a",encoding="utf-8") as log:
            proc=subprocess.Popen([sys.executable,"-m","codex_blender.cli","studio"],cwd=ROOT,stdin=subprocess.DEVNULL,
                                  stdout=log,stderr=log,creationflags=flags,start_new_session=os.name!="nt")
        (DATA/"server.pid").write_text(str(proc.pid),encoding="ascii")
        for _ in range(40):
            if ready(revision):break
            if proc.poll() is not None:
                raise RuntimeError("Không khởi động được Studio. Xem studio-data/server.log; cổng 8765 có thể đang được dùng.")
            time.sleep(.25)
        else:raise RuntimeError("Studio chưa phản hồi. Xem studio-data/server.log")
    print("Frame Studio: "+URL)
    webbrowser.open(URL)


if __name__=="__main__":main()
