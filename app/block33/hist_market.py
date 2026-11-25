"""시장 블록(B01~B10) 주별 과거 값 (11/24 의장: "앞의 B1~B18은 자료를 다 채웠나?" → 블록점수이력에는 시장 블록 칸이 없었음).
매주 금요일, 그 주까지 알 수 있던 값만으로 엔진(features.market)과 같은 변수를 다시 만들고, blocks.yaml '시장' 공식 36개를 엔진 _ev로 판정한다.
  같은 코드를 그대로 씀: risk_signals.signals(CTM·MA 클러스터·코폭·QQQ:RSP 앵커드 VWAP·CPCE·109주선), flowpos.compute(CTA·변동성 목표·시스템 매수 전환),
  B01 HMM은 team_q b01_hmm과 같은 방식(분기마다 그 앞 주만으로 다시 맞춤, 앞으로만 거름).
  값이 없는 변수는 비워 둔다(대신 값 쓰지 않음). 어느 변수가 언제부터 있는지는 실행 끝에 찍는다.
입력 폴더 d: 시장위험_장기.csv, 가격10년_지수장기.csv.gz, (있으면) CPCE.csv·신용스프레드_이력.csv·공포탐욕_이력.csv·지정학위험_이력.csv·가격10년_종가.csv.gz·유니버스.csv
출력: d/시장블록이력.csv (날짜, 변수 값, 공식별 결과 1/0/빈칸, 블록별 부담·기회 신호 수, 시장부담·시장기회, S&P·나스닥100 4·12·26·52주 뒤 수익)
실행: python hist_market.py <입력 폴더> <blocks.yaml> [시작 YYYY-MM-DD]"""
import os
import sys

import numpy as np
import pandas as pd
import yaml

H = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [H, os.path.join(os.path.dirname(os.path.dirname(H)), 'collect')]
import risk_signals as RSG  # noqa: E402
import flowpos as FP  # noqa: E402


def _ev(expr, row):   # engine._ev와 같은 규칙(쓰는 칸 하나라도 없으면 '자료 없음')
    names = compile(expr, '<f>', 'eval').co_names
    env = {k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in row.items()}
    if any(env.get(n) is None for n in names):
        return None
    try:
        return bool(eval(expr, {'__builtins__': {}}, env))
    except (TypeError, NameError):
        return None


def _csv(d, name, **kw):
    p = f'{d}/{name}'
    return pd.read_csv(p, **kw) if os.path.exists(p) else None


def hmm_bear(c, min_weeks=156, n_states=3, iters=100, seed=2611, volwin=21):
    """B01 하락 국면(가우시안 HMM 3상태, 분기마다 다시 맞춤). 주별 '하락 상태가 가장 높을 때 그 확률, 아니면 0'(features.market의 US_BEAR·KR_BEAR 규칙)."""
    try:
        from hmmlearn.hmm import GaussianHMM
        from scipy.special import logsumexp
    except ImportError:
        return pd.Series(dtype=float)
    w = c.resample('W-FRI').last()
    vol = c.pct_change(fill_method=None).rolling(volwin).std().resample('W-FRI').last()
    x = pd.DataFrame({'ret': np.log(w / w.shift(1)), 'vol': vol}).dropna()
    out = pd.Series(np.nan, index=x.index)
    fitted = quarter = alpha = None
    for i in range(min_weeks, len(x)):
        date = x.index[i]; q = date.to_period('Q')
        if fitted is None or q != quarter:
            train = x.iloc[:i].to_numpy(); mean = train.mean(0); scale = train.std(0)
            if np.any(scale == 0):
                continue
            fitted = GaussianHMM(n_states, covariance_type='diag', n_iter=iters, random_state=seed, min_covar=1e-5)
            try:
                fitted.fit((train - mean) / scale)
            except (ValueError, np.linalg.LinAlgError):
                fitted = None; continue
            order = np.argsort(fitted.means_[:, 0]); alpha = np.log(np.maximum(fitted.startprob_, 1e-300))
            for em in fitted._compute_log_likelihood((train - mean) / scale):
                alpha = em + logsumexp(alpha[:, None] + np.log(np.maximum(fitted.transmat_, 1e-300)), axis=0); alpha -= logsumexp(alpha)
            quarter = q
        em = fitted._compute_log_likelihood(((x.iloc[i].to_numpy() - mean) / scale)[None, :])[0]
        alpha = em + logsumexp(alpha[:, None] + np.log(np.maximum(fitted.transmat_, 1e-300)), axis=0); alpha -= logsumexp(alpha)
        p = np.exp(alpha)[order]   # [하락, 중립, 상승]
        out.loc[date] = p[0] if p.argmax() == 0 else 0.0
    return out


