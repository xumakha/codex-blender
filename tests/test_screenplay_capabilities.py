import copy
from pathlib import Path
import tempfile
import unittest
import wave
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from codex_blender import audio, fonts, studio
from codex_blender.models import SceneSpec, ShotBrief, ShotDesign, VideoPlan, Rig
from codex_blender.planning import check_animation, check_contract, check_elements, check_inventory
from codex_blender.sounddesign import prepare_sound, write_sound


def skeleton():
    return {'name':'Skeleton', 'root':'Hero', 'bones':[
        {'name':'Arm', 'head':[0,0,1], 'tail':[0,0,2], 'objects':['Hand'],
         'keyframes':[{'time':1, 'rotation':[0,0,45]}]},
    ]}


def geometry():
    return [{'name':'Hero', 'kind':'empty', 'location':[0,0,0]},
            {'name':'Hand', 'kind':'cube', 'parent':'Hero', 'location':[0,0,2]}]


class ScreenplayCapabilitiesTests(unittest.TestCase):
    def test_global_reuse_instruction_applies_to_individual_props(self):
        plan=VideoPlan(title='Reuse',duration=2,style='3D',shots=[{
            'title':'Room','start':0,'end':2,'setting':'Room','actions':['Move table'],
            'elements':[{'id':'table','label':'Table','source':'Bàn gỗ','role':'prop',
                         'appearance':'Wooden table','construction':'asset'}]}])
        check_inventory(plan,'Bàn gỗ.\nƯu tiên sử dụng lại các assets đã có trong thư viện.')
        for instruction in ['Sử dụng ảnh asset reference để tham khảo phong cách.',
                            'Không sử dụng lại các assets đã có trong thư viện.']:
            with self.subTest(instruction=instruction), self.assertRaisesRegex(ValueError,'prompt không yêu cầu'):
                check_inventory(plan,'Bàn gỗ.\n'+instruction)

    def test_legacy_music_only_scene_does_not_call_voice_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene=SceneSpec(duration=2,objects=geometry(),music_cues=[{'start':0,'end':2,'style':'playful'}])
            draft=studio.Draft(scene=scene,voice_mode='none')
            with patch.object(audio,'synthesize',new_callable=AsyncMock) as voice, \
                 patch.object(studio,'submit',return_value={'id':'job'}) as submit, \
                 patch.object(studio,'read_project',return_value={'jobs':[]}), \
                 patch.object(studio,'save_project') as save:
                studio.prepare_and_render('project',draft,scene,Path(tmp),'video')
                voice.assert_not_called()
                submit.assert_called_once()
                self.assertEqual(save.call_args.kwargs['state'],'ready')

    def test_legacy_duration_change_retimes_pose_keys(self):
        scene=SceneSpec(duration=2,objects=geometry(),rigs=[skeleton()])
        result=studio.scene_for_render(studio.Draft(scene=scene,duration=4))
        self.assertEqual(result.rigs[0].bones[0].keyframes[0].time,2)

    def test_warning_does_not_disable_hard_unsupported_checks(self):
        raw={'title':'Warning','duration':2,'style':'3D', 'warnings':['Speech will be measured at the audio stage'],
             'shots':[{'title':'A','start':0,'end':2,'setting':'Room','actions':['Wave hand']}]}
        check_contract(VideoPlan(**raw), {'duration':2,'intervals':[],'speech':[]})
        with self.assertRaisesRegex(ValueError,'Unsupported renderer operation'):
            check_contract(VideoPlan(**raw,unsupported=['Unsupported renderer operation']),
                           {'duration':2,'intervals':[],'speech':[]})

    def test_requested_skeleton_cannot_be_replaced_by_empty_pivots(self):
        brief=ShotBrief(title='Wave',start=0,end=2,setting='Studio',actions=['Wave hand'],
            elements=[{'id':'hero','label':'Hero','source':'Hero','role':'character',
                       'appearance':'Orange blocks','rigged':True}])
        design=ShotDesign(objects=geometry(),bindings=[{'action_index':0,'objects':['Hand'],
            'elements':['hero'],'start':0,'end':2}],element_bindings=[{'element_id':'hero','objects':['Hero']}])
        with self.assertRaisesRegex(ValueError,'rig xương'):
            check_elements(brief,design)
        design.rigs=[Rig(**skeleton())]
        check_elements(brief,design)

    def test_bone_animation_fulfills_action_without_dummy_object_motion(self):
        design=ShotDesign(objects=geometry(), rigs=[skeleton()],
            bindings=[{'action_index':0,'objects':['Hand'],'start':0,'end':2}])
        SceneSpec(duration=2, objects=design.objects, rigs=design.rigs)
        brief=ShotBrief(title='Wave',start=0,end=2,setting='Studio',actions=['Wave hand'])
        check_animation(brief,design)
        design.rigs[0].bones[0].keyframes=[]
        with self.assertRaisesRegex(ValueError,'chuyển động'):
            check_animation(brief,design)

    def test_invalid_rigs_are_rejected_before_blender(self):
        variants=[]
        for key,value in [('parent','Arm'),('parent','missing'),('tail',[0,0,1]),
                          ('objects',['Hero']),('objects',['missing']),
                          ('keyframes',[{'time':3,'rotation':[0,0,45]}])]:
            rig=skeleton();rig['bones'][0][key]=value;variants.append(rig)
        rig=skeleton();bone=copy.deepcopy(rig['bones'][0]);bone['name']='Other';rig['bones'].append(bone)
        variants.append(rig)
        for rig in variants:
            with self.subTest(rig=rig), self.assertRaises(ValidationError):
                SceneSpec(duration=2,objects=geometry(),rigs=[rig])

    def test_music_segments_cannot_overlap_or_exceed_video(self):
        for intervals in [[(0,2),(1,3)],[(0,4)],[(2,1)]]:
            with self.subTest(intervals=intervals), self.assertRaises(ValidationError):
                SceneSpec(duration=3,objects=geometry(),music_cues=[
                    {'start':a,'end':b,'style':'playful'} for a,b in intervals])

    def test_nature_effects_are_distinct_non_silent_wavs(self):
        with tempfile.TemporaryDirectory() as tmp:
            values=[]
            for kind in ('bird','fly','water_drop'):
                path=Path(tmp)/(kind+'.wav')
                write_sound(path,kind,1)
                with wave.open(str(path)) as wav:
                    self.assertEqual(wav.getnframes(),24000)
                    self.assertEqual(wav.getnchannels(),1)
                    pcm=wav.readframes(wav.getnframes())
                    self.assertTrue(any(pcm))
                    values.append(pcm)
            self.assertEqual(len(set(values)),3)

    def test_music_changes_prepare_separate_reusable_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            scene=SceneSpec(duration=3,objects=geometry(),music_style='ambient',music_cues=[
                {'start':0,'end':2,'style':'playful'}, {'start':2,'end':3,'style':'triumphant'}])
            prepare_sound(scene,root)
            self.assertIsNone(scene.music)
            self.assertEqual([Path(cue.audio).name for cue in scene.music_cues],
                             ['bed-v1-playful.wav','bed-v1-triumphant.wav'])
            self.assertTrue(all((root/cue.audio).is_file() for cue in scene.music_cues))

    def test_bad_font_is_not_claimed_to_support_vietnamese(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'fake.ttf').write_bytes(b'not a font')
            self.assertFalse(fonts.supports_vietnamese(root/'fake.ttf'))
            with self.assertRaisesRegex(ValueError,'Font'):
                fonts.ensure_font(root,'fake.ttf')

    def test_installed_font_fallback_is_valid_and_reused(self):
        if not fonts.supports_vietnamese('C:/Windows/Fonts/arial.ttf'):
            self.skipTest('No Windows Arial fixture installed')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=fonts.ensure_font(root)
            self.assertTrue(fonts.supports_vietnamese(root/path))
            self.assertEqual(fonts.ensure_font(root),path)
