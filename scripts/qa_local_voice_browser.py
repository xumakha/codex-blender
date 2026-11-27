"""Generate and play the registered local Tuấn Anh clone without saving a project."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',
            headless=True, args=['--disable-gpu'])
        page = browser.new_page(viewport={'width':1440, 'height':1100})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://127.0.0.1:8765/#studio', wait_until='networkidle')
        voices = page.request.get('http://127.0.0.1:8765/api/bootstrap').json()['voices']
        voice = next(v for v in voices if v['name'] == 'Tuấn Anh')
        assert voice['provider'] == 'voicestudio' and not voice['disabled']
        assert not voice['requires_api_key']
        page.locator('[data-tab="audio"]').click()
        page.locator('[data-voice="tts"]').click()
        page.locator('#voice-id').select_option(voice['id'])
        page.locator('#rate').select_option('0')
        page.locator('#narration').fill('Hôm nay, chúng ta cùng khám phá thế giới khoa học.')
        assert 'không cần API key' in page.locator('#voice-provider-note').inner_text()
        with page.expect_response('**/api/voice-preview', timeout=600000) as pending:
            page.locator('#preview-voice').click()
        response = pending.value
        assert response.ok, response.text()
        result = response.json()
        page.locator('#tts-player').wait_for(state='visible')
        page.wait_for_function('document.querySelector("#tts-player").readyState>=2', timeout=15000)
        duration = page.locator('#tts-player').evaluate('(player)=>player.duration')
        assert duration > 1
        assert page.locator('#voice-id').input_value() == voice['id']
        assert not page.locator('#preview-voice').is_disabled()
        assert not errors, errors
        out = Path('outputs/local-voice-qa')
        out.mkdir(exist_ok=True)
        page.locator('#tab-audio').screenshot(path=str(out/'tuan-anh-preview.png'))
        (out/'result.json').write_text(json.dumps({'path':result['path'], 'duration':duration,
                                                  'voice':voice['id']}, indent=2), encoding='utf-8')
        browser.close()
    print(f'Tuan Anh local clone: preview API, browser audio and button recovery OK ({duration:.2f}s)')


if __name__ == '__main__':
    main()
