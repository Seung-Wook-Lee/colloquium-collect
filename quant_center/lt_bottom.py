"""이번 하락의 바닥 확률 — 연구된 방법 그대로(11/21 의장: "니가 모형 만들지 말고 바닥을 찾는 모형을 가져와").

  하락 구간 판정 = Lunde & Timmermann(2004) 필터. R 패키지 bbdetection(Zakamulin, CRAN)의
                   run_filtering_alg(src/filter.cpp)를 한 줄씩 그대로 옮김.
                   고점에서 '약세 문턱'% 빠지면 하락 구간 시작, 저점에서 '강세 문턱'% 오르면 끝.
  바닥 확률     = 과거 하락 구간 중 지금만큼 이상 빠졌던 것들에서, 최종 저점이 지금 가격의 3% 안이었던 비율
                  (Lunde & Timmermann의 '낙폭·기간에 따른 하락장 종료 확률'을 표본 비율로 셈).
  그 뒤 지수    = 그 과거 하락들이 지금 낙폭에 처음 닿은 날부터 13주·26주 뒤 지수 수익률 평균·승률.
  자료          = 야후 지수 종가(S&P500 1928~, 나스닥100 1985~).

  위험률 모형(hazard, 화면·원고에 쓰는 본 숫자) = Lunde & Timmermann(2004)의 본 모형 형태:
                  하락 구간 안의 주마다 '이번 주가 최종 저점 3% 안인가'를 낙폭·기간(로그 주수)과
                  시장 상태 변수(VIX, VIX 4주 변화, 미 10년 금리 4주 변화, RSI(14), 200일선 이격, 4주 수익률)로
                  로지스틱 위험률 회귀. 해마다 그 전 자료로만 학습해 그해를 맞힘(2000~, 걸어가며 검정).
"""
import numpy as np
import pandas as pd

DEF = dict(강세_문턱=10.0, 약세_문턱=5.0, 바닥_여유=0.03)
START = {'^GSPC': '1928-01-01', '^NDX': '1985-01-01'}


def lt_filter(x, tr_bull, tr_bear):
    """bbdetection::run_filtering_alg 그대로. True = 강세(상승 구간), False = 약세(하락 구간)"""
    n = len(x); bull = np.ones(n, bool); enter = ext = 0; ins = True
    for i in range(1, n):
        if ins:
            mx = x[enter:i + 1].max()
            if (mx - x[i]) / mx * 100 > tr_bear:
                ext = i; ins = False
                ind = enter + int(np.argmax(x[enter:i + 1])); bull[ind + 1:i + 1] = False
            else:
                bull[i] = True
        else:
            mn = x[ext:i + 1].min()
            if (x[i] - mn) / mn * 100 > tr_bull:
                ins = True; enter = i
                ind = ext + int(np.argmin(x[ext:i + 1])); bull[ind + 1:i + 1] = True
            else:
                bull[i] = False
    if n > 1 and not bull[1]:
        bull[0] = False
    return bull


def episodes(s, tr_bull, tr_bear):
    """하락 구간 목록: 고점 위치·저점 위치·최종 낙폭·끝났는지"""
    x = s.values; b = lt_filter(x, tr_bull, tr_bear); out = []; i = 0; n = len(x)
    while i < n:
        if b[i]:
            i += 1; continue
        j = i
        while j < n and not b[j]:
            j += 1
        pk = max(i - 1, 0); lo = i + int(np.argmin(x[i:j]))
        out.append(dict(pk=pk, lo=lo, dd=x[lo] / x[pk] - 1, done=j < n))
        i = j
    return pd.DataFrame(out)


