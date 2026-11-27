import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from codex_blender import director,studio,config
from codex_blender.asset_preparation import (AssetPreparation,model_inventory,fingerprint,validate_preparation,
    check_plan_assets,check_design_assets,check_scene_assets)
from codex_blender.library import catalog
from codex_blender.models import VideoPlan,ShotDesign,SceneSpec,Object

def write_glb(path):
    document=json.dumps({'asset':{'version':'2.0'},'meshes':[{'primitives':[]}]}).encode()
    document+=b' '*((-len(document))%4)
    path.write_bytes(struct.pack('<4sIII4s',b'glTF',2,20+len(document),len(document),b'JSON')+document)

class AssetPreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        for name in ('gear','core-cube','sofa'):write_glb(self.root/(name+'.glb'))
        self.models=model_inventory(catalog(self.root),self.root)
        self.prepared=AssetPreparation(requirements=[{'id':'drive','label':'Drive','source':'Gear drive','role':'prop',
            'reason':'Gear meshes and core blocks assemble a gearbox',
            'objects':[{'name':'gear','kind':'model','asset':'gear.glb'},
                       {'name':'housing','kind':'model','asset':'core-cube.glb','repeat':{'count':2,'offset':[1,0,0]}}]}])
        self.plan=VideoPlan(title='Drive',duration=2,style='Library',shots=[{'title':'Drive','start':0,'end':2,
            'setting':'Gear drive','actions':['Rotate gear'],
            'elements':[{'id':'drive','label':'Drive','source':'Gear drive','role':'prop','appearance':'Gear drive',
                'construction':'asset','requirement_id':'drive','asset_paths':['gear.glb','core-cube.glb']}]}])
        self.design=ShotDesign(ground=False,objects=[{'name':'gear','kind':'model','asset':'gear.glb','keyframes':[{'time':2,'rotation':[0,360,0]}]},
            {'name':'housing','kind':'model','asset':'core-cube.glb','repeat':{'count':2,'offset':[1,0,0]}}],
            element_bindings=[{'element_id':'drive','objects':['gear','housing']}])

    def test_existing_core_blocks_can_assemble_a_missing_finished_object(self):
        validate_preparation(self.prepared,self.models,'Gear drive',self.root)
        check_plan_assets(self.plan,self.prepared)
        check_design_assets(self.plan.shots[0],self.design,self.prepared,self.root)

    def test_every_library_model_is_available_beyond_old_200_limit(self):
        assets=[{'path':'gear.glb','kind':'model','name':f'Asset {i}','tags':[]} for i in range(260)]
        assets.append({'path':'sofa.glb','kind':'image','name':'Not a model'})
        inventory=model_inventory(assets,self.root)
        self.assertEqual(len(inventory),260);self.assertEqual(inventory[-1]['name'],'Asset 259')
        changed=copy.deepcopy(inventory);changed[-1]['modified']=123
        self.assertNotEqual(fingerprint(inventory),fingerprint(changed))

    def test_unprepared_unrelated_asset_is_rejected_in_shot(self):
        self.design.objects[0].asset='sofa.glb'
        with self.assertRaisesRegex(ValueError,'chưa được chuẩn bị'):check_design_assets(self.plan.shots[0],self.design,self.prepared,self.root)

    def test_unprepared_setting_and_silently_dropped_requirement_are_rejected(self):
        self.plan.shots[0].elements[0].requirement_id='unknown'
        with self.assertRaisesRegex(ValueError,'chuẩn bị'):check_plan_assets(self.plan,self.prepared)
        self.plan.shots[0].elements=[]
        with self.assertRaisesRegex(ValueError,'bỏ sót'):check_plan_assets(self.plan,self.prepared)

    def test_preparation_rejects_new_primitives_and_broken_files(self):
        self.prepared.requirements[0].objects[0].kind='cube'
        with self.assertRaisesRegex(ValueError,'không tự sinh'):validate_preparation(self.prepared,self.models,'Gear drive',self.root)
        self.prepared.requirements[0].objects[0].kind='model'
        (self.root/'gear.glb').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'GLB không hợp lệ'):validate_preparation(self.prepared,self.models,'Gear drive',self.root)

    def test_shot_cannot_drop_prepared_component_counts(self):
        self.design.objects[1].repeat=None
        with self.assertRaisesRegex(ValueError,'thiếu số lượng'):check_design_assets(self.plan.shots[0],self.design,self.prepared,self.root)

    def test_final_render_guard_rejects_native_geometry_and_missing_asset(self):
        with self.assertRaisesRegex(ValueError,'không tự sinh'):check_scene_assets(SceneSpec(ground=False,objects=[{'name':'fake','kind':'cube'}]),self.root)
        scene=SceneSpec(ground=False,objects=[{'name':'real','kind':'model','asset':'gear.glb'}])
        check_scene_assets(scene,self.root)
        (self.root/'gear.glb').unlink()
        with self.assertRaises(ValueError):check_scene_assets(scene,self.root)

    def test_assembly_uses_group_repetitions_and_keeps_scale(self):
        req=self.prepared.requirements[0];req.count=3
        req.objects=[Object(name='Group',kind='empty',repeat={'count':3,'offset':[1,0,0]}),
                     Object(name='Gear',kind='model',asset='gear.glb',parent='Group')]
        validate_preparation(self.prepared,self.models,'Gear drive',self.root)
        self.prepared.requirements[0].objects[0].scale=(1,2,1)
        validate_preparation(self.prepared,self.models,'Gear drive',self.root)
        self.prepared.requirements[0].objects[0].scale=(-1,2,1)
        with self.assertRaisesRegex(ValueError,'tỷ lệ'):validate_preparation(self.prepared,self.models,'Gear drive',self.root)

    def test_missing_asset_triggers_generation_before_screenplay_and_reports_export_failure(self):
        data=self.root/'data';pid='a'*32;path=data/'projects'/pid;path.mkdir(parents=True)
        draft=studio.Draft(prompt='A dragon')
        (path/'project.json').write_text(json.dumps({'id':pid,'draft':draft.model_dump(mode='json'),'state':'planning'}))
        missing=AssetPreparation(requirements=[{'id':'dragon','label':'Dragon','source':'A dragon','role':'prop',
            'reason':'Cannot assemble the required detailed skin','missing':'Chưa có bộ phận phù hợp'}])
        def fake_planner(pid,draft,root,model,task,instructions,stage,validate):
            self.assertEqual(stage,'assets');self.assertEqual(len(task['models']),3);validate(missing);return missing
        with patch.object(studio,'DATA',data),patch.object(director,'call_planner',side_effect=fake_planner) as planner, \
             patch('codex_blender.fonts.ensure_font',return_value='font.ttf'),patch.object(studio,'render_project') as render, \
             patch('codex_blender.asset_generation.generate_missing',side_effect=RuntimeError('Export failed')) as generate:
            studio.plan_scene(pid,draft,self.root,auto_render=True)
        saved=json.loads((path/'project.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['state'],'error');self.assertFalse(saved['asset_preparation']['ready'])
        self.assertIn('Dragon',saved['error']);self.assertFalse((path/'screenplay.json').exists())
        self.assertEqual(planner.call_count,1);render.assert_not_called()
        generate.assert_called_once()
        self.assertEqual(saved['asset_preparation']['generation_state'],'failed')

    def test_style_and_manual_preferences_do_not_restrict_future_selection(self):
        from codex_blender.planning import signature
        first=studio.Draft(prompt='Gear drive',style='Old clay preset',selected_assets=['sofa.glb'])
        second=studio.Draft(prompt='Gear drive')
        self.assertEqual(signature(first),signature(second))

    def test_generation_is_completed_before_screenplay_and_prepared_components_are_used(self):
        data=self.root/'data';pid='b'*32;path=data/'projects'/pid;path.mkdir(parents=True)
        draft=studio.Draft(prompt='Gear drive')
        (self.root/'font.ttf').write_bytes(b'test font')
        (path/'project.json').write_text(json.dumps({'id':pid,'draft':draft.model_dump(mode='json'),'state':'planning'}))
        pending=AssetPreparation(requirements=[{'id':'drive','label':'Drive','source':'Gear drive','role':'prop',
            'reason':'Need a custom housing variant','missing':'Generate housing and gear'}])
        stages=[]
        def planner(pid,draft,root,model,task,instructions,stage,validate):
            stages.append(stage)
            value=pending if stage=='assets' else self.plan if stage=='screenplay' else self.design
            validate(value);return value
        def generate(pid,draft,root,requirement,models,planner):
            stages.append('generate')
            requirement.objects=self.prepared.requirements[0].objects
            requirement.missing=''
        with patch.object(studio,'DATA',data),patch.object(director,'call_planner',side_effect=planner), \
             patch('codex_blender.fonts.ensure_font',return_value='font.ttf'),patch('codex_blender.fonts.supports_vietnamese',return_value=True), \
             patch('codex_blender.director.validate_assets'),patch('codex_blender.asset_generation.generate_missing',side_effect=generate):
            self.design.bindings=[{'action_index':0,'objects':['gear'],'start':0,'end':2,'elements':['drive']}]
            self.design=ShotDesign.model_validate(self.design.model_dump())
            studio.plan_scene(pid,draft,self.root)
        saved=json.loads((path/'project.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['state'],'ready',saved.get('error'))
        self.assertEqual(stages,['assets','generate','screenplay','shot-01'])
        self.assertTrue(saved['asset_preparation']['ready'])

    def test_generated_materials_and_native_details_are_authorized_with_library_references(self):
        from codex_blender.asset_generation import GeneratedAssembly,validate_generated
        design=GeneratedAssembly(reference_assets=['core-cube.glb'],description='Cyan ice and extra snow cap',ground=False,
            objects=[{'name':'Ice','kind':'model','asset':'core-cube.glb','recolor':'#55CCFF','transmission':.95,'scale':[1,2,1]},
                     {'name':'Snow','kind':'cone','color':'#FFFFFF'}])
        validate_generated(design,self.models,self.root)
        design.reference_assets=['invented.glb']
        with self.assertRaisesRegex(ValueError,'thực sự có'):validate_generated(design,self.models,self.root)

    def test_nonvisual_rules_are_not_reported_as_missing_physical_assets(self):
        value=AssetPreparation(requirements=[{'id':'camera','label':'Camera hold','source':'Camera fixed',
            'role':'graphic','reason':'Camera constraint'}])
        with self.assertRaisesRegex(ValueError,'constraints'):validate_preparation(value,self.models,'Camera fixed',self.root)

    def test_direct_scene_import_does_not_bypass_asset_preparation(self):
        scene=SceneSpec(prompt='Gear drive',ground=False,objects=[{'name':'Gear','kind':'model','asset':'gear.glb'}])
        with patch.object(studio,'DATA',self.root/'data'):
            project=studio.create_project(studio.Draft(prompt='Gear drive',scene=scene))
            with patch.object(studio,'start_plan',return_value={'state':'planning'}) as prepare,patch.object(studio,'submit') as submit:
                result=studio.render_project(project['id'],'preview')
            prepare.assert_called_once_with(project['id'],auto_render=True,render_mode='preview')
            submit.assert_not_called();self.assertEqual(result['state'],'planning')

if __name__=='__main__':unittest.main()
