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


for y in (2024, 2017):
    show(f'NBIM pdf {y}', f'https://www.nbim.no/no/holdingsdata/eq_{y}_country.pdf')
    for ext in ('xlsx', 'csv'):
        show(f'NBIM {ext} {y}', f'https://www.nbim.no/no/holdingsdata/eq_{y}_country.{ext}')
show('NBIM 전체 투자 페이지', 'https://www.nbim.no/en/investments/all-investments/')
r = show('NBIM pdf 2024', 'https://www.nbim.no/no/holdingsdata/eq_2024_country.pdf')
if r is not None and r.status_code == 200 and r.content[:4] == b'%PDF':
    open('/tmp/nbim.pdf', 'wb').write(r.content)
    try:
        import pdfplumber
        with pdfplumber.open('/tmp/nbim.pdf') as p:
            print('   쪽수', len(p.pages))
            t = p.pages[0].extract_text() or ''
            print('   첫 쪽', t[:800].replace('\n', ' | '))
            for pg in p.pages:
                tx = pg.extract_text() or ''
                if 'Korea' in tx or 'Samsung' in tx:
                    print('   한국 쪽', tx[:600].replace('\n', ' | ')); break
    except Exception as e:  # noqa: BLE001
        print('   pdf 읽기 실패', e)
show('CPP 해외 F25', 'https://www.cppinvestments.com/wp-content/uploads/2025/05/Foreign-Publicly-Traded-Equity-Holdings_ibfs-Q4F25.html')
show('CPP 해외 F24', 'https://www.cppinvestments.com/wp-content/uploads/2024/05/Foreign-Publicly-Traded-Equity-Holdings_ibfs-Q4F24.html')
show('국민연금 국내주식(공공데이터)', 'https://www.data.go.kr/data/3070507/fileData.do')
