"""Reference-sheet expansion: native editable meshes, with explicit reuse coverage."""
import argparse
from functools import partial
import json
import math
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from scripts import build_universal_assets as U
from codex_blender.config import assets_dir
import bpy
from mathutils import Vector

W=U.W; B=U.B
box,sphere,cyl,rod,tube,poly,ring=B.box,B.sphere,B.cyl,B.rod,B.tube,B.poly,B.ring
PACK='universal-expansion-v2'
GROUPS={'expressions':'Nhân vật · Biểu cảm','accessories':'Phụ kiện nhân vật',
        'icons':'Biểu tượng 3D','emoji':'Cảm xúc','effects':'Hiệu ứng hình học',
        'ui':'Giao diện 3D','topics':'Chủ đề video','mechanisms':'Cơ khí và truyền động',
        'electronics':'Điện và điều khiển','architecture':'Kiến trúc module',
        'environment':'Cảnh quan và đường phố','examples':'Bối cảnh lắp sẵn'}
REFERENCES=['76ece555-d3fb-4023-b3d1-3b36e89dbfbe.png','ec70184d-f95b-4696-aeed-95fb3f582069.png',
            '5d81b81a-bab4-4397-ad2c-c60ddf9f1af9.png','376e0ba1-e6e2-4ab4-aa57-1e3b45f04f11.png']
ASSETS={}
def add(slug,name,group,fn):ASSETS[slug]=(name,group,name,fn)
def move(fn,loc=(0,0,0),scale=1,rotation=0):W.transform(fn,loc,scale,rotation)
def disk(name,pos,r,mat='gold',depth=.15):return cyl(name,pos,r,depth,mat,rotation=(90,0,0))
def glyph(text,mat='gold',size=1,pos=(0,-.13,.1)):
    curve=bpy.data.curves.new('Editable symbol','FONT');curve.body=text;curve.align_x='CENTER'
    curve.size=size;curve.extrude=.055;curve.bevel_depth=.015;curve.bevel_resolution=3
    font=Path('C:/Windows/Fonts/arialbd.ttf')
    if font.exists():curve.font=bpy.data.fonts.load(str(font),check_existing=True)
    obj=bpy.data.objects.new('Symbol '+text,curve);bpy.context.collection.objects.link(obj)
    obj.location=pos;obj.rotation_euler=(math.pi/2,0,0);obj.parent=B.PARENT;obj.data.materials.append(B.mat(mat))
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.ops.object.convert(target='MESH')
def shape(name,pts,mat='gold',y=0,depth=.15):
    obj=poly(name,pts,depth,mat,.025);obj.location.y=y;return obj
def star(name='Star',center=(0,0,.6),radius=.5,mat='gold'):
    x,y,z=center;pts=[]
    for i in range(10):
        a=math.pi/2+i*math.pi/5;r=radius if i%2==0 else radius*.46;pts.append((x+r*math.cos(a),z+r*math.sin(a)))
    shape(name,pts,mat,y)
def arc(name,c,r,a,b,mat='gold',thickness=.055):
    tube(name,[(c[0]+r*math.cos(t),c[1],c[2]+r*math.sin(t)) for t in [a+(b-a)*i/24 for i in range(25)]],thickness,mat)
def heart(name='Heart',pos=(0,0,.55),scale=1,mat='red'):
    pts=[]
    for i in range(64):
        t=math.tau*i/64;pts.append((pos[0]+scale*math.sin(t)**3*.5,pos[2]+scale*(13*math.cos(t)-5*math.cos(2*t)-2*math.cos(3*t)-math.cos(4*t))/32))
    shape(name,pts,mat,pos[1])
def arrow(kind='right'):
    if kind=='loop':
        arc('Loop',(0,0,.55),.43,-.1,math.pi*1.65,'copper',.085)
        shape('Arrow tip',[(.40,.58),(.65,.72),(.57,.38)],'copper')
    else:
        for offset in ([0] if kind=='right' else [-.27,.27]):
            shape('Arrow',[(offset-.48,.39),(offset+.05,.39),(offset+.05,.17),(offset+.50,.55),(offset+.05,.93),(offset+.05,.71),(offset-.48,.71)],'gold')
def icon(kind):
    if kind in ('question','exclamation'):glyph('?' if kind=='question' else '!','gold' if kind=='question' else 'red',1.35)
    elif kind=='idea':
        sphere('Bulb',(0,0,.85),(.34,.26,.37),'lamp');cyl('Socket',(0,0,.42),.19,.27,'steel')
        for i in range(7):
            a=math.pi*i/6;rod('Idea ray',(.47*math.cos(a),0,.86+.47*math.sin(a)),(.62*math.cos(a),0,.86+.62*math.sin(a)),.035,'gold')
    elif kind=='check':disk('Green medallion',(0,0,.55),.53,'green');tube('Check',[(-.26,-.13,.55),(-.07,-.13,.35),(.28,-.13,.76)],.075,'white')
    elif kind=='warning':
        shape('Warning border',[(-.58,.08),(.58,.08),(0,1.1)],'gold');shape('Warning inset',[(-.44,.15),(.44,.15),(0,.95)],'shirt',-.09);glyph('!','brown_dark',.75,(0,-.20,.22))
    elif kind=='success':star()
    elif kind=='coin':disk('Coin',(0,0,.6),.52,'gold');ring('Raised rim',(0,-.11,.6),.46,.40,.05,'gold_light');glyph('$','gold_light',.70,(0,-.17,.34))
    elif kind=='speech':
        box('Speech bubble',(0,0,.65),(1.25,.25,.73),'cream',.22);shape('Bubble tail',[(-.40,.40),(-.38,.08),(-.08,.40)],'cream')
        for x in (-.30,0,.30):sphere('Speech dot',(x,-.16,.67),(.065,.035,.065),'steel')
    elif kind=='cloud':
        for x,z,r in [(-.35,.4,.27),(0,.59,.38),(.38,.42,.28)]:sphere('Cloud lobe',(x,0,z),(r,.22,r),'white')
    elif kind=='blueprint':
        box('Blueprint',(0,0,.58),(1.05,.15,1.05),'blue',.04)
        for x in (-.43,.43):rod('Paper roller',(x,0,.02),(x,0,1.13),.065,'paper')
        move(partial(B.gear,'Blueprint gear',radius=.27,material='white'),(0,-.13,.13),1)
    elif kind=='gear':B.gear('Gear icon',radius=.50,material='steel')
    elif kind=='clock':W.wall_clock()

def emoji(kind):
    sphere('Emotion face',(0,0,.65),(.58,.24,.58),'gold')
    y=-.245
    for s in (-1,1):
        x=s*.20
        if kind=='love':heart('Heart eye',(x,-.26,.83),.31)
        elif kind=='cool':box('Sunglass lens',(x,-.27,.81),(.35,.09,.23),'boot',.07)
        elif kind=='dizzy':
            tube('Spiral eye',[(x+.10*t/4*math.cos(t),y-.025,.82+.10*t/4*math.sin(t)) for t in [j*math.pi/16 for j in range(65)]],.018,'brown_dark')
        elif kind in ('happy','laugh'):
            arc('Closed happy eye',(x,y,.79),.09,0,math.pi,'brown_dark',.025)
        else:
            sphere('Eye',(x,y,.82),(.045,.035,.075),'brown_dark')
        if kind in ('angry','worried','sad','thinking'):
            angle=s*(.055 if kind=='angry' else -.055)
            rod('Brow',(x-.09,y,.99-angle),(x+.09,y,.99+angle),.025,'brown_dark')
    if kind in ('surprised','dizzy'):sphere('Open mouth',(0,-.26,.43),(.095,.035,.14),'mouth')
    elif kind in ('worried','sad','angry'):arc('Frown',(0,-.26,.30),.16,.15,math.pi-.15,'brown_dark',.027)
    elif kind=='thinking':
        rod('Mouth',(-.11,-.26,.43),(.09,-.26,.43),.025,'brown_dark');sphere('Thinking hand',(.29,-.30,.35),(.13,.10,.13),'shirt')
    else:
        arc('Smile',(0,-.26,.61),.22,math.pi,math.tau,'mouth',.045)
        if kind=='laugh':sphere('Laugh mouth',(0,-.25,.46),(.18,.04,.14),'mouth');box('Teeth',(0,-.30,.53),(.26,.025,.07),'white',.025)
    if kind=='sad':sphere('Tear',(-.30,-.25,.52),(.065,.04,.12),'water')
    if kind=='cool':rod('Glasses bridge',(-.06,-.32,.81),(.06,-.32,.81),.03,'boot')

