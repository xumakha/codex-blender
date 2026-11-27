"""Read-only Chrome regression for the asset tab and invalid API responses."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from codex_blender.config import source_revision

BASE='http://127.0.0.1:8765'


def main():
    out=Path('outputs/api-recovery-qa');out.mkdir(exist_ok=True)
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.on('pageerror',lambda e:errors.append(str(e)))
        response=page.request.get(BASE+'/api/bootstrap')
        assert response.json()['server_revision']==source_revision()
        assert response.headers['cache-control']=='no-store'
        page.goto(BASE,wait_until='networkidle')
        page.locator('#nav [data-page="assetgen"]').click()
        page.locator('#page-assetgen').wait_for(state='visible')
        page.wait_for_function("document.querySelector('#assetgen-history').children.length>0")
        assert page.locator('#assetgen-error').is_hidden()
        assert not page.locator('#toast').is_visible()
        for status,body,expected in [(404,'Not Found','start-studio.cmd'),(500,'Internal Server Error','HTTP 500'),(200,'<html>Unexpected page</html>','HTTP 200')]:
            page.route('**/api/asset-generations',lambda route,request,s=status,b=body:route.fulfill(status=s,body=b,content_type='text/html'))
            page.locator('#refresh-asset-generations').click()
            page.wait_for_function('(expected)=>document.querySelector("#toast").textContent.includes(expected)',arg=expected)
            page.unroute('**/api/asset-generations')
        page.reload(wait_until='networkidle')
        page.locator('#nav [data-page="assetgen"]').click()
        page.wait_for_function("document.querySelector('#assetgen-history').children.length>0")
        assert not page.locator('#toast').is_visible()
        missing=page.request.get(BASE+'/api/unknown-feature')
        assert missing.status==404 and 'error' in missing.json()
        page.screenshot(path=str(out/'asset-tab.png'),full_page=True)
        assert not errors,errors
        browser.close()
    print('Live asset tab, JSON 404, stale-server response, HTTP 500 and recovery: OK')


if __name__=='__main__':main()
