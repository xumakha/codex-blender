import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from codex_blender import studio,config
from codex_blender.asset_preparation import AssetPreparation, model_inventory, fingerprint, validate_preparation
from codex_blender.library import catalog
from codex_blender.models import SceneSpec,Object

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

    def test_existing_core_blocks_can_assemble_a_missing_finished_object(self):
        validate_preparation(self.prepared,self.models,'Gear drive',self.root)

    def test_every_library_model_is_available_beyond_old_200_limit(self):
        assets=[{'path':'gear.glb','kind':'model','name':f'Asset {i}','tags':[]} for i in range(260)]
        assets.append({'path':'sofa.glb','kind':'image','name':'Not a model'})
        inventory=model_inventory(assets,self.root)
        self.assertEqual(len(inventory),260);self.assertEqual(inventory[-1]['name'],'Asset 259')
        changed=copy.deepcopy(inventory);changed[-1]['modified']=123
        self.assertNotEqual(fingerprint(inventory),fingerprint(changed))

    def test_preparation_rejects_new_primitives_and_broken_files(self):
        self.prepared.requirements[0].objects[0].kind='cube'
        with self.assertRaisesRegex(ValueError,'không tự sinh'):validate_preparation(self.prepared,self.models,'Gear drive',self.root)
        self.prepared.requirements[0].objects[0].kind='model'
        (self.root/'gear.glb').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'GLB không hợp lệ'):validate_preparation(self.prepared,self.models,'Gear drive',self.root)

    def test_assembly_uses_group_repetitions_and_keeps_scale(self):
        req=self.prepared.requirements[0];req.count=3
        req.objects=[Object(name='Group',kind='empty',repeat={'count':3,'offset':[1,0,0]}),
                     Object(name='Gear',kind='model',asset='gear.glb',parent='Group')]
        validate_preparation(self.prepared,self.models,'Gear drive',self.root)
        self.prepared.requirements[0].objects[0].scale=(1,2,1)
        validate_preparation(self.prepared,self.models,'Gear drive',self.root)
        self.prepared.requirements[0].objects[0].scale=(-1,2,1)
        with self.assertRaisesRegex(ValueError,'tỷ lệ'):validate_preparation(self.prepared,self.models,'Gear drive',self.root)

    def test_style_and_manual_preferences_do_not_restrict_future_selection(self):
        from codex_blender.planning import signature
        first=studio.Draft(prompt='Gear drive',style='Old clay preset',selected_assets=['sofa.glb'])
        second=studio.Draft(prompt='Gear drive')
        self.assertEqual(signature(first),signature(second))

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

    def test_direct_scene_import_accepts_native_geometry(self):
        scene = SceneSpec(prompt='Gear drive', objects=[{'name': 'Gear', 'kind': 'cylinder'}])
        with patch.object(studio, 'DATA', self.root / 'data'):
            project = studio.create_project(studio.Draft(prompt='Gear drive', scene=scene))
            with patch.object(studio, 'assets_dir', return_value=self.root), \
                 patch.object(studio, 'start_plan') as prepare, patch.object(studio, 'submit', return_value={'id': 'f' * 32}) as submit, \
                 patch.object(studio, 'status', return_value={'state': 'queued'}):
                result = studio.render_project(project['id'], 'preview')
            prepare.assert_not_called()
            submit.assert_called_once()
            self.assertEqual(result['job']['state'], 'queued')


if __name__=='__main__':unittest.main()
