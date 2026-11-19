"""자료 어댑터: 07시 파일 + 퀀트센터 파일 → 종목 한 줄(features) + 시장 한 줄(market).
새 자료를 붙이려면 여기에 어댑터 함수 하나를 더한다. 칸 이름은 blocks.yaml 식에서 쓰는 이름."""
import re
import numpy as np
import pandas as pd

EVENT = {'방산': ['종전', '휴전', '평화협상', 'ceasefire', 'peace deal', 'truce'],
         '우주': ['종전', '휴전', 'ceasefire'],
         '조선': ['관세', '선박 수수료', 'port fee'],
         '자동차': ['관세', 'tariff'],
         '원전': ['원전 취소', '계약 종료'],
         '화장품': ['관세', 'tariff']}


def _r(d, name):
    try:
        return pd.read_csv(f'{d}/{name}.csv', encoding='utf-8-sig')
    except FileNotFoundError:
        return pd.DataFrame()


def _num(s):
    return pd.to_numeric(s, errors='coerce')


def _streak(x):
    m = re.match(r'순(매수|매도)\s*(\d+)', str(x))
    return np.nan if not m else (int(m.group(2)) if m.group(1) == '매수' else -int(m.group(2)))


def _px(d):
    try:
        return pd.read_csv(f'{d}/가격2년.csv', encoding='utf-8-sig', index_col=0, parse_dates=True)
    except FileNotFoundError:
        return pd.DataFrame()