def effect(kind):
    if kind in ('right','forward','loop'):arrow(kind);return
    if kind=='heat':
        for x in (-.34,0,.34):
            tube('Heat trail',[(x+.06*math.sin(t*math.tau),0,.08+t*.85) for t in [i/24 for i in range(25)]],.055,'red')
            shape('Heat arrow',[(x-.13,.83),(x+.13,.83),(x,1.1)],'red')
    elif kind=='cold':
        for i in range(6):
            a=math.tau*i/6;v=Vector((math.sin(a),0,math.cos(a)));c=Vector((0,0,.6))
            rod('Snowflake arm',c,c+v*.53,.045,'cyan')
            for s in (-1,1):
                d=Vector((math.sin(a+s*.85),0,math.cos(a+s*.85)));rod('Snow crystal',c+v*.32,c+v*.32+d*.19,.035,'cyan')
    elif kind=='water':
        for i in range(7):
            a=math.pi*i/6;ob=sphere('Water droplet',(.45*math.cos(a),0,.2+.65*math.sin(a)),(.10,.10,.22),'cyan');ob.rotation_euler.y=math.pi/2-a
    elif kind=='fire':
        shape('Outer flame',[(-.42,.13),(-.47,.45),(-.17,.78),(-.09,1.26),(.20,.91),(.32,.56),(.45,.67),(.44,.28),(.15,.06)],'red')
        shape('Inner flame',[(-.23,.15),(-.20,.43),(.03,.87),(.11,.48),(.27,.25),(.10,.08)],'gold',-.13)
    elif kind=='smoke':
        for x,z,r in [(-.14,.22,.14),(.06,.45,.22),(-.18,.67,.27),(.21,.75,.27),(0,1,.25)]:sphere('Smoke puff',(x,0,z),(r,r*.7,r),'stone_light')
    elif kind=='sparkles':
        for x,z,r in [(-.32,.43,.23),(.12,.86,.29),(.43,.27,.16)]:star('Sparkle',(x,0,z),r)
    elif kind=='emphasis':
        for a in (-.6,0,.6):rod('Emphasis ray',(.28*math.sin(a),0,.2+.28*math.cos(a)),(.75*math.sin(a),0,.2+.75*math.cos(a)),.07,'gold')
    elif kind=='impact':
        ring('Impact outer',(0,0,.6),.58,.54,.08,'cyan');ring('Impact inner',(0,0,.6),.40,.37,.06,'white')
    elif kind=='orbit':
        ob=B.torus('Orbit ring',(0,0,.6),.50,.03,'gold');ob.rotation_euler.x=.35
        star('Orbit star',(.39,-.20,.72),.22)

def ui(kind):
    colors={'play':'green','pause':'gold','stop':'red','undo':'purple','settings':'steel','menu':'blue','home':'copper'}
    if kind in colors:
        box('Button',(0,0,.58),(1.12,.27,.91),colors[kind],.18)
        if kind=='play':shape('Play triangle',[(-.21,.31),(-.21,.85),(.30,.58)],'white',-.19)
        elif kind=='pause':
            for x in (-.17,.17):box('Pause bar',(x,-.19,.58),(.13,.08,.48),'white',.025)
        elif kind=='stop':box('Stop square',(0,-.19,.58),(.47,.08,.47),'white',.05)
        elif kind=='menu':
            for z in (.34,.58,.82):box('Menu bar',(0,-.19,z),(.60,.08,.075),'white',.03)
        elif kind=='settings':move(partial(B.gear,'Settings',radius=.32,material='white'),(0,-.19,.08))
        elif kind=='home':shape('House icon',[(-.34,.58),(0,.90),(.34,.58),(.24,.58),(.24,.29),(.06,.29),(.06,.47),(-.06,.47),(-.06,.29),(-.24,.29),(-.24,.58)],'white',-.19)
        else:
            arc('Undo arrow',(0,-.19,.53),.24,-.5,math.pi*1.2,'white',.055);shape('Arrowhead',[(-.35,.57),(-.05,.63),(-.23,.84)],'white',-.19)
    elif kind in ('progress','slider','toggle'):
        box('Track',(0,0,.25),(1.6,.23,.29),'stone_light',.14)
        box('Active track',(-.32,-.13,.25),(.90,.08,.19),'green' if kind!='slider' else 'copper',.08)
        if kind!='progress':sphere('Thumb',(.27,-.19,.25),(.18,.10,.18),'white' if kind=='toggle' else 'gold')
    elif kind.startswith('checkbox'):
        box('Checkbox',(0,0,.4),(.66,.20,.66),'green' if kind.endswith('checked') else 'cream',.10)
        if kind.endswith('checked'):tube('Tick',[(-.19,-.15,.41),(-.04,-.15,.26),(.21,-.15,.58)],.05,'white')
    elif kind in ('new','live'):
        box('Badge',(0,0,.35),(1.30,.23,.50),'red',.20);glyph(kind.upper(),'white',.31,(0,-.18,.23))
    elif kind=='panel':
        box('Panel',(0,0,.55),(1.6,.20,1.0),'cream',.13)
        for x in (-.65,.65):
            for z in (.18,.92):disk('Panel rivet',(x,-.13,z),.035,'gold',.04)
    elif kind=='dialog':icon('speech')
    elif kind=='banner':
        box('Banner',(0,0,.55),(1.5,.20,.50),'gold',.04)
        for s in (-1,1):shape('Ribbon tail',[(s*.55,.42),(s*.95,.32),(s*.87,.57),(s*.95,.78),(s*.55,.66)],'copper',.06)
    elif kind=='reward':
        disk('Award medal',(0,0,.7),.44,'gold');star('Award star',(0,-.16,.7),.31,'gold_light')
        for s in (-1,1):box('Award ribbon',(s*.18,.03,.23),(.24,.10,.52),'copper',.025,rotation=(0,s*15,0))

def expression(role,kind):
    W.character(role)
    bpy.context.view_layer.update()
    # Keep head, hair and headwear only. Existing full-body archetypes are reused.
    for obj in list(B.PARENT.children_recursive):
        if obj.type in ('MESH','CURVE'):
            corners=[obj.matrix_basis@Vector(c) for c in obj.bound_box]
            # Local geometry bounds: root scale is applied at export.
            if (min(p.z for p in corners)+max(p.z for p in corners))/2<2.20 and not any(k in obj.name for k in ('hair','ponytail')):bpy.data.objects.remove(obj,do_unlink=True)
    W.remove_named('eye white','eye pupil','eye glint','eyebrow','open smile','smile teeth','tongue','surprised mouth','smile curve')
    for s in (-1,1):
        x=s*.28
        if kind in ('happy','excited','laugh') or (kind=='wink' and s==1):arc('Closed eyelid',(x,-.56,2.70),.13,0,math.pi,'brown_dark',.028)
        else:
            sphere('Eye white',(x,-.50,2.72),(.16,.08,.22),'white');sphere('Eye pupil',(x,-.58,2.72),(.075,.04,.13),'brown_dark');sphere('Eye glint',(x-.025,-.62,2.77),(.027,.015,.04),'white')
        delta=s*(.06 if kind=='worried' else -.02);brow_z=3.10 if kind=='excited' else 3.02
        rod('Eyebrow',(x-.12,-.53,brow_z-delta),(x+.12,-.53,brow_z+delta),.035,'hair')
    if kind=='surprised':sphere('O mouth',(0,-.54,2.37),(.10,.05,.14),'mouth')
    elif kind in ('thinking','worried'):
        if kind=='thinking':rod('Pursed mouth',(-.10,-.55,2.37),(.10,-.55,2.37),.025,'mouth')
        else:arc('Worried mouth',(0,-.55,2.28),.13,0,math.pi,'mouth',.025)
    elif kind=='default':arc('Small smile',(0,-.55,2.43),.13,math.pi,math.tau,'mouth',.025)
    else:
        sphere('Happy open mouth',(0,-.53,2.36),(.25 if kind=='laugh' else .22,.07,.20 if kind=='excited' else .15),'mouth');box('Smile teeth',(0,-.60,2.43),(.31,.025,.065),'white',.02)
        if kind in ('excited','laugh'):sphere('Tongue',(0,-.60,2.28),(.11,.025,.04),'tongue')
    box('Bust display collar',(0,.02,2.10),(.86,.58,.25),'shirt',.06)

