"""Native Blender library from the two Universal Core / Interior reference sheets."""
import argparse
from functools import partial
import json
import math
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codex_blender.config import ROOT, assets_dir
from scripts import build_story_world as W
import bpy
from mathutils import Vector

B=W.B
box,sphere,cyl,rod,tube=B.box,B.sphere,B.cyl,B.rod,B.tube
PACK='universal-interior-v1'
GROUPS={
 'primitives':'A · Khối cơ bản','structure':'B · Tấm và kết cấu','pipes':'C · Ống nối',
 'joints':'D · Bản lề và khớp','motion':'E · Bánh xe và truyền động','controls':'F · Tay nắm và điều khiển',
 'fasteners':'G · Bu lông và chi tiết nối','panels':'H · Panel và khung','openings':'I · Cửa và cửa sổ',
 'barriers':'J · Lan can và thang','containers':'K · Hòm và thùng','signs':'L · Mái hiên và biển bảng',
 'fixtures':'M · Đèn và tín hiệu','environment':'N · Đồ vật thiên nhiên','tiles':'O · Bề mặt module',
 'core-examples':'P · Ví dụ lắp ghép','seating':'Nội thất · Ghế','tables':'Nội thất · Bàn',
 'beds':'Nội thất · Giường','storage':'Nội thất · Tủ kệ','lighting':'Nội thất · Đèn',
 'kitchen':'Nội thất · Nhà bếp','kitchenware':'Nội thất · Đồ dùng bếp','learning':'Nội thất · Học tập và làm việc',
 'decor':'Nội thất · Trang trí','interior-modules':'Nội thất · Module kiến trúc','rooms':'Nội thất · Diorama',
 'character':'Nhân vật tham khảo'}
ASSETS={}
REFERENCES=['dc1f72c9-861b-4774-b204-0ed8b3806d9d.png','376e0ba1-e6e2-4ab4-aa57-1e3b45f04f11.png']


def add(slug,name,group,fn,description=None):
    ASSETS[slug]=(name,group,description or name,fn)


def hollow(name,points,outer=.18,inner=.12,material='steel',segments=32):
    """Swept annular mesh with actual open bores, including curved elbows."""
    points=list(map(Vector,points));vertices=[]
    for i,p in enumerate(points):
        tangent=(points[min(i+1,len(points)-1)]-points[max(0,i-1)]).normalized()
        reference=Vector((0,0,1)) if abs(tangent.z)<.9 else Vector((0,1,0))
        u=tangent.cross(reference).normalized();v=tangent.cross(u).normalized()
        for radius in (outer,inner):
            vertices.extend(tuple(p+radius*(u*math.cos(j*math.tau/segments)+v*math.sin(j*math.tau/segments))) for j in range(segments))
    faces=[];stride=2*segments
    for i in range(len(points)-1):
        for side in range(2):
            for j in range(segments):
                a=i*stride+side*segments+j;b=i*stride+side*segments+(j+1)%segments
                face=(a,b,b+stride,a+stride)
                faces.append(face if side==0 else face[::-1])
    for i in (0,len(points)-1):
        for j in range(segments):
            a=i*stride+j;b=i*stride+(j+1)%segments
            faces.append((a,a+segments,b+segments,b))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    return B.finish(obj,name,material,.012)


