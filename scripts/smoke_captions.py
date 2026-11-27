"""Offline check of timed word captions, animation, font loading and audio mixing."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import imageio_ffmpeg
from codex_blender.audio import encode_video
from codex_blender.captions import save_words
from codex_blender.config import OUTPUTS


def main():
    path = OUTPUTS / 'word-captions-demo'
    path.mkdir(parents=True, exist_ok=True)
    frames = path / 'frames'
    frames.mkdir(exist_ok=True)
    font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/arialbd.ttf'
    if not font.is_file():
        raise RuntimeError('Set a local font path in this smoke script for this platform.')
    shutil.copyfile(font, path/'font.ttf')
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg, '-v','error','-y','-f','lavfi','-i','color=c=0x182536:s=540x960:r=30',
                    '-t','6',str(frames/'frame_%04d.png')],check=True)
    subprocess.run([ffmpeg,'-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=2',
                    '-af','volume=0.02',str(path/'cue.wav')],check=True)
    save_words(path/'cue.wav',[
        {'text':'Xin','start':.1,'end':.35}, {'text':'chào!','start':.45,'end':.85},
        {'text':'Mượt','start':1.0,'end':1.35}, {'text':'mà.','start':1.5,'end':1.85}])
    encode_video(path, {'duration':6,'fps':30,'width':540,'height':960,'font':'font.ttf',
                       'captions':True,'shots':[{'narration':[
                           {'text':'Xin chào! Mượt mà.','start':1,'end':3,'audio':'cue.wav'},
                           {'text':'Xin chào! Mượt mà.','start':4,'end':6,'audio':'cue.wav'}]}]}, path)
    timing = json.loads((path/'caption-timing.json').read_text(encoding='utf-8'))
    assert not timing['estimated']
    assert len(timing['words']) == 8
    assert timing['words'][4]['start'] == 4.1
    subprocess.run([ffmpeg,'-v','error','-i',str(path/'video.mp4'),'-f','null','-'],check=True)
    for name, second in [('before',.7),('enter',1.1),('peak',1.17),('settle',1.3),('next',1.65),('pause',3.5)]:
        subprocess.run([ffmpeg,'-v','error','-y','-ss',str(second),'-i',str(path/'video.mp4'),
                        '-frames:v','1',str(path/f'{name}.png')],check=True)
    print(path/'video.mp4')


if __name__ == '__main__':
    main()
