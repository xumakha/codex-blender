"""Check the installed Studio library and decode every new thumbnail in Chrome."""
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from codex_blender.config import ROOT,assets_dir
from playwright.async_api import async_playwright

PACK='universal-expansion-v2'

async def main():
    folder=assets_dir()/'generated'/PACK;run=ROOT/'outputs'/PACK;run.mkdir(parents=True,exist_ok=True)
    expected=len(json.loads((folder/'manifest.json').read_text(encoding='utf-8'))['assets'])
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True,args=['--disable-gpu'])
        page=await browser.new_page(viewport={'width':1600,'height':1050});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        await page.goto('http://127.0.0.1:8765/#library',wait_until='networkidle')
        await page.locator('#asset-search').fill(PACK)
        await page.locator('#asset-filters [data-kind="model"]').click()
        cards=page.locator('#library-grid .asset-card');await cards.first.wait_for()
        assert await cards.count()==expected,(await cards.count(),expected)
        images=await page.locator('#library-grid img').evaluate_all('els => Promise.all(els.map(async e => {e.loading="eager";try{await e.decode();return e.naturalWidth>0}catch{return false}}))')
        assert len(images)==expected and all(images)
        await page.screenshot(path=str(run/'studio-library.png'))
        await page.goto((folder/'catalog.html').as_uri(),wait_until='load')
        await page.locator('article img').evaluate_all('els => Promise.all(els.map(e => e.decode()))')
        for name in ('expressions','mechanisms','architecture','examples'):
            await page.locator('#'+name).screenshot(path=str(run/(name+'-catalog.png')))
        assert not errors,errors
        (run/'browser-validation.json').write_text(json.dumps({'passed':True,'studio_cards':expected,'decoded_thumbnails':len(images),'page_errors':errors},indent=2),encoding='utf-8')
        print('BROWSER PASS',expected,'cards and thumbnails')
        await browser.close()

if __name__=='__main__':asyncio.run(main())