def stocks(d):
    N = _r(d, '닉스')
    f = pd.DataFrame({'번호': N['번호'], '종목': N['정식 종목명'], '시장': N['시장'], '구분': N['구분'],
                      'ticker': N['yfinance 티커']})
    c = lambda k: _num(N[k])
    f = f.assign(close=c('종가'), dd52=c('52주고점대비(%)'), rsi_d=c('일_RSI'), gap50=c('일_50일_이격도'),
                 m5=c('월_5개월선'), pctb_d=c('일_볼린저_%B'), cci_d=c('일_CCI'), sto_k_d=c('일_STO_K'),
                 osc_d=c('일_MACD오실레이터'), osc_d1=c('일_MACD오실레이터_1봉전'),
                 osc_w=c('주_MACD오실레이터'), osc_w1=c('주_MACD오실레이터_1봉전'), osc_w2=c('주_MACD오실레이터_2봉전'),
                 rsi_w=c('주_RSI'), gap60w=c('주_60주_이격도'), vol_w=c('주_거래량_20주평균대비'),
                 tail_low_d=c('일_봉_아랫꼬리(%)'), body_d=c('일_봉_몸통(%)').abs(),
                 sup_touch_d=N['일_지지1_터치'].astype(str).isin(['예', 'True', '1', 'Y']).astype(int))
    f['m5gap'] = f.close / f.m5 * 100
    E = _r(d, '예외검정')
    if len(E):
        e = pd.DataFrame({'번호': E['번호'], 'layer': E['층'], 'p10': _num(E['10년_하락p']), 'p5': _num(E['5년_하락p']),
                          'p3': _num(E['3년_하락p']), 'res4p': _num(E['잔차4주_하락p']), 'res13p': _num(E['잔차13주_하락p']),
                          'up10_13': _num(E['10년_13주상승p']), 'beta': _num(E['베타(주간2년)']), 'sigma_note': E['예외 정리']})
        f = f.merge(e, on='번호', how='left')
    F = _r(d, '국내수급')
    if len(F):
        q = pd.DataFrame({'번호': F['번호'], 'f5': _num(F['외국인 5일(억원)']), 'f20': _num(F['외국인 20일(억원)']),
                          'inst5': _num(F['기관 5일(억원)']), 'ind5': _num(F['개인 5일(억원)']), 'fstreak': F['외국인 연속'].map(_streak),
                          'dip_buy': F['표시'].astype(str).str.contains('주가↓·외국인↑').astype(int)})
        for c, k in (('외국인 5일 z', 'fz5'), ('기관 5일 z', 'iz5')):   # 11/19 B20 수급 z점수(b09_kflow, 자기 30일 대비)
            q[k] = _num(F[c]) if c in F else np.nan
        f = f.merge(q, on='번호', how='left')
    V = _r(d, '밸류에이션')
    if len(V) and '시가총액(억원)' in V:
        f = f.merge(pd.DataFrame({'번호': V['번호'], 'mcap_kr': _num(V['시가총액(억원)'])}), on='번호', how='left')
    if len(V):
        f = f.merge(pd.DataFrame({'번호': V['번호'], 'pbr': _num(V['PBR']), 'fper': _num(V['선행 PER(야후)']),
                                  'per_kis': _num(V['PER'])}), on='번호', how='left')
    for name, per, roe in (('DART', 'PER TTM(주가÷EPS)', 'ROE TTM(%)'), ('SEC', 'PER TTM(주가÷EPS)', 'ROE TTM(%)')):
        X = _r(d, name)
        if len(X):
            x = pd.DataFrame({'번호': X['번호'], f'per_{name}': _num(X[per]), f'roe_{name}': _num(X[roe])})
            f = f.merge(x, on='번호', how='left')
    nan = pd.Series(np.nan, index=f.index)
    f['per_ttm'] = f.get('per_DART', nan).combine_first(f.get('per_SEC', nan)).combine_first(f.get('per_kis', nan))
    f['roe'] = f.get('roe_DART', nan).combine_first(f.get('roe_SEC', nan))
    # 층 안 순위(낮을수록 쌈)
    for k in ('per_ttm', 'pbr'):
        v = f[k].where(f[k] > 0)
        f[f'{k.split("_")[0]}_rank'] = v.groupby(f['layer']).rank(pct=True)
    # 분기 실적·추정치(야후)
    Q = _r(d, '분기실적')
    if len(Q):
        q = Q.rename(columns={'실적지표': 'kind', '이익_전년비': 'op_yoy', 'OPM_전년비': 'opm_yoy', 'OPM_2연속': 'opm2',
                              '매출_전년비': 'rev_yoy', '추정_30일': 'est30', '추정_90일': 'est90', '상향30': 'up30',
                              '하향30': 'dn30', '최근분기': 'last_q', 'OPM': 'opm'})
        f = f.merge(q[[c for c in ['번호', 'kind', 'op_yoy', 'opm_yoy', 'opm2', 'rev_yoy', 'est30', 'est90', 'up30', 'dn30',
                                   'last_q', 'opm'] if c in q]], on='번호', how='left')
    # ETF 자체 자금 유출입(07시 ETF자금, 억원·백만달러)
    A = _r(d, 'ETF자금')
    if len(A):
        f = f.merge(pd.DataFrame({'번호': A['번호'], 'etf_flow5': _num(A['유입_5일']), 'etf_flow20': _num(A['유입_20일'])}), on='번호', how='left')
    # 분기 원자료로 다시 계산: 한국은 DART 3분기 잠정실적을 최신 분기로 붙임(야후에 아직 없음)
    QR = _r(d, '분기원자료')
    if len(QR):
        DQ = _r(d, 'DART')
        add = []
        for _, x in DQ.iterrows():
            if str(x.get('잠정 분기')) == '2026 3Q':
                add.append(dict(번호=x['번호'], 분기='2026-09-30', 매출=_num(pd.Series([x['잠정 매출(억원)']])).iloc[0] * 1e8,
                                영업이익=_num(pd.Series([x['잠정 영업이익(억원)']])).iloc[0] * 1e8,
                                순이익=_num(pd.Series([x['잠정 순이익(억원)']])).iloc[0] * 1e8, 출처='DART 잠정'))
        QR = pd.concat([QR, pd.DataFrame(add)]).drop_duplicates(['번호', '분기'], keep='last')
        rows = []
        for no, g in QR.groupby('번호'):
            g = g.sort_values('분기'); g['분기'] = pd.to_datetime(g['분기'])
            fin = g.loc[g['출처'] == '야후', '영업이익'].isna().all()
            g['x'] = g['순이익'] if fin else g['영업이익']
            g = g[~((g['출처'] == 'DART 잠정') & g['x'].isna())]   # 금융 잠정에 이익 칸 없으면 버림
            if fin:   # 금융: DART 잠정 매출(영업수익 총액)은 야후 매출과 정의가 달라 이익률 비교 안 함
                g.loc[g['출처'] == 'DART 잠정', '매출'] = np.nan
            g['m'] = g['x'] / g['매출'] * 100
            def yoy(i, col):
                cur = g.iloc[i]; prev = g[(g['분기'] - cur['분기'] + pd.Timedelta(days=365)).abs() <= pd.Timedelta(days=20)]
                if not len(prev) or pd.isna(cur[col]) or pd.isna(prev[col].iloc[0]): return np.nan
                pv = prev[col].iloc[0]
                if col == 'm': return cur[col] - pv
                return (cur[col] / pv - 1) * 100 if pv > 0 else (999 if cur[col] > 0 else -999)
            r = dict(번호=no, kind='순이익' if fin else '영업이익', last_q=str(g['분기'].iloc[-1].date()), q_src=g['출처'].iloc[-1],
                     op_yoy=yoy(-1, 'x'), opm_yoy=yoy(-1, 'm'), rev_yoy=yoy(-1, '매출'), opm=g['m'].iloc[-1],
                     prev_op_yoy=yoy(-2, 'x') if len(g) > 1 else np.nan,
                     opm2=int(g['m'].iloc[-1] > g['m'].iloc[-2] > g['m'].iloc[-3]) if len(g) >= 3 and g['m'].tail(3).notna().all() else np.nan)
            rows.append(r)
        RQ = pd.DataFrame(rows)
        f = f.drop(columns=[c for c in ['kind', 'op_yoy', 'opm_yoy', 'opm2', 'rev_yoy', 'last_q', 'opm'] if c in f]).merge(RQ, on='번호', how='left')
    # 장기 펀드 13F(fetch_13f.py): 지난 분기 늘렸나·줄였나(미국 상장 주식만)
    LT = _r(d, '장기펀드13F')
    if len(LT):
        f = f.merge(LT[['ticker', 'lt_funds', 'lt_up', 'lt_dn', 'lt_net', 'lt_net_prev', '분기']].rename(columns={'분기': 'lt_q'}),
                    on='ticker', how='left')
    # 퀀트센터 자료(BLOCK20 quant_live)
    K = _r(d, '퀀트자료')
    if len(K):
        k = pd.DataFrame({'ticker': K['ticker'], 'surprise': _num(K['서프라이즈_최근(%)']),
                          'surp4': _num(K['서프라이즈_최근4번_플러스']), 'fcf': _num(K['FCF(TTM)']),
                          'fcf_yield': _num(K['FCF수익률(%)']), 'z': _num(K['Z점수']), 'accel': _num(K['영업이익가속(%p)']),
                          'fscore': _num(K['F점수(대용)']), 'pension20': _num(K['연기금_20일(억)'])})
        f = f.merge(k, on='ticker', how='left')
    L = _r(d, 'forward_log')
    if len(L):
        L.columns = [c.lstrip('﻿') for c in L.columns]
        L = L[L['asof'] == L['asof'].max()]
        f = f.merge(L[['ticker', 'p63', 'n0_63', 'p126', 'n0_126', 'p252', 'n0_252', 'cap']], on='ticker', how='left')
    C = _r(d, '1달조합')
    if len(C):
        f = f.merge(pd.DataFrame({'번호': C['번호'], 'combo1m': (C['판정'] == '충족').astype(int)}), on='번호', how='left')
    # 업종 ETF(섹터 60주·자금): 종목이 상위 10에 든 섹터 ETF 값
    Y = _r(d, '역도산')
    if len(Y):
        etf = Y[Y['구분'] == 'ETF'].set_index('ETF')
        h = Y[Y['구분'] == '종목'][['ETF', '티커']].copy()
        h['티커'] = h['티커'].astype(str).str.upper()
        h['sec_gap60'] = h['ETF'].map(_num(etf['60주 이격']))
        h['sec_flow5'] = h['ETF'].map(_num(etf['자금5일']))
        h = h.groupby('티커')[['sec_gap60', 'sec_flow5']].first()
        key = f['ticker'].astype(str).str.upper().str.replace(r'\.(KS|KQ)$', '', regex=True)
        f['sec_gap60'] = key.map(h['sec_gap60'])
        f['sec_flow5'] = key.map(h['sec_flow5'])
        # 11/19 완성도: 어떤 업종 ETF 상위 10에도 없는 개별주는 같은 시장·층 종목들이 받은 업종 ETF 값(중앙값)으로 채움
        for c in ('sec_gap60', 'sec_flow5'):
            fill = f.groupby(['시장', 'layer'])[c].transform('median')
            f[c] = f[c].where(f[c].notna() | (f['구분'] != '개별주'), fill)
    # 재무 건전성·연매출(야후 info, 200종목)
    H = _r(d, '재무건전성')
    if len(H):
        h = pd.DataFrame({'번호': H['번호'], 'debt': _num(H['총부채']), 'ebitda': _num(H['EBITDA']),
                          'fcf_y': _num(H['FCF']), 'mcap': _num(H['시총'])})
        f = f.merge(h, on='번호', how='left')
        f['debt_ebitda'] = np.where(f['ebitda'] > 0, f['debt'] / f['ebitda'], np.where(f['ebitda'].notna(), 99, np.nan))
        for k in ('fcf', 'fcf_yield'):
            if k not in f: f[k] = np.nan
        f['fcf'] = f['fcf'].combine_first(f['fcf_y'])
        f['fcf_yield'] = f['fcf_yield'].combine_first(f['fcf_y'] / f['mcap'] * 100)
    FZ = _r(d, 'FZ점수')   # 200종목 직접 계산(야후 연간 재무제표), 퀀트자료 없는 종목 채움
    if len(FZ):
        fz = pd.DataFrame({'번호': FZ['번호'], 'f_y': _num(FZ['F점수']), 'z_y': _num(FZ['Z점수'])})
        f = f.merge(fz, on='번호', how='left')
        for k, y in (('fscore', 'f_y'), ('z', 'z_y')):
            f[k] = (f[k] if k in f else pd.Series(np.nan, index=f.index)).combine_first(f[y])
    # 자기역사 PER 3년 밴드(11/16 의장: 3년치만)
    P3 = _r(d, 'PER3년')
    if P3 is not None and len(P3):
        f = f.merge(P3[['번호', 'per_now', 'per_med3', 'per_pct3']], on='번호', how='left')
    else:
        f['per_pct3'] = np.nan; f['per_med3'] = np.nan
    RV = _r(d, '연매출')
    if len(RV):
        f = f.merge(pd.DataFrame({'번호': RV['번호'], 'rev_krw': _num(RV['연매출(원)'])}), on='번호', how='left')
    # 가격 2년(야후): 종목 위험(변동성·꼬리) 
    P = _px(d)
    if len(P):
        r = np.log(P).diff()
        vol = r.tail(60).std() * np.sqrt(252) * 100
        es = r.tail(252).apply(lambda x: x.dropna().sort_values().head(max(1, int(len(x.dropna()) * 0.05))).mean() * 100)
        f['vol60'] = f['ticker'].map(vol)
        f['es5'] = f['ticker'].map(es)
        # 돈의 방향: 시장(코스피·코스닥·S&P500) 대비 5·20일 상대수익, 같은 층 대비, 50일선
        try:
            I = pd.read_csv(f'{d}/지수2년.csv', encoding='utf-8-sig', index_col=0, parse_dates=True)
        except FileNotFoundError:
            I = pd.DataFrame()
        def ret(x, n):
            x = x.dropna(); return (x.iloc[-1] / x.iloc[-1 - n] - 1) * 100 if len(x) > n else np.nan
        r5 = P.apply(lambda x: ret(x, 5)); r20 = P.apply(lambda x: ret(x, 20))
        ma50 = P.apply(lambda x: x.dropna().tail(50).mean()); last = P.apply(lambda x: x.dropna().iloc[-1] if x.notna().any() else np.nan)
        f['ret5'] = f['ticker'].map(r5); f['ret20'] = f['ticker'].map(r20)
        f['above50'] = (f['ticker'].map(last) > f['ticker'].map(ma50)).astype(int).where(f['ticker'].map(ma50).notna())
        idx = np.where(f['ticker'].astype(str).str.endswith('.KQ'), '^KQ11', np.where(f['시장'] == '한국', '^KS11', '^GSPC'))
        i5 = {k: ret(I[k], 5) for k in I}; i20 = {k: ret(I[k], 20) for k in I}
        f['rs5'] = f['ret5'] - pd.Series(idx).map(i5).values
        f['rs20'] = f['ret20'] - pd.Series(idx).map(i20).values
        f['peer20'] = f['ret20'] - f.groupby(['시장', 'layer'])['ret20'].transform('median')
        # 11/17 운용사·외부 AI 반영: 중간 속도 추세(Winton·AQR), 방어주(Robeco·챗지), 가짜 바닥(제이미 B29)
        for n in (63, 120, 126):
            f[f'ret{n}'] = f['ticker'].map(P.apply(lambda x, n=n: ret(x, n)))
        v126 = r.tail(126).std() * np.sqrt(252) * 100
        f['vol126'] = f['ticker'].map(v126)
        f['vol126_rank'] = f.groupby(['시장', 'layer'])['vol126'].rank(pct=True)
        ma200 = P.apply(lambda x: x.dropna().tail(200).mean())
        f['ma200'] = f['ticker'].map(ma200); f['ma50'] = f['ticker'].map(ma50)
        f['survive'] = ((f['ticker'].map(last) >= f['ma200'] * 0.95) & ~((f['ma50'] < f['ma200']) & (f['ret5'] >= 5))).astype(int).where(f['ma200'].notna())
        # 11/19 의장 "금융공학 공식": Carver EWMAC 추세 예측치, Frog-in-the-pan, 잔차 모멘텀, MAX 효과
        def ewmac(x, fa, sl, k):   # Carver(Systematic Trading): (빠른 EWMA − 느린 EWMA) ÷ 가격 변동성(36일 EW) × 예측 눈금, ±20
            x = x.dropna()
            if len(x) < sl: return np.nan
            sd = x.diff().ewm(span=36).std().iloc[-1]
            return float(np.clip((x.ewm(span=fa).mean().iloc[-1] - x.ewm(span=sl).mean().iloc[-1]) / sd * k, -20, 20)) if sd > 0 else np.nan
        f['ewmac16'] = f['ticker'].map(P.apply(lambda x: ewmac(x, 16, 64, 3.75)))
        f['ewmac32'] = f['ticker'].map(P.apply(lambda x: ewmac(x, 32, 128, 2.65)))
        f['ewmac'] = (f['ewmac16'] + f['ewmac32']) / 2
        r252 = r.tail(252)
        f['ret252'] = f['ticker'].map(P.apply(lambda x: ret(x, 252)))
        # Da·Gurun·Warachka(2014): ID = sign(1년 수익) × (내린 날 비율 − 오른 날 비율). 음수 = 조금씩 꾸준히 오름(추세 지속)
        pos = (r252 > 0).sum() / r252.notna().sum(); neg = (r252 < 0).sum() / r252.notna().sum()
        f['fip_id'] = np.sign(f['ret252']) * (f['ticker'].map(neg) - f['ticker'].map(pos))
        # Blitz·Huij·Martens(2011): 시장 베타를 뺀 잔차의 12−1달 합 ÷ 잔차 표준편차
        IR_ = np.log(I).diff() if len(I) else pd.DataFrame()
        def resmom(t, ix):
            if ix not in IR_ or t not in r: return np.nan
            z = pd.concat([r[t], IR_[ix]], axis=1).dropna().tail(252)
            if len(z) < 200: return np.nan
            y, xm = z.iloc[:, 0].values, z.iloc[:, 1].values
            b = np.polyfit(xm, y, 1); e = y - np.polyval(b, xm)
            return float(e[:-21].sum() / (e[:-21].std() * np.sqrt(len(e) - 21)))
        f['resmom'] = [resmom(t, ix) for t, ix in zip(f['ticker'], idx)]
        # 11/19 의장 B12 '제2의 젠슨 황': 사건 연구(event study) 가격 충격. 시장 베타를 뺀 하루 잔차 ÷ 잔차 표준편차(1년)
        def shock(t, ix, n=5):
            if ix not in IR_ or t not in r: return [np.nan] * n
            z = pd.concat([r[t], IR_[ix]], axis=1).dropna().tail(252)
            if len(z) < 200: return [np.nan] * n
            y, xm = z.iloc[:, 0].values, z.iloc[:, 1].values
            b = np.polyfit(xm, y, 1); e = y - np.polyval(b, xm)
            return list(e[-n:] / e[:-n].std())
        SZ = pd.DataFrame([shock(t, ix) for t, ix in zip(f['ticker'], idx)], index=f.index)
        f['shock_z5'] = SZ.min(axis=1)                                   # 최근 5일 중 가장 큰 잔차 하락(σ)
        f['shock_own'] = (f['shock_z5'] <= -3).astype(int).where(f['shock_z5'].notna())
        g = f.groupby(['시장', 'layer']).ngroup()
        cnt = SZ.notna().groupby(g).transform('sum'); bad = (SZ <= -2).groupby(g).transform('sum')
        share = (bad / cnt.where(cnt >= 3))                              # 같은 층에서 같은 날 −2σ 아래로 빠진 비율
        f['shock_layer_share'] = share.max(axis=1)
        f['shock_layer'] = (f['shock_layer_share'] >= 0.5).astype(int).where(f['shock_layer_share'].notna())
        f['resmom_mpct'] = f.groupby('시장')['resmom'].rank(pct=True)
        # 11/19 의장 B20 큰돈이 모으나: Chaikin Money Flow(20일)·Money Flow Index(14일), 고가·저가·거래량(fetch_px.py)
        try:
            Hh = pd.read_csv(f'{d}/고가2년.csv', encoding='utf-8-sig', index_col=0, parse_dates=True)
            Ll = pd.read_csv(f'{d}/저가2년.csv', encoding='utf-8-sig', index_col=0, parse_dates=True)
            Vv = pd.read_csv(f'{d}/거래량2년.csv', encoding='utf-8-sig', index_col=0, parse_dates=True)
            C_ = P.reindex(index=Hh.index, columns=Hh.columns)
            mfm = ((C_ - Ll) - (Hh - C_)) / (Hh - Ll).replace(0, np.nan)          # 종가가 그날 고가 쪽이면 +1, 저가 쪽이면 −1
            f['cmf20'] = f['ticker'].map((mfm * Vv).tail(20).sum() / Vv.tail(20).sum().replace(0, np.nan))
            tp = (Hh + Ll + C_) / 3; rmf = tp * Vv; up = tp.diff() > 0; dn = tp.diff() < 0
            def mfi(k):
                pos = rmf.where(up).iloc[-14 - k:len(rmf) - k].sum(); neg = rmf.where(dn).iloc[-14 - k:len(rmf) - k].sum()
                return 100 - 100 / (1 + pos / neg.replace(0, np.nan))
            f['mfi14'] = f['ticker'].map(mfi(0)); f['mfi14_5'] = f['ticker'].map(mfi(5))
        except FileNotFoundError:
            f['cmf20'] = np.nan; f['mfi14'] = np.nan; f['mfi14_5'] = np.nan
        # Bali·Cakici·Whitelaw(2011) MAX: 최근 21일 최대 일간 수익이 큰 종목(복권형)은 이후 수익이 낮음
        f['max21'] = f['ticker'].map(r.tail(21).max() * 100)
        f['max21_mpct'] = f.groupby('시장')['max21'].rank(pct=True)
    # 블룸버그 12개월 선행 EPS(톰스뉴스 표, 미국 상위 30): 1주·YTD 변화, 선행 PER
    BB = _r(d, '블룸버그EPS')
    if len(BB):
        bb = BB.rename(columns={'1주등락': 'bb_ret1w', 'YTD등락': 'bb_ytd', '1주fwdEPS': 'bb_eps1w', 'YTDfwdEPS': 'bb_epsytd', 'fwdPER': 'bb_fper'})
        k2 = f['ticker'].astype(str).str.upper()
        for c in ['bb_ret1w', 'bb_ytd', 'bb_eps1w', 'bb_epsytd', 'bb_fper']:
            f[c] = k2.map(dict(zip(bb['ticker'], bb[c])))
    # 11/19 B20: 공매도 잔고(미국, fetch_short.py) — Boehmer·Jones·Zhang(2008) 공매도 많은 종목은 이후 수익 낮음
    SH = _r(d, '공매도')
    if len(SH):
        k2 = f['ticker'].astype(str)
        f['short_pf'] = k2.map(dict(zip(SH['ticker'], _num(SH['유통대비(%)']))))
        f['short_chg'] = k2.map(dict(zip(SH['ticker'], _num(SH['전월대비(%)']))))
        f['short_dtc'] = k2.map(dict(zip(SH['ticker'], _num(SH['커버일수']))))
    else:
        f['short_pf'] = np.nan; f['short_chg'] = np.nan; f['short_dtc'] = np.nan
    # 이익률 조건: 금융인데 최신 분기 이익률을 비교할 수 없으면 해당 없음(통과)
    f['opm_ok'] = ((f['opm_yoy'] >= 0) | ((f['kind'] == '순이익') & f['opm_yoy'].isna())).astype(int).where(f['opm_yoy'].notna() | (f['kind'] == '순이익'))
    # 추천 조건용: 돈이 들어온다 / 돌아섰다 (자료 있는 것만으로 판단, 하나도 없으면 NaN)
    def money(r):
        if r['구분'] != '개별주':
            v = r.get('etf_flow5'); return np.nan if pd.isna(v) else int(v > 0)
        if r['시장'] == '한국':
            if pd.isna(r.get('f5')): return np.nan
            return int(r['f5'] > 0 and ((r.get('f20') or 0) > 0 or (r.get('fstreak') or 0) >= 3))
        v = r.get('sec_flow5'); return np.nan if pd.isna(v) else int(v > 0)
    f['money_ok'] = f.apply(money, axis=1)
    t2 = (f['osc_w'] > f['osc_w1']) & (f['osc_w1'] > f['osc_w2'])
    f['turn_ok'] = (t2 | (f.get('above50', pd.Series(0, index=f.index)) == 1)).astype(int)
    # 한 분기 꺾임 봐주기: 앞 분기 이익 전년비 증가 + 추정치 상향(자료 없으면 0)
    f['earn_relief'] = ((f.get('prev_op_yoy', np.nan) > 0) & (f['est30'] > 0) & (f['up30'] >= f['dn30'])).astype(int) if 'est30' in f else 0
    # 동료 비교: 같은 시장·같은 층 개별주 안에서 순위(1에 가까울수록 좋음)
    stk = f['구분'] == '개별주'
    g = [f['시장'], f['layer']]
    for k, asc in (('est30', True), ('fper', False)):
        if k in f:
            v = f[k].where(stk & (f[k] > 0 if k == 'fper' else True))
            f[f'peer_{k}'] = v.groupby(g).rank(pct=True, ascending=asc)
    # 사건 역풍
    U = _r(d, '유니버스')
    sect = dict(zip(U.get('번호', []), U.get('섹터/테마', pd.Series(dtype=str)).astype(str))) if len(U) else {}
    NW = _r(d, '뉴스')
    heads = ' '.join(' '.join(map(str, r)) for r in NW.itertuples(index=False)).lower() if len(NW) else ''
    hits = []
    for no in f['번호']:
        s = sect.get(no, '')
        hits.append(','.join(sorted({w for k2, ws in EVENT.items() if k2 in s for w in ws if w.lower() in heads})))
    # 11/19 의장 B20 '제2의 젠슨 황': 뉴스 감성(FinBERT 영어·KR-FinBERT 한국어, 07시 b09_newssent.py). 업종 낱말·사건상태표는 판정에서 뺌
    NS = _r(d, '뉴스감성')
    f['news_neg'] = 0.0; f['news_title'] = ''
    if len(NS):
        NS['부정'] = _num(NS['부정']); low = NS['제목'].fillna('').astype(str).str.lower()
        for i, nm in zip(f.index, f['종목'].astype(str)):
            m = (NS['종목'].astype(str) == nm) | (low.str.contains(nm.lower(), regex=False) if len(nm) >= 4 else False)
            if m.any():
                j = NS.loc[m, '부정'].idxmax()
                f.at[i, 'news_neg'] = NS.at[j, '부정']; f.at[i, 'news_title'] = str(NS.at[j, '제목'])[:80]
    f['news_strong'] = (f['news_neg'] >= 0.9).astype(int)   # 강한 부정 뉴스(부정 확률 0.9 이상)
    # 제2의 젠슨 황 = 강한 부정 뉴스 + 그 종목 −2σ 급락, 또는 업종 동반 급락(자료 없으면 '증거 없음' = 0)
    sz = f['shock_z5'] if 'shock_z5' in f else pd.Series(np.nan, index=f.index)
    sl = f['shock_layer'] if 'shock_layer' in f else pd.Series(np.nan, index=f.index)
    f['jensen'] = (((f['news_strong'] == 1) & (sz <= -2)) | (sl == 1)).astype(int)
    # 사건 상태표(손 작성): 11/19부터 판정에 안 쓰고 표시만
    ST = _r(d, '사건상태')
    if len(ST):
        for i, no in enumerate(f['번호']):
            s2 = sect.get(no, '')
            on = [r['사건'] + '(' + r['상태'] + ')' for _, r in ST.iterrows() if str(r['업종']) in s2]
            if on:
                hits[i] = ','.join([x for x in [hits[i]] + on if x])
    f['event_words'] = hits
    # 변수 달력(앞으로 예정된 큰 사건): 거르지 않고 종목마다 '변수'로 표시
    CAL = _r(d, '변수달력')
    var = []
    for no in f['번호']:
        s2 = sect.get(no, '')
        var.append(' / '.join(f"{r['시기']} {r['사건']} → {r['방향']}" for _, r in CAL.iterrows()
                              if any(w and w in s2 for w in str(r['영향 업종 낱말']).split('|'))) if len(CAL) else '')
    f['변수'] = var
    # 대형 이벤트 앞 수급 경계(11/17 의장): 날짜가 확인된 사건이 7일 안이고 '영향 층'에 들면 event_near = 1
    near = [0] * len(f)
    if len(CAL) and '날짜' in CAL and '영향 층' in CAL:
        today = pd.Timestamp.now(tz='Asia/Seoul').normalize().tz_localize(None)
        for _, r in CAL.iterrows():
            dt = pd.to_datetime(r['날짜'], errors='coerce')
            if pd.isna(dt) or not (0 <= (dt - today).days <= 7):
                continue
            lays = str(r['영향 층']).split('|')
            near = [1 if (n or lay in lays) else 0 for n, lay in zip(near, f['layer'].astype(str))]
    f['event_near'] = near
    f['event_hit'] = f['event_words'] != ''
    if 'shock_z5' in f:   # 가격 충격 설명(매도 신호 칸에 붙음)
        lab = np.where(f['shock_layer'] == 1, '업종 동반 급락', '')
        lab = [', '.join(x for x in (a, f'잔차 {z:.1f}σ' if z <= -3 else '') if x) for a, z in zip(lab, f['shock_z5'].fillna(0))]
        f['event_words'] = [', '.join(x for x in (w, l) if x) for w, l in zip(f['event_words'], lab)]
    f['event_words'] = [', '.join(x for x in (w, f'부정 뉴스 {p:.2f} "{t}"' if p >= 0.9 else '') if x) for w, p, t in zip(f['event_words'], f['news_neg'], f['news_title'])]
    f['sector'] = f['번호'].map(sect)
    return f


