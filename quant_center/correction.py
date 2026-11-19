"""조정 단계표 (11/20 의장: "하락폭 5%·10%·15%를 단계로, 1년에 조정 몇 번, 레버리지로 더 잦고 깊다").

S&P500(1928~)·나스닥100(1985~) 종가로 고점 대비 조정을 자동으로 센다.
- 조정 = 고점에서 내려가 새 고점을 다시 넘을 때까지 한 덩어리. 가장 깊은 낙폭을 그 조정의 깊이로 본다.
- 단계마다: 1년 평균 횟수(전체·최근 10년·그 이전), 다음 단계까지 더 빠질 확률,
  그 단계에 처음 닿은 날 샀을 때 13·26주 절대수익률·승률, 산 뒤 더 빠진 폭.
- 변동성 배수: 낙폭 ÷ 고점 당시 1년 연율 변동성. 변동성이 큰 시기의 −10%와 조용한 시기의 −10%를 같은 자로 잰다.
- 표시만 한다. 바닥 근접도 모형(bottom.py)은 바꾸지 않는다.
"""
import sys

import numpy as np
import pandas as pd

DEF = dict(단계=[5, 10, 15, 20, 30], 배수=[0.3, 0.6, 0.9, 1.2, 1.8], 최근해=10)
START = {'^GSPC': '1927-12-01', '^NDX': '1985-10-01', '^KS11': '1996-07-01', '^KQ11': '1996-07-01'}
NAME = {'^GSPC': 'S&P500', '^NDX': '나스닥100', '^KS11': '코스피', '^KQ11': '코스닥'}


def prices(idx):
    import yfinance as yf
    return yf.download(idx, start=START.get(idx, '1985-01-01'), auto_adjust=True, progress=False)['Close'].squeeze().dropna()


def episodes(p):
    """고점→새 고점까지를 한 조정으로. 끝나지 않은 조정은 진행중=1."""
    peak = p.cummax(); dd = p / peak - 1
    vol = np.log(p).diff().rolling(252, min_periods=120).std() * np.sqrt(252)
    grp = (dd == 0).cumsum()
    out = []
    for _, g in dd.groupby(grp):
        g = g[g < 0]
        if g.empty:
            continue
        pk = p.index[p.index.get_loc(g.index[0]) - 1]
        out.append(dict(고점일=pk, 저점일=g.idxmin(), 깊이=-g.min() * 100, 고점변동성=float(vol.get(pk, np.nan)) * 100,
                        회복일=None if g.index[-1] == p.index[-1] else g.index[-1], 진행중=int(g.index[-1] == p.index[-1])))
    E = pd.DataFrame(out)
    E['배수'] = E['깊이'] / E['고점변동성']
    return E, dd


def first_cross(dd, E, lv, col='깊이', vol=None):
    """각 조정에서 그 단계(lv)에 처음 닿은 날."""
    days = []
    for _, e in E[E[col] >= lv].iterrows():
        seg = dd[e['고점일']:(e['회복일'] or dd.index[-1])]
        x = -seg * 100 if col == '깊이' else -seg * 100 / e['고점변동성']
        days.append(x[x >= lv].index[0])
    return days


def table(p, E, dd, cfg, col='깊이'):
    levels = cfg['단계'] if col == '깊이' else cfg['배수']
    yrs = (p.index[-1] - p.index[0]).days / 365.25
    cut = p.index[-1] - pd.DateOffset(years=cfg['최근해'])
    old_yrs = (cut - p.index[0]).days / 365.25
    rows = []
    for i, lv in enumerate(levels):
        hit = E[E[col] >= lv]; done = hit[hit['진행중'] == 0]
        nxt = levels[i + 1] if i + 1 < len(levels) else None
        cr = first_cross(dd, E, lv, col)
        f13 = pd.Series([p.iloc[min(p.index.get_loc(d) + 63, len(p) - 1)] / p[d] - 1 if p.index.get_loc(d) + 63 < len(p) else np.nan for d in cr]) * 100
        f26 = pd.Series([p.iloc[p.index.get_loc(d) + 126] / p[d] - 1 if p.index.get_loc(d) + 126 < len(p) else np.nan for d in cr]) * 100
        more = pd.Series([(p[d:(e['회복일'] or p.index[-1])].min() / p[d] - 1) * 100 for d, (_, e) in zip(cr, hit.iterrows())])
        tag = f'−{lv}%' if col == '깊이' else f'{lv}배'
        rows.append({'단계': i + 1, '낙폭': tag, '횟수': len(hit), '1년_평균횟수': round(len(hit) / yrs, 2),
                     f'최근{cfg["최근해"]}년_1년횟수': round((hit['고점일'] >= cut).sum() / cfg['최근해'], 2),
                     '그이전_1년횟수': round((hit['고점일'] < cut).sum() / old_yrs, 2),
                     '다음단계': (f'−{nxt}%' if col == '깊이' else f'{nxt}배') if nxt else '',
                     '다음단계까지_갈확률(%)': round((done[col] >= nxt).mean() * 100, 1) if nxt and len(done) else np.nan,
                     '처음닿은날_사면_13주평균(%)': round(f13.mean(), 1), '13주_승률(%)': round((f13.dropna() > 0).mean() * 100, 1),
                     '처음닿은날_사면_26주평균(%)': round(f26.mean(), 1), '26주_승률(%)': round((f26.dropna() > 0).mean() * 100, 1),
                     '산뒤_더빠진폭_중앙값(%)': round(more.median(), 1), '산뒤_더빠진폭_최악(%)': round(more.min(), 1),
                     '저점까지_걸린날_중앙값': int(pd.Series([(e['저점일'] - e['고점일']).days for _, e in done.iterrows()]).median()) if len(done) else np.nan})
    return pd.DataFrame(rows)


