"""AI vs 비AI 갈림 검정 (11/20 의장: "AI는 오르고 비AI는 빠지는 날, 바닥에 가까워진 건가?").

AI 묶음(SMH·XLK·IGV) ÷ 방어 묶음(XLF·XLP·XLV·XLU) 동일가중 비율(B08 ETF 근사, 유니버스 비율과 상관 0.88).
조건(전부 과거 백분위로, 손 숫자 없음):
  ① 갈림: 그날 AI 묶음 − 방어 묶음 하루 수익 차이가 지난 1년 상위 10%
  ② 그전에 AI가 크게 밀림: 비율의 60일 고점 대비 낙폭이 지난 1년 하위 20%
  ③ 나스닥100 52주 고점 대비 −10% 이하(조정장)
그날 사면 나스닥100(QQQ) 20·60·120거래일 뒤 절대 수익률·승률, 그 뒤 더 빠진 폭. 비교: 아무 날, 조정장 아무 날.
"""
import sys

import numpy as np
import pandas as pd

AI, DEF = ['SMH', 'XLK', 'IGV'], ['XLF', 'XLP', 'XLV', 'XLU']


def run(W, start='2007-01-01'):
    import yfinance as yf
    P = yf.download(AI + DEF + ['QQQ', '^NDX'], start=start, auto_adjust=True, progress=False)['Close'].ffill()
    r = P.pct_change(fill_method=None)
    spread = r[AI].mean(axis=1) - r[DEF].mean(axis=1)
    ratio = (1 + r[AI].mean(axis=1)).cumprod() / (1 + r[DEF].mean(axis=1)).cumprod()
    rdd = ratio / ratio.rolling(60).max() - 1
    pct = lambda s: s.rolling(252, min_periods=200).rank(pct=True)
    ndd = P['^NDX'] / P['^NDX'].rolling(252, min_periods=60).max() - 1
    q = P['QQQ']
    fwd = {n: (q.shift(-n) / q - 1) * 100 for n in (20, 60, 120)}
    low = pd.Series([q.iloc[i:i + 61].min() / q.iloc[i] - 1 if i + 1 < len(q) else np.nan for i in range(len(q))], index=q.index) * 100
    c1 = pct(spread) >= 0.9; c2 = pct(rdd) <= 0.2; c3 = ndd <= -0.10
    G = {'아무 날': c1 | ~c1, '조정장(나스닥 −10%)': c3, '갈림(AI 강세 상위 10%)': c1,
         '갈림 + AI 크게 밀린 뒤': c1 & c2, '갈림 + AI 밀린 뒤 + 조정장': c1 & c2 & c3}
    rows = []
    for k, g in G.items():
        g = g.fillna(False)
        row = {'묶음': k, '날수': int(g.sum())}
        for n, f in fwd.items():
            v = f[g].dropna()
            row[f'{n}일_평균%'] = round(v.mean(), 1); row[f'{n}일_승률%'] = round((v > 0).mean() * 100, 1)
        row['60일 안 더 빠진 폭 중앙%'] = round(low[g].dropna().median(), 1)
        rows.append(row)
    T = pd.DataFrame(rows)
    D = pd.DataFrame({'AI−방어 하루차%': (spread * 100).round(2), '갈림백분위': pct(spread).round(2), 'AI밀림백분위': pct(rdd).round(2),
                      '나스닥고점대비%': (ndd * 100).round(1), '뒤20일%': fwd[20].round(1), '뒤60일%': fwd[60].round(1)})
    E = D[(c1 & c2 & c3).fillna(False)]
    T.to_csv(f'{W}/AI갈림_검정.csv', index=False, encoding='utf-8-sig')
    E.to_csv(f'{W}/AI갈림_해당일.csv', encoding='utf-8-sig')
    D.tail(10).to_csv(f'{W}/AI갈림_최근.csv', encoding='utf-8-sig')
    return T, E, D.tail(5)


if __name__ == '__main__':
    pd.set_option('display.width', 250)
    T, E, L = run(sys.argv[1] if len(sys.argv) > 1 else '.')
    print(T.to_string()); print(L.to_string()); print(E.tail(25).to_string())