def headwear(kind):
    if kind in ('helmet','cap','newsboy','fedora','scarf','chef'):
        color={'helmet':'gold','cap':'blue','newsboy':'brown','fedora':'paper','scarf':'shirt','chef':'white'}[kind]
        sphere('Hat crown',(0,0,.42),(.62,.48,.32),color)
        box('Hat brim',(0,-.15,.23),(1.25,.95,.10),color,.07)
        if kind=='helmet':box('Helmet ridge',(0,0,.69),(.13,.69,.12),'gold_light',.04);disk('Headlamp',(0,-.51,.43),.15,'lamp')
        if kind=='fedora':box('Fedora crown',(0,0,.55),(.92,.67,.48),'paper',.12);box('Hat band',(0,-.35,.43),(.94,.05,.12),'brown',.02)
        if kind=='scarf':sphere('Scarf knot',(.60,0,.28),(.18,.16,.15),'gold');shape('Scarf tail',[(.54,.28),(.94,.08),(.86,.45)],'shirt')
        if kind=='chef':
            for x,y in [(-.32,0),(0,-.15),(.32,0),(0,.19)]:sphere('Chef puff',(x,y,.76),(.30,.32,.31),'white')
            cyl('Chef hat band',(0,0,.35),.48,.42,'white')
    else:glasses('goggles')
def glasses(kind):
    for s in (-1,1):
        x=s*.30
        if kind in ('round','monocle'):ring('Spectacle rim',(x,0,.5),.25,.21,.08,'gold')
        else:
            move(partial(U.frame,'Lens frame',.52,.42,.10,'gold' if kind=='goggles' else 'white' if kind=='protective' else 'boot',.5,True),(x,0,0))
            box('Lens',(x,.03,.5),(.43,.04,.33),'blue_light' if kind=='goggles' else ('steel' if kind=='visor' else 'glass'),.06)
        if kind=='monocle':break
        rod('Glasses temple',(x+s*.24,0,.58),(x+s*.24,.53,.55),.025,'brown_dark')
    if kind!='monocle':rod('Bridge',(-.07,0,.52),(.07,0,.52),.025,'gold' if kind=='round' else 'boot')
    else:tube('Monocle chain',[(-.52,0,.37),(-.60,.02,.06),(-.31,.03,.02)],.018,'gold')
def bag(kind):
    color='blue' if kind=='satchel' else ('cream' if kind=='apron-bag' else 'leather')
    box('Bag body',(0,0,.52),(.95,.43,.83),color,.12)
    box('Bag flap',(0,-.24,.67),(1.0,.07,.37),color,.07)
    for x in (-.27,.27):
        box('Buckle strap',(x,-.29,.52),(.09,.035,.42),'brown_dark',.02);B.buckle('Bag buckle',(x,-.32,.44),.17,.15,'gold',.025)
    if kind in ('backpack','rucksack'):
        for x in (-.30,.30):tube('Backpack strap',[(x,.2,.18),(x,.52,.26),(x,.56,.83),(x,.21,.94)],.055,'brown')
        if kind=='backpack':cyl('Bedroll',(0,0,1.08),.19,1.04,'paper',rotation=(0,90,0))
    elif kind in ('handbag','satchel'):arc('Bag handle',(0,0,.94),.28,0,math.pi,'brown',.055)
    else:
        for x in (-.30,.30):box('Belt loop',(x,.27,.81),(.13,.10,.38),'brown_dark',.025)
        if kind=='apron-bag':box('Apron top',(0,.15,1.14),(.70,.13,.52),'cream',.05)
    if kind=='rucksack':box('Front pocket',(0,-.29,.35),(.53,.15,.32),'copper',.05)
    if kind=='belt-pouch':
        for obj in B.PARENT.children_recursive:obj.scale*=.65;obj.location*=.65
def clothing(kind):
    color={'vest':'shirt','coat':'brown','labcoat':'white','apron':'cream','tool-apron':'leather','overalls':'copper','safety-vest':'gold'}[kind]
    box('Garment back',(0,.12,.73),(.95,.13,1.30),color,.055)
    for s in (-1,1):
        box('Front panel',(s*.26,-.12,.73),(.43,.15,1.30),color,.055)
        box('Shoulder',(s*.38,0,1.33),(.29,.40,.21),color,.05)
        box('Pocket',(s*.26,-.22,.52),(.29,.06,.28),'paper' if kind=='labcoat' else 'brown',.035)
    if kind in ('apron','tool-apron'):box('Apron bib',(0,-.13,1.10),(.67,.16,.50),color,.05)
    if kind=='overalls':
        for x in (-.25,.25):box('Overall leg',(x,0,.0),(.43,.42,.64),'copper',.055)
    if kind=='safety-vest':
        for z in (.44,.92):box('Reflective stripe',(0,-.23,z),(.95,.03,.085),'white',.01)

def tool(kind):
    if kind=='magnifier':ring('Magnifier',(0,0,.85),.32,.25,.13,'gold');rod('Magnifier grip',(-.15,0,.57),(-.44,0,.08),.07,'brown')
    elif kind=='blueprint':icon('blueprint')
    elif kind=='scroll':B.scroll()
    else:
        rod('Wooden handle',(0,0,.12),(0,0,1.0),.075,'brown')
        if kind=='hammer':box('Hammer head',(0,0,1.04),(.62,.28,.25),'steel',.05)
        elif kind=='pickaxe':tube('Pick head',[(-.54,0,.84),(-.25,0,1.10),(.1,0,1.12),(.53,0,.99)],.075,'steel')
        elif kind=='shovel':shape('Shovel blade',[(-.23,.44),(-.24,.10),(0,-.06),(.24,.10),(.23,.44)],'steel');ring('D grip',(0,0,1.12),.20,.13,.14,'brown')
        elif kind=='trowel':shape('Trowel blade',[(-.20,.45),(0,-.03),(.20,.45)],'steel')

def topic(kind):
    if kind=='leaf':
        shape('Leaf',[(-.36,.15),(-.47,.52),(-.18,.94),(.53,1.04),(.42,.38),(0,.19)],'green');rod('Leaf vein',(-.40,-.10,.03),(.38,-.10,.90),.028,'green_dark')
    elif kind=='rocket':
        cyl('Rocket hull',(0,0,.70),.23,.85,'white');W.cone('Nose',(0,0,1.30),.24,0,.40,'red');disk('Porthole',(0,-.22,.81),.13,'blue')
        for s in (-1,1):shape('Rocket fin',[(s*.18,.29),(s*.45,.12),(s*.23,.70)],'red')
        W.cone('Exhaust',(0,0,.11),.05,.16,.40,'gold')
    elif kind=='art':
        sphere('Artist palette',(0,0,.52),(.61,.12,.43),'copper')
        for i,col in enumerate(('red','gold','blue','green','white')):sphere('Paint dab',(-.40+i*.20,-.13,.63+(.12 if i%2 else 0)),(.075,.025,.075),col)
        rod('Paintbrush',(-.35,-.17,.12),(.43,-.17,.95),.03,'brown');sphere('Brush tip',(.43,-.17,.95),(.07,.035,.10),'blue')
    elif kind=='gaming':
        box('Game controller',(0,0,.48),(1.26,.48,.58),'purple',.22)
        for size in ((.34,.06,.10),(.10,.06,.34)):box('D pad',(-.32,-.28,.51),size,'boot',.025)
        for x,z,col in [(.30,.62,'red'),(.44,.48,'gold'),(.17,.48,'blue'),(.30,.34,'green')]:sphere('Action button',(x,-.28,z),(.065,.035,.065),col)
    elif kind=='video':
        box('Clapper body',(0,0,.43),(1.1,.21,.73),'boot',.04)
        for z in (.68,.88):
            box('Clapper strip',(0,0,z),(1.15,.24,.16),'white',.02)
            for x in (-.4,-.1,.2,.5):box('Stripe',(x,-.135,z),(.12,.025,.14),'boot',.005,rotation=(0,-25,0))
    elif kind=='business':
        for i,col in enumerate(('blue','gold','copper')):box('Chart bar',((i-1)*.35,0,.2+i*.17),(.25,.30,.4+i*.34),col,.035)
    elif kind=='health':heart()
    elif kind=='engineering':move(partial(tool,'hammer'),(-.1,0,0),.8,30);move(B.wrench,(.1,-.1,.1),.8,-30)
    elif kind=='cooking':headwear('chef')

