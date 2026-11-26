"""Real render test: reuse a saved GLB and mix voice/music with ducking and captions."""
import json
from pathlib import Path
import subprocess
import time
import imageio_ffmpeg
from codex_blender import library
from codex_blender.config import assets_dir
from codex_blender.models import SceneSpec
from codex_blender.jobs import submit,status

model=next(a for a in library.catalog() if a['kind']=='model' and a['source']=='blender')
scene=SceneSpec(title='Studio media integration test',duration=.5,fps=4,width=160,height=284,samples=2,
    camera={'location':[5,-8,4],'target':[0,0,1]},
    objects=[{'name':'Reused model','kind':'model','asset':model['path']}],
    voice_audio='elevator-sample-chime.wav',music='elevator-sample-chime.wav',
    font='sample-arial-bold.ttf',subtitles='Thử voice + nhạc',voice_volume=.8,music_volume=.1,duck_music=True)
job=submit(scene,'video',assets_dir())
deadline=time.monotonic()+180
while time.monotonic()<deadline:
    data=status(job['id'])
    if data['state']=='failed':raise RuntimeError(data['error']+'; '+data['artifacts'].get('render.log',''))
    if data['state']=='completed':break
    time.sleep(1)
else:raise TimeoutError('Media test timed out')
result=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-i',data['artifacts']['video.mp4'],'-f','null','-'],capture_output=True,text=True)
assert result.returncode==0,result.stderr
assert 'Audio: aac' in result.stderr and '160x284' in result.stderr,result.stderr
print(json.dumps({'passed':True,'job':job['id'],'glb':model['path'],'video':data['artifacts']['video.mp4']},indent=2))
