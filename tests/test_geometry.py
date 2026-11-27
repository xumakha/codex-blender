from copy import deepcopy
import unittest

from pydantic import ValidationError
from codex_blender.geometry import expand_objects, recipe_instances
from codex_blender.models import Object, ShotBrief, ShotDesign, VideoPlan
from codex_blender.planning import check_elements, check_inventory, normalize_inventory, prompt_contract


def obj(name,kind='cube',**values):
    return Object(name=name,kind=kind,**values).model_dump(mode='json')


class GeometryTests(unittest.TestCase):
    def test_nested_repeats_build_ten_floors_and_one_hundred_steps(self):
        templates=[obj('building','empty'),obj('floor','empty',parent='building',repeat={'count':10,'offset':[0,0,3]}),
            obj('slab',parent='floor'),obj('step',parent='floor',repeat={'count':10,'offset':[.15,0,.3]})]
        expanded=expand_objects(templates)
        self.assertEqual(len({item['name'] for item in expanded}),len(expanded))
        self.assertEqual(len(recipe_instances(templates,['step'])),100)
        self.assertEqual(len(recipe_instances(templates,['slab'])),10)
        final=next(item for item in expanded if item['name']=='step__R1_9__R2_9')
        self.assertEqual(final['parent'],'floor__R1_9')
        self.assertAlmostEqual(final['location'][0],1.35)

    def test_repeated_motion_keeps_offsets_and_does_not_modify_recipe(self):
        templates=[obj('door',repeat={'count':2,'offset':[3,0,0]},keyframes=[{'time':2,'location':[1,0,1]}])]
        original=deepcopy(templates)
        expanded=expand_objects(templates)
        self.assertEqual(expanded[1]['keyframes'][0]['location'],[4,0,1])
        self.assertEqual(templates,original)
        with self.assertRaises(ValueError):expand_objects(templates,limit=1)

    def test_a_head_mesh_does_not_count_its_parented_eyes_as_head_parts(self):
        templates=[obj('head','sphere'),obj('eye','sphere',parent='head',repeat={'count':2,'offset':[.2,0,0]})]
        self.assertEqual(len(recipe_instances(templates,['head'],parts=True)),1)
        self.assertEqual(len(recipe_instances(templates,['eye'],parts=True)),2)

    def test_a_repeated_flight_is_counted_as_an_assembly_not_all_its_steps(self):
        templates=[obj('flight','empty',repeat={'count':18,'offset':[0,0,1]}),obj('step',parent='flight',repeat={'count':10,'offset':[.1,0,.1]}),obj('empty_group','empty')]
        self.assertEqual(len(recipe_instances(templates,['flight'],parts=True)),18)
        self.assertEqual(len(recipe_instances(templates,['step'],parts=True)),180)
        self.assertEqual(recipe_instances(templates,['empty_group'],parts=True),[])

    def test_elements_must_have_actual_separate_geometry_and_correct_counts(self):
        brief=ShotBrief(title='Building',start=0,end=5,setting='Studio',actions=['Reveal the stairs'],elements=[
            {'id':'building','label':'Ten-floor building','source':'Tòa nhà 10 tầng','role':'setting','appearance':'Cream','parts':[{'name':'floors','count':10}]}])
        design=ShotDesign(objects=[{'name':'building','kind':'empty'},{'name':'slab','kind':'cube','parent':'building','repeat':{'count':10,'offset':[0,0,1]}}],
            element_bindings=[{'element_id':'building','objects':['building'],'parts':[{'part':'floors','objects':['slab']}]}])
        check_elements(brief,design)
        design.objects[1].repeat.count=9
        with self.assertRaises(ValueError):check_elements(brief,design)
        design.objects[1].repeat.count=10
        design.objects[1].kind='image';design.objects[1].asset='photo.png'
        with self.assertRaises(ValueError):check_elements(brief,design)

    def test_part_bindings_cannot_reuse_one_block_for_different_body_parts(self):
        brief=ShotBrief(title='Person',start=0,end=5,setting='Studio',actions=['Point'],elements=[
            {'id':'person','label':'Inventor','source':'Nhà phát minh áo vàng','role':'character','appearance':'Yellow shirt',
             'parts':[{'name':'head'},{'name':'shirt'}]}])
        design=ShotDesign(objects=[{'name':'body','kind':'cube'}],element_bindings=[{'element_id':'person','objects':['body'],
            'parts':[{'part':'head','objects':['body']},{'part':'shirt','objects':['body']}]}])
        with self.assertRaises(ValueError):check_elements(brief,design)

    def test_inventory_keeps_explicit_quantities_and_source_quotes(self):
        plan=VideoPlan(title='Building',duration=5,style='3D',shots=[{'title':'Building','start':0,'end':5,'setting':'Studio','actions':['Reveal stairs'],
            'elements':[{'id':'building','label':'Building','source':'Tòa nhà 10 tầng','role':'setting','appearance':'Cream'}]}])
        with self.assertRaises(ValueError):check_inventory(plan,'Tòa nhà 10 tầng')
        from codex_blender.models import ElementPart
        plan.shots[0].elements[0].parts=[ElementPart(name='floors',count=10)]
        check_inventory(plan,'Tòa nhà 10 tầng')
        with self.assertRaises(ValueError):check_inventory(plan,'A completely different prompt')

    def test_declared_full_duration_overrides_old_preview_prefix(self):
        prompt='Tạo thử 5 giây với script này. Cảnh 1, mở đầu.\n\nThời lượng: 90–120 giây.\n00:00–00:10\nLời đọc: “Opening words.”\n00:10–01:35'
        contract=prompt_contract(prompt)
        self.assertEqual(contract['scope'],'full')
        self.assertEqual(contract['duration'],95)
        self.assertEqual(contract['duration_range'],(90,120))
        self.assertEqual(contract['intervals'],[(0,10),(10,95)])
        self.assertEqual(contract['speech'],['Opening words.'])

    def test_preview_without_a_declared_full_duration_is_still_supported(self):
        contract=prompt_contract('Tạo thử 5 giây với script này.\n\n00:00–00:10\n00:10–01:35')
        self.assertEqual(contract['scope'],'excerpt')
        self.assertEqual(contract['duration'],5)

    def test_floor_count_in_a_source_quote_does_not_require_ten_studios(self):
        plan=VideoPlan(title='Studio',duration=5,style='3D',shots=[{'title':'Studio','start':0,'end':5,'setting':'Studio','actions':['Point'],
            'elements':[{'id':'studio','label':'Nền studio','source':'Tòa nhà 10 tầng đứng trên nền kem','role':'setting','appearance':'Cream','parts':[{'name':'floor','count':1}]}]}])
        check_inventory(plan,'Tòa nhà 10 tầng đứng trên nền kem')

    def test_timed_subtitles_are_an_overlay_not_a_fake_3d_prop(self):
        plan=VideoPlan(title='Caption',duration=5,style='3D',captions=True,shots=[{'title':'Studio','start':0,'end':5,'setting':'Studio','actions':['Point'],
            'elements':[{'id':'captions','label':'Phụ đề tiếng Việt','source':'Phụ đề tiếng Việt','role':'graphic','appearance':'White text'}]}])
        normalize_inventory(plan)
        self.assertEqual(plan.shots[0].elements[0].construction,'overlay')
        check_elements(plan.shots[0],ShotDesign(objects=[{'name':'body','kind':'cube'}]))
