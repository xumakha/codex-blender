"""Exercise batch UI with simulated API responses, without creating user projects."""
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    reference=Path('outputs/assetgen-smoke-batch/assets/reference.png').resolve()
    out=Path('outputs/assetgen-batch-browser-qa')
    out.mkdir(exist_ok=True)
    job={'id':'b'*32,'name':'QA collection','state':'planning','stage':'inventory','error':None,
         'updated':'2026-11-27T00:00:00Z','references':['qa-reference.png'],'prompt':'QA','result':None,
         'mode':'multiple','max_assets':5,'items':[],'notes':''}
    models=[{'path':f'generated/qa-{name}.glb','name':name,'kind':'model','bytes':1000,'source':'blender',
             'description':'Browser QA fixture','tags':[],'preview':'qa-reference.png','modified':0} for name in ['chair','table']]
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1100})
        page.on('pageerror',lambda e:errors.append(str(e)))
        current={'started':False,'stage':0}
        def generations(route):
            if route.request.method=='POST':
                body=route.request.post_data_json
                assert body['references']==['qa-reference.png']
                assert body['mode']=='multiple' and body['max_assets']==5
                current['started']=True
                route.fulfill(status=202,json=job)
            elif not current['started']:route.fulfill(json=[])
            else:
                value=dict(job)
                if current['stage']>=1:
                    value.update(stage='rendering',items=[
                        {'id':model['name'],'name':model['name'],'state':'running','stage':'rendering','result':None,'error':None} for model in models])
                    value['items'].append({'id':'lamp','name':'lamp','state':'pending','stage':'pending','result':None,'error':None})
                if current['stage']>=2:
                    value.update(stage='completed',state='ready',error='2/3 assets saved',notes='Deduplicated repeated views')
                    for item,model in zip(value['items'],models):item.update(state='completed',stage='completed',result=model)
                    value['items'][-1].update(state='failed',stage='failed',error='Geometry unavailable')
                current['stage']+=1
                route.fulfill(json=[value])
        page.route('**/api/asset-generations',generations)
        page.route('**/api/asset-generations/*/items/*/files/preview.png',lambda r:r.fulfill(path=str(reference),content_type='image/png'))
        page.route('**/api/uploads',lambda r:r.fulfill(json={'path':'qa-reference.png','assets':[]}))
        page.route('**/api/assets/file?path=qa-reference.png',lambda r:r.fulfill(path=str(reference),content_type='image/png'))
        def assets(route):
            data=route.fetch().json()
            data['assets'].extend(models)
            route.fulfill(json=data)
        page.route('**/api/library',assets)
        page.goto('http://127.0.0.1:8765/#assetgen',wait_until='networkidle')
        assert page.locator('#assetgen-batch-options').is_hidden()
        page.locator('#assetgen-mode').select_option('multiple')
        assert page.locator('#assetgen-batch-options').is_visible()
        page.locator('#assetgen-limit').select_option('5')
        page.locator('#assetgen-name').fill('QA collection')
        page.locator('#assetgen-upload').click()
        assert not page.locator('#file-input').evaluate('(e)=>e.multiple')
        page.locator('#file-input').set_input_files(str(reference))
        page.locator('#assetgen-references img').wait_for()
        page.locator('#assetgen-generate').click()
        page.wait_for_function("document.querySelector('#assetgen-status').textContent.includes('QA collection')")
        page.wait_for_function("document.querySelectorAll('#assetgen-result img').length===2",timeout=20000)
        assert page.locator('#assetgen-result .assetgen-preview').count()==3
        assert 'Geometry unavailable' in page.locator('#assetgen-result').inner_text()
        assert not page.locator('#assetgen-generate').is_disabled()
        links=page.locator('#assetgen-result a').evaluate_all('(a)=>a.map(e=>e.getAttribute("href"))')
        assert any('/items/chair/files/model.glb' in url for url in links)
        assert any('/items/table/files/scene.blend' in url for url in links)
        page.screenshot(path=str(out/'completed.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(out/'completed-mobile.png'),full_page=True)
        page.locator('[data-generated-item="table"]').click()
        page.locator('#tab-art').wait_for(state='visible')
        assert page.locator('#preferred-assets input:checked').count()>=1
        assert not errors,errors
        browser.close()
    print('Batch selection, one-image upload, request limit, per-item results/downloads/errors, reuse and mobile layout: OK')


if __name__=='__main__':main()
