"""Image-guided native Blender assets, with persistent progress and GLB export."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from typing import Literal

from pydantic import Field, field_validator, model_validator
from . import studio
from .config import ROOT, assets_dir, asset_path, blender_command
from .director import call_planner
from .jobs import submit, status, job_path, write_json
from .models import Model, ShotDesign, SceneSpec
from .planning import object_names


class AssetRequest(Model):
    name: str = Field(min_length=1, max_length=100)
    prompt: str = Field(default='', max_length=10000)
    references: list[str] = Field(min_length=1, max_length=4)
    style: str = Field(default='3D mềm, rõ hình khối, giữ màu sắc và tỷ lệ trong ảnh', max_length=3000)
    mode: Literal['single','multiple'] = 'single'
    max_assets: int = Field(default=20,ge=1,le=40)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError('Nhập tên asset')
        return value.strip()

    @model_validator(mode='after')
    def batch_image(self):
        if self.mode=='multiple' and len(self.references)!=1:
            raise ValueError('Chế độ nhiều asset cần đúng một ảnh chứa nhiều đồ vật.')
        return self


class AssetDesign(ShotDesign):
    description: str = Field(default='', max_length=3000)
    unsupported: list[str] = Field(default_factory=list, max_length=20)


class InventoryItem(Model):
    id: str = Field(pattern=r'^[a-z][a-z0-9-]{0,39}$')
    name: str = Field(min_length=1,max_length=100)
    prompt: str = Field(min_length=1,max_length=4000)


class AssetInventory(Model):
    items: list[InventoryItem] = Field(min_length=1,max_length=40)
    notes: str = Field(default='',max_length=2000)


INVENTORY_INSTRUCTIONS = '''Inspect the attached image and identify separate reusable 3D objects.
This image may be an asset sheet with MANY DIFFERENT subjects, NOT multiple views of one subject.
Return at most max_assets items, prioritizing objects requested in the user's prompt. With no selection,
choose the most distinct visible objects up to the limit. Do not invent objects absent from the image.
Each item is ONE complete object (e.g. bicycle, chair, tree), not its attached wheels, legs or leaves.
Include standalone components only if separately illustrated as reusable modules. Ignore labels, swatches,
decorative frames and background. De-duplicate repeated views/closeups of the same object and skip an
assembled scene when its component objects are already listed. Do not collapse unrelated objects together.
id must be a unique short lowercase ASCII slug; name must be a specific Vietnamese name.
prompt must identify the object's LOCATION in the source image and describe its silhouette, proportions,
visible parts, colors and materials, sufficient to distinguish it from every other object on this sheet.
notes briefly states any limitation, ambiguous object, or items omitted due to the user limit, in Vietnamese.
'''


INSTRUCTIONS = '''Build ONE reusable static 3D asset from the attached reference images.
Identify the main subject, silhouette, colors, proportions and distinctive parts in the images.
User prompt clarifies the subject to extract when an image has multiple objects. If prompt is empty,
use the most prominent subject. Multiple images show the SAME asset from different views.
Reconstruct a recognizable, stylized interpretation using native Blender primitives and parent groups.
Infer hidden sides conservatively and keep the visible design consistent. This is not photogrammetry.
Return all required schema fields. No action bindings or element bindings are needed: use empty lists.
Use only cube/sphere/cylinder/cone/torus/plane/empty; asset=null, keyframes=[] for every object.
NEVER place a reference image on a plane, import a model, or include scripts/code in output.
Separate meaningful parts. Do not replace the entire subject with one box. Exclude the photo background,
caption text, scenery, stage and decorative frame. Do not create a ground plane as an asset part.
Center the subject at world origin with its bottom at Z=0. Keep a useful scale in meters.
Use a neutral background and a camera showing the whole object with margin. No animation/audio/text.
description briefly describes the reconstructed asset in Vietnamese for future reuse.
unsupported lists requirements that cannot be represented; otherwise [].
Z up; rotations are degrees. Cube side=2, sphere radius=1, cylinder depth=2, plane side=2.
Use nonuniform scale for proportions. Empty group roots must have explicit location [0,0,0].
Parented coordinates are local. repeat={count,offset,rotation} repeats the object AND its children.
Use distinct short ASCII identifiers (max 40 characters). Maximum 150 objects, no parent cycles.
'''


def validate_design(design):
    if design.unsupported:
        raise ValueError('Chưa dựng được yêu cầu: '+ '; '.join(design.unsupported))
    if any(o.kind in {'image','model','text'} or o.asset or o.keyframes for o in design.objects):
        raise ValueError('Asset phải là hình học Blender tĩnh, không dùng ảnh thay mô hình')
    if any(len(o.name)>40 for o in design.objects):
        raise ValueError('Tên bộ phận tối đa 40 ký tự để giữ đúng tên khi xuất GLB')
    if not any(o.kind != 'empty' and o.visible and o.opacity > 0 for o in design.objects):
        raise ValueError('Asset cần có hình học nhìn thấy được')
    make_scene(design, 'Asset')  # Validate names, hierarchy, repetitions and camera.


def make_scene(design, name):
    # Ground/lights are staging only, excluded from the exported object names.
    return SceneSpec(title=name, duration=1, fps=1, width=512, height=512, samples=16,
                     objects=design.objects, camera=design.camera, background=design.background, floor=design.floor)


def public(pid):
    project = studio.read_project(pid)
    if project.get('kind') != 'asset-generation':
        raise ValueError('Không tìm thấy tác vụ tạo asset')
    return {'id':pid, 'name':project['draft']['title'], 'state':project['state'],
            'stage':project.get('asset_stage','planning'), 'error':project.get('error'),
            'updated':project['updated'], 'references':project['draft']['references'],
            'prompt':project['draft']['prompt'], 'result':project.get('asset_result'),
            'style':project['draft']['style'],
            'mode':project.get('asset_mode','single'), 'max_assets':project.get('asset_limit',20),
            'items':project.get('asset_items',[]), 'notes':project.get('asset_notes',''),
            'current_item':project.get('asset_current_item'),
            'render_state':project.get('job',{}).get('state')}


def collection():
    values = []
    for path in (studio.DATA/'projects').glob('*/project.json'):
        try:
            if json.loads(path.read_text(encoding='utf-8')).get('kind') == 'asset-generation':
                values.append(public(path.parent.name))
        except (ValueError, OSError):
            continue
    return sorted(values,key=lambda x:x['updated'],reverse=True)


def start(request):
    root = assets_dir()
    for name in request.references:
        if asset_path(name,root).suffix.lower() not in {'.png','.jpg','.jpeg'}:
            raise ValueError('Ảnh tham khảo cần là PNG hoặc JPG')
    blender_command()
    with studio.LOCK:
        if any(p['state'] in {'planning','exporting'} for p in collection()):
            raise ValueError('Đang tạo một asset. Chờ tác vụ hiện tại hoàn tất.')
        draft = studio.Draft(title=request.name,prompt=request.prompt,style=request.style,
                             references=request.references,voice_mode='none',width=512,height=512)
        project = studio.create_project(draft)
        pid = project['id']
        studio.save_project(pid,kind='asset-generation',state='planning',asset_stage='inventory' if request.mode=='multiple' else 'planning',
                            asset_root=str(root),asset_mode=request.mode,asset_limit=request.max_assets,asset_items=[])
        studio.POOL.submit(run,pid,draft,root)
    return public(pid)


def build_one(pid,draft,root,planner_stage='asset',on_stage=None):
    def progress(stage):
        studio.save_project(pid,state='exporting' if stage=='exporting' else 'planning',asset_stage=stage)
        if on_stage:on_stage(stage)
    progress('planning')
    design = call_planner(pid,draft,root,AssetDesign,
        {'name':draft.title,'prompt':draft.prompt,'style':draft.style,'reference_count':len(draft.references)},
        INSTRUCTIONS,planner_stage,validate_design)
    validate_design(design)
    scene = make_scene(design,draft.title)
    job = submit(scene,'preview',root)
    latest=studio.read_project(pid)
    studio.save_project(pid,current_job=job['id'],jobs=latest['jobs']+[job['id']])
    progress('rendering')
    deadline = time.monotonic()+900
    while True:
        info = status(job['id'])
        if info['state'] == 'completed':
            break
        if info['state'] == 'failed':
            raise RuntimeError(info.get('error','Blender không dựng được asset'))
        if time.monotonic() >= deadline:
            raise RuntimeError('Blender render quá lâu; xem render.log của tác vụ')
        time.sleep(1)
    progress('exporting')
    destination = root/'generated'/f'{uuid.uuid4().hex}.glb'
    destination.parent.mkdir(parents=True,exist_ok=True)
    options = studio.project_path(pid)/(planner_stage+'-export.json')
    write_json(options,{'blend':info['artifacts']['scene.blend'],'output':str(destination),
                        'names':[name for name,_ in object_names(scene.model_dump(mode='json'))]})
    env = os.environ.copy()
    runtime = studio.project_path(pid)/'blender-user'
    runtime.mkdir(exist_ok=True)
    env['BLENDER_USER_RESOURCES'] = str(runtime)
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    with (studio.project_path(pid)/'export.log').open('a',encoding='utf-8') as log:
        subprocess.run(blender_command()+[str(ROOT/'codex_blender/export_asset.py'),'--',str(options)],
                       cwd=ROOT,env=env,stdout=log,stderr=log,timeout=300,check=True,creationflags=flags)
    if not destination.is_file() or destination.stat().st_size < 12 or not destination.with_suffix('.png').is_file():
        raise RuntimeError('Blender chưa tạo đủ GLB và ảnh xem trước')
    relative = destination.relative_to(root).as_posix()
    write_json(destination.with_suffix('.asset.json'),{'name':draft.title,'description':design.description or draft.prompt,
        'tags':['image-guided','3d'],'source':'blender','preview':destination.with_suffix('.png').relative_to(root).as_posix()})
    return {'path':relative,'name':draft.title,'description':design.description,'root':str(root),'job_id':job['id']}


def run_multiple(pid,draft,root):
    project=studio.read_project(pid)
    limit=project.get('asset_limit',20)
    def validate_inventory(inventory):
        if len(inventory.items)>limit:
            raise ValueError(f'Chỉ tạo tối đa {limit} asset theo lựa chọn.')
        if len({item.id for item in inventory.items})!=len(inventory.items) or len({item.name.strip().casefold() for item in inventory.items})!=len(inventory.items):
            raise ValueError('Mỗi đồ vật cần ID và tên riêng, không lặp các góc nhìn.')
        if any(not item.name.strip() or not item.prompt.strip() for item in inventory.items):
            raise ValueError('Mỗi asset cần tên và mô tả nhận diện trong ảnh.')
    inventory=call_planner(pid,draft,root,AssetInventory,
        {'prompt':draft.prompt,'collection_name':draft.title,'style':draft.style,'max_assets':limit},
        INVENTORY_INSTRUCTIONS,'inventory',validate_inventory)
    validate_inventory(inventory)
    items=[{**item.model_dump(),'state':'pending','stage':'pending','result':None,'error':None} for item in inventory.items]
    studio.save_project(pid,asset_items=items,asset_notes=inventory.notes)
    for item in items:
        studio.save_project(pid,asset_current_item=item['name'],current_job=None,error=None)
        def update(stage):
            item.update(state='running',stage=stage)
            studio.save_project(pid,asset_items=items)
        try:
            selected=draft.model_copy(deep=True)
            selected.title=item['name']
            selected.prompt=f"Build ONLY this object from the full reference image: {item['prompt']}\nCollection guidance: {draft.prompt}\nIgnore every other object on the sheet."
            result=build_one(pid,selected,root,planner_stage='item-'+item['id'],on_stage=update)
            item.update(state='completed',stage='completed',result=result,error=None)
        except Exception as exc:
            item.update(state='failed',stage='failed',error=str(exc))
        studio.save_project(pid,asset_items=items)
    completed=sum(item['state']=='completed' for item in items)
    failures=len(items)-completed
    studio.save_project(pid,state='ready' if completed else 'error',asset_stage='completed' if completed else 'failed',
                        current_job=None,asset_current_item=None,error=None if not failures else f'Đã lưu {completed}/{len(items)} asset; {failures} món chưa tạo được. Xem lỗi từng món bên dưới.')


def run(pid,draft,root):
    try:
        if studio.read_project(pid).get('asset_mode')=='multiple':
            run_multiple(pid,draft,root)
        else:
            result=build_one(pid,draft,root)
            studio.save_project(pid,state='ready',asset_stage='completed',error=None,
                                asset_result=result,last_saved_asset=str(root/result['path']))
    except Exception as exc:
        studio.save_project(pid,state='error',asset_stage='failed',error=str(exc))


def artifact(pid,name,item_id=None):
    public(pid)
    project = studio.read_project(pid)
    result=project.get('asset_result')
    if item_id:
        item=next((item for item in project.get('asset_items',[]) if item['id']==item_id),None)
        if not item or not item.get('result'):raise ValueError('Asset chưa hoàn tất hoặc không có trong tác vụ này')
        result=item['result']
    if name == 'preview.png' and result:
        return asset_path(str(Path(result['path']).with_suffix('.png')),Path(project['asset_root']))
    if name == 'model.glb' and result:
        return asset_path(result['path'],Path(project['asset_root']))
    job_id=result.get('job_id') if result else project.get('current_job')
    if name == 'scene.blend' and job_id:
        return job_path(job_id)/'scene.blend'
    if name in {'planning.log','export.log'}:
        path = studio.project_path(pid)/name
        if path.is_file():
            return path
    raise ValueError('File chưa có hoặc không hợp lệ')
