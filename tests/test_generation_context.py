import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from codex_blender.asset_generation import generation_context


class GenerationContextTests(unittest.TestCase):
    def test_large_library_keeps_catalog_and_only_relevant_mesh_details(self):
        models=[{'path':f'character-{i}.glb','name':'Unrelated character',
                 'prepared_assembly':{'objects':['x'*20000]}} for i in range(500)]
        models += [{'path':'core-sphere.glb','name':'Core sphere'},
                   {'path':'food.glb','name':'Thực phẩm tươi và hỏng'}]
        requirement=SimpleNamespace(label='Bộ thực phẩm tươi và hỏng',missing='Tạo thực phẩm')
        def inspect(path,root):
            return {'path':path,'nodes':[{'name':'part','center':[0.123456789,0,0]}],
                    'metadata':{'preview':path+'.png','unneeded':'x'*1000000}}
        with patch('codex_blender.asset_generation.inspect_reference',side_effect=inspect) as read:
            compact,details=generation_context(requirement,models,None)
        self.assertEqual(len(compact),len(models))
        self.assertEqual(details[0]['path'],'food.glb')
        self.assertIn('core-sphere.glb',[d['path'] for d in details])
        self.assertLessEqual(read.call_count,12)
        self.assertLess(len(json.dumps({'models':compact,'details':details})),200000)
        self.assertEqual(details[0]['nodes'][0]['center'][0],0.12346)

    def test_mesh_details_respect_budget(self):
        models=[{'path':f'food-{i}.glb','name':'Food'} for i in range(15)]
        with patch('codex_blender.asset_generation.inspect_reference',
                   side_effect=lambda path,root:dict(path=path,nodes=['x'*100000])):
            compact,details=generation_context(SimpleNamespace(label='food',missing='food'),models,None)
        self.assertEqual(len(compact),15)
        self.assertLessEqual(len(json.dumps(details)),300000)


if __name__=='__main__':
    unittest.main()
