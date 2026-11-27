"""Small locally synthesized music beds and animation sound effects."""
from array import array
import hashlib
import math
import random
import uuid
import wave


def write_sound(path, kind, seconds, music=False):
    rate = 24000
    rng = random.Random(42)
    samples = array('h')
    notes = [261.63, 329.63, 392, 440, 392, 329.63, 293.66, 392]
    smooth = 0
    for i in range(max(1,round(seconds*rate))):
        t = i/rate
        noise = rng.uniform(-1,1)
        smooth = .8*smooth+.2*noise
        if music:
            tempo = {'ambient':.8,'playful':3,'triumphant':2}[kind]
            beat = t*tempo
            note = notes[int(beat)%len(notes)]
            envelope = math.exp(-4*(beat%1))
            melody = math.sin(2*math.pi*note*t)*envelope
            bass = math.sin(2*math.pi*(130.81 if int(beat/4)%2==0 else 98)*t)*.3
            value = .22*(melody+bass)
        elif kind in {'chime','success','scan'}:
            frequency = (523.25 if kind=='chime' else 660 if kind=='scan' else notes[min(7,int(t*4))])
            value = .6*math.sin(2*math.pi*frequency*t)*math.exp(-3*(t if kind!='success' else t%.25))
        elif kind=='mechanical':
            value = .25*math.sin(2*math.pi*75*t)+.1*smooth
        elif kind=='footstep':
            phase = t%.4
            value = math.exp(-35*phase)*(.7*smooth+.3*math.sin(2*math.pi*85*t))
        elif kind=='breath':
            value = smooth*.8*(math.sin(math.pi*(t%1.4)/1.4)**2)
        elif kind=='whoosh':
            value = smooth*math.sin(math.pi*t/seconds)
        elif kind=='bird':
            # Short frequency sweeps, separated by quiet gaps, like cartoon birds.
            phase = t % .8
            pulse = math.sin(math.pi*phase/.24)**2 if phase < .24 else 0
            value = .35*pulse*math.sin(2*math.pi*(1800*phase+2400*phase*phase))
        elif kind=='fly':
            frequency = 155
            phase = 2*math.pi*frequency*t + 1.5*math.sin(2*math.pi*6*t)
            value = (.22*math.sin(phase)+.1*math.sin(2*phase)+.05*math.sin(3*phase))*(.6+.4*math.sin(2*math.pi*.7*t)**2)
        elif kind=='water_drop':
            phase = t % .65
            value = .6*math.exp(-30*phase)*math.sin(2*math.pi*(1400*phase-900*phase*phase))
        else:
            value = smooth*math.exp(-25*(t if kind=='pop' else t%.4))
        fade = min(1,t/.01,(seconds-t)/.05)
        samples.append(round(max(-1,min(1,value*max(0,fade)))*32767))
    partial = path.with_name(path.stem+'.'+uuid.uuid4().hex+'.partial.wav')
    try:
        with wave.open(str(partial),'wb') as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(rate)
            output.writeframes(samples.tobytes())
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def background_only(scene, music=None, volume=None):
    """One continuous music bed; narration remains text for captions, never audio."""
    first = scene.music_cues[0] if scene.music_cues else None
    scene.music = music or scene.music or (first.audio if first else None) or scene.audio
    scene.music_style = first.style if first else scene.music_style if scene.music_style != 'none' else 'ambient'
    scene.music_cues = []
    scene.effects = []
    scene.audio = None
    scene.voice_audio = None
    scene.voice_volume = 0
    scene.duck_music = False
    scene.audio_mode = 'music_only'
    if volume is not None:scene.music_volume = volume
    for shot in scene.shots:
        for cue in shot.narration:cue.audio = None
    return scene


def prepare_sound(scene, root):
    if scene.audio_mode == 'music_only':background_only(scene)
    folder = root/'audio-generated'
    folder.mkdir(exist_ok=True)
    if not scene.music_cues and not scene.music and scene.music_style!='none':
        path = folder/f'bed-v1-{scene.music_style}.wav'
        if not path.exists():
            write_sound(path,scene.music_style,8,music=True)
        scene.music = path.relative_to(root).as_posix()
    for cue in scene.music_cues:
        if not cue.audio:
            path = folder/f'bed-v1-{cue.style}.wav'
            if not path.exists():
                write_sound(path, cue.style, 8, music=True)
            cue.audio = path.relative_to(root).as_posix()
    for cue in scene.effects:
        if cue.audio:
            continue
        digest = hashlib.sha256(f'{cue.kind}|{cue.end-cue.start:.6f}'.encode()).hexdigest()[:20]
        path = folder/f'effect-v1-{digest}.wav'
        if not path.exists():
            write_sound(path,cue.kind,cue.end-cue.start)
        cue.audio = path.relative_to(root).as_posix()
