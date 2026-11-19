"""시장 과열 검정 (11/20 의장: "많이 올랐어, 분위기도 과열이니 조금 팔아 현금화할 때" 같은 판단이 매일 나와야 한다 — 단계적으로 검정해서).

지수 일봉으로 과열 신호마다, 그리고 신호 개수(과열 점수)마다 '그날 산(=안 판) 사람'의 뒤 20·60·120·250거래일 절대 수익률·승률과
뒤 60일 안 최대 낙폭을 아무 날과 비교한다. 과열 날 뒤 수익이 아무 날보다 확실히 나쁘고 낙폭이 깊어야 '현금화' 규칙으로 쓸 수 있다.
- 신호: 50일 이격 ≥ 108, 일봉 RSI(14) ≥ 70, 200일 이격 ≥ 115, 1년 수익 ≥ 30%, 3달 수익 ≥ 15%, VIX ≤ 15.5(미국만, B02 문턱)
- 사건(첫날): 신호가 20거래일 꺼져 있다가 켜진 날만 따로 센다(겹침 줄임).
출력: 과열_검정{_지수}.csv, 과열_오늘{_지수}.csv
"""
import sys

import numpy as np
import pandas as pd

START = {'^GSPC': '1950-01-01', '^NDX': '1985-10-01', '^KS11': '1996-07-01', '^KQ11': '1996-07-01'}
NAME = {'^GSPC': 'S&P500', '^NDX': '나스닥100', '^KS11': '코스피', '^KQ11': '코스닥'}
H = (20, 60, 120, 250)


def rsi(p, n=14):
    d = p.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def signals(p, vix=None):
    S = pd.DataFrame(index=p.index)
    S['50일 이격 ≥ 108'] = p / p.rolling(50).mean() * 100 >= 108
    S['일봉 RSI ≥ 70'] = rsi(p) >= 70
    S['200일 이격 ≥ 115'] = p / p.rolling(200).mean() * 100 >= 115
    S['1년 수익 ≥ 30%'] = p / p.shift(252) - 1 >= 0.30
    S['3달 수익 ≥ 15%'] = p / p.shift(63) - 1 >= 0.15
    if vix is not None:
        v = vix.reindex(p.index).ffill()
        S['VIX ≤ 15.5'] = (v <= 15.5).where(v.notna(), False)
    S = S.where(p.rolling(252).count() >= 252, False)
    return S


def fwd(p):
    F = pd.DataFrame({f'{h}일%': (p.shift(-h) / p - 1) * 100 for h in H})
    lo = p[::-1].rolling(60, min_periods=1).min()[::-1].shift(-1)
    F['60일안_최대낙폭%'] = (lo / p - 1) * 100
    return F


def first_days(m, gap=20):
    off = (~m).rolling(gap, min_periods=gap).sum().shift(1) == gap
    return m & off


def row(name, m, F):
    x = F[m]
    r = {'신호': name, '날수': int(m.sum())}
    for h in H:
        v = x[f'{h}일%'].dropna()
        r[f'{h}일_평균%'] = round(v.mean(), 2); r[f'{h}일_승률%'] = round((v > 0).mean() * 100, 1)
    r['60일안_최대낙폭_중앙%'] = round(x['60일안_최대낙폭%'].median(), 1)
    r['60일안_−10%이상_빠질확률%'] = round((x['60일안_최대낙폭%'] <= -10).mean() * 100, 1)
    return r


def run(W, idx='^NDX'):
    import yfinance as yf
    p = yf.download(idx, start=START.get(idx, '1990-01-01'), auto_adjust=True, progress=False)['Close'].squeeze().dropna()
    vix = None
    if idx in ('^GSPC', '^NDX'):
        vix = yf.download('^VIX', start='1990-01-01', auto_adjust=True, progress=False)['Close'].squeeze().dropna()
    S = signals(p, vix)
    F = fwd(p)
    ok = S.index[p.rolling(252).count() >= 252]
    S, F2 = S.loc[ok], F.loc[ok]
    n = S.sum(axis=1)
    rows = [row('아무 날(기준)', pd.Series(True, index=ok), F2)]
    for c in S.columns:
        rows.append(row(c, S[c], F2))
        rows.append(row(c + ' (첫날만)', first_days(S[c]), F2))
    for k in range(1, S.shape[1] + 1):
        m = n >= k
        if m.sum() >= 20:
            rows.append(row(f'과열 점수 ≥ {k}', m, F2))
            rows.append(row(f'과열 점수 ≥ {k} (첫날만)', first_days(m), F2))
    T = pd.DataFrame(rows)
    base = T.iloc[0]
    T['120일_기준대비%p'] = (T['120일_평균%'] - base['120일_평균%']).round(2)
    T['250일_기준대비%p'] = (T['250일_평균%'] - base['250일_평균%']).round(2)
    T.insert(0, '지수', NAME.get(idx, idx))
    today = S.iloc[-1]
    ONE = pd.DataFrame([{'지수': NAME.get(idx, idx), '날짜': S.index[-1].date(), '과열 점수': int(today.sum()), '켜진 신호': ', '.join(S.columns[today]) or '없음',
                         '50일 이격': round(float(p.iloc[-1] / p.rolling(50).mean().iloc[-1] * 100), 1), 'RSI': round(float(rsi(p).iloc[-1]), 1),
                         '200일 이격': round(float(p.iloc[-1] / p.rolling(200).mean().iloc[-1] * 100), 1)}])
    tag = '' if idx == '^GSPC' else '_' + NAME.get(idx, idx)
    T.to_csv(f'{W}/과열_검정{tag}.csv', index=False, encoding='utf-8-sig')
    ONE.to_csv(f'{W}/과열_오늘{tag}.csv', index=False, encoding='utf-8-sig')
    return T, ONE


if __name__ == '__main__':
    pd.set_option('display.width', 300); pd.set_option('display.max_columns', 30)
    W = sys.argv[1] if len(sys.argv) > 1 else '.'
    for i in (sys.argv[2:] or ['^GSPC', '^NDX', '^KS11', '^KQ11']):
        T, ONE = run(W, i)
        print(ONE.to_string()); print(T.to_string())
