"""Recompile an existing screenplay without starting renders or changing its draft."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

from codex_blender import audio, director, fonts, studio
from codex_blender.config import assets_dir, asset_path
from codex_blender.library import catalog
from codex_blender.models import VideoPlan
from codex_blender.planning import check_contract, check_inventory, normalize_inventory, prompt_contract, signature


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('project_id')
    parser.add_argument('--result',type=Path,help='Validate a saved real planner result without another AI request')
    args=parser.parse_args()
    project=studio.read_project(args.project_id)
    draft=studio.Draft.model_validate(project['draft'])
    root=assets_dir();font=fonts.ensure_font(root,draft.font)
    voices=[voice for voice in audio.voice_options() if not voice.get('disabled')]
    assets=catalog(root);preferred=set(draft.selected_assets)
    assets.sort(key=lambda item:item['path'] not in preferred)
    contract=prompt_contract(draft.prompt)
    task={'prompt':draft.prompt,'style_default':draft.style,'default_font':font,
        'output_defaults':{'fps':draft.fps,'width':draft.width,'height':draft.height},
        'voices':voices,'preferred_voice_id':draft.voice_id,'preferred_voice_rate':draft.rate,
        'preferred_assets':draft.selected_assets,'required_timeline':contract,
        'assets':[{key:item[key] for key in ('path','kind','name','description')} for item in assets[:200]]}
    def validate(plan):
        normalize_inventory(plan)
        check_contract(plan,contract)
        check_inventory(plan,draft.prompt)
        assert plan.font and fonts.supports_vietnamese(asset_path(plan.font,root))
        assert plan.export_assets
        assert {'bird','fly','water_drop'} <= {effect.kind for effect in plan.effects}
        assert {'playful','triumphant'} <= {cue.style for cue in plan.music_cues}
        assert all(cue.voice_id in {voice['id'] for voice in voices}
                   for shot in plan.shots for cue in shot.narration)
    if args.result:
        plan=VideoPlan.model_validate_json(args.result.read_text(encoding='utf-8'))
        validate(plan)
    else:
        plan=director.call_planner(args.project_id,draft,root,VideoPlan,task,director.BRIEF,
                                  'capabilities-screenplay',validate)
    out=Path('outputs/screenplay-recovery');out.mkdir(exist_ok=True)
    (out/'plan.json').write_text(plan.model_dump_json(indent=2),encoding='utf-8')
    (out/'source-signature.txt').write_text(signature(draft),encoding='ascii')
    print(json.dumps({'ok':True,'duration':plan.duration,'shots':len(plan.shots),'font':plan.font,
        'effects':[effect.kind for effect in plan.effects],'music_cues':len(plan.music_cues),
        'export_assets':plan.export_assets,'unsupported':plan.unsupported,'warnings':plan.warnings},ensure_ascii=True))


if __name__=='__main__':main()
