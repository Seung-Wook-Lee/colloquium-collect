"""블록 성적표 + 조합 시험(11/19 의장).
1) 과거 매주, 그날까지의 가격만으로 블록 점수를 다시 매긴다(그날 알 수 없던 자료는 쓰지 않음).
2) 블록 성적표: 블록 점수 0.5 이상(예)·미만(아니오) 종목의 4·12·26·52주 뒤 절대 수익률·승률, 순위 상관(IC).
3) 조합 시험(걸어가며 검증): 해마다 '그 전까지 결과를 알 수 있던 날'만으로 블록 조합을 고르고(앞으로 하나씩 더하기),
   그해 매주 종합점수 상위 5종목의 실제 성적을 잰다. 고를 때 본 기간과 성적을 잰 기간이 겹치지 않는다.
가격으로 다시 계산할 수 없는 칸(실적·수급·13F·뉴스·공매도 등)은 비워 두므로, 그런 블록은 기록이 쌓일 때까지 빠진다.
쓰는 법: python backtest.py <입력폴더>   (입력폴더에 10년치 데이터베이스 가격10년_*.csv.gz가 있어야 함, 따로 받지 않음)
결과: <입력폴더>/../블록점수이력.csv(다음 실행 때 새 날짜만 계산), 블록성적.csv, 조합시험.csv, 조합후보_오늘.csv
오늘 후보는 엔진 판정표(<입력폴더>/../out_판정표.csv)에서 '후보'(거르기·추천 자격 통과)인 종목만."""
import ast
import math
import os
import shutil
import sys
import tempfile
from multiprocessing import Pool

import numpy as np
import pandas as pd
import yaml

HERE = os.path.dirname(os.path.realpath(__file__))
COLLECT = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'collect')   # 11/21 두 폴더: 수집(collect)·스튜디오(app)
sys.path.insert(0, COLLECT)   # nyx.py(닉스 지표), blocks/b09_exc.py(예외 검정)
sys.path.insert(0, os.path.join(COLLECT, 'data'))
import px_store as PS  # noqa: E402  10년치 데이터베이스 하나
import features as F  # noqa: E402
import hist_fund as HF  # 11/23 과거 재무 칸(SEC·DART 공시일 기준)
import hist_sector as HS
import hist_flow as HK
import hist_13f as H13
import hist_short as HSH  # noqa: E402
import hist_etf as HE  # noqa: E402
import eps_proxy as EP  # noqa: E402
import nyx  # noqa: E402
import orders as O  # noqa: E402
from engine import _ev  # noqa: E402
import qc_config as QCC  # noqa: E402

PX = dict(PS.F)   # 데이터베이스 칸 → 닉스 지표 이름(시가·고가·저가·종가·거래량)
KEEP = 520          # 엔진이 받는 것과 같은 2년치만 넘김
TOPN = 5
SCORED = ('점수', '핵심', '타이밍', '매도')
PRICE_ALWAYS = {'shock_layer', 'shock_own', 'sup_touch_d'}   # 가격으로 계산되지만 0·1 값이라 날짜를 바꿔도 같게 나올 수 있는 칸


def _exc_fn():
    """blocks/b09_exc.py의 exc_row(10년 p값·베타 잔차 p값)를 그대로 가져온다(같은 식 한 벌)."""
    src = open(os.path.join(COLLECT, 'blocks', 'b09_exc.py'), encoding='utf-8').read()
    keep = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name in ('_exc_norm_cdf', 'exc_row')]
    ns = {'math': math, 'np': np, 'pd': pd}
    exec(compile(ast.Module(body=keep, type_ignores=[]), 'b09_exc', 'exec'), ns)
    return ns['exc_row']


EXC_ROW = _exc_fn()


def load_long(d):
    """11/26 의장: 10년치 데이터베이스 하나에서 읽는다(따로 받던 10년 사본 없앰)."""
    return {k: PS.frame(d, k) for k in PX}


