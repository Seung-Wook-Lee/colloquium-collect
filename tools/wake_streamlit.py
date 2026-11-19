# 스트림릿 깨우기 (2026-11-20 의장: "9시부터는 열어서 내가 링크를 걸 수 있도록")
# 스트림릿 클라우드는 한동안 아무도 안 들어오면 잠든다. 회의 전에 브라우저로 한 번 들어가 깨워 둔다.
# 잠들어 있으면 'Yes, get this app back up' 단추를 누르고, 유튜브 화면까지 열어 본다.
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('APP_URL', 'https://colloquium-tom.streamlit.app').rstrip('/')

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    for path in ('', '/유튜브'):
        pg.goto(URL + path, timeout=120000)
        time.sleep(8)
        btn = pg.get_by_role('button', name='Yes, get this app back up')
        if btn.count():
            print('잠들어 있음 → 깨움')
            btn.first.click()
            time.sleep(90)
        print(path or '/', '열림:', pg.title())
    b.close()
sys.exit(0)
