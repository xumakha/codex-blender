"""Export selected objects from an app-generated .blend as a reusable normalized GLB."""
import json
from pathlib import Path
import sys
import math
import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else sys.argv[1:]
data = json.loads(Path(args[0]).read_text(encoding="utf-8"))
bpy.context.preferences.filepaths.use_scripts_auto_execute = False
bpy.ops.wm.open_mainfile(filepath=data["blend"], load_ui=False)
scene = bpy.context.scene
scene.frame_set(1)
selected = set()
for name in data["names"]:
    obj = scene.objects.get(name)
    if obj is None:
        raise ValueError(f"Object not found: {name}")
    selected.add(obj)
    selected.update(obj.children_recursive)
geometry = [o for o in selected if o.type in {"MESH", "FONT", "CURVE"}]
if not geometry:
    raise ValueError("No geometry selected")
points = [o.matrix_world @ Vector(corner) for o in geometry for corner in o.bound_box]
lo = Vector(tuple(min(p[i] for p in points) for i in range(3)))
hi = Vector(tuple(max(p[i] for p in points) for i in range(3)))
origin = Vector(((lo.x+hi.x)/2, (lo.y+hi.y)/2, lo.z))
# Freeze animation and normalize floor-center origin for the next scene.
for obj in selected:
    obj.animation_data_clear()
for obj in selected:
    if obj.parent not in selected:
        if obj.parent:
            world = obj.matrix_world.copy()
            obj.parent = None
            obj.matrix_world = world
        obj.location -= origin
bpy.context.view_layer.update()
bpy.ops.object.select_all(action="DESELECT")
for obj in selected:
    obj.select_set(True)
bpy.context.view_layer.objects.active = geometry[0]
for obj in list(geometry):
    if obj.type in {"FONT", "CURVE"}:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.ops.object.convert(target="MESH")
bpy.ops.object.select_all(action="DESELECT")
for obj in selected:
    obj.select_set(True)
output = Path(data["output"])
partial = output.with_name(output.stem+".partial.glb")
bpy.ops.export_scene.gltf(filepath=str(partial), export_format="GLB", use_selection=True, export_animations=False)
partial.replace(output)
for obj in scene.objects:
    if obj.type not in {"LIGHT", "CAMERA"}:
        obj.hide_render = obj not in selected
radius = max((hi-lo).length/2, .5)
target = Vector((0,0,(hi.z-lo.z)*.5))
camera = scene.camera
camera.animation_data_clear()
camera.location = target + Vector((1.8,-2.8,1.5))*radius
camera.rotation_euler = (target-camera.location).to_track_quat("-Z","Y").to_euler()
camera.data.lens = 50
scene.render.resolution_x = scene.render.resolution_y = 256
scene.render.resolution_percentage = 100
scene.cycles.samples = 8
scene.render.filepath = str(output.with_suffix(".png"))
bpy.ops.render.render(write_still=True)
