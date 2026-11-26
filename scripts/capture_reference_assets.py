"""Capture a contact sheet from the actual Blender-rendered asset thumbnails."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
run=root/'outputs'/'inventor-toy-kit'
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    page=browser.new_page(viewport={'width':1920,'height':1200},device_scale_factor=1)
    page.goto((run/'catalog.html').as_uri(),wait_until='load')
    page.wait_for_function('Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)')
    page.screenshot(path=str(run/'asset-contact-sheet.png'),full_page=True)
    page.goto('http://127.0.0.1:8765/#library',wait_until='networkidle')
    page.wait_for_selector('#library-grid .asset-card')
    page.locator('#asset-search').fill('inventor-toy')
    page.wait_for_timeout(500)
    assert page.locator('#library-grid .asset-card').count()==32
    page.set_viewport_size({'width':1440,'height':1000})
    page.screenshot(path=str(run/'studio-library.png'),full_page=True)
    browser.close()
print(json.dumps({'contact_sheet':str(run/'asset-contact-sheet.png'),'studio_models_verified':32},indent=2))
