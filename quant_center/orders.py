"""국면(B00)과 주문 한도(B27·B28·B29)·분할(B30)·층별 바구니. 모든 수치는 blocks.yaml '국면'·'주문' 칸에서 읽는다.
11/17 의장 지시: 외부 AI 검토(챗지 B00·B27~B30, 제이미 C_rate·C_techvol·C_breadth 기록) 반영. 클로드 판단 없이 식으로만."""
import numpy as np, pandas as pd

AI, DEFL = ('S1', 'S2', 'S3'), ('S5', 'S6')


def _u(d):
    U = pd.read_csv(f'{d}/유니버스.csv', encoding='utf-8-sig').drop_duplicates('yfinance 티커')
    return U.set_index('yfinance 티커')


def regime(d, P, C):
    """시장별 AI÷금융·방어 동일가중 비율. 진입: G≤g_in·M≤m_in이 최근 5일 중 3일+당일, 해제: G≥g_out·M≥m_out 같은 방식, 그 사이 유지."""
    U = _u(d); r = P.pct_change(fill_method=None); out = {}
    for mk in ('한국', '미국'):
        ai = [t for t in P if t in U.index and U.at[t, '시장'] == mk and U.at[t, '층'] in AI]
        df = [t for t in P if t in U.index and U.at[t, '시장'] == mk and U.at[t, '층'] in DEFL]
        if not ai or not df:
            continue
        A = (1 + r[ai].mean(axis=1).fillna(0)).cumprod(); N = (1 + r[df].mean(axis=1).fillna(0)).cumprod(); X = A / N
        G = (X / X.rolling(50).mean() - 1) * 100; M = (X / X.shift(20) - 1) * 100
        cin = (G <= C['G_진입']) & (M <= C['M_진입']); cout = (G >= C['G_해제']) & (M >= C['M_해제'])
        n, k = C['창'], C['충족일']
        st, since, hist = False, None, []
        for i in range(len(X)):
            if pd.isna(G.iloc[i]) or pd.isna(M.iloc[i]):
                hist.append(st); continue
            win_in = cin.iloc[max(0, i - n + 1):i + 1].sum(); win_out = cout.iloc[max(0, i - n + 1):i + 1].sum()
            if not st and cin.iloc[i] and win_in >= k:
                st, since = True, X.index[i]
            elif st and cout.iloc[i] and win_out >= k:
                st, since = False, X.index[i]
            hist.append(st)
        out[mk] = dict(DEF=int(st), G=round(float(G.iloc[-1]), 2), M=round(float(M.iloc[-1]), 2),
                       since=None if since is None else str(since.date()))
    return out


def _z(x, last):
    """겹치지 않는 직전 5일 단위 관측치(최대 52개) 대비 로버스트 z. 26개 미만·MAD 0이면 None."""
    h = x.iloc[:-5][::-1].iloc[::5].dropna().head(52)
    if len(h) < 26:
        return None
    mad = (h - h.median()).abs().median()
    return None if mad == 0 else float((last - h.median()) / (1.4826 * mad))