def prob(s, cfg=None):
    """s: 일별 지수 종가(오래된 것부터). 돌려줌: dict(하락중, 지금낙폭, 비교수, 확률, 최종낙폭_중앙값, 뒤13주_평균, 뒤13주_승률, 뒤26주_평균, 뒤26주_승률)"""
    C = {**DEF, **(cfg or {})}
    s = s.dropna(); x = s.values
    E = episodes(s, C['강세_문턱'], C['약세_문턱'])
    if not len(E) or E.iloc[-1]['done']:
        return dict(하락중=False)
    cur = E.iloc[-1]; dd = x[-1] / x[int(cur.pk)] - 1
    P = E[E['done'] & (E['dd'] <= dd + 1e-12)]
    r13, r26 = [], []
    for _, e in P.iterrows():
        pk, lo = int(e.pk), int(e.lo)
        hit = pk + int(np.argmax(x[pk:lo + 1] / x[pk] - 1 <= dd + 1e-12))   # 지금 낙폭에 처음 닿은 날
        if hit + 63 < len(x): r13.append(x[hit + 63] / x[hit] - 1)
        if hit + 126 < len(x): r26.append(x[hit + 126] / x[hit] - 1)
    f = lambda a: (round(float(np.mean(a)) * 100, 1), round(float(np.mean(np.array(a) > 0)) * 100, 1)) if a else (np.nan, np.nan)
    (a13, w13), (a26, w26) = f(r13), f(r26)
    return dict(하락중=True, 고점일=str(s.index[int(cur.pk)].date()), 지금낙폭=round(dd * 100, 1), 비교수=len(P),
                확률=round(float(((1 + P['dd']) >= (1 + dd) * (1 - C['바닥_여유'])).mean()) * 100, 1),
                최종낙폭_중앙값=round(float(P['dd'].median()) * 100, 1),
                뒤13주_평균=a13, 뒤13주_승률=w13, 뒤26주_평균=a26, 뒤26주_승률=w26)


def today(idx_list=('^NDX', '^GSPC'), cfg=None):
    import yfinance as yf
    rows = []
    for t in idx_list:
        s = yf.download(t, start=START.get(t, '1985-01-01'), auto_adjust=True, progress=False)['Close'].squeeze()
        rows.append({'기준지수': t, '날짜': str(s.dropna().index[-1].date()), **prob(s, cfg)})
    return pd.DataFrame(rows)


HZ_F = ['낙폭', 'log주수', 'VIX', 'VIX_4주변화', '10년_4주변화', 'RSI', '200일선_이격', '4주_수익']


def _rsi(x, n=14):
    d = x.diff(); u = d.clip(lower=0).ewm(alpha=1 / n).mean(); v = (-d.clip(upper=0)).ewm(alpha=1 / n).mean()
    return 100 - 100 / (1 + u / v)


def hazard_weeks(s, vix, tnx, cfg=None):
    """하락 구간 안의 주(금요일) 표: 입력 변수 + 정답 y(끝난 하락만, 최종 저점 3% 안이면 1)"""
    C = {**DEF, **(cfg or {})}
    s = s.dropna(); x = s.values
    E = episodes(s, C['강세_문턱'], C['약세_문턱'])
    ph = np.full(len(x), -1); pk = np.full(len(x), np.nan); fin = np.full(len(x), np.nan); done = np.zeros(len(x), bool)
    for k, e in E.iterrows():
        a = int(e.pk) + 1; b = int(e.lo) if e.done else len(x) - 1
        ph[a:b + 1] = k; pk[a:b + 1] = x[int(e.pk)]; fin[a:b + 1] = x[int(e.lo)]; done[a:b + 1] = bool(e.done)
    D = pd.DataFrame({'px': s, 'ph': ph, 'pk': pk, 'fin': fin, 'done': done}, index=s.index)
    D['낙폭'] = (D.px / D.pk - 1) * 100
    first = D[D.ph >= 0].groupby('ph').apply(lambda g: g.index[0])
    D['주수'] = [((i - first[p]).days / 7 + 1) if p >= 0 else np.nan for i, p in zip(D.index, D.ph)]
    v = vix.reindex(s.index).ffill(); D['VIX'] = v; D['VIX_4주변화'] = v - v.shift(20)
    D['10년_4주변화'] = tnx.reindex(s.index).ffill().diff(20)
    D['RSI'] = _rsi(s); D['200일선_이격'] = (s / s.rolling(200).mean() - 1) * 100; D['4주_수익'] = s.pct_change(20) * 100
    D['뒤13주'] = (s.shift(-63) / s - 1) * 100; D['뒤26주'] = (s.shift(-126) / s - 1) * 100
    W = D.resample('W-FRI').last()
    W = W[W.ph >= 0].copy()
    W['y'] = np.where(W.done, (W.px <= W.fin * (1 + C['바닥_여유'])).astype(float), np.nan)
    W['log주수'] = np.log(W['주수'])
    return W.dropna(subset=HZ_F)