def lathe(name,profile,material='cream',segments=40):
    vertices=[(radius*math.cos(j*math.tau/segments),radius*math.sin(j*math.tau/segments),z)
              for radius,z in profile for j in range(segments)]
    faces=[(i*segments+j,i*segments+(j+1)%segments,(i+1)*segments+(j+1)%segments,(i+1)*segments+j)
           for i in range(len(profile)-1) for j in range(segments)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    obj=B.finish(obj,name,material)
    for polygon in mesh.polygons:polygon.use_smooth=True
    return obj


def frame(name,width=1,height=1,depth=.13,material='gold',z=None,rounded=False):
    z=height/2 if z is None else z
    if rounded:
        r=min(width,height)*.20
        points=[]
        for cx,cz,start in [(width/2-r,z+height/2-r,0),(-width/2+r,z+height/2-r,90),
                            (-width/2+r,z-height/2+r,180),(width/2-r,z-height/2+r,270)]:
            points.extend((cx+r*math.cos(math.radians(start+a)),0,cz+r*math.sin(math.radians(start+a))) for a in range(0,91,15))
        tube(name,points,depth/2,material,cyclic=True)
    else:
        for x in (-width/2,width/2):box(name+' side',(x,0,z),(depth,depth,height),material,.035)
        for zz in (z-height/2,z+height/2):box(name+' rail',(0,0,zz),(width,depth,depth),material,.035)


def arch_block(width=1.2,height=1.2,depth=.5,wall=False):
    radius=width*.27;spring=height*.40
    points=[(-width/2,0),(-width/2,height),(width/2,height),(width/2,0),(radius,0),(radius,spring)]
    points += [(radius*math.cos(i*math.pi/24),spring+radius*math.sin(i*math.pi/24)) for i in range(1,25)]
    points += [(-radius,0)]
    B.poly('Arch opening',points,depth,'cream',.04)
    if wall:
        for s in (-1,1):box('Pillar cap',(s*(width/2-.08),0,height),(.23,depth+.1,.14),'brown',.03)


def steps(width=1.0,depth=1.0,height=.9,count=3,rails=False):
    for i in range(count):
        box('Step %02d'%i,(0,-depth/2+(i+.5)*depth/count,(i+1)*height/(2*count)),
            (width,depth/count-.01,(i+1)*height/count),'copper' if rails else 'cream',.035)
    if rails:
        for x in (-width*.55,width*.55):
            for y,z in [(-depth*.42,height/count+.4),(depth*.42,height+.4)]:
                box('Stair rail post',(x,y,z/2),(.12,.12,z),'brown',.025)
                box('Post cap',(x,y,z),(.19,.19,.1),'copper',.025)
            rod('Sloping handrail',(x,-depth*.5,height/count+.35),(x,depth*.5,height+.35),.045,'copper')


def pipe(kind):
    if kind=='cap':
        cyl('Pipe cap shell',(0,0,.2),.24,.4,'steel');cyl('Gold clamp',(0,0,.07),.255,.13,'gold');return
    if kind=='elbow':
        pts=[(.40-.4*math.cos(i*math.pi/2/16),0,.23+.4*math.sin(i*math.pi/2/16)) for i in range(17)]
        hollow('Elbow bore',pts)
        hollow('Lower collar',[(0,0,.18),(0,0,.30)],.23,.12,'gold')
        hollow('Upper collar',[(.34,0,.63),(.47,0,.63)],.23,.12,'steel_light');return
    hollow('Main pipe',[(-.55,0,.24),(.55,0,.24)])
    for x in (-.52,.52):hollow('End collar',[(x-.04,0,.24),(x+.04,0,.24)],.23,.12,'steel_light')
    if kind in {'tee','cross'}:
        # Branches share a central chamber; boolean cutters open the intersection.
        for sign in ([1] if kind=='tee' else [-1,1]):
            hollow('Branch pipe',[(0,0,.24),(0,sign*.5,.24)])
            hollow('Branch collar',[(0,sign*.44,.24),(0,sign*.56,.24)],.23,.12,'gold')
        cutters=[]
        for a,b in [((-.65,0,.24),(.65,0,.24)),((0,-.65,.24),(0,.65,.24))]:
            cutter=rod('Bore cutter',a,b,.12,'steel');cutters.append(cutter)
        for obj in list(B.PARENT.children):
            if obj in cutters:continue
            for cutter in cutters:
                mod=obj.modifiers.new('Open connector bore','BOOLEAN');mod.operation='DIFFERENCE';mod.object=cutter
                bpy.context.view_layer.objects.active=obj
                bpy.ops.object.modifier_apply(modifier=mod.name)
        for cutter in cutters:bpy.data.objects.remove(cutter,do_unlink=True)


def hinge():
    for x in (-.29,.29):
        box('Hinge leaf',(x,0,.4),(.43,.10,.78),'steel',.035)
        for z in (.15,.65):cyl('Leaf screw',(x,-.065,z),.045,.035,'steel_light',rotation=(90,0,0))
    for i in range(3):cyl('Hinge knuckle',(0,0,.15+i*.25),.12,.23,'gold' if i==1 else 'steel')
    cyl('Hinge pin',(0,0,.40),.05,.86,'gold')


def bracket(kind='L'):
    box('Bracket flange',(0,0,.09),(.8,.55,.18),'steel',.035)
    box('Bracket upright',(0,.19,.42),(.8,.18,.72),'steel',.035)
    if kind=='T':box('T crossbar',(0,.19,.78),(1.15,.18,.22),'steel',.035)
    for x in (-.24,.24):cyl('Bolt recess',(x,-.03,.19),.055,.018,'dark_steel')
    for x in (-.24,.24):cyl('Wall recess',(x,.08,.56),.055,.018,'dark_steel',rotation=(90,0,0))


def pivot():
    box('Pivot foot',(0,0,.09),(.65,.55,.18),'steel',.04)
    for y in (-.16,.16):box('Pivot cheek',(0,y,.39),(.22,.14,.65),'steel',.045)
    cyl('Joint barrel',(0,0,.65),.22,.48,'steel',rotation=(90,0,0))
    cyl('Golden pivot axle',(0,-.04,.65),.115,.58,'gold',rotation=(90,0,0))


def clamp():
    box('Clamp back',(0,.10,.4),(.85,.15,.8),'steel',.035)
    for x in (-.34,.34):box('Clamp jaw',(x,-.10,.4),(.18,.44,.8),'steel',.03)
    box('Adjustable clamp',(0,-.35,.4),(.5,.12,.2),'gold',.025)
    rod('Clamp spindle',(-.22,-.40,.4),(.22,-.40,.4),.055,'dark_steel')


def wheel(spoked=False,pulley=False):
    if pulley:
        B.ring('Pulley groove',(0,0,.52),.47,.14,.12,'steel')
        for y in (-.09,.09):B.ring('Pulley lip',(0,y,.52),.52,.14,.045,'steel_light')
    else:
        B.ring('Rubber tire',(0,0,.5),.5,.34,.24,'sole')
        if spoked:
            B.ring('Wheel rim',(0,-.02,.5),.35,.28,.26,'gold')
            for i in range(8):
                a=i*math.tau/8
                rod('Spoke',(0,-.10,.5),(.29*math.cos(a),-.10,.5+.29*math.sin(a)),.035,'gold')
        else:
            cyl('Wheel hub',(0,0,.5),.33,.27,'steel',rotation=(90,0,0))
            for i in range(16):
                a=i*math.tau/16
                box('Tread block',(.46*math.sin(a),0,.5+.46*math.cos(a)),(.13,.28,.12),'sole',.025,rotation=(0,math.degrees(a),0))
    cyl('Axle boss',(0,-.16,.5),.13,.12,'steel_light',rotation=(90,0,0))


def handle(kind):
    if kind=='pull':
        tube('Pull handle',[(-.4,.03,.14),(-.4,0,.4),(-.30,0,.48),(.3,0,.48),(.4,0,.4),(.4,0,.14)],.07,'steel')
    elif kind=='bar':
        for x in (-.4,.4):cyl('Handle mount',(x,0,.16),.085,.32,'gold')
        rod('Grip',(-.4,0,.36),(.4,0,.36),.09,'steel')
    elif kind in {'round','button'}:
        cyl('Knob spindle',(0,0,.14),.10,.28,'steel')
        if kind=='round':sphere('Round knob',(0,0,.42),(.23,.23,.23),'gold')
        else:box('Button',(0,0,.38),(.44,.44,.3),'gold',.075)
    elif kind=='lever':
        box('Lever base',(0,0,.07),(.6,.5,.14),'steel',.045)
        rod('Lever shaft',(0,0,.12),(.2,0,.65),.055,'steel_light');sphere('Lever ball',(.2,0,.65),(.16,.16,.16),'red')
    else:
        cyl('Valve stem',(0,0,.16),.10,.32,'steel')
        hollow('Valve wheel',[(0,0,.38),(0,0,.46)],.40,.30,'red')
        for i in range(3):
            a=i*math.tau/3
            rod('Valve spoke',(0,0,.42),(.34*math.cos(a),.34*math.sin(a),.42),.045,'red')


def fastener(kind):
    if kind in {'washer','nut'}:
        if kind=='washer':hollow('Washer',[(0,0,.03),(0,0,.11)],.32,.15,'steel_light')
        else:
            obj=cyl('Hex nut',(0,0,.14),.35,.28,'steel_light',vertices=6)
            cutter=cyl('Nut bore',(0,0,.14),.15,.8,'steel',bevel=0)
            mod=obj.modifiers.new('Thread bore','BOOLEAN');mod.object=cutter
            bpy.context.view_layer.objects.active=obj;bpy.ops.object.modifier_apply(modifier=mod.name)
            bpy.data.objects.remove(cutter,do_unlink=True)
        return
    cyl('Fastener shaft',(0,0,.32),.10,.64,'steel_light')
    if kind=='pin':
        for z in (.08,.60):cyl('Pin shoulder',(0,0,z),.16,.12,'steel')
        return
    cyl('Fastener head',(0,0,.73),.26,.18,'steel_light',vertices=6 if kind=='bolt' else 32)
    points=[(.105*math.cos(i*math.tau/18),.105*math.sin(i*math.tau/18),.07+i*.50/90) for i in range(91)]
    tube('Thread ridge',points,.017,'steel')
    if kind=='screw':
        for angle in (0,90):box('Phillips recess',(0,0,.83),(.29,.045,.012),'dark_steel',.008,rotation=(0,0,angle))


def panel(kind):
    if kind in {'square','rounded'}:frame('Frame',.9,1,.14,'gold',rounded=kind=='rounded');return
    if kind=='grid':
        frame('Grate border',.9,1,.10,'steel')
        for x in (-.22,0,.22):box('Grate vertical',(x,0,.5),(.045,.09,.93),'steel',.012)
        for z in (.25,.5,.75):box('Grate horizontal',(0,0,z),(.88,.09,.045),'steel',.012)
        return
    box('Panel',(0,0,.5),(.9,.12,1),'cream' if kind=='plain' else 'steel',.07)
    if kind=='vent':
        for z in (.22,.40,.58,.76):
            box('Vent opening',(0,-.07,z),(.66,.02,.09),'dark_steel',.025)
            box('Vent slat',(0,-.10,z+.035),(.68,.07,.055),'steel_light',.02)
    elif kind=='riveted':
        for x in (-.34,.34):
            for z in (.14,.86):sphere('Panel rivet',(x,-.085,z),(.045,.025,.045),'steel_light')


def door(kind='solid',color='copper'):
    width,height=1,1.9
    if kind=='arch':
        points=[(-.5,0),(.5,0),(.5,1.4)]+[(.5*math.cos(i*math.pi/24),1.4+.5*math.sin(i*math.pi/24)) for i in range(1,25)]
        B.poly('Arched door',points,.12,color,.045)
    else:box('Door panel',(0,0,height/2),(width,.12,height),color,.06)
    frame('Door jamb',width+.12,height+.08,.09,'brown')
    for x in (-.32,-.10,.12,.34):box('Wood seam',(x,-.068,.75),(.012,.01,1.32),'brown',.003)
    if kind=='window':
        box('Door glass',(0,-.085,1.37),(.61,.035,.60),'glass',.035)
        frame('Glass frame',.66,.65,.065,'gold',z=1.37)
    sphere('Door knob',(.31,-.13,.85),(.065,.045,.065),'gold')


def window(kind='square'):
    if kind=='round':
        B.ring('Round window frame',(0,0,.65),.65,.51,.15,'copper')
        cyl('Round glass',(0,0,.65),.50,.06,'blue',rotation=(90,0,0))
        rod('Window cross',(-.5,-.08,.65),(.5,-.08,.65),.035,'gold')
        rod('Window mullion',(0,-.08,.14),(0,-.08,1.16),.035,'gold')
    else:B.window((0,0,.75),1.2,1.5,arched=kind=='arch')


def railing(kind='straight'):
    if kind=='balcony':B.balcony((0,0,0),1.5);return
    for x in (-.68,.68):
        box('Barrier post',(x,0,.5),(.14,.16,1),'brown',.03)
        box('Barrier cap',(x,0,1.03),(.22,.24,.12),'gold',.035)
    for z in (.20,.88):box('Barrier rail',(0,0,z),(1.5,.12,.10),'copper',.025)
    for x in (-.36,0,.36):
        box('Baluster',(x,0,.53),(.10,.10,.65),'cream' if kind=='picket' else 'steel',.025)
        if kind=='picket':
            triangle=B.poly('Picket tip',[(x-.08,.84),(x,.99),(x+.08,.84)],.1,'cream');triangle.location.y=0


def ladder(step=False):
    for side in (-1,1):
        rod('Ladder stile',(side*.39,-.24 if step else 0,0),(side*.39,.12 if step else 0,1.8),.055,'copper',rectangular=(.12,.12))
        if step:rod('Rear support',(side*.39,.65,0),(side*.39,.12,1.8),.055,'brown',rectangular=(.12,.12))
    for i in range(5):
        z=.22+i*.32;y=(-.24+.36*z/1.8) if step else 0
        box('Ladder rung',(0,y,z),(.82,.25 if step else .12,.09),'gold',.025)
    if step:box('Top platform',(0,.12,1.8),(.98,.48,.13),'gold',.04)


def barrel():
    lathe('Barrel staves',[(0,0),(.38,0),(.46,.25),(.48,.55),(.43,.95),(.35,1.05),(0,1.05)],'copper')
    for z,r in [(.14,.43),(.84,.46)]:hollow('Barrel hoop',[(0,0,z),(0,0,z+.1)],r+.025,r-.025,'steel')
    for i in range(10):
        a=i*math.tau/10
        tube('Stave seam',[(r*math.cos(a),r*math.sin(a),z) for r,z in [(.385,.05),(.465,.3),(.485,.55),(.45,.85),(.36,1.02)]],.008,'brown')


def storage_box(handle=False,reinforced=False):
    if handle:
        box('Crate floor',(0,0,.07),(1.10,.72,.14),'brown',.035)
        for y in (-.36,.36):
            for z in (.24,.47,.70):box('Open box plank',(0,y,z),(1.16,.10,.21),'copper',.025)
        for x in (-.54,.54):box('End panel',(x,0,.43),(.10,.68,.70),'brown',.035)
        for x in (-.24,.24):box('Carrying handle upright',(x,0,.96),(.10,.12,.55),'gold',.03)
        rod('Carrying grip',(-.24,0,1.20),(.24,0,1.20),.065,'brown')
        return
    B.crate()
    if reinforced:
        for x in (-.48,.48):
            for z in (.1,.9):box('Metal corner strap',(x,-.49,z),(.18,.06,.18),'steel',.025)
    if handle:
        for obj in B.PARENT.children_recursive:
            if 'diagonal' in obj.name.lower():obj.hide_render=True
        box('Handle recess',(0,-.515,.68),(.36,.025,.10),'brown_dark',.035)


def sack():
    sphere('Canvas sack',(0,0,.42),(.4,.31,.46),'cream')
    W.cone('Gathered neck',(0,0,.84),.14,.23,.22,'paper')
    B.torus('Sack tie',(0,0,.79),.15,.025,'brown')


def chest():
    box('Chest body',(0,0,.35),(1.1,.66,.7),'brown',.10)
    box('Chest lid',(0,0,.74),(1.15,.71,.28),'copper',.13)
    for x in (-.39,.39):box('Chest band',(x,0,.45),(.10,.76,.88),'gold',.025)
    box('Lock plate',(0,-.40,.52),(.26,.08,.31),'gold',.035)
    cyl('Keyhole',(0,-.45,.55),.04,.02,'brown_dark',rotation=(90,0,0))


def awning(striped=True):
    for i in range(6):
        x=(i-2.5)*.26
        box('Awning roof',(x,0,.52),(.265,.80,.12),'red' if striped and i%2==0 else 'paper' if striped else 'blue',.05,rotation=(15,0,0))
        sphere('Scallop valance',(x,-.39,.37),(.132,.08,.16),'red' if striped and i%2==0 else 'paper' if striped else 'blue')


def sign(kind):
    if kind=='hanging':
        for x in (-.55,.55):cyl('Hanger',(x,0,1),.055,.7,'brown')
        rod('Sign crossbar',(-.65,0,1.45),(.65,0,1.45),.06,'copper')
        box('Hanging wooden sign',(0,0,.65),(1.1,.14,.65),'copper',.05)
    elif kind=='aframe':
        for y in (-.22,.22):
            for x in (-.40,.40):rod('A-frame leg',(x,y,0),(x,0,1.2),.045,'brown',rectangular=(.09,.09))
        box('Blackboard sign',(0,-.11,.72),(.90,.12,.95),'blackboard',.06,rotation=(-10,0,0))
        frame('Sign trim',.86,.91,.05,'gold',z=.72)
        B.poly('Sign arrow',[(-.22,.60),(.10,.60),(.10,.50),(.29,.72),(.10,.94),(.10,.84),(-.22,.84)],.025,'paper').location.y=-.20
    else:
        for x in (-.65,.65):box('Billboard post',(x,0,.8),(.12,.14,1.6),'brown',.03)
        box('Billboard panel',(0,0,1.1),(1.6,.15,1.1),'cream',.04)
        frame('Billboard trim',1.65,1.15,.12,'copper',z=1.1)


def lantern(hanging=False):
    for x in (-.19,.19):
        for y in (-.16,.16):box('Lantern corner',(x,y,.45),(.045,.045,.60),'brown',.015)
    box('Lamp base',(0,0,.13),(.48,.43,.13),'brown',.025)
    W.cone('Lantern cap',(0,0,.82),.35,.19,.18,'brown',vertices=4)
    box('Lamp glow',(0,0,.46),(.28,.25,.50),'lamp',.035)
    B.ring('Hanging loop',(0,0,1),.14,.09,.04,'brown')
    if hanging:rod('Hanging bracket',(-.30,0,1.2),(.1,0,1.2),.045,'brown')


def fixture(kind):
    if kind=='street':W.streetlamp();return
    if kind=='hanging':lantern(True);return
    if kind=='beacon':
        cyl('Beacon base',(0,0,.10),.31,.2,'steel')
        sphere('Alert dome',(0,0,.35),(.25,.25,.31),'red');sphere('Alert glow',(0,-.18,.45),(.10,.08,.12),'lamp');return
    if kind=='wall':
        box('Wall fitting',(0,.2,.35),(.28,.12,.6),'brown',.05)
        tube('Wall lamp neck',[(0,.2,.35),(0,0,.35),(0,-.12,.5)],.05,'brown')
    else:cyl('Ceiling lamp stem',(0,0,.45),.045,.9,'brown')
    W.cone('Lamp shade',(0,0,.32),.35,.12,.28,'brown')
    sphere('Warm bulb',(0,0,.18),(.20,.20,.15),'lamp')


def tile(kind):
    if kind in {'road-straight','road-corner','road-intersection'}:
        W.road({'road-straight':'straight','road-corner':'corner','road-intersection':'cross'}[kind]);return
    if kind=='ground':W.terrain();return
    if kind=='water':W.terrain('river');return
    wall=kind.startswith('wall-')
    if kind=='wall-plaster':box('Plaster tile',(0,0,1),(2,.18,2),'cream',.07);return
    if wall:
        for row in range(4 if kind=='wall-brick' else 3):
            for col in range(4 if kind=='wall-brick' else 3):
                n=4 if kind=='wall-brick' else 3
                box('Wall block',(-1+(col+.5)*2/n,0,(row+.5)*2/n),(2/n-.025,.22,2/n-.025),'copper' if kind=='wall-brick' else 'stone',.04)
        return
    n=5 if kind=='floor-wood' else 2 if kind=='floor-tile' else 3
    for row in range(n):
        for col in range(1 if kind=='floor-wood' else n):
            width=2 if kind=='floor-wood' else 2/n
            box('Floor surface',((col+.5)*width-1,(row+.5)*2/n-1,.09),(width-.02,2/n-.02,.18),
                'copper' if kind=='floor-wood' else 'paper' if kind=='floor-tile' else 'stone',.035)


# Core sheet: one standalone asset per labeled object or variant.
for slug,name,fn in [
 ('cube','Cube',lambda:box('Cube',(0,0,.5),(1,1,1),'cream',.06)),
 ('prism','Rectangular Prism',lambda:box('Prism',(0,0,.3),(1.5,.7,.6),'cream',.06)),
 ('cylinder','Cylinder',lambda:cyl('Cylinder',(0,0,.5),.45,1,'cream')),
 ('cone','Cone',lambda:W.cone('Cone',(0,0,.55),.45,0,1.1,'gold')),
 ('rounded-cube','Rounded Cube',lambda:box('Rounded cube',(0,0,.5),(1,1,1),'cream',.24)),
 ('sphere','Sphere',lambda:sphere('Sphere',(0,0,.5),(.5,.5,.5),'cream')),
 ('wedge','Wedge',lambda:B.poly('Wedge',[(-.6,0),(.6,0),(.6,1)],.7,'cream',.035)),
 ('arch','Arch Block',arch_block),('stair','Stair Block',steps),
 ('corner-l','Corner Block L',lambda:[box('Corner base',(0,0,.2),(1,.7,.4),'cream'),box('Corner riser',(.3,0,.6),(.4,.7,.8),'cream')]),
 ('roof-slope','Roof Slope',lambda:[B.poly('Roof wedge',[(-.6,0),(.6,0),(.6,.6)],.9,'red'),box('Roof seam',(.24,0,.47),(.04,.92,.05),'brown',.008,rotation=(0,-27,0))])]:
    add('core-'+slug,name,'primitives',fn)
for slug,name,fn in [
 ('plate','Plate Thin',lambda:box('Thin plate',(0,0,.06),(1,.8,.12),'cream',.025)),
 ('round-plate','Rounded Plate',lambda:cyl('Round plate',(0,0,.07),.5,.14,'cream')),
 ('beam','Beam Long',lambda:box('Beam',(0,0,.13),(1.8,.3,.26),'copper',.035)),
 ('plank','Wood Plank',lambda:[box('Plank',(0,y,.07),(1.8,.18,.14),'copper',.02) for y in (-.2,0,.2)]),
 ('column','Column Segment',lambda:[cyl('Shaft',(0,0,.5),.22,.8,'cream'),cyl('Capital',(0,0,.94),.3,.15,'cream'),cyl('Plinth',(0,0,.08),.3,.16,'cream')]),
 ('column-stack','Column Stack',lambda:[box('Stack block',(0,0,.16+i*.3),(.5,.5,.29),'cream' if i<3 else 'brown',.04) for i in range(4)])]:add('core-'+slug,name,'structure',fn)
for kind in ('straight','elbow','tee','cross','cap'):add('core-pipe-'+kind,'Pipe '+kind,'pipes',partial(pipe,kind))
for slug,name,fn in [('hinge','Hinge',hinge),('pivot','Pivot Joint',pivot),('clamp','Clamp',clamp),('bracket-l','Bracket L',bracket),('bracket-t','Bracket T',partial(bracket,'T'))]:add('core-'+slug,name,'joints',fn)
for slug,name,fn in [('wheel-solid','Solid Wheel',wheel),('wheel-spoke','Spoked Wheel',partial(wheel,True)),
 ('axle','Axle Rod',lambda:rod('Axle',(-.65,0,.13),(.65,0,.13),.10,'steel_light')),
 ('gear-small','Small Gear',lambda:B.gear('Small gear',radius=.4,material='steel',teeth=8)),
 ('gear-large','Large Gear',lambda:B.gear('Large gear',center=(0,0,.65),radius=.65,teeth=10)),
 ('pulley','Pulley Wheel',partial(wheel,pulley=True))]:add('core-'+slug,name,'motion',fn)
for kind in ('pull','bar','round','button','lever','valve'):add('core-control-'+kind,'Control '+kind,'controls',partial(handle,kind))
for kind in ('bolt','screw','nut','washer','pin'):add('core-'+kind,kind.title(),'fasteners',partial(fastener,kind))
for kind in ('plain','vent','riveted','square','rounded','grid'):add('core-panel-'+kind,'Panel '+kind,'panels',partial(panel,kind))
for kind in ('solid','window'):add('core-door-'+kind,'Door '+kind,'openings',partial(door,kind))
for kind in ('square','arch','round'):add('core-window-'+kind,'Window '+kind,'openings',partial(window,kind))
for kind in ('straight','balcony','picket'):add('core-railing-'+kind,'Railing '+kind,'barriers',partial(railing,kind))
add('core-ladder','Ladder','barriers',ladder);add('core-stepladder','Step Ladder','barriers',partial(ladder,True))
for slug,name,fn in [('crate','Wood Crate',B.crate),('crate-reinforced','Reinforced Crate',partial(storage_box,reinforced=True)),
 ('barrel','Barrel',barrel),('box-handle','Box with Handle',partial(storage_box,True)),('sack','Sack',sack),('chest','Locked Chest',chest)]:add('core-'+slug,name,'containers',fn)
add('core-awning-stripes','Striped Awning','signs',awning);add('core-awning-solid','Solid Awning','signs',partial(awning,False))
for kind in ('hanging','aframe','billboard'):add('core-sign-'+kind,'Sign '+kind,'signs',partial(sign,kind))
for kind in ('street','hanging','wall','ceiling','beacon'):add('core-light-'+kind,'Light '+kind,'fixtures',partial(fixture,kind))
for slug,name,fn in [('bush-small','Small Bush',lambda:W.transform(W.bush,scale=.65)),('bush-large','Large Bush',W.bush),
 ('plant','Potted Plant',B.leafy_plant),('grass','Grass Clump',W.grass),
 ('rock-small','Small Rock',lambda:box('Small rock',(0,0,.2),(.6,.5,.4),'stone',.15)),
 ('rock-large','Large Rock',W.rock),('water','Water Tile',partial(tile,'water'))]:add('core-'+slug,name,'environment',fn)
for kind in ('floor-tile','floor-wood','floor-stone','wall-brick','wall-stone','wall-plaster',
             'road-straight','road-corner','road-intersection','ground'):add('core-tile-'+kind,'Tile '+kind,'tiles',partial(tile,kind))


def stool():
    cyl('Stool seat',(0,0,.82),.39,.16,'copper')
    for i in range(4):
        a=i*math.tau/4+math.pi/4
        rod('Stool leg',(.29*math.cos(a),.29*math.sin(a),0),(.22*math.cos(a),.22*math.sin(a),.77),.055,'brown')


def round_table():
    cyl('Round tabletop',(0,0,1.1),.72,.16,'copper')
    cyl('Table pedestal',(0,0,.57),.12,1.06,'brown')
    cyl('Pedestal foot',(0,0,.09),.44,.18,'brown')


def coffee_table():
    W.table()
    box('Table runner',(0,-.08,.76),(.34,.94,.025),'paper',.01)
    box('Runner drape',(0,-.50,.64),(.34,.035,.23),'cream',.02)
    W.transform(partial(cup,'cup'),(-.42,-.1,.75),.42)


def bunk_bed():
    W.bed()
    W.transform(W.bed,(0,0,1.48),1)
    for x in (-.7,.7):
        for y in (-1,1):box('Bunk upright',(x,y,1.55),(.18,.18,3.1),'brown',.035)
    for x in (-.72,.72):
        for z in (2.48,2.75):box('Safety rail',(x,0,z),(.1,2,.10),'copper',.025)
    W.transform(ladder,(1,-.72,0),1.25)


def cabinet(kind='plain'):
    if kind=='rack':
        for x in (-.63,.63):
            for y in (-.23,.23):box('Rack upright',(x,y,1),(.09,.09,2),'steel',.02)
        for z in (.15,.75,1.35,1.95):
            box('Rack shelf',(0,0,z),(1.38,.63,.12),'copper',.025)
            if z<1.5:box('Shelf box',(-.23,0,z+.22),(.70,.45,.32),'paper',.04)
        return
    if kind=='bookcase':W.cabinet();return
    W.cabinet('glass' if kind=='display' else 'wardrobe')
    if kind=='display':
        for obj in B.PARENT.children_recursive:
            if 'cabinet door' in obj.name:
                obj.data.materials.clear();obj.data.materials.append(B.mat('glass'))
        for z in (.35,.74):
            box('Display drawer',(0,-.44,z),(1.13,.08,.25),'copper',.035)
            box('Drawer pull',(0,-.50,z),(.30,.06,.055),'gold',.02)
    if kind=='plain':
        for obj in B.PARENT.children_recursive:obj.location.z*=.78;obj.scale.z*=.78


def pendant():
    cyl('Ceiling rose',(0,0,1.2),.12,.08,'brown')
    cyl('Pendant cord',(0,0,.77),.025,.86,'brown_dark')
    W.cone('Pendant shade',(0,0,.34),.39,.13,.30,'brown')
    cyl('Pendant glow',(0,0,.18),.32,.03,'lamp')


def jar(color='gold',height=.35):
    cyl('Spice jar',(0,0,height/2),.13,height,'paper')
    cyl('Jar lid',(0,0,height+.025),.15,.07,color)


def counter(sink=False,lab=False):
    box('Counter carcass',(0,0,.52),(1.8,.78,1.04),'steel' if lab else 'brown',.05)
    box('Countertop',(0,0,1.10),(1.94,.9,.15),'paper',.045)
    for x in (-.45,.45):
        box('Counter door',(x,-.42,.48),(.78,.08,.78),'steel_light' if lab else 'copper',.035)
        box('Door handle',(x,-.48,.55),(.05,.06,.22),'gold',.02)
    if sink:
        # Rim and a recessed, open basin built from five surfaces.
        box('Basin floor',(0,0,1.105),(.66,.43,.025),'dark_steel',.015)
        for x in (-.37,.37):box('Sink side',(x,0,1.18),(.07,.58,.14),'steel_light',.02)
        for y in (-.26,.26):box('Sink lip',(0,y,1.18),(.80,.07,.14),'steel_light',.02)
        tube('Gooseneck faucet',[(0,.30,1.2),(0,.30,1.62),(0,.18,1.74),(0,0,1.74),(0,-.06,1.59)],.04,'steel')
        box('Sink towel',(.65,-.40,.97),(.30,.06,.42),'cream',.025)
    elif lab:
        W.transform(W.test_tubes,(-.54,.05,1.20),.5)
        W.transform(W.vessel,(.16,0,1.20),.52)
        W.transform(partial(W.vessel,'round','purple'),(.63,.05,1.20),.5)
    else:
        for x,col in [(-.60,'gold'),(-.23,'copper'),(.45,'brown')]:W.transform(partial(jar,col),(x,0,1.18),.65)


def refrigerator():
    box('Fridge back',(0,.38,1.05),(1,.10,2.1),'cream',.09)
    for x in (-.45,.45):box('Fridge side',(x,0,1.05),(.12,.82,2.1),'cream',.07)
    for z in (.08,1.33,2.04):box('Interior shelf',(0,0,z),(.90,.79,.10),'white',.04)
    for z in (.47,.87,1.71):box('Glass shelf',(0,-.02,z),(.85,.67,.04),'glass',.01)
    for z,h in ((.65,1.18),(1.68,.71)):
        obj=box('Lower door' if z<1 else 'Freezer door',(0,-.45,z),(1,.13,h),'paper',.085)
        box('Door pull',(-.28,-.56,z),(.07,.08,.33),'steel',.025)
        box('Sticky note',(.22,-.525,z+.1),(.22,.015,.25),'shirt',.015)
        sphere('Note magnet',(.23,-.55,z+.23),(.035,.015,.035),'red')
    for x in (-.34,.34):
        for y in (-.28,.28):cyl('Appliance foot',(x,y,.05),.065,.10,'brown_dark')


def hood():
    box('Hood chimney',(0,.10,.94),(.66,.54,.72),'steel',.045)
    B.poly('Hood canopy',[(-.85,.25),(.85,.25),(.49,.69),(-.49,.69)],.72,'steel',.04)
    box('Hood rim',(0,0,.24),(1.77,.78,.12),'steel',.035)
    for x in (-.57,.57):box('Extractor light',(x,-.40,.24),(.27,.025,.07),'lamp',.015)


def shelf():
    box('Wall shelf',(0,0,.30),(1.5,.48,.13),'copper',.035)
    for x in (-.5,.5):box('Shelf bracket',(x,.13,.16),(.12,.16,.32),'brown',.025)
    for x,col in [(-.48,'brown'),(0,'copper'),(.48,'gold')]:W.transform(partial(jar,col),(x,0,.38),.85)


def cup(kind='cup'):
    if kind=='plate':
        lathe('Plate',[(0,0),(.37,0),(.47,.05),(.49,.10),(.45,.13),(.35,.07),(0,.07)],'cream');return
    if kind=='bowl':
        lathe('Bowl',[(0,0),(.20,0),(.33,.12),(.40,.36),(.34,.36),(.27,.13),(.17,.07),(0,.07)],'cream');return
    if kind=='glass':
        lathe('Glass',[(0,0),(.18,0),(.24,.55),(.20,.55),(.145,.055),(0,.055)],'glass');return
    lathe('Cup',[(0,0),(.21,0),(.25,.08),(.25,.45),(.20,.45),(.19,.08),(0,.08)],'paper')
    B.ring('Cup handle',(.27,0,.26),.16,.10,.075,'paper',start=-math.pi*.65,end=math.pi*.65)


def cookware(kind):
    if kind=='kettle':
        lathe('Kettle',[(0,0),(.30,0),(.39,.10),(.34,.50),(.24,.61),(0,.61)],'cream')
        cyl('Kettle lid',(0,0,.62),.26,.07,'brown')
        tube('Kettle handle',[(-.34,0,.42),(-.33,0,.85),(0,0,.98),(.33,0,.85),(.34,0,.42)],.055,'brown_dark')
        tube('Kettle spout',[(.28,0,.22),(.55,0,.38),(.58,0,.55)],.07,'cream');return
    if kind=='pan':
        lathe('Frying pan',[(0,0),(.48,0),(.52,.07),(.52,.13),(.47,.14),(.43,.06),(0,.06)],'steel')
        rod('Pan handle',(.45,0,.11),(1.1,0,.14),.07,'brown_dark');return
    lathe('Pot',[(0,0),(.35,0),(.39,.06),(.39,.43),(.33,.43),(.32,.07),(0,.07)],'red')
    cyl('Pot lid',(0,0,.46),.42,.06,'brown');sphere('Lid knob',(0,0,.54),(.075,.075,.07),'gold')
    for x in (-.5,.5):box('Pot handle',(x,0,.31),(.24,.13,.10),'brown_dark',.04)


def upright_books():
    for i,col in enumerate(('blue','red','paper','brown')):
        box('Book pages',((i-1.5)*.18,0,.28+i*.025),(.14,.36,.52+i*.05),'paper',.01)
        for y in (-.20,.20):box('Book cover',((i-1.5)*.18,y,.28+i*.025),(.16,.025,.56+i*.05),col,.012)
        box('Book spine',((i-1.5)*.18,-.20,.28+i*.025),(.16,.05,.56+i*.05),col,.012)


def whiteboard():
    box('Whiteboard',(0,0,1.2),(1.7,.12,1.2),'white',.05)
    frame('Whiteboard rim',1.77,1.27,.08,'steel',z=1.2)
    for x in (-.62,.62):
        box('Board support',(x,.03,.60),(.08,.10,1.20),'steel',.025)
        box('Rolling foot',(x,0,.10),(.14,.65,.10),'steel',.025)
        for y in (-.27,.27):cyl('Caster',(x,y,.07),.07,.06,'boot',rotation=(0,90,0))
    for x,z,col in [(-.4,1.5,'shirt'),(.1,1.38,'pink'),(.48,1.65,'blue')]:
        box('Sticky note',(x,-.075,z),(.22,.025,.20),col,.018)
    for a,b in [((-.3,-.1,1.45),(.1,-.1,1.38)),((.1,-.1,1.38),(.47,-.1,1.62))]:rod('Diagram line',a,b,.012,'steel')


def toolboard():
    box('Tool board',(0,0,.75),(1.7,.13,1.5),'copper',.045)
    for x in (-.70,-.35,0,.35,.70):
        for z in (.2,.45,.7,.95,1.2,1.4):cyl('Peg hole',(x,-.08,z),.018,.015,'brown_dark',rotation=(90,0,0))
    W.transform(B.wrench,(-.5,-.14,.26),.62)
    W.transform(B.screwdriver,(.35,-.14,.25),.72)
    rod('Hammer grip',(0,-.18,.4),(0,-.18,1.1),.045,'gold')
    box('Hammer head',(0,-.18,1.16),(.47,.17,.17),'steel',.04)


def workshop():
    for x in (-.75,.75):
        for y in (-.3,.3):box('Workbench leg',(x,y,.48),(.16,.17,.96),'brown',.035)
    box('Workbench top',(0,0,1.03),(2,.9,.18),'copper',.05)
    for z in (.32,.64):
        box('Workbench drawer',(-.50,-.34,z),(.55,.10,.24),'brown',.035)
        box('Tool drawer handle',(-.50,-.42,z),(.22,.06,.045),'gold',.018)
    W.transform(toolboard,(0,.33,1.16),1)
    box('Bench vise',(.60,-.27,1.19),(.46,.37,.25),'red',.035)
    rod('Vise screw',(.60,-.3,1.19),(.99,-.3,1.19),.045,'steel')


def classroom_desk():
    W.transform(W.chair,(0,.92,0),1)
    for x in (-.50,.50):
        for y in (-.25,.25):box('Desk leg',(x,y,.48),(.10,.12,.96),'steel',.025)
    box('Student desktop',(0,0,1.02),(1.3,.75,.15),'copper',.04)
    box('Book shelf',(0,.1,.75),(1.1,.5,.12),'brown',.03)


def hanging_plant():
    W.transform(B.leafy_plant,(0,0,.15),.6)
    for a in (0,math.tau/3,2*math.tau/3):
        tube('Hanging rope',[(.24*math.cos(a),.24*math.sin(a),.5),(0,0,1.5)],.015,'gold')
    for i in range(7):
        sphere('Trailing leaf',(.23*math.sin(i*1.7),-.24,.5-i*.11),(.10,.045,.13),'green')


def portrait():
    box('Portrait frame',(0,0,.55),(.75,.12,1.1),'brown',.055)
    box('Portrait backing',(0,-.075,.55),(.60,.035,.93),'paper',.025)
    rod('Flower stem',(0,-.11,.22),(0,-.11,.62),.025,'green_dark')
    for i in range(5):
        a=i*math.tau/5
        sphere('Flower petal',(.13*math.cos(a),-.13,.68+.13*math.sin(a)),(.115,.025,.115),'red')
    sphere('Flower center',(0,-.17,.68),(.075,.025,.075),'shirt')


def hourglass():
    for z in (.07,.95):cyl('Hourglass cap',(0,0,z),.28,.14,'copper')
    for x in (-.22,.22):rod('Hourglass support',(x,0,.13),(x,0,.89),.027,'gold')
    W.cone('Lower glass',(0,0,.31),.22,.05,.36,'glass');W.cone('Upper glass',(0,0,.69),.05,.22,.36,'glass')
    W.cone('Lower sand',(0,0,.22),.17,0,.20,'gold');W.cone('Upper sand',(0,0,.76),0,.16,.16,'gold')
    cyl('Falling sand',(0,0,.5),.009,.32,'gold')


def diffuser():
    lathe('Diffuser jar',[(0,0),(.20,0),(.22,.15),(.19,.37),(.10,.42),(0,.42)],'gold')
    for i in range(5):rod('Reed',((i-2)*.025,0,.35),((i-2)*.11,0,1.02-abs(i-2)*.05),.012,'copper')


def basket():
    box('Basket bottom',(0,0,.10),(.85,.55,.18),'copper',.035)
    for y in (-.28,.28):
        for z in (.25,.40):box('Woven side',(0,y,z),(.94,.08,.12),'gold',.025)
    for x in (-.45,.45):box('Basket end',(x,0,.31),(.09,.58,.36),'copper',.025)
    tube('Basket handle',[(-.35,0,.46),(-.32,0,.74),(0,0,.85),(.32,0,.74),(.35,0,.46)],.05,'copper')


def rug(kind='rectangle'):
    if kind=='round':
        for r,z,col in [(.9,.04,'red'),(.75,.075,'paper'),(.63,.09,'red'),(.49,.105,'cream')]:cyl('Rug band',(0,0,z),r,.035,col)
    else:
        for w,d,z,col in [(1.8,1.2,.025,'red'),(1.58,.99,.045,'paper'),(1.39,.80,.062,'red'),(1.16,.58,.08,'cream')]:box('Woven rug band',(0,0,z),(w,d,.035),col,.04)


def interior_wall(kind):
    if kind=='arch':arch_block(1.8,2.4,.22,True);return
    if kind=='column':
        for z,h,col in [(.13,.26,'brown'),(1.15,1.8,'cream'),(2.15,.26,'brown')]:box('Wall column',(0,0,z),(.38,.38,h),col,.04)
        return
    if kind in {'trim-long','trim-short'}:box('Wall trim',(0,0,.09),(1.65 if kind=='trim-long' else .60,.22,.18),'copper',.035);return
    box('Wall panel',(0,0,1.1),(1.8,.18,2.2),'cream',.04)
    if kind=='wood':
        for i in range(7):box('Wood wainscot',((i-3)*.24,-.12,.65),(.22,.08,1.2),'paper',.02)
        for z in (.08,1.3):box('Wainscot trim',(0,-.13,z),(1.86,.15,.12),'copper',.025)


def interior_floor(kind):
    if kind=='rug':rug();return
    if kind in {'tile','wood'}:tile('floor-'+kind);return
    for x in range(3 if kind=='cobble' else 2):
        for y in range(3 if kind=='cobble' else 2):
            n=3 if kind=='cobble' else 2
            box('Floor stone',(-1+(x+.5)*2/n,-1+(y+.5)*2/n,.08),(2/n-.025,2/n-.025,.16),
                'stone' if (x+y)%2 else 'steel_light',.09 if kind=='cobble' else .025)


for slug,name,fn in [('sofa','Sofa',B.sofa),('armchair','Ghế bành / Armchair',W.armchair),('chair','Ghế gỗ / Chair',W.chair),('stool','Ghế đẩu / Stool',stool)]:add('interior-'+slug,name,'seating',fn)
for slug,name,fn in [('coffee-table','Bàn trà / Coffee Table',coffee_table),('table','Bàn ăn / Table',partial(W.table,True)),('round-table','Bàn tròn / Round Table',round_table)]:add('interior-'+slug,name,'tables',fn)
add('interior-bed','Giường / Bed','beds',W.bed);add('interior-bunk-bed','Giường tầng / Bunk Bed','beds',bunk_bed)
for kind,name in [('bookcase','Kệ sách'),('display','Tủ trưng bày'),('plain','Tủ đồ'),('wardrobe','Tủ quần áo'),('rack','Kệ chứa đồ')]:add('interior-'+kind,name,'storage',partial(cabinet,kind))
add('interior-storage-box','Thùng chứa / Storage Box','storage',partial(storage_box,True));add('interior-toolbox','Hộp dụng cụ / Toolbox','storage',B.toolbox)
for slug,name,fn in [('floor-lamp','Đèn đứng',partial(W.shade_lamp,True)),('table-lamp','Đèn bàn',W.shade_lamp),('desk-lamp','Đèn học',B.lamp),('wall-lamp','Đèn tường',partial(fixture,'wall')),('pendant','Đèn treo trần',pendant)]:add('interior-'+slug,name,'lighting',fn)
for slug,name,fn in [('fridge','Tủ lạnh / Fridge',refrigerator),('sink','Bồn rửa / Sink',partial(counter,True)),('kitchen-counter','Tủ bếp / Kitchen Counter',counter),('stove','Bếp và lò / Stove Oven',partial(W.kitchen,stove=True)),('range-hood','Máy hút mùi / Range Hood',hood),('kitchen-shelf','Kệ bếp / Kitchen Shelf',shelf)]:add('interior-'+slug,name,'kitchen',fn)
add('interior-plates','Đĩa / Plates','kitchenware',lambda:[W.transform(partial(cup,'plate'),(0,0,i*.08)) for i in range(3)])
for kind,name in [('cup','Cốc'),('glass','Ly thủy tinh'),('bowl','Bát')]:add('interior-'+kind,name,'kitchenware',partial(cup,kind))
for kind,name in [('kettle','Ấm nước'),('pot','Nồi'),('pan','Chảo')]:add('interior-'+kind,name,'kitchenware',partial(cookware,kind))
for slug,name,fn in [('desk','Bàn học',partial(W.table,desk=True)),('classroom-desk','Bàn lớp học',classroom_desk),('whiteboard','Bảng trắng',whiteboard),('chalkboard','Bảng phấn',W.blackboard),('lab-counter','Bàn thí nghiệm',partial(counter,lab=True)),('workshop-table','Bàn làm mộc',workshop),('tool-board','Bảng dụng cụ',toolboard)]:add('interior-'+slug,name,'learning',fn)
for slug,name,fn in [('books-stack','Sách xếp chồng',W.books),('books-upright','Sách dựng đứng',upright_books),('open-book','Sách mở',W.open_book),('globe','Quả địa cầu',W.globe),('plant-small','Chậu cây nhỏ',lambda:W.transform(B.leafy_plant,scale=.6)),('plant-medium','Chậu cây vừa',B.leafy_plant),('hanging-plant','Cây treo',hanging_plant),('landscape','Tranh phong cảnh',W.wall_art),('portrait','Tranh hoa',portrait),('clock','Đồng hồ',W.wall_clock),('hourglass','Đồng hồ cát',hourglass),('lantern','Đèn lồng',lantern),('diffuser','Lọ khuếch tán',diffuser),('basket','Giỏ đan',basket)]:add('interior-'+slug,name,'decor',fn)
for kind,name,col in [('window','Cửa kính gỗ','copper'),('arch','Cửa vòm','copper'),('window','Cửa kính xanh','blue')]:
    add('interior-door-'+('blue' if col=='blue' else kind),name,'interior-modules',partial(door,kind,col))
for kind in ('square','arch','round'):add('interior-window-'+kind,'Cửa sổ '+kind,'interior-modules',partial(window,kind))
add('interior-window-curtains','Cửa sổ có rèm','interior-modules',W.curtained_window)
add('interior-stairs-railed','Cầu thang có lan can','interior-modules',partial(steps,1.5,2,1.3,5,True))
add('interior-stairs','Bậc thang','interior-modules',partial(steps,1.5,1.5,1,4))
add('interior-railing-straight','Lan can thẳng','interior-modules',railing)
add('interior-railing-balcony','Lan can ban công','interior-modules',partial(railing,'balcony'))
for kind in ('wood','plain','arch','column','trim-long','trim-short'):add('interior-wall-'+kind,'Module tường '+kind,'interior-modules',partial(interior_wall,kind))
for kind in ('tile','wood','checker','rug','cobble'):add('interior-floor-'+kind,'Module sàn '+kind,'interior-modules',partial(interior_floor,kind))
add('interior-rug-rectangle','Thảm chữ nhật','decor',rug);add('interior-rug-round','Thảm tròn','decor',partial(rug,'round'))


def room_shell():
    box('Room platform',(0,0,.04),(4.9,3.4,.18),'brown',.08)
    for x in range(8):
        for y in range(5):box('Room floorboard',((x-3.5)*.59,(y-2)*.62,.16),(.58,.61,.10),'paper',.025)
    box('Back plaster wall',(0,1.64,1.47),(4.9,.18,2.7),'cream',.055)
    box('Side plaster wall',(-2.36,0,1.47),(.18,3.3,2.7),'cream',.055)
    for x in range(8):box('Wall cap stone',((x-3.5)*.61,1.64,2.86),(.60,.33,.23),'brown',.05)
    for y in range(5):box('Side cap stone',(-2.36,(y-2)*.64,2.86),(.33,.63,.23),'brown',.05)
    for x in (-2.3,2.3):
        for z in (.35,1.15,1.95,2.65):box('Corner masonry',(x,1.53,z),(.32,.35,.35),'stone',.045)


def room(kind='living'):
    room_shell()
    W.transform(W.curtained_window,(-.8,1.43,.65),.72)
    if kind=='living':
        W.transform(B.sofa,(.05,.65,.21),.72)
        W.transform(W.armchair,(1.50,-.37,.21),.66,rotation=-15)
        W.transform(W.cabinet,(1.57,1.1,.21),.68)
        W.transform(partial(W.shade_lamp,True),(-1.65,.57,.21),.83)
        W.transform(rug,(0,-.65,.21),1.05)
        W.transform(coffee_table,(0,-.58,.34),.70)
        W.transform(W.wall_art,(.95,1.49,1.65),.52)
    elif kind=='bedroom':
        W.transform(W.bed,(-.85,.20,.21),.9)
        W.transform(W.nightstand,(-1.8,.65,.21),.65)
        W.transform(W.shade_lamp,(-1.8,.65,.83),.55)
        W.transform(partial(W.table,desk=True),(1.15,.85,.21),.69)
        W.transform(W.chair,(1.16,-.14,.21),.63)
        W.transform(shelf,(1.2,1.44,1.85),.75)
        W.transform(portrait,(.05,1.47,1.7),.64)
        W.transform(partial(rug,'round'),(1.1,-.8,.22),.8)
    else:
        W.transform(refrigerator,(-1.94,.95,.21),.73)
        W.transform(partial(counter,True),(-.87,.95,.21),.61)
        W.transform(partial(W.kitchen,stove=True),(.27,.95,.21),.57)
        W.transform(workshop,(1.53,.75,.21),.66)
        W.transform(hood,(.27,1.18,1.48),.57)
        W.transform(shelf,(-.85,1.41,1.60),.64)
        W.transform(stool,(1.48,-.27,.21),.65)
        W.transform(B.leafy_plant,(-2.0,-1.1,.21),.70)


def machine():
    W.transform(W.console,(-.42,0,0),.75)
    W.transform(partial(W.crystal_jar,True),(1.05,.10,0),.72)
    W.transform(partial(B.gear,'Machine drive',radius=.48),(0.2,.32,1.75),1)
    tube('Machine supply pipe',[(-1,.5,1),(-1,.5,2.2),(-.7,.5,2.5),(.2,.5,2.5)],.10,'steel')


def loaded_cart():
    W.handcart()
    for x,y,z in [(-.3,0,1.28),(.25,.18,1.27),(-.2,.12,1.62)]:box('Parcel',(x,y,z),(.52,.46,.42),'paper' if x<0 else 'copper',.035)


for slug,name,fn in [('house','Nhà lắp ghép / House',W.house),('cart','Xe kéo chở hàng / Cart',loaded_cart),
                     ('machine','Máy cơ khí lắp ghép / Machine',machine),('room-corner','Góc phòng / Room Corner',room)]:
    add('example-'+slug,name,'core-examples',fn)
for kind,name in [('living','Phòng khách'),('bedroom','Phòng ngủ và học tập'),('kitchen','Góc bếp và xưởng')]:add('room-'+kind,name,'rooms',partial(room,kind))
add('core-inventor','Nhà phát minh / Inventor','character',partial(W.character,'inventor'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--only');parser.add_argument('--resume',action='store_true')
    parser.add_argument('--resolution',type=int,default=384);parser.add_argument('--samples',type=int,default=8)
    args=parser.parse_args();root=assets_dir();folder=root/'generated'/PACK;folder.mkdir(parents=True,exist_ok=True)
    refs=root/'references'/PACK;refs.mkdir(parents=True,exist_ok=True)
    for name in REFERENCES:
        source=Path('D:/Downloads')/name
        if not (refs/name).exists():shutil.copyfile(source,refs/name)
    W.PACK=PACK;W.GROUPS=GROUPS;W.ASSETS=ASSETS
    manifest=folder/'manifest.json';old=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {}
    entries={item['slug']:item for item in old.get('assets',[])}
    chosen=args.only.split(',') if args.only else list(ASSETS)
    for index,slug in enumerate(chosen):
        if slug not in ASSETS:raise ValueError('Unknown asset: '+slug)
        if args.resume and slug in entries and all((folder/(slug+s)).is_file() for s in ('.glb','.blend','.png','.asset.json')):continue
        entries[slug]=W.build(slug,folder,root,args.resolution,args.samples)
        entries[slug]['description']=entries[slug]['description'].replace('Bộ Story World','Bộ Universal Core & Interior')
        (folder/(slug+'.asset.json')).write_text(json.dumps({key:value for key,value in entries[slug].items()
            if key not in {'slug','path'}},ensure_ascii=False,indent=2),encoding='utf-8')
        manifest.write_text(json.dumps({'pack':PACK,'groups':GROUPS,'palette':B.PALETTE,
            'references':[(refs/name).relative_to(root).as_posix() for name in REFERENCES],
            'assets':list(entries.values())},ensure_ascii=False,indent=2),encoding='utf-8')
        print('DONE',index+1,'/',len(chosen),slug,flush=True)
    print('PACK READY',len(entries),folder,flush=True)


if __name__=='__main__':main()
