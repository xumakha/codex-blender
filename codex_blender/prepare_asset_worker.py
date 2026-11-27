"""Bake generated/reference-based assemblies into editable reusable component GLBs before screenplay."""
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from mathutils import Vector,Matrix
import render_scene as R
from rigging import build_rigs

def main(options):
    root=Path(options['root']);folder=Path(options['folder']);folder.mkdir(parents=True,exist_ok=True)
    design=options['design'];bpy.ops.wm.read_factory_settings(use_empty=True)
    authored={};owned={}
    for data in design['objects']:
        obj=R.add_object(data,root,None);authored[data['name']]=obj
        owned[data['name']]={obj,*obj.children_recursive}
    for data in design['objects']:
        if data['parent']:authored[data['name']].parent=authored[data['parent']]
    bpy.context.view_layer.update()
    prototypes=[];component_paths=[]
    for index,data in enumerate(design['objects']):
        prototype=dict(data);prototype['keyframes']=[]
        if data['kind']=='empty':prototypes.append(prototype);continue
        obj=authored[data['name']];parent=obj.parent;local=obj.matrix_basis.copy()
        output=folder/f'part-{index:03d}.glb';partial=folder/f'part-{index:03d}.partial.glb'
        try:
            obj.parent=None;obj.matrix_world=Matrix.Identity(4)
            bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT')
            points=[child.matrix_world@Vector(corner) for child in owned[data['name']] if child.type=='MESH' for corner in child.bound_box]
            lower=[min(p[i] for p in points) for i in range(3)];upper=[max(p[i] for p in points) for i in range(3)]
            for child in owned[data['name']]:child.select_set(True)
            bpy.context.view_layer.objects.active=obj
            bpy.ops.export_scene.gltf(filepath=str(partial),export_format='GLB',use_selection=True,
                export_animations=False,export_skins=False,export_apply=True)
            partial.replace(output)
        finally:
            obj.parent=parent;obj.matrix_basis=local
        relative=output.relative_to(root).as_posix();component_paths.append(relative)
        meta={'name':options['name']+' · '+data['name'],'description':design['description'],
              'source':'blender','tags':['auto-prepared','component',options['requirement']],
              'dimensions':[b-a for a,b in zip(lower,upper)],'local_bounds':[lower,upper],
              'component_of':(folder/'assembly.glb').relative_to(root).as_posix(),
              'reference_assets':design['reference_assets'],'preview':(folder/'preview.png').relative_to(root).as_posix()}
        output.with_suffix('.asset.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
        prototype.update(kind='model',asset=relative,asset_nodes=[],asset_pivot=[0,0,0],recolor=None,transmission=0,bevel=0)
        prototypes.append(prototype)
    # Rebuild the full assembly with repetitions after exporting each reusable template once.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    expanded=R.expand_objects(design['objects']);authored={}
    for data in expanded:authored[data['name']]=R.add_object(data,root,None)
    for data in expanded:
        if data['parent']:authored[data['name']].parent=authored[data['parent']]
    bpy.context.view_layer.update()
    build_rigs(design['rigs'],authored,1,1)
    R.animate_visibility(expanded,authored,1,1)
    R.animate_opacity(expanded,authored,1,1)
    # Keep a complete, rigged model as well as the separately controllable parts.
    bpy.ops.object.select_all(action='SELECT')
    complete=folder/'assembly.glb'
    bpy.ops.export_scene.gltf(filepath=str(complete),export_format='GLB',use_selection=True,export_animations=False,export_skins=True,export_apply=True)
    recipe={'objects':prototypes,'rigs':design['rigs']}
    (folder/'assembly.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2),encoding='utf-8')
    complete.with_suffix('.asset.json').write_text(json.dumps({'name':options['name'],'description':design['description'],
        'source':'blender','tags':['auto-prepared','assembly',options['requirement']],
        'preview':(folder/'preview.png').relative_to(root).as_posix(),'reference_assets':design['reference_assets'],
        'assembly_recipe':(folder/'assembly.json').relative_to(root).as_posix(),'rigged':bool(design['rigs']),
        'component_assets':component_paths},ensure_ascii=False,indent=2),encoding='utf-8')
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    points=[o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
    lo=Vector([min(p[i] for p in points) for i in range(3)]);hi=Vector([max(p[i] for p in points) for i in range(3)])
    center=(lo+hi)/2;radius=max((hi-lo).length/2,.15)
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=8
    scene.cycles.use_denoising=True;scene.render.resolution_x=384;scene.render.resolution_y=384
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene.world=bpy.data.worlds.new('Preview world');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.22,.22,.22,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.6
    for loc,power in [((3,-4,5),1200),((-4,-2,3),800),((2,3,4),1000)]:
        bpy.ops.object.light_add(type='AREA',location=center+Vector(loc)*radius)
        lamp=bpy.context.object;lamp.data.energy=power*radius**2;lamp.data.shape='DISK';lamp.data.size=radius*4;R.track(lamp,center)
    bpy.ops.object.camera_add(location=center+Vector((3,-7,2.8)).normalized()*radius*3.8)
    camera=bpy.context.object;camera.data.lens=45;R.track(camera,center);scene.camera=camera
    scene.render.filepath=str(folder/'preview.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'assembly.blend'))
    bpy.ops.render.render(write_still=True)
    (folder/'result.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PREPARED',options['requirement'],len(component_paths),'parts',flush=True)

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    main(json.loads(Path(args[0]).read_text(encoding='utf-8')))