for role in ('inventor','explorer'):
    for kind in ('default','happy','excited','surprised','thinking','laugh','wink' if role=='inventor' else 'worried'):
        add('expression-'+role+'-'+kind,role.title()+' · '+kind,'expressions',partial(expression,role,kind))
for kind in ('helmet','cap','newsboy','fedora','scarf','chef'):add('hat-'+kind,'Headwear · '+kind,'accessories',partial(headwear,kind))
for kind in ('rectangular','round','goggles','protective','visor','monocle'):add('glasses-'+kind,'Glasses · '+kind,'accessories',partial(glasses,kind))
for kind in ('backpack','satchel','handbag','belt-pouch','apron-bag','rucksack'):add('bag-'+kind,'Bag · '+kind,'accessories',partial(bag,kind))
for kind in ('vest','coat','labcoat','apron','tool-apron','overalls','safety-vest'):add('clothing-'+kind,'Clothing · '+kind,'accessories',partial(clothing,kind))
for kind in ('hammer','pickaxe','shovel','trowel','magnifier','blueprint','scroll'):add('tool-'+kind,'Tool · '+kind,'accessories',partial(tool,kind))
for kind in ('idea','question','exclamation','check','warning','success','coin','speech','cloud','blueprint'):add('icon-'+kind,'Icon · '+kind,'icons',partial(icon,kind))
for kind in ('happy','laugh','surprised','thinking','worried','sad','angry','cool','love','dizzy'):add('emoji-'+kind,'Emotion · '+kind,'emoji',partial(emoji,kind))
for kind in ('right','forward','loop','heat','cold','water','fire','smoke','sparkles','emphasis','impact','orbit'):add('effect-'+kind,'Effect · '+kind,'effects',partial(effect,kind))
for kind in ('play','pause','stop','undo','settings','menu','home','progress','toggle','checkbox-checked','checkbox-empty','slider','new','live','panel','dialog','banner','reward'):add('ui-'+kind,'UI · '+kind,'ui',partial(ui,kind))
for kind in ('leaf','rocket','art','gaming','video','business','health','engineering','cooking'):add('topic-'+kind,'Topic · '+kind,'topics',partial(topic,kind))


def boat():
    # Closed tapered hull, cabins and separate lifesaver ring.
    U.lathe('Hull profile',[(0,.04),(.50,.04),(.84,.28),(.95,.56),(.91,.65),(.76,.58),(0,.58)],'blue')
    box('Boat deck',(0,0,.64),(1.65,1.25,.15),'brown',.15)
    box('Wheelhouse',(0,.14,1.05),(.98,.77,.74),'cream',.12)
    box('Cabin roof',(0,.14,1.46),(1.15,.94,.13),'gold',.07)
    box('Front glass',(0,-.265,1.13),(.67,.04,.40),'blue',.05)
    for x in (-.51,.51):box('Side glass',(x,.14,1.13),(.04,.47,.40),'blue',.04)
    cyl('Smokestack',(.30,.27,1.68),.13,.43,'brown_dark')
    ring('Lifesaver',(.57,-.61,.65),.30,.17,.16,'white')
    for a in (0,math.pi/2,math.pi,math.pi*1.5):
        x=.57+.235*math.cos(a);z=.65+.235*math.sin(a)
        box('Lifesaver stripe',(x,-.71,z),(.16,.07,.15),'red',.025,rotation=(0,-math.degrees(a),0))

def mechanism(kind):
    if kind in ('tire','rim','bearing','spacer','shaft','flange','coupling'):
        r,inner,depth,mat={'tire':(.55,.32,.32,'boot'),'rim':(.34,.21,.24,'steel_light'),
            'bearing':(.24,.12,.15,'steel'),'spacer':(.19,.10,.12,'steel_light'),
            'shaft':(.10,0,1.1,'steel'),'flange':(.30,.16,.12,'steel'),
            'coupling':(.31,.13,.55,'steel')}[kind]
        if inner:ring(kind,(0,0,.6),r,inner,depth,mat)
        else:disk('Shaft',(0,0,.6),r,mat,depth)
        if kind=='tire':
            for i in range(20):
                a=i*math.tau/20;box('Tread',(.53*math.sin(a),0,.6+.53*math.cos(a)),(.13,.36,.08),'sole',.018,rotation=(0,math.degrees(a),0))
        if kind in ('rim','flange'):
            for i in range(6):
                a=i*math.tau/6;disk('Hub fastener',(.265*math.sin(a),-.15,.6+.265*math.cos(a)),.025,'brown_dark',.025)
        if kind=='bearing':
            for i in range(10):
                a=i*math.tau/10;sphere('Bearing ball',(.175*math.sin(a),-.09,.6+.175*math.cos(a)),(.033,.033,.033),'steel_light')
        if kind=='coupling':
            for y in (-.18,.18):ring('Coupling collar',(0,y,.6),.34,.14,.07,'steel_light')
    elif kind in ('cog','bevel-gear'):
        B.gear('Drive gear',radius=.47,material='steel',teeth=12)
        if kind=='bevel-gear':
            for i in range(12):
                a=i*math.tau/12;box('Bevel tooth',(.36*math.cos(a),-.18,.5+.36*math.sin(a)),(.12,.20,.15),'steel_light',.018,rotation=(0,90-math.degrees(a),22))
            ring('Bevel hub',(0,-.13,.5),.25,.12,.30,'steel')
    elif kind=='belt':
        pts=[(.33*math.cos(a)+s,0,.45+.33*math.sin(a)) for s,start in [(.35,-math.pi/2),(-.35,math.pi/2)] for a in [start+i*math.pi/24 for i in range(25)]]
        tube('Drive belt',pts,.065,'boot',cyclic=True)
    elif kind=='chain':
        for i in range(20):
            a=math.tau*i/20;x=.64*math.cos(a);z=.44+.30*math.sin(a)
            ob=ring('Chain link',(x,0,z),.115,.07,.065,'steel');ob.rotation_euler.y=0
    elif kind=='spring':
        tube('Helical spring',[(.27*math.cos(t),.27*math.sin(t),.14+t/(math.tau*7)*1.2) for t in [i*math.tau*7/420 for i in range(421)]],.055,'steel')
    elif kind=='shock':
        cyl('Shock piston',(0,0,.73),.09,1.24,'steel_light')
        tube('Shock spring',[(.22*math.cos(t),.22*math.sin(t),.35+t/(math.tau*5)*.80) for t in [i*math.tau*5/240 for i in range(241)]],.045,'steel')
        for z in (.23,1.25):cyl('Shock collar',(0,0,z),.28,.16,'gold')
        for z in (.05,1.46):ring('Mount eye',(0,0,z),.13,.07,.14,'steel')
    elif kind=='tensioner':
        for x in (-.36,.36):disk('Tensioner roller',(x,0,.44),.24,'steel');disk('Hub',(x,-.13,.44),.11,'gold')
        for z in (.16,.72):rod('Tensioner belt',(-.36,0,z),(.36,0,z),.055,'boot')
        for x in (-.36,.36):arc('Belt bend',(x,0,.44),.28,-math.pi/2,math.pi/2 if x>0 else -3*math.pi/2,'boot',.055)
    elif kind=='gearbox':
        box('Gearbox shell',(0,0,.53),(1.05,.68,.88),'steel',.10);B.gear('Front gear',(0,-.40,.57),.28,'gold',10)
        rod('Output shaft',(-.92,0,.53),(-.52,0,.53),.12,'steel_light')
        for x in (-.40,.40):
            for z in (.20,.87):disk('Case screw',(x,-.36,z),.04,'steel_light',.04)
    elif kind=='motor':
        cyl('Motor body',(0,0,.56),.40,.81,'steel',rotation=(0,90,0));rod('Motor shaft',(.40,0,.56),(.88,0,.56),.10,'steel_light')
        for x in (-.24,0,.24):cyl('Motor cooling fin',(x,0,.56),.44,.055,'dark_steel',rotation=(0,90,0))
        box('Motor base',(0,0,.13),(.92,.70,.17),'gold',.04)
    elif kind=='fuel-can':
        box('Fuel can',(0,0,.51),(.75,.35,.90),'red',.08)
        move(partial(U.frame,'Fuel handle',.42,.23,.09,'red',1.08,True))
        cyl('Fuel cap',(.26,0,1.02),.10,.12,'brown_dark')
        for s in (-1,1):rod('Can reinforcement',(-.25,-.21,.21 if s==1 else .77),(.25,-.21,.77 if s==1 else .21),.03,'copper')
    elif kind=='triangle-bracket':shape('Triangle bracket',[(0,.05),(.8,.05),(0,.85)],'steel',depth=.18);box('Foot',(0.4,0,.03),(.95,.46,.10),'steel',.025)
    elif kind=='mount-plate':
        box('Mount plate',(0,0,.5),(.95,.16,.85),'steel',.05)
        for x in (-.30,.30):
            for z in (.25,.75):disk('Mount recessed hole',(x,-.10,z),.065,'dark_steel',.025)
    elif kind=='slotted-beam':
        for z in (.18,.48):box('Beam rail',(0,0,z),(1.7,.25,.10),'steel',.025)
        for x in (-.80,-.40,0,.40,.80):box('Slot separator',(x,0,.33),(.10,.25,.29),'steel',.02)
    elif kind=='rail':
        for x in (-.25,.25):box('Guide rail',(x,0,.25),(.13,1.5,.30),'steel',.02)
        box('Rail shoe',(0,0,.11),(.68,1.5,.10),'dark_steel',.025)
    elif kind=='gauge':
        disk('Gauge rim',(0,0,.62),.38,'steel');disk('Gauge face',(0,-.10,.62),.31,'white',.04)
        for i in range(9):
            a=math.pi*.16+math.pi*.68*i/8;rod('Gauge tick',(.24*math.cos(a),-.135,.62+.24*math.sin(a)),(.28*math.cos(a),-.135,.62+.28*math.sin(a)),.012,'brown_dark')
        rod('Needle',(0,-.15,.62),(.16,-.15,.82),.018,'red');rod('Pressure stem',(0,0,.0),(0,0,.27),.065,'steel')

