"""종목 진단 — 블록33을 쓰는 순서(11/21 의장).

질문 "지금 ○○를 사도 되나? 26주·52주 뒤는?"에 이 순서로 답한다. 회의 원고와는 별개.
  1 시장   : 기준지수가 이번 하락의 바닥일 확률(Lunde & Timmermann, market/lt_bottom.py), 지수 고점 대비 낙폭, VIX
  2 종목   : 52주 고점 대비 낙폭(변동성 단위 포함), 200일선 위치, 12-1개월 모멘텀, RSI, TTM PER과 자기 역사 속 백분위
  3 비슷한 때: 이 종목의 과거(2015~1년 전)에서 지금과 낙폭·200일선·모멘텀이 비슷했던 날을 모아
             26주·52주 뒤 수익률(평균·중앙·승률)과 그 사이 추가로 더 빠진 폭(중앙·하위 25%)
  4 판정   : 비공개 blocks.yaml '진단' 문턱으로 '지금 사도 좋다 / 아직 더 떨어질 수 있다 / 사지 않는다' 중 하나와 근거
쓰기: python app/diagnose/run.py GOOGL MSFT MRVL JNJ JPM [--out 폴더]
출력: 화면 + <out>/진단_YYYYMMDD.md·.csv
"""
import argparse
import datetime as dt
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path[:0] = [APP, os.path.join(APP, 'block33'), os.path.join(APP, 'market')]
import qc_config as QCC  # noqa: E402

NAMES = {'GOOGL': '알파벳(구글)', 'MSFT': '마이크로소프트', 'MRVL': '마벨 테크놀로지', 'JNJ': '존슨앤존슨', 'JPM': 'JP모건'}


def cfg():
    B = QCC.load_blocks(switches=False)
    if '진단' not in B:
        raise SystemExit("비공개 blocks.yaml에 '진단' 문턱이 없습니다.")
    return B['진단']


def rsi(s, n=14):
    d = s.diff(); u = d.clip(lower=0).ewm(alpha=1 / n).mean(); v = (-d.clip(upper=0)).ewm(alpha=1 / n).mean()
    return 100 - 100 / (1 + u / v)


def bench(s, P):
    """기준지수 = 최근 3년 일간 수익률로 가장 잘 설명되는 지수(나스닥100·S&P500·반도체 SOXX 중 결정계수 최대)."""
    r = s.pct_change().iloc[-756:]
    r2 = {b: r.corr(P[b].reindex(r.index).pct_change()) ** 2 for b in ('^NDX', '^GSPC', 'SOXX')}
    best = max(r2, key=r2.get)
    return best if r2[best] > r2['^GSPC'] + 0.05 else '^GSPC'   # 뚜렷이 낫지 않으면 S&P500


def ttm_pe(tk, s):
    import yfinance as yf
    try:
        E = yf.Ticker(tk).get_earnings_dates(limit=60)
    except Exception:   # noqa: BLE001
        return pd.Series(np.nan, index=s.index)
    E = E.dropna(subset=['Reported EPS']).copy()
    E.index = pd.to_datetime(E.index, utc=True).tz_localize(None).normalize()
    E = E[~E.index.duplicated()].sort_index()
    ttm = E['Reported EPS'].rolling(4).sum().reindex(s.index.union(E.index)).ffill().reindex(s.index)
    pe = s / ttm
    return pe.where(ttm > 0)


def state(s, b, vix, pe):
    r = s.pct_change()
    D = pd.DataFrame(index=s.index)
    D['dd52'] = s / s.rolling(252, min_periods=200).max() - 1
    D['ddv'] = D['dd52'] / (r.rolling(252).std() * np.sqrt(252))
    D['x200'] = s / s.rolling(200).mean() - 1
    D['mom'] = s.shift(21) / s.shift(252) - 1
    D['rsi'] = rsi(s)
    D['bdd'] = b / b.rolling(252, min_periods=200).max() - 1
    D['vix'] = vix
    D['pe'] = pe
    D['f26'] = s.shift(-126) / s - 1
    D['f52'] = s.shift(-252) / s - 1
    D['lo26'] = s[::-1].rolling(126, min_periods=126).min()[::-1].shift(-1) / s - 1
    return D


