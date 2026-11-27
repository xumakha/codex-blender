"""Real Blender check: bone deformation, orthographic camera, GLB skins, music and VN captions."""
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codex_blender import audio, fonts
from codex_blender.models import SceneSpec
from codex_blender.sounddesign import prepare_sound


def main():
    import bpy
    from codex_blender.render_scene import run
    folder=Path('outputs/screenplay-capabilities-smoke').resolve()
    folder.mkdir(parents=True,exist_ok=True)
    root=folder/'library';root.mkdir(exist_ok=True)
    font=fonts.ensure_font(root)
    sample=Path('D:/VoiceStudio/Voices/TuanAnh/Tuan-Anh-preview.mp3')
    if not sample.is_file():
        raise RuntimeError('This smoke check needs the locally verified Tuấn Anh speech sample')
    shutil.copyfile(sample,root/'voice.mp3')
    element={'id':'inventor', 'label':'Inventor rig', 'role':'character', 'construction':'geometry',
        'source':'Smoke test', 'appearance':'Two orange blocks with an armature', 'parts':[]}
    shot={'title':'Bone motion','start':0,'end':3,'setting':'Studio','actions':['Raise arm'],
        'camera':{'projection':'orthographic','ortho_scale':6,'location':[5,-8,5],'target':[0,0,1.5]},
        'objects':[{'name':'Hero','kind':'empty','location':[0,0,0]},
            {'name':'Body','kind':'cube','parent':'Hero','location':[0,0,1],'scale':[.4,.3,.6],'color':'#FFA500'},
            {'name':'Hand','kind':'cube','parent':'Hero','location':[.8,0,1.8],'scale':[.15,.15,.6],'color':'#FF9900'}],
        'rigs':[{'name':'Skeleton','root':'Hero','bones':[
            {'name':'Spine','head':[0,0,.5],'tail':[0,0,1.5],'objects':['Body']},
            {'name':'Arm','parent':'Spine','head':[.8,0,1.2],'tail':[.8,0,2.4],'objects':['Hand'],
             'keyframes':[{'time':0,'rotation':[0,0,0]},{'time':2.5,'rotation':[0,0,70]}]}]}],
        'bindings':[{'action_index':0,'objects':['Hand'],'start':0,'end':3,'elements':['inventor']}],
        'elements':[element], 'element_bindings':[{'element_id':'inventor','objects':['Hero']}],
        'narration':[{'start':0,'end':2.5,'text':'Xin chào, đây là giọng Tuấn Anh.','audio':'voice.mp3'}]}
    second={**shot,'title':'Victory','start':3,'end':6,'narration':[]}
    spec=SceneSpec(title='Screenplay capability smoke',duration=6,fps=2,width=160,height=160,samples=1,
        font=font,captions=True,export_assets=True,shots=[shot,second], music_cues=[
            {'start':0,'end':3,'style':'playful'}, {'start':3,'end':6,'style':'triumphant'}],
        effects=[{'start':0,'end':1,'kind':'bird'},{'start':1,'end':2,'kind':'fly'},
                 {'start':2,'end':3,'kind':'water_drop'}])
    prepare_sound(spec,root)
    path=folder/'scene.json';path.write_text(spec.model_dump_json(indent=2),encoding='utf-8')
    run(path,root,'video')
    scene=bpy.data.scenes['S01_Bone motion'];bpy.context.window.scene=scene
    armature=scene.objects['S01_Skeleton'];mesh=scene.objects['S01_Hand']
    assert armature.type=='ARMATURE' and len(armature.data.bones)==2
    assert mesh.vertex_groups.get('Arm') is not None
    assert scene.camera.data.type=='ORTHO'
    def vertex(frame):
        scene.frame_set(frame);bpy.context.view_layer.update()
        evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return evaluated.matrix_world @ evaluated.data.vertices[0].co
    before,after=vertex(1),vertex(6)
    assert (after-before).length>.1,(before,after)
    manifest=json.loads((folder/'exported-assets.json').read_text(encoding='utf-8'))
    assert len(manifest)==1,manifest
    glb=root/manifest[0]['path']
    with glb.open('rb') as stream:
        assert stream.read(4)==b'glTF'
        stream.seek(12);length,kind=struct.unpack('<II',stream.read(8))
        document=json.loads(stream.read(length))
    assert document.get('skins') and len(document['skins'][0]['joints'])==2
    assert len(list((folder/'frames').glob('frame_*.png')))==12
    audio.encode_video(folder,spec.model_dump(mode='json'),root)
    assert audio.audio_duration(folder/'video.mp4')>=5.9
    assert (folder/'captions.ass').is_file()
    print(json.dumps({'ok':True,'deformation':(after-before).length,'rigged_asset':str(glb),
                      'video':str(folder/'video.mp4'),'duration':audio.audio_duration(folder/'video.mp4')}))


if __name__=='__main__':main()
