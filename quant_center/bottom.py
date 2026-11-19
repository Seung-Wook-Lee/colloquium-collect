"""바닥 근접도(11/19 의장): 블록33이 '이런 모양'일 때 미국 지수가 바닥 즈음이었나를 배워 오늘을 잰다.

  지문(주 단위)  = 미국 개별주 점수 블록별(표시만 블록 B11·B12·B17·B32 제외, 엔진·성적표 정의가 같은 가격 블록만) '예'(점수 ≥ 0.5) 비율(블록점수이력.csv, 오늘은 엔진 판정표)
                 + 시장 블록 값(VIX·VIX3M·MOVE·신용·금융 스트레스·금리·공탐 근사·CTA·변동성 타기팅·HMM·AI÷방어·지정학 위험·S&P 낙폭)
  정답(규칙)     = 그 주 S&P 종가가 앞 13주 최저·뒤 13주 최저의 3% 안 + 52주 고점 대비 −5% 이하 (정확한 날이 아니라 1~2주 구간)
  모형           = 로지스틱 회귀(표준화, 바닥 주 가중). 해마다 그 전 자료로만 학습해 그해를 예측(걸어가며 검정),
                   그 예측으로 아이소토닉 눈금 보정 → 보정 확률. 원점수는 과거 10년 중 백분위로도 보여 줌.
  검정           = AUC·순열 검정 p값(13주 덩어리)·정밀도·재현율·브라이어 기술 점수·사건 적중(앞뒤 2주)·헛경보
  출력           = 바닥근접도.csv(오늘 한 줄), 바닥근접도_검정.csv, 바닥근접도_이력.csv, 바닥근접도_닮은주.csv
  설정           = blocks.yaml '바닥:' 칸(없으면 아래 기본값)
  자료           = 야후(지수·VIX·MOVE·HYG·IEF), FRED API(FRED_KEY: STLFSI4·DGS10·DGS2·T10Y2Y), 지정학 위험 지수(Caldara·Iacoviello). 모두 무료.
실행: python bottom.py <작업폴더>   (작업폴더/블록점수이력.csv, 작업폴더/out_판정표.csv 사용)
"""
import io
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

DEF = dict(정답_주=13, 정답_여유=0.03, 정답_낙폭=-0.05, 경보=0.5, 검정_시작해=2020, 닮은주=6, 블록=['B13', 'B16', 'B28', 'B29', 'B30', 'B31', 'B33'])
YF = ['^GSPC', '^NDX', '^RUT', '^VIX', '^VIX3M', '^MOVE', 'HYG', 'IEF']
FRED = {'STLFSI4': 'STLFSI', 'DGS10': 'US10Y', 'DGS2': 'US2Y', 'T10Y2Y': 'T10Y2Y'}
GPR_URL = 'https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls'


def _pct(s, w=252, mp=120):
    return s.rolling(w, min_periods=mp).apply(lambda a: (a <= a[-1]).mean() * 100, raw=True)


def _rsi(x, n=14):
    d = x.diff(); up = d.clip(lower=0).ewm(alpha=1 / n).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / n).mean()
    return 100 - 100 / (1 + up / dn)


def _hmm(p):
    """B01: 2국면 가우시안 HMM(수익률·20일 변동성), 63일마다 그날까지로 다시 맞춤, 변동성 큰 국면의 그날 확률"""
    try:
        from hmmlearn.hmm import GaussianHMM
    except ImportError:
        return pd.Series(np.nan, index=p.index)
    r = np.log(p).diff().dropna(); X = pd.concat([r, r.rolling(20).std()], axis=1).dropna()
    out = pd.Series(np.nan, index=X.index); mdl = None; bear = 0
    for i in range(750, len(X)):
        if mdl is None or i % 63 == 0:
            try:
                mdl = GaussianHMM(2, 'full', n_iter=50, random_state=0).fit(X.values[:i + 1]); bear = int(np.argmax(mdl.means_[:, 1]))
            except Exception:   # noqa: BLE001 — 맞춤 실패면 이전 모형 유지
                pass
        if mdl is not None:
            out.iloc[i] = mdl.predict_proba(X.values[max(0, i - 250):i + 1])[-1, bear]
    return out


