"""B21 펀드 자체 공시 출처 점검(수동, 11/24 의장 "확보해보시고"): 노르웨이 NBIM 보유 목록·캐나다 CPP 해외 상장주식 목록·국민연금 국내주식(공공데이터)."""
import re

import requests

H = {'User-Agent': 'Mozilla/5.0'}


def show(n, u):
    try:
        r = requests.get(u, headers=H, timeout=30)
        ct = r.headers.get('content-type', '')
        print(f'[{n}] {r.status_code} {ct} {len(r.content)}B {u}')
        if 'html' in ct:
            t = r.text
            links = sorted(set(re.findall(r'href="([^"]+\.(?:xlsx|csv|pdf|xls)[^"]*)"', t)))[:40]
            for l in links: print('   ', l)
            api = sorted(set(re.findall(r'(/[A-Za-z0-9_/\-]*(?:holding|Holding)[A-Za-z0-9_/\-\.]*)', t)))[:30]
            for a in api: print('   api?', a)
        return r
    except Exception as e:  # noqa: BLE001
        print(f'[{n}] 실패 {type(e).__name__} {str(e)[:200]} {u}')


r = show('NBIM 전체 투자 페이지', 'https://www.nbim.no/en/investments/all-investments/')
if r is not None:
    t = r.text
    for m in sorted(set(re.findall(r'(?:href|src|data-[a-z\-]+)="([^"]+)"', t))):
        if any(k in m.lower() for k in ('download', 'holding', 'api', '.js', 'csv', 'xlsx', 'investments')): print('   ', m[:200])
    for m in sorted(set(re.findall(r'https?://[^"\' <>]+', t)))[:60]: print('   url', m[:200])
    for m in re.findall(r'.{80}(?:csv|xlsx).{80}', t)[:20]: print('   ctx', m)
r = show('NBIM 앱 js', 'https://www.nbim.no/static/investment/assets/index.js')
if r is not None:
    t = r.text
    for m in sorted(set(re.findall(r'["\'`](/?(?:api|holding|investments)[^"\'`]{0,150})["\'`]', t)))[:60]: print('   js', m)
    for k in ('Holding', 'holding', '.json', 'xlsx', 'csv', 'fetch'):
        for m in [t[max(0,x.start()-100):x.start()+150] for x in re.finditer(re.escape(k), t)][:6]: print('   ctx', k, m.replace(chr(10),' '))
show('CPP 해외 F25', 'https://www.cppinvestments.com/wp-content/uploads/2025/05/Foreign-Publicly-Traded-Equity-Holdings_ibfs-Q4F25.html')
show('CPP 해외 F24', 'https://www.cppinvestments.com/wp-content/uploads/2024/05/Foreign-Publicly-Traded-Equity-Holdings_ibfs-Q4F24.html')
show('국민연금 국내주식(공공데이터)', 'https://www.data.go.kr/data/3070507/fileData.do')
