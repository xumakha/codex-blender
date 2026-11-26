"""Create the first five seconds of the supplied elevator script as a reusable scene."""
import json
import math
from pathlib import Path
import shutil
import struct
import wave
from codex_blender.models import SceneSpec

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)
shutil.copyfile("C:/Windows/Fonts/arialbd.ttf", ASSETS / "sample-arial-bold.ttf")
objects = []


def add(name, kind, loc, scale, color, rotation=(0, 0, 0), keys=None, **extra):
    objects.append(dict(name=name, kind=kind, location=loc, scale=scale, color=color,
                        rotation=rotation, roughness=0.65, metallic=0,
                        keyframes=keys or [], **extra))


def box(name, loc, scale, color, **kw):
    add(name, "cube", loc, scale, color, **kw)


cream, mint, trim, glass = "#F4EBDD", "#93B5A8", "#D8DED2", "#3F6875"
# Architectural model: ten clearly separated floors, framed windows and a stair core.
box("Display plinth", (0, 0, 0.12), (2.9, 2.15, .12), "#E7DAC2")
box("Back wall", (.3, 1.2, 5.05), (1.6, .12, 4.72), mint)
box("Right wall", (1.82, .2, 5.05), (.12, 1, 4.72), mint)
for i in range(11):
    z = .35 + .94*i
    box(f"Floor slab {i:02}", (.3, .15, z), (1.65, 1.17, .065), trim)
for x in (-1.22, 1.82):
    box(f"Front column {x}", (x, -1, 5.05), (.09, .1, 4.72), "#CAD5C7")
for i in range(10):
    z = .35 + .94*i + .47
    # Two permanent facade strips leave an open central stair core.
    for x in (-.94, 1.54):
        box(f"Facade {i}-{x}", (x, -1.02, z), (.22, .08, .4), mint)
        box(f"Window {i}-{x}", (x, -1.113, z+.025), (.145, .025, .25), glass)
    # Landings at the back and five broad steps per flight, alternating direction.
    if i < 9:
        direction = 1 if i % 2 == 0 else -1
        for step in range(5):
            x = .3 + direction*(-.73 + step*.365)
            sz = .35 + i*.94 + (step+1)*.188
            box(f"Stair {i}-{step}", (x, -.3, sz), (.20, .43, .055), "#D8AD78")
        # Matching diagonal handrail, cylinders oriented from Z toward the stair flight.
        add(f"Rail {i}", "cylinder", (.3, -.78, .35+i*.94+.99), (.025,.025,1.02), "#5E8276", rotation=(0, direction*62, 0))
box("Roof cap", (.3, .15, 9.9), (1.79, 1.30, .13), "#D2AA77")
box("Roof trim", (.3, .15, 10.08), (1.69, 1.2, .045), "#F4E8D4")

# An intentionally stylized inventor, built from consistent rounded primitives.
# Camera faces negative Y; face details are placed on the front of the head.
cx, cy = -2.05, -1.65
skin, yellow, brown, black = "#E6B68E", "#F1CD70", "#826046", "#292A2B"
for dx in (-.17, .17):
    box(f"Shoe {dx}", (cx+dx, cy-.08, .34), (.13,.24,.10), black)
    add(f"Trouser leg {dx}", "cylinder", (cx+dx, cy, .72), (.115,.115,.32), brown)
box("Shirt", (cx,cy,1.28), (.32,.18,.34), yellow)
add("Neck", "cylinder", (cx,cy,1.70), (.10,.10,.12), skin)
add("Head", "sphere", (cx,cy,2.01), (.28,.24,.34), skin)
add("Hair cap", "sphere", (cx,cy+.025,2.21), (.29,.24,.17), black)
for dx in (-.12,.12):
    add(f"Ear {dx}", "sphere", (cx+dx*2.25,cy,2.02), (.055,.065,.10), skin)
    add(f"Eye {dx}", "sphere", (cx+dx,cy-.219,2.055), (.032,.024,.045), black)
add("Nose", "sphere", (cx,cy-.255,1.99), (.058,.07,.064), skin)
box("Smile", (cx,cy-.224,1.87), (.075,.018,.016), "#9A5346", rotation=(0,8,0))
for z in (1.17,1.35,1.52):
    add(f"Shirt button {z}", "sphere", (cx,cy-.19,z), (.018,.014,.018), "#B18C45")
# Left arm on hip; right forearm points up at the building.
add("Left sleeve", "sphere", (cx-.36,cy,1.47), (.14,.16,.20), yellow, rotation=(0,-22,0))
add("Left forearm", "cylinder", (cx-.41,cy-.03,1.19), (.075,.075,.20), skin, rotation=(0,-20,0))
add("Left hand", "sphere", (cx-.32,cy-.08,1.03), (.09,.075,.10), skin)
add("Right sleeve", "sphere", (cx+.37,cy,1.49), (.14,.16,.20), yellow, rotation=(0,-40,0))
add("Right forearm", "cylinder", (cx+.58,cy,1.72), (.075,.075,.25), skin, rotation=(0,32,0), keys=[
    {"time":0,"rotation":[0,48,0]}, {"time":2,"rotation":[0,27,0]}, {"time":5,"rotation":[0,27,0]}])
add("Pointing hand", "sphere", (cx+.70,cy,1.95), (.09,.075,.11), skin)
add("Pointing finger", "cylinder", (cx+.75,cy,2.10), (.026,.026,.10), skin, rotation=(0,17,0))

# An original, quiet musical cue; no external audio service or downloaded music.
rate = 44100
notes = [(0.1, 523.25), (.42,659.25), (.74,783.99), (2.3,659.25), (2.62,783.99), (3,1046.5)]
with wave.open(str(ASSETS / "elevator-sample-chime.wav"), "wb") as output:
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(rate)
    samples = []
    for n in range(rate*5):
        t = n/rate
        signal = 0
        for start, frequency in notes:
            dt = t-start
            if 0 <= dt < 1.6:
                envelope = min(1,dt/.012)*math.exp(-4*dt)
                signal += .12*envelope*(math.sin(2*math.pi*frequency*dt)+.18*math.sin(4*math.pi*frequency*dt))
        samples.append(struct.pack("<h", int(max(-1,min(1,signal))*32767)))
    output.writeframes(b"".join(samples))

source = Path("C:/Users/thanh/.codex/attachments/49e90e4c-8179-44e0-8ee1-7363980698ce/Pasted text.txt").read_text(encoding="utf-8")
scene = SceneSpec(title="Ngôi nhà 10 tầng — thử 5 giây", prompt="Tạo thử 5 giây với script này. Cảnh 1, mở đầu, giữ kín tên phát minh.", content=source,
    duration=5, fps=24, width=540, height=960, background=cream, floor=cream,
    camera={"location":[12,-24,13], "target":[-.2,0,5.0], "end_location":[10.5,-22.7,13.2], "lens":47},
    objects=objects, font="sample-arial-bold.ttf", audio="elevator-sample-chime.wav")
path = ROOT / "examples" / "elevator-opening-5s.json"
path.write_text(scene.model_dump_json(indent=2),encoding="utf-8")
print(f"Saved {len(objects)} objects: {path}")
