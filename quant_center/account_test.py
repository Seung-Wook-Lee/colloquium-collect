"""계좌 규칙 과거 검증 (11/20 의장: "저런 상황에서 저걸 샀을 때 많이 올랐어? 검증해봤어?").

블록점수이력(매주 종목별 블록 점수 + 뒤 4·12·26·52주 수익률)과 나스닥100 바닥 근접도 이력으로,
미국 계좌 규칙(위기 단계에 떨어진·고베타 종목 매수)의 가격으로 시험할 수 있는 부분을 시험한다.
- 가격 블록만 과거가 있다: B29(52주 고점 −10%), B13(이례적 하락), B16(과매도), B33(주도 업종).
- 우량(B23·B25·B26)·싼가(B15)·이익 전망(B24)은 과거 값이 없어 시험 못 한다 → 결과표에 그렇게 적는다.
- 베타 = 그 주까지 1년 나스닥100 대비(일별). 오늘 종목으로 과거를 돌려 생존 편향(절대 수익률 부풀림).
출력: 계좌규칙_검정.csv(묶음별 12·26주 평균·중앙값·승률·건수), 계좌규칙_종목별.csv(오늘 후보가 과거 같은 조건이었을 때)
"""
import sys

import numpy as np
import pandas as pd


def rolling_beta(tickers, start='2016-01-01', idx='^NDX'):
    import yfinance as yf
    P = yf.download(sorted(set(tickers) | {idx}), start=start, auto_adjust=True, progress=False)['Close']
    R = P.pct_change(fill_method=None)
    m = R[idx]
    cov = R.drop(columns=idx).rolling(252, min_periods=120).cov(m)
    return (cov.div(m.rolling(252, min_periods=120).var(), axis=0)).resample('W-FRI').last()


def run(W, H, raw, names=(), cut=0.5):
    H = H[(H['시장'] == '미국') & (H['구분'] == '개별주')].copy()
    H['날짜'] = pd.to_datetime(H['날짜'])
    B = rolling_beta(H['ticker'].dropna().unique())
    H['베타'] = [B.at[d, t] if (d in B.index and t in B.columns) else np.nan for d, t in zip(H['날짜'], H['ticker'])]
    raw = raw.copy(); raw.index = pd.to_datetime(raw.index)
    H['나스닥점수'] = H['날짜'].map(raw)
    H = H[H['나스닥점수'].notna()]
    H['가격순위'] = H[['B13', 'B16']].mean(axis=1)
    ready = H['나스닥점수'] >= cut
    fell = H['B29'] >= 1
    rk = H['가격순위'] >= 0.5
    hb = H['베타'] >= 1.0
    G = {'전체 주(기준)': H.index == H.index,
         f'나스닥 준비 주(≥{cut})': ready,
         '준비 + 떨어짐(B29)': ready & fell,
         '준비 + 떨어짐 + 가격순위(B13·B16 ≥0.5)': ready & fell & rk,
         '준비 + 떨어짐 + 가격순위 + 베타≥1': ready & fell & rk & hb,
         '준비 + 떨어짐 + 가격순위 + 베타<1': ready & fell & rk & ~hb,
         '준비 + 떨어짐 + 베타≥1 + 주도 업종(B33)': ready & fell & hb & (H['B33'] >= 1),
         '평상 주 + 떨어짐 + 가격순위 + 베타≥1': ~ready & fell & rk & hb}
    rows = []
    for k, g in G.items():
        x = H[g]
        r = {'묶음': k, '건수': len(x), '주수': x['날짜'].nunique()}
        for c in ('12주', '26주'):
            v = pd.to_numeric(x[c], errors='coerce').dropna()
            r.update({f'{c}_평균%': round(v.mean(), 1), f'{c}_중앙%': round(v.median(), 1), f'{c}_승률%': round((v > 0).mean() * 100, 1)})
        rows.append(r)
    T = pd.DataFrame(rows)
    T['시험 못 한 것'] = '우량(B23·B25·B26)·싼가(B15)·이익전망(B24): 과거 값 없음. 생존 편향 있음'
    pick = ready & fell & hb
    N = H[pick & H['ticker'].isin(names)][['날짜', 'ticker', '종목', '나스닥점수', '베타', 'B13', 'B16', '12주', '26주']].copy()
    N['베타'] = N['베타'].round(2)
    S = N.groupby('ticker').agg(건수=('날짜', 'size'), 첫날=('날짜', lambda v: str(v.min().date())), 끝날=('날짜', lambda v: str(v.max().date())),
                                 **{'12주_평균%': ('12주', 'mean'), '26주_평균%': ('26주', 'mean')},
                                 **{'12주_승률%': ('12주', lambda v: (pd.to_numeric(v, errors='coerce').dropna() > 0).mean() * 100)}).round(1).reset_index()
    T.to_csv(f'{W}/계좌규칙_검정.csv', index=False, encoding='utf-8-sig')
    S.to_csv(f'{W}/계좌규칙_종목별.csv', index=False, encoding='utf-8-sig')
    N.to_csv(f'{W}/계좌규칙_종목별_주.csv', index=False, encoding='utf-8-sig')
    return T, S, N


if __name__ == '__main__':
    # python account_test.py <블록점수이력.csv> <바닥근접도_이력_나스닥100.csv> <출력폴더> [티커...]
    hist, rawf, W = sys.argv[1:4]
    H = pd.read_csv(hist, encoding='utf-8-sig', low_memory=False)
    R = pd.read_csv(rawf, encoding='utf-8-sig', index_col=0)['원점수']
    T, S, N = run(W, H, R, sys.argv[4:])
    pd.set_option('display.width', 250)
    print(T.drop(columns='시험 못 한 것').to_string()); print(S.to_string())
