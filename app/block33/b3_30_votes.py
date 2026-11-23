"""3-30 바닥 신호 집계(따로 집계, 종목점수에 섞지 않음). 11/20 의장 "다 켜면 교란? 따로 집계" → '넵'.

표준: 볼린저(2001) 다중공선성 규칙·Murphy(1999) — 같은 갈래 지표는 여러 개 세지 않는다.
→ 켜진 기법(비공개 blocks.yaml '3-30' 켜기, 나라별)을 기법 모음의 갈래(과매도·다이버전스·전환·바닥 모양·캔들·투매)로 묶고,
  갈래 안 기법 중 하나라도 최근 창(설정 '집계'.'창일') 안에 켜졌으면 그 갈래 1표. 종목마다 '표 수 / 켜진 갈래 수'.
- history(): 10년 표 수별 바닥즈음 맞힘 비율·26주 초과(코드가 표 수의 뜻을 정함) + 기법 사이 신호 겹침(갈래 안 vs 갈래 밖).
- today(): 오늘 종목별 표 수·켜진 기법 이름. 매일 블록 3 출력 '3_analysis/바닥신호집계.csv'.
  python -m analysis.b3_30_votes --data <1_data> --universe <유니버스.csv> --out <폴더>   # 10년 성적·겹침
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

from . import b3_30_ta_library as LIB
from . import b3_30_ta_test as TT


def cfg():
    return TT.private_cfg()


def on_list(C3, country):
    return [k for k in ((C3.get('켜기') or {}).get(country) or []) if k in LIB.META.index]


def groups(techs):
    g = {}
    for k in techs:
        g.setdefault(LIB.META.at[k, '갈래'], []).append(k)
    return g


def ticker_signals(C, O, H, L, V, tickers, cal):
    """종목별 신호(겹침 정리 없이 원래 켜진 날). 반환: {종목: (종가 Series, {기법: bool Series})}"""
    days = C.index[cal.reindex(C.index).fillna(False).values]
    cs = LIB.cross_section(C.loc[days], tickers)
    out = {}
    for t in tickers:
        c = C.loc[days, t].dropna()
        if len(c) < 300:
            continue
        o, h, l, v = (X.loc[c.index, t] for X in (O, H, L, V))
        sig = LIB.per_ticker(o.fillna(c), h.fillna(c), l.fillna(c), c, v.fillna(0))
        for kk in ('T10', 'T11'):
            sig[kk] = cs[kk].loc[c.index, t].astype(bool)
        out[t] = (c, sig)
    return out


def votes(sig, G, win):
    """갈래별 '최근 win일 안에 켜짐' → 표 수 Series, 갈래별 bool DataFrame."""
    gv = {}
    for g, ks in G.items():
        any_ = pd.concat([sig[k] for k in ks], axis=1).any(axis=1)
        gv[g] = any_.astype(int).rolling(win, min_periods=1).max() > 0
    D = pd.DataFrame(gv)
    return D.sum(axis=1), D


def overlap(SIG, techs, near=5):
    """기법 A가 켜진 날 앞뒤 near일 안에 기법 B도 켜진 비율(종목 전체 합)."""
    K = len(techs)
    hit = np.zeros((K, K)); tot = np.zeros(K)
    for c, sig in SIG.values():
        A = np.array([sig[k].values for k in techs])
        W = np.array([pd.Series(a).rolling(2 * near + 1, center=True, min_periods=1).max().values > 0 for a in A])
        for i in range(K):
            m = A[i]
            tot[i] += m.sum()
            hit[i] += W[:, m].sum(axis=1)
    R = hit / np.where(tot == 0, np.nan, tot)[:, None]
    return pd.DataFrame(R, index=techs, columns=techs)


def history(data, uni, out):
    C3 = cfg()
    if not C3.get('시험'):
        raise SystemExit("비공개 blocks.yaml '3-30'이 없습니다(QC_PRIVATE).")
    T = C3['시험']
    win = (C3.get('집계') or {}).get('창일', T['겹침일'])
    C, O, H, L, V, cty, cal = TT.load(data, uni)
    os.makedirs(out, exist_ok=True)
    rows, ov = [], []
    for nm in ('미국', '한국'):
        techs = on_list(C3, nm)
        if not techs:
            continue
        G = groups(techs)
        SIG = ticker_signals(C, O, H, L, V, cty[nm], cal[nm])
        recs = []
        for t, (c, sig) in SIG.items():
            n, _ = votes(sig, G, win)
            z3 = TT.zone(c, T['허용폭'][0], T['앞뒤일'], T['낙폭'])
            z1 = TT.zone(c, T['허용폭'][-1], T['앞뒤일'], T['낙폭'])
            f26 = c.shift(-126) / c - 1
            recs.append(pd.DataFrame({'표': n.values, 'z3': z3.values, 'z1': z1.values,
                                      'f26x': (f26 - f26.mean()).values * 100, 'f26': f26.values * 100}))
        R = pd.concat(recs)
        base3, base1 = R['z3'].mean(), R['z1'].mean()
        for k, g in R.groupby('표'):
            rows.append({'나라': nm, '표 수': int(k), '갈래 수': len(G), '종목·날 수': len(g),
                         '바닥즈음 3%': round(g['z3'].mean() * 100, 1), '배율 3%': round(g['z3'].mean() / base3, 2),
                         '바닥즈음 1%': round(g['z1'].mean() * 100, 1), '배율 1%': round(g['z1'].mean() / base1, 2),
                         '26주 평균': round(g['f26'].mean(), 1), '26주 오른 비율': round((g['f26'].dropna() > 0).mean() * 100, 1),
                         '26주 초과': round(g['f26x'].mean(), 2)})
        M = overlap(SIG, techs)
        gi = {k: LIB.META.at[k, '갈래'] for k in techs}
        same = [M.at[a, b] for a in techs for b in techs if a != b and gi[a] == gi[b]]
        diff = [M.at[a, b] for a in techs for b in techs if gi[a] != gi[b]]
        ov.append({'나라': nm, '갈래 안 겹침(평균)': round(np.nanmean(same) * 100, 1) if same else None,
                   '갈래 밖 겹침(평균)': round(np.nanmean(diff) * 100, 1), '갈래': ' / '.join(f'{g} {len(v)}' for g, v in G.items())})
        M.round(3).to_csv(os.path.join(out, f'바닥신호_겹침_{nm}.csv'), encoding='utf-8-sig')
    os.makedirs(out, exist_ok=True)
    A = pd.DataFrame(rows)
    A.to_csv(os.path.join(out, '바닥신호집계_성적.csv'), index=False, encoding='utf-8-sig')
    B = pd.DataFrame(ov)
    B.to_csv(os.path.join(out, '바닥신호_갈래겹침.csv'), index=False, encoding='utf-8-sig')
    print(A.to_string()); print(B.to_string())
    return A, B


def today(U, years=4):
    """오늘 종목별 바닥 신호 집계. U = 유니버스 DataFrame. 가격은 블록 1 1-1·1-6 코드 그대로(최근 years년)."""
    C3 = cfg()
    if not C3:
        return None
    U = U[~(U['yfinance 티커'].notna() & U['yfinance 티커'].duplicated())]   # 11/23: 같은 티커 두 줄이면 가격 칸이 겹쳐 멈춤
    win = (C3.get('집계') or {}).get('창일', (C3.get('시험') or {}).get('겹침일', 20))
    import tempfile
    from data import b1_1_prices as P1, b1_6_clean as P6
    d = tempfile.mkdtemp()
    U.to_csv(os.path.join(d, '유니버스.csv'), index=False, encoding='utf-8-sig')
    ctx = {'in': d, 'out': d, 'drive': False}
    P1.run(ctx, {'년': years})
    P6.run(ctx, {})
    rd = lambda f: pd.read_csv(os.path.join(d, f), index_col=0, parse_dates=True, encoding='utf-8-sig')  # noqa: E731
    C, O, H, L, V = rd('가격10년_정제.csv.gz'), rd('가격10년_시가.csv.gz'), rd('가격10년_고가.csv.gz'), \
        rd('가격10년_저가.csv.gz'), rd('거래량10년_정제.csv.gz')
    raw = rd('가격10년_종가.csv.gz')
    cal = {'미국': raw['^GSPC'].notna(), '한국': raw['^KS11'].notna()}
    name = U.set_index('yfinance 티커')['정식 종목명'].to_dict()
    rows = []
    for nm in ('미국', '한국'):
        techs = on_list(C3, nm)
        if not techs:
            continue
        G = groups(techs)
        tick = [t for t in U.loc[U['시장'] == nm, 'yfinance 티커'].dropna() if t in C.columns]
        for t, (c, sig) in ticker_signals(C, O, H, L, V, tick, cal[nm]).items():
            n, D = votes(sig, G, win)
            fired = [LIB.META.at[k, '기법'] for k in techs if sig[k].iloc[-win:].any()]
            rows.append({'시장': nm, '종목': name.get(t, t), 'ticker': t, '기준일': str(c.index[-1].date()),
                         '바닥 신호(표)': int(n.iloc[-1]), '갈래 수': len(G),
                         '켜진 갈래': ', '.join(g for g in D.columns if D[g].iloc[-1]),
                         '켜진 기법': ', '.join(fired)})
    out = pd.DataFrame(rows)
    return out.sort_values(['시장', '바닥 신호(표)'], ascending=[True, False]) if len(out) else out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data'); ap.add_argument('--universe', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--today', action='store_true')
    a = ap.parse_args()
    if a.today:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'collect'))
        os.makedirs(a.out, exist_ok=True)
        T = today(pd.read_csv(a.universe, dtype=str, encoding='utf-8-sig'))
        T.to_csv(os.path.join(a.out, '바닥신호집계.csv'), index=False, encoding='utf-8-sig')
        print(T.head(30).to_string())
    else:
        history(a.data, a.universe, a.out)


if __name__ == '__main__':
    main()
