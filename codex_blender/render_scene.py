"""Executed by Blender (or optional bpy wheel), not imported by the MCP server."""
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


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


def add_object(data, assets, font):
    kind = data["kind"]
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


def run(spec_path, assets_path, mode):
    path = Path(spec_path).resolve()
    output = path.parent
    assets = Path(assets_path).resolve()
    spec = json.loads(path.read_text(encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
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
    scene.frame_end = max(1, round(spec["duration"] * spec["fps"]))
    scene.render.image_settings.file_format = "PNG"
    scene.world = bpy.data.worlds.new("Studio World")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = rgba(spec["background"])
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.5
    scene.view_settings.view_transform = "AgX"
    font = bpy.data.fonts.load(str(assets / spec["font"])) if spec["font"] else None
    for data in spec["objects"]:
        obj = add_object(data, assets, font)
        animate(obj, data, spec["fps"], scene.frame_end)
    bpy.ops.mesh.primitive_plane_add(size=200)
    floor = bpy.context.object
    floor.name = "Studio Floor"
    floor.data.materials.append(material("Floor", spec["floor"], roughness=0.55))
    for location, energy, size in [((2, -4, 8), 1800, 6), ((-5, -1, 5), 1200, 5), ((2, 5, 6), 2200, 4)]:
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy, light.data.shape, light.data.size = energy, "DISK", size
        track(light, (0, 0, 1))
    cam_data = spec["camera"]
    bpy.ops.object.camera_add(location=cam_data["location"])
    camera = bpy.context.object
    camera.data.lens = cam_data["lens"]
    track(camera, cam_data["target"])
    scene.camera = camera
    if cam_data["end_location"]:
        camera.keyframe_insert(data_path="location", frame=1)
        camera.keyframe_insert(data_path="rotation_euler", frame=1)
        camera.location = cam_data["end_location"]
        track(camera, cam_data["target"])
        camera.keyframe_insert(data_path="location", frame=scene.frame_end)
        camera.keyframe_insert(data_path="rotation_euler", frame=scene.frame_end)
    frames = output / "frames"
    frames.mkdir(exist_ok=True)
    scene.render.filepath = str(frames / "frame_")
    scene.frame_set(1)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "scene.blend"))
    # Always make a preview; rendering a full video uses the same saved scene.
    scene.render.filepath = str(output / "preview.png")
    bpy.ops.render.render(write_still=True)
    if mode == "video":
        scene.render.filepath = str(frames / "frame_")
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    run(*args)