def hook():
    ring('Crane hook',(0,0,.32),.22,.12,.16,'steel',start=-math.pi*.92,end=math.pi*.60)
    rod('Hook shank',(.12,0,.48),(.12,0,.85),.085,'steel')
def lifting(kind):
    if kind=='gantry':
        for x in (-.80,.80):box('Crane post',(x,0,.95),(.18,.30,1.75),'steel',.035);box('Crane foot',(x,0,.10),(.53,.65,.20),'gold',.05)
        box('Crane girder',(0,0,1.89),(1.96,.38,.28),'gold',.04)
        for x in (-.66,-.22,.22,.66):box('Hazard stripe',(x,-.21,1.89),(.13,.035,.24),'boot',.01,rotation=(0,-24,0))
        box('Trolley',(0,0,1.62),(.40,.45,.24),'steel',.04);rod('Hoist cable',(0,0,.79),(0,0,1.52),.025,'boot');move(hook,(-.12,0,0))
    elif kind=='arm':
        box('Crane base',(0,0,.13),(.85,.70,.26),'gold',.06)
        for a,b in [((0,0,.28),(-.28,0,1.12)),((-.28,0,1.12),(.72,0,1.36))]:rod('Boom',a,b,.10,'gold');disk('Boom pivot',a,.14,'steel')
        rod('Hook cable',(.72,0,.83),(.72,0,1.36),.025,'boot');move(hook,(.60,0,0))
    else:
        box('Hoist housing',(0,0,1.05),(.63,.39,.48),'gold',.04)
        for x in (-.2,0,.2):box('Hoist stripe',(x,-.21,1.05),(.09,.03,.39),'boot',.01,rotation=(0,-20,0))
        move(hook,(-.12,0,.04));rod('Hoist cable',(0,0,1.3),(0,0,1.65),.05,'steel')
        if kind=='pulley':disk('Pulley wheel',(0,0,1.1),.35,'gold');ring('Pulley rim',(0,-.23,1.1),.27,.18,.05,'steel')

def electronics(kind):
    if kind in ('switch-box','monitor','hmi','dial','pushbutton','toggle'):
        box('Control housing',(0,0,.53),(1.0,.34,.92),'steel',.08)
        if kind in ('monitor','hmi'):
            box('Screen frame',(0,-.21,.60),(.83,.08,.60),'boot',.05);box('Screen',(0,-.26,.60),(.70,.03,.48),'blue',.025)
            if kind=='hmi':move(partial(B.gear,'HMI icon',radius=.18,material='cyan'),(0,-.30,.11))
            else:
                for i in range(4):box('Chart bar',(-.22+i*.14,-.29,.49+i*.035),(.08,.025,.12+i*.07),'cyan',.01)
            box('Screen stand',(0,0,.10),(.60,.44,.12),'dark_steel',.035)
        elif kind=='switch-box':
            for z,col in [( .26,'green'),(.53,'gold'),(.80,'red')]:disk('Status button',(0,-.23,z),.11,col,.10)
        elif kind=='dial':disk('Rotary dial',(0,-.28,.55),.27,'boot',.18);rod('Dial indicator',(0,-.39,.55),(.11,-.39,.73),.035,'gold')
        elif kind=='pushbutton':cyl('Emergency stop base',(0,0,1.04),.22,.12,'gold');cyl('Stop mushroom',(0,0,1.17),.28,.17,'red')
        else:rod('Toggle lever',(0,-.23,.48),(0,-.42,.87),.05,'steel');sphere('Lever grip',(0,-.42,.87),(.10,.10,.12),'red')
    elif kind in ('signal','tower'):
        cyl('Signal pedestal',(0,0,.25),.15,.50,'steel')
        for i,col in enumerate(('green','gold','red')):cyl('Signal segment',(0,0,.64+i*.24),.19,.22,col)
        cyl('Signal cap',(0,0,1.25),.21,.08,'dark_steel')
    elif kind=='cage-lamp':
        U.lantern()
        for a in range(0,360,45):rod('Safety cage',(.24*math.cos(math.radians(a)),.24*math.sin(math.radians(a)),.15),(.24*math.cos(math.radians(a)),.24*math.sin(math.radians(a)),.73),.025,'steel')
    elif kind in ('floodlight','led-bar'):
        width=1.25 if kind=='led-bar' else .8
        box('Light housing',(0,0,.45),(width,.28,.42 if kind=='led-bar' else .68),'steel',.07)
        box('Light face',(0,-.16,.45),(width-.15,.05,.28 if kind=='led-bar' else .52),'lamp',.045)
        move(partial(U.frame,'Light bracket',width+.15,.50,.10,'dark_steel',.26))

def exploded(kind):
    if kind=='wheel':
        for i,part in enumerate(('tire','rim','bearing','spacer','shaft')):move(partial(mechanism,part),((i-2)*.93,0,0))
    else:
        move(partial(B.gear,'Large gear',radius=.55),(-2,0,.1))
        for i,part in enumerate(('spacer','cog','shaft','bearing')):move(partial(mechanism,part),(-.9+i*.85,0,0))
        move(partial(U.fastener,'screw'),(2.6,0,.1),.7)

add('vehicle-boat','Boat · Tàu nhỏ','mechanisms',boat)
for kind in ('tire','rim','bearing','spacer','shaft','flange','coupling','cog','bevel-gear','belt','chain','spring','shock','tensioner','gearbox','motor','fuel-can','triangle-bracket','mount-plate','slotted-beam','rail','gauge'):
    add('mechanism-'+kind,'Mechanism · '+kind,'mechanisms',partial(mechanism,kind))
