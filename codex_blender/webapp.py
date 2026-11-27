"""Loopback-only local web UI. No cloud hosting or API key storage."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import logging
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .config import ROOT, OUTPUTS, assets_dir, asset_path, blender_command, codex_command, source_revision
from .models import SceneSpec
from .jobs import status, job_path
from . import studio, library
from .audio import VOICES, voice_options, synthesize

SERVER_REVISION = source_revision()
LOGGER = logging.getLogger(__name__)


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
            response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api/') else 'no-cache'
            return response
        except (ValueError, OSError, RuntimeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception:
            request_id = uuid.uuid4().hex[:12]
            LOGGER.exception('Studio request failed: %s %s [%s]',request.method,request.url.path,request_id)
            return JSONResponse({'error':f'Studio gặp lỗi khi xử lý yêu cầu. Mã tra cứu: {request_id}. Xem studio-data/server.log.',
                                 'request_id':request_id},status_code=500)


async def error_handler(request, exc):
    return JSONResponse({"error": str(exc)}, status_code=400)


async def http_error_handler(request, exc):
    if request.url.path.startswith('/api/'):
        message = 'API không có trong server đang chạy. Chạy lại start-studio.cmd để cập nhật Studio.' if exc.status_code==404 else f'Yêu cầu API không được hỗ trợ (HTTP {exc.status_code}).'
        return JSONResponse({'error':message},status_code=exc.status_code)
    return JSONResponse({'error':str(exc.detail)},status_code=exc.status_code)


async def bootstrap(request):
    try:
        codex_available = bool(codex_command())
    except RuntimeError:
        codex_available = False
    try:
        command, error = blender_command(), None
    except Exception as exc:
        command, error = None, str(exc)
    return JSONResponse({"application": "frame-studio", "server_revision": SERVER_REVISION, "settings": library.settings(), "assets": library.catalog(), "projects": studio.projects(),
                         "voices": voice_options(), "blender_ready": bool(command), "blender_error": error,
                         "codex_available": codex_available})


async def list_library(request):
    return JSONResponse({"assets": library.catalog(), "settings": library.settings()})


async def asset_generations(request):
    from . import assetgen
    if request.method == 'POST':
        try:
            draft = assetgen.AssetRequest.model_validate(await request.json())
        except ValueError:
            raise ValueError('Nhập tên, ảnh PNG/JPG và mô tả tối đa 10000 ký tự. Chế độ nhiều asset cần đúng 1 ảnh; tối đa 40 món.') from None
        return JSONResponse(assetgen.start(draft),status_code=202)
    return JSONResponse(assetgen.collection())


async def asset_generation_detail(request):
    from . import assetgen
    return JSONResponse(assetgen.public(request.path_params['pid']))


async def asset_generation_artifact(request):
    from . import assetgen
    name = request.path_params['name']
    path = assetgen.artifact(request.path_params['pid'],name,request.path_params.get('item_id'))
    return FileResponse(path,filename=name if request.query_params.get('download') else None)


async def elevenlabs_credentials(request):
    from . import credentials
    if request.method == 'POST':
        return JSONResponse(credentials.save_elevenlabs((await request.json()).get('api_key')))
    if request.method == 'DELETE':
        return JSONResponse(credentials.delete_elevenlabs())
    return JSONResponse(credentials.status())


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
    import hashlib
    body = await request.json()
    root = assets_dir()
    folder = root / "voices"
    folder.mkdir(parents=True,exist_ok=True)
    text=str(body.get('text','Xin chào! Đây là giọng đọc cho video của bạn.'))[:300]
    voice=body.get('voice',VOICES[0]['id'])
    rate=int(body.get('rate',0))
    selected=next((item for item in voice_options() if item['id']==voice),None)
    edge=selected is not None and not selected.get('provider')
    digest=hashlib.sha256(json.dumps([voice,rate,text],ensure_ascii=False).encode('utf-8')).hexdigest()[:32]
    output = folder / (f'preview-edge-{digest}.mp3' if edge else f'preview-{uuid.uuid4().hex}.mp3')
    if edge and output.is_file() and output.stat().st_size:
        return JSONResponse({'path':output.relative_to(root).as_posix()})
    try:
        await synthesize(text,voice,rate,output)
    except Exception as exc:
        raise RuntimeError("Chưa tạo được giọng đọc: "+str(exc).rstrip('. ')+". Bạn vẫn có thể tải file voice có sẵn.") from exc
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
            extra = {'asset_stage':'failed'} if data.get('kind') == 'asset-generation' else {}
            studio.save_project(p.parent.name, state="error", error="Ứng dụng đã khởi động lại trước khi tác vụ hoàn tất. Bạn có thể chạy lại.", **extra)
    yield


routes=[Route("/api/bootstrap",bootstrap),Route("/api/library",list_library),Route("/api/projects",project_collection,methods=["GET","POST"]),
    Route('/api/asset-generations',asset_generations,methods=['GET','POST']),
    Route('/api/asset-generations/{pid}',asset_generation_detail),
    Route('/api/asset-generations/{pid}/files/{name}',asset_generation_artifact),
    Route('/api/asset-generations/{pid}/items/{item_id}/files/{name}',asset_generation_artifact),
    Route("/api/projects/{pid}/control/{action}",control_render,methods=["POST"]),
    Route("/api/projects/{pid}",project_detail,methods=["GET","PUT"]),Route("/api/projects/{pid}/plan",plan,methods=["POST"]),
    Route("/api/projects/{pid}/render",render,methods=["POST"]),Route("/api/projects/{pid}/retry",retry_render,methods=["POST"]),Route("/api/projects/{pid}/export",export,methods=["POST"]),
    Route("/api/voice-preview",voice_preview,methods=["POST"]),Route("/api/uploads",uploads,methods=["POST"]),
    Route("/api/credentials/elevenlabs",elevenlabs_credentials,methods=["GET","POST","DELETE"]),
    Route("/api/assets/file",asset_file),Route("/api/settings",configure,methods=["POST"]),Route("/api/folder-picker",folder_picker,methods=["POST"]),
    Route("/api/jobs",history),Route("/api/jobs/{jid}",job_detail),Route("/api/jobs/{jid}/{name}",job_artifact),
    Route("/api/import-job",import_job,methods=["POST"]),
    Mount("/",StaticFiles(directory=Path(__file__).parent/"web",html=True),name="web")]
app=Starlette(routes=routes,lifespan=lifespan,exception_handlers={ValueError:error_handler,OSError:error_handler,RuntimeError:error_handler,HTTPException:http_error_handler})
app.add_middleware(LocalRequests)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=["localhost","127.0.0.1","testserver","[::1]"])


def main(port=8765):
    import uvicorn
    uvicorn.run(app,host="127.0.0.1",port=port)


if __name__=="__main__":
    main()
