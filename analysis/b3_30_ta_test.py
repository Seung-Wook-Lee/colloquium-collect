"""3-30 기법 시험: 미국·한국 따로, 10년 1_data 정제 가격으로 '바닥즈음' 맞힘을 잰다.

표준: Sullivan·Timmermann·White(1999) 데이터 뒤지기 검사, Aronson(2006) 증거 기반 기술적 분석.
- 바닥즈음(정답) = 종가가 앞뒤 13주(65거래일) 최저 종가의 허용폭(3%, 1%) 안 + 52주 최고 종가보다 5% 이상 아래
  (quant_center/bottom.py 정답 규칙을 일봉에 그대로).
- 맞힘 비율 = 신호 가운데 바닥즈음에서 나온 비율. 기준 비율 = 아무 날이나 바닥즈음일 비율. 배율 = 맞힘 ÷ 기준.
- 잡은 비율 = 바닥즈음 구간(연속된 날) 가운데 신호가 한 번이라도 나온 비율.
- 보조: 4·12·26·52주 뒤 수익, 같은 종목 아무 날 대비 초과.
- 운인지: 종목마다 신호 날짜를 통째로 무작위로 밀어(간격 유지) 다시 센다. 개별 p → Benjamini·Hochberg,
  여러 기법 중 최고가 우연인지 = 최댓값 검사(White 리얼리티 체크와 같은 생각, Romano·Wolf 한 단계).
- 최근 맞춤: 앞 7년과 뒤 3년 따로(나눔날은 Team_Q), 최근 해에 무게(반감기는 Team_Q).
  python -m analysis.b3_30_ta_test --data <1_data 폴더> --universe <유니버스.csv> --out <결과 폴더>
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import yaml

from . import b3_30_ta_library as LIB

HZ = {'4주': 20, '12주': 60, '26주': 126, '52주': 252}
# 시험 설정·통과 문턱은 비공개 Team_Q blocks.yaml '3-30' → '시험'에만 둔다.


def private_cfg():
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'quant_center'))
        import qc_config as QCC
        y = yaml.safe_load(open(QCC.blocks_path(), encoding='utf-8')) or {}
        return y.get('3-30', {}) or {}
    except Exception:   # noqa: BLE001
        return {}


def load(data, uni):
    rd = lambda f: pd.read_csv(os.path.join(data, f), index_col=0, parse_dates=True, encoding='utf-8-sig')  # noqa: E731
    C = rd('가격10년_정제.csv.gz')
    raw = rd('가격10년_종가.csv.gz')
    O, H, L = rd('가격10년_시가.csv.gz'), rd('가격10년_고가.csv.gz'), rd('가격10년_저가.csv.gz')
    V = rd('거래량10년_정제.csv.gz')
    log = pd.read_csv(os.path.join(data, '정제_기록.csv.gz'), encoding='utf-8-sig')
    bad = log[log['무엇'].str.startswith('튄 값')]
    for _, r in bad.iterrows():
        d = pd.Timestamp(r['날짜'])
        for X in (O, H, L):
            if r['ticker'] in X and d in X.index:
                X.at[d, r['ticker']] = np.nan
    U = pd.read_csv(uni, dtype=str, encoding='utf-8-sig')
    cty = {}
    for nm, mk in (('미국', '미국'), ('한국', '한국')):
        cty[nm] = [t for t in U.loc[U['시장'] == mk, 'yfinance 티커'].dropna() if t in C.columns]
    cal = {'미국': raw['^GSPC'].notna(), '한국': raw['^KS11'].notna()}
    return C, O, H, L, V, cty, cal


def zone(c, x, k, dd):
    """바닥즈음 표시(1/0, 앞뒤 창이 다 없으면 NaN)."""
    lo = c.rolling(2 * k + 1, center=True, min_periods=2 * k + 1).min()
    hi = c.rolling(252, min_periods=126).max()
    z = ((c <= lo * (1 + x)) & (c <= hi * (1 - dd))).astype(float)
    return z.where(lo.notna() & hi.notna())


def decluster(b, gap):
    idx = np.where(b)[0]
    keep, last = [], -10 ** 9
    for i in idx:
        if i - last >= gap:
            keep.append(i)
            last = i
    return np.array(keep, dtype=int)


def collect(C, O, H, L, V, tickers, cal, cfg, index_name):
    """종목별 신호·정답·수익을 한 줄로 이어 붙인 배열로."""
    k, dd, gap = cfg['앞뒤일'], cfg['낙폭'], cfg['겹침일']
    rows = []   # 종목별 dict
    days = C.index[cal.reindex(C.index).fillna(False).values]
    cs = LIB.cross_section(C.loc[days], tickers)
    for t in tickers:
        c = C.loc[days, t]
        ok = c.notna()
        if ok.sum() < 300:
            continue
        c = c[ok]
        o, h, l, v = (X.loc[c.index, t] for X in (O, H, L, V))
        h = h.fillna(c); l = l.fillna(c); o = o.fillna(c)
        sig = LIB.per_ticker(o, h, l, c, v.fillna(0))
        for kk in ('T10', 'T11'):
            sig[kk] = cs[kk].loc[c.index, t]
        Z = {x: zone(c, x, k, dd).values for x in cfg['허용폭']}
        F = {hn: (c.shift(-hh) / c - 1).values * 100 for hn, hh in HZ.items()}
        ev = {kk: decluster(s.values, gap) for kk, s in sig.items()}
        rows.append({'t': t, 'd': c.index.values, 'Z': Z, 'F': F, 'ev': ev, 'n': len(c)})
    return rows


def collect_market(C, V, tickers, idx_close, cfg):
    c = idx_close.dropna()
    sig = LIB.market(C.loc[c.index], V.loc[c.index], tickers, c)
    Z = {x: zone(c, x, cfg['앞뒤일'], cfg['낙폭']).values for x in cfg['허용폭']}
    F = {hn: (c.shift(-hh) / c - 1).values * 100 for hn, hh in HZ.items()}
    ev = {kk: decluster(s.values, cfg['겹침일']) for kk, s in sig.items()}
    return [{'t': idx_close.name, 'd': c.index.values, 'Z': Z, 'F': F, 'ev': ev, 'n': len(c)}]


def episodes(z):
    """연속된 바닥즈음 구간 [(시작, 끝)]."""
    a = np.nan_to_num(z, nan=0) > 0
    out, s = [], None
    for i, v in enumerate(a):
        if v and s is None:
            s = i
        if not v and s is not None:
            out.append((s, i - 1)); s = None
    if s is not None:
        out.append((s, len(a) - 1))
    return out


def score(rows, techs, cfg, split, hl, mask=None):
    """기법별 성적. mask: 'train'/'test'/None(전체)."""
    T_end = max(r['d'][-1] for r in rows)
    out = []
    xs = cfg['허용폭']
    for kk in techs:
        hits = {x: [] for x in xs}
        fw = {h: [] for h in HZ}
        ex = {h: [] for h in HZ}
        wts = []
        caught = {x: 0 for x in xs}
        neps = {x: 0 for x in xs}
        for r in rows:
            d = r['d']
            sel = np.ones(len(d), bool)
            if mask == 'train':
                sel = d < split
            elif mask == 'test':
                sel = d >= split
            e = r['ev'][kk]
            e = e[sel[e]] if len(e) else e
            for x in xs:
                z = r['Z'][x]
                ev = e[~np.isnan(z[e])] if len(e) else e
                hits[x].extend(z[ev].tolist())
                for s0, s1 in episodes(np.where(sel, z, np.nan)):
                    neps[x] += 1
                    if len(e) and ((e >= s0) & (e <= s1)).any():
                        caught[x] += 1
                if x == xs[0]:
                    age = (T_end - d[ev]).astype('timedelta64[D]').astype(float) / 365.25
                    wts.extend((0.5 ** (age / hl)).tolist())
            for h in HZ:
                f = r['F'][h]
                base = np.nanmean(f[sel])
                ff = f[e] if len(e) else np.array([])
                fw[h].extend(ff.tolist())
                ex[h].extend((ff - base).tolist())
        row = {'번호': kk, '건수': len(hits[xs[0]])}
        for x in xs:
            hz = np.array(hits[x])
            allz = np.concatenate([np.where(sel_all(r, mask, split), r['Z'][x], np.nan) for r in rows])
            base = np.nanmean(allz)
            p = hz.mean() if len(hz) else np.nan
            tag = f'{int(round(x * 100))}%'
            row[f'맞힘_{tag}'] = p
            row[f'기준_{tag}'] = base
            row[f'배율_{tag}'] = p / base if base else np.nan
            row[f'잡은_{tag}'] = caught[x] / neps[x] if neps[x] else np.nan
            if x == xs[0] and len(hz):
                w = np.array(wts)
                row['최근가중_배율'] = (w * hz).sum() / w.sum() / base if base else np.nan
        for h in HZ:
            a = np.array(fw[h]); a = a[~np.isnan(a)]
            b = np.array(ex[h]); b = b[~np.isnan(b)]
            row[f'{h}_평균'] = a.mean() if len(a) else np.nan
            row[f'{h}_오른비율'] = (a > 0).mean() if len(a) else np.nan
            row[f'{h}_초과'] = b.mean() if len(b) else np.nan
        out.append(row)
    return pd.DataFrame(out).set_index('번호')


def sel_all(r, mask, split):
    d = r['d']
    if mask == 'train':
        return d < split
    if mask == 'test':
        return d >= split
    return np.ones(len(d), bool)


def permute(rows, techs, cfg, R, seed=0):
    """종목마다 같은 무작위 이동(모든 기법 공통) → 3% 맞힘 수·26주 초과의 우연 분포."""
    rng = np.random.default_rng(seed)
    x = cfg['허용폭'][0]
    K = len(techs)
    obs_h = np.zeros(K); obs_e = np.zeros(K)
    PH = np.zeros((R, K)); PE = np.zeros((R, K))
    # 26주 초과 = 수익 − 종목 평균
    prep = []
    for r in rows:
        z = r['Z'][x]
        f = r['F']['26주']
        fx = f - np.nanmean(f)
        prep.append((z, fx, r['n']))
    for j, kk in enumerate(techs):
        hz, he = [], []
        for r, (z, fx, n) in zip(rows, prep):
            e = r['ev'][kk]
            if len(e):
                hz.append(z[e]); he.append(fx[e])
        hz = np.concatenate(hz) if hz else np.array([])
        he = np.concatenate(he) if he else np.array([])
        obs_h[j] = np.nanmean(hz) if len(hz) else np.nan
        obs_e[j] = np.nanmean(he) if len(he) else np.nan
    for b in range(R):
        shifts = [rng.integers(0, n) for (_, _, n) in prep]
        for j, kk in enumerate(techs):
            sz = se = cz = ce = 0.0
            for r, (z, fx, n), u in zip(rows, prep, shifts):
                e = r['ev'][kk]
                if not len(e):
                    continue
                ee = (e + u) % n
                a = z[ee]; m = ~np.isnan(a); sz += a[m].sum(); cz += m.sum()
                a = fx[ee]; m = ~np.isnan(a); se += a[m].sum(); ce += m.sum()
            PH[b, j] = sz / cz if cz else np.nan
            PE[b, j] = se / ce if ce else np.nan
    res = {}
    for nm, obs, P in (('맞힘', obs_h, PH), ('26주초과', obs_e, PE)):
        p = (1 + (P >= obs[None, :]).sum(0)) / (R + 1)
        mu, sd = np.nanmean(P, 0), np.nanstd(P, 0)
        sd[sd == 0] = np.nan
        zo = (obs - mu) / sd
        zp = (P - mu) / sd
        mx = np.nanmax(zp, axis=1)
        fw = np.array([(1 + (mx >= zo[j]).sum()) / (R + 1) if not np.isnan(zo[j]) else np.nan for j in range(K)])
        res[f'p_{nm}'] = p
        res[f'q_{nm}'] = bh(p)
        res[f'최댓값p_{nm}'] = fw
    return pd.DataFrame(res, index=techs)


def bh(p):
    p = np.asarray(p, float)
    n = np.sum(~np.isnan(p))
    o = np.argsort(np.where(np.isnan(p), np.inf, p))
    q = np.full_like(p, np.nan)
    prev = 1.0
    for rank in range(n, 0, -1):
        i = o[rank - 1]
        prev = min(prev, p[i] * n / rank)
        q[i] = prev
    return q


def run_country(name, rows, techs, cfg, R):
    split = np.datetime64(cfg['나눔날'])
    hl = cfg['반감기년']
    full = score(rows, techs, cfg, split, hl)
    tr = score(rows, techs, cfg, split, hl, 'train')
    te = score(rows, techs, cfg, split, hl, 'test')
    pm = permute(rows, techs, cfg, R)
    df = full.join(pm)
    df['앞7년_배율_3%'] = tr['배율_3%']
    df['뒤3년_배율_3%'] = te['배율_3%']
    df['뒤3년_건수'] = te['건수']
    df['뒤3년_26주초과'] = te['26주_초과']
    df.insert(0, '나라', name)
    return df


def verdict(df, cfg):
    P = cfg['통과']
    ok = (df['q_맞힘'] <= P['q']) & (df['건수'] >= P['최소건수']) & (df['뒤3년_배율_3%'] > P['최근배율']) \
        & (df['배율_3%'] > 1)
    df['통과'] = np.where(ok, '통과', '')
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True); ap.add_argument('--universe', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--reps', type=int)
    a = ap.parse_args()
    pc = private_cfg()
    if not pc.get('시험'):
        raise SystemExit("비공개 설정 blocks.yaml '3-30' → '시험'이 없습니다(QC_PRIVATE).")
    cfg = {**pc['시험'], '보고_개수': pc.get('보고_개수', 10)}
    R = a.reps or cfg['반복']
    os.makedirs(a.out, exist_ok=True)
    C, O, H, L, V, cty, cal = load(a.data, a.universe)
    stock_techs = [k for k in LIB.META.index if LIB.META.at[k, '단위'] == '종목']
    mk_techs = [k for k in LIB.META.index if LIB.META.at[k, '단위'] == '시장']
    allres = []
    for nm, idxn in (('미국', '^GSPC'), ('한국', '^KS11')):
        t0 = time.time()
        rows = collect(C, O, H, L, V, cty[nm], cal[nm], cfg, idxn)
        df = run_country(nm, rows, stock_techs, cfg, R)
        df['단위'] = '종목'
        mrows = collect_market(C, V, cty[nm], C[idxn].where(cal[nm]).rename(idxn), cfg)
        dm = run_country(nm, mrows, mk_techs, cfg, R)
        dm['단위'] = '시장(' + idxn + ')'
        allres.append(verdict(pd.concat([df, dm]), cfg))
        print(f'[{nm}] 종목 {len(rows)}개, {time.time() - t0:.0f}초', flush=True)
    res = pd.concat(allres)
    res = res.join(LIB.META[['기법', '갈래', '출처']])
    res.to_csv(os.path.join(a.out, '기법시험_전체.csv'), encoding='utf-8-sig')
    json.dump({'설정': {k: (v if not isinstance(v, np.generic) else v.item()) for k, v in cfg.items()}, '반복': R},
              open(os.path.join(a.out, '기법시험_설정.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    one_page(res, cfg, R, os.path.join(a.out, '기법시험_한장.md'), cfg.get('보고_개수', 10))
    print(res[['나라', '기법', '건수', '배율_3%', '배율_1%', '잡은_3%', 'q_맞힘', '뒤3년_배율_3%', '26주_초과', '통과']].round(2).to_string())



def one_page(res, cfg, R, path, top=10):
    """한 장 표: 나라별 통과 기법을 최근 가중 배율 순으로 나란히(열 미국|한국)."""
    def cell(r):
        s = f"{r['기법']} · 3% {r['맞힘_3%'] * 100:.0f}%({r['배율_3%']:.1f}배)"
        s += f" · 1% {r['맞힘_1%'] * 100:.0f}%({r['배율_1%']:.1f}배) · 뒤3년 {r['뒤3년_배율_3%']:.1f}배"
        s += f" · 26주 {r['26주_초과']:+.1f}%p"
        return s
    L = {}
    for nm in ('미국', '한국'):
        d = res[(res['나라'] == nm) & (res['통과'] == '통과')].sort_values('최근가중_배율', ascending=False)
        L[nm] = [cell(r) for _, r in d.head(top).iterrows()]
        L[nm + '_n'] = len(d)
    n = max(len(L['미국']), len(L['한국']))
    lines = ['| 순위 | 미국 | 한국 |', '|---|---|---|']
    for i in range(n):
        u = L['미국'][i] if i < len(L['미국']) else ''
        k = L['한국'][i] if i < len(L['한국']) else ''
        lines.append(f'| {i + 1} | {u} | {k} |')
    base = {nm: res[(res['나라'] == nm) & (res['단위'] == '종목')]['기준_3%'].iloc[0] for nm in ('미국', '한국')}
    head = [f"아무 날이나 바닥즈음일 비율(3%): 미국 {base['미국'] * 100:.1f}%, 한국 {base['한국'] * 100:.1f}%. "
            f"'배율'은 신호 난 날이 그보다 몇 배 자주 바닥즈음이었나. 무작위 이동 {R}번, 보정 q ≤ {cfg['통과']['q']}, "
            f"건수 ≥ {cfg['통과']['최소건수']}, 뒤 3년 배율 > {cfg['통과']['최근배율']}이면 통과. "
            f"통과 미국 {L['미국_n']}개·한국 {L['한국_n']}개 중 최근 가중 배율 위 {top}개(나머지는 기법시험_전체.csv).",
            "칸 = 기법 · 3% 바닥즈음 맞힘(배율) · 1% 맞힘(배율) · 뒤 3년 배율 · 26주 뒤 같은 종목 아무 날 대비 초과 수익."]
    open(path, 'w', encoding='utf-8').write('\n'.join(head + [''] + lines) + '\n')


if __name__ == '__main__':
    main()