for kind in ('gantry','arm','hoist','pulley'):add('crane-'+kind,'Crane · '+kind,'mechanisms',partial(lifting,kind))
for kind in ('switch-box','monitor','hmi','dial','pushbutton','toggle','signal','tower','cage-lamp','floodlight','led-bar'):add('electric-'+kind,'Electronics · '+kind,'electronics',partial(electronics,kind))
for kind in ('wheel','gear'):add('assembly-exploded-'+kind,'Exploded assembly · '+kind,'mechanisms',partial(exploded,kind))


def roof(kind='gable'):
    color='blue' if 'blue' in kind or kind=='curved' else ('red' if kind=='hip-red' else 'copper' if kind=='hip-brown' else 'gold')
    if kind in ('flat','curved'):
        if kind=='flat':box('Flat roof',(0,0,.20),(2.4,2.05,.35),'steel',.08);box('Chimney',(.6,.4,.66),(.35,.35,.70),'steel',.04)
        else:
            for i in range(12):
                a=-math.pi/2+(i+.5)*math.pi/12;x=1.05*math.sin(a);z=.15+.65*math.cos(a)
                box('Curved roof segment',(x,0,z),(.29,1.9,.11),color,.025,rotation=(0,math.degrees(a),0))
        return
    if kind.startswith('hip'):
        verts=[(-1.2,-1,.05),(1.2,-1,.05),(1.2,1,.05),(-1.2,1,.05),(-.43,0,.95),(.43,0,.95)]
        mesh=bpy.data.meshes.new('Hip roof');mesh.from_pydata(verts,[],[(0,1,5,4),(1,2,5),(2,3,4,5),(3,0,4),(3,2,1,0)])
        obj=bpy.data.objects.new('Hip roof',mesh);bpy.context.collection.objects.link(obj);B.finish(obj,'Hip roof',color,.035)
        for z in (.25,.50,.75):
            f=(.95-z)/.9
            for y in (-f,f):rod('Tile course',(-.43-.77*f,y,z),(.43+.77*f,y,z),.025,'brown')
    else:
        shape('Gable wall',[(-1.1,.05),(1.1,.05),(0,.90)],'cream',depth=1.8)
        for s in (-1,1):
            for row in range(4):
                x=s*(row+.5)*.30;z=.96-abs(x)*.72
                for j in range(6):box('Individual roof tile',(x,(j-2.5)*.34,z),(.37,.33,.13),color,.035,rotation=(0,s*36,0))
        for j in range(6):box('Ridge tile',(0,(j-2.5)*.34,1.0),(.27,.34,.16),'brown',.045)
        if kind=='skylight':box('Skylight frame',(.58,-.1,.64),(.57,.94,.13),'copper',.03,rotation=(0,36,0));box('Skylight glass',(.58,-.1,.72),(.46,.81,.05),'blue_light',.02,rotation=(0,36,0))

def facade(kind):
    box('Building base',(0,0,.12),(3,2.15,.24),'steel',.07)
    box('Facade walls',(0,0,1.30),(2.65,1.8,2.4),'cream',.06)
    for x in (-1.32,1.32):
        for z in (.45,.92,1.39,1.86,2.33):box('Facade quoins',(x,-.91,z),(.27,.22,.39),'stone',.035)
    if kind=='school':
        move(partial(U.door,'arch'),(0,-.98,.24),.7)
        for x in (-.91,.91):B.window((x,-.94,1.36),.48,.87)
        move(roof,(0,0,2.48),1.15);box('Clock turret',(0,-.92,3.10),(.80,.40,1.0),'cream',.04)
        move(W.wall_clock,(0,-1.15,2.85),.42)
        box('Clock turret cap',(0,-.92,3.64),(.96,.53,.14),'gold',.035)
        rod('School flagpole',(0,-.92,3.70),(0,-.92,4.12),.025,'brown')
        shape('School flag',[(.02,3.85),(.42,3.91),(.42,4.14),(.02,4.10)],'copper',-.92,depth=.04)
    else:
        move(partial(U.door,'window'),(0,-.99,.25),.72)
        for x in (-.92,.92):B.window((x,-.94,1.19),.46,.93)
        box('Flat cornice',(0,0,2.54),(2.90,2.05,.23),'brown_dark',.07)
        box('Building sign',(0,-1.04,2.39),(1.02,.18,.62),'gold' if kind=='workshop' else 'steel',.07)
        if kind=='workshop':move(B.wrench,(0,-1.19,2.08),.35,35);move(partial(W.awning,'red'),(0,-1.0,1.89))
        elif kind=='factory':
            move(partial(B.gear,'Factory emblem',radius=.25),(0,-1.20,1.90))
            for x,z in [(-.65,3.06),(.65,3.27)]:cyl('Factory chimney',(x,.35,z),.16,1.20,'copper');cyl('Chimney cap',(x,.35,z+.62),.21,.12,'steel')
            tube('Factory pipe',[(-1.5,.2,.5),(-1.5,.2,2.9),(-1.0,.2,3.1)],.10,'gold')
        else:
            for angle in (0,60,120):
                pts=[(.29*math.cos(t),-.0,.29*.45*math.sin(t)) for t in [i*math.tau/40 for i in range(41)]]
                a=math.radians(angle);tube('Atom orbit',[(x*math.cos(a)-z*math.sin(a),-1.2,2.4+x*math.sin(a)+z*math.cos(a)) for x,y,z in pts],.02,'white')
            move(partial(W.crystal_jar,True),(1.72,.18,.24),.70)

def wall_module(kind):
    if kind=='window':
        for x in (-.57,.57):box('Wall pier',(x,0,.84),(.36,.45,1.68),'cream',.035)
        for z in (.18,1.51):box('Window wall beam',(0,0,z),(.78,.45,.34),'cream',.04)
        move(partial(U.window,'square'),(0,-.27,.37),.64)
    elif kind=='corner':
        box('Wall return',(0,.4,.75),(.38,1.18,1.5),'cream',.035);box('Corner wall',(.59,0,.75),(.80,.38,1.5),'cream',.035)
        for x,y,sx,sy in [(0,.4,.50,1.30),(.65,0,.80,.5)]:box('Corner coping',(x,y,1.55),(sx,sy,.18),'brown',.035)
    elif kind=='trim':W.wall();box('Cornice',(0,0,1.54),(2.25,.60,.17),'cream',.03)
    else:U.arch_block(1.6,1.7,.45,True)

def opening(kind):
    if kind in ('window-awning','window-shutter'):
        U.window('square')
        if kind=='window-awning':move(partial(W.awning,'red'),(0,-.23,1.08),.65)
        else:
            for s in (-1,1):
                box('Wood shutter',(s*.78,0,.64),(.34,.11,1.04),'brown',.03)
                for z in (.25,.45,.65,.85,1.05):box('Shutter slat',(s*.78,-.08,z),(.30,.07,.10),'copper',.018)
    elif kind=='door-double':
        for s in (-1,1):move(partial(U.door,'window'),(s*.43,0,0),.72)
    elif kind=='door-louvered':
        U.door('solid')
        for z in [.35+i*.13 for i in range(8)]:box('Door louver',(0,-.12,z),(.67,.10,.09),'brown_dark',.018)
    elif kind=='door-metal':
        box('Steel door',(0,0,.9),(1.05,.18,1.80),'steel',.08)
        for x in (-.43,.43):
            for z in (.20,.60,1,1.4,1.65):disk('Door rivet',(x,-.11,z),.025,'steel_light',.03)
        for x in (-.38,-.14,.10,.34):box('Safety stripe',(x,-.12,.3),(.13,.03,.39),'gold',.005,rotation=(0,-25,0))
        box('Door pull',(.30,-.17,.96),(.07,.12,.24),'steel_light',.02)

def balcony(kind):
    U.railing('balcony')
    if kind in ('planted','flower'):
        box('Balcony planter',(0,-.18,.87),(1.28,.37,.30),'copper',.04)
        for x in (-.46,0,.46):move(partial(W.bush,False),(x,-.18,1.01),.36)
        if kind=='flower':
            for x in (-.4,0,.4):W.flower((x,-.43,1.21),.35,'pink',True)
    elif kind=='stone':W.recolor(['rail','post'],'stone_light')
    else:
        for x in (-.62,.62):box('Terrace post',(x,.28,1.08),(.14,.14,2.16),'brown',.025)
        box('Terrace canopy',(0,.28,2.16),(1.55,.70,.16),'gold',.035)

