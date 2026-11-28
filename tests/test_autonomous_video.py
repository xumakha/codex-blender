from collections import Counter
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from codex_blender import director, studio
from codex_blender.config import ROOT, validate_glb
from codex_blender.mesh_program import build_mesh
from codex_blender.models import ShotDesign, VideoPlan


MESH = """vertices = [(cos(i*tau/12), sin(i*tau/12), 0) for i in range(12)]
faces = [[i for i in range(12)]]
"""


def brief(index):
    return {
        'title': f'Ring {index}', 'start': index - 1, 'end': index,
        'setting': 'Studio', 'actions': [], 'animate': False,
        'elements': [{'id': 'ring', 'label': 'Ring', 'role': 'prop', 'source': 'Green ring',
                      'appearance': 'Green custom ring'}],
    }


def mesh_design(color='#226644', program=MESH):
    return ShotDesign(objects=[{'name': 'ring', 'kind': 'mesh', 'color': color,
                                'mesh': {'program': program, 'solidify': .06}}],
                      element_bindings=[{'element_id': 'ring', 'objects': ['ring']}])


class AutonomousVideoTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'outputs').mkdir(exist_ok=True)
        work = Path(self.enterContext(tempfile.TemporaryDirectory(dir=ROOT / 'outputs')))
        self.root = work / 'assets'
        self.root.mkdir()
        self.enterContext(patch.object(studio, 'DATA', work / 'data'))
        self.enterContext(patch.object(director, 'blender_command', return_value=['blender']))
        self.enterContext(patch('codex_blender.fonts.ensure_font', side_effect=ValueError('No font')))

    def build(self, planner, reviewer=None, **settings):
        draft = studio.Draft(prompt='Green ring', **settings)
        pid = studio.create_project(draft)['id']
        report = ({'visible_times': {'ring': [0]}, 'images': []}, [])
        with patch.object(director, 'call_planner', side_effect=planner), \
             patch.object(director, 'render_shot_review', side_effect=reviewer, return_value=report):
            studio.plan_scene(pid, draft, self.root)
        return pid, draft, studio.read_project(pid)

    def test_empty_library_and_missing_reference_with_all_modes(self):
        for mode in ('auto', 'library_first', 'full_ai'):
            with self.subTest(mode=mode):
                def planner(pid, draft, root, model, task, prompt, stage, validate=None, **options):
                    if stage == 'screenplay':
                        self.assertNotIn('assets', task)
                        self.assertEqual(options['images'], [])
                        value = VideoPlan(title='Ring', duration=1, style='3D', shots=[brief(1)])
                        validate(value)
                        return value
                    if stage == 'shot-01':
                        self.assertEqual(task['assets'], [])
                        self.assertEqual(task['asset_generation_mode'], mode)
                        return mesh_design()
                    return director.PreviewReview(issues=[], warnings=[])

                _, _, result = self.build(planner, asset_generation_mode=mode, references=['missing.png'])
                self.assertEqual(result['state'], 'ready', result.get('error'))
                self.assertIsNone(result['asset_preparation'])
                self.assertEqual(result['generation']['generated'], 1)
                self.assertTrue(any('missing.png' in entry for entry in result['generation_warnings']))

    def test_mixed_native_and_unregistered_import_ignores_prepared_path(self):
        document = json.dumps({'meshes': [{}]}).encode('ascii')
        (self.root / 'unregistered.glb').write_bytes(
            struct.pack('<4sIII4s', b'glTF', 2, 20 + len(document), len(document), b'JSON') + document)
        value = VideoPlan(title='Ring', duration=1, style='3D', shots=[brief(1)])
        value.shots[0].elements[0].asset_paths = ['removed.glb']
        design = mesh_design()
        data = design.model_dump()
        data['objects'].append({'name': 'stand', 'kind': 'model', 'asset': 'unregistered.glb'})
        data['element_bindings'][0]['objects'].append('stand')
        design = ShotDesign.model_validate(data)
        director.validate_shot(value.shots[0], design, self.root, 'auto')
        with self.assertRaisesRegex(ValueError, 'Full AI'):
            director.validate_shot(value.shots[0], design, self.root, 'full_ai')

        def planner(pid, draft, root, model, task, prompt, stage, validate=None, **options):
            if stage == 'screenplay':
                validate(value)
                return value
            if stage == 'shot-01':
                self.assertEqual(task['asset_generation_mode'], 'library_first')
                return design
            return director.PreviewReview(issues=[], warnings=[])

        _, _, result = self.build(planner, asset_generation_mode='library_first')
        self.assertEqual(result['state'], 'ready', result.get('error'))
        self.assertEqual((result['generation']['reused'], result['generation']['generated']), (1, 1))

    def test_external_model_resources_are_rejected(self):
        document = json.dumps({'meshes': [{}], 'images': [{'uri': '../other.png'}]}).encode('ascii')
        path = self.root / 'external-resource.glb'
        path.write_bytes(struct.pack('<4sIII4s', b'glTF', 2, 20 + len(document), len(document), b'JSON') + document)
        with self.assertRaisesRegex(ValueError, 'embed all'):
            validate_glb(path)

    def test_unsuitable_library_suggestion_can_be_ignored(self):
        document = json.dumps({'meshes': [{}]}).encode('ascii')
        (self.root / 'sofa.glb').write_bytes(
            struct.pack('<4sIII4s', b'glTF', 2, 20 + len(document), len(document), b'JSON') + document)

        def planner(pid, draft, root, model, task, prompt, stage, validate=None, **options):
            if stage == 'screenplay':
                value = VideoPlan(title='Ring', duration=1, style='3D', shots=[brief(1)])
                validate(value)
                return value
            if stage == 'shot-01':
                self.assertIn('sofa.glb', {item['path'] for item in task['assets']})
                return mesh_design()
            return director.PreviewReview(issues=[], warnings=[])

        _, _, result = self.build(planner)
        self.assertEqual(result['state'], 'ready', result.get('error'))
        self.assertEqual((result['generation']['reused'], result['generation']['generated']), (0, 1))

    def test_legacy_draft_exposes_hybrid_defaults_to_the_ui(self):
        pid = studio.create_project(studio.Draft())['id']
        studio.save_project(pid, draft={'prompt': 'Green ring'})
        draft = studio.read_project(pid)['draft']
        self.assertEqual(draft['asset_generation_mode'], 'auto')
        self.assertTrue(draft['cache_reusable_assets'])
        self.assertTrue(draft['auto_repair'])
        self.assertEqual(draft['max_repair_attempts'], 3)

    def test_render_error_and_empty_camera_resume_only_failed_shot(self):
        designs = Counter()
        blocked = True
        seen_feedback = []

        def planner(pid, draft, root, model, task, prompt, stage, validate=None, **options):
            if stage == 'screenplay':
                result = VideoPlan(title='Ring', duration=3, style='3D', shots=[brief(i) for i in (1, 2, 3)])
                validate(result)
                return result
            if stage.endswith('-review'):
                issues = ['The grip is partly hidden'] if stage == 'shot-03-review' else []
                return director.PreviewReview(issues=issues, warnings=[])
            designs[stage] += 1
            if stage == 'shot-03':
                seen_feedback.append(task['repair_feedback'].get('error', ''))
            return mesh_design(f'#{designs[stage]:06x}')

        def render(folder, assets, plan, shot, design, samples):
            if shot.title == 'Ring 3' and designs['shot-03'] == 1:
                raise ValueError('Blender rejected degenerate mesh')
            if shot.title == 'Ring 3' and designs['shot-03'] == 2:
                return {'visible_times': {'ring': []}, 'images': []}, []
            if shot.title == 'Ring 3' and blocked and designs['shot-03'] == 3:
                raise director.BlenderUnavailable('Disk full')
            return {'visible_times': {'ring': [0]}, 'images': []}, []

        pid, draft, failed = self.build(planner, render)
        self.assertEqual(failed['state'], 'error')
        self.assertEqual(failed['generation']['severity'], 'critical')
        self.assertEqual(designs, {'shot-01': 1, 'shot-02': 1, 'shot-03': 3})
        self.assertIn('degenerate mesh', seen_feedback[1])
        self.assertIn('Camera không thấy vật thể nào', seen_feedback[2])
        blocked = False
        with patch.object(director, 'call_planner', side_effect=planner), \
             patch.object(director, 'render_shot_review', side_effect=render), \
             patch.object(studio, 'POOL') as queue, patch.object(studio, 'assets_dir', return_value=self.root):
            studio.retry_render(pid)
            callback, *args = queue.submit.call_args.args
            callback(*args)
        resumed = studio.read_project(pid)
        self.assertEqual(resumed['state'], 'ready', resumed.get('error'))
        self.assertEqual(designs, {'shot-01': 1, 'shot-02': 1, 'shot-03': 4})
        self.assertEqual(len(resumed['draft']['scene']['shots']), 3)
        self.assertIn('The grip is partly hidden', resumed['generation_warnings'])

    def test_mesh_program_is_bounded_and_has_no_file_or_module_access(self):
        vertices, faces = build_mesh(MESH)
        self.assertEqual(len(vertices), 12)
        self.assertEqual(tuple(faces[0]), tuple(range(12)))
        for program in ('import os', 'x = open(0)', 'x = pi.__class__', 'x = [i for i in range(10000000)]'):
            with self.subTest(program=program), self.assertRaises(ValueError):
                build_mesh(program)
        with patch.dict('os.environ', {'CODEX_BLENDER_MESH_BUDGET': '8'}), self.assertRaisesRegex(ValueError, 'budget'):
            build_mesh(MESH)