def asof_dir(d, L, t, out):
    """t일 기준 입력 폴더: 가격 파일은 t까지 잘라 넣고, 닉스 지표·예외 검정은 t까지의 가격으로 다시 계산"""
    os.makedirs(out, exist_ok=True)
    for x in os.listdir(d):
        p = os.path.join(d, x)
        if os.path.isfile(p) and x not in {PS.name(k) for k in L} and x not in ('닉스.csv', '예외검정.csv'):
            os.symlink(p, os.path.join(out, x))
    for k, v in L.items():
        v.loc[:t].tail(KEEP).to_csv(f'{out}/{PS.name(k)}', encoding='utf-8-sig', compression={'method': 'gzip', 'compresslevel': 1})
    N = pd.read_csv(f'{d}/닉스.csv', encoding='utf-8-sig')
    I = L['Close'].loc[:t]
    rows, ex = [], []
    for tk in N['yfinance 티커'].astype(str):
        o = pd.DataFrame({c: L[k][tk] for k, c in PX.items() if tk in L[k]}).loc[:t].dropna(subset=['종가']).tail(KEEP)
        a = nyx.analyze(o) if len(o) and '고가' in o else {}
        rows.append(a)
        c = L['Close'][tk].loc[:t].dropna() if tk in L['Close'] else pd.Series(dtype=float)
        mk = '^GSPC' if not tk.endswith(('.KS', '.KQ')) else '^KS11'
        try:
            w = c.resample('W-FRI').last().dropna(); m = I[mk].dropna().resample('W-FRI').last().dropna()
            ex.append(EXC_ROW(w, m) if len(w) > 60 else {})
        except Exception:   # noqa: BLE001 — 자료 짧은 종목은 비워 둠
            ex.append({})
    A = pd.DataFrame(rows, index=N.index)
    for col in A.columns.intersection(N.columns):
        N[col] = A[col]
    for col in set(N.columns) & {'종가', '52주고점대비(%)'} - set(A.columns):
        N[col] = np.nan
    N.to_csv(f'{out}/닉스.csv', index=False, encoding='utf-8-sig')
    try:
        E = pd.read_csv(f'{d}/예외검정.csv', encoding='utf-8-sig')
        X = pd.DataFrame(ex, index=N.index); X['번호'] = N['번호']
        E = E[[c for c in E.columns if c not in X.columns or c == '번호']].merge(X, on='번호', how='left')
        E.to_csv(f'{out}/예외검정.csv', index=False, encoding='utf-8-sig')
    except FileNotFoundError:
        pass