def limits(d, P, f, O):
    """층(시장 무관)별 주문 승수와 경보. 여러 경보면 가장 엄격한 한도 하나."""
    U = _u(d); mult = {}; why = {}
    def hit(lay, m, txt):
        mult[lay] = min(mult.get(lay, 1.0), m); why.setdefault(lay, []).append(txt)
    # B27 대장 이탈
    r5 = P / P.shift(5) - 1
    for lay, ld in (O.get('대장') or {}).items():
        if ld not in P:
            continue
        peers = [t for t in P if t != ld and t in U.index and U.at[t, '층'] == lay]
        pm = r5[peers].median(axis=1); D5 = (r5[ld] - pm) * 100
        last = D5.dropna()
        if not len(last):
            continue
        z = _z(last, last.iloc[-1])
        if pm.iloc[-1] > 0 and last.iloc[-1] <= O['B27_격차'] and z is not None and z <= O['B27_z']:
            hit(lay, O['승수'], f"B27 대장 이탈({U.at[ld, '정식 종목명']} 5일 격차 {last.iloc[-1]:.1f}%p, z {z:.1f})")
    # B28 확정 대형 이벤트: 이벤트 뒤 첫 세션까지 남은 매수 세션 ≤ 3
    try:
        CAL = pd.read_csv(f'{d}/변수달력.csv', encoding='utf-8-sig')
    except FileNotFoundError:
        CAL = pd.DataFrame()
    today = np.datetime64(pd.Timestamp.now(tz='Asia/Seoul').date())
    if len(CAL) and {'날짜', '영향 층', '확정'} <= set(CAL.columns):
        for _, e in CAL.iterrows():
            if str(e['확정']).strip() != '예':
                continue
            dt = pd.to_datetime(e['날짜'], errors='coerce')
            if pd.isna(dt):
                continue
            ev = np.datetime64(dt.date())
            left = np.busday_count(today, ev + np.timedelta64(1, 'D')) + 1
            if today <= np.busday_offset(ev, 1, roll='forward') and left <= O['B28_세션']:
                for lay in str(e['영향 층']).split('|'):
                    hit(lay, O['승수'], f"B28 확정 이벤트({e['사건']}, {str(dt.date())})")
    # B29 업종 수급 이동(이력이 쌓이기 전에는 방향·비율·규모로, z는 이력 26개 이상부터)
    flow = {}
    k = f[(f['시장'] == '한국') & (f['구분'] == '개별주') & f['f5'].notna()] if 'f5' in f else pd.DataFrame()
    for lay, g in k.groupby('layer'):
        if len(g) < 2: continue
        neg = (g['f5'] < 0).mean(); pos = (g['f5'] > 0).mean()
        flow[('한국', lay)] = -1 if neg >= O['B29_비율'] and g['f5'].sum() < 0 else (1 if pos >= O['B29_비율'] and g['f5'].sum() > 0 else 0)
    try:
        E = pd.read_csv(f'{d}/ETF자금.csv', encoding='utf-8-sig').set_index('코드')
        for lay, tk in (O.get('미국_업종ETF') or {}).items():
            if tk in E.index:
                v = pd.to_numeric(E.at[tk, '유입_5일'], errors='coerce') / pd.to_numeric(E.at[tk, '순자산'], errors='coerce') * 100
                flow[('미국', lay)] = -1 if v <= -O['B29_미국_%'] else (1 if v >= O['B29_미국_%'] else 0)
    except (FileNotFoundError, KeyError):
        pass
    for mk in ('한국', '미국'):
        out_ai = [l for l in AI if flow.get((mk, l)) == -1]; in_df = [l for l in DEFL if flow.get((mk, l)) == 1]
        if out_ai and in_df:
            for l in out_ai:
                hit(l, O['승수'], f"B29 수급 이동({mk} {l} 유출·{'/'.join(in_df)} 유입)")
    return mult, {k: ' / '.join(v) for k, v in why.items()}, flow


def record(m):
    """제이미 국면 조건 3개: 매일 계산해 기록만(발동식에는 안 씀)."""
    g = lambda k: m.get(k)
    c = {}
    if g('US10Y') is not None:
        c['C_rate'] = int((g('US10Y') >= 4.8) or ((g('REAL10Y') or 0) - (g('REAL10Y_1W') or g('REAL10Y') or 0) >= 0.20))
    if g('VXN_PCT') is not None and g('VIX_PCT') is not None:
        c['C_techvol'] = int(g('VXN_PCT') - g('VIX_PCT') >= 15 and g('VXN_PCT') >= 80)
    if g('EWNDX_PCT') is not None and g('VOLT') is not None:
        c['C_breadth'] = int(g('EWNDX_PCT') >= 75 and g('VOLT') <= 0.60)
    return c


def layer_rs(d, P):
    """업종(층) 상대강도(AQR): 시장별 층 바스켓 63·126·252일 수익률 평균의 순위(1=최강). 층 수의 1/3 이내 = 주도 층."""
    U = _u(d); r = P.pct_change(fill_method=None); rank = {}
    for mk in ('한국', '미국'):
        sc = {}
        for lay in ('S1', 'S2', 'S3', 'S4', 'S5', 'S6'):
            tk = [t for t in P if t in U.index and U.at[t, '시장'] == mk and U.at[t, '층'] == lay]
            if len(tk) < 2:
                continue
            B = (1 + r[tk].mean(axis=1).fillna(0)).cumprod()
            sc[lay] = np.mean([B.iloc[-1] / B.iloc[-1 - n] - 1 for n in (63, 126, 252) if len(B) > n])
        s = pd.Series(sc).rank(ascending=False)
        for lay, v in s.items():
            rank[(mk, lay)] = (int(v), len(s))
    return rank


