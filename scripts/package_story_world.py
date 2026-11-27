"""Render six reusable examples, capture category sheets and zip the validated library."""
import json
from pathlib import Path
import shutil
import time
import zipfile

from codex_blender.config import ROOT,assets_dir
from codex_blender.models import SceneSpec
from codex_blender.jobs import submit,status

PACK='story-world-v1'
ROOT_ASSETS=assets_dir()
FOLDER=ROOT_ASSETS/'generated'/PACK
RUN=ROOT/'outputs'/PACK


def scenes():
    results=[]
    for template in sorted((FOLDER/'templates').glob('*.json')):
        spec=SceneSpec.model_validate_json(template.read_text(encoding='utf-8'))
        spec.width,spec.height,spec.samples=768,432,12
        job=submit(spec,'preview',ROOT_ASSETS)
        deadline=time.monotonic()+240
        while True:
            result=status(job['id'])
            if result['state']=='completed':break
            if result['state']=='failed' or time.monotonic()>deadline:raise RuntimeError(json.dumps(result))
            time.sleep(.5)
        shutil.copyfile(result['artifacts']['scene.blend'],template.with_suffix('.blend'))
        shutil.copyfile(result['artifacts']['preview.png'],template.with_suffix('.png'))
        results.append({'name':spec.title,'slug':template.stem,'preview':str(template.with_suffix('.png')),'blend':str(template.with_suffix('.blend'))})
        print('SCENE',template.stem,flush=True)
    (RUN/'scenes.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')


def capture():
    from playwright.sync_api import sync_playwright
    data=json.loads((FOLDER/'manifest.json').read_text(encoding='utf-8'))
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1800,'height':1100},device_scale_factor=1)
        page.goto((FOLDER/'catalog.html').as_uri(),wait_until='load')
        page.wait_for_function('Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)')
        page.screenshot(path=str(RUN/'all-assets.png'),full_page=True)
        for group in data['groups']:
            page.locator('#'+group).screenshot(path=str(RUN/(group+'.png')))
        page.goto('http://127.0.0.1:8765/#library',wait_until='networkidle')
        page.locator('#asset-search').fill(PACK)
        page.locator('#asset-filters [data-kind="model"]').click()
        page.wait_for_timeout(700)
        count=page.locator('#library-grid .asset-card').count()
        assert count==102,count
        page.screenshot(path=str(RUN/'studio-library.png'),full_page=True)
        browser.close()
    print('Studio library: 102 model cards verified',flush=True)


def package():
    destination=RUN/'Story-World-102-assets.zip'
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
        for folder in [FOLDER,ROOT_ASSETS/'references'/PACK]:
            for path in sorted(folder.rglob('*')):
                if path.is_file():archive.write(path,path.relative_to(ROOT_ASSETS))
        archive.writestr('START-HERE.txt',
            'Story World: 102 reusable Blender assets based on six supplied art references.\n'
            'Unzip into your Frame Studio assets directory, preserving generated/ and references/.\n'
            'Open generated/story-world-v1/catalog.html to browse by category.\n'
            'Each model: GLB + BLEND + PNG + asset metadata. Native geometry; no image billboards.\n'
            'All assets are static, with separate named meshes. Characters have no skeleton or facial rig.\n'
            'Origin at bottom center; front -Y, Z up, meters. Terrain tiles are 2x2m.\n'
            'templates/ contains six editable example scenes (JSON + BLEND + PNG).\n'
            'This is a stylized interpretation of the references, with simplified detail.\n')
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
    print('ZIP READY',destination,destination.stat().st_size,flush=True)


if __name__=='__main__':
    scenes();capture();package()
