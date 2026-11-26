"""Build real reusable Blender meshes inspired by the user's four art references.

Run with the project's bpy-enabled Python. No reference image is used as a mesh,
texture billboard or substitute for geometry. Every asset has a GLB, editable
blend, thumbnail and Studio sidecar metadata. Z up, front faces negative Y.
"""
import argparse
import json
import math
import os
from pathlib import Path
import random
import shutil
import sys

from codex_blender.config import ROOT, assets_dir

RUN = ROOT / "outputs" / "inventor-toy-kit"
RUN.mkdir(parents=True, exist_ok=True)
os.environ["BLENDER_USER_RESOURCES"] = str(RUN / "blender-user")
(RUN / "blender-user").mkdir(exist_ok=True)

import bpy
from mathutils import Vector

PALETTE = {
    "skin": "#FFC18C", "skin_dark": "#EFA26A", "cheek": "#F5A078", "cream": "#F2D5AC",
    "stone": "#E6BC8A", "stone_light": "#FFE1B4", "gold": "#E9A62E", "gold_light": "#FFD16C",
    "shirt": "#FFCF65", "shirt_light": "#FFDF90", "copper": "#BA7139", "leather": "#774A38",
    "brown": "#956044", "brown_dark": "#5B3D35", "hair": "#292733", "hair_light": "#36323C",
    "boot": "#343644", "sole": "#262735", "blue": "#4D91C4", "blue_light": "#98D4ED",
    "steel": "#7C8799", "steel_light": "#B6BEC7", "dark_steel": "#465064", "white": "#FFF5E7",
    "mouth": "#5B2428", "tongue": "#E57375", "red": "#BD5343", "green": "#8EAE46", "green_dark": "#61803C",
    "soil": "#654C38", "paper": "#F8D8A5", "lamp": "#FFDC81", "background": "#EFE5DF",
}
MATS = {}
PARENT = None
PART = 0


def color(value):
    value = PALETTE.get(value, value)
    rgb = [int(value[i:i+2], 16)/255 for i in (1,3,5)]
    return tuple(c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in rgb)+(1,)


def mat(key):
    if key not in MATS:
        material = bpy.data.materials.new("Toy / "+key)
        material.use_nodes = True
        shader = material.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = color(key)
        shader.inputs["Roughness"].default_value = .5
        if key in {"gold", "copper", "steel", "steel_light", "dark_steel"}:
            shader.inputs["Metallic"].default_value = .35
            shader.inputs["Roughness"].default_value = .34
        if key in {"blue", "blue_light"}:
            shader.inputs["Roughness"].default_value = .22
            shader.inputs["Metallic"].default_value = .15
        if key == "skin":
            shader.inputs["Subsurface Weight"].default_value = .055
        if key == "lamp":
            shader.inputs["Emission Color"].default_value = color("lamp")
            shader.inputs["Emission Strength"].default_value = 2
        MATS[key] = material
    return MATS[key]


def finish(obj, name, material, bevel=0):
    global PART
    PART += 1
    obj.name = f"{PART:04d}_{name}"
    obj.parent = PARENT
    obj.data.materials.append(mat(material))
    if bevel:
        b = obj.modifiers.new("Soft toy edges", "BEVEL")
        b.width, b.segments = bevel, 4
        b.affect = "EDGES"
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    if hasattr(obj.data, "polygons"):
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    return obj


def box(name, position, size, material="cream", bevel=.07, rotation=(0,0,0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler = [math.radians(v) for v in rotation]
    return finish(obj, name, material, min(bevel, min(size)*.43))


def sphere(name, position, size, material="skin"):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=1, location=position)
    obj = bpy.context.object
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, material)


def cyl(name, position, radius, length, material="gold", rotation=(0,0,0), bevel=.025, vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=length, location=position)
    obj = bpy.context.object
    obj.rotation_euler = [math.radians(v) for v in rotation]
    return finish(obj, name, material, min(bevel, length*.2, radius*.25))


def torus(name, position, major, minor, material="gold", rotation=(0,0,0)):
    bpy.ops.mesh.primitive_torus_add(major_segments=40, minor_segments=12, major_radius=major, minor_radius=minor, location=position)
    obj = bpy.context.object
    obj.rotation_euler = [math.radians(v) for v in rotation]
    return finish(obj, name, material)


def rod(name, a, b, radius, material="gold", rectangular=None):
    a,b = Vector(a),Vector(b)
    if rectangular:
        obj = box(name, (a+b)/2, (*rectangular,(b-a).length), material, .07)
    else:
        obj = cyl(name, (a+b)/2, radius, (b-a).length, material)
    obj.rotation_euler = (b-a).to_track_quat("Z","Y").to_euler()
    return obj


def tube(name, points, radius, material="gold", cyclic=False):
    data = bpy.data.curves.new(name,"CURVE")
    data.dimensions = "3D"
    data.resolution_u = 2
    data.bevel_depth, data.bevel_resolution = radius, 3
    spline = data.splines.new("POLY")
    spline.points.add(len(points)-1)
    for pt,value in zip(spline.points,points):
        pt.co = (*value,1)
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name,data)
    bpy.context.collection.objects.link(obj)
    return finish(obj,name,material)


