"""Build a modular Blender library from the user's six stylized reference sheets."""
import argparse
import json
import math
import os
from pathlib import Path
import random
import shutil
import time

from codex_blender.config import ROOT, assets_dir
import importlib.util
_spec=importlib.util.spec_from_file_location('reference_mesh_helpers',Path(__file__).with_name('build_reference_assets.py'))
B=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)
import bpy
from mathutils import Vector

PACK='story-world-v1'
RUN=ROOT/'outputs'/PACK
RUN.mkdir(parents=True,exist_ok=True)
os.environ['BLENDER_USER_RESOURCES']=str(RUN/'blender-user')
(RUN/'blender-user').mkdir(exist_ok=True)
B.PALETTE.update({'pink':'#F799B6','purple':'#AC65D1','cyan':'#43C5ED','grass':'#9DBB35',
                  'water':'#4AB6E4','flower':'#FFEBBB','blackboard':'#315354','silverhair':'#CFC7C2','glass':'#98D4ED'})
_base_mat=B.mat
def material(key):
    value=_base_mat(key)
    if key=='glass':
        shader=value.node_tree.nodes.get('Principled BSDF')
        shader.inputs['Alpha'].default_value=.22
        shader.inputs['Roughness'].default_value=.18
        value.surface_render_method='DITHERED'
    return value
B.mat=material
box,sphere,cyl,torus,rod,tube,poly,ring=B.box,B.sphere,B.cyl,B.torus,B.rod,B.tube,B.poly,B.ring
ASSETS={}


def add(slug,name,group,fn,description=''):
    ASSETS[slug]=(name,group,description or name,fn)


def cone(name,pos,r1,r2,height,material='gold',vertices=32):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices,radius1=r1,radius2=r2,depth=height,location=pos)
    return B.finish(bpy.context.object,name,material,.025)


def transform(fn,location=(0,0,0),scale=1,rotation=0):
    old=set(B.PARENT.children_recursive)
    fn()
    new=set(B.PARENT.children_recursive)-old
    angle=math.radians(rotation)
    for obj in new:
        x,y,z=obj.location
        obj.location=(location[0]+scale*(x*math.cos(angle)-y*math.sin(angle)),
                      location[1]+scale*(x*math.sin(angle)+y*math.cos(angle)),location[2]+scale*z)
        obj.scale*=scale
        obj.rotation_euler.z+=angle


def remove_named(*parts):
    for obj in list(B.PARENT.children_recursive):
        if any(part in obj.name for part in parts):bpy.data.objects.remove(obj,do_unlink=True)


def recolor(parts,material):
    for obj in B.PARENT.children_recursive:
        if obj.type=='MESH' and any(p in obj.name for p in parts):
            obj.data.materials.clear();obj.data.materials.append(B.mat(material))


def spectacles():
    for x in (-.29,.29):
        B.buckle('spectacles frame',(x,-.578,2.73),.47,.46,'brown_dark',.045)
    rod('spectacles bridge',(-.06,-.60,2.76),(.06,-.60,2.76),.026,'brown_dark')
    for s in (-1,1):rod('spectacles arm',(s*.52,-.57,2.80),(s*.64,.12,2.80),.025,'brown_dark')


def character(role):
    B.inventor('happy' if role in ('inventor','merchant','explorer') else 'smile',role=='inventor')
    if role in ('scientist','scholar','merchant','student','worker'):
        remove_named('goggle','lens glint','strap buckle')
    if role in ('scientist','scholar','merchant'):
        remove_named('backpack','back strap','rolled drawing','roll inner','paper lip','paper spiral')
    if role=='scientist':
        spectacles()
        for s in (-1,1):
            box('lab coat front',(s*.36,-.24,1.30),(.28,.19,1.14),'white',.05)
            box('coat pocket',(s*.36,-.35,1.18),(.22,.04,.24),'cream',.025)
            box('coat sleeve',(s*.57,.01,1.73),(.36,.48,.43),'white',.10,rotation=(0,s*-18,0))
        box('coat back',(0,.30,1.28),(1.02,.12,1.18),'white',.07)
        box('ID badge',(.25,-.40,1.79),(.19,.04,.25),'blue',.02)
        box('ID photo',(.25,-.427,1.83),(.10,.015,.10),'cream',.01)
    elif role=='explorer':
        for i in range(4):sphere('ponytail',(.10,.71+i*.05,2.77-i*.26),(.35,.34,.36),'hair')
        torus('ponytail tie',(.1,.75,2.82),.31,.05,'gold',rotation=(90,0,0))
    elif role=='scholar':
        spectacles();recolor(['hair','forelock','temple','sideburn'],'silverhair')
        box('moustache left',(-.13,-.57,2.46),(.28,.13,.13),'white',.06,rotation=(0,-12,0))
        box('moustache right',(.13,-.57,2.46),(.28,.13,.13),'white',.06,rotation=(0,12,0))
        cone('short beard',(0,-.51,2.24),.05,.23,.36,'silverhair')
        box('long scholarly coat',(0,.12,1.05),(1.02,.62,1.16),'brown_dark',.11)
        for s in (-1,1):box('cream coat lapel',(s*.27,-.23,1.49),(.22,.10,.85),'cream',.04)
        transform(open_book,(0,-.56,1.31),.60)
    elif role=='worker':
        sphere('safety helmet',(0,.04,3.34),(.76,.58,.40),'gold')
        box('helmet brim',(0,-.17,3.25),(1.50,1.18,.12),'shirt',.08)
        box('helmet stripe',(0,-.16,3.56),(.15,.81,.11),'gold_light',.035)
        cyl('headlamp frame',(0,-.62,3.40),.19,.13,'brown_dark',rotation=(90,0,0))
        cyl('headlamp',(0,-.70,3.40),.13,.03,'lamp',rotation=(90,0,0))
    elif role=='student':
        remove_named('tool pouch','pouch lip','screwdriver','wrench handle','wrench fork')
        recolor(['backpack','back strap'],'blue')
        sphere('school cap',(0,.02,3.30),(.73,.57,.27),'blue')
        box('cap visor',(0,-.56,3.24),(1.18,.60,.11),'blue',.08)
        for obj in B.PARENT.children_recursive:
            if 'trouser' in obj.name:obj.scale.z*=.70
        B.PARENT.scale=(.43,.43,.43)
    elif role=='merchant':
        remove_named('tool pouch','pouch lip','screwdriver','wrench handle','wrench fork','front suspender','suspender buckle')
        sphere('head scarf',(0,.09,3.31),(.76,.60,.27),'shirt')
        box('headscarf knot',(.71,.05,3.24),(.31,.22,.28),'gold',.08)
        box('cream apron',(0,-.34,1.16),(.92,.12,.99),'cream',.10)
        box('apron bib',(0,-.34,1.76),(.55,.10,.39),'cream',.06)
        box('apron pocket',(.20,-.43,1.12),(.36,.04,.30),'white',.025)


for role,name in [('inventor','Nhà phát minh'),('scientist','Nhà khoa học áo blouse'),('explorer','Nhà thám hiểm'),
                  ('scholar','Học giả lớn tuổi'),('worker','Kỹ sư mũ bảo hộ'),('student','Học sinh'),('merchant','Chủ cửa hàng')]:
    add('character-'+role,name,'characters',lambda r=role:character(r),'Nhân vật chibi toàn thân, trang phục riêng, các phần cơ thể là mesh rời; tư thế tĩnh, chưa có rig.')


def book(pos=(0,0,.12),color='red',size=(.8,.56,.22)):
    x,y,z=pos;w,d,h=size
    box('book pages',pos,(w-.07,d-.04,h),'paper',.015)
    for s in (-1,1):box('book cover',(x,y,z+s*h/2),(w,d,.045),color,.02)
    box('book spine',(x-w/2,y,z),(.07,d,h+.04),color,.025)
    for yy in (-.12,.12):box('spine gold trim',(x-w/2-.035,y+yy,z),(.025,.04,h*.8),'gold',.005)


