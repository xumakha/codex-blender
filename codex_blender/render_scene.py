"""Executed by Blender (or optional bpy wheel), not imported by the MCP server."""
import json
import math
from pathlib import Path
import sys

# Blender also executes this file directly, outside the installed app's Python environment.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry import expand_objects
from pause_control import checkpoint

import bpy
from mathutils import Vector


def complete_png(path):
    try:
        with path.open("rb") as image:
            if image.read(8) != b"\x89PNG\r\n\x1a\n":
                return False
            image.seek(-12, 2)
            return image.read() == b"\x00\x00\x00\x00IEND\xaeB`\x82"
    except (OSError, ValueError):
        return False


def render_frames(scene, frames, offset=0):
    for frame in range(scene.frame_start, scene.frame_end + 1):
        target = frames / f"frame_{frame+offset:04d}.png"
        if complete_png(target):
            continue
        checkpoint(frames.parent)
        scene.frame_set(frame)
        scene.render.filepath = str(target)
        bpy.ops.render.render(write_still=True)


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


def add_object(data, assets, font):
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
        obj = bpy.data.objects.new(data["name"], None)
        bpy.context.collection.objects.link(obj)
        for child in imported:
            if child.parent is None:
                child.parent = obj
        transform(obj, data)
        return obj
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
    for data in spec["objects"]:
        authored[data["name"]] = add_object(data, assets, font)
    for data in spec["objects"]:
        obj = authored[data["name"]]
        if data.get("parent"):
            obj.parent = authored[data["parent"]]
        animate(obj, data, spec["fps"], scene.frame_end)
    animate_visibility(spec["objects"], authored, spec["fps"], scene.frame_end)
    animate_opacity(spec["objects"], authored, spec["fps"], scene.frame_end)
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
    track(camera, cam_data["target"])
    scene.camera = camera
    camera.keyframe_insert(data_path="location", frame=1)
    camera.keyframe_insert(data_path="rotation_euler", frame=1)
    camera.data.keyframe_insert(data_path="lens", frame=1)
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
        frame = min(scene.frame_end, 1+round(key["time"]*spec["fps"]))
        camera.keyframe_insert(data_path="location", frame=frame)
        camera.keyframe_insert(data_path="rotation_euler", frame=frame)
        camera.data.keyframe_insert(data_path="lens", frame=frame)
    return scene


def run(spec_path, assets_path, mode):
    path = Path(spec_path).resolve()
    output, assets = path.parent, Path(assets_path).resolve()
    spec = json.loads(path.read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    frames = output / "frames"
    frames.mkdir(exist_ok=True)
    scenes = []
    if spec.get("shots"):
        for index, shot in enumerate(spec["shots"]):
            prefix = f"S{index+1:02d}_"
            objects = [{**obj, "name": prefix+obj["name"], "parent": prefix+obj["parent"] if obj.get("parent") else None} for obj in expand_objects(shot["objects"])]
            start, end = round(shot["start"]*spec["fps"]), round(shot["end"]*spec["fps"])
            if end <= start:
                raise ValueError("A shot must contain at least one output frame")
            local = {**spec, **shot, "objects": objects, "duration": shot["end"]-shot["start"]}
            scenes.append((build_scene(local, assets, prefix+shot["title"], end-start), start))
    else:
        scenes.append((build_scene({**spec,'objects':expand_objects(spec['objects'])}, assets, spec["title"], max(1,round(spec["duration"]*spec["fps"]))), 0))
    first = scenes[0][0]
    bpy.context.window.scene = first
    first.frame_set(1)
    first.render.filepath = str(output / "preview.png")
    bpy.ops.file.pack_all()
    if not (output / "scene.blend").exists():
        bpy.ops.wm.save_as_mainfile(filepath=str(output / "scene.blend"))
    if not complete_png(output / "preview.png"):
        checkpoint(output)
        bpy.ops.render.render(write_still=True)
    if mode == "video":
        for scene, offset in scenes:
            bpy.context.window.scene = scene
            render_frames(scene, frames, offset)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    run(*args)