def analog(H, m, label, min_ep):
    x = H[m].dropna(subset=['f26'])
    if not len(x):
        return dict(조건=label, 날수=0, 사건수=0)
    ep = 1 + int(((x.index[1:] - x.index[:-1]).days > 30).sum())
    x52 = x.dropna(subset=['f52'])
    out = dict(조건=label, 날수=len(x), 사건수=ep,
               평균26=x.f26.mean() * 100, 중앙26=x.f26.median() * 100, 승률26=(x.f26 > 0).mean() * 100,
               평균52=x52.f52.mean() * 100 if len(x52) else np.nan, 중앙52=x52.f52.median() * 100 if len(x52) else np.nan,
               승률52=(x52.f52 > 0).mean() * 100 if len(x52) else np.nan,
               추가하락중앙=x.lo26.median() * 100, 추가하락하위25=x.lo26.quantile(0.25) * 100)
    out['충분'] = ep >= min_ep[0] and len(x) >= min_ep[1] and len(x52) >= 20
    return out


def diagnose(tk, P, MKT, C):
    import yfinance as yf
    try:
        info = yf.Ticker(tk).info
    except Exception:   # noqa: BLE001
        info = {}
    s = P[tk].dropna()
    bm = bench(s, P)
    b = P[bm].reindex(s.index).ffill()
    D = state(s, b, P['^VIX'].reindex(s.index).ffill(), ttm_pe(tk, s))
    now = D.iloc[-1]
    H = D.loc[:s.index[-1] - pd.Timedelta(days=366)].loc['2015-06':]
    pep = (D['pe'].loc['2015':].dropna() <= now.pe).mean() * 100 if pd.notna(now.pe) else np.nan
    tol = C['낙폭_폭'] / 100
    near = (H.dd52 - now.dd52).abs() <= tol
    same200 = (H.x200 < 0) == (now.x200 < 0)
    samemom = (H.mom < 0) == (now.mom < 0)
    rows = [analog(H, pd.Series(True, index=H.index), '모든 날(기준)', (1, 1)),
            analog(H, near, f'52주 고점 대비 {now.dd52 * 100:.0f}% ±{C["낙폭_폭"]}%p', (C['최소사건'], C['최소날수'])),
            analog(H, near & same200, f'+ 200일선 {"아래" if now.x200 < 0 else "위"}', (C['최소사건'], C['최소날수'])),
            analog(H, near & same200 & samemom, f'+ 12-1개월 모멘텀 {"마이너스" if now.mom < 0 else "플러스"}', (C['최소사건'], C['최소날수']))]
    # 가장 좁으면서 사건이 충분한 조건을 판정에 쓴다
    use = next((r for r in reversed(rows[1:]) if r.get('충분')), None)
    thin = use is None
    if thin:   # 비슷했던 때가 모자라면 판정을 보류하고 가장 넓은 조건을 보여 준다
        use = rows[1] if rows[1].get('날수') and pd.notna(rows[1].get('승률52')) else rows[0]
    # 판정
    good = (use['승률52'] >= C['좋음_52주승률'] and use['중앙52'] >= C['좋음_52주중앙'])
    bad = (use['승률52'] < C['나쁨_52주승률'] or use['중앙52'] < C['나쁨_52주중앙'])
    deep = use['추가하락중앙'] < -C['추가하락_허용']
    dear = pd.notna(pep) and pep > C['비쌈_PER백분위']
    # 시장 관문은 보수적으로: 나스닥100·S&P500 중 하락 중이면서 바닥 확률이 더 낮은 쪽(11/21 하루 1억 손실 뒤)
    down = [(k, v) for k, v in MKT.items() if v.get('하락중') in (True, 'True', 1)]
    mbm, mk = min(down, key=lambda kv: kv[1].get('확률') or 0) if down else ('^GSPC', MKT.get('^GSPC') or {})
    mkt_bad = mk.get('하락중') and (mk.get('확률') or 0) < C['시장_바닥확률_준비']
    if thin:
        verdict = '판단 보류 — 과거에 비슷했던 때가 적음'
    elif bad:
        verdict = '사지 않는다'
    elif good and not deep and not dear and not mkt_bad:
        verdict = '지금 사도 좋다(나눠서)'
    elif good:
        verdict = '아직 더 떨어질 수 있다 — 나눠서 천천히'
    else:
        verdict = '아직 더 떨어질 수 있다 — 기다린다'
    why = []
    why.append(f"과거 비슷했던 때({use['조건']}, {use['사건수']}번·{use['날수']}일): 52주 뒤 중앙 {use['중앙52']:+.1f}%·승률 {use['승률52']:.0f}%, "
               f"26주 뒤 중앙 {use['중앙26']:+.1f}%·승률 {use['승률26']:.0f}%")
    why.append(f"그 사이 추가로 더 빠진 폭: 중앙 {use['추가하락중앙']:.1f}%, 나쁜 쪽(하위 25%) {use['추가하락하위25']:.1f}%")
    if pd.notna(now.pe):
        why.append(f"TTM PER {now.pe:.1f}배 = 2015년 이후 하위 {pep:.0f}%" + (' (비싼 쪽)' if dear else ''))
    if mk:
        why.append(f"시장({mbm}): " + (f"이번 하락의 바닥일 확률 {mk.get('확률')}%, 고점 대비 {mk.get('지금낙폭')}%" if mk.get('하락중') else '하락 구간 아님')
                   + f", VIX {now.vix:.1f}")
    st = {'가격': round(s.iloc[-1], 2), '52주 고점 대비%': round(now.dd52 * 100, 1), '변동성 단위 낙폭': round(now.ddv, 2),
          '200일선 대비%': round(now.x200 * 100, 1), '12-1개월 모멘텀%': round(now.mom * 100, 1), 'RSI14': round(now.rsi),
          'TTM PER': round(now.pe, 1) if pd.notna(now.pe) else None, 'PER 백분위(2015~)': round(pep) if pd.notna(pep) else None}
    return dict(종목=tk, 이름=info.get('shortName') or NAMES.get(tk, tk), 기준지수=bm, 판정=verdict, 근거=why, 상태=st, 비슷한때=rows)