def books():
    for i,col in enumerate(('brown','red','blue')):book(((-1)**i*.04,0,.13+i*.27),col)


def open_book():
    for s in (-1,1):
        box('open book cover',(s*.35,0,.08),(.70,.82,.08),'leather',.035,rotation=(0,s*9,0))
        box('open pages',(s*.34,0,.14),(.64,.75,.10),'paper',.025,rotation=(0,s*9,0))
        for i in range(5):box('page line',(s*.34,-.25+i*.12,.21),(.44,.015,.008),'copper',.003)
    rod('book center seam',(0,-.38,.20),(0,.38,.20),.018,'brown')


def vessel(kind='flask',liquid='cyan'):
    if kind=='round':
        sphere('round flask',(0,0,.47),(.42,.42,.44),'glass')
        sphere('colored reagent',(0,0,.39),(.35,.35,.29),liquid)
        cyl('flask neck',(0,0,.97),.12,.38,'glass')
        torus('neck lip',(0,0,1.17),.14,.025,'steel_light')
    elif kind=='beaker':
        cyl('beaker body',(0,0,.45),.38,.84,'glass')
        cyl('beaker liquid',(0,-.014,.30),.34,.50,liquid)
        torus('beaker rim',(0,0,.89),.39,.035,'steel_light')
        for i in range(4):box('measurement',( .17,-.373,.25+i*.15),(.19 if i%2==0 else .10,.025,.025),'white',.004)
    else:
        cone('glass flask',(0,0,.40),.43,.14,.73,'glass')
        cone('flask liquid',(0,-.01,.27),.35,.23,.36,liquid)
        cyl('flask neck',(0,0,.91),.13,.37,'glass')
        torus('flask lip',(0,0,1.10),.15,.027,'steel_light')
    for i in range(3):sphere('reagent bubble',(-.12+i*.10,-.32,.35+i*.07),(.025,.015,.025),'white')


def test_tubes():
    box('rack base',(0,0,.08),(1.55,.52,.16),'brown',.04)
    for s in (-1,1):box('rack upright',(s*.69,.07,.55),(.13,.18,1.10),'copper',.03)
    box('rack crossbar',(0,.08,.94),(1.55,.36,.14),'brown',.04)
    for x,col in zip((-.43,0,.43),('cyan','gold','purple')):
        cyl('test tube',(x,-.04,.53),.12,.72,'glass');sphere('round tube bottom',(x,-.04,.18),(.12,.12,.12),'glass')
        cyl('test reagent',(x,-.06,.45),.095,.45,col)
        cyl('tube cap',(x,-.04,1.05),.15,.09,'steel_light')


def crystal_jar(energy=False):
    radius=.49 if not energy else .65
    height=1.25 if not energy else 2.5
    cyl('jar base',(0,0,.10),radius+.10,.20,'dark_steel' if energy else 'brown')
    # A sparse glass cage keeps the crystal visible and avoids opaque glass in GLB viewers.
    for angle in (45,135,225,315):
        a=math.radians(angle);rod('glass edge',(radius*math.cos(a),radius*math.sin(a),.20),(radius*math.cos(a),radius*math.sin(a),height-.12),.025,'blue_light')
    for z in (.26,height-.18):torus('glass rim',(0,0,z),radius,.035,'blue_light')
    cyl('jar lid',(0,0,height),radius+.10,.16,'gold' if energy else 'brown')
    for x,s in ((-.18,.65),(.14,1),(.27,.5)):
        obj=cone('crystal',(x,0,height*.45),.19*s,0,.70*s,'cyan' if energy else 'grass',vertices=6)
        obj.rotation_euler.y=math.radians(x*70)
    if energy:
        for z in (.10,height):
            for a in range(0,360,90):
                x,y=.65*math.cos(math.radians(a)),.65*math.sin(math.radians(a))
                box('reactor clamp',(x,y,z),(.22,.24,.32),'gold',.04)


def globe():
    cyl('globe base',(0,0,.08),.43,.16,'brown');cyl('globe stand',(0,0,.28),.12,.32,'gold')
    sphere('blue planet',(0,0,1.0),(.55,.55,.55),'blue')
    for x,y,z,sx,sz in [(-.26,-.42,1.18,.24,.19),(.18,-.49,.90,.20,.21),(.12,.43,1.20,.28,.16),(-.30,.28,.76,.20,.12)]:
        sphere('stylized continent',(x,y,z),(sx,.08,sz),'grass')
    ring('globe meridian',(0,0,1),.66,.61,.08,'gold',start=-math.pi*.6,end=math.pi*.65)


def telescope():
    for angle in (0,120,240):
        a=math.radians(angle);rod('tripod',(0,0,.90),(.65*math.cos(a),.65*math.sin(a),.08),.075,'brown_dark')
    cyl('telescope hub',(0,0,1.0),.17,.28,'gold')
    rod('telescope tube',(-.60,0,1.33),(.62,0,1.62),.22,'steel')
    cyl('front gold rim',(.67,0,1.63),.29,.16,'gold',rotation=(0,77,0))
    cyl('blue lens',(.76,0,1.66),.23,.025,'blue',rotation=(0,77,0))


def microscope():
    box('microscope base',(0,0,.10),(.96,.72,.20),'cream',.09)
    tube('microscope arm',[(.26,.1,.2),(.43,.1,.65),(.39,.1,1.20),(.15,.1,1.49)],.12,'cream')
    box('specimen stage',(-.1,-.1,.59),(.75,.60,.09),'dark_steel',.025)
    cyl('focus knob',(.43,-.11,.96),.14,.15,'gold',rotation=(90,0,0))
    rod('optical body',(-.10,.0,.88),(.16,.0,1.55),.13,'steel')
    cyl('eyepiece',(.19,0,1.64),.16,.20,'brown_dark',rotation=(0,21,0))
    cyl('objective',(-.15,0,.79),.10,.19,'gold')


def blackboard():
    box('blackboard',(0,0,1.06),(2.35,.15,1.42),'blackboard',.04)
    for z in (.33,1.79):box('blackboard frame',(0,-.06,z),(2.55,.18,.13),'brown',.04)
    for x in (-1.20,1.20):box('blackboard side',(x,-.06,1.06),(.13,.18,1.48),'copper',.04)
    for x in (-.91,.91):rod('board leg',(x,.05,.45),(x,-.15,.04),.065,'brown')
    box('chalk tray',(0,-.20,.40),(2.46,.32,.10),'copper',.025)
    for angle in (0,60,120):
        a=math.radians(angle)
        points=[(-.40+.17*math.cos(t)*math.cos(a)-.50*math.sin(t)*math.sin(a),-.125,
                 1.12+.17*math.cos(t)*math.sin(a)+.50*math.sin(t)*math.cos(a)) for t in [i*math.tau/48 for i in range(49)]]
        tube('atom orbit',points,.012,'white')
    sphere('atom nucleus',(-.40,-.14,1.12),(.06,.018,.06),'gold_light')
    for i in range(4):box('chalk equation',(.70,-.13,1.48-i*.19),(.45-i*.05,.018,.025),'white',.005)


def robot_arm():
    cyl('robot base',(0,0,.12),.52,.24,'dark_steel');cyl('rotating plinth',(0,0,.31),.35,.23,'gold')
    points=[(0,0,.40),(-.30,0,1.10),(.38,0,1.54),(.80,0,1.22)]
    for a,b in zip(points,points[1:]):rod('robot arm link',a,b,0,'gold',(.22,.31))
    for p in points[1:]:cyl('arm joint',p,.18,.38,'steel',rotation=(90,0,0))
    for s in (-1,1):tube('gripper',[(.80+s*.10,0,1.14),(.80+s*.26,0,.94),(.80+s*.15,0,.77)],.06,'dark_steel')


