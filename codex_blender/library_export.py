"""Export independent copies of modeled screenplay elements into the asset library."""
import json
from pathlib import Path
import re

import bpy
from mathutils import Vector

from geometry import descendants


def export_elements(scene, shot, authored, output, assets, seen):
    exported = []
    for element in shot.get('elements', []):
        if (element['construction'] in {'image', 'overlay'} or element['id'] in seen
                or not (shot.get('export_assets') or element.get('reusable'))):
            continue
        binding = next((item for item in shot.get('element_bindings', [])
                        if item['element_id'] == element['id']), None)
        if not binding:
            continue
        roots = [obj['name'] for obj in shot['objects'] if obj['name'].split('__R', 1)[0] in binding['objects']]
        names = descendants(shot['objects'], roots)
        if not shot.get('export_assets') and any(obj['kind'] in {'model', 'image'} or obj['keyframes']
                                                for obj in shot['objects'] if obj['name'] in names):
            continue
        selected = {authored[name] for name in names}
        selected |= {child for obj in list(selected) for child in obj.children_recursive}
        # Keep skeleton dependencies so character GLBs remain rigged on reuse.
        selected |= {mod.object for obj in list(selected) for mod in obj.modifiers
                     if mod.type == 'ARMATURE' and mod.object is not None}
        for obj in list(selected):
            parent = obj.parent
            while parent is not None:
                selected.add(parent)
                parent = parent.parent
        geometry = [obj for obj in selected if obj.type in {'MESH','FONT','CURVE'}]
        if not geometry:
            continue
        scene.frame_set(1)
        bpy.context.view_layer.update()
        points = [obj.matrix_world @ Vector(corner) for obj in geometry for corner in obj.bound_box]
        lo = Vector(tuple(min(point[i] for point in points) for i in range(3)))
        hi = Vector(tuple(max(point[i] for point in points) for i in range(3)))
        origin = Vector(((lo.x+hi.x)/2, (lo.y+hi.y)/2, lo.z))
        temporary = bpy.data.scenes.new('AssetExport')
        copies = {}
        folder = assets/'generated'/('video-'+re.sub(r'[^A-Za-z0-9_-]', '_', output.name))
        folder.mkdir(parents=True, exist_ok=True)
        path = folder/(element['id']+'.glb')
        partial = path.with_suffix('.partial.glb')
        try:
            for obj in selected:
                copy = obj.copy()
                copy.animation_data_clear()
                temporary.collection.objects.link(copy)
                copies[obj] = copy
            for obj, copy in copies.items():
                world = obj.matrix_world.copy()
                copy.parent = copies.get(obj.parent)
                copy.matrix_world = world
                if copy.parent is None:
                    copy.location -= origin
                copy.hide_render = False
                for mod in copy.modifiers:
                    if mod.type == 'ARMATURE' and mod.object in copies:
                        mod.object = copies[mod.object]
            bpy.context.window.scene = temporary
            bpy.context.view_layer.update()
            for copy in copies.values():
                if copy.type in {'FONT','CURVE'}:
                    bpy.ops.object.select_all(action='DESELECT')
                    copy.select_set(True)
                    bpy.context.view_layer.objects.active = copy
                    bpy.ops.object.convert(target='MESH')
            bpy.ops.object.select_all(action='SELECT')
            bpy.context.view_layer.objects.active = copies[geometry[0]]
            bpy.ops.export_scene.gltf(filepath=str(partial), export_format='GLB',
                                      use_selection=True, export_animations=False, export_skins=True)
            partial.replace(path)
            meta = {'name':element['label'], 'description':element['appearance'],
                    'source':'blender', 'tags':['video-generated'], 'preview':None}
            path.with_suffix('.asset.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
            exported.append({'element':element['id'], 'path':path.relative_to(assets).as_posix()})
            seen.add(element['id'])
        finally:
            bpy.context.window.scene = scene
            for copy in copies.values():
                bpy.data.objects.remove(copy, do_unlink=True)
            bpy.data.scenes.remove(temporary)
            partial.unlink(missing_ok=True)
    return exported