def main(d, ypath, start='2000-01-07'):
    B = yaml.safe_load(open(ypath, encoding='utf-8'))
    F = [(bid, k, n, e, side) for bid, b in B['시장'].items() for k, (n, e, side) in enumerate(b['공식'])]
    R = pd.read_csv(f'{d}/시장위험_장기.csv', index_col=0, parse_dates=True)
    R = R[~R.index.duplicated()].sort_index()
    cp = _csv(d, 'CPCE.csv', encoding='utf-8-sig', index_col=0, parse_dates=True)
    if cp is not None and 'CPCE' not in R:
        R = R.join(cp[['CPCE']], how='outer')
    I = pd.read_csv(f'{d}/가격10년_지수장기.csv.gz'); I['날짜'] = pd.to_datetime(I['날짜'])
    IX = I.pivot_table(index='날짜', columns='지수', values='종가').sort_index()
    spx = R['SPX'].dropna() if 'SPX' in R else IX['^GSPC'].dropna()
    ndx = R['NDX'].dropna() if 'NDX' in R else IX['^NDX'].dropna()
    ks = IX['^KS11'].dropna() if '^KS11' in IX else pd.Series(dtype=float)
    fri = pd.date_range(start, spx.index.max(), freq='W-FRI')
    fri = [t for t in fri if t >= spx.index.min()]
    def asof(s, lim=10):
        s = s.dropna()
        if not len(s):
            return pd.Series(np.nan, index=fri)
        s.index = pd.to_datetime(s.index)
        return s[~s.index.duplicated()].sort_index().reindex(fri, method='ffill', tolerance=pd.Timedelta(days=lim))
    V = pd.DataFrame(index=pd.DatetimeIndex(fri))
    # 리스크 표 값(features.market: 리스크·매크로체크리스트)
    for k, c in (('VIX', 'VIX'), ('MOVE', 'MOVE'), ('STLFSI', 'STLFSI4'), ('US10Y', 'DGS10'), ('T10Y2Y', 'T10Y2Y')):
        V[k] = asof(R[c]).values if c in R else np.nan
    hy = R['BAMLH0A0HYM2'] if 'BAMLH0A0HYM2' in R else pd.Series(dtype=float)
    cs = _csv(d, '신용스프레드_이력.csv', encoding='utf-8-sig', index_col=0, parse_dates=True)
    if cs is not None and '하이일드' in cs:
        hy = hy.combine_first(cs['하이일드'])
    V['HY'] = asof(hy).values if len(hy) else np.nan
    if 'SOFR' in R:
        iorb = R['IORB'].combine_first(R['IOER']) if 'IORB' in R and 'IOER' in R else R.get('IORB', R.get('IOER'))
        V['SOFR_IORB'] = asof(R['SOFR'] - iorb.reindex(R.index).ffill()).values if iorb is not None else np.nan
    else:
        V['SOFR_IORB'] = np.nan
    fg = _csv(d, '공포탐욕_이력.csv', encoding='utf-8-sig', index_col=0, parse_dates=True)
    V['FG'] = asof(fg.iloc[:, 0]).values if fg is not None else np.nan
    # 수급포지셔닝(flowpos.compute) — RUT 없으면 비움
    if 'RUT' in R:
        P = FP.compute({'GSPC': spx, 'NDX': ndx, 'RUT': R['RUT'].dropna()})
        for k, c in (('CTA', 'CTA σ(근사)'), ('VOLT', '변동성타기팅 노출(배)'), ('SYS_TURN', '시스템 매수 전환')):
            V[k] = asof(P[c], 5).values
    else:
        V['CTA'] = V['VOLT'] = V['SYS_TURN'] = np.nan
    V['KR_SAFE_FLOW5'] = np.nan   # 한국 ETF 좌수 과거 기록 아직 없음
    V['SPX_FPER'] = np.nan        # S&P500 선행 EPS 과거 기록 아직 없음
    # 코스피 50일 이격
    V['KS_GAP50'] = asof(ks / ks.rolling(50).mean() * 100).values if len(ks) else np.nan
    # 지정학 위험: 7일 평균의 10년 백분위(b09_gpr과 같은 식)
    gp = _csv(d, '지정학위험_이력.csv', encoding='utf-8-sig', index_col=0, parse_dates=True)
    if gp is not None:
        ma = gp['GPRD'].rolling(7, min_periods=5).mean().dropna()
        pc = pd.Series([float((ma.loc[t - pd.Timedelta(days=3653):t] <= ma.loc[t]).mean() * 100) for t in ma.index], index=ma.index)
        V['GPR_PCT'] = asof(pc).values
    else:
        V['GPR_PCT'] = np.nan
    # B01 HMM
    V['US_BEAR'] = asof(hmm_bear(spx), 7).values
    V['KR_BEAR'] = asof(hmm_bear(ks), 7).values if len(ks) else np.nan
    # 분산 깨짐·순환 국면(가격10년 + 유니버스 층)
    px = _csv(d, '가격10년_종가.csv.gz', index_col=0, parse_dates=True)
    U = _csv(d, '유니버스.csv', encoding='utf-8-sig')
    V['CORR_JUMP'] = np.nan; V['ROT_DEF'] = np.nan
    if px is not None:
        r = np.log(px.sort_index()).diff()
        lay = dict(zip(U['yfinance 티커'], U['층'])) if U is not None else {}
        ai = [t for t in px if lay.get(t) in ('S1', 'S2', 'S3')]; df = [t for t in px if lay.get(t) in ('S5', 'S6')]
        rr = px.sort_index().pct_change(fill_method=None)
        Rt = (1 + rr[ai].mean(axis=1).fillna(0)).cumprod() / (1 + rr[df].mean(axis=1).fillna(0)).cumprod() if ai and df else None
        def mc(x):
            c = x.dropna(axis=1, thresh=int(len(x) * 0.8)).corr().values; n = len(c)
            return (np.nansum(c) - n) / (n * n - n) if n > 1 else np.nan
        for t in V.index:
            x = r.loc[:t]
            if len(x) < 260:
                continue
            V.at[t, 'CORR_JUMP'] = mc(x.tail(20)) - mc(x.tail(252))
            if Rt is not None:
                q = Rt.loc[:t]
                V.at[t, 'ROT_DEF'] = int(q.iloc[-1] / q.tail(50).mean() < 1 and q.iloc[-1] / q.iloc[-21] < 1)
    # risk_signals.signals: 그 주까지의 표로 매주 다시 계산(엔진과 같은 코드)
    keep = ('CTM_RED', 'CTM_GREEN', 'MA_CLUSTER_RED', 'COP_REV', 'COP_UP0', 'QQRSP_AVWAP', 'CPCE_UP20', 'SPX_W109_SUP', 'SPX_W109_UPX')
    D = R.loc['1985':]
    rows = []
    for t in V.index:
        s = RSG.signals(D.loc[:t])
        rows.append({k: s.get(k) for k in keep})
    S = pd.DataFrame(rows, index=V.index).astype(float)
    for k in keep:
        V[k] = S[k]
    # 공식 판정
    out = V.copy()
    for bid, k, n, e, side in F:
        out[f'{bid}-{k + 1}'] = [None if (v := _ev(e, row)) is None else int(v) for row in V.to_dict('records')]
    for bid in B['시장']:
        for side in ('부담', '기회'):
            cols = [f'{b}-{k + 1}' for b, k, n, e, sd in F if b == bid and sd == side]
            if cols:
                out[f'{bid}_{side}'] = out[cols].sum(axis=1, min_count=1)
    out['시장부담'] = out[[c for c in out if c.endswith('_부담')]].sum(axis=1, min_count=1)
    out['시장기회'] = out[[c for c in out if c.endswith('_기회')]].sum(axis=1, min_count=1)
    for nm, s in (('SPX', spx), ('NDX', ndx)):
        w = s.reindex(V.index, method='ffill')
        for h in (4, 12, 26, 52):
            out[f'{nm}_{h}주'] = (w.shift(-h) / w - 1) * 100
    out.index.name = '날짜'
    out.to_csv(f'{d}/시장블록이력.csv', encoding='utf-8-sig')
    have = {c: (str(out[c].first_valid_index().date()) if out[c].notna().any() else '없음') for c in V.columns}
    print(f'시장블록이력 {len(out)}주 ({out.index.min().date()}~{out.index.max().date()}), 공식 {len(F)}개')
    print('변수 시작: ' + ' · '.join(f'{k} {v}' for k, v in have.items()))
    return out


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], *(sys.argv[3:4]))
