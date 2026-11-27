"""Build native Blender geometry and verify the saved prompt's requested timeline."""
import json
from pathlib import Path
import sys
import time

import imageio_ffmpeg
from codex_blender import studio
from codex_blender.config import assets_dir
from codex_blender.geometry import expand_objects
from codex_blender.models import VideoPlan
from codex_blender.planning import normalize_inventory, check_inventory, check_contract, prompt_contract, signature


def main():
    source_id=sys.argv[1] if len(sys.argv)>1 else 'e4dbee0117be4a52adbf5d494346c538'
    source=studio.read_project(source_id)
    draft=studio.Draft.model_validate(source['draft'])
    draft.scene=None;draft.source_signature=None
    draft.width,draft.height,draft.fps,draft.samples=360,640,12,4
    if '--resume-project' in sys.argv:
        project=source
        # Revalidate the previous real AI screenplay after a validation-only repair.
        path=studio.project_path(project['id'])
        for candidate in sorted(path.glob('screenplay-*.json'),key=lambda file:file.stat().st_mtime,reverse=True):
            if 'schema' in candidate.name:continue
            try:
                plan=normalize_inventory(VideoPlan.model_validate_json(candidate.read_text(encoding='utf-8')))
                check_contract(plan,prompt_contract(draft.prompt));check_inventory(plan,draft.prompt)
            except ValueError:continue
            cache=path/'compiled';cache.mkdir(exist_ok=True)
            (cache/f'{signature(draft)}-screenplay.json').write_text(plan.model_dump_json(indent=2),encoding='utf-8')
            break
    else:
        project=studio.create_project(draft)
    studio.save_project(project['id'],state='planning',error=None)
    print(json.dumps({'project':project['id'],'source_project':source_id,'prompt_characters':len(draft.prompt)},ensure_ascii=False),flush=True)
    studio.plan_scene(project['id'],draft,assets_dir(),auto_render=True)
    deadline=time.monotonic()+7200
    while time.monotonic()<deadline:
        project=studio.read_project(project['id'])
        job=project.get('job',{})
        if project['state']=='error' or job.get('state')=='failed':
            raise RuntimeError(project.get('error') or job.get('error'))
        if job.get('state')=='completed':break
        print(json.dumps({'state':project['state'],'render':job.get('state'),'frames':job.get('frames_rendered',0)}),flush=True)
        time.sleep(10)
    else:raise TimeoutError('Geometry render did not finish')
    scene=project['draft']['scene']
    contract=prompt_contract(draft.prompt)
    plan=VideoPlan.model_validate_json((studio.project_path(project['id'])/'screenplay.json').read_text(encoding='utf-8'))
    check_contract(plan,contract)
    assert scene['duration']==plan.duration
    assert [(shot['start'],shot['end']) for shot in scene['shots']]==[(shot.start,shot.end) for shot in plan.shots]
    assert all(obj['kind'] not in ('model','image') for shot in scene['shots'] for obj in shot['objects'])
    expanded=[expand_objects(shot['objects']) for shot in scene['shots']]
    frames,seconds=imageio_ffmpeg.count_frames_and_secs(job['artifacts']['video.mp4'])
    assert abs(seconds-scene['duration'])<=1/scene['fps']
    print(json.dumps({'passed':True,'project':project['id'],'job':job['id'],'video':job['artifacts']['video.mp4'],
        'frames':frames,'seconds':seconds,'geometry_parts':sum(len(parts) for parts in expanded),
        'elements':[element['label'] for shot in scene['shots'] for element in shot['elements']]},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