def run(W, idx='^GSPC', cfg=None, p=None):
    C = {**DEF, **(cfg or {})}
    p = prices(idx) if p is None else p
    E, dd = episodes(p)
    T = table(p, E, dd, C); TV = table(p, E, dd, C, '배수')
    now = E.iloc[-1] if E.iloc[-1]['진행중'] else None
    cur = -dd.iloc[-1] * 100
    lv = [x for x in C['단계'] if cur >= x]
    st = len(lv)
    vol_now = float(np.log(p).diff().tail(252).std() * np.sqrt(252) * 100)
    mult = cur / (now['고점변동성'] if now is not None else vol_now)
    name = NAME.get(idx, idx)
    if st == 0:
        msg = f'{name} 고점 대비 −{cur:.1f}%, 조정 단계 아님(5% 미만). 5% 조정은 1년 평균 {T.iloc[0]["1년_평균횟수"]}번.'
    else:
        r = T.iloc[st - 1]
        msg = (f'{name} {st}단계(−{lv[-1]}%) 조정: 고점 대비 −{cur:.1f}%(변동성 {mult:.2f}배), 이번 조정 최저 −{now["깊이"]:.1f}%. '
               f'과거 −{lv[-1]}% 조정 {r["횟수"]}번(1년 {r["1년_평균횟수"]}번, 최근 {C["최근해"]}년 {r[f"최근{C["최근해"]}년_1년횟수"]}번)'
               + (f', {r["다음단계"]}까지 간 확률 {r["다음단계까지_갈확률(%)"]}%' if r['다음단계'] else '')
               + f'. 처음 −{lv[-1]}% 닿은 날 샀으면 13주 평균 {r["처음닿은날_사면_13주평균(%)"]:+.1f}%(승률 {r["13주_승률(%)"]}%), '
               f'26주 {r["처음닿은날_사면_26주평균(%)"]:+.1f}%(승률 {r["26주_승률(%)"]}%), 산 뒤 더 빠진 폭 중앙값 {r["산뒤_더빠진폭_중앙값(%)"]}%.')
    ONE = pd.DataFrame([dict(기준지수=idx, 날짜=p.index[-1].date(), 고점일=None if now is None else now['고점일'].date(),
                             고점대비=round(-cur, 1), 이번조정_최저=None if now is None else round(-now['깊이'], 1),
                             단계=st, 변동성배수=round(mult, 2), 연변동성=round(vol_now, 1), 문장=msg)])
    L = E[E['깊이'] >= C['단계'][0]].copy()
    for c in ('고점일', '저점일', '회복일'):
        L[c] = pd.to_datetime(L[c]).dt.date
    L[['깊이', '고점변동성', '배수']] = L[['깊이', '고점변동성', '배수']].round(2)
    tag = '' if idx == '^GSPC' else '_' + NAME.get(idx, idx.strip('^'))
    for k, v in (('조정단계_오늘', ONE), ('조정단계표', T), ('조정단계표_변동성배수', TV), ('조정목록', L)):
        v.to_csv(f'{W}/{k}{tag}.csv', index=False, encoding='utf-8-sig')
    print(msg)
    return ONE, T, TV


if __name__ == '__main__':
    W = sys.argv[1] if len(sys.argv) > 1 else '.'
    for i in (sys.argv[2:] or ['^GSPC', '^NDX', '^KS11', '^KQ11']):
        run(W, i)