def poly(name, points, thickness, material="gold", bevel=.02):
    """Extrude a polygon in XZ along Y. Points are world x,z coordinates."""
    n = len(points)
    vertices = [(x,-thickness/2,z) for x,z in points]+[(x,thickness/2,z) for x,z in points]
    faces = [tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    obj = bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    return finish(obj,name,material,bevel)


def ring(name, center, outer, inner, depth, material="gold", start=0, end=math.tau, segments=48):
    x,y,z = center
    angles = [start+(end-start)*i/segments for i in range(segments+1)]
    vertices = [(x+r*math.cos(a),y+dy,z+r*math.sin(a)) for dy in (-depth/2,depth/2) for r in (outer,inner) for a in angles]
    n=len(angles)
    faces=[]
    for i in range(n-1):
        faces += [(i,i+1,n+i+1,n+i),(2*n+i,3*n+i,3*n+i+1,2*n+i+1),
                  (i,2*n+i,2*n+i+1,i+1),(n+i,n+i+1,3*n+i+1,3*n+i)]
    faces += [(0,n,3*n,2*n),(n-1,3*n-1,4*n-1,2*n-1)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    return finish(obj,name,material,.012)


def buckle(name, pos, width, height, material="gold", thickness=.04):
    x,y,z=pos
    box(name+" top",(x,y,z+height/2),(width,thickness,thickness),material,.02)
    box(name+" bottom",(x,y,z-height/2),(width,thickness,thickness),material,.02)
    for sign in (-1,1):box(name+" side",(x+sign*width/2,y,z),(thickness,thickness,height),material,.02)
    box(name+" pin",(x+width*.13,y-.02,z),(width*.5,thickness*.7,thickness*.65),material,.01)


def gear(name, center=(0,0,.5), radius=.45, material="gold", teeth=10):
    x,y,z=center
    ring(name+" rim",center,radius*.78,radius*.38,.12,material)
    for i in range(teeth):
        angle=math.tau*i/teeth
        box(name+" tooth",(x+radius*.81*math.sin(angle),y,z+radius*.81*math.cos(angle)),
            (radius*.28,.12,radius*.32),material,.025,rotation=(0,math.degrees(angle),0))


def inventor(expression="smile", raised=False):
    for side in (-1,1):
        x=side*.24
        box("boot sole",(x,-.075,.055),(.46,.72,.11),"sole",.05)
        box("boot",(x,-.045,.23),(.43,.63,.31),"boot",.10)
        box("boot toe",(x,-.19,.19),(.43,.43,.24),"boot",.10)
        box("trouser",(x,.015,.70),(.37,.48,.73),"leather",.08,rotation=(0,side*-2,0))
        box("folded trouser cuff",(x,0,.44),(.43,.54,.18),"brown",.045)
        box("trouser pocket",(x+side*.12,-.247,.89),(.20,.055,.28),"brown",.025)
    box("hips",(0,.01,1.08),(.88,.51,.30),"leather",.08)
    box("shirt",(0,0,1.61),(.90,.55,.88),"shirt",.17)
    box("shirt button placket",(0,-.29,1.62),(.07,.024,.68),"shirt_light",.01)
    for z in (1.44,1.63,1.82):sphere("shirt button",(0,-.315,z),(.024,.014,.024),"gold")
    for side in (-1,1):
        collar=poly("pointed collar",[(side*.025,2.06),(side*.31,1.99),(side*.17,1.82)],.065,"shirt_light")
        collar.location.y=-.285
        box("front suspender",(side*.28,-.305,1.65),(.115,.055,.80),"leather",.025,rotation=(0,side*3,0))
        buckle("suspender buckle",(side*.28,-.35,1.46),.155,.17,"copper",.035)
    box("belt",(0,-.005,1.17),(.96,.62,.16),"brown_dark",.055)
    buckle("belt buckle",(0,-.35,1.17),.29,.21,"steel_light",.055)
    cyl("neck",(0,0,2.10),.16,.24,"skin")
    box("head",(0,0,2.68),(1.26,.96,1.16),"skin",.25)
    for side in (-1,1):
        box("ear",(side*.67,-.015,2.64),(.23,.28,.39),"skin",.09)
        box("ear inner",(side*.69,-.17,2.65),(.12,.025,.22),"skin_dark",.04)
        box("eye white",(side*.28,-.490,2.72),(.29,.055,.39),"white",.10)
        box("eye pupil",(side*.278,-.525,2.71),(.19,.04,.30),"hair",.07)
        sphere("eye glint",(side*.278-.035,-.553,2.80),(.043,.016,.048),"white")
        z=3.01 if expression!="surprised" else 3.08
        box("eyebrow",(side*.28,-.49,z),(.32,.07,.12),"hair",.04,rotation=(0,side*(-7 if expression=="happy" else 2),0))
        sphere("cheek",(side*.43,-.482,2.49),(.105,.015,.05),"cheek")
    box("nose",(0,-.54,2.58),(.17,.15,.16),"skin_dark",.045)
    if expression=="happy":
        box("open smile",(0,-.494,2.36),(.43,.05,.26),"mouth",.10)
        box("smile teeth",(0,-.532,2.44),(.32,.028,.07),"white",.025)
        sphere("tongue",(0,-.531,2.28),(.12,.012,.045),"tongue")
    elif expression=="surprised":
        sphere("surprised mouth",(0,-.507,2.35),(.10,.022,.14),"mouth")
    else:
        tube("smile",[(.24*math.cos(a),-.51,2.43+.10*math.sin(a)) for a in [math.pi+i*math.pi/24 for i in range(25)]],.018,"brown_dark")
    # Sculptural locks: chunky overlapping rounded blocks, rather than a spherical cap.
    box("hair base",(0,.11,3.10),(1.31,.93,.46),"hair",.15)
    for side in (-1,1):
        box("temple lock",(side*.59,-.15,2.99),(.25,.36,.50),"hair",.08,rotation=(0,side*-8,0))
        box("sideburn",(side*.53,-.35,2.91),(.16,.16,.32),"hair_light",.045)
        for i in range(3):
            box("side hair lock",(side*.59,.03+i*.24,3.02-i*.08),(.29,.35,.42),"hair" if i%2 else "hair_light",.08,rotation=(side*5,side*-12,-side*7))
    for i,(x,z,tilt) in enumerate([(-.43,3.20,-17),(-.12,3.19,16),(.22,3.20,-22),(.48,3.18,-5)]):
        box("forelock",(x,-.31,z),(.42,.37,.46),"hair_light" if i%2 else "hair",.09,rotation=(9,tilt,0))
    for x in (-.42,0,.42):
        box("rear hair lock",(x,.52,2.94),(.44,.28,.52),"hair",.08)
        box("top hair tuft",(x,.16,3.37),(.44,.48,.25),"hair_light",.065,rotation=(0,-8,6))
    # Pilot goggles with a double rim and glass highlights, sitting on the hair.
    for side in (-1,1):
        box("goggle strap side",(side*.66,.12,3.26),(.09,.67,.16),"leather",.025,rotation=(12,0,0))
        x=side*.32
        box("goggle leather backing",(x,-.25,3.43),(.61,.21,.48),"brown_dark",.13,rotation=(24,side*-7,side*-6))
        box("goggle copper frame",(x,-.32,3.46),(.56,.18,.44),"copper",.12,rotation=(24,side*-7,side*-6))
        box("goggle dark gasket",(x,-.421,3.47),(.44,.03,.33),"dark_steel",.10,rotation=(24,side*-7,side*-6))
        box("goggle lens",(x,-.44,3.48),(.37,.025,.27),"blue",.08,rotation=(24,side*-7,side*-6))
        box("lens glint",(x-.07,-.459,3.50),(.075,.012,.20),"blue_light",.015,rotation=(24,-23,0))
        box("strap buckle",(side*.70,.04,3.29),(.07,.20,.21),"gold",.035)
    rod("goggle bridge",(-.08,-.30,3.43),(.08,-.30,3.43),.055,"leather")
    # Backpack and rolled drawings; all details remain actual geometry in the GLB.
    box("backpack",(0,.46,1.60),(.79,.40,.83),"leather",.10)
    box("backpack flap",(0,.70,1.90),(.84,.12,.29),"brown_dark",.07)
    for side in (-1,1):
        box("backpack pocket",(side*.26,.70,1.46),(.24,.12,.32),"brown",.04)
        box("back strap",(side*.25,.25,1.73),(.10,.13,.69),"brown",.025)
    box("backpack clasp",(0,.79,1.75),(.18,.05,.18),"gold",.04)
    for x,z in ((-.23,2.04),(.20,2.11)):
        cyl("rolled drawing",(x,.48,z),.10,.83,"paper")
        cyl("roll inner shadow",(x,.48,z+.42),.073,.018,"copper")
        torus("paper lip",(x,.48,z+.43),.083,.015,"paper")
        tube("paper spiral",[(x+(.01+.05*t)*math.cos(t*math.tau*1.5),.48+(.01+.05*t)*math.sin(t*math.tau*1.5),z+.445) for t in [i/40 for i in range(41)]],.008,"paper")
    box("tool pouch",(-.52,-.20,1.00),(.31,.25,.43),"copper",.06,rotation=(0,7,0))
    box("pouch lip",(-.52,-.22,1.21),(.34,.29,.09),"gold",.025)
    rod("screwdriver shaft",(-.58,-.21,1.12),(-.58,-.21,1.43),.025,"steel_light")
    box("red screwdriver grip",(-.58,-.21,1.46),(.10,.11,.22),"red",.04,rotation=(0,5,0))
    rod("wrench handle",(-.40,-.22,1.07),(-.40,-.22,1.45),.045,"steel_light")
    ring("wrench fork",(-.40,-.22,1.48),.10,.052,.065,"steel_light",start=math.radians(35),end=math.radians(325),segments=28)
    for side in (-1,1):
        shoulder=Vector((side*.48,0,1.87))
        if raised and side==1:
            elbow=Vector((.83,-.015,1.63));wrist=Vector((1.03,-.10,2.13))
        else:
            elbow=Vector((side*.65,-.005,1.52));wrist=Vector((side*.79,-.06,1.22))
        upper=rod("shirt sleeve",shoulder,elbow,0,"shirt",(.34,.44))
        direction=(elbow-shoulder).normalized()
        cuff=box("rolled sleeve cuff",elbow-direction*.04,(.39,.49,.18),"shirt_light",.055)
        cuff.rotation_euler=upper.rotation_euler
        rod("forearm",elbow,wrist,0,"skin",(.27,.32))
        hand=box("hand",wrist,(.31,.36,.30),"skin",.10)
        if raised and side==1:
            hand.rotation_euler.y=math.radians(-12)
        box("thumb",(wrist.x-side*.13,wrist.y-.12,wrist.z+.02),(.12,.15,.17),"skin",.055)
    PARENT.scale = (.51,.51,.51)


BUILDERS = {}


def register(slug,name,description,tags):
    def wrap(fn):
        BUILDERS[slug]=(name,description,tags,fn)
        return fn
    return wrap


register("inventor-smile","Nhà phát minh • nụ cười","Nhân vật chibi tóc đen dạng khối, kính phi công đồng với tròng xanh, áo vàng, dây đeo nâu, ba lô bản vẽ và túi dụng cụ. Hai tay hạ tự nhiên. Tư thế tĩnh.",["nhân vật","inventor-toy","smile"])(lambda:inventor("smile"))
register("inventor-cheer","Nhà phát minh • hào hứng","Cùng một nhân vật và trang phục với bản nụ cười; miệng cười mở, tay phải giơ nắm đấm. Tư thế tĩnh.",["nhân vật","inventor-toy","happy"])(lambda:inventor("happy",True))
register("inventor-surprised","Nhà phát minh • ngạc nhiên","Cùng thiết kế nhân vật, mắt mở to, chân mày cao và miệng chữ O. Tư thế tĩnh.",["nhân vật","inventor-toy","surprised"])(lambda:inventor("surprised"))


def window(center=(0,0,1.3),width=1.05,height=1.25,arched=False):
    x,y,z=center
    box("window outer stone",(x,y,z),(width+.26,.22,height+.27),"stone_light",.09)
    box("wooden window frame",(x,y-.13,z),(width+.04,.11,height+.04),"copper",.065)
    box("blue window",(x,y-.194,z),(width-.13,.025,height-.12),"blue",.04)
    box("window reflection",(x-width*.17,y-.212,z+.04),(width*.15,.01,height*.76),"blue_light",.02,rotation=(0,-15,0))
    box("window mullion",(x,y-.23,z),(.065,.06,height-.08),"gold",.015)
    box("stone sill",(x,y-.09,z-height/2-.10),(width+.40,.43,.14),"stone_light",.04)
    if arched:
        # Curved upper transom and separate voussoir stones form an actual arch.
        box("window upper infill",(x,y-.03,z+height*.38),(width,.18,.45),"blue",.05)
        for i in range(7):
            a=i*math.pi/7+.025;b=(i+1)*math.pi/7-.025
            obj=ring("arched window stone",(x,y-.09,z+height*.37),width*.64,width*.47,.24,
                     "stone_light" if i%2 else "stone",start=a,end=b,segments=5)
        box("window cross bar",(x,y-.25,z+.15),(width-.08,.06,.07),"gold",.015)


def arch_entry():
    for side in (-1,1):
        box("stone jamb",(side*.95,0,.90),(.35,.42,1.8),"stone",.07)
        box("jamb base",(side*.95,-.015,.18),(.45,.5,.36),"brown_dark",.07)
        for j in range(3):box("jamb block",(side*.95,-.235,.46+j*.49),(.38,.07,.43),"stone_light",.045)
    for i in range(9):
        a=i*math.pi/9+.013;b=(i+1)*math.pi/9-.013
        ring("arch wedge",(0,0,1.76),1.13,.79,.45,"brown" if i%2 else "stone",start=a,end=b,segments=5)
    box("golden keystone",(0,-.27,2.83),(.34,.16,.42),"gold",.06)
    cyl("keystone rivet",(0,-.37,2.83),.08,.025,"gold_light",rotation=(90,0,0))
    for side in (-1,1):
        box("door leaf",(side*.37,-.02,.89),(.72,.16,1.71),"leather",.055)
        box("door window",(side*.37,-.116,1.19),(.47,.02,.80),"blue",.025)
        box("door handle",(side*.12,-.18,.84),(.055,.07,.31),"steel_light",.025)
        box("entry lamp frame",(side*1.15,-.19,1.13),(.20,.16,.51),"copper",.055)
        box("entry warm light",(side*1.15,-.29,1.13),(.12,.04,.36),"lamp",.035)
    box("door threshold",(0,-.13,.075),(2.55,.80,.15),"stone_light",.045)


def stairs(width=1.32,run=3.0,height=2.3,steps=12,offset=(0,0,0),reverse=False,railing=True):
    ox,oy,oz=offset
    sign=-1 if reverse else 1
    for i in range(steps):
        top=height*(i+1)/steps
        y=oy+sign*(-run/2+(i+.5)*run/steps)
        box("solid stair step",(ox,y,oz+top/2),(width,run/steps+.012,top),"stone_light",.027)
    if railing:
        for side in (-1,1):
            x=ox+side*(width/2+.035)
            a=(x,oy-sign*run*.46,oz+.82);b=(x,oy+sign*run*.46,oz+height+.64)
            rod("sloping handrail",a,b,.045,"brown")
            for t in (.02,.32,.65,.98):
                y=a[1]+(b[1]-a[1])*t
                z=a[2]+(b[2]-a[2])*t
                rod("stair baluster",(x,y,z-.68),(x,y,z),.026,"gold")


def planter(center=(0,0,0),scale=1):
    x,y,z=center;s=scale
    box("terracotta planter",(x,y,z+.22*s),(.62*s,.52*s,.44*s),"brown",.055*s)
    box("planter rim",(x,y,z+.42*s),(.70*s,.60*s,.11*s),"stone",.03*s)
    box("soil",(x,y,z+.46*s),(.54*s,.44*s,.025*s),"soil",.01)
    for dx,dy,dz,size in [(-.15,0,.66,.32),(.14,.05,.70,.36),(0,-.09,.87,.33)]:
        box("topiary leaves",(x+dx*s,y+dy*s,z+dz*s),(size*s,size*s,size*.82*s),"green" if dx else "green_dark",.09*s)


def balcony(center=(0,0,0),width=1.3):
    x,y,z=center
    box("balcony slab",(x,y,z),(width,.85,.18),"brown",.055)
    for side in (-1,1):
        box("balcony post",(x+side*width*.45,y-.35,z+.40),(.075,.08,.72),"leather",.02)
        cyl("balcony post cap",(x+side*width*.45,y-.35,z+.78),.075,.08,"gold")
    box("balcony top rail",(x,y-.35,z+.66),(width,.09,.10),"brown_dark",.025)
    for dx in (-.3,0,.3):box("balcony upright",(x+dx,y-.35,z+.37),(.045,.05,.53),"gold",.01)
    planter((x,y+.03,z+.10),.65)


def story(level=0,cutaway=False,details=True):
    z=level*2.3
    box("floor band",(0,0,z+.10),(5.1,4.05,.20),"brown",.065)
    box("floor cream tile",(0,0,z+.24),(4.70,3.7,.12),"stone_light",.035)
    # Tiles split around a real stairwell opening in the cutaway version.
    if cutaway:
        for side in (-1,1):
            box("room back wall",(side*1.6,1.82,z+1.30),(1.8,.20,2.0),"cream",.075)
        # Replace the broad solid floor with side room floors and a rear landing.
        # Hide only objects just added by their known local semantic names.
        for obj in list(bpy.context.scene.objects):
            if "floor cream tile" in obj.name and abs(obj.location.z-(z+.24))<.01:
                bpy.data.objects.remove(obj,do_unlink=True)
        for side in (-1,1):box("room floor",(side*1.63,0,z+.24),(1.45,3.6,.12),"stone_light",.025)
        box("rear landing",(0,1.52,z+.24),(1.80,.62,.12),"stone_light",.025)
        stairs(width=1.32,run=2.8,height=2.3,steps=12,offset=(0,0,z+.3),reverse=level%2==1)
        # Small desks give the opened rooms a readable sense of use.
        if details:
            for side in (-1,1):
                x=side*1.66
                box("desk top",(x,.44,z+.94),(1.0,.68,.10),"copper",.04)
                for dx in (-.35,.35):box("desk leg",(x+dx,.44,z+.63),(.075,.50,.58),"leather",.02)
                box("desk book",(x-.15,.43,z+1.04),(.32,.25,.10),"blue",.02)
                window((x,1.70,z+1.42),.7,.85)
    else:
        box("front cream wall",(0,-1.78,z+1.30),(4.60,.21,2.03),"cream",.07)
        box("rear cream wall",(0,1.78,z+1.30),(4.60,.21,2.03),"cream",.07)
        for x in (-1.15,1.15):
            window((x,-1.93,z+1.32),.91,1.10)
            if details:window((x,1.93,z+1.32),.91,1.10)
        box("front central column",(0,-1.97,z+1.27),(.35,.24,2.20),"brown",.055)
        box("rear central column",(0,1.97,z+1.27),(.35,.24,2.20),"brown",.055)
        for zz in (.65,1.82):
            box("horizontal masonry seam",(0,-1.899,z+zz),(4.55,.025,.028),"stone_light",.008)
    for side in (-1,1):
        box("side cream wall",(side*2.25,0,z+1.30),(.19,3.55,2.02),"cream",.07)
        for y in (-1.50,1.50):box("corner stone",(side*2.30,y,z+1.32),(.31,.36,2.12),"stone_light",.07)
        if details:
            balcony((side*2.30,-.35,z+.20),.88)


def roof(z):
    box("roof cornice",(0,0,z+.17),(5.40,4.3,.34),"brown",.10)
    box("roof light surface",(0,0,z+.38),(4.95,3.88,.12),"stone_light",.035)
    for side in (-1,1):
        box("roof parapet",(side*2.5,0,z+.61),(.22,4.10,.38),"brown_dark",.055)
    box("roof rear parapet",(0,1.94,z+.62),(5.1,.23,.38),"brown_dark",.055)
    box("roof room",(.55,.44,z+1.28),(2.18,1.74,1.55),"stone",.09)
    window((.55,-.47,z+1.34),1.65,.96)
    box("roof room cap",(.55,.44,z+2.13),(2.54,2.05,.27),"brown",.08)
    cyl("roof water drum",(-1.5,.65,z+1.05),.47,1.25,"gold")
    for zz in (.53,1.55):cyl("water drum band",(-1.5,.65,z+zz),.51,.13,"brown",bevel=.025)
    # Small dish, mast and flag are entirely geometric.
    rod("dish mast",(-1.43,-.45,z+.48),(-1.43,-.45,z+1.85),.08,"brown_dark")
    sphere("satellite dish",(-1.43,-.45,z+1.96),(.57,.17,.40),"cream")
    rod("dish receiver",(-1.43,-.62,z+1.95),(-1.43,-.98,z+2.13),.045,"copper")
    rod("flag pole",(2.05,.8,z+.4),(2.05,.8,z+2.8),.035,"brown_dark")
    box("orange flag",(2.44,.8,z+2.40),(.72,.065,.53),"gold",.04)
    # Plain small gear badge, with no words or logos.
    gear("flag gear",(2.44,.748,z+2.40),.18,"white",8)


def tower(cutaway=False):
    box("foundation",(0,0,.12),(5.65,4.45,.24),"brown_dark",.08)
    for i in range(10):story(i,cutaway,details=True)
    roof(23.0)
    if not cutaway:
        # Ground-floor portal in front of the existing facade, scale suitable for a 1.9-unit character.
        before=set(bpy.context.scene.objects)
        arch_entry()
        for obj in set(bpy.context.scene.objects)-before:obj.location.y-=2.20
        cyl("entry gear backing",(0,-2.10,3.1),.53,.12,"brown_dark",rotation=(90,0,0))
        gear("entry emblem",(0,-2.20,3.1),.48,"gold",10)
        for side in (-1,1):planter((side*1.7,-2.2,.24),.86)


register("building-ten-floors","Tòa nhà 10 tầng • Toy Inventor","Tòa nhà 10 tầng, tường kem, viền nâu bo tròn, kính xanh, ban công cây xanh, cổng vòm và huy hiệu bánh răng; mái có phòng, bồn nước và cờ. Mặt ngoài hoàn chỉnh.",["kiến trúc","inventor-toy","10 tầng"])(lambda:tower(False))
register("building-cutaway","Tòa nhà 10 tầng • cắt lớp Toy Inventor","Cùng kiến trúc với bản bên ngoài, mặt trước mở để thấy cầu thang nối các tầng, bàn và cửa sổ bên trong. Dùng cho cảnh giải thích việc leo thang.",["kiến trúc","inventor-toy","cắt lớp"])(lambda:tower(True))
register("floor-module","Tầng nhà • mặt ngoài","Mô-đun một tầng nhà, kem-nâu, cửa sổ kính xanh và ban công cây xanh. Bước lặp theo Z là 2.3 đơn vị.",["modular","inventor-toy","kiến trúc"])(lambda:story(0,False))
register("floor-cutaway","Tầng nhà • cắt lớp","Mô-đun tầng cắt lớp với phòng hai bên và cầu thang ở giữa. Bước lặp Z=2.3; cầu thang có tay vịn và bậc đặc.",["modular","inventor-toy","cầu thang"])(lambda:story(0,True))
register("stair-flight","Cầu thang • mô-đun","Một vế cầu thang bậc kem, tay vịn nâu-vàng. Chiều cao nối tầng 2.3 đơn vị, có thể xoay 180 độ cho tầng kế tiếp.",["modular","inventor-toy","cầu thang"])(stairs)
register("arched-window","Cửa sổ vòm • kính xanh","Cửa sổ kính xanh với khung vàng và đá vòm kem. Mặt trước hướng -Y.",["kiến trúc","inventor-toy"])(lambda:window((0,0,.95),1.15,1.25,True))
register("arched-entry","Cổng vòm • đèn ấm","Cổng đá vòm bo tròn, cửa đôi gỗ với ô kính xanh, khóa vàng và hai đèn phát sáng màu ấm.",["kiến trúc","inventor-toy"])(arch_entry)
register("balcony","Ban công • cây xanh","Lan can nâu-vàng, mặt sàn bo tròn và chậu cây dạng khối.",["kiến trúc","inventor-toy","modular"])(balcony)


def cabin(opened=True,offset=(0,0,0)):
    x,y,z=offset
    box("cabin foundation",(x,y,z+.10),(1.95,1.58,.20),"brown_dark",.07)
    box("cabin tiled floor",(x,y,z+.24),(1.70,1.35,.10),"steel",.03)
    for dx in (-.57,0,.57):box("floor tile seam",(x+dx,y,z+.297),(.012,1.32,.006),"dark_steel",.001)
    box("cabin rear wall",(x,y+.69,z+1.17),(1.77,.13,1.79),"stone",.055)
    for side in (-1,1):
        box("cabin side",(x+side*.87,y,z+1.16),(.14,1.35,1.77),"dark_steel",.06)
        box("cabin side window",(x+side*.95,y-.06,z+1.24),(.026,.75,1.02),"blue",.045)
        box("front corner post",(x+side*.85,y-.73,z+1.16),(.17,.20,1.83),"brown",.055)
        box("cream inner doorway",(x+side*.73,y-.76,z+1.14),(.11,.17,1.65),"stone_light",.035)
        box("side handrail",(x+side*.70,y+.10,z+1.05),(.055,.92,.055),"gold",.02)
    box("rear handrail",(x,y+.56,z+1.05),(1.40,.07,.07),"steel_light",.025)
    box("cabin roof",(x,y,z+2.12),(2.10,1.69,.25),"brown",.08)
    box("ceiling lamp surround",(x,y-.07,z+1.975),(.85,.66,.08),"gold",.035)
    box("ceiling warm light",(x,y-.08,z+1.93),(.69,.53,.025),"lamp",.03)
    box("upper display frame",(x,y-.89,z+2.11),(.56,.12,.17),"brown_dark",.04)
    box("upper warm indicator",(x,y-.965,z+2.11),(.40,.025,.08),"lamp",.02)
    for side in (-1,1):
        box("corner foot",(x+side*.82,y-.76,z+.18),(.23,.23,.30),"gold",.055)
        box("roof hanger",(x+side*.53,y,z+2.34),(.15,.19,.31),"steel",.04)
        cyl("hanger pin",(x+side*.53,y-.12,z+2.38),.055,.08,"gold",rotation=(90,0,0))
    if opened:
        box("interior control frame",(x+.59,y+.53,z+1.20),(.24,.09,.62),"brown_dark",.035)
        for i in range(4):box("interior button",(x+.59,y+.465,z+.99+i*.15),(.13,.035,.10),"lamp" if i==3 else "steel_light",.025)
    else:
        for side in (-1,1):
            box("sliding door leaf",(x+side*.355,y-.76,z+1.12),(.695,.07,1.60),"steel_light",.035)
            box("door inlay",(x+side*.355,y-.807,z+1.12),(.60,.018,1.48),"steel",.035)
        box("door central seam",(x,y-.82,z+1.13),(.014,.014,1.58),"dark_steel",.002)


def pulley(offset=(0,0,0),radius=.65):
    x,y,z=offset
    box("sheave base",(x,y+.07,z+.10),(1.75,.87,.20),"brown",.065)
    for side in (-1,1):
        box("sheave bearing support",(x+side*.50,y+.10,z+.47),(.22,.50,.67),"dark_steel",.05)
        cyl("base bolt",(x+side*.65,y-.22,z+.22),.075,.05,"steel_light")
    center=(x,y-.07,z+.91)
    torus("sheave gold rim",center,radius-.09,.10,"gold",rotation=(90,0,0))
    torus("cable groove front",(x,y-.17,z+.91),radius-.06,.027,"brown_dark",rotation=(90,0,0))
    torus("cable groove rear",(x,y+.04,z+.91),radius-.06,.027,"brown_dark",rotation=(90,0,0))
    for i in range(8):
        a=math.tau*i/8
        rod("sheave spoke",(x+.12*math.cos(a),y-.07,z+.91+.12*math.sin(a)),
            (x+(radius-.14)*math.cos(a),y-.07,z+.91+(radius-.14)*math.sin(a)),.065,"gold")
    cyl("sheave hub",center,.19,.31,"copper",rotation=(90,0,0))
    cyl("sheave axle cap",(x,y-.28,z+.91),.145,.12,"steel_light",rotation=(90,0,0))


def motor(offset=(0,0,0)):
    x,y,z=offset
    box("motor base",(x,y,z+.07),(1.48,.95,.14),"brown",.06)
    for side in (-1,1):
        box("motor foot",(x+side*.42,y,z+.22),(.21,.67,.21),"steel",.04)
        for yy in (-.31,.31):cyl("motor mounting bolt",(x+side*.45,y+yy,z+.18),.065,.05,"steel_light")
    cyl("motor barrel",(x,y,z+.66),.40,.99,"dark_steel",rotation=(0,90,0))
    for xx in (-.45,-.30,-.15,0,.15,.30,.45):
        torus("motor cooling fin",(x+xx,y,z+.66),.393,.034,"steel",rotation=(0,90,0))
    cyl("motor end cap",(x-.57,y,z+.66),.41,.18,"steel",rotation=(0,90,0))
    cyl("motor gold cover",(x-.69,y,z+.66),.29,.12,"gold",rotation=(0,90,0))
    cyl("motor output shaft",(x+.65,y,z+.66),.12,.32,"steel_light",rotation=(0,90,0))
    box("motor junction box",(x-.1,y,z+1.10),(.40,.40,.19),"dark_steel",.055)


def counterweight(offset=(0,0,0),blocks=4):
    x,y,z=offset
    for i in range(blocks):box("counterweight block",(x,y,z+.17+i*.31),(.91,.43,.29),"steel",.055)
    height=blocks*.31
    top=z+height
    box("counterweight gold top",(x,y,top+.05),(1.0,.48,.17),"gold",.04)
    for side in (-1,1):
        box("counterweight hanger",(x+side*.31,y,top+.20),(.18,.20,.34),"gold",.045)
        cyl("counterweight pin",(x+side*.31,y-.13,top+.25),.064,.07,"dark_steel",rotation=(90,0,0))
        box("weight frame side",(x+side*.45,y+.18,z+height*.5),(.06,.06,height),"dark_steel",.01)


def cable(offset=(0,0,0),height=2.7):
    x,y,z=offset
    rod("steel cable core",(x,y,z),(x,y,z+height),.035,"dark_steel")
    for strand in range(3):
        points=[]
        for i in range(161):
            t=i/160;angle=t*math.tau*height/.15+strand*math.tau/3
            points.append((x+.031*math.cos(angle),y+.031*math.sin(angle),z+t*height))
        tube("braided cable strand",points,.012,"steel_light")
    for zz in (z+.05,z+height-.05):cyl("cable end collar",(x,y,zz),.065,.10,"steel")


def shaft():
    # A static, assembled teaching model. Cabin and counterweight remain separate named meshes.
    box("shaft foundation",(0,0,.15),(4.65,2.4,.30),"brown",.08)
    for side in (-1,1):
        for zz in range(5):box("shaft stone column block",(side*2.08,.45,1.25+zz*2.0),(.43,.70,1.91),"cream",.08)
    for z in (.40,2.60,4.80,7.05,8.25,10.25):box("shaft horizontal lintel",(0,.45,z),(4.65,.85,.30),"brown",.08)
    for x in (-1.45,.43,1.52):
        rod("vertical guide rail",(x,.35,.35),(x,.35,8.05),.055,"dark_steel")
        for z in (1.0,3.2,5.5,7.7):box("rail clamp",(x,.32,z),(.18,.22,.15),"steel",.03)
    cabin(True,(-.52,-.30,.45))
    counterweight((1.32,.02,4.75))
    pulley((.28,-.20,6.59),.93)
    motor((.35,.47,8.40))
    cable((-.55,-.27,2.89),4.61)
    cable((1.10,-.27,6.18),1.32)
    # Wrap the top rope across the sheave so the two runs belong to one mechanism.
    tube("rope over sheave",[(.28+.83*math.cos(a),-.27,7.50+.83*math.sin(a)) for a in [i*math.pi/48 for i in range(49)]],.035,"dark_steel")
    for i in range(8):
        box("threshold warning stripe",(-1.5+i*.42,-.87,.313),(.25,.48,.015),"gold" if i%2 else "dark_steel",.003,rotation=(0,0,-22))


def call_panel():
    box("call button backplate",(0,0,.44),(.38,.16,.88),"dark_steel",.09)
    box("call button inset",(0,-.10,.44),(.28,.045,.75),"steel",.055)
    for z,sign in ((.65,1),(.26,-1)):
        points=[(-.085,z-sign*.045),(.085,z-sign*.045),(0,z+sign*.09)]
        obj=poly("call arrow",points,.035,"gold");obj.location.y=-.15
    for x in (-.115,.115):
        for z in (.10,.78):cyl("panel screw",(x,-.135,z),.02,.02,"gold",rotation=(90,0,0))


register("cabin-open","Cabin thang máy • mở","Cabin mở nhìn vào trong, trần đèn ấm, tay vịn, sàn gạch, bảng nút bấm và ô kính hai bên. Tỷ lệ nhân vật Toy Inventor 1.9 đơn vị.",["thang máy","inventor-toy","cabin"])(lambda:cabin(True))
register("cabin-closed","Cabin thang máy • đóng","Cùng thiết kế cabin, có hai cánh cửa trượt kim loại đóng ở phía trước. Mô hình tĩnh; các cánh cửa giữ tên riêng trong .blend.",["thang máy","inventor-toy","cabin"])(lambda:cabin(False))
register("pulley-assembly","Cụm ròng rọc vàng","Bánh puly có vành, rãnh dây, tám nan, trục và giá đỡ. Trục quay theo Y, mặt bánh hướng -Y.",["cơ khí","inventor-toy","ròng rọc"])(pulley)
register("electric-motor","Động cơ điện • xanh thép","Động cơ bo tròn với thân có gân tản nhiệt, hộp điện, chân bu-lông và trục đầu ra dọc X.",["cơ khí","inventor-toy","động cơ"])(motor)
register("counterweight","Đối trọng • bốn khối","Bốn khối thép bo cạnh trong khung, đỉnh vàng với hai tai treo. Tách biệt để diễn hoạt ngược chiều cabin.",["cơ khí","inventor-toy","đối trọng"])(counterweight)
register("steel-cable","Cáp thép bện • 2.7 đơn vị","Đoạn cáp ba sợi bện thật bằng mesh, chiều dài theo Z=2.7; có vòng kẹp hai đầu.",["cơ khí","inventor-toy","cáp"])(cable)
register("elevator-shaft","Hệ thống thang máy • cắt lớp","Bản lắp tĩnh của khung giếng, cabin mở, đối trọng, ray, dây cáp, puly và động cơ. Dùng toàn cảnh giải thích; để diễn hoạt chính xác nên dùng các asset thành phần riêng.",["thang máy","inventor-toy","cắt lớp"])(shaft)
register("call-buttons","Bảng gọi thang • lên xuống","Bảng nút kim loại bo tròn có hai mũi tên lên/xuống màu vàng, đinh vít góc.",["thang máy","inventor-toy","đạo cụ"])(call_panel)


def wall_panel():
    box("wall backing",(0,.05,1.0),(2.6,.40,2.0),"stone",.06)
    for row in range(4):
        for col in range(3):
            x=-.86+col*.86+(.15 if row%2 else 0)
            box("cream masonry block",(x,-.18,.30+row*.45),(.80,.14,.40),"cream" if (row+col)%2 else "stone_light",.055)
    for z in (.12,2.02):box("brown wall cap",(0,-.02,z),(2.85,.63,.23),"brown_dark",.06)
    for side in (-1,1):box("wall end stone",(side*1.3,-.09,1.08),(.23,.5,1.73),"stone_light",.055)


def floor_tiles():
    box("tiled floor foundation",(0,0,.10),(2.9,2.9,.20),"brown",.07)
    for i in range(3):
        for j in range(3):box("floor tile",(-.94+i*.94,-.94+j*.94,.25),(.91,.91,.18),"stone_light" if (i+j)%2 else "cream",.055)


def rail():
    for side in (-1,1):
        box("rail foot",(side*.95,0,.12),(.28,.31,.24),"brown_dark",.045)
        box("rail post",(side*.95,0,.66),(.14,.16,1.0),"leather",.035)
        box("gold post cap",(side*.95,0,1.20),(.23,.25,.19),"gold",.05)
    box("top rail",(0,0,1.05),(2.0,.16,.15),"brown",.04)
    box("lower gold rail",(0,0,.32),(2.0,.12,.12),"gold",.035)
    for x in (-.47,0,.47):box("baluster",(x,0,.65),(.065,.075,.66),"gold",.02)


def water_tank():
    box("tank foundation",(0,0,.10),(1.75,1.75,.20),"brown",.055)
    for x in (-.55,.55):
        for y in (-.55,.55):box("tank leg",(x,y,.66),(.15,.15,1.04),"leather",.04)
    for y in (-.55,.55):
        rod("tank cross brace",(-.55,y,.27),(.55,y,1.10),.065,"brown")
        rod("tank cross brace",(.55,y,.27),(-.55,y,1.10),.065,"brown")
    cyl("tank blue barrel",(0,0,1.76),.69,1.31,"dark_steel")
    for z in (1.14,2.29):
        cyl("tank copper hoop",(0,0,z),.75,.14,"copper")
        for angle in [i*math.tau/8 for i in range(8)]:sphere("hoop rivet",(.75*math.sin(angle),.75*math.cos(angle),z),(.045,.045,.045),"gold")
    bpy.ops.mesh.primitive_cone_add(vertices=12,radius1=.82,radius2=.12,depth=.38,location=(0,0,2.57))
    finish(bpy.context.object,"tank cap","dark_steel",.035)
    cyl("tank top knob",(0,0,2.80),.16,.08,"steel")
    tube("tank outflow pipe",[(.66,0,1.61),(.99,0,1.61),(1.10,0,1.50),(1.10,0,.50)],.10,"steel")
    for z in (.57,1.41):cyl("pipe collar",(1.1,0,z),.13,.13,"dark_steel")


def sofa():
    for side in (-1,1):
        for y in (-.41,.41):box("sofa foot",(side*.9,y,.12),(.19,.19,.24),"brown_dark",.04)
    box("sofa base",(0,0,.40),(2.35,1.11,.43),"leather",.12)
    for x in (-.56,0,.56):
        box("seat cushion",(x,-.13,.70),(.56,.83,.25),"copper",.09)
        box("back cushion",(x,.35,1.11),(.57,.30,.93),"red",.10,rotation=(7,0,0))
    for side in (-1,1):
        box("sofa arm",(side*1.04,-.02,.83),(.34,1.13,.76),"copper",.13)
        box("sofa corner cap",(side*1.05,-.60,.42),(.22,.075,.16),"gold",.035)
    box("cream pillow",(-.37,-.05,1.03),(.50,.17,.47),"paper",.09,rotation=(7,-8,8))
    box("yellow pillow",(.39,-.04,1.04),(.48,.18,.48),"shirt",.09,rotation=(8,4,-9))


def lamp():
    cyl("lamp circular foot",(0,0,.08),.43,.16,"brown_dark")
    cyl("lamp gold base",(0,0,.19),.27,.14,"gold")
    rod("lamp post",(0,0,.25),(0,0,1.34),.075,"brown_dark")
    rod("lamp arm",(0,0,1.34),(.51,0,1.63),.065,"brown")
    for point in ((0,0,1.34),(.51,0,1.63)):cyl("lamp joint",point,.12,.18,"gold",rotation=(90,0,0))
    bpy.ops.mesh.primitive_cone_add(vertices=32,radius1=.38,radius2=.13,depth=.43,location=(.62,-.05,1.42))
    shade=finish(bpy.context.object,"lamp shade","brown_dark",.025)
    shade.rotation_euler=(math.radians(-12),math.radians(-12),0)
    cyl("lamp glowing diffuser",(.66,-.095,1.205),.30,.035,"lamp",rotation=(-12,-12,0))


def leafy_plant():
    box("plant pot",(0,0,.33),(.65,.65,.66),"brown",.08)
    box("plant pot rim",(0,0,.65),(.79,.79,.17),"stone",.055)
    box("plant soil",(0,0,.742),(.58,.58,.02),"soil",.005)
    for a,b in [((0,0,.73),(-.27,0,1.55)),((0,0,.73),(.29,.12,1.37)),((0,0,.73),(.04,-.13,1.73))]:
        rod("plant stem",a,b,.035,"green_dark")
        box("stylized leaf",b,(.46,.24,.34),"green",.09,rotation=(12,-24 if b[0]<0 else 23,20))


def toolbox():
    box("toolbox bottom",(0,0,.35),(1.05,.62,.62),"leather",.08)
    box("red toolbox lid",(0,0,.75),(1.12,.67,.28),"red",.085)
    for side in (-1,1):
        box("toolbox handle support",(side*.28,0,1.00),(.11,.14,.30),"gold",.035)
        for y in (-.29,.29):box("toolbox corner protector",(side*.46,y,.15),(.18,.12,.21),"gold",.04)
    box("toolbox handle",(0,0,1.14),(.62,.14,.13),"brown_dark",.05)
    box("toolbox latch",(0,-.365,.59),(.22,.10,.24),"steel_light",.045)
    box("latch inset",(0,-.425,.59),(.12,.02,.13),"dark_steel",.02)


def wrench():
    box("wrench grip",(0,0,.59),(.17,.12,.92),"steel_light",.07)
    ring("wrench lower ring",(0,0,.18),.18,.09,.13,"steel_light")
    ring("wrench open jaw",(0,0,1.18),.28,.15,.14,"steel_light",start=math.radians(125),end=math.radians(415),segments=32)
    cyl("grip inset",(0,-.075,.38),.058,.012,"dark_steel",rotation=(90,0,0))


def screwdriver():
    box("screwdriver red grip",(0,0,.31),(.24,.22,.62),"red",.075)
    cyl("screwdriver gold collar",(0,0,.66),.13,.10,"gold")
    cyl("screwdriver shaft",(0,0,.97),.045,.59,"steel_light")
    box("flat screwdriver tip",(0,0,1.29),(.09,.027,.15),"steel_light",.008)
    for side in (-1,1):box("grip groove",(side*.10,-.075,.32),(.025,.045,.34),"brown_dark",.01)


def crate():
    box("wood crate core",(0,0,.63),(1.22,1.12,1.20),"copper",.065)
    for side in (-1,1):
        for x in (-.44,0,.44):box("crate plank",(x,side*.583,.63),(.38,.075,1.14),"brown",.035)
        for z in (.10,1.17):box("crate horizontal frame",(0,side*.64,z),(1.36,.14,.20),"leather",.035)
        rod("crate diagonal brace",(-.51,side*.67,.21),(.51,side*.67,1.08),0,"stone",(.16,.10))
        for x in (-.58,.58):
            for z in (.11,1.16):
                box("crate corner metal",(x,side*.71,z),(.20,.06,.21),"steel",.025)
                cyl("crate rivet",(x,side*.75,z),.028,.023,"gold",rotation=(90,0,0))


def scroll():
    box("blueprint paper",(0,0,.73),(.92,.055,1.21),"paper",.035)
    for z in (.12,1.35):
        cyl("scroll paper roll",(0,0,z),.13,1.23,"paper",rotation=(0,90,0))
        for side in (-1,1):
            cyl("scroll roll end",(side*.62,0,z),.095,.025,"copper",rotation=(0,90,0))
            cyl("scroll paper inner",(side*.638,0,z),.055,.012,"paper",rotation=(0,90,0))
    # Blueprint marks use geometry, so the drawing survives without external textures.
    for side in (-1,1):box("drawing shaft side",(side*.25,-.04,.65),(.018,.012,.60),"steel",.004)
    box("drawing shaft top",(0,-.04,.96),(.52,.012,.018),"steel",.004)
    box("drawing cabin",(0,-.04,.52),(.30,.012,.26),"blue",.012)
    ring("drawing pulley",(0,-.05,.90),.09,.055,.012,"steel")
    for side in (-1,1):box("drawing rope",(side*.075,-.055,.73),(.012,.012,.29),"steel",.002)
    gear("drawing gear",(0,-.05,1.14),.12,"steel",8)


def arrow_sign():
    box("sign foot",(0,0,.09),(.65,.48,.18),"brown_dark",.05)
    box("sign post",(0,0,.68),(.14,.16,1.21),"leather",.035)
    shape=[(-.62,.94),(.24,.94),(.24,.75),(.69,1.20),(.24,1.65),(.24,1.45),(-.62,1.45)]
    poly("wood arrow sign",shape,.17,"brown",.04)
    shape=[(-.45,1.07),(.25,1.07),(.25,.96),(.50,1.20),(.25,1.46),(.25,1.33),(-.45,1.33)]
    obj=poly("gold arrow",shape,.045,"gold",.025);obj.location.y=-.13


register("stone-wall","Tường đá • kem nâu","Tấm tường gạch bo cạnh với các viên đá thật và hai gờ nâu, mặt trước -Y.",["kiến trúc","inventor-toy","modular"])(wall_panel)
register("tiled-floor","Sàn lát • chín viên","Mảng sàn 3×3 viên đá kem, mép nâu bo tròn. Có thể lặp hoặc đặt làm bục.",["kiến trúc","inventor-toy","modular"])(floor_tiles)
register("balcony-rail","Lan can • nâu vàng","Đoạn lan can gỗ tối, thanh vàng và chân đế, mô-đun dùng cho cầu thang hoặc sân thượng.",["kiến trúc","inventor-toy","modular"])(rail)
register("water-tank","Bồn nước • sân thượng","Bồn xanh thép, đai đồng, nắp chóp, chân gỗ có giằng chéo và ống dẫn.",["đạo cụ","inventor-toy","sân thượng"])(water_tank)
register("sofa","Sofa • xưởng nhà phát minh","Sofa ba đệm nâu đỏ bo tròn với gối kem và vàng, chân gỗ và chi tiết đồng.",["nội thất","inventor-toy","đạo cụ"])(sofa)
register("desk-lamp","Đèn bàn • ánh sáng vàng","Đèn kiểu công nghiệp hoạt hình, khớp đồng và chụp nâu, mặt sáng dùng vật liệu emissive.",["nội thất","inventor-toy","đèn"])(lamp)
register("potted-plant","Chậu cây • lá khối","Chậu nâu viền kem với lá xanh tạo hình khối mềm, dùng trang trí phòng và sân thượng.",["nội thất","inventor-toy","cây"])(leafy_plant)
register("toolbox","Hộp dụng cụ • đỏ nâu","Hộp dụng cụ nắp đỏ, thân nâu, tay xách và bảo vệ góc màu vàng, khóa thép.",["đạo cụ","inventor-toy","dụng cụ"])(toolbox)
register("wrench","Cờ lê • đầu hở","Cờ lê xám thép, một đầu vòng và một đầu hở, mesh thật có lỗ.",["đạo cụ","inventor-toy","dụng cụ"])(wrench)
register("screwdriver","Tua vít • tay cầm đỏ","Tua vít đầu dẹt, trục thép, cổ vàng và tay cầm đỏ bo tròn.",["đạo cụ","inventor-toy","dụng cụ"])(screwdriver)
register("wood-crate","Thùng gỗ • nẹp kim loại","Thùng gỗ có ván, giằng chéo, nẹp góc xám và đinh tán vàng.",["đạo cụ","inventor-toy","thùng"])(crate)
register("blueprint-scroll","Bản vẽ cuộn • thang máy","Tờ bản vẽ màu giấy với hai đầu cuộn và sơ đồ thang máy/bánh răng dựng bằng hình học, không dùng ảnh texture.",["đạo cụ","inventor-toy","bản vẽ"])(scroll)
register("direction-sign","Biển chỉ hướng • mũi tên","Biển gỗ có mũi tên vàng, chân trụ nâu. Không có chữ hay logo.",["đạo cụ","inventor-toy","biển"])(arrow_sign)


def reset(slug):
    global MATS,PARENT,PART
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version=0
    bpy.context.preferences.filepaths.file_preview_type="NONE"
    MATS={};PART=0
    collection=bpy.data.collections.new("ASSET / "+slug)
    bpy.context.scene.collection.children.link(collection)
    bpy.context.view_layer.active_layer_collection=bpy.context.view_layer.layer_collection.children[collection.name]
    PARENT=bpy.data.objects.new(slug,None)
    collection.objects.link(PARENT)
    PARENT["style_pack"]="inventor-toy-v1"
    PARENT["front_axis"]="-Y"
    PARENT["up_axis"]="Z"


def convert_curves():
    for obj in list(bpy.context.scene.objects):
        if obj.type=="CURVE":
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True);bpy.context.view_layer.objects.active=obj
            bpy.ops.object.convert(target="MESH")
    # Correct normals on the explicit arch/gear/arrow mesh surfaces.
    import bmesh
    for obj in PARENT.children_recursive:
        if obj.type=="MESH":
            bm=bmesh.new();bm.from_mesh(obj.data)
            bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
            bm.to_mesh(obj.data);bm.free()


def bounds(objects):
    bpy.context.view_layer.update()
    points=[obj.matrix_world@Vector(c) for obj in objects if obj.type=="MESH" for c in obj.bound_box]
    lo=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    hi=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return lo,hi


def setup_studio(lo,hi,resolution=512):
    global PARENT
    PARENT=None
    scene=bpy.context.scene
    scene.render.engine="CYCLES"
    scene.cycles.device="CPU"
    scene.cycles.samples=24
    scene.cycles.use_denoising=True
    scene.render.use_persistent_data=True
    scene.render.resolution_x=scene.render.resolution_y=resolution
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.world=bpy.data.worlds.new("Warm studio")
    scene.world.use_nodes=True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value=(.77,.74,.73,1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value=.35
    scene.view_settings.view_transform="AgX"
    try:scene.view_settings.look="AgX - Medium High Contrast"
    except TypeError:pass
    scene.view_settings.exposure=-.4
    target=(lo+hi)/2
    size=hi-lo
    radius=max(size.length/2,.4)
    bpy.ops.mesh.primitive_plane_add(size=max(1000,radius*150),location=(0,0,-.018))
    floor=bpy.context.object;floor.name="STUDIO / floor";floor.data.materials.append(mat("background"))
    for offset,power,scale in [((-3,-4,6),550,4),((4,-1,3),260,3),((1,4,5),850,3)]:
        bpy.ops.object.light_add(type="AREA",location=target+Vector(offset)*radius)
        light=bpy.context.object
        light.name="STUDIO / softbox"
        light.data.energy=power*radius**2
        light.data.shape="DISK";light.data.size=scale*radius
        light.rotation_euler=(target-light.location).to_track_quat("-Z","Y").to_euler()
    bpy.ops.object.camera_add(location=target+Vector((3.0,-7.0,2.2))*radius)
    camera=bpy.context.object;camera.name="STUDIO / camera"
    camera.rotation_euler=(target-camera.location).to_track_quat("-Z","Y").to_euler()
    camera.data.type="ORTHO"
    # Fit all eight corners of the bounds, including tall towers and wide sofas.
    inv=camera.rotation_euler.to_matrix().inverted()
    corners=[Vector((x,y,z)) for x in (lo.x,hi.x) for y in (lo.y,hi.y) for z in (lo.z,hi.z)]
    local=[inv@(p-target) for p in corners]
    camera.data.ortho_scale=max(max(v.x for v in local)-min(v.x for v in local),max(v.y for v in local)-min(v.y for v in local))*1.16
    scene.camera=camera
    return scene


def build_asset(slug,folder,root,no_preview=False,resolution=512):
    name,description,tags,builder=BUILDERS[slug]
    print(f"BUILD {slug} / {name}",flush=True)
    reset(slug)
    builder()
    convert_curves()
    asset_root=PARENT
    objects=[asset_root]+list(asset_root.children_recursive)
    lo,hi=bounds(objects)
    shift=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
    asset_root.location-=shift
    bpy.context.view_layer.update()
    lo,hi=bounds(objects)
    dims=[round(float(v),3) for v in hi-lo]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:obj.select_set(True)
    bpy.context.view_layer.objects.active=asset_root
    output=folder/(slug+".glb")
    bpy.ops.export_scene.gltf(filepath=str(output),export_format="GLB",use_selection=True,
                              export_animations=False,export_extras=True,export_apply=True)
    full_description=description+f" Phong cách đồ chơi 3D bo tròn, bảng màu kem/vàng/nâu/kính xanh. Kích thước X×Y×Z={dims[0]}×{dims[1]}×{dims[2]}; gốc giữa đáy, mặt trước -Y, Z lên. Không có rig/animation."
    metadata={"name":name,"description":full_description,"tags":tags+["reference-kit","bo tròn"],"source":"blender",
              "preview":output.with_suffix(".png").relative_to(root).as_posix(),"dimensions":dims,"pack":"inventor-toy-v1",
              "blend":output.with_suffix(".blend").relative_to(root).as_posix(),"mesh_objects":sum(o.type=="MESH" for o in objects)}
    output.with_suffix(".asset.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    scene=setup_studio(lo,hi,resolution)
    bpy.ops.wm.save_as_mainfile(filepath=str(output.with_suffix(".blend")))
    if not no_preview:
        scene.render.filepath=str(output.with_suffix(".png"))
        bpy.ops.render.render(write_still=True)
    return {"slug":slug,"path":output.relative_to(root).as_posix(),**metadata}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only",help="Comma-separated asset slugs for an incremental build")
    parser.add_argument("--no-previews",action="store_true")
    parser.add_argument("--resolution",type=int,default=512)
    args=parser.parse_args()
    root=assets_dir()
    folder=root/"generated"/"inventor-toy-v1"
    folder.mkdir(parents=True,exist_ok=True)
    refs=["4f0ea80f-c548-43c7-938e-9334a3686114.png","322194c1-15bb-4021-8801-3735ce55b99c.png",
          "6cb1ba38-f344-4b36-83bc-e3235932c6b1.png","ce2c8459-cceb-42cf-852a-bef4ca95667d.png"]
    refdir=root/"references"/"inventor-toy-v1";refdir.mkdir(parents=True,exist_ok=True)
    for filename in refs:
        source=Path("C:/Users/thanh/Downloads")/filename
        if source.is_file():shutil.copyfile(source,refdir/filename)
    slugs=args.only.split(",") if args.only else list(BUILDERS)
    if any(slug not in BUILDERS for slug in slugs):raise ValueError("Unknown asset slug")
    manifest=folder/"manifest.json"
    entries=json.loads(manifest.read_text(encoding="utf-8")).get("assets",[]) if manifest.exists() else []
    for i,slug in enumerate(slugs):
        entry=build_asset(slug,folder,root,args.no_previews,args.resolution)
        entries=[old for old in entries if old["slug"]!=slug]+[entry]
        manifest.write_text(json.dumps({"pack":"inventor-toy-v1","palette":PALETTE,"assets":entries},ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"DONE {i+1}/{len(slugs)} {slug}",flush=True)
    print(f"PACK READY / {len(entries)} assets / {folder}",flush=True)


if __name__=="__main__":main()
