"""Check pause controls and progress with isolated API fixtures in Chrome."""
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, expect

from codex_blender.studio import Draft
from codex_blender.audio import VOICES, ELEVENLABS_VOICE_ID


web = Path(__file__).resolve().parents[1] / 'codex_blender' / 'web'
output = Path('outputs/studio-qa')
output.mkdir(parents=True, exist_ok=True)
project = {
    'id': 'a' * 32, 'state': 'ready', 'scene_current': True,
    'draft': Draft(title='Kiểm tra tạm dừng').model_dump(mode='json'),
    'job': {'id': 'b' * 32, 'state': 'rendering', 'mode': 'video',
            'frames_rendered': 30, 'frames_total': 120, 'artifacts': {}},
}
settings = {'assets_directory': 'assets'}
calls = []
errors = []


def route_request(route):
    path = urlparse(route.request.url).path
    if path == '/api/bootstrap':
        body = {'assets': [], 'projects': [{'id': project['id'], 'title': 'Kiểm tra tạm dừng'}],
                'settings': settings, 'voices': VOICES, 'blender_ready': True, 'codex_available': True}
    elif path == '/api/library':
        body = {'assets': [], 'settings': settings}
    elif path == '/api/projects':
        body = [{'id': project['id'], 'title': 'Kiểm tra tạm dừng'}]
    elif path.endswith('/control/pause'):
        calls.append('pause')
        project['job']['state'] = 'pausing'
        body = project
    elif path.endswith('/control/resume'):
        calls.append('resume')
        project['job']['state'] = 'rendering'
        body = project
    elif path == '/api/projects/' + project['id']:
        body = project
    elif path in ('/', '/app.js', '/style.css'):
        file = web / ('index.html' if path == '/' else path[1:])
        content_type = {'.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css'}[file.suffix]
        route.fulfill(body=file.read_text(encoding='utf-8'), content_type=content_type)
        return
    else:
        route.fulfill(status=404, body='Not found')
        return
    route.fulfill(json=body)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/*', route_request)
    page.goto('http://127.0.0.1:8766/')
    button = page.locator('#pause-render')
    expect(button).to_have_text('Tạm dừng')
    expect(page.locator('#progress-count')).to_have_text('25% · 30 / 120 khung hình')
    expect(page.locator('#progress-track')).to_have_attribute('aria-valuenow', '25')
    button.click()
    expect(page.locator('#status-title')).to_have_text('Đang chờ tạm dừng')
    expect(button).to_have_text('Tiếp tục')
    project['job']['state'] = 'paused'
    page.reload()
    expect(page.locator('#status-title')).to_have_text('Đã tạm dừng render')
    expect(page.locator('#prompt')).to_be_disabled()
    page.screenshot(path=str(output / 'pause-desktop.png'), full_page=True)
    button.click()
    expect(button).to_have_text('Tạm dừng')
    assert calls == ['pause', 'resume'], calls
    project['job']['state'] = 'encoding'
    page.reload()
    expect(button).to_be_hidden()
    expect(page.locator('#progress-track')).to_have_attribute('aria-valuenow', '25')
    project['job'].update(state='completed', frames_rendered=120)
    page.reload()
    expect(page.locator('#progress-count')).to_contain_text('100%')
    page.locator('[data-tab="audio"]').click()
    expect(page.locator('#voice-options')).to_be_visible()
    expect(page.locator('#voice-tts')).to_be_hidden()
    page.locator('#voice-id').select_option(ELEVENLABS_VOICE_ID)
    expect(page.locator('#voice-provider-note')).to_contain_text('ELEVENLABS_API_KEY')
    expect(page.locator('#preview-voice')).to_be_visible()
    page.locator('[data-voice="tts"]').click()
    expect(page.locator('#voice-tts')).to_be_visible()
    expect(page.locator('#voice-id')).to_have_value(ELEVENLABS_VOICE_ID)
    page.locator('[data-voice="none"]').click()
    expect(page.locator('#voice-options')).to_be_hidden()
    page.locator('[data-voice="auto"]').click()
    page.set_viewport_size({'width': 390, 'height': 844})
    expect(page.locator('#voice-options')).to_be_visible()
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
    page.screenshot(path=str(output / 'elevenlabs-mobile.png'), full_page=True)
    project['job'].update(state='paused', frames_rendered=30)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.reload()
    expect(button).to_have_text('Tiếp tục')
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
    page.screenshot(path=str(output / 'pause-mobile.png'), full_page=True)
    assert not errors, errors
    browser.close()
print(json.dumps({'passed': True, 'actions': calls, 'elevenlabs_voice': ELEVENLABS_VOICE_ID, 'page_errors': errors}))
