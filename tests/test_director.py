import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from codex_blender.models import SceneSpec, VideoPlan, Shot, ShotBrief, ShotDesign
from codex_blender.planning import prompt_contract, check_contract, check_animation, signature
from codex_blender import audio, studio, config


def shot(start=0, end=5, **extra):
    return Shot(title='Moving box',start=start,end=end,setting='A room',actions=['Move left to right'],
        objects=[{'name':'box','kind':'cube','keyframes':[{'time':end-start,'location':[3,0,1]}]}],
        bindings=[{'action_index':0,'objects':['box'],'start':0,'end':end-start}],**extra)


class DirectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config.OUTPUTS.mkdir(exist_ok=True)

    def test_script_contract_keeps_all_scenes_and_exact_speech(self):
        prompt='Thời lượng: 90–120 giây\n00:00–00:10\n**Lời đọc:**\n“Xin chào!”\n00:10–01:35'
        contract=prompt_contract(prompt)
        self.assertEqual(contract['duration'],95)
        self.assertEqual(contract['duration_range'],(90,120))
        self.assertEqual(contract['speech'],['Xin chào!'])
        plan=VideoPlan(title='Full story',duration=95,style='3D',shots=[shot(0,10,narration=[{'start':0,'end':2,'text':'Xin chào!'}]),shot(10,95)])
        check_contract(plan,contract)
        with self.assertRaises(ValueError):check_contract(plan,{'duration':120,'intervals':[],'speech':[]})
        with self.assertRaises(ValueError):check_contract(plan,{'duration':95,'intervals':[],'speech':['Dropped dialogue']})

    def test_duration_ranges_without_scene_timestamps_are_enforced(self):
        for text in ('**Thời lượng:** 90–120 giây.', 'Duration: 90-120 seconds.',
                     'Thời lượng: 90 — 120 giây.', 'Video dài 90 đến 120 giây.',
                     'Thời lượng: 1,5–2 phút.', 'Duration: 1.5 minutes to 2 minutes.'):
            with self.subTest(prompt=text):
                contract=prompt_contract(text)
                self.assertIsNone(contract['duration'])
                self.assertEqual(contract['duration_range'],(90,120))
                for seconds in (90,95,120):
                    check_contract(VideoPlan(title='Full',duration=seconds,style='3D',shots=[shot(0,seconds)]),contract)
                for seconds in (5,89,121):
                    with self.assertRaises(ValueError):
                        check_contract(VideoPlan(title='Wrong duration',duration=seconds,style='3D',shots=[shot(0,seconds)]),contract)

    def test_exact_duration_still_works_and_conflicting_timeline_fails(self):
        for text in ('**Thời lượng:** 95 giây.', 'Duration: 95 seconds.'):
            self.assertEqual(prompt_contract(text)['duration'],95)
        contract=prompt_contract('Thời lượng: 90–120 giây.\n00:00–00:05')
        with self.assertRaises(ValueError):
            check_contract(VideoPlan(title='Too short',duration=5,style='3D',shots=[shot()]),contract)

    def test_full_duration_cannot_be_filled_by_stretching_one_opening_shot(self):
        contract=prompt_contract('Thời lượng: 90–120 giây.\n00:00–00:10\n00:10–01:35')
        with self.assertRaises(ValueError):
            check_contract(VideoPlan(title='Stretched opening',duration=95,style='3D',shots=[shot(0,95)]),contract)

    def test_quoted_dialogue_keeps_its_order(self):
        contract=prompt_contract('Lời đọc: “First.”\nLời đọc: “Second.”')
        plan=VideoPlan(title='Reversed speech',duration=5,style='3D',shots=[shot(narration=[
            {'start':0,'end':2,'text':'Second.'},{'start':2,'end':5,'text':'First.'}])])
        with self.assertRaises(ValueError):check_contract(plan,contract)

    def test_project_reports_requested_timing_instead_of_stale_preview(self):
        with tempfile.TemporaryDirectory(dir=config.ROOT/'outputs') as tmp,patch.object(studio,'DATA',Path(tmp)):
            draft=studio.Draft(prompt='Thời lượng: 90–120 giây.\n00:00–00:10\n00:10–01:35',
                scene=SceneSpec(duration=5,objects=[{'name':'box','kind':'cube'}]))
            project=studio.create_project(draft)
            result=studio.read_project(project['id'])
            self.assertFalse(result['scene_current'])
            self.assertEqual(result['prompt_timing']['duration'],95)
            self.assertEqual(result['prompt_timing']['duration_range'],(90,120))

    def test_no_camera_zoom_substitute_for_actions(self):
        brief=ShotBrief(title='Walk',start=0,end=5,setting='Room',actions=['Walk across room'])
        design=ShotDesign(camera={'end_location':[1,-3,2]},objects=[{'name':'person','kind':'cube'}],bindings=[{'action_index':0,'objects':['person'],'start':0,'end':5}])
        with self.assertRaises(ValueError):check_animation(brief,design)
        design.objects[0].keyframes=shot().objects[0].keyframes
        check_animation(brief,design)

    def test_explicit_dialogue_windows_are_enforced(self):
        contract=prompt_contract('Lời đọc: “Xin chào.” đọc từ 0.5 đến 2.5 giây.')
        self.assertEqual(contract['speech_windows'],[('Xin chào.',.5,2.5)])
        plan=VideoPlan(title='Voice',duration=5,style='3D',shots=[shot(narration=[{'start':1,'end':3,'text':'Xin chào.'}])])
        with self.assertRaises(ValueError):check_contract(plan,contract)

    def test_reject_gaps_out_of_shot_keys_and_parent_cycles(self):
        with self.assertRaises(ValidationError):SceneSpec(duration=12,shots=[shot(0,5),shot(6,12)])
        raw=shot().model_dump()
        raw['objects'][0]['keyframes'][0]['time']=6
        with self.assertRaises(ValidationError):SceneSpec(duration=5,shots=[raw])
        raw=shot().model_dump();raw['objects'][0]['parent']='box'
        with self.assertRaises(ValidationError):SceneSpec(duration=5,shots=[raw])

    def test_compiled_timing_is_not_overridden_by_draft_defaults(self):
        scene=SceneSpec(duration=12,fps=30,width=720,height=1280,shots=[shot(0,6),shot(6,12)])
        result=studio.scene_for_render(studio.Draft(scene=scene,duration=5,fps=24))
        self.assertEqual((result.duration,result.fps,result.width),(12,30,720))
        self.assertEqual(result.shots[1].start,6)

    def test_changed_prompt_replans_instead_of_exporting_stale_scene(self):
        with tempfile.TemporaryDirectory(dir=config.ROOT/'outputs') as tmp,patch.object(studio,'DATA',Path(tmp)):
            scene=SceneSpec(prompt='A moving box',objects=[{'name':'box','kind':'cube'}])
            draft=studio.Draft(prompt=scene.prompt,scene=scene)
            p=studio.create_project(draft)
            saved=p['draft'];saved['prompt']='Two rooms with narration'
            studio.save_project(p['id'],draft=saved)
            with patch.object(studio,'start_plan',return_value={'state':'planning'}) as plan,patch.object(studio,'submit') as submit:
                studio.render_project(p['id'],'video')
            plan.assert_called_once_with(p['id'],auto_render=True,render_mode='video')
            submit.assert_not_called()

    def test_timed_audio_inputs_and_captions_preserve_cue_offsets(self):
        with tempfile.TemporaryDirectory(dir=config.ROOT/'outputs') as tmp:
            root=Path(tmp);(root/'voice.wav').write_bytes(b'voice');(root/'font.ttf').write_bytes(b'font')
            spec=SceneSpec(duration=10,font='font.ttf',captions=True,shots=[shot(0,5,narration=[{'start':1,'end':3,'text':'First line','audio':'voice.wav'}]),shot(5,10,narration=[{'start':6,'end':8,'text':'Second line','audio':'voice.wav'}])])
            with patch.object(audio.subprocess,'run') as run,patch.object(audio.imageio_ffmpeg,'get_ffmpeg_exe',return_value='ffmpeg'),patch('codex_blender.captions.font_family',return_value='Arial'):
                audio.encode_video(root,spec.model_dump(mode='json'),root)
            cmd=run.call_args.args[0];graph=cmd[cmd.index('-filter_complex')+1]
            self.assertIn('adelay=1000:all=1',graph)
            self.assertIn('adelay=6000:all=1',graph)
            self.assertIn('captions.ass',cmd[cmd.index('-vf')+1])
            timing=json.loads((root/'caption-timing.json').read_text())
            self.assertTrue(timing['estimated'])
            words=timing['words']
            self.assertEqual([w['text'] for w in words],['First','line','Second','line'])
            self.assertEqual(words[0]['start'],1)
            self.assertEqual(words[2]['start'],6)
            self.assertLessEqual(words[-1]['end'],8)
            self.assertIn('\\fscy112',(root/'captions.ass').read_text())

    def test_speech_never_silently_cuts_a_long_paragraph(self):
        with patch.object(audio,'audio_duration',return_value=20),patch.object(audio.subprocess,'run') as run:
            with self.assertRaises(ValueError):audio.fit_speech('voice.mp3','result.wav',5)
            run.assert_not_called()