def market(start='2007-01-01'):
    """시장 블록 값(일별, 그날 알 수 있는 값만)"""
    import requests
    import yfinance as yf
    import flowpos as FP
    M = yf.download(YF, start=start, auto_adjust=True, progress=False)['Close']
    sp = M['^GSPC'].dropna()
    px = pd.DataFrame({'GSPC': M['^GSPC'], 'NDX': M['^NDX'], 'RUT': M['^RUT']}).dropna()
    fp = FP.compute({'GSPC': px['GSPC'], 'NDX': px['NDX'], 'RUT': px['RUT']})
    fr = {}
    key = os.environ.get('FRED_KEY')
    if key:
        for sid, nm in FRED.items():
            try:
                r = requests.get('https://api.stlouisfed.org/fred/series/observations', timeout=30,
                                 params={'series_id': sid, 'api_key': key, 'file_type': 'json', 'observation_start': start})
                ob = [o for o in r.json().get('observations', []) if o['value'] not in ('.', '')]
                fr[nm] = pd.Series([float(o['value']) for o in ob], index=pd.to_datetime([o['date'] for o in ob]))
            except Exception as e:   # noqa: BLE001
                print(f'[바닥] FRED {sid} 실패: {e}')
    loc = os.environ.get('BOTTOM_HIST')   # 시험용: 미리 받은 FRED_일별.csv·GPR_일별.csv 폴더
    if loc and not fr and os.path.exists(f'{loc}/FRED_일별.csv'):
        F0 = pd.read_csv(f'{loc}/FRED_일별.csv', index_col=0, parse_dates=True)
        fr = {nm: F0[nm].dropna() for nm in FRED.values() if nm in F0}
    gp = pd.Series(dtype=float)
    try:
        if loc and os.path.exists(f'{loc}/GPR_일별.csv'):
            g = pd.read_csv(f'{loc}/GPR_일별.csv', encoding='utf-8-sig', low_memory=False)
        else:
            g = pd.read_excel(io.BytesIO(requests.get(GPR_URL, timeout=60, headers={'User-Agent': 'Mozilla/5.0'}).content))
        g.index = pd.to_datetime(g['date'].astype(str).str[:10], errors='coerce'); g = g[g.index.notna()]
        g7 = pd.to_numeric(g['GPRD'], errors='coerce').rolling(7, min_periods=5).mean()
        gp = _pct(g7, 2520, 500)
    except Exception as e:   # noqa: BLE001
        print(f'[바닥] 지정학 위험 실패: {e}')
    # 공탐 근사(CNN 7개 중 가격으로 되는 4개, 각 1년 백분위 평균): 모멘텀, VIX(반대), 안전자산, 정크본드
    fg = pd.concat([_pct(sp / sp.rolling(125).mean()), _pct(-(M['^VIX'] / M['^VIX'].rolling(50).mean()).dropna()),
                    _pct((sp.pct_change(20) - M['IEF'].pct_change(20)).dropna()), _pct((M['HYG'] / M['IEF']).pct_change(20).dropna())], axis=1).mean(axis=1)
    us2 = fr.get('US2Y', pd.Series(dtype=float))
    D = pd.DataFrame({
        'B01 HMM 하락': _hmm(sp), 'B02 VIX 1년 백분위': _pct(M['^VIX'].dropna()), 'B02 VIX−VIX3M': M['^VIX'] - M['^VIX3M'], 'B02 MOVE': M['^MOVE'],
        'B03 신용 HYG÷IEF 60일': (M['HYG'] / M['IEF']).pct_change(60) * 100, 'B03 금융 스트레스': fr.get('STLFSI'),
        'B04 미 10년물': fr.get('US10Y'), 'B04 10Y−2Y': fr.get('T10Y2Y'), 'B04 2년물 20일 변화': us2 - us2.shift(20),
        'B05 공탐(근사)': fg, 'B06 CTA': fp['CTA σ(근사)'], 'B06 변동성 타기팅': fp['변동성타기팅 노출(배)'],
        'B10 지정학 백분위': gp, 'S&P 고점 대비': (sp / sp.rolling(252, min_periods=60).max() - 1) * 100, 'S&P RSI': _rsi(sp)})
    return D.sort_index().ffill(limit=10), sp


def fingerprint(H, blocks):
    U = H[(H['시장'] == '미국') & (H['구분'] == '개별주')]
    cols = [b for b in blocks if b in U]
    g = U.groupby('날짜')[cols].apply(lambda x: (x >= 0.5).sum() / x.notna().sum() * 100)
    g.columns = [f'{b} 예 비율' for b in cols]
    return g


def today_rows(S, blocks):
    """엔진 판정표(오늘) → 블록점수이력과 같은 꼴(통과/탈락은 1/0)"""
    T = S.copy()
    for b in blocks:
        if b in T:
            T[b] = pd.to_numeric(T[b].replace({'통과': 1.0, '탈락': 0.0}), errors='coerce')
    return T