def market(d):
    m = {}
    R = _r(d, '리스크')
    if len(R):
        g = dict(zip(R['항목'], _num(R['값'])))
        m.update(VIX=g.get('VIX'), MOVE=g.get('MOVE'), VIX_VIX3M=g.get('VIX − VIX3M'), HY=g.get('하이일드 스프레드'),
                 STLFSI=g.get('세인트루이스'), SOFR_IORB=g.get('SOFR−IORB'), T10Y2Y=g.get('10년−2년'))
    C = _r(d, '매크로체크리스트')
    if len(C):
        g = dict(zip(C['항목'], _num(C['값'])))
        m.update(US10Y=g.get('미국 10년물'), REAL10Y=g.get('실질금리(10년 TIPS)'))
        m['REAL10Y_1W'] = dict(zip(C['항목'], _num(C['1주 전']))).get('실질금리(10년 TIPS)')
    G = _r(d, '공포탐욕')
    if len(G):
        m['FG'] = float(_num(G.loc[G['구분'] == '종합', '점수']).iloc[0])
    P = _r(d, '수급포지셔닝')
    if len(P):
        g = dict(zip(P['항목'], _num(P['값'])))
        m.update(CTA=g.get('CTA σ(근사)'), VOLT=g.get('변동성타기팅 노출(배)'), VXN_PCT=g.get('VXN 1년 백분위(%)'),
                 VIX_PCT=g.get('VIX 1년 백분위(%)'), EWNDX_PCT=g.get('비율 1년 백분위(%)'))
    A = _r(d, 'ETF자금')
    if len(A):
        safe = A[(A['시장'] == '한국') & A['이름'].astype(str).str.contains('200|커버드콜|미국S&P500|미국나스닥100')]
        m['KR_SAFE_FLOW5'] = float(_num(safe['유입_5일']).sum())
    V2 = _r(d, '지수밸류')
    if len(V2):
        v = V2.iloc[-1]; m['SPX_FPER'] = float(v['선행PER'])
        if len(V2) >= 6: m['SPX_EPS_UP'] = float(V2['선행EPS'].iloc[-1] - V2['선행EPS'].iloc[-6])
    P = _px(d)
    if len(P):   # 분산 깨짐: 종목 간 평균 상관(20일) − 1년 평균
        r = np.log(P).diff().dropna(how='all')
        def mc(x):
            c = x.corr().values; n = len(c)
            return (np.nansum(c) - n) / (n * n - n)
        m['CORR20'] = float(mc(r.tail(20))); m['CORR1Y'] = float(mc(r.tail(252)))
        m['CORR_JUMP'] = m['CORR20'] - m['CORR1Y']
        # 순환 국면(11/17 의장 역추적): AI 묶음(S1·S2·S3) ÷ 비AI 방어 묶음(S5 금융·S6 방어·내수) 비율
        try:
            U = pd.read_csv(f'{d}/유니버스.csv', encoding='utf-8-sig').drop_duplicates('yfinance 티커')
            lay = dict(zip(U['yfinance 티커'], U['층']))
            rr = P.pct_change(fill_method=None)
            ai = [t for t in P if lay.get(t) in ('S1', 'S2', 'S3')]; df = [t for t in P if lay.get(t) in ('S5', 'S6')]
            A = (1 + rr[ai].mean(axis=1).fillna(0)).cumprod(); N = (1 + rr[df].mean(axis=1).fillna(0)).cumprod(); Rt = A / N
            m['ROT_GAP50'] = float(Rt.iloc[-1] / Rt.tail(50).mean() * 100 - 100)
            m['ROT_CH20'] = float(Rt.iloc[-1] / Rt.iloc[-21] * 100 - 100)
            m['ROT_DEF'] = int(m['ROT_GAP50'] < 0 and m['ROT_CH20'] < 0)
        except Exception:
            pass
    try:   # BLOCK20 아침보고 [국면] 줄
        t = open(f'{d}/아침보고.txt', encoding='utf-8').read()
        for k, c in (('미국', 'US_BEAR'), ('한국', 'KR_BEAR')):
            g = re.search(k + r' B01 (상승|중립|하락) (\d+)%', t)
            if g: m[c] = int(g.group(2)) / 100 if g.group(1) == '하락' else 0.0
    except FileNotFoundError:
        pass
    try:   # 코스피 50일 이격(의장 기준: 125 과열주의, 130 과열)
        ix = pd.read_csv(f'{d}/지수2년.csv', index_col=0)['^KS11'].dropna()
        m['KS_GAP50'] = float(ix.iloc[-1] / ix.iloc[-50:].mean() * 100)
    except Exception:
        pass
    # B10 세계는 평화로운가: 지정학 위험 지수(GPR, Caldara·Iacoviello) 7일 평균의 10년 백분위(07시 수집 b09_gpr.py)
    GP = _r(d, '지정학위험')
    if len(GP) and 'GPR_PCT' in GP:
        m['GPR_PCT'] = _num(GP['GPR_PCT']).dropna().iloc[-1] if _num(GP['GPR_PCT']).notna().any() else None
    return m
