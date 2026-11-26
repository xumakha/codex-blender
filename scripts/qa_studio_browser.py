"""Browser-level QA against a running local Studio, using the installed Chrome."""
import json
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright

base=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8766'
out=Path('outputs/studio-qa');out.mkdir(parents=True,exist_ok=True)
errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(base,wait_until='networkidle')
    page.wait_for_function("document.querySelector('#title').value.length>0 && !document.querySelector('#connection-label').textContent.includes('Đang')")
    page.locator('[data-template="product"]').click()
    page.wait_for_function("document.querySelector('#scene-json').value.includes('Hero')")
    page.locator('[data-tab="art"]').click()
    fixture=next(Path('outputs').glob('*/preview.png')).resolve()
    page.locator('#upload-references').click()
    page.locator('#file-input').set_input_files(str(fixture))
    page.locator('#reference-grid img').first.wait_for()
    page.locator('[data-tab="audio"]').click()
    page.locator('[data-voice="tts"]').click()
    page.locator('#voice-id').select_option('vi-VN-HoaiMyNeural')
    page.locator('#narration').fill('Xin chào, đây là video thử nghiệm.')
    page.locator('#music').select_option('elevator-sample-chime.wav')
    page.locator('#music-volume').fill('0.15')
    page.locator('#save-project').click()
    page.wait_for_function("document.querySelector('#save-state').textContent==='Đã lưu'")
    project_title=page.locator('#title').input_value()
    project_ids=page.request.get(base+'/api/projects').json()
    pid=next(x['id'] for x in project_ids if x['title']==project_title)
    draft=page.request.get(base+'/api/projects/'+pid).json()['draft']
    assert draft['voice_id']=='vi-VN-HoaiMyNeural'
    assert draft['music_volume']==.15
    assert len(draft['references'])>=1
    page.locator('[data-voice="none"]').click()
    page.locator('#save-project').click()
    page.wait_for_timeout(500)
    page.locator('[data-tab="script"]').click()
    page.screenshot(path=str(out/'studio-desktop.png'),full_page=True)
    page.locator('#nav [data-page="library"]').click()
    page.locator('#library-grid .asset-card').first.wait_for()
    page.locator('#asset-search').fill('không-có-tài-nguyên-này')
    page.locator('#library-grid .empty-state').wait_for()
    page.locator('#asset-search').fill('')
    page.locator('#nav [data-page="settings"]').click()
    assert page.locator('#assets-directory').input_value()
    page.screenshot(path=str(out/'studio-settings.png'),full_page=True)
    page.locator('#nav [data-page="studio"]').click()
    page.set_viewport_size({'width':390,'height':844})
    page.screenshot(path=str(out/'studio-mobile.png'),full_page=True)
    overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth')
    assert not overflow,'Mobile layout overflows horizontally'
    assert not errors,errors
    browser.close()
print(json.dumps({'passed':True,'page_errors':errors,'screenshots':str(out)},indent=2))
