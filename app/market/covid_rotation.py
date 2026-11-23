"""코로나 폭락 뒤 '금 → 다음은 무엇' 순서 (11/23 의장).
의장 질문: "코로나 폭락 직후 금·채권 모두 떨어졌다가 금값부터 오르더라. 그때 금값 오르고 이어서 뭐가 올랐지? 주식이면 어떤 주식."
계산: 2020-02-01~2020-06-30 안에서 자산마다
  - 저점 날짜, 고점(2020-02-19 무렵) 대비 최대 낙폭
  - 반등 시작일 = 저점에서 +10% 처음 넘은 날, 금(GLD) 반등 시작일보다 며칠 뒤인가
  - 금 저점 날짜 종가에서 1·3·6개월 뒤 수익
대상: 자산군 ETF·원자재·비트코인 + 유니버스(콜로키움100_유니버스_20261121, 삭제 DHR·APP·PH 뺌) 개별주·ETF.
결과: /mnt/project-files/유니버스/start/covid_rotation/
"""
from pathlib import Path
import pandas as pd
import yfinance as yf

OUT = Path('/mnt/project-files/유니버스/start/covid_rotation/')
ASSET = {'GLD': '금', 'SLV': '은', 'GDX': '금광주', 'TLT': '미국 장기채', 'IEF': '미국 10년채', 'LQD': '투자등급 회사채', 'HYG': '하이일드 채권',
         'UUP': '달러', 'HG=F': '구리', 'CL=F': 'WTI 원유', 'BTC-USD': '비트코인', 'SPY': 'S&P500', 'QQQ': '나스닥100', 'IWM': '러셀2000',
         'EEM': '신흥국', 'SOXX': '반도체', 'XLK': '기술', 'XLV': '헬스케어', 'XLY': '임의소비재', 'XLP': '필수소비재', 'XLE': '에너지',
         'XLF': '금융', 'XLI': '산업재', 'XLB': '소재', 'XLU': '유틸리티', 'XLRE': '부동산', 'XLC': '커뮤니케이션', 'ARKK': '혁신 성장주',
         '^KS11': '코스피', '^KQ11': '코스닥'}


def stats(c, g_low_day, g_start):
    c = c.dropna()
    w = c['2020-02-01':'2020-06-30']
    if len(w) < 60:
        return None
    pk = c['2020-01-01':'2020-03-10'].max()
    lo_d = w.idxmin(); lo = w.min()
    after = w[lo_d:]
    st = after[after >= lo * 1.10]
    st_d = st.index[0] if len(st) else pd.NaT
    base = c.asof(g_low_day)
    f = lambda m: c.asof(g_low_day + pd.DateOffset(months=m)) / base - 1
    rec = c[lo_d:][c[lo_d:] >= pk]
    rec_d = rec.index[0] if len(rec) else pd.NaT
    return {'저점일': lo_d.date(), '최대 낙폭(%)': (lo / pk - 1) * 100, '반등 시작일(+10%)': st_d.date() if pd.notna(st_d) else '',
            '금보다 며칠 뒤': (st_d - g_start).days if pd.notna(st_d) else None,
            '폭락 전 고점 회복일': rec_d.date() if pd.notna(rec_d) else '2021-01 안 회복 못 함',
            '고점 회복까지 금 저점일부터(일)': (rec_d - g_low_day).days if pd.notna(rec_d) else None,
            '금 저점일부터 1개월(%)': f(1) * 100, '3개월(%)': f(3) * 100, '6개월(%)': f(6) * 100}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    U = pd.read_csv('/mnt/project-files/유니버스/콜로키움100_유니버스_20261121.csv', encoding='utf-8-sig')
    U = U[~U['yfinance 티커'].isin(['DHR', 'APP', 'PH'])].dropna(subset=['yfinance 티커'])
    tk = list(ASSET) + [t for t in U['yfinance 티커'].unique() if t not in ASSET]
    cache = Path('/tmp/claude-0/covid_px.pkl')
    if cache.exists():
        P = pd.read_pickle(cache)
    else:
        P = yf.download(tk, start='2019-12-01', end='2021-01-31', auto_adjust=True, progress=False)['Close']
        cache.parent.mkdir(parents=True, exist_ok=True); P.to_pickle(cache)
    g = P['GLD'].dropna()['2020-02-01':'2020-06-30']
    g_low = g.idxmin(); g_start = g[g_low:][g[g_low:] >= g.min() * 1.10].index[0]
    rows = []
    for t in tk:
        if t not in P:
            continue
        s = stats(P[t], g_low, g_start)
        if s is None:
            continue
        if t in ASSET:
            nm, kind = ASSET[t], '자산군'
        else:
            r = U[U['yfinance 티커'] == t].iloc[0]
            nm = t if r['시장'] == '미국' else r['정식 종목명']
            kind = f"{r['구분']}·{r['섹터/테마']}"
        rows.append({'구분': kind, '대상': nm, **s})
    R = pd.DataFrame(rows)
    R.to_csv(OUT / '코로나_반등순서.csv', index=False, encoding='utf-8-sig')
    print(f'금 저점 {g_low.date()}, 금 반등 시작(+10%) {g_start.date()}')
    A = R[R['구분'] == '자산군'].sort_values('고점 회복까지 금 저점일부터(일)')
    print(A.round(1).to_string(index=False))
    S = R[R['구분'] != '자산군']
    print('\n유니버스: 금 저점일부터 3개월 상위 20')
    print(S.sort_values('3개월(%)', ascending=False).head(20).round(1).to_string(index=False))
    print('\n유니버스: 폭락 전 고점 회복 빠른 순 25')
    print(S.sort_values('고점 회복까지 금 저점일부터(일)').head(25).round(1).to_string(index=False))
    print('\n회복 순서(유니버스 개별주, 30일 단위)')
    S2 = S.dropna(subset=['고점 회복까지 금 저점일부터(일)'])
    print(pd.cut(S2['고점 회복까지 금 저점일부터(일)'], [0, 30, 60, 90, 120, 180, 300]).value_counts().sort_index().to_string(), '/ 못 회복', S['고점 회복까지 금 저점일부터(일)'].isna().sum())
    print('\n섹터별 3개월 중앙값')
    print(S.groupby('구분')['3개월(%)'].agg(['median', 'count']).sort_values('median', ascending=False).round(1).head(20).to_string())


if __name__ == '__main__':
    main()