def market(bms):
    import lt_bottom as LB
    T = LB.hazard_today(idx_list=tuple(x for x in bms if x in ('^NDX', '^GSPC')) or ('^GSPC',))
    return {r['기준지수']: r.to_dict() for _, r in T.iterrows()}


def render(res, day):
    L = [f'# 종목 진단 {day}', '', '순서: 1 시장 → 2 종목 상태 → 3 과거 비슷했던 때(26주·52주 뒤) → 4 판정. 숫자는 코드 계산, 판정 문턱은 비공개 규칙.', '']
    for r in res:
        L += [f"## {r['이름']} ({r['종목']}) — {r['판정']}", '']
        L += [f'- {w}' for w in r['근거']]
        L += ['', '| 지금 | 값 |', '|---|---|'] + [f'| {k} | {v} |' for k, v in r['상태'].items()]
        L += ['', '| 과거 비슷했던 때 | 사건 | 26주 중앙 | 26주 승률 | 52주 중앙 | 52주 승률 | 추가 하락 중앙 | 하위 25% |', '|---|---|---|---|---|---|---|---|']
        for a in r['비슷한때']:
            if not a.get('날수'):
                L.append(f"| {a['조건']} | 0 | | | | | | |"); continue
            L.append(f"| {a['조건']} | {a['사건수']} | {a['중앙26']:+.1f}% | {a['승률26']:.0f}% | {a['중앙52']:+.1f}% | {a['승률52']:.0f}% | {a['추가하락중앙']:.1f}% | {a['추가하락하위25']:.1f}% |")
        L.append('')
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tickers', nargs='+')
    ap.add_argument('--out', default=os.path.join(HERE, 'out'))
    a = ap.parse_args()
    import yfinance as yf
    C = cfg()
    bms = ['^NDX', '^GSPC', 'SOXX', '^VIX']
    P = yf.download(a.tickers + bms, start='2013-01-01', auto_adjust=True, progress=False)['Close'].ffill()
    MKT = market(bms)
    res = [diagnose(t, P, MKT, C) for t in a.tickers]
    day = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime('%Y%m%d')
    os.makedirs(a.out, exist_ok=True)
    md = render(res, day)
    open(os.path.join(a.out, f'진단_{day}.md'), 'w', encoding='utf-8').write(md)
    pd.DataFrame([{'종목': r['종목'], '판정': r['판정'], **r['상태']} for r in res]).to_csv(os.path.join(a.out, f'진단_{day}.csv'), index=False, encoding='utf-8-sig')
    print(md)


if __name__ == '__main__':
    main()
