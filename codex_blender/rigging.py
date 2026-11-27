"""Create real Blender armatures with rigid weights for stylized body parts."""
import math
import bpy


def build_rigs(rigs, authored, fps, last):
    result = {}
    for rig in rigs:
        skeleton = bpy.data.armatures.new(rig['name'])
        armature = bpy.data.objects.new(rig['name'], skeleton)
        bpy.context.collection.objects.link(armature)
        armature.parent = authored[rig['root']]
        armature.location = (0, 0, 0)
        bpy.ops.object.select_all(action='DESELECT')
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='EDIT')
        for spec in rig['bones']:
            bone = skeleton.edit_bones.new(spec['name'])
            bone.head, bone.tail = spec['head'], spec['tail']
        for spec in rig['bones']:
            if spec.get('parent'):
                skeleton.edit_bones[spec['name']].parent = skeleton.edit_bones[spec['parent']]
        bpy.ops.object.mode_set(mode='OBJECT')
        for spec in rig['bones']:
            bone = armature.pose.bones[spec['name']]
            bone.rotation_mode = 'XYZ'
            bone.rotation_euler = [math.radians(v) for v in spec['rotation']]
            bone.keyframe_insert(data_path='rotation_euler', frame=1)
            for key in sorted(spec['keyframes'], key=lambda key: key['time']):
                bone.rotation_euler = [math.radians(v) for v in key['rotation']]
                bone.keyframe_insert(data_path='rotation_euler', frame=min(last, 1+round(key['time']*fps)))
            for name in spec['objects']:
                root = authored[name]
                meshes = [obj for obj in [root, *root.children_recursive] if obj.type == 'MESH']
                for mesh in meshes:
                    group = mesh.vertex_groups.new(name=spec['name'])
                    group.add(list(range(len(mesh.data.vertices))), 1, 'REPLACE')
                    modifier = next((mod for mod in mesh.modifiers
                                     if mod.type == 'ARMATURE' and mod.object is armature), None)
                    if modifier is None:
                        modifier = mesh.modifiers.new('Skeleton', 'ARMATURE')
                        modifier.object = armature
        result[rig['name']] = armature
    return result
