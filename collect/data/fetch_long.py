"""블록 성적표(backtest.py)용 긴 가격: 10년 종가·고가·저가·거래량 + 지수(야후 무료). 일주일에 한 번이면 충분.
쓰는 법: python fetch_long.py <입력폴더>  →  <입력폴더>/장기/가격2년.csv 등(이름은 엔진과 같게, 기간만 10년)"""
import os, sys
import pandas as pd, yfinance as yf

d = sys.argv[1] if len(sys.argv) > 1 else 'in'
o = f'{d}/장기'; os.makedirs(o, exist_ok=True)
N = pd.read_csv(f'{d}/닉스.csv', encoding='utf-8-sig')
t = [x for x in N['yfinance 티커'].dropna().astype(str).unique()]
D = yf.download(t, period='10y', auto_adjust=True, progress=False, threads=True)
# 11/23 의장 "만들어진 지 얼마 안 됐으면 나스닥100·S&P500으로 돌리면 되잖아(트래킹 에러 작음)":
#   최근 상장 지수 ETF는 상장 전 구간을 추종 지수 가격으로 이어 붙인다(상장 첫날 값에 맞춰 비율 조정). 거래량은 잇지 않음.
PROXY = {'QQQM': '^NDX', 'SPYM': '^GSPC', 'SOXQ': '^SOX'}
px = [v for k, v in PROXY.items() if k in t]
if px:
    PI = yf.download(px, period='10y', auto_adjust=True, progress=False)
    for k in ('Close', 'Open', 'High', 'Low'):
        for e, ix in PROXY.items():
            if e not in D[k] or ix not in PI[k]: continue
            s, q = D[k][e], PI[k][ix].reindex(D.index)
            f0 = s.first_valid_index()
            if f0 is None or pd.isna(q.get(f0)): continue
            m = (D.index < f0) & q.notna()
            D.loc[m, (k, e)] = (q[m] * s[f0] / q[f0]).values
            if k == 'Close': print(f'{e}: {f0.date()} 전은 {ix}로 이음({int(m.sum())}일)')
for k, f in (('Close', '가격2년'), ('Open', '시가2년'), ('High', '고가2년'), ('Low', '저가2년'), ('Volume', '거래량2년')):
    D[k].to_csv(f'{o}/{f}.csv', encoding='utf-8-sig')
I = yf.download(['^GSPC', '^KS11', '^KQ11'], period='10y', auto_adjust=True, progress=False)['Close']
I.to_csv(f'{o}/지수2년.csv', encoding='utf-8-sig')
print(D['Close'].shape, D.index[0], D.index[-1])