def run(W, S=None, cfg=None, idx='^GSPC'):
    """idx: 정답·낙폭을 잴 지수(^GSPC S&P500, ^NDX 나스닥100). 11/19 의장: 이번 조정은 나스닥이 −10% 넘어 조정장"""
    from scipy.stats import mannwhitneyu
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score, brier_score_loss, precision_score, recall_score, roc_auc_score
    from sklearn.preprocessing import StandardScaler
    C = {**DEF, **(cfg or {})}
    H = pd.read_csv(f'{W}/블록점수이력.csv', encoding='utf-8-sig', parse_dates=['날짜'], low_memory=False)
    if S is None and os.path.exists(f'{W}/out_판정표.csv'):
        S = pd.read_csv(f'{W}/out_판정표.csv', encoding='utf-8-sig')
    MK, sp = market()
    tag = '' if idx == '^GSPC' else '_나스닥100'
    if idx != '^GSPC':
        import yfinance as yf
        sp = yf.download(idx, start='2007-01-01', auto_adjust=True, progress=False)['Close'].squeeze().dropna()
        MK['S&P 고점 대비'] = (sp / sp.rolling(252, min_periods=60).max() - 1) * 100
    today = sp.index[-1]
    FPH = fingerprint(H, C['블록'])
    if S is not None:
        T = today_rows(S, C['블록']); T['날짜'] = today
        FPH = pd.concat([FPH[FPH.index < today - pd.Timedelta(days=3)], fingerprint(T, C['블록'])])
    wk = MK.resample('W-FRI').last()
    X = FPH.copy(); X.index = pd.DatetimeIndex(X.index).to_period('W-FRI').to_timestamp('W-FRI') if len(X) else X.index
    X = X[~X.index.duplicated(keep='last')].join(wk, how='inner').dropna(axis=1, how='all')
    # 정답
    w = sp.resample('W-FRI').last(); n = C['정답_주']
    fut = w[::-1].rolling(n + 1, min_periods=1).min()[::-1]; past = w.rolling(n).min(); dd = w / w.rolling(52).max() - 1
    Y = ((w <= fut * (1 + C['정답_여유'])) & (w <= past * (1 + C['정답_여유'])) & (dd <= C['정답_낙폭'])).astype(int)
    f13 = (w.shift(-13) / w - 1) * 100; f26 = (w.shift(-26) / w - 1) * 100
    known = X.index <= w.index[-(n + 1)]
    med = X[known].median()
    Xa = X.fillna(med)
    # 걸어가며 예측
    raw = pd.Series(np.nan, index=X.index)
    for yr in range(C['검정_시작해'], X.index[-1].year + 1):
        tr = known & (X.index.year < yr); te = X.index.year == yr
        if Y.reindex(X.index[tr]).sum() < 5 or te.sum() == 0:
            continue
        sc = StandardScaler().fit(Xa[tr]); lr = LogisticRegression(C=0.3, class_weight='balanced', max_iter=3000)
        lr.fit(sc.transform(Xa[tr]), Y.reindex(X.index[tr]))
        raw[te] = lr.predict_proba(sc.transform(Xa[te]))[:, 1]
    ev = raw.index[known & raw.notna()]
    p, t = raw[ev], Y.reindex(ev).astype(int)
    iso = IsotonicRegression(out_of_bounds='clip', y_min=0, y_max=1).fit(p, t)
    cal = pd.Series(iso.predict(raw.fillna(0)), index=raw.index).where(raw.notna())
    # 검정
    rng = np.random.default_rng(0); auc = roc_auc_score(t, p)
    perm = [roc_auc_score(np.roll(t.values, rng.integers(1, len(t))), p) for _ in range(2000)]
    yhat = (p >= C['경보']).astype(int)
    grp = (t.diff() != 0).cumsum(); evs = [g.index for _, g in t.groupby(grp) if g.iloc[0] == 1]
    win = lambda a, b, k: pd.date_range(a - pd.Timedelta(weeks=k), b + pd.Timedelta(weeks=k), freq='W-FRI')
    hit = sum(bool((p.reindex(win(e[0], e[-1], 2)) >= C['경보']).any()) for e in evs)
    ag = (yhat.diff() != 0).cumsum(); al = [g.index for _, g in yhat.groupby(ag) if g.iloc[0] == 1]
    fa = sum(not bool(t.reindex(win(a[0], a[-1], 4)).fillna(0).any()) for a in al)
    pc = cal[ev]
    TEST = pd.DataFrame([dict(검정기간=f'{ev[0].date()}~{ev[-1].date()}', 주수=len(t), 바닥구간주=int(t.sum()), 기준확률=round(t.mean(), 3),
                              AUC=round(auc, 3), AUC_p값_맨휘트니=round(mannwhitneyu(p[t == 1], p[t == 0], alternative='greater').pvalue, 5),
                              AUC_p값_순열=round((np.sum(np.array(perm) >= auc) + 1) / 2001, 4), PR_AUC=round(average_precision_score(t, p), 3),
                              브라이어_기술점수_원점수=round(1 - brier_score_loss(t, p) / brier_score_loss(t, np.full(len(t), t.mean())), 3),
                              브라이어_기술점수_보정=round(1 - brier_score_loss(t, pc) / brier_score_loss(t, np.full(len(t), t.mean())), 3),
                              정밀도=round(precision_score(t, yhat, zero_division=0), 3), 재현율=round(recall_score(t, yhat), 3),
                              바닥사건=len(evs), 사건적중_앞뒤2주=hit, 경보덩어리=len(al), 헛경보=fa)])
    # 오늘
    lastw = X.index[-1]; r0 = float(raw.iloc[-1]) if not pd.isna(raw.iloc[-1]) else np.nan
    hist = raw[ev]
    near = hist[(hist - r0).abs() <= 0.1].index if not np.isnan(r0) else hist.index[:0]
    Z = (Xa - Xa[known].mean()) / Xa[known].std(); dist = ((Z[known] - Z.iloc[-1]) ** 2).sum(axis=1) ** 0.5
    keep = []
    for k in dist.nsmallest(60).index:
        if all(abs((k - q).days) > 60 for q in keep):
            keep.append(k)
        if len(keep) == C['닮은주']:
            break
    AN = pd.DataFrame({'날짜': [k.date() for k in keep], '거리': dist[keep].round(2).values, '바닥구간': Y.reindex(keep).values,
                       '뒤13주(%)': f13.reindex(keep).round(1).values, '뒤26주(%)': f26.reindex(keep).round(1).values})
    sc = StandardScaler().fit(Xa[known]); lr = LogisticRegression(C=0.3, class_weight='balanced', max_iter=3000).fit(sc.transform(Xa[known]), Y.reindex(X.index[known]))
    contrib = pd.Series(lr.coef_[0] * sc.transform(Xa.iloc[[-1]])[0], index=X.columns).sort_values()
    ONE = pd.DataFrame([dict(기준지수=idx, 날짜=lastw.date(), 원점수=round(r0, 3), 보정확률=round(float(cal.iloc[-1]), 3),
                             과거백분위=round(float((hist <= r0).mean() * 100), 1), 경보=int(r0 >= C['경보']),
                             비슷한점수_주수=len(near), 비슷한점수_뒤13주_평균=round(f13.reindex(near).mean(), 1),
                             비슷한점수_뒤13주_승률=round((f13.reindex(near).dropna() > 0).mean() * 100, 1),
                             비슷한점수_뒤26주_평균=round(f26.reindex(near).mean(), 1),
                             비슷한점수_뒤26주_승률=round((f26.reindex(near).dropna() > 0).mean() * 100, 1),
                             바닥쪽_블록=' / '.join(contrib.index[::-1][:3]), 반대쪽_블록=' / '.join(contrib.index[:3]),
                             닮은주=', '.join(str(k.date()) for k in keep[:3]))])
    HIST = pd.DataFrame({'원점수': raw.round(3), '보정확률': cal.round(3), '바닥구간': Y.reindex(X.index)})
    for k, v in (('바닥근접도', ONE), ('바닥근접도_검정', TEST), ('바닥근접도_닮은주', AN)):
        v.to_csv(f'{W}/{k}{tag}.csv', index=False, encoding='utf-8-sig')
    HIST.to_csv(f'{W}/바닥근접도_이력{tag}.csv', encoding='utf-8-sig')
    print(ONE.T.to_string()); print(TEST.T.to_string())
    return ONE, TEST, AN


if __name__ == '__main__':
    import qc_config as QCC
    W = sys.argv[1] if len(sys.argv) > 1 else '.'
    try:
        cfg = QCC.load_blocks().get('바닥')
    except Exception:   # noqa: BLE001 — 비공개 설정 없으면 기본값
        cfg = None
    run(W, cfg=cfg)
