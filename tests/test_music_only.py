from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from codex_blender import audio, studio
from codex_blender.models import SceneSpec
from codex_blender.sounddesign import background_only, prepare_sound


class MusicOnlyTests(unittest.TestCase):
    def scene(self):
        return SceneSpec(duration=2,shots=[{'title':'A','start':0,'end':2,'setting':'Room','actions':['Hold'],
            'objects':[{'name':'Box','kind':'cube'}],
            'narration':[{'start':0,'end':2,'text':'Caption remains','audio':'unavailable-voice.wav'}]}],
            voice_audio='unavailable-upload.wav',music_cues=[{'start':0,'end':2,'style':'triumphant'}],
            effects=[{'start':0,'end':1,'kind':'fly','audio':'unavailable-effect.wav'}])

    def test_music_only_preserves_text_and_removes_all_other_audio(self):
        scene=background_only(self.scene(),'chosen.wav',.3)
        self.assertEqual(scene.music,'chosen.wav')
        self.assertEqual(scene.music_volume,.3)
        self.assertEqual(scene.music_cues,[])
        self.assertEqual(scene.effects,[])
        self.assertIsNone(scene.voice_audio)
        self.assertIsNone(scene.shots[0].narration[0].audio)
        self.assertEqual(scene.shots[0].narration[0].text,'Caption remains')
        self.assertFalse(scene.duck_music)

    def test_preparation_never_invokes_speech_or_builds_effect_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene=background_only(self.scene())
            with patch.object(audio,'synthesize_cues',new_callable=AsyncMock) as cues, \
                 patch.object(audio,'synthesize',new_callable=AsyncMock) as voice, \
                 patch.object(studio,'submit',return_value={'id':'job'}), \
                 patch.object(studio,'read_project',return_value={'jobs':[]}), \
                 patch.object(studio,'save_project') as save:
                studio.prepare_and_render('pid',studio.Draft(voice_mode='tts'),scene,Path(tmp),'video')
                cues.assert_not_called();voice.assert_not_called()
                self.assertEqual(save.call_args.kwargs['state'],'ready')
            self.assertEqual([p.name for p in (Path(tmp)/'audio-generated').iterdir()],['bed-v1-triumphant.wav'])

    def test_encoder_ignores_unavailable_voice_and_effects_and_loops_one_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'music.wav').write_bytes(b'test')
            spec=self.scene().model_dump(mode='json')
            spec.update(audio_mode='music_only',music='music.wav',captions=False)
            # Even stale JSON with extra audio cannot leak it into the final mix.
            with patch.object(audio.subprocess,'run') as run:
                audio.encode_video(root,spec,root)
            cmd=run.call_args.args[0]
            self.assertEqual(cmd.count('-i'),2)
            self.assertEqual(cmd.count('-stream_loop'),1)
            self.assertFalse(any('unavailable' in str(part) for part in cmd))
            graph=cmd[cmd.index('-filter_complex')+1]
            self.assertNotIn('sidechaincompress',graph)
            self.assertIn('atrim=duration=2.0',graph)