def console():
    box('console pedestal',(0,0,.65),(1.90,.70,1.30),'steel',.14)
    box('display surround',(0,-.40,1.11),(1.48,.16,.94),'dark_steel',.08)
    box('cyan screen',(0,-.49,1.12),(1.21,.025,.68),'blackboard',.04)
    for i in range(4):box('display graph',(-.36+i*.23,-.51,.95+i*.07),(.12,.015,.25+i*.12),'cyan',.01)
    box('control shelf',(0,-.62,.49),(2.0,.70,.20),'steel_light',.07)
    for x in (-.66,-.33,0,.33):box('control key',(x,-.77,.62),(.19,.18,.08),'gold' if x<0 else 'red',.02)
    cyl('joystick stem',(.70,-.65,.75),.04,.27,'steel');sphere('joystick',(.70,-.65,.90),(.12,.12,.12),'red')
    for x in (-.3,0,.3):sphere('indicator light',(x,-.02,1.42),(.09,.06,.08),'lamp')


def tesla():
    box('coil base',(0,0,.10),(1.2,.70,.20),'dark_steel',.05)
    cyl('coil core',(0,0,.67),.12,.95,'steel')
    for z in (.33,.50,.67,.84,1.01):torus('copper coil',(0,0,z),.27,.055,'copper')
    sphere('blue terminal',(0,0,1.27),(.22,.22,.22),'blue')
    for s in (-1,1):cyl('side terminal',(s*.48,0,.56),.035,.88,'steel');sphere('terminal bulb',(s*.48,0,1.03),(.09,.09,.09),'gold')


def drone():
    box('drone body',(0,0,.25),(.76,.65,.43),'cream',.15)
    cyl('camera rim',(0,-.37,.23),.17,.10,'dark_steel',rotation=(90,0,0))
    cyl('camera lens',(0,-.43,.23),.11,.03,'blue',rotation=(90,0,0))
    for x in (-.64,.64):
        for y in (-.50,.50):
            rod('drone strut',(0,0,.25),(x,y,.28),.07,'dark_steel')
            torus('prop guard',(x,y,.33),.26,.055,'gold')
            box('prop blade',(x,y,.33),(.39,.08,.035),'steel',.015,rotation=(0,0,30))


for slug,name,fn in [('test-tubes','Giá ống nghiệm',test_tubes),('flask-blue','Bình tam giác xanh',lambda:vessel()),
 ('flask-purple','Bình cầu tím',lambda:vessel('round','purple')),('beaker','Cốc chia độ',lambda:vessel('beaker','gold')),
 ('crystal-jar','Hũ tinh thể',crystal_jar),('books','Chồng sách',books),('open-book','Sách mở',open_book),
 ('globe','Quả địa cầu',globe),('telescope','Kính thiên văn',telescope),('microscope','Kính hiển vi',microscope),
 ('blackboard','Bảng khoa học',blackboard),('tesla-coil','Cuộn dây điện',tesla),('console','Bàn điều khiển',console),
 ('energy-chamber','Buồng năng lượng',lambda:crystal_jar(True)),('robot-arm','Cánh tay robot',robot_arm),('drone','Drone bốn cánh',drone)]:
    add(slug,name,'science',fn)


def wheel(x,y,z,r=.38,width=.20,axis='X'):
    rotation=(0,90,0) if axis=='X' else (90,0,0)
    cyl('rubber tire',(x,y,z),r,width,'boot',rotation=rotation,bevel=.055)
    cyl('wheel hub',(x,y,z),r*.62,width+.025,'steel_light',rotation=rotation)
    cyl('gold axle hub',(x,y,z),r*.24,width+.06,'gold',rotation=rotation)
    for i in range(12):
        a=i*math.tau/12
        if axis=='X':box('tire tread',(x,y+r*.94*math.sin(a),z+r*.94*math.cos(a)),(width*.8,r*.23,r*.12),'sole',.015,rotation=(math.degrees(-a),0,0))
        else:box('tire tread',(x+r*.94*math.sin(a),y,z+r*.94*math.cos(a)),(r*.23,width*.8,r*.12),'sole',.015,rotation=(0,math.degrees(a),0))


def bicycle(scooter=False,motor=False):
    r=.36 if not scooter else .24
    rear,front=-.76,.76
    wheel(rear,0,r,r,.23,'Y');wheel(front,0,r,r,.23,'Y')
    if scooter:
        box('scooter deck',(-.10,0,.28),(1.36,.38,.13),'gold',.06)
        rod('scooter stem',(.60,0,.30),(.70,0,1.55),.075,'dark_steel')
    elif motor:
        box('motor chassis',(-.08,0,.64),(1.16,.40,.23),'dark_steel',.07)
        box('fuel tank',(.20,0,.98),(.68,.44,.42),'gold',.13)
        box('motor seat',(-.40,0,1.12),(.79,.44,.18),'leather',.08)
        box('engine housing',(-.05,-.02,.63),(.46,.46,.42),'steel',.07)
        for z in (.51,.61,.71):box('engine rib',(-.04,-.27,z),(.42,.04,.04),'steel_light',.01)
        rod('exhaust',(-.65,-.30,.43),(.10,-.30,.43),.085,'steel')
        cyl('motor headlight',(.82,0,1.15),.18,.14,'gold',rotation=(0,90,0))
        cyl('headlamp glass',(.90,0,1.15),.13,.03,'lamp',rotation=(0,90,0))
    else:
        points=[(-.76,0,r),(-.35,0,.98),(.20,0,.46),(-.76,0,r),(.40,0,1.03),(.20,0,.46),(-.35,0,.98)]
        for a,b in zip(points,points[1:]):rod('cycle frame',a,b,.055,'gold')
        box('cycle saddle',(-.38,0,1.12),(.42,.27,.13),'leather',.06)
        cyl('crankset',(.20,0,.46),.13,.28,'steel',rotation=(90,0,0))
        rod('crank',(.20,-.19,.46),(.34,-.19,.24),.035,'steel')
        box('pedal',(.34,-.19,.22),(.23,.15,.07),'brown_dark',.02)
    if not scooter:
        rod('front fork',(.76,0,r),(.45,0,1.20),.065,'gold')
    rod('steering stem',(.48 if not scooter else .7,0,1.1),(.58 if not scooter else .7,0,1.50),.06,'steel')
    rod('handlebar',(.58 if not scooter else .7,-.34,1.50),(.58 if not scooter else .7,.34,1.50),.06,'brown_dark')