def crowding(d, P, f, m, O):
    """쏠림(MSCI·GS·Man): 층별 4지표 중 3개 이상이면 그 층 주문 승수 0.5. 종목 간 상관 급등(B07 CORR_JUMP)이면 전 층."""
    U = _u(d); r = P.pct_change(fill_method=None); out = {}
    for lay in ('S1', 'S2', 'S3', 'S4', 'S5', 'S6'):
        tk = [t for t in P if t in U.index and U.at[t, '층'] == lay]
        if len(tk) < 3:
            continue
        B = (1 + r[tk].mean(axis=1).fillna(0)).cumprod()
        r60 = (B / B.shift(60) - 1).dropna().tail(252)
        a = r60.iloc[-1] >= r60.quantile(0.9)
        rr = r[tk].tail(252)
        c = lambda x: (np.nansum(x.corr().values) - x.shape[1]) / (x.shape[1] ** 2 - x.shape[1])
        b = c(rr.tail(20)) - c(rr) >= O['쏠림_상관']
        bv = B.pct_change().rolling(20).std().dropna().tail(252)
        cc = bv.iloc[-1] >= O['쏠림_변동성배'] * bv.median()
        pp = f.loc[f['layer'] == lay, 'per_pct3'].median() if 'per_pct3' in f else np.nan
        dd = bool(pp >= O['쏠림_PER백분위']) if not pd.isna(pp) else False
        n = int(a) + int(b) + int(cc) + int(dd)
        if n >= O['쏠림_개수']:
            out[lay] = f'쏠림 {n}/4(60일 수익률 상위 10%·상관 급등·변동성 1.5배·3년 PER 상위 20% 중)'
    if (m.get('CORR_JUMP') or 0) >= O['쏠림_상관']:
        for lay in ('S1', 'S2', 'S3', 'S4', 'S5', 'S6'):
            out[lay] = (out.get(lay, '') + ' / 시장 상관 급등(B07)').strip(' /')
    return out


def cta_flip(d):
    """CTA 매도 전환까지 남은 %(JPM 방식): 21·63·100일 추세 신호가 뒤집히는 지수 수준까지 거리. 지금 플러스인 신호 중 가장 가까운 것."""
    try:
        I = pd.read_csv(f'{d}/지수2년.csv', encoding='utf-8-sig', index_col=0, parse_dates=True)
    except FileNotFoundError:
        return {}
    out = {}
    for mk, k in (('미국', '^GSPC'), ('한국', '^KS11')):
        x = I[k].dropna() if k in I else pd.Series(dtype=float)
        if len(x) < 101:
            continue
        dist = [(x.iloc[-1 - n] / x.iloc[-1] - 1) * 100 for n in (21, 63, 100) if x.iloc[-1] > x.iloc[-1 - n]]
        out[mk] = None if not dist else round(-max(dist), 2)   # 몇 % 더 빠지면 첫 매도 전환
    return out


def index_regime(d):
    """지수 252·21일 추세 4국면(BlackRock·MSCI·GS) — 기록만(발동식은 B00)."""
    try:
        I = pd.read_csv(f'{d}/지수2년.csv', encoding='utf-8-sig', index_col=0, parse_dates=True)
    except FileNotFoundError:
        return {}
    out = {}
    for mk, k in (('미국', '^GSPC'), ('한국', '^KS11')):
        x = I[k].dropna() if k in I else pd.Series(dtype=float)
        if len(x) < 253:
            continue
        s, q = x.iloc[-1] > x.iloc[-253], x.iloc[-1] > x.iloc[-22]
        out[mk] = {(True, True): '강세', (True, False): '조정', (False, False): '약세', (False, True): '반등'}[(s, q)]
    return out


def basket_dd(d, P):
    """직전 추천 바구니 낙폭(Millennium): 추천장부 마지막 추천일 동일가중 수익률(절대값, %)."""
    try:
        L = pd.read_csv('/mnt/project-files/퀀트센터/추천기록/추천장부.csv', encoding='utf-8-sig')
    except FileNotFoundError:
        return None
    if not len(L):
        return None
    last = L[L['추천일'] == L['추천일'].max()]
    rs = [P[t].dropna().iloc[-1] / b - 1 for t, b in zip(last['티커'], last['기준가']) if t in P and P[t].notna().any() and b]
    return None if not rs else round(float(np.mean(rs)) * 100, 2)
