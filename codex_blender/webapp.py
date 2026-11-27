"""Loopback-only local web UI. No cloud hosting or API key storage."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .config import ROOT, OUTPUTS, assets_dir, asset_path, blender_command
from .models import SceneSpec
from .jobs import status, job_path
from . import studio, library
from .audio import VOICES, synthesize


class LocalRequests(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("x-studio-request") != "1":
                return JSONResponse({"error": "Yêu cầu không hợp lệ"}, status_code=403)
            origin = request.headers.get("origin")
            if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
                return JSONResponse({"error": "Chỉ chấp nhận giao diện trên máy này"}, status_code=403)
            try:
                if int(request.headers.get("content-length", 0)) > 210*1024*1024:
                    return JSONResponse({"error": "File quá lớn (tối đa 200 MB)"}, status_code=413)
            except ValueError:
                return JSONResponse({"error": "Content-Length không hợp lệ"}, status_code=400)
        try:
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response
        except (ValueError, OSError, RuntimeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)


async def error_handler(request, exc):
    return JSONResponse({"error": str(exc)}, status_code=400)


async def bootstrap(request):
    try:
        command, error = blender_command(), None
    except Exception as exc:
        command, error = None, str(exc)
    return JSONResponse({"application": "frame-studio", "settings": library.settings(), "assets": library.catalog(), "projects": studio.projects(),
                         "voices": VOICES, "blender_ready": bool(command), "blender_error": error,
                         "codex_available": bool(shutil.which("codex.cmd" if os.name=="nt" else "codex"))})


async def list_library(request):
    return JSONResponse({"assets": library.catalog(), "settings": library.settings()})


async def project_collection(request):
    if request.method == "GET":
        return JSONResponse(studio.projects())
    body = await request.json()
    template = body.get("template")
    if template in {"product", "elevator"}:
        name = "product.json" if template == "product" else "elevator-opening-5s.json"
        scene = SceneSpec.model_validate_json((ROOT/"examples"/name).read_text(encoding="utf-8"))
        draft = studio.Draft(title=scene.title, prompt=scene.prompt, script=scene.content, scene=scene,
                             duration=scene.duration, fps=scene.fps, width=scene.width, height=scene.height,
                             font=scene.font, music=scene.audio)
    else:
        draft = studio.Draft.model_validate(body.get("draft", {}))
    return JSONResponse(studio.create_project(draft),status_code=201)


async def project_detail(request):
    pid = request.path_params["pid"]
    if request.method == "GET":
        return JSONResponse(studio.read_project(pid))
    project = studio.read_project(pid)
    studio.ensure_idle(project)
    draft = studio.Draft.model_validate(await request.json())
    return JSONResponse(studio.save_project(pid, draft=draft.model_dump(mode="json"), error=None))


async def plan(request):
    body = await request.json()
    return JSONResponse(studio.start_plan(request.path_params["pid"], auto_render=body.get("auto_render") is True))


async def render(request):
    mode = (await request.json()).get("mode", "preview")
    if mode not in {"preview","video"}:
        raise ValueError("Chế độ render không hợp lệ")
    return JSONResponse(studio.render_project(request.path_params["pid"], mode))


async def export(request):
    body = await request.json()
    if not isinstance(body.get("names"),list) or len(body["names"]) > 150:
        raise ValueError("Danh sách đối tượng không hợp lệ")
    return JSONResponse(studio.export_asset(request.path_params["pid"], body["job_id"], str(body.get("name","")),
                                           body["names"], str(body.get("description",""))[:3000],
                                           [str(t)[:50] for t in body.get("tags",[])][:20]))


async def retry_render(request):
    return JSONResponse(studio.retry_render(request.path_params["pid"]))


async def control_render(request):
    return JSONResponse(studio.control_render(request.path_params["pid"], request.path_params["action"]))


async def voice_preview(request):
    body = await request.json()
    root = assets_dir()
    folder = root / "voices"
    folder.mkdir(parents=True,exist_ok=True)
    output = folder / f"preview-{uuid.uuid4().hex}.mp3"
    try:
        await synthesize(str(body.get("text", "Xin chào! Đây là giọng đọc cho video của bạn."))[:300],
                         body.get("voice", VOICES[0]["id"]), int(body.get("rate",0)),output)
    except Exception as exc:
        raise RuntimeError("Dịch vụ voice online chưa trả về âm thanh: "+str(exc)+". Bạn vẫn có thể tải file voice có sẵn.") from exc
    return JSONResponse({"path": output.relative_to(root).as_posix()})


async def uploads(request):
    async with request.form(max_files=1, max_fields=5, max_part_size=200*1024*1024) as form:
        file = form.get("file")
        if not file or not hasattr(file,"filename"):
            raise ValueError("Chọn một file để tải lên")
        root, path = library.upload_path(file.filename, form.get("category", "images"))
        count = 0
        try:
            with path.open("xb") as out:
                while chunk := await file.read(1024*1024):
                    count += len(chunk)
                    if count > 200*1024*1024:
                        raise ValueError("File vượt quá 200 MB")
                    out.write(chunk)
            if not count:
                raise ValueError("File rỗng")
        except Exception:
            path.unlink(missing_ok=True)
            raise
    return JSONResponse({"path":path.relative_to(root).as_posix(),"assets":library.catalog(root)})


async def asset_file(request):
    path = asset_path(request.query_params.get("path", ""))
    if path.suffix.lower() not in library.KINDS:
        raise ValueError("Không thể mở loại file này")
    return FileResponse(path)


async def configure(request):
    return JSONResponse(library.set_directory((await request.json())["assets_directory"]))


def pick_folder():
    # Opens only when the user clicks the folder picker; never at server startup.
    program = "import tkinter as t;from tkinter import filedialog;r=t.Tk();r.withdraw();r.attributes('-topmost',True);print(filedialog.askdirectory(title='Chọn thư mục assets cố định'));r.destroy()"
    result = subprocess.run([sys.executable,"-X","utf8","-c",program],capture_output=True,text=True,encoding="utf-8",timeout=180)
    if result.returncode:
        raise RuntimeError("Không mở được hộp chọn thư mục. Hãy dán đường dẫn thư mục vào ô cài đặt.")
    return result.stdout.strip()


async def folder_picker(request):
    return JSONResponse({"path": await run_in_threadpool(pick_folder)})


async def job_detail(request):
    return JSONResponse(status(request.path_params["jid"]))


async def job_artifact(request):
    name = request.path_params["name"]
    if name not in {"preview.png","scene.blend","scene.json","video.mp4","render.log","ngoi-nha-10-tang-5s.mp4"}:
        raise ValueError("File kết quả không hợp lệ")
    path = job_path(request.path_params["jid"])/name
    if not path.is_file():
        return JSONResponse({"error":"File chưa sẵn sàng"},status_code=404)
    return FileResponse(path,filename=name if request.query_params.get("download") else None)


async def history(request):
    result=[]
    for p in sorted(OUTPUTS.glob("*/status.json"),key=lambda p:p.stat().st_mtime,reverse=True)[:100]:
        try:
            result.append(status(p.parent.name))
        except (ValueError,OSError):
            pass
    return JSONResponse(result)


async def import_job(request):
    jid=(await request.json())["job_id"]
    scene=SceneSpec.model_validate_json((job_path(jid)/"scene.json").read_text(encoding="utf-8"))
    project=studio.create_project(studio.Draft(title=scene.title, prompt=scene.prompt,script=scene.content,
        duration=scene.duration,fps=scene.fps,width=scene.width,height=scene.height,scene=scene,font=scene.font,
        music=scene.music or scene.audio,voice_mode="upload" if scene.voice_audio else "none",voice_file=scene.voice_audio))
    return JSONResponse(studio.save_project(project["id"],current_job=jid,jobs=[jid]))


@asynccontextmanager
async def lifespan(app):
    for p in (studio.DATA / "projects").glob("*/project.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("state") in {"planning", "preparing_audio", "exporting"}:
            studio.save_project(p.parent.name, state="error", error="Ứng dụng đã khởi động lại trước khi tác vụ hoàn tất. Bạn có thể chạy lại.")
    yield


routes=[Route("/api/bootstrap",bootstrap),Route("/api/library",list_library),Route("/api/projects",project_collection,methods=["GET","POST"]),
    Route("/api/projects/{pid}/control/{action}",control_render,methods=["POST"]),
    Route("/api/projects/{pid}",project_detail,methods=["GET","PUT"]),Route("/api/projects/{pid}/plan",plan,methods=["POST"]),
    Route("/api/projects/{pid}/render",render,methods=["POST"]),Route("/api/projects/{pid}/retry",retry_render,methods=["POST"]),Route("/api/projects/{pid}/export",export,methods=["POST"]),
    Route("/api/voice-preview",voice_preview,methods=["POST"]),Route("/api/uploads",uploads,methods=["POST"]),
    Route("/api/assets/file",asset_file),Route("/api/settings",configure,methods=["POST"]),Route("/api/folder-picker",folder_picker,methods=["POST"]),
    Route("/api/jobs",history),Route("/api/jobs/{jid}",job_detail),Route("/api/jobs/{jid}/{name}",job_artifact),
    Route("/api/import-job",import_job,methods=["POST"]),Mount("/",StaticFiles(directory=Path(__file__).parent/"web",html=True),name="web")]
app=Starlette(routes=routes,lifespan=lifespan,exception_handlers={ValueError:error_handler,OSError:error_handler,RuntimeError:error_handler})
app.add_middleware(LocalRequests)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=["localhost","127.0.0.1","testserver","[::1]"])


def main(port=8765):
    import uvicorn
    uvicorn.run(app,host="127.0.0.1",port=port)


if __name__=="__main__":
    main()
