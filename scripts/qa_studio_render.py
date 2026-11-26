"""Exercise the actual preview/render controls and the asset export modal in Chrome."""
from pathlib import Path
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8766',wait_until='networkidle')
    page.locator('[data-project="8ee70cd7df33498495ccf2b82c20e525"]').click()
    page.wait_for_function("document.querySelector('#title').value==='AI · Nhân vật dùng lại'")
    page.locator('#render-preview').click()
    page.wait_for_function("document.querySelector('#status-title').textContent==='Preview đã sẵn sàng'",timeout=60000)
    assert page.locator('#preview-image').is_visible()
    page.locator('#export-asset').click()
    page.locator('#export-dialog').wait_for(state='visible')
    page.locator('#export-objects input').first.check()
    assert page.locator('#export-objects input:checked').count()==1
    page.locator('#export-dialog form button').click()
    page.locator('#render-video').click()
    page.wait_for_function("document.querySelector('#status-title').textContent==='Video đã hoàn tất'",timeout=60000)
    assert page.locator('#preview-video').is_visible()
    page.locator('#preview-video').evaluate('(el)=>{el.currentTime=0.4}')
    page.wait_for_timeout(1000)
    Path('outputs/studio-qa').mkdir(parents=True,exist_ok=True)
    page.screenshot(path='outputs/studio-qa/studio-completed.png',full_page=True)
    page.locator('#nav [data-page="library"]').click()
    page.wait_for_timeout(700)
    assert page.locator('#library-grid').get_by_text('Nhà phát minh áo vàng',exact=True).count()==1
    page.screenshot(path='outputs/studio-qa/library.png',full_page=True)
    assert not errors,errors
    browser.close()
print('Actual UI preview, export modal, video render and generated library: passed')
