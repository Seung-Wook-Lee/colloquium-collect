"""ETF 좌수(설정·환매) 과거 기록 (11/24 B20 ETF 자금 과거 값).
State Street 공식 NAV 이력 엑셀(블록 9-ETF자금 _spdr_hist와 같은 출처)은 설정일부터 날짜·NAV·좌수를 모두 준다(XLK 5,9xx줄 확인).
대상: 유니버스 ETF 중 SPDR 펀드 + 블록 9-ETF자금의 SPDR 섹터 11개·SPY.
한국 ETF는 KRX 로그인(KRX_ID·KRX_PW)이 있어야 좌수 이력을 받을 수 있어 여기서는 못 받음. 다른 미국 운용사(Invesco·VanEck 등)는 일별 좌수 이력 공개 파일 없음.
출력: <폴더>/가격10년_ETF좌수.csv.gz(10년치 저장본 칸) (날짜, 코드, NAV, 상장좌수, 출처)
실행: python collect/data/hist_etf_flow.py <유니버스.csv 있는 폴더>"""
import io
import sys
import time

import pandas as pd
import requests

d = sys.argv[1] if len(sys.argv) > 1 else 'in'
SECT = ['XLK', 'XLC', 'XLY', 'XLP', 'XLE', 'XLF', 'XLV', 'XLI', 'XLB', 'XLRE', 'XLU', 'SPY', 'SPYM']
U = pd.read_csv(f'{d}/유니버스.csv', encoding='utf-8-sig', dtype=str)
e = U[(U['시장'] == '미국') & (U['구분'] == 'ETF')]
spdr = e[e['정식 종목명'].str.contains('SPDR', case=False, na=False)]['yfinance 티커'].str.upper().tolist()
tk = sorted(set(SECT) | set(spdr))
out, rep = [], []
for t in tk:
    b = None
    for n in range(3):
        try:
            r = requests.get(f'https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-{t.lower()}.xlsx',
                             headers={'User-Agent': 'Mozilla/5.0'}, timeout=90)
            if r.status_code == 200 and r.content[:2] == b'PK':
                b = r.content; break
        except Exception as ex:   # noqa: BLE001
            print(t, '재시도', ex)
        time.sleep(2 + 3 * n)
    if b is None:
        rep.append(f'{t} 실패'); continue
    raw = pd.read_excel(io.BytesIO(b), header=None)
    hdr = raw.index[raw.iloc[:, 0].astype(str).str.strip().str.lower() == 'date'][0]
    df = raw.iloc[hdr + 1:].copy(); df.columns = [str(c).strip().lower() for c in raw.iloc[hdr]]
    sh = next(c for c in df.columns if 'shares' in c)
    x = pd.DataFrame({'날짜': pd.to_datetime(df['date'], errors='coerce', format='mixed'), '코드': t,
                      'NAV': pd.to_numeric(df['nav'], errors='coerce'),
                      '상장좌수': pd.to_numeric(df[sh].astype(str).str.replace(',', ''), errors='coerce'), '출처': 'SPDR 이력'}).dropna()
    out.append(x.sort_values('날짜'))
    rep.append(f'{t} {len(x)}({x["날짜"].min().date()}~)')
    time.sleep(1)
H = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=['날짜', '코드', 'NAV', '상장좌수', '출처'])
H['날짜'] = pd.to_datetime(H['날짜']).dt.strftime('%Y-%m-%d')
H.to_csv(f'{d}/가격10년_ETF좌수.csv.gz', index=False, compression='gzip')
print('ETF 좌수 이력', H['코드'].nunique(), '개,', len(H), '줄 |', ' · '.join(rep))
