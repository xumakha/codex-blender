"""Add the supplied Vietnamese opening caption and verify the final 5 second MP4."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import imageio_ffmpeg
from codex_blender.jobs import status, job_path

job_id = sys.argv[1]
preview_only = "--preview-only" in sys.argv
info = status(job_id)
if info["state"] != "completed" and not preview_only:
    raise RuntimeError(f"Render has not completed: {info['state']}")
path = job_path(job_id)
for filename, text in (("title-1.txt", "MỘT NGÔI NHÀ"), ("title-2.txt", "10 TẦNG"),
                       ("caption-1.txt", "Giả sử bạn vừa xây được"), ("caption-2.txt", "một tòa nhà cao 10 tầng.")):
    (path / filename).write_text(text, encoding="utf-8")
shutil.copyfile(Path("assets/sample-arial-bold.ttf"), path / "font.ttf")
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
filters = ",".join(
    f"drawtext=fontfile=font.ttf:textfile={file}:fontsize={size}:fontcolor={color}:"
    f"borderw={border}:bordercolor=0x242424:x=(w-text_w)/2:y={y}"
    for file, size, color, border, y in (
        ("title-1.txt", 32, "0x294A42", 0, 100),
        ("title-2.txt", 48, "0x294A42", 0, 146),
        ("caption-1.txt", 24, "white", 2, 800),
        ("caption-2.txt", 24, "white", 2, 834)))
output = "ngoi-nha-10-tang-5s.mp4"
if preview_only:
    subprocess.run([ffmpeg,"-y","-i","preview.png","-vf",filters,"-frames:v","1","sample-preview.png"],cwd=path,check=True,capture_output=True)
    print(path / "sample-preview.png")
    sys.exit(0)
subprocess.run([ffmpeg,"-y","-i","video.mp4","-vf",filters,"-c:v","libx264","-crf","18",
                "-preset","medium","-c:a","copy","-movflags","+faststart",output],cwd=path,check=True,capture_output=True)
subprocess.run([ffmpeg,"-y","-ss","2.5","-i",output,"-frames:v","1","sample-preview.png"],cwd=path,check=True,capture_output=True)
decoded = subprocess.run([ffmpeg,"-hide_banner","-i",output,"-f","null","-"],cwd=path,capture_output=True,text=True)
if decoded.returncode:
    raise RuntimeError(decoded.stderr)
if "Audio: aac" not in decoded.stderr or "540x960" not in decoded.stderr or "00:00:05.00" not in decoded.stderr:
    raise RuntimeError(f"Unexpected media properties: {decoded.stderr}")
print(json.dumps({"video":str(path/output),"preview":str(path/"sample-preview.png"),"seconds":5,"resolution":"540x960","fps":24,"frames":120,"audio":"original synthesized chime, AAC", "voiceover":False},ensure_ascii=False,indent=2))
