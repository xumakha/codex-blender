"""Browser persistence check with isolated preference/project responses; never alters user projects."""
import asyncio
import copy
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codex_blender.config import ROOT
from playwright.async_api import async_playwright

async def main():
    saved={'video':{},'ui':{}};project=None;errors=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True,args=['--disable-gpu'])
        page=await browser.new_page(viewport={'width':1440,'height':1000})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('dialog',lambda d:asyncio.create_task(d.accept()))
        async def preferences(route):
            if route.request.method=='POST':
                for key,value in route.request.post_data_json.items():saved[key].update(value)
            await route.fulfill(json=saved)
        async def projects(route):
            nonlocal project
            request=route.request
            if request.method=='GET' and request.url.endswith('/api/projects'):
                await route.fulfill(json=[{'id':'f'*32,'title':'Preference QA','state':'idle','updated':'','has_scene':False}]);return
            if request.method=='POST':
                from codex_blender.studio import Draft
                project={'id':'f'*32,'draft':Draft(**saved['video']).model_dump(mode='json'),'state':'idle','jobs':[],'scene_current':False}
            elif request.method=='PUT':project['draft']=request.post_data_json
            elif project is None:
                from codex_blender.studio import Draft
                project={'id':'f'*32,'draft':Draft().model_dump(mode='json'),'state':'idle','jobs':[],'scene_current':False}
            await route.fulfill(json=project)
        await page.route('**/api/preferences',preferences)
        await page.route('**/api/projects',projects)
        await page.route('**/api/projects/*',projects)
        await page.goto('http://127.0.0.1:8765/',wait_until='networkidle')
        await page.locator('[data-tab="output"]').click()
        await page.locator('#fps').select_option('30')
        await page.locator('#aspect').select_option('16:9')
        await page.locator('#resolution').select_option('full')
        await page.locator('[data-tab="audio"]').click()
        await page.locator('#music-volume').fill('0.42')
        fonts=await page.locator('#font option').evaluate_all('els=>els.map(e=>e.value).filter(Boolean)')
        assert fonts
        await page.locator('[data-tab="output"]').click()
        await page.locator('#font').select_option(fonts[0])
        await page.wait_for_timeout(700)
        assert saved['video']['fps']==30 and saved['video']['width']==1920
        assert saved['video']['music_volume']==.42 and saved['video']['font']==fonts[0]
        await page.reload(wait_until='networkidle')
        assert await page.locator('#fps').input_value()=='30'
        assert await page.locator('#resolution').input_value()=='full'
        assert await page.locator('#font').input_value()==fonts[0]
        assert float(await page.locator('#music-volume').input_value())==.42
        await page.locator('#new-project').click();await page.wait_for_timeout(300)
        assert await page.locator('#fps').input_value()=='30'
        assert await page.locator('#font').input_value()==fonts[0]
        assert not errors,errors
        result={'passed':True,'reload':True,'new_project':True,'font':True,'audio_volume':True,'resolution':True,'page_errors':errors}
        (ROOT/'outputs'/'preferences-browser-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result));await browser.close()

if __name__=='__main__':asyncio.run(main())
