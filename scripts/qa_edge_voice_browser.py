"""Live Nam Minh preview check; does not save or modify user projects."""
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1100})
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto('http://127.0.0.1:8765/#studio',wait_until='networkidle')
        page.locator('[data-tab="audio"]').click()
        page.locator('[data-voice="tts"]').click()
        page.locator('#voice-id').select_option('vi-VN-NamMinhNeural')
        page.locator('#narration').fill('Xin chào! Đây là giọng đọc Nam Minh cho video của bạn.')
        with page.expect_response('**/api/voice-preview',timeout=135000) as pending:
            page.locator('#preview-voice').click()
        response=pending.value
        assert response.ok,response.text()
        page.locator('#tts-player').wait_for(state='visible')
        page.wait_for_function('document.querySelector("#tts-player").readyState>=2',timeout=15000)
        duration=page.locator('#tts-player').evaluate('(player)=>player.duration')
        assert duration>0
        assert page.locator('#voice-id').input_value()=='vi-VN-NamMinhNeural'
        assert not page.locator('#preview-voice').is_disabled()
        assert not errors,errors
        out=Path('outputs/edge-voice-qa');out.mkdir(exist_ok=True)
        page.locator('#tab-audio').screenshot(path=str(out/'nam-minh-preview.png'))
        browser.close()
    print(f'Nam Minh live preview, browser audio playback and button recovery: OK ({duration:.2f}s)')


if __name__=='__main__':main()
