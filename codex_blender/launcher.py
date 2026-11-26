"""Start/reuse the local Studio server and open the browser on Windows."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser
from .config import DATA, ROOT

URL="http://127.0.0.1:8765"


def ready():
    try:
        with urllib.request.urlopen(URL+"/api/bootstrap",timeout=2) as response:
            return json.load(response).get("application")=="frame-studio"
    except (OSError, ValueError):
        return False


def main():
    DATA.mkdir(parents=True,exist_ok=True)
    if not ready():
        flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
        with (DATA/"server.log").open("a",encoding="utf-8") as log:
            proc=subprocess.Popen([sys.executable,"-m","codex_blender.cli","studio"],cwd=ROOT,stdin=subprocess.DEVNULL,
                                  stdout=log,stderr=log,creationflags=flags,start_new_session=os.name!="nt")
        (DATA/"server.pid").write_text(str(proc.pid),encoding="ascii")
        for _ in range(40):
            if ready():break
            if proc.poll() is not None:
                raise RuntimeError("Không khởi động được Studio. Xem studio-data/server.log; cổng 8765 có thể đang được dùng.")
            time.sleep(.25)
        else:raise RuntimeError("Studio chưa phản hồi. Xem studio-data/server.log")
    print("Frame Studio: "+URL)
    webbrowser.open(URL)


if __name__=="__main__":main()
