"""Check generation settings and progress in Studio without editing a saved project."""
import asyncio
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codex_blender.config import ROOT
from playwright.async_api import async_playwright

async def main():
    run=ROOT/'outputs'/'library-first-smoke'
    pid=(run/'project-id.txt').read_text().strip()
    fixture=json.loads((run/'data'/'projects'/pid/'project.json').read_text(encoding='utf-8'))['generation']
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True,args=['--disable-gpu'])
        page=await browser.new_page(viewport={'width':1500,'height':1100}, permissions=['clipboard-read','clipboard-write']);errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        async def inventory_response(route):
            response=await route.fetch();value=await response.json()
            if 'draft' in value:value['generation']=fixture
            await route.fulfill(response=response,json=value)
        await page.route('**/api/projects/*',inventory_response)
        await page.goto('http://127.0.0.1:8765/',wait_until='networkidle')
        assert await page.locator('[data-tab="art"]').count()==0
        assert await page.locator('#style').count()==0
        assert await page.locator('#library-policy').is_visible()
        for tab in ('audio','output','script'):
            await page.locator(f'[data-tab="{tab}"]').click()
            assert await page.locator('#tab-'+tab).is_visible(),tab
        assert await page.locator('#asset-preparation-panel').is_visible()
        await page.locator('#asset-preparation-panel summary').click()
        assert await page.locator('#prepared-assets').is_visible()
        await page.screenshot(path=str(run/'studio-assets-panel.png'))
        await page.locator('#asset-generation-settings summary').click()
        mode=page.locator('#asset-generation-mode')
        assert await mode.locator('option').count() == 3
        await mode.select_option('full_ai')
        assert 'Tự dựng toàn bộ' in await page.locator('#asset-mode-description').inner_text()
        await page.locator('#auto-repair').uncheck()
        assert await page.locator('#max-repair-attempts').is_disabled()
        await page.locator('#auto-repair').check()
        await page.locator('#max-repair-attempts').fill('2')
        await page.locator('#copy-generation-config').click()
        payload=json.loads(await page.evaluate('navigator.clipboard.readText()'))
        assert payload['asset_generation_mode'] == 'full_ai' and payload['max_repair_attempts'] == 2
        assert payload['allow_custom_geometry'] and not payload['require_registered_assets'] and not payload['require_reference_images']
        await page.locator('#asset-generation-settings').screenshot(path=str(run/'generation-settings.png'))
        await page.locator('#prompt').fill('Changed prompt for browser check only')
        assert not await page.locator('#asset-preparation-panel').is_visible()
        assert not errors,errors
        await browser.close()
        result={'passed':True,'tabs_work':True,'generation_progress_visible':True,
                'stale_progress_hidden_on_edit':True,'page_errors':errors}
        (run/'browser-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))

if __name__=='__main__':asyncio.run(main())
