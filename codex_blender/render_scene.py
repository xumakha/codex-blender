"""Executed by Blender (or optional bpy wheel), not imported by the MCP server."""
import json
import math
import fnmatch
from pathlib import Path
import sys
import time

# Blender also executes this file directly, outside the installed app's Python environment.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry import expand_objects, descendants
from mesh_program import build_mesh, validate_mesh
from pause_control import checkpoint
from render_artifacts import complete_png, complete_blend
from render_timing import record_frame, shot_review_frames
from rigging import build_rigs

import bpy
from mathutils import Vector, Matrix


def render_frames(scene, frames, offset=0):
    for frame in range(scene.frame_start, scene.frame_end + 1):
        target = frames / f"frame_{frame+offset:04d}.png"
        if complete_png(target):
            continue
        checkpoint(frames.parent)
        started = time.monotonic()
        scene.frame_set(frame)
        scene.render.filepath = str(target)
        bpy.ops.render.render(write_still=True)
        record_frame(frames.parent, time.monotonic() - started)


def rgba(hex_color):
    # Blender shaders take linear color values.
    srgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb) + (1,)


def material(name, color, metallic=0, roughness=0.4):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = rgba(color)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    return mat


def track(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def transform(obj, data):
    obj.location = data["location"]
    obj.rotation_euler = [math.radians(v) for v in data["rotation"]]
    obj.scale = data["scale"]


def animate(obj, data, fps, last):
    for prop in ("location", "rotation_euler", "scale"):
        obj.keyframe_insert(data_path=prop, frame=1)
    for key in sorted(data["keyframes"], key=lambda k: k["time"]):
        frame = min(last, 1 + round(key["time"] * fps))
        for source, dest in (("location", "location"), ("rotation", "rotation_euler"), ("scale", "scale")):
            if key[source] is not None:
                value = key[source]
                setattr(obj, dest, [math.radians(v) for v in value] if source == "rotation" else value)
                obj.keyframe_insert(data_path=dest, frame=frame)


def animate_visibility(data, authored, fps, last):
    lookup = {item['name']: item for item in data}
    roots = set(authored.values())
    for item in data:
        chain = [item]
        while chain[-1].get('parent'):
            chain.append(lookup[chain[-1]['parent']])
        times = {0} | {key['time'] for ancestor in chain for key in ancestor['keyframes'] if key.get('visible') is not None}
        obj = authored[item['name']]
        def owned(child):
            parent = child.parent
            while parent is not None and parent not in roots:
                parent = parent.parent
            return parent is obj
        targets = [obj] + [child for child in obj.children_recursive if child not in roots and owned(child)]
        for time in sorted(times):
            visible = True
            for ancestor in chain:
                state = ancestor.get('visible', True)
                for key in sorted(ancestor['keyframes'], key=lambda key: key['time']):
                    if key['time'] <= time and key.get('visible') is not None:
                        state = key['visible']
                visible = visible and state
            for target in targets:
                target.hide_render = not visible
                target.keyframe_insert(data_path='hide_render', frame=min(last,1+round(time*fps)))


def animate_opacity(data, authored, fps, last):
    lookup = {item['name']:item for item in data}
    roots = set(authored.values())
    def value_at(item, time):
        values = {0:item.get('opacity',1)}
        values.update({key['time']:key['opacity'] for key in item['keyframes'] if key.get('opacity') is not None})
        previous, value = 0, values[0]
        for point, following in sorted(values.items()):
            if time <= point:
                return value if point==previous else value+(following-value)*(time-previous)/(point-previous)
            previous, value = point, following
        return value
    for item in data:
        chain = [item]
        while chain[-1].get('parent'):
            chain.append(lookup[chain[-1]['parent']])
        if all(ancestor.get('opacity',1)==1 and not any(key.get('opacity') is not None for key in ancestor['keyframes']) for ancestor in chain):
            continue
        times = {0} | {key['time'] for ancestor in chain for key in ancestor['keyframes'] if key.get('opacity') is not None}
        obj = authored[item['name']]
        targets = [obj]
        for child in obj.children_recursive:
            parent = child.parent
            while parent is not None and parent not in roots:
                parent = parent.parent
            if child not in roots and parent is obj:
                targets.append(child)
        for target in targets:
            for slot in target.material_slots:
                mat = slot.material
                if not mat or not mat.use_nodes:
                    continue
                shader = mat.node_tree.nodes.get('Principled BSDF')
                if not shader:
                    continue
                for time in sorted(times):
                    shader.inputs['Alpha'].default_value = math.prod(value_at(ancestor,time) for ancestor in chain)
                    shader.inputs['Alpha'].keyframe_insert(data_path='default_value',frame=min(last,1+round(time*fps)))


def add_object(data, assets, font, mesh_cache=None):
    kind = data["kind"]
    if kind == 'empty':
        obj = bpy.data.objects.new(data['name'], None)
        bpy.context.collection.objects.link(obj)
        transform(obj, data)
        return obj
    ops = {"cube": bpy.ops.mesh.primitive_cube_add, "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
           "cylinder": bpy.ops.mesh.primitive_cylinder_add, "cone": bpy.ops.mesh.primitive_cone_add,
           "torus": bpy.ops.mesh.primitive_torus_add, "plane": bpy.ops.mesh.primitive_plane_add,
           "image": bpy.ops.mesh.primitive_plane_add, "text": bpy.ops.object.text_add}
    if kind == "model":
        before = set(bpy.context.scene.objects)
        bpy.ops.import_scene.gltf(filepath=str(assets / data["asset"]))
        imported = set(bpy.context.scene.objects) - before
        bpy.context.view_layer.update()
        selectors=data.get('asset_nodes',[])
        if selectors:
            chosen=[child for child in imported if child.type=='MESH' and any(
                fnmatch.fnmatchcase(child.name.casefold(),pattern.casefold()) or pattern.casefold() in child.name.casefold()
                for pattern in selectors)]
            if not chosen:raise ValueError('No mesh matches asset_nodes for '+data['name'])
            pivot=Matrix.Translation(-Vector(data.get('asset_pivot',(0,0,0))))
            for child in chosen:
                world=child.matrix_world.copy();child.parent=None;child.matrix_world=pivot@world
                # Extracted parts will receive their own rig; do not keep a dangling source armature.
                for modifier in list(child.modifiers):
                    if modifier.type=='ARMATURE':child.modifiers.remove(modifier)
                child.vertex_groups.clear()
            for child in imported-set(chosen):bpy.data.objects.remove(child,do_unlink=True)
            imported=set(chosen)
        obj = bpy.data.objects.new(data["name"], None)
        bpy.context.collection.objects.link(obj)
        for child in imported:
            if child.parent is None:
                child.parent = obj
        if data.get('recolor') is not None:
            mat=material(data['name']+' variant',data['recolor'],data['metallic'],data['roughness'])
            shader=mat.node_tree.nodes.get('Principled BSDF')
            shader.inputs['Transmission Weight'].default_value=data.get('transmission',0)
            shader.inputs['IOR'].default_value=1.33 if data.get('transmission',0) else 1.45
            for child in imported:
                if child.type=='MESH':child.data.materials.clear();child.data.materials.append(mat)
        transform(obj, data)
        return obj
    if kind == 'mesh':
        geometry = data['mesh']
        if geometry.get('program') is not None:
            program = geometry['program']
            if mesh_cache is None:
                mesh_cache = {}
            if program not in mesh_cache:
                mesh_cache[program] = build_mesh(program)
            vertices, faces = mesh_cache[program]
        else:
            vertices, faces = validate_mesh(geometry['vertices'], geometry['faces'])
        mesh = bpy.data.meshes.new(data['name'])
        mesh.from_pydata(vertices, [], faces)
        if mesh.validate() or not any(poly.area > 1e-10 for poly in mesh.polygons):
            raise ValueError(f"{data['name']}: invalid or degenerate mesh")
        obj = bpy.data.objects.new(data['name'], mesh)
        bpy.context.collection.objects.link(obj)
        for polygon in mesh.polygons:
            polygon.use_smooth = geometry['smooth']
        if geometry.get('mirror_x'):
            obj.modifiers.new('Mirror X', 'MIRROR')
        if geometry['subdivision']:
            modifier = obj.modifiers.new('Subdivision', 'SUBSURF')
            modifier.levels = modifier.render_levels = geometry['subdivision']
        if geometry['solidify']:
            modifier = obj.modifiers.new('Thickness', 'SOLIDIFY')
            modifier.thickness = geometry['solidify']
    elif kind == 'curve':
        geometry = data['curve']
        points = geometry['points']
        curve = bpy.data.curves.new(data['name'], 'CURVE')
        curve.dimensions = '3D'
        curve.bevel_depth = geometry['radius']
        curve.bevel_resolution = 2
        curve.resolution_u = 12
        curve.use_fill_caps = True
        spline = curve.splines.new(geometry['mode'].upper())
        spline.use_cyclic_u = geometry['closed']
        if geometry['mode'] == 'bezier':
            spline.bezier_points.add(len(points) - 1)
            for item, point in zip(spline.bezier_points, points):
                item.co = point
                item.handle_left_type = item.handle_right_type = 'AUTO'
        else:
            spline.points.add(len(points) - 1)
            for item, point in zip(spline.points, points):
                item.co = (*point, 1)
            if geometry['mode'] == 'nurbs':
                spline.order_u = min(4, len(points))
                spline.use_endpoint_u = not spline.use_cyclic_u
        obj = bpy.data.objects.new(data['name'], curve)
        bpy.context.collection.objects.link(obj)
    else:
        ops[kind]()
        obj = bpy.context.object
    obj.name = data["name"]
    transform(obj, data)
    mat = material(data["name"], data["color"], data["metallic"], data["roughness"])
    if kind == "text":
        obj.data.body = data["text"]
        obj.data.align_x = "CENTER"
        obj.data.align_y = "CENTER"
        obj.data.extrude = 0.018
        obj.data.bevel_depth = 0.004
        if font:
            obj.data.font = font
    if kind == "image":
        image = bpy.data.images.load(str(assets / data["asset"]))
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        shader = mat.node_tree.nodes.get("Principled BSDF")
        mat.node_tree.links.new(tex.outputs["Color"], shader.inputs["Base Color"])
        # Plane base shape is square; preserve image aspect before user scaling.
        obj.scale.x *= image.size[0] / max(1, image.size[1])
    obj.data.materials.append(mat)
    shader=mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Transmission Weight'].default_value=data.get('transmission',0)
    if data.get('bevel',0) and obj.type=='MESH':
        modifier=obj.modifiers.new('Rounded reference edges','BEVEL');modifier.width=data['bevel'];modifier.segments=3
    if kind in {"sphere", "cylinder", "cone", "torus"}:
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    if kind == "cube":
        bevel = obj.modifiers.new("Soft edges", "BEVEL")
        bevel.width = 0.08
        bevel.segments = 3
        obj.modifiers.new("Normals", "WEIGHTED_NORMAL")
    return obj


def build_scene(spec, assets, name, count):
    scene = bpy.data.scenes.new(name)
    bpy.context.window.scene = scene
    # CPU Cycles works without a GUI or graphics context, including the bpy wheel.
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = spec.get("samples", 16)
    scene.cycles.use_denoising = True
    scene.render.use_persistent_data = True
    scene.render.resolution_x = spec["width"]
    scene.render.resolution_y = spec["height"]
    scene.render.resolution_percentage = 100
    scene.render.fps = spec["fps"]
    scene.frame_start = 1
    scene.frame_end = count
    scene.render.image_settings.file_format = "PNG"
    scene.world = bpy.data.worlds.new("Studio World")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = rgba(spec["background"])
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = spec.get("ambient", .5)
    scene.view_settings.view_transform = "AgX"
    font = bpy.data.fonts.load(str(assets / spec["font"])) if spec["font"] else None
    authored = {}
    mesh_cache = {}
    for data in spec["objects"]:
        authored[data["name"]] = add_object(data, assets, font, mesh_cache)
    for data in spec["objects"]:
        obj = authored[data["name"]]
        if data.get("parent"):
            obj.parent = authored[data["parent"]]
        animate(obj, data, spec["fps"], scene.frame_end)
    animate_visibility(spec["objects"], authored, spec["fps"], scene.frame_end)
    animate_opacity(spec["objects"], authored, spec["fps"], scene.frame_end)
    build_rigs(spec.get('rigs', []), authored, spec['fps'], scene.frame_end)
    if spec.get("ground", True):
        bpy.ops.mesh.primitive_plane_add(size=200)
        floor = bpy.context.object
        floor.name = "Studio Floor"
        floor.data.materials.append(material("Floor", spec["floor"], roughness=0.55))
    defaults = [{"location":location,"energy":energy,"size":size,"color":"#FFFFFF"} for location,energy,size in [((2,-4,8),1800,6),((-5,-1,5),1200,5),((2,5,6),2200,4)]]
    for data in spec.get("lights", defaults):
        bpy.ops.object.light_add(type="AREA", location=data["location"])
        light = bpy.context.object
        light.data.energy, light.data.shape, light.data.size = data["energy"], "DISK", data["size"]
        light.data.color = rgba(data["color"])[:3]
        track(light, (0, 0, 1))
    cam_data = spec["camera"]
    bpy.ops.object.camera_add(location=cam_data["location"])
    camera = bpy.context.object
    camera.data.lens = cam_data["lens"]
    camera.data.type = 'ORTHO' if cam_data.get('projection') == 'orthographic' else 'PERSP'
    camera.data.ortho_scale = cam_data.get('ortho_scale', 10)
    track(camera, cam_data["target"])
    scene.camera = camera
    scene.frame_set(1)
    camera.keyframe_insert(data_path="location", frame=1)
    camera.keyframe_insert(data_path="rotation_euler", frame=1)
    camera.data.keyframe_insert(data_path="lens", frame=1)
    camera.data.keyframe_insert(data_path='ortho_scale', frame=1)
    if cam_data["end_location"]:
        camera.keyframe_insert(data_path="location", frame=1)
        camera.keyframe_insert(data_path="rotation_euler", frame=1)
        camera.location = cam_data["end_location"]
        track(camera, cam_data["target"])
        camera.keyframe_insert(data_path="location", frame=scene.frame_end)
        camera.keyframe_insert(data_path="rotation_euler", frame=scene.frame_end)
    for key in sorted(cam_data.get("keyframes", []), key=lambda key: key["time"]):
        camera.location = key["location"]
        track(camera, key["target"])
        camera.data.lens = key["lens"]
        if key.get('ortho_scale') is not None:
            camera.data.ortho_scale = key['ortho_scale']
        frame = min(scene.frame_end, 1+round(key["time"]*spec["fps"]))
        camera.keyframe_insert(data_path="location", frame=frame)
        camera.keyframe_insert(data_path="rotation_euler", frame=frame)
        camera.data.keyframe_insert(data_path="lens", frame=frame)
        camera.data.keyframe_insert(data_path='ortho_scale', frame=frame)
    return scene


def review_shot(spec, assets, output):
    from bpy_extras.object_utils import world_to_camera_view

    shot = spec['shots'][0]
    count = max(1, round(shot['end'] * spec['fps']) - round(shot['start'] * spec['fps']))
    objects = expand_objects(shot['objects'])
    scale = min(1, 480 / max(spec['width'], spec['height']))
    local = {**spec, **shot, 'objects': objects, 'samples': 2,
             'width': max(64, round(spec['width'] * scale)),
             'height': max(64, round(spec['height'] * scale))}
    scene = build_scene(local, assets, 'Shot review', count)
    groups = {}
    for binding in shot['element_bindings']:
        roots = [obj['name'] for obj in objects if obj['name'].split('__R', 1)[0] in binding['objects']]
        names = descendants(objects, roots)
        group = {scene.objects[name] for name in names}
        groups[binding['element_id']] = [obj for obj in group | {
            child for obj in group for child in obj.children_recursive} if obj.type in {'MESH', 'CURVE', 'FONT'}]
    visible_times = {identifier: [] for identifier in groups}
    images = []
    frames, visibility_frames = shot_review_frames(count, spec['fps'], shot['bindings'])
    for frame in sorted(visibility_frames):
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        second = round((frame - 1) / spec['fps'], 3)
        for identifier, group in groups.items():
            for obj in group:
                if obj.hide_render:
                    continue
                evaluated = obj.evaluated_get(depsgraph)
                projected = [world_to_camera_view(scene, scene.camera, evaluated.matrix_world @ Vector(point))
                             for point in evaluated.bound_box]
                if (max(p.z for p in projected) > scene.camera.data.clip_start
                        and min(p.z for p in projected) < scene.camera.data.clip_end
                        and min(p.x for p in projected) < 1 and max(p.x for p in projected) > 0
                        and min(p.y for p in projected) < 1 and max(p.y for p in projected) > 0):
                    visible_times[identifier].append(second)
                    break
        if frame in frames:
            image = output / f'review-{frame:04d}.png'
            scene.render.filepath = str(image)
            bpy.ops.render.render(write_still=True)
            if not complete_png(image):
                raise RuntimeError(f'Incomplete shot preview at frame {frame}')
            images.append({'file': image.name, 'second': second})
    (output / 'review.json').write_text(json.dumps({'images': images, 'visible_times': visible_times}), encoding='utf-8')


def prepare_scenes(spec, output, assets):
    scenes = []
    exported, seen = [], set()
    if spec.get("shots"):
        for index, shot in enumerate(spec["shots"]):
            prefix = f"S{index+1:02d}_"
            objects = [{**obj, "name": prefix+obj["name"], "parent": prefix+obj["parent"] if obj.get("parent") else None} for obj in expand_objects(shot["objects"])]
            start, end = round(shot["start"]*spec["fps"]), round(shot["end"]*spec["fps"])
            if end <= start:
                raise ValueError("A shot must contain at least one output frame")
            rigs = [{**rig, 'name':prefix+rig['name'], 'root':prefix+rig['root'],
                     'bones':[{**bone, 'objects':[prefix+name for name in bone['objects']]} for bone in rig['bones']]}
                    for rig in shot.get('rigs', [])]
            elements = [{**binding, 'objects':[prefix+name for name in binding['objects']]}
                        for binding in shot.get('element_bindings', [])]
            local = {**spec, **shot, "objects": objects, 'rigs':rigs, 'element_bindings':elements, "duration": shot["end"]-shot["start"]}
            try:
                scene = build_scene(local, assets, prefix+shot["title"], end-start)
            except Exception as exc:
                raise RuntimeError(f"Shot {index+1} ({shot['title']}): {exc}") from exc
            if spec.get('export_assets') or spec.get('cache_reusable_assets'):
                from library_export import export_elements
                try:
                    authored = {obj['name']: scene.objects[obj['name']] for obj in objects}
                    exported.extend(export_elements(scene, local, authored, output, assets, seen))
                except Exception as exc:
                    print(f'WARNING: asset cache for shot {index+1}: {exc}', flush=True)
            scenes.append((scene, start))
    else:
        scenes.append((build_scene({**spec,'objects':expand_objects(spec['objects'])}, assets, spec["title"], max(1,round(spec["duration"]*spec["fps"]))), 0))
    first = scenes[0][0]
    if spec.get('export_assets') or exported:
        try:
            (output/'exported-assets.json').write_text(json.dumps(exported, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            print(f'WARNING: could not write asset cache report: {exc}', flush=True)
    bpy.context.window.scene = first
    first.frame_set(1)
    first.render.filepath = str(output / "preview.png")
    bpy.ops.file.pack_all()
    partial = output / 'scene-partial.blend'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(partial), compress=False)
    partial.replace(output / 'scene.blend')
    return scenes


def saved_scenes(spec, path):
    if not complete_blend(path):
        return []
    try:
        bpy.ops.wm.open_mainfile(filepath=str(path), use_scripts=False)
        if not spec.get('shots'):
            existing = [scene for scene in bpy.data.scenes if scene.camera]
            return [(existing[0], 0)] if len(existing) == 1 else []
        saved = []
        for index, shot in enumerate(spec['shots'], 1):
            candidates = [scene for scene in bpy.data.scenes if scene.name.startswith(f'S{index:02d}_') and scene.camera]
            start = round(shot['start'] * spec['fps'])
            if len(candidates) != 1 or candidates[0].frame_end != round(shot['end'] * spec['fps']) - start:
                return []
            saved.append((candidates[0], start))
        return saved
    except RuntimeError:
        return []


def run(spec_path, assets_path, mode):
    path = Path(spec_path).resolve()
    output, assets = path.parent, Path(assets_path).resolve()
    spec = json.loads(path.read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if mode == 'review':
        review_shot(spec, assets, output)
        return
    frames = output / "frames"
    frames.mkdir(exist_ok=True)
    (output / 'render-timing.json').unlink(missing_ok=True)
    scenes = saved_scenes(spec, output / 'scene.blend')
    if not scenes:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scenes = prepare_scenes(spec, output, assets)
    first = scenes[0][0]
    bpy.context.window.scene = first
    first.frame_set(1)
    first.render.filepath = str(output / 'preview.png')
    if not complete_png(output / "preview.png"):
        checkpoint(output)
        bpy.ops.render.render(write_still=True)
    if mode == "video":
        for index, (scene, offset) in enumerate(scenes, 1):
            bpy.context.window.scene = scene
            print(f'Rendering shot {index}/{len(scenes)} ({scene.name})', flush=True)
            try:
                render_frames(scene, frames, offset)
            except Exception as exc:
                raise RuntimeError(f'Shot {index} ({scene.name}): {exc}') from exc


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    run(*args)
