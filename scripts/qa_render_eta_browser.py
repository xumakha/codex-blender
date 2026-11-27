"""Read-only browser checks with simulated render progress responses."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from codex_blender.studio import Draft
from codex_blender.models import SceneSpec


def main():
    out=Path('outputs/render-eta-browser-qa')
    out.mkdir(exist_ok=True)
    current={'state':'rendering','eta_seconds':90,'frames_rendered':25}
    project={'id':'a'*32,'state':'ready','error':None,'updated':'2026-11-27T00:00:00Z',
             'scene_current':True,'draft':Draft(title='Render ETA QA',voice_mode='none',
             scene=SceneSpec(objects=[{'name':'cube','kind':'cube'}])).model_dump(mode='json')}
    recent={'id':project['id'],'title':'Render ETA QA','state':'ready'}
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.on('pageerror',lambda error:errors.append(str(error)))
        def bootstrap(route):
            data=route.fetch().json()
            data['projects']=[recent]
            route.fulfill(json=data)
        def detail(route):
            route.fulfill(json={**project,'job':{'id':'b'*32,'mode':'video','frames_total':100,
                          'artifacts':{},**current}})
        page.route('**/api/bootstrap',bootstrap)
        page.route('**/api/projects',lambda route:route.fulfill(json=[recent]))
        page.route('**/api/projects/'+project['id'],detail)
        page.goto('http://127.0.0.1:8765/#studio',wait_until='networkidle')
        assert page.locator('#progress-eta').inner_text()=='Còn khoảng 2 phút'
        assert '25%' in page.locator('#progress-count').inner_text()
        page.screenshot(path=str(out/'desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(out/'mobile.png'),full_page=True)
        for state,eta,expected in [('rendering',35,'Còn khoảng 35 giây'),
                                    ('rendering',None,'Đang ước tính…'),
                                    ('paused',35,'Đã tạm dừng'),
                                    ('encoding',None,'Đang hoàn tất MP4…'),
                                    ('completed',0,'Đã hoàn tất')]:
            current.update(state=state,eta_seconds=eta)
            page.wait_for_function('(text)=>document.querySelector("#progress-eta").textContent===text',arg=expected,timeout=6000)
        current.update(state='failed')
        page.locator('#progress-eta').wait_for(state='hidden',timeout=6000)
        assert not errors,errors
        browser.close()
    print('Live ETA, speed updates, initial estimate, pause, encoding, completion and mobile layout: OK')


if __name__=='__main__':main()
