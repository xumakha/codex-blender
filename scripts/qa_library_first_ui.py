"""Read-only browser checks; project inventory is injected in browser responses, never saved."""
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
    fixture=json.loads((run/'data'/'projects'/pid/'asset-preparation.json').read_text(encoding='utf-8'))
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True,args=['--disable-gpu'])
        page=await browser.new_page(viewport={'width':1500,'height':1100});errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        async def inventory_response(route):
            response=await route.fetch();value=await response.json()
            if 'draft' in value:value['asset_preparation']=fixture
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
        await page.locator('#prompt').fill('Changed prompt for browser check only')
        assert not await page.locator('#asset-preparation-panel').is_visible()
        assert not errors,errors
        await browser.close()
        result={'passed':True,'style_tab_removed':True,'tabs_work':True,'prepared_inventory_visible':True,
                'stale_inventory_hidden_on_edit':True,'page_errors':errors}
        (run/'browser-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))

if __name__=='__main__':asyncio.run(main())
