"""B19(장기 펀드 13F 늘렸나) 과거 성적: 공시일 다음 거래일에 샀다면 4·12·26·52주 뒤 절대 수익률 중앙값·승률.

비교: 늘림(lt_net > 0) / 줄임(lt_net < 0) / B19 공식 3개 모두 예(늘림 + 늘린 곳 ≥ 줄인 곳 + 2분기 연속).
가격: yfinance 수정주가. 미래 정보 없음: 그 분기 13F가 모두 공시된 날(공시일) 다음 거래일 종가에서 출발.
실행: python grade_13f.py <입력 폴더>  →  <입력>/../장기펀드13F_성적.csv
"""
import sys

import numpy as np
import pandas as pd

H = {'4주': 20, '12주': 60, '26주': 130, '52주': 260}


def grade(R, P):
    rows = []
    for _, r in R.iterrows():
        t = r['ticker']
        if t not in P or pd.isna(r['lt_net']):
            continue
        px = P[t].dropna()
        i = px.index.searchsorted(pd.Timestamp(r['공시일']), side='right')
        if i >= len(px):
            continue
        e = dict(ticker=t, 분기=r['분기'], 출발=px.index[i].date(), 늘림=r['lt_net'] > 0, 줄임=r['lt_net'] < 0,
                 전부예=(r['lt_net'] > 0) and (r['lt_up'] >= r['lt_dn']) and (r.get('lt_net_prev', np.nan) > 0))
        for k, n in H.items():
            e[k] = (px.iloc[i + n] / px.iloc[i] - 1) * 100 if i + n < len(px) else np.nan
        rows.append(e)
    E = pd.DataFrame(rows)
    out = []
    for lab, m in (('늘림', E['늘림']), ('줄임', E['줄임']), ('B19 전부 예(2분기 연속 늘림)', E['전부예']), ('전체', E['늘림'] | ~E['늘림'])):
        g = E[m]
        for k in H:
            v = g[k].dropna()
            out.append(dict(구분=lab, 기간=k, 건수=len(v), 수익률중앙값=round(v.median(), 2) if len(v) else None,
                            승률=round((v > 0).mean() * 100, 1) if len(v) else None))
    return pd.DataFrame(out), E


if __name__ == '__main__':
    import yfinance as yf
    d = sys.argv[1]
    R = pd.read_csv(f'{d}/장기펀드13F_이력.csv', encoding='utf-8-sig')
    P = yf.download(sorted(R['ticker'].unique()), start='2013-01-01', auto_adjust=True, progress=False)['Close']
    G, E = grade(R, P)
    G.to_csv(f'{d}/../장기펀드13F_성적.csv', index=False, encoding='utf-8-sig')
    print(G.pivot(index='구분', columns='기간', values=['수익률중앙값', '승률', '건수']).to_string())