def gate(kind):
    if kind in ('arch-lighted','arch-dark'):
        B.arch_entry();W.recolor(['arch','stone'],'brown_dark' if kind=='arch-dark' else 'stone')
        if kind=='arch-lighted':
            for x in (-1.0,1.0):move(U.lantern,(x,-.42,.85),.35)
    elif kind=='metal':
        U.frame('Gate frame',1.5,1.7,.12,'dark_steel',.87)
        for x in (-.6,-.3,0,.3,.6):rod('Gate bar',(x,0,.1),(x,0,1.62),.025,'steel')
        arc('Gate arch',(0,0,1.5),.75,0,math.pi,'dark_steel',.065)
    elif kind=='wood':
        for x in (-.60,-.30,0,.30,.60):box('Gate plank',(x,0,.75),(.27,.14,1.5-abs(x)*.25),'copper',.055)
        for z in (.35,1.05):box('Gate brace',(0,-.11,z),(1.5,.10,.13),'brown',.025)
    elif kind=='rope':
        for x in (-.65,.65):cyl('Rope post',(x,0,.57),.09,1.14,'brown');sphere('Post cap',(x,0,1.17),(.13,.13,.13),'gold')
        tube('Barrier rope',[(x,0,.90+.38*(x/.65)**2) for x in [-.65+i*1.3/24 for i in range(25)]],.045,'paper')
    elif kind=='chainlink':
        for x in (-.80,.80):rod('Fence post',(x,0,.05),(x,0,1.30),.045,'steel')
        for z in (.12,1.20):rod('Fence rail',(-.8,0,z),(.8,0,z),.035,'steel')
        for s in (-1,1):
            for k in range(-6,7):
                pts=[]
                for i in range(65):
                    x=-.76+i*1.52/64;z=s*x+k*.23+.65
                    if .15<=z<=1.18:pts.append((x,0,z))
                if len(pts)>1:tube('Chainlink wire',pts,.012,'steel')

def street(kind):
    if kind=='trash':
        box('Trash bin',(0,0,.55),(.68,.63,1.10),'steel',.05);box('Bin lid',(0,0,1.15),(.78,.73,.16),'dark_steel',.06)
        for x in (-.23,0,.23):box('Bin rib',(x,-.33,.56),(.045,.035,.80),'dark_steel',.015)
    elif kind=='bollard':cyl('Bollard',(0,0,.43),.18,.86,'boot');cyl('Reflective band',(0,0,.63),.185,.14,'gold')
    elif kind=='cone':
        box('Cone base',(0,0,.06),(.66,.66,.12),'red',.045)
        for z,r1,r2,col in [(.24,.24,.19,'red'),(.43,.19,.14,'white'),(.62,.14,.09,'red'),(.78,.09,.045,'white')]:W.cone('Traffic cone',(0,0,z),r1,r2,.20,col)
    elif kind in ('double-lamp','gooseneck'):
        cyl('Lamp base',(0,0,.12),.22,.24,'brown_dark');rod('Lamp post',(0,0,.12),(0,0,2.0),.06,'brown_dark')
        for s in ((-1,1) if kind=='double-lamp' else (1,)):
            tube('Curved lamp arm',[(0,0,1.65),(s*.18,0,2.10),(s*.49,0,2.16),(s*.64,0,1.96)],.055,'brown_dark')
            W.cone('Lamp hood',(s*.64,0,1.91),.25,.08,.16,'brown');sphere('Glowing bulb',(s*.64,0,1.81),(.15,.15,.13),'lamp')
    elif kind=='market':
        box('Stall counter',(0,0,.60),(1.7,.85,.22),'copper',.04)
        for x in (-.70,.70):
            for y in (-.30,.30):box('Stall post',(x,y,.9),(.12,.12,1.8),'brown',.025)
        move(partial(W.awning,'red'),(0,.10,1.76),.82)
        for x in (-.5,0,.5):box('Produce crate',(x,0,.84),(.4,.50,.27),'gold',.03)
    elif kind=='flower-planter':box('Flower box',(0,0,.25),(1.35,.65,.5),'cream',.05);[W.flower((x,0,.48),.6,'pink') for x in (-.4,0,.4)]

def bridge(kind):
    # Curved masonry arch with open water clearance, rather than a solid block.
    color='steel' if kind=='gray' else 'stone'
    ring('Bridge arch',(0,0,.15),1.1,.79,1.05,color,start=0,end=math.pi,segments=20)
    for i in range(11):
        x=(i-5)*.21;z=.20+math.sqrt(max(0,1.1**2-x*x))
        box('Bridge paving',(x,0,z),(.23,1.1,.14),'stone_light' if kind!='gray' else 'steel_light',.035)
        for y in (-.57,.57):box('Stone parapet',(x,y,z+.23),(.23,.18,.38),color,.035)

def landscape(kind):
    if kind.startswith('cliff'):
        W.cliff()
        if kind=='cliff-outer':move(W.cliff,(.44,.48,0),.70,90)
        elif kind=='cliff-inner':move(W.cliff,(-.44,.48,0),.70,90)
        elif kind=='cliff-rocky':move(W.rock,(.48,-.38,.02),.70)
    elif kind.startswith('hill'):
        n={'hill-low':1,'hill-mid':2,'hill-high':3}[kind]
        for i in range(n):
            size=1.35-i*.28;box('Hill tier',(0,0,.22+i*.35),(size,size,.46),'stone',.13);box('Grassy hill cap',(0,0,.46+i*.35),(size+.05,size+.05,.15),'grass',.10)
    elif kind in ('water-edge','water-corner'):
        W.terrain('river');move(W.cliff,(0,.74,0),.75)
        if kind=='water-corner':move(W.cliff,(.74,0,0),.75,90)
    elif kind=='waterfall-tiered':W.waterfall();move(W.waterfall,(0,.75,.95),.72)
    elif kind=='palm':
        tube('Palm trunk',[(0,0,0),(.10,0,.7),(.15,0,1.5),(.05,0,2.0)],.12,'brown')
        for i in range(7):
            a=i*math.tau/7;end=(.95*math.cos(a),.95*math.sin(a),1.60)
            tube('Palm frond',[(.05,0,2),(.50*math.cos(a),.50*math.sin(a),2.15),end],.10,'green')
    elif kind=='fern':
        for s in (-1,1):
            for i in range(4):
                z=.23+i*.16;rod('Fern stem',(0,0,.05),(s*.15*(i+1),0,z+.25),.018,'green_dark')
                for j in range(3):sphere('Fern leaflet',(s*(.08*(i+1)+j*.06),0,z+j*.055),(.15,.035,.06),'green')
    elif kind=='tulips':
        for x in (-.28,0,.28):rod('Tulip stem',(x,0,0),(x,0,.60),.023,'green');sphere('Tulip',(x,0,.65),(.12,.10,.17),'red')
    elif kind in ('log','stump'):
        length=1.25 if kind=='log' else .48
        cyl('Bark',(0,0,.30),.30,length,'brown',rotation=(0,90,0) if kind=='log' else (0,0,0))
        for s in (-1,1):
            if kind=='log':cyl('Cut wood',(s*(length/2+.01),0,.30),.26,.025,'paper',rotation=(0,90,0))
            else:cyl('Cut wood',(0,0,.55),.26,.025,'paper')
    elif kind.startswith('mushroom'):
        r=.30 if kind.endswith('large') else .18
        cyl('Mushroom stalk',(0,0,r*.7),r*.22,r*1.4,'cream');sphere('Mushroom cap',(0,0,r*1.5),(r,r,r*.45),'red')
        for x,y in [(-.1,-.1),(.09,-.09),(0,.11)]:sphere('White cap spot',(x,y,r*1.85),(.035,.035,.02),'white')
    elif kind=='gold-bars':
        for x,y,z in [(-.27,0,.13),(.27,0,.13),(0,.10,.37)]:box('Gold ingot',(x,y,z),(.48,.43,.24),'gold',.04)
    elif kind=='rock-column':
        for x,z,s in [(-.3,.5,.45),(.25,.9,.55),(.55,.3,.35)]:box('Rock pillar',(x,0,z),(s,.6,z*2),'steel',.12)
    elif kind=='road-t':
        W.road('crossroad');box('T junction curb',(0,.82,.30),(1.9,.26,.14),'cream',.03)
    elif kind=='tactile':
        W.road(sidewalk=True)
        for x in (-.55,-.18,.18,.55):
            for y in (-.55,-.18,.18,.55):sphere('Tactile dot',(x,y,.37),(.07,.07,.035),'gold')
    elif kind=='path-cobble':
        box('Path tile',(0,0,.08),(1.6,1.6,.16),'stone',.04)
        for x in (-.55,0,.55):
            for y in (-.55,0,.55):box('Cobble',(x,y,.20),(.50,.50,.14),'stone_light',.10)
    elif kind=='ramp':shape('Ramp',[(-.8,0),(.8,0),(.8,.85)],'stone',depth=1.1)

