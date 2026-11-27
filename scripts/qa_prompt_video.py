"""Live prompt -> screenplay -> animated shots -> timed Vietnamese speech -> MP4."""
import json
from pathlib import Path
import time
import imageio_ffmpeg

from codex_blender import studio
from codex_blender.config import assets_dir

PROMPT = """Tạo video thử gồm đúng 2 cảnh, thời lượng 6 giây, dọc 160x284, 4 FPS.
Phong cách 3D tối giản, camera đứng yên ở cả hai cảnh để thấy hành động rõ ràng.
CẢNH 1 — 00:00–00:03: Trong căn phòng màu xanh nhạt có sàn và hai bức tường,
một khối lập phương đỏ trượt từ bên trái sang bên phải. Camera không zoom.
Lời đọc: “Xin chào.” Giọng nam tiếng Việt, đọc từ 0.5 đến 2.5 giây.
CẢNH 2 — 00:03–00:06: Cắt sang căn phòng xanh lá nhạt có sàn và hai bức tường,
một quả cầu vàng bay từ gần mặt sàn lên cao. Camera không zoom.
Lời đọc: “Tạm biệt.” Giọng nam tiếng Việt, đọc từ 4 đến 5.5 giây.
Hiện phụ đề tiếng Việt đúng theo hai đoạn lời đọc, dùng sample-arial-bold.ttf.
Không nhạc, không hiệu ứng âm thanh, không chữ khác, không cần khẩu hình.
"""


def main():
    draft = studio.Draft(title='QA · Hai cảnh theo prompt', prompt=PROMPT, width=160, height=284, fps=4, samples=2)
    p = studio.create_project(draft)
    studio.save_project(p['id'], state='planning')
    print(json.dumps({'project':p['id'],'stage':'planning'}), flush=True)
    studio.plan_scene(p['id'], draft, assets_dir(), auto_render=True)
    deadline = time.monotonic()+360
    while time.monotonic()<deadline:
        p = studio.read_project(p['id'])
        job = p.get('job', {})
        if p['state']=='error' or job.get('state')=='failed':
            raise RuntimeError(p.get('error') or job.get('error'))
        if job.get('state')=='completed':
            break
        print(json.dumps({'state':p['state'],'job_state':job.get('state'),'frames':job.get('frames_rendered',0)}), flush=True)
        time.sleep(5)
    else:
        raise TimeoutError('Live render did not finish')
    scene=p['draft']['scene']
    assert len(scene['shots'])==2 and scene['duration']==6
    assert (scene['width'],scene['height'],scene['fps'])==(160,284,4)
    cues=[cue for shot in scene['shots'] for cue in shot['narration']]
    assert [cue['text'] for cue in cues]==['Xin chào.','Tạm biệt.']
    assert all(cue['audio'] for cue in json.loads(Path(job['artifacts']['scene.json']).read_text(encoding='utf-8'))['shots'][0]['narration'])
    frames,seconds=imageio_ffmpeg.count_frames_and_secs(job['artifacts']['video.mp4'])
    assert frames==24 and seconds==6,(frames,seconds)
    print(json.dumps({'passed':True,'project':p['id'],'job':job['id'],'video':job['artifacts']['video.mp4'],'frames':frames,'seconds':seconds},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