def hazard(s, vix, tnx, cfg=None, start_year=2000):
    """돌려줌: (오늘 한 줄 dict, 검정 dict). 오늘이 하락 구간이 아니면 하락중=False"""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.preprocessing import StandardScaler
    W = hazard_weeks(s, vix, tnx, cfg)
    s = s.dropna(); live = len(W) and W.index[-1] >= s.index[-1] - pd.Timedelta(days=6)
    fit = lambda m: (StandardScaler().fit(W.loc[m, HZ_F]),)
    raw = pd.Series(np.nan, index=W.index)
    for yr in range(start_year, W.index[-1].year + 1):
        tr = (W.index.year < yr) & W.y.notna(); te = W.index.year == yr
        if te.sum() == 0 or W.y[tr].sum() < 5:
            continue
        sc = StandardScaler().fit(W.loc[tr, HZ_F]); lr = LogisticRegression(C=1.0, max_iter=3000).fit(sc.transform(W.loc[tr, HZ_F]), W.loc[tr, 'y'])
        raw[te] = lr.predict_proba(sc.transform(W.loc[te, HZ_F]))[:, 1]
    ev = W.y.notna() & raw.notna(); y, p = W.y[ev], raw[ev]
    TEST = dict(검정기간=f'{start_year}~', 검정주=int(len(y)), 바닥주=int(y.sum()), AUC=round(roc_auc_score(y, p), 3),
                브라이어_기술점수=round(1 - brier_score_loss(y, p) / brier_score_loss(y, np.full(len(y), y.mean())), 3))
    if not live:
        return dict(하락중=False), TEST
    r = W.iloc[-1]; p0 = float(raw.iloc[-1])
    near = raw[ev | (raw.notna() & W.done)].dropna()
    near = near[(near - p0).abs() <= 0.1].index
    f13, f26 = W.loc[near, '뒤13주'].dropna(), W.loc[near, '뒤26주'].dropna()
    ONE = dict(하락중=True, 확률=round(p0 * 100, 1), 지금낙폭=round(r['낙폭'], 1), 주수=int(r['주수']), VIX=round(r['VIX'], 1), RSI=round(r['RSI'], 1),
               비슷한확률_주수=int(len(near)), 뒤13주_평균=round(f13.mean(), 1), 뒤13주_승률=round((f13 > 0).mean() * 100, 1),
               뒤26주_평균=round(f26.mean(), 1), 뒤26주_승률=round((f26 > 0).mean() * 100, 1))
    return ONE, TEST


def hazard_today(idx_list=('^NDX', '^GSPC'), cfg=None):
    import yfinance as yf
    P = yf.download(list(idx_list) + ['^VIX', '^TNX'], start='1985-01-01', auto_adjust=True, progress=False)['Close']
    rows = []
    for t in idx_list:
        one, test = hazard(P[t], P['^VIX'], P['^TNX'], cfg)
        rows.append({'기준지수': t, '날짜': str(P[t].dropna().index[-1].date()), **one, **{f'검정_{k}': v for k, v in test.items()}})
    return pd.DataFrame(rows)


if __name__ == '__main__':
    import sys
    T = hazard_today()
    print(T.T.to_string())
    if len(sys.argv) > 1:
        T.to_csv(f'{sys.argv[1]}/바닥확률.csv', index=False, encoding='utf-8-sig')
