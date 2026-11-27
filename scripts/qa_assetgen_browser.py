"""Browser QA using simulated job responses; no Codex requests or project saves."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    reference=Path('outputs/assetgen-smoke/assets/reference.png').resolve()
    out=Path('outputs/assetgen-browser-qa')
    out.mkdir(exist_ok=True)
    errors=[]
    job={'id':'b'*32,'name':'QA model','state':'planning','stage':'planning','error':None,
         'updated':'2026-11-27T00:00:00Z','references':['qa-reference.png'],'prompt':'QA','result':None}
    model={'path':'generated/qa-model.glb','name':'QA model','kind':'model','bytes':1000,'source':'blender',
           'description':'Browser QA fixture','tags':[],'preview':'qa-reference.png','modified':0}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1100})
        page.on('pageerror',lambda e:errors.append(str(e)))
        current={'started':False,'stage':0}
        def generations(route):
            if route.request.method=='POST':
                body=route.request.post_data_json
                assert body['references']==['qa-reference.png']
                current['started']=True
                route.fulfill(status=202,json=job)
            elif not current['started']:
                route.fulfill(json=[])
            else:
                value=dict(job)
                if current['stage']>=1:value.update(stage='exporting',state='exporting')
                if current['stage']>=2:value.update(stage='completed',state='ready',result={'path':model['path'],'description':'QA preview'})
                current['stage']+=1
                route.fulfill(json=[value])
        page.route('**/api/asset-generations',generations)
        page.route('**/api/asset-generations/*/files/preview.png',lambda r:r.fulfill(path=str(reference),content_type='image/png'))
        page.route('**/api/uploads',lambda r:r.fulfill(json={'path':'qa-reference.png','assets':[]}))
        page.route('**/api/assets/file?path=qa-reference.png',lambda r:r.fulfill(path=str(reference),content_type='image/png'))
        def assets(route):
            response=route.fetch()
            data=response.json()
            data['assets'].append(model)
            route.fulfill(json=data)
        page.route('**/api/library',assets)
        page.goto('http://127.0.0.1:8765/#assetgen',wait_until='networkidle')
        page.locator('#assetgen-name').fill('QA model')
        page.locator('#assetgen-upload').click()
        page.locator('#file-input').set_input_files(str(reference))
        page.locator('#assetgen-references img').wait_for()
        page.locator('#assetgen-generate').click()
        page.wait_for_function("document.querySelector('#assetgen-generate').disabled")
        page.locator('#assetgen-result img').wait_for(timeout=20000)
        assert not page.locator('#assetgen-generate').is_disabled()
        page.screenshot(path=str(out/'completed.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(out/'completed-mobile.png'),full_page=True)
        page.locator('[data-use-generated-asset]').click()
        page.locator('#tab-art').wait_for(state='visible')
        assert page.locator('#preferred-assets input:checked').count()>=1
        assert not errors,errors
        browser.close()
    print('Image upload, generation stages, GLB result, reuse and mobile layout: OK')


if __name__=='__main__':
    main()