def flag(kind):
    if kind=='bunting':
        tube('Bunting rope',[(-1,0,1),(-.5,0,.85),(0,0,.80),(.5,0,.85),(1,0,1)],.02,'brown')
        for x,col in [(-.75,'red'),(-.25,'blue'),(.25,'gold'),(.75,'green')]:shape('Pennant',[(x-.20,.91),(x+.20,.91),(x,.43)],col)
    else:
        rod('Flag pole',(-.46,0,.05),(-.46,0,1.7),.035,'brown');sphere('Pole cap',(-.46,0,1.73),(.075,.075,.075),'gold')
        pts=[(-.44,.81),(.42,.81),(.42,1.59),(-.44,1.59)] if kind=='rectangle' else [(-.44,1.59),(.40,1.59),(.40,.83),(0,.61),(-.44,.83)]
        shape('Flag cloth',pts,'copper' if kind=='rectangle' else 'blue' if kind=='pennant' else 'red',depth=.045)
        if kind=='award':star('Banner star',(0,-.07,1.18),.22)

def diorama(kind):
    box('Diorama base',(0,0,.10),(6,4,.20),'steel',.08)
    if kind in ('garage','factory'):
        box('Workshop back wall',(0,1.73,1.35),(5.8,.24,2.6),'cream',.06)
        if kind=='garage':
            move(U.workshop,(-1.6,1.05,.2),.8);move(W.car,(1.30,.1,.2),.75)
            move(partial(lifting,'gantry'),(1.15,.7,.2),.9);move(partial(tool,'hammer'),(-2,-.6,.2),.7)
            move(partial(street,'cone'),(2.28,-1,.2),.7)
        else:
            move(U.machine,(1.4,1,.2),.8);move(W.robot_arm,(-1.5,.9,.2),.9)
            box('Conveyor body',(0,-.30,.72),(4.3,.82,.25),'steel',.04)
            for x in [-1.9+i*.27 for i in range(15)]:cyl('Conveyor roller',(x,-.30,.88),.09,.78,'steel_light',rotation=(90,0,0))
            for x in (-1.2,.3,1.6):move(B.crate,(x,-.3,.98),.28)
            move(partial(electronics,'tower'),(2.45,.8,.2),.9)
    elif kind=='street':
        for x,fn in [(-1.9,W.house),(0,partial(W.house,'shop')),(1.9,partial(W.house,'cafe'))]:move(fn,(x,.70,.20),.61)
        move(W.bench,(.7,-.9,.2),.55);move(W.streetlamp,(-1.8,-.9,.2),.65)
        box('Road',(0,-1.43,.25),(5.8,.66,.08),'boot',.02)
        for x in (-2,-1,0,1,2):box('Road dash',(x,-1.44,.30),(.5,.035,.01),'white',.002)
    elif kind=='village':
        move(W.watchtower,(-1.9,.9,.2),.61);move(W.house,(1.6,.9,.2),.60)
        cyl('Fountain basin',(0,-.45,.38),.83,.35,'stone');cyl('Fountain water',(0,-.45,.57),.70,.035,'water')
        cyl('Fountain pillar',(0,-.45,.89),.13,.70,'stone_light');cyl('Fountain bowl',(0,-.45,1.18),.40,.16,'stone')
        for x in (-2.3,2.3):move(W.tree,(x,-.60,.20),.50)
    else:
        move(partial(facade,'workshop'),(-1.45,.5,.2),.66);move(partial(facade,'lab'),(1.1,.5,.2),.66)
        for x in (-2.4,2.4):move(W.tree,(x,-.6,.2),.47)
        move(partial(gate,'chainlink'),(0,-1.4,.2),.65)

for kind in ('workshop','school','lab','factory'):add('facade-'+kind,'Building facade · '+kind,'architecture',partial(facade,kind))
for kind in ('gable','gable-blue','hip-red','hip-brown','flat','curved','skylight'):add('roof-'+kind,'Roof module · '+kind,'architecture',partial(roof,kind))
for kind in ('window','corner','trim','arch'):add('wall-'+kind,'Wall module · '+kind,'architecture',partial(wall_module,kind))
for kind in ('window-awning','window-shutter','door-double','door-louvered','door-metal'):add('opening-'+kind,'Opening · '+kind,'architecture',partial(opening,kind))
for kind in ('planted','flower','stone','terrace'):add('balcony-'+kind,'Balcony · '+kind,'architecture',partial(balcony,kind))
for kind in ('arch-lighted','arch-dark','metal','wood','rope','chainlink'):add('gate-'+kind,'Gate / barrier · '+kind,'architecture',partial(gate,kind))
for kind in ('trash','bollard','cone','double-lamp','gooseneck','market','flower-planter'):add('street-'+kind,'Street prop · '+kind,'environment',partial(street,kind))
for kind in ('stone','gray'):add('bridge-'+kind,'Bridge · '+kind,'environment',partial(bridge,kind))
for kind in ('cliff-outer','cliff-inner','cliff-rocky','hill-low','hill-mid','hill-high','water-edge','water-corner','waterfall-tiered','palm','fern','tulips','log','stump','mushroom-small','mushroom-large','gold-bars','rock-column','road-t','tactile','path-cobble','ramp'):
    add('environment-'+kind,'Environment · '+kind,'environment',partial(landscape,kind))
for kind in ('rectangle','pennant','award','bunting'):add('flag-'+kind,'Flag · '+kind,'environment',partial(flag,kind))
for kind in ('garage','factory','street','village','science'):add('diorama-'+kind,'Diorama · '+kind,'examples',partial(diorama,kind))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--only');parser.add_argument('--resume',action='store_true');parser.add_argument('--resolution',type=int,default=320);parser.add_argument('--samples',type=int,default=8)
    args=parser.parse_args();root=assets_dir();folder=root/'generated'/PACK;folder.mkdir(parents=True,exist_ok=True)
    refs=root/'references'/PACK;refs.mkdir(parents=True,exist_ok=True)
    for name in REFERENCES:
        if not (refs/name).exists():shutil.copyfile(Path('D:/Downloads')/name,refs/name)
    W.PACK=PACK;W.GROUPS=GROUPS;W.ASSETS=ASSETS
    manifest=folder/'manifest.json';data=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {}
    entries={a['slug']:a for a in data.get('assets',[])}
    chosen=args.only.split(',') if args.only else list(ASSETS)
    for i,slug in enumerate(chosen):
        if args.resume and slug in entries and all((folder/(slug+s)).exists() for s in ('.glb','.blend','.png','.asset.json')):continue
        entry=W.build(slug,folder,root,args.resolution,args.samples)
        entry['description']=ASSETS[slug][2]+' · Universal Expansion. Mô hình tĩnh, mesh chỉnh sửa được; chưa có rig hoặc animation.'
        entries[slug]=entry
        (folder/(slug+'.asset.json')).write_text(json.dumps({k:v for k,v in entry.items() if k not in ('slug','path')},ensure_ascii=False,indent=2),encoding='utf-8')
        manifest.write_text(json.dumps({'pack':PACK,'groups':GROUPS,'references':[(refs/n).relative_to(root).as_posix() for n in REFERENCES],'assets':list(entries.values())},ensure_ascii=False,indent=2),encoding='utf-8')
        print('DONE',i+1,'/',len(chosen),slug,flush=True)
    print('PACK READY',len(entries),flush=True)

if __name__=='__main__':main()