def handcart(mining=False):
    for x in (-.64,.64):wheel(x,.0,.39,.39,.23)
    box('cart undercarriage',(0,0,.40),(1.30,1.08,.18),'dark_steel',.05)
    box('cart floor',(0,0,.67),(1.40,1.17,.13),'brown' if not mining else 'gold',.04)
    for z in (.85,1.08):
        for x in (-.71,.71):box('cart side plank',(x,0,z),(.11,1.23,.20),'gold' if mining else 'copper',.035)
        for y in (-.58,.58):box('cart end plank',(0,y,z),(1.44,.11,.20),'gold' if mining else 'brown',.035)
    for x in (-.60,.60):
        rod('cart handle',(x,.48,.82),(x,1.39,1.40),.065,'brown_dark')
        for y in (-.57,.57):box('cart corner bracket',(x,y,.94),(.17,.14,.55),'steel',.025)
    rod('handle grip',(-.60,1.39,1.40),(.60,1.39,1.40),.08,'brown')
    if mining:
        for i in range(5):sphere('coal lump',((i%3-1)*.33,(i//3-.5)*.37,1.20),(.28,.24,.27),'boot')


def car(van=False):
    width,length=1.25,2.30 if van else 1.92
    for x in (-.66,.66):
        for y in (-.65,.70 if van else .61):wheel(x,y,.35,.35,.22)
    box('vehicle chassis',(0,0,.43),(width,length,.30),'steel',.08)
    box('body',(0,0,.76),(width,length,.65),'cream' if van else 'gold',.16)
    if van:
        box('cargo body',(0,.48,1.14),(1.34,1.25,1.45),'cream',.13)
        box('cargo stripe',(0,-.03,1.10),(1.39,.10,.46),'gold',.025)
        box('rear double door',(0,1.135,1.21),(1.15,.05,1.14),'stone_light',.04)
        for x in (-.09,.09):box('rear door handle',(x,1.18,1.18),(.06,.06,.22),'steel',.015)
    box('cabin',(0,-.40 if van else .10,1.19),(1.14,1.07, .70),'cream',.15)
    box('windshield',(0,-.963 if van else -.475,1.25),(.93,.035,.43),'blue',.04)
    for x in (-.58,.58):
        box('side window',(x,-.36 if van else .04,1.27),(.025,.75,.40),'blue',.035)
        box('door handle',(x,-.15,.93),(.05,.16,.055),'brown_dark',.015)
        box('side mirror',(x*1.17,-.62,1.13),(.19,.15,.16),'brown_dark',.04)
    for x in (-.42,.42):
        cyl('headlight bezel',(x,-length/2-.035,.82),.16,.08,'gold',rotation=(90,0,0))
        cyl('headlight glass',(x,-length/2-.08,.82),.12,.025,'lamp',rotation=(90,0,0))
    box('front grille',(0,-length/2-.05,.66),(.54,.08,.26),'dark_steel',.04)
    for z in (.60,.70):box('grille slat',(0,-length/2-.10,z),(.43,.015,.025),'steel',.005)
    box('front bumper',(0,-length/2-.10,.44),(1.32,.16,.19),'stone',.05)


def battery(generator=False):
    box('battery body',(0,0,.48),(1.20,.70,.90),'dark_steel',.10)
    box('battery cap',(0,0,.97),(1.29,.77,.15),'gold',.05)
    for x,col in ((-.32,'blue'),(.32,'red')):cyl('battery terminal',(x,0,1.10),.11,.14,col)
    lightning=poly('lightning symbol',[(-.12,.80),(.10,.80),(-.02,.57),(.18,.57),(-.16,.20),(-.04,.48),(-.23,.48)],.035,'gold')
    lightning.location.y=-.38
    if generator:
        for x in (-.72,.72):tube('generator protection',[(x,-.43,.1),(x,.43,.1),(x,.43,1.17),(x,-.43,1.17),(x,-.43,.1)],.06,'brown_dark')
        for z in (.25,.42,.59,.76):box('vent grille',(-.32,-.4,z),(.36,.025,.06),'steel',.015)
        box('generator handle',(0,.0,1.25),(.60,.14,.12),'brown',.04)


def fan():
    box('fan housing',(0,.06,.60),(1.18,.30,1.18),'steel',.10)
    cyl('fan aperture',(0,-.11,.60),.47,.05,'dark_steel',rotation=(90,0,0))
    for i in range(5):
        a=i*math.tau/5
        blade=sphere('fan blade',(.25*math.sin(a),-.17,.60+.25*math.cos(a)),(.14,.045,.27),'gold')
        blade.rotation_euler.y=-a
    cyl('fan hub',(0,-.23,.6),.11,.10,'copper',rotation=(90,0,0))
    for x in (-.47,.47):
        for z in (.13,1.07):cyl('housing screw',(x,-.115,z),.045,.02,'steel_light',rotation=(90,0,0))


def engine():
    box('engine block',(0,0,.49),(1.14,.76,.70),'dark_steel',.10)
    box('yellow cylinder head',(0,0,.93),(1.12,.75,.20),'gold',.08)
    box('air filter',(0,.04,1.10),(.42,.44,.14),'brown_dark',.05)
    for x in (-.4,-.13,.13,.4):
        tube('exhaust manifold',[(x,-.34,.80),(x,-.53,.69),(x,-.56,.39)],.065,'steel_light')
        box('engine bolt',(x,-.40,.46),(.07,.04,.07),'steel_light',.015)
    cyl('engine pulley',(.64,0,.56),.25,.14,'steel',rotation=(0,90,0))


def crane():
    box('crane pedestal',(0,0,.12),(.86,.86,.24),'steel',.06)
    box('crane mast',(0,0,1.12),(.24,.30,2.03),'dark_steel',.05)
    box('crane boom',(.66,0,2.15),(1.66,.36,.28),'gold',.05)
    for x in (.1,.53,.96,1.39):box('boom hazard stripe',(x,-.195,2.15),(.11,.025,.25),'brown_dark',.01,rotation=(0,-25,0))
    cyl('cable reel',(1.25,0,1.97),.16,.37,'steel',rotation=(90,0,0))
    rod('suspended cable',(1.25,0,1.94),(1.25,0,.98),.024,'boot')
    box('hook block',(1.25,0,.95),(.29,.25,.29),'gold',.05)
    ring('lifting hook',(1.25,0,.61),.22,.14,.12,'steel',start=.15*math.pi,end=1.7*math.pi)


def pipe(tee=False):
    if tee:
        rod('horizontal pipe',(-.49,0,.63),(.49,0,.63),.15,'steel')
        rod('pipe branch',(0,0,.16),(0,0,.63),.15,'steel')
        for x in (-.50,.50):cyl('pipe flange',(x,0,.63),.22,.11,'gold',rotation=(0,90,0))
        cyl('base flange',(0,0,.11),.22,.11,'gold')
    else:
        points=[(0,0,.12),(0,0,.39)]+[(.32-.32*math.cos(t),0,.39+.32*math.sin(t)) for t in [i*math.pi/24 for i in range(13)]]+[(.64,0,.71)]
        tube('elbow pipe',points,.15,'steel')
        cyl('pipe flange',(0,0,.10),.22,.12,'gold')
        cyl('pipe flange',(.65,0,.71),.22,.12,'steel_light',rotation=(0,90,0))


def gears():
    B.gear('large gear',(-.28,.03,.63),.61,'steel',12)
    B.gear('small gear',(.43,-.02,.30),.32,'gold',9)


def axle():
    for x in (-.57,.57):wheel(x,0,.40,.40,.22)
    rod('axle',(-.70,0,.40),(.70,0,.40),.09,'steel_light')


for slug,name,fn in [('bicycle','Xe đạp',bicycle),('scooter','Xe scooter',lambda:bicycle(True)),('handcart','Xe kéo gỗ',handcart),
 ('motorbike','Xe máy',lambda:bicycle(motor=True)),('small-car','Ô tô nhỏ',car),('delivery-van','Xe giao hàng',lambda:car(True)),
 ('construction-cart','Xe chở vật liệu',lambda:handcart(True)),('generator','Máy phát điện',lambda:battery(True)),
 ('crane-hook','Cần cẩu và móc',crane),('toolbox','Hộp dụng cụ',B.toolbox),('wrench','Cờ lê',B.wrench),('screwdriver','Tua vít',B.screwdriver),
 ('gears','Cặp bánh răng',gears),('engine-block','Động cơ',engine),('fan-unit','Quạt thông gió',fan),('battery','Ắc quy',battery),
 ('pipe-elbow','Ống khuỷu',pipe),('pipe-tee','Ống chữ T',lambda:pipe(True)),('wheel-axle','Bánh xe và trục',axle)]:
    add(slug,name,'mechanics',fn)


def doorway():
    box('door frame',(0,0,1.0),(1.0,.20,2.0),'copper',.06)
    box('door panel',(0,-.12,.99),(.80,.07,1.78),'brown',.04)
    for z in (.53,1.32):box('recessed door panel',(0,-.17,z),(.57,.04,.56),'copper',.025)
    box('door handle',(.28,-.22,1.0),(.06,.06,.17),'gold',.02)


def roof(width=2.6,depth=2.2,z=2.7):
    for side in (-1,1):
        for row in range(4):
            x=side*(row+.5)*width/8
            zz=z+.69-(row+.5)*.69/4
            for j in range(6):box('roof tile',(x,-depth/2+(j+.5)*depth/6,zz),(width/7.5,depth/6-.025,.15),'gold' if (j+row)%3 else 'shirt',.045,rotation=(0,side*28,0))
        rod('roof eave',(side*width/2,-depth/2-.03,z),(0,-depth/2-.03,z+.73),.085,'brown_dark')
    box('roof ridge',(0,0,z+.73),(.20,depth+.15,.19),'copper',.07)


def awning(color='blue'):
    for i in range(7):
        x=(i-3)*.31
        box('striped awning',(x,0,.34),(.31,.88,.12),color if i%2==0 else 'white',.025,rotation=(12,0,0))
        box('awning scallop',(x,-.43,.19),(.31,.10,.22),color if i%2==0 else 'white',.07)
    for x in (-1.08,1.08):rod('awning support',(x,.30,0),(x,-.40,.27),.035,'brown_dark')


def house(kind='house'):
    width=2.5
    box('foundation',(0,0,.13),(2.9,2.5,.26),'steel',.08)
    box('house walls',(0,0,1.43),(width,2.10,2.6),'cream',.07)
    for x in (-1.23,1.23):
        for z in (.43,.79,1.15,1.51,1.87,2.23,2.59):box('corner masonry',(x,-1.03,z),(.31,.24,.31),'stone',.045)
    if kind=='house':
        transform(doorway,(0,-1.12,.25),.78)
        for x in (-.80,.80):B.window((x,-1.07,1.49),.47,.71)
        roof()
        box('chimney',(.67,.46,3.13),(.37,.40,.86),'stone',.05)
        box('chimney cap',(.67,.46,3.58),(.49,.49,.12),'brown_dark',.035)
    else:
        for x in (-.78,.78):B.window((x,-1.08,1.24),.80,1.38)
        transform(doorway,(0,-1.13,.27),.55)
        box('shop cornice',(0,0,2.79),(2.79,2.35,.23),'brown_dark',.07)
        box('shop sign',(0,-1.23,2.52),(.95,.15,.64),'copper' if kind=='cafe' else 'gold',.10)
        if kind=='cafe':
            cyl('coffee logo',(0,-1.35,2.53),.20,.04,'white',rotation=(90,0,0))
            ring('cup handle',(.23,-1.35,2.54),.11,.07,.04,'white')
        else:
            box('shop logo basket',(0,-1.34,2.55),(.39,.035,.22),'white',.025)
            for x in (-.13,.13):sphere('cart logo wheel',(x,-1.36,2.36),(.045,.018,.045),'white')
        transform(lambda:awning('red' if kind=='cafe' else 'blue'),(0,-1.22,1.96))
    for x in (-1.12,1.12):
        transform(lambda:B.planter(),(x,-1.39,.21),.50)


def watchtower():
    box('tower footing',(0,0,.16),(1.9,1.9,.32),'steel',.08)
    box('tower shaft',(0,0,1.73),(1.26,1.26,3.20),'stone',.07)
    for z in (.55,1.23,1.91,2.59):box('tower masonry course',(0,0,z),(1.38,1.38,.16),'cream',.025)
    B.window((0,-.66,2.28),.36,.70)
    for x in (-.72,.72):
        for y in (-.72,.72):box('tower lookout post',(x,y,3.36),(.16,.16,1.10),'brown',.035)
    for z in (2.96,3.27):
        for x in (-.76,.76):box('lookout rail',(x,0,z),(.12,1.64,.13),'gold',.03)
        for y in (-.76,.76):box('lookout rail',(0,y,z),(1.64,.12,.13),'gold',.03)
    roof(2.08,2.08,3.90)


def road(kind='straight',sidewalk=False):
    box('tile foundation',(0,0,.10),(2,2,.20),'stone',.055)
    box('road surface',(0,0,.22),(1.87,1.87,.08),'boot' if not sidewalk else 'stone_light',.035)
    if sidewalk:
        for x in (-.48,.48):
            for y in (-.48,.48):box('paving slab',(x,y,.29),(.93,.93,.08),'cream',.025)
        return
    for y in (-.60,0,.60):
        if kind!='crossroad':box('lane dash',(0,y,.266),(.055,.29,.012),'white',.004)
    if kind=='crossing':
        for x in (-.64,-.32,0,.32,.64):box('zebra stripe',(x,0,.272),(.18,1.24,.014),'white',.005)
    if kind=='corner':
        points=[(.60-.60*math.cos(t),.60-.60*math.sin(t),.27) for t in [i*math.pi/32 for i in range(17)]]
        tube('curved lane',points,.023,'white')
    if kind=='crossroad':
        for s in (-1,1):
            for a in (.62,.84):box('junction lane',(s*a,0,.27),(.18,.045,.01),'white',.003);box('junction lane',(0,s*a,.27),(.045,.18,.01),'white',.003)


def streetlamp():
    cyl('streetlamp base',(0,0,.10),.25,.20,'brown_dark')
    cyl('lamp post',(0,0,1.15),.067,2.10,'brown_dark')
    box('lantern glass',(0,0,2.21),(.35,.35,.48),'lamp',.05)
    for x in (-.20,.20):
        for y in (-.20,.20):rod('lantern corner',(x,y,1.97),(x,y,2.47),.028,'brown_dark')
    cone('lantern roof',(0,0,2.52),.34,.12,.18,'brown',vertices=4)
    box('lantern foot',(0,0,1.96),(.48,.48,.10),'brown_dark',.035)
    sphere('lamp finial',(0,0,2.69),(.09,.09,.09),'gold')


def traffic_sign():
    cyl('sign footing',(0,0,.06),.23,.12,'steel')
    rod('sign pole',(0,0,.12),(0,0,1.67),.05,'steel')
    cyl('road sign',(0,0,1.65),.36,.10,'white',rotation=(90,0,0))
    cyl('sign blue face',(0,-.06,1.65),.31,.025,'blue',rotation=(90,0,0))
    arrow=poly('direction arrow',[(-.20,1.69),(.03,1.69),(.03,1.81),(.22,1.65),(.03,1.48),(.03,1.60),(-.20,1.60)],.025,'white')
    arrow.location.y=-.087


def bench():
    for x in (-.68,.68):
        for y in (-.25,.25):box('bench foot',(x,y,.27),(.15,.15,.54),'brown_dark',.035)
        box('bench side arm',(x,-.02,.74),(.13,.78,.13),'gold',.04)
        rod('bench back upright',(x,.26,.15),(x,.31,1.19),.06,'brown_dark')
    for y in (-.24,0,.24):box('seat plank',(0,y,.55),(1.66,.22,.13),'copper',.035)
    for z in (.88,1.12):box('bench back plank',(0,.31,z),(1.66,.12,.20),'brown',.035)


def mailbox():
    box('mailbox post',(0,.10,.45),(.16,.16,.90),'brown_dark',.03)
    box('mailbox body',(0,0,1.04),(.62,.46,.88),'red',.20)
    box('mailbox inset',(0,-.25,1.02),(.44,.04,.49),'copper',.05)
    box('mail slot',(0,-.28,1.25),(.32,.025,.06),'brown_dark',.01)
    B.buckle('envelope',(0,-.29,.98),.25,.17,'paper',.017)


def wall():
    for row in range(4):
        for column in range(4):box('wall brick',((column-1.5)*.49,0,.18+row*.32),(.47,.39,.30),'stone' if (row+column)%2 else 'cream',.04)
    box('wall cap',(0,0,1.38),(2.12,.53,.18),'brown',.05)


for slug,name,fn in [('small-house','Nhà mái ngói',house),('shop','Mặt tiền cửa hàng',lambda:house('shop')),('cafe','Quán cà phê',lambda:house('cafe')),
 ('watchtower','Tháp quan sát',watchtower),('street-stairs','Cầu thang phố',lambda:B.stairs(width=1.3,run=1.9,height=1.0,steps=6)),
 ('road-straight','Đường thẳng',road),('road-crossing','Vạch qua đường',lambda:road('crossing')),('road-corner','Đường góc',lambda:road('corner')),
 ('road-crossroad','Ngã tư',lambda:road('crossroad')),('sidewalk','Vỉa hè',lambda:road(sidewalk=True)),('streetlamp','Đèn đường',streetlamp),
 ('traffic-sign','Biển chỉ hướng',traffic_sign),('bench','Ghế công viên',bench),('mailbox','Hòm thư',mailbox),('archway','Cổng vòm',B.arch_entry),
 ('door','Cửa gỗ',doorway),('window','Cửa sổ xanh',lambda:B.window()),('awning','Mái hiên sọc',awning),('wall','Tường gạch',wall),('balcony','Ban công',B.balcony)]:
    add(slug,name,'town',fn)


def table(dining=False,desk=False):
    w,d,h=(1.9,1.22,1.02) if dining else (1.65,.95,.66)
    if desk:w,d,h=2.20,.85,1.03
    for x in (-w*.38,w*.38):
        for y in (-d*.32,d*.32):box('table leg',(x,y,h/2),(.17,.17,h),'brown_dark',.045)
    for i in range(5):box('wood tabletop',((i-2)*w/5,0,h),(w/5-.018,d,.16),'copper',.045)
    if desk:
        for z in (.30,.60,.88):
            box('desk drawer',(-.67,0,z),(.61,.68,.24),'brown',.04)
            box('drawer pull',(-.67,-.36,z),(.20,.06,.05),'gold',.02)
        transform(books,(-.68,.02,h+.10),.45)
        transform(B.lamp,(.65,.04,h+.08),.42)
    elif not dining:
        transform(lambda:book(),(-.38,0,h+.18),.45)
        transform(lambda:B.leafy_plant(),(.44,0,h+.09),.33)


def chair():
    for x in (-.27,.27):
        for y in (-.24,.24):box('chair leg',(x,y,.38),(.12,.12,.76),'brown',.03)
    box('seat cushion',(0,0,.78),(.76,.72,.16),'cream',.07)
    for x in (-.28,.28):box('chair back upright',(x,.27,1.20),(.13,.14,.93),'brown',.035)
    for z in (1.16,1.49):box('chair back slat',(0,.27,z),(.65,.15,.23),'copper',.04)


def armchair():
    box('armchair base',(0,0,.35),(1.20,1.12,.45),'leather',.13)
    box('armchair cushion',(0,-.16,.63),(.81,.80,.26),'copper',.10)
    box('armchair back',(0,.35,1.0),(.98,.32,.88),'red',.13)
    for x in (-.52,.52):box('chair arm',(x,0,.76),(.26,1.12,.70),'copper',.12)
    box('pillow',(0,.02,1.0),(.49,.20,.50),'cream',.09,rotation=(7,0,8))


def bed():
    for x in (-.64,.64):
        for y in (-.93,.93):box('bed post',(x,y,.37),(.18,.18,.74),'brown',.045)
    box('bed frame',(0,0,.44),(1.54,2.10,.30),'brown',.09)
    box('bed mattress',(0,0,.66),(1.40,1.98,.26),'white',.13)
    box('bed quilt',(0,-.39,.83),(1.45,1.25,.16),'shirt',.07)
    box('blanket drop',(0,-.99,.65),(1.45,.11,.41),'gold',.045)
    box('headboard',(0,.98,1.07),(1.51,.15,.90),'copper',.12)
    for x in (-.35,.35):box('pillow',(x,.61,.88),(.59,.47,.15),'paper',.07,rotation=(8,0,0))


def cabinet(kind='bookcase'):
    w,h=1.35,1.86
    box('cabinet back',(0,.23,h/2),(w,.08,h),'brown',.035)
    for x in (-w/2,w/2):box('cabinet side',(x,0,h/2),(.14,.62,h),'copper',.045)
    for z in (.12,.69,1.26,1.88):box('cabinet shelf',(0,0,z),(w+.17,.69,.13),'brown',.04)
    if kind=='bookcase':
        for z in (.20,.77,1.34):
            for i,col in enumerate(('blue','red','paper','leather')):
                box('upright book',(-.42+i*.22,.02,z+.19),(.15,.39,.38-i*.035),col,.015)
        transform(B.leafy_plant,(.37,0,1.95),.30)
    else:
        for x in (-.34,.34):
            material='blue' if kind=='glass' else 'copper'
            box('cabinet door',(x,-.39,1.0),(.62,.10,1.55),material,.055)
            if kind=='glass':
                for z in (.36,1.65):box('glass frame',(x,-.45,z),(.62,.05,.12),'brown',.025)
                for s in (-1,1):box('glass frame',(x+s*.26,-.45,1.0),(.09,.05,1.38),'brown',.025)
            box('cabinet pull',(x-math.copysign(.18,x),-.48,1.04),(.055,.055,.25),'gold',.018)


def nightstand():
    box('nightstand body',(0,0,.43),(.75,.65,.73),'brown',.07)
    box('nightstand top',(0,0,.84),(.88,.75,.15),'copper',.05)
    for z in (.28,.60):
        box('nightstand drawer',(0,-.34,z),(.60,.06,.23),'copper',.03)
        box('drawer handle',(0,-.39,z),(.17,.055,.05),'gold',.015)


def shade_lamp(floor=False):
    h=1.90 if floor else .75
    cyl('lamp foot',(0,0,.065),.28 if floor else .22,.13,'brown')
    cyl('lamp stem',(0,0,h*.45),.045,h*.85,'gold')
    cone('lamp shade',(0,0,h),.43 if floor else .32,.24 if floor else .18,.50 if floor else .36,'shirt')
    cyl('lamp diffuser',(0,0,h-.25 if floor else h-.18),.35 if floor else .26,.025,'lamp')


def kitchen(fridge=False,stove=False):
    if fridge:
        box('refrigerator',(0,0,1.0),(1.0,.82,2.0),'cream',.15)
        for z,hh in ((.65,1.18),(1.62,.65)):
            box('fridge door',(0,-.44,z),(.93,.10,hh),'paper',.09)
            box('fridge handle',(-.29,-.52,z),(.07,.07,.35),'steel',.025)
        box('fridge note',(.18,-.51,1.65),(.24,.015,.27),'shirt',.015)
        sphere('note magnet',(.17,-.535,1.80),(.035,.015,.035),'red')
        return
    box('counter body',(0,0,.52),(1.83,.81,1.04),'brown',.07)
    box('countertop',(0,0,1.09),(1.99,.94,.14),'cream',.05)
    if stove:
        box('oven glass',(0,-.44,.49),(1.43,.045,.51),'dark_steel',.06)
        box('oven glow',(0,-.47,.49),(1.20,.015,.33),'gold',.035)
        box('oven handle',(0,-.51,.80),(1.28,.07,.07),'gold',.02)
        for x in (-.48,.48):
            for y in (-.20,.20):torus('stove burner',(x,y,1.19),.16,.035,'brown_dark')
        for x in (-.54,-.18,.18,.54):cyl('oven knob',(x,-.44,.94),.07,.06,'gold',rotation=(90,0,0))
        cyl('cooking pot',(.48,.16,1.40),.22,.36,'red');cyl('pot lid',(.48,.16,1.60),.26,.06,'brown');sphere('pot knob',(.48,.16,1.66),(.055,.055,.045),'gold')
    else:
        for x in (-.48,.48):
            box('kitchen door',(x,-.45,.58),(.82,.07,.76),'copper',.045)
            box('cabinet handle',(x*.60,-.50,.66),(.045,.05,.22),'gold',.015)
        box('sink rim',(.42,.0,1.19),(.76,.63,.06),'steel_light',.04)
        box('sink bowl',(.42,.0,1.225),(.60,.46,.03),'dark_steel',.035)
        tube('faucet',[(.42,.27,1.20),(.42,.27,1.67),(.42,.06,1.72),(.42,-.02,1.60)],.035,'steel')


def curtained_window():
    B.window((0,0,1.10),1.35,1.60)
    rod('curtain rod',(-1.0,-.28,2.05),(1.0,-.28,2.05),.05,'gold')
    for s in (-1,1):
        for i in range(3):box('curtain fold',(s*(.56+i*.12),-.28,1.12),(.17,.18,1.77),'paper' if i%2 else 'cream',.075)
        box('curtain tie',(s*.69,-.39,.90),(.45,.08,.13),'gold',.03)


def wall_clock():
    cyl('clock case',(0,0,.60),.60,.14,'brown',rotation=(90,0,0),vertices=12)
    cyl('clock dial',(0,-.09,.60),.50,.04,'paper',rotation=(90,0,0),vertices=12)
    for i in range(12):
        a=i*math.tau/12
        box('clock tick',(.40*math.sin(a),-.125,.60+.40*math.cos(a)),(.035,.025,.08),'brown_dark',.008,rotation=(0,math.degrees(a),0))
    rod('hour hand',(0,-.15,.60),(-.20,-.15,.75),.024,'brown_dark')
    rod('minute hand',(0,-.16,.60),(.26,-.16,.91),.018,'brown_dark')
    sphere('clock pin',(0,-.19,.60),(.045,.025,.045),'gold')


def wall_art():
    box('picture frame',(0,0,.63),(1.24,.13,1.26),'brown',.08)
    box('picture sky',(0,-.08,.63),(1.02,.035,1.04),'blue_light',.025)
    for x,z in ((-.22,.52),(.22,.49)):
        mountain=poly('picture mountain',[(x-.36,.19),(x,z+.28),(x+.36,.19)],.025,'green')
        mountain.location.y=-.115
    sphere('picture sun',(-.28,-.13,.95),(.12,.018,.12),'shirt')


for slug,name,fn in [('sofa','Sofa ba chỗ',B.sofa),('armchair','Ghế bành',armchair),('coffee-table','Bàn trà',table),
 ('dining-table','Bàn ăn',lambda:table(True)),('chair','Ghế gỗ',chair),('bed','Giường ngủ',bed),('nightstand','Tủ đầu giường',nightstand),
 ('table-lamp','Đèn ngủ',shade_lamp),('floor-lamp','Đèn đứng',lambda:shade_lamp(True)),('bookcase','Kệ sách',cabinet),
 ('glass-cabinet','Tủ kính',lambda:cabinet('glass')),('wardrobe','Tủ quần áo',lambda:cabinet('wardrobe')),('desk','Bàn học',lambda:table(desk=True)),
 ('kitchen-counter','Tủ bếp và chậu rửa',kitchen),('fridge','Tủ lạnh',lambda:kitchen(fridge=True)),('stove','Bếp và lò nướng',lambda:kitchen(stove=True)),
 ('curtained-window','Cửa sổ có rèm',curtained_window),('wall-clock','Đồng hồ treo tường',wall_clock),('wall-art','Tranh phong cảnh',wall_art)]:
    add(slug,name,'interiors',fn)


def tree(kind='green'):
    if kind=='pine':
        cyl('pine trunk',(0,0,.68),.18,1.36,'brown')
        for z,r in ((1.10,.80),(1.66,.65),(2.18,.46)):
            cone('pine bough',(0,0,z),r,.05,.92,'green_dark' if z<1.5 else 'green',vertices=8)
    else:
        cyl('tree trunk',(0,0,.84),.22,1.68,'brown',vertices=9)
        for s in (-1,1):rod('tree branch',(0,0,.80),(s*.43,0,1.72),.12,'brown')
        color={'green':'grass','blossom':'pink','autumn':'gold'}[kind]
        for x,y,z,scale in [(-.51,0,1.94,.66),(.50,.04,2.0,.67),(0,.33,2.22,.65),(0,-.32,2.36,.66),(-.38,-.29,2.48,.46),(.34,.22,2.64,.48)]:
            box('chunky foliage',(x,y,z),(scale*1.3,scale,scale),color,.19)
        if kind=='blossom':
            for x,y,z in [(-.54,-.40,2.13),(.44,-.32,2.43),(.02,-.67,2.55)]:
                flower((x,y,z),.16,'white',vertical=True)
    for x in (-.29,.29):rod('tree root',(0,0,.24),(x,-.10,.06),.09,'brown')


def flower(position=(0,0,0),scale=1,color='pink',vertical=False):
    x,y,z=position
    if not vertical:rod('flower stem',(x,y,z),(x,y,z+.60*scale),.023*scale,'green_dark')
    height=z if vertical else z+.64*scale
    for i in range(5):
        a=i*math.tau/5
        sphere('flower petal',(x+math.sin(a)*.14*scale,y-.03*scale,height+math.cos(a)*.14*scale),(.105*scale,.045*scale,.105*scale),color)
    sphere('flower center',(x,y-.09*scale,height),(.075*scale,.035*scale,.075*scale),'gold')
    if not vertical:
        for s in (-1,1):
            obj=sphere('flower leaf',(x+s*.10*scale,y,z+.30*scale),(.14*scale,.045*scale,.06*scale),'green')
            obj.rotation_euler.y=s*-.5


def bush(berries=False):
    for x,y,z in [(-.3,0,.30),(.28,.08,.32),(0,.12,.58),(0,-.19,.29)]:box('bush foliage',(x,y,z),(.53,.48,.51),'green',.18)
    for x,z in ((-.32,.45),(.05,.67),(.32,.33)):
        if berries:sphere('berry',(x,-.30,z),(.09,.08,.09),'red')
        else:flower((x,-.3,z),.34,'white',vertical=True)


def grass():
    for i in range(7):
        angle=(i-3)*.21
        blade=cone('grass blade',((i-3)*.07,0,.24+abs(i-3)*-.025),.055,.006,.58-abs(i-3)*.08,'grass',vertices=6)
        blade.rotation_euler.y=angle


def rock(moss=False):
    for i,(x,y,z,s) in enumerate([(-.34,.08,.36,.50),(.28,.16,.49,.61),(.02,-.31,.20,.36)]):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1,location=(x,y,z))
        obj=bpy.context.object;obj.scale=(s,s*.83,s*.80);B.finish(obj,'faceted rock','steel' if not moss else 'stone',.035)
        if moss:box('moss cap',(x,y,z+s*.60),(s*1.30,s*1.10,.13),'grass',.07)


def cliff():
    for row in range(3):
        for col in range(3):box('earth block',((col-1)*.48,0,.21+row*.39),(.46,.90,.37),'stone' if (row+col)%2 else 'brown',.065)
    for col in range(5):box('grass cliff lip',((col-2)*.31,-.02,1.33),(.33,.99,.21),'grass',.075)


def terrain(kind='grass'):
    box('terrain base',(0,0,.14),(2,2,.28),'stone',.07)
    color={'grass':'grass','path':'paper','river':'water'}[kind]
    box('terrain surface',(0,0,.31),(1.98,1.98,.13),color,.045)
    if kind=='grass':
        for x,y in [(-.62,-.48),(.52,.45)]:transform(grass,(x,y,.37),.34)
        flower((.49,-.45,.37),.45,'white')
    elif kind=='path':
        for x,y in [(-.4,-.5),(.3,.1),(-.2,.6)]:box('path stone',(x,y,.41),(.46,.35,.08),'steel_light',.09,rotation=(0,0,x*30))
    else:
        for x,y in [(-.55,-.50),(.36,.25),(-.20,.65)]:
            tube('water ripple',[(x-.20,y,.39),(x,y+.03,.39),(x+.18,y,.39)],.012,'blue_light')


def waterfall():
    cliff()
    box('waterfall flow',(0,-.53,.81),(.62,.06,1.13),'water',.025)
    for x in (-.16,.13):box('white water line',(x,-.57,.83),(.045,.015,.99),'blue_light',.015)
    box('river pool',(0,-.82,.16),(1.60,.83,.18),'water',.08)
    for x in (-.28,0,.28):sphere('water splash',(x,-.65,.29),(.15,.15,.10),'white')


def bridge():
    for i in range(9):
        x=(i-4)*.22;z=.45+.23*(1-(x/.90)**2)
        box('bridge deck plank',(x,0,z),(.21,1.06,.14),'copper',.04)
    for y in (-.56,.56):
        for x in (-.92,0,.92):
            box('bridge post',(x,y,.75),(.15,.15,1.10),'brown',.04)
            box('gold post cap',(x,y,1.34),(.22,.22,.13),'gold',.04)
        tube('curved bridge rail',[(-.95,y,.98),(-.50,y,1.13),(0,y,1.18),(.50,y,1.13),(.95,y,.98)],.055,'brown')


def fence():
    for x in (-.65,.65):
        box('fence post',(x,0,.50),(.16,.19,1.0),'brown',.035)
        box('post cap',(x,0,1.04),(.23,.25,.15),'gold',.04)
    for z in (.30,.72):box('fence rail',(0,0,z),(1.44,.14,.16),'copper',.035)


def planter():
    box('planter floor',(0,0,.13),(1.40,.70,.22),'brown',.04)
    for y in (-.36,.36):box('planter plank',(0,y,.30),(1.48,.10,.41),'copper',.04)
    for x in (-.72,.72):box('planter end',(x,0,.30),(.10,.70,.41),'brown',.04)
    box('planter earth',(0,0,.43),(1.31,.61,.03),'soil',.01)
    for x in (-.45,0,.45):transform(lambda:bush(True),(x,0,.44),.40)


for slug,name,fn in [('tree-green','Cây tán xanh',tree),('tree-blossom','Cây hoa hồng',lambda:tree('blossom')),('tree-pine','Cây thông',lambda:tree('pine')),
 ('tree-autumn','Cây mùa thu',lambda:tree('autumn')),('flower-bush','Bụi hoa',bush),('berry-bush','Bụi quả đỏ',lambda:bush(True)),
 ('hedge','Hàng rào cây',lambda:box('hedge',(0,0,.42),(1.6,.52,.84),'green',.16)),('grass','Bụi cỏ',grass),
 ('flowers','Cụm hoa nhiều màu',lambda:[flower((x,0,0),.7,c) for x,c in [(-.36,'pink'),(0,'gold'),(.36,'purple')]]),
 ('rocks','Cụm đá',rock),('moss-rocks','Đá phủ rêu',lambda:rock(True)),('cliff','Vách đất phủ cỏ',cliff),('river-tile','Mảnh mặt nước',lambda:terrain('river')),
 ('waterfall','Thác nước',waterfall),('bridge','Cầu gỗ',bridge),('fence','Hàng rào gỗ',fence),('signpost','Cột chỉ đường',B.arrow_sign),
 ('planter','Luống cây',planter),('stepping-stones','Đá bước chân',lambda:[box('stepping stone',(x,0,.09),(s,s*.7,.18),'steel_light',.08) for x,s in [(-.6,.45),(0,.55),(.6,.4)]]),
 ('grass-tile','Mảnh đất cỏ',terrain),('path-tile','Mảnh đường đất',lambda:terrain('path'))]:
    add(slug,name,'nature',fn)


REFS=['bf383b40-5b5e-4a8d-9431-4323e37e817c.png','c08414e1-7377-4a3f-b2ff-551093482db0.png',
      'f1f764c8-51fc-4f29-a061-bec64950dd99.png','195ec106-2ec2-444f-9c4c-1f72cae14cb1.png',
      'dd251996-0e18-48ba-ad9e-ee77c9ec90e5.png','b7d8974b-f142-461a-aa28-1176e3d759e9.png']
GROUPS={'characters':'Nhân vật','science':'Khoa học','mechanics':'Cơ khí và xe cộ','town':'Nhà phố','interiors':'Nội thất','nature':'Thiên nhiên'}


def build(slug,folder,root,resolution,samples):
    name,group,description,fn=ASSETS[slug]
    print('BUILD',slug,flush=True)
    B.reset(slug);B.PARENT['style_pack']=PACK
    fn();B.convert_curves()
    parent=B.PARENT;objects=[parent]+list(parent.children_recursive)
    lo,hi=B.bounds(objects)
    parent.location-=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
    bpy.context.view_layer.update();lo,hi=B.bounds(objects)
    dims=[round(float(v),4) for v in hi-lo]
    output=folder/(slug+'.glb')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.select_set(True)
    bpy.context.view_layer.objects.active=parent
    bpy.ops.export_scene.gltf(filepath=str(output),export_format='GLB',use_selection=True,export_animations=False,export_extras=True,export_apply=True)
    metadata={'name':name,'description':description+f' Bộ Story World, {GROUPS[group]}. Hình khối bo tròn theo ảnh tham khảo, vật liệu màu thật. Kích thước X/Y/Z={dims}; gốc giữa đáy, mặt trước -Y, Z lên. Mesh rời có tên; mô hình tĩnh, chưa rig.',
              'tags':[PACK,GROUPS[group],group,'hoạt hình','modular'],'source':'blender','pack':PACK,'category':group,
              'preview':output.with_suffix('.png').relative_to(root).as_posix(),'blend':output.with_suffix('.blend').relative_to(root).as_posix(),
              'dimensions':dims,'mesh_objects':sum(o.type=='MESH' for o in objects)}
    scene=B.setup_studio(lo,hi,resolution);scene.cycles.samples=samples
    scene.render.filepath=str(output.with_suffix('.png'))
    bpy.ops.wm.save_as_mainfile(filepath=str(output.with_suffix('.blend')))
    bpy.ops.render.render(write_still=True)
    output.with_suffix('.asset.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'slug':slug,'path':output.relative_to(root).as_posix(),**metadata}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--only');parser.add_argument('--resolution',type=int,default=384)
    parser.add_argument('--samples',type=int,default=12);parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();root=assets_dir();folder=root/'generated'/PACK
    folder.mkdir(parents=True,exist_ok=True)
    references=root/'references'/PACK;references.mkdir(parents=True,exist_ok=True)
    for filename in REFS:
        source=Path('D:/Downloads')/filename
        if source.is_file() and not (references/filename).exists():shutil.copyfile(source,references/filename)
    manifest=folder/'manifest.json'
    old=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {}
    entries={e['slug']:e for e in old.get('assets',[])}
    slugs=args.only.split(',') if args.only else list(ASSETS)
    if any(slug not in ASSETS for slug in slugs):raise ValueError('Unknown slug')
    for index,slug in enumerate(slugs):
        if args.resume and slug in entries and all((folder/(slug+suffix)).is_file() for suffix in ('.glb','.blend','.png','.asset.json')):
            continue
        entries[slug]=build(slug,folder,root,args.resolution,args.samples)
        manifest.write_text(json.dumps({'pack':PACK,'groups':GROUPS,'palette':B.PALETTE,'references':[str(p.relative_to(root).as_posix()) for p in references.glob('*.png')],
                                       'assets':list(entries.values())},ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'DONE {index+1}/{len(slugs)} {slug}',flush=True)
    print('PACK READY',len(entries),'assets',folder,flush=True)


if __name__=='__main__':main()