def feats(dd, B):
    f = F.stocks(dd)
    f = f[f['시장'].isin(['한국', '미국'])].reset_index(drop=True)
    P = F._px(dd)
    RG = O.regime(dd, P, B['국면']) if len(P) else {}
    DEF = {mk: v['DEF'] for mk, v in RG.items()}
    if DEF.get('미국'): DEF['한국'] = 1
    LR = O.layer_rs(dd, P) if len(P) else {}
    f['lay_rs_rank'] = [LR.get((mk, l), (np.nan, 0))[0] for mk, l in zip(f['시장'], f['layer'])]
    f['lay_rs_top'] = [int(LR[(mk, l)][0] <= max(1, LR[(mk, l)][1] // 3)) if (mk, l) in LR else np.nan for mk, l in zip(f['시장'], f['layer'])]
    f = O.relative(dd, P, f)
    f['DEF'] = f['시장'].map(DEF).fillna(0).astype(int)
    return f


def scores(f, SB, mask):
    """엔진과 같은 규칙: 공식 '예' 비율, 자료 있는 공식이 절반 미만이면 점수 없음. 국면 조건은 성적표에서 따로 나눈다."""
    f = f.copy()
    for v in mask:
        if v in f: f[v] = np.nan
    out = []
    for _, row in f.iterrows():
        r = row.to_dict(); o = {}
        for bid, b in SB.items():
            # 11/23 의장 '24개 블록 과거 값 채워': 정보 블록(B12·B17·B32 등)도 이력에 점수를 남긴다(역할로 거르지 않음)
            if b.get('대상') == '개별주' and r['구분'] != '개별주':
                continue
            if '조건' in b and not _ev(b['조건'], r):
                continue
            if '통과식' in b:
                v = _ev(b['통과식'], r); o[bid] = None if v is None else float(v); continue
            ok = [x for x in (_ev(e, r) for _, e, *_ in b['공식']) if x is not None]
            o[bid] = (sum(ok) / len(ok)) if ok and len(ok) * 2 >= len(b['공식']) else None
        out.append(o)
    return pd.DataFrame(out, index=f.index)


def formula_vars(SB):
    v = set()
    for b in SB.values():
        for _, e, *_ in b['공식']:
            v |= set(compile(e, '<f>', 'eval').co_names)
        for k in ('조건', '통과식'):
            if k in b: v |= set(compile(b[k], '<f>', 'eval').co_names)
    return v


def price_vars(d, L, B, dates):
    """가격으로 다시 계산되는 칸 = 기준일을 바꾸면 값이 달라지는 칸. 나머지(오늘 자료로 고정된 칸)는 과거 시험에서 비움."""
    V = formula_vars(B['종목']); fs = []
    for t in dates:
        tmp = tempfile.mkdtemp(); asof_dir(d, L, t, tmp); fs.append(feats(tmp, B)); shutil.rmtree(tmp)
    ch = set()
    for a in fs[1:]:
        for v in V:
            if v in a and v in fs[0] and not a[v].equals(fs[0][v]):
                x, y = pd.to_numeric(a[v], errors='coerce'), pd.to_numeric(fs[0][v], errors='coerce')
                if ((x - y).abs() > 1e-12).any() or (x.isna() != y.isna()).any():
                    ch.add(v)
    ch |= PRICE_ALWAYS & V
    return ch, V - ch


def _one(args):
    d, L, t, B, mask = args
    tmp = tempfile.mkdtemp()
    try:
        asof_dir(d, L, t, tmp)
        f = feats(tmp, B)
        close = L['Close'].loc[:t].ffill().iloc[-1].to_dict()
        f = HF.apply(f, t, close, d, (B.get('메모리반대') or {}).get('종목', []))
        f = HS.apply(f, t, d)   # B18 업종 ETF 60주선 이격(시타델 주봉 창고)
        f = HK.apply(f, t, d)   # B19·B14·B22 한국 수급(한투 일별 투자자)
        f = H13.apply(f, t, d)   # B21 장기 펀드 13F(공시일 기준)
        f = HSH.apply(f, t, d)   # B22 미국 공매도(FINRA 결제일, 공표 뒤)
        f = HE.apply(f, t, d)   # B20 ETF 자금(State Street 좌수 이력)
        f = EP.apply(f, t, d)   # B24 실제 이익 공식(EPS TTM, 공시일 기준) — 그 주 기준으로 다시
        S = scores(f, B['종목'], mask)
        S.insert(0, '날짜', t.date()); S.insert(1, '번호', f['번호']); S.insert(2, '종목', f['종목'])
        S.insert(3, '시장', f['시장']); S.insert(4, '구분', f['구분']); S.insert(5, '층', f['layer']); S.insert(6, '방어국면', f['DEF'])
        S.insert(7, 'ticker', f['ticker'])
        return S
    finally:
        shutil.rmtree(tmp)


def forward(L, H, ticker, t):
    c = L['Close'][ticker].dropna() if ticker in L['Close'] else pd.Series(dtype=float)
    i = c.index.searchsorted(t, side='right') - 1
    return {f'{w}주': (c.iloc[i + n] / c.iloc[i] - 1) * 100 if i >= 0 and i + n < len(c) else np.nan for w, n in H.items()}


def report(Z, SB, H):
    rows = []
    for bid, b in SB.items():
        if bid not in Z: continue
        reg = b.get('국면')
        z = Z if not reg else Z[Z['방어국면'] == (1 if reg == '방어' else 0)]
        z = z[z[bid].notna()]
        for w in H:
            k = f'{w}주'; zz = z[z[k].notna()]
            if zz['날짜'].nunique() < 8: continue
            y, n = zz[zz[bid] >= 0.5][k], zz[zz[bid] < 0.5][k]
            ic = zz.groupby('날짜').apply(lambda g: g[bid].rank().corr(g[k].rank()) if g[bid].nunique() > 1 else np.nan,
                                          include_groups=False).dropna()
            rows.append(dict(블록=bid, 질문=b['질문'], 영문=b.get('영문', ''), 국면=reg or '전체', 기간=k, 날짜수=zz['날짜'].nunique(),
                             예_종목수=len(y), 예_평균수익률=round(y.mean(), 2), 예_승률=round((y > 0).mean() * 100, 1),
                             아니오_평균수익률=round(n.mean(), 2), 아니오_승률=round((n > 0).mean() * 100, 1),
                             IC평균=round(ic.mean(), 3), IC_t=round(ic.mean() / ic.std() * math.sqrt(len(ic)), 2) if len(ic) > 2 and ic.std() > 0 else np.nan))
    return pd.DataFrame(rows)


def combo_score(Z, bl):
    X = Z[bl]
    s = X.mean(axis=1)
    return s.where(X.notna().sum(axis=1) * 2 >= len(bl))


def top_ret(Z, bl, k, n=None):
    n = n or TOPN
    z = Z.assign(_s=combo_score(Z, bl)).dropna(subset=['_s', k])
    if not len(z): return np.nan, np.nan, 0
    t = z.sort_values('_s', ascending=False).groupby('날짜').head(n)
    return t[k].mean(), (t[k] > 0).mean() * 100, t['날짜'].nunique()


def greedy(Z, cand, k, max_n=8):
    """앞으로 하나씩 더하기: 상위 5종목 평균 수익률이 가장 많이 오르는 블록을 더한다. 더 안 오르면 멈춤."""
    sel, best = [], -np.inf
    while len(sel) < max_n:
        tr = [(top_ret(Z, sel + [c], k)[0], c) for c in cand if c not in sel]
        tr = [x for x in tr if not np.isnan(x[0])]
        if not tr: break
        v, c = max(tr)
        if v <= best: break
        sel.append(c); best = v
    return sel


def walk(Z, SB, H, first_test_year):
    """해마다: 그해 1월 1일 전에 결과가 확정된 날짜만으로 조합을 고르고, 그해 성적을 잰다."""
    cand = [b for b in SB if b in Z and Z[b].notna().any() and SB[b]['역할'] != '매도']
    Z = Z.copy(); Z['날짜'] = pd.to_datetime(Z['날짜'])
    rows, last = [], {}
    for w, n in H.items():
        k = f'{w}주'
        for y in sorted(Z['날짜'].dt.year.unique()):
            if y < first_test_year: continue
            start = pd.Timestamp(f'{y}-01-01')
            tr = Z[Z['날짜'] + pd.tseries.offsets.BDay(n) < start]
            te = Z[(Z['날짜'] >= start) & (Z['날짜'] < pd.Timestamp(f'{y + 1}-01-01'))]
            if tr['날짜'].nunique() < 26 or not len(te): continue
            bl = greedy(tr, cand, k)
            if not bl: continue
            m, wr, nd = top_ret(te, bl, k)
            mt, wt, _ = top_ret(tr, bl, k)
            rows.append(dict(기간=k, 시험연도=y, 조합=' + '.join(bl), 블록수=len(bl), 고른기간_상위5_평균수익률=round(mt, 2),
                             고른기간_승률=round(wt, 1), 시험_날짜수=nd, 시험_상위5_평균수익률=round(m, 2), 시험_승률=round(wr, 1)))
        tr = Z[Z['날짜'] + pd.tseries.offsets.BDay(n) <= Z['날짜'].max()]
        last[k] = greedy(tr, cand, k)
    return pd.DataFrame(rows), last


def main(d, cfg=None, step='W-FRI', workers=None):
    d = os.path.abspath(d)   # 기준일 폴더의 링크가 상대 경로로 깨지지 않게
    B = QCC.load_blocks(cfg)
    for b in B.get('_꺼짐_종목', []):   # 11/24 의장 "B27은 일단 비워 놓읍시다": 켜기 목록에서 뺀 블록은 이력에도 점수 없음(엔진 '적용 안 함'과 같게)
        B['종목'].pop(b, None)
    global TOPN
    BT = B.get('성적표', {}); TOPN = int(BT.get('상위', 5))
    H = {str(k): v for k, v in BT.get('기간', {4: 20, 12: 60, 26: 130, 52: 260}).items()}
    L = load_long(d)
    C = L['Close'][[c for c in L['Close'].columns if not str(c).startswith('^')]]
    start = C.index[0] + pd.Timedelta(days=int(BT.get('준비일', 400)))   # 252거래일 + 여유
    dates = [C.index[C.index.searchsorted(x, side='right') - 1] for x in pd.date_range(start, C.index[-1], freq=step)]
    dates = sorted(set(dates) | {C.index[-1]})
    keep, mask = price_vars(d, L, B, [dates[-1], dates[-13], dates[-53]])
    if os.path.exists(f'{d}/장기/SEC재무_분기.csv.gz') or os.path.exists(f'{d}/장기/DART재무_분기.csv.gz'):
        mask = mask - HF.VARS; keep = keep | (HF.VARS & formula_vars(B['종목']))   # 재무 칸은 공시일 기준 과거 값으로 채움
    if os.path.exists(f'{d}/장기/시타델_주봉.csv'):
        mask = mask - HS.VARS; keep = keep | (HS.VARS & formula_vars(B['종목']))   # B18 60주선 이격은 주봉 창고로 그 주 값
    if os.path.exists(f'{d}/장기/국내수급_일별.csv.gz'):
        mask = mask - HK.VARS; keep = keep | (HK.VARS & formula_vars(B['종목']))   # 한국 수급은 일별 기록으로 그 주 값
    if os.path.exists(f'{d}/장기/장기펀드13F_이력.csv'):
        mask = mask - H13.VARS; keep = keep | (H13.VARS & formula_vars(B['종목']))   # B21 13F는 공시일 기준 그 주 값
    if os.path.exists(f'{d}/장기/공매도_미국_이력.csv.gz'):
        mask = mask - HSH.VARS; keep = keep | (HSH.VARS & formula_vars(B['종목']))   # B22 공매도는 FINRA 이력으로 그 주 값
    if os.path.exists(f'{d}/장기/ETF좌수_이력.csv.gz'):
        mask = mask - HE.VARS; keep = keep | (HE.VARS & formula_vars(B['종목']))   # B20 ETF 자금은 좌수 이력으로 그 주 값(이력 없는 ETF는 비움)
    if os.path.exists(f'{d}/{PS.name("EPS")}'):
        mask = mask - EP.VARS; keep = keep | (EP.VARS & formula_vars(B['종목']))   # B24 실제 이익 공식은 데이터베이스 EPS 칸으로 그 주 값
    print('비운 칸(과거 값 없음):', ', '.join(sorted(mask)))
    cache = os.path.join(d, '..', '블록점수이력.csv')
    old = pd.read_csv(cache, encoding='utf-8-sig') if os.path.exists(cache) else pd.DataFrame()
    sig = ','.join(sorted(mask)) + '|' + ','.join(SB for SB in B['종목'])
    if len(old) and str(old.get('_설정', pd.Series([''])).iloc[0]) != sig:
        old = pd.DataFrame()   # 블록·칸이 바뀌면 처음부터 다시
    # 11/22 의장(BNY·PEP·STX 26주 승률 없음): 새 날짜만 덧붙이면 나중에 유니버스에 들어온 종목은 과거 주가 영영 비었다.
    # 유니버스에 있고(기준층 S0 제외) 긴 가격이 처음 절반 안에 있는데 이력에 한 줄도 없는 종목이 있으면 처음부터 다시 계산.
    if len(old):
        up = os.path.join(d, '유니버스.csv')
        if os.path.exists(up):
            U = pd.read_csv(up, encoding='utf-8-sig')
            tc = next((c for c in ('yfinance 티커', 'ticker', '티커') if c in U), None)
            seen = set(old['번호'])
            half = C.iloc[:max(len(C) // 2, 1)]
            miss = [n for n, t, ly in zip(U['번호'], U[tc] if tc else [None] * len(U), U.get('층', pd.Series([''] * len(U))))
                    if n not in seen and t in half.columns and half[t].notna().any()]   # 11/23 의장 'QQQM·SPYM 블록 다 돌려' → 기준층(S0)도 이력에
            if miss:
                print(f'이력에 없는 종목 {len(miss)}개({", ".join(map(str, miss[:10]))}) → 처음부터 다시 계산')
                old = pd.DataFrame()
    have = set(pd.to_datetime(old['날짜']).dt.date) if len(old) else set()
    todo = [t for t in dates if t.date() not in have or t == dates[-1]]
    with Pool(workers or os.cpu_count()) as pool:
        new = pool.map(_one, [(d, L, t, B, mask) for t in todo])
    Z = pd.concat([old[old['날짜'].astype(str) != str(dates[-1].date())]] + new, ignore_index=True) if len(old) else pd.concat(new, ignore_index=True)
    Z['날짜'] = pd.to_datetime(Z['날짜']).dt.date
    fw = pd.DataFrame([forward(L, H, tk, pd.Timestamp(t)) for tk, t in zip(Z['ticker'], Z['날짜'])], index=Z.index)
    Z = pd.concat([Z.drop(columns=[c for c in fw.columns if c in Z]), fw], axis=1)
    Z['_설정'] = ''
    Z.loc[Z.index[:1], '_설정'] = sig   # 설정 표시는 첫 줄에만(파일 크기)
    Z.round(3).to_csv(cache, index=False, encoding='utf-8-sig')
    SB = B['종목']
    Z = Z[Z['층'] != 'S0']   # 이력 파일엔 기준층(QQQM·SPYM 등)도 남기고, 종목 성적표·조합 시험(종목 고르기)에서만 뺀다
    R = report(Z, SB, H)
    R.to_csv(os.path.join(d, '..', '블록성적.csv'), index=False, encoding='utf-8-sig')
    W, last = walk(Z, SB, H, int(BT.get('첫시험연도', pd.Timestamp(dates[0]).year + 2)))
    W.to_csv(os.path.join(d, '..', '조합시험.csv'), index=False, encoding='utf-8-sig')
    today = Z[Z['날짜'] == dates[-1].date()]
    # 11/19 의장: 오늘 후보는 엔진과 같은 문(이익 거르기·제2의 젠슨 황 거르기·추천 자격 연매출)을 통과한 종목에서만.
    # 엔진 판정표(out_판정표.csv)의 판정 '후보'가 그 문. 판정표가 없으면 후보를 내지 않는다.
    jp = os.path.join(d, '..', 'out_판정표.csv')
    gate = set(pd.read_csv(jp, encoding='utf-8-sig').query("판정 == '후보'")['번호']) if os.path.exists(jp) else set()
    today = today[today['번호'].isin(gate)]
    T = []
    for k, bl in last.items():
        if not bl: continue
        t = today.assign(종합=combo_score(today, bl)).dropna(subset=['종합']).sort_values('종합', ascending=False).head(5)
        for i, (_, r) in enumerate(t.iterrows(), 1):
            T.append(dict(기간=k, 순위=i, 종목=r['종목'], 시장=r['시장'], 층=r['층'], 종합=round(r['종합'], 3), 조합=' + '.join(bl)))
    pd.DataFrame(T).to_csv(os.path.join(d, '..', '조합후보_오늘.csv'), index=False, encoding='utf-8-sig')
    print(f'날짜 {len(dates)}개(새로 {len(todo)}), 가격으로 다시 계산한 칸 {len(keep)}, 비운 칸 {len(mask)}')
    print('블록 성적에 들어간 블록:', sorted(R['블록'].unique()) if len(R) else [])
    print(W.to_string(index=False))
    return Z, R, W


if __name__ == '__main__':
    main(sys.argv[1])
