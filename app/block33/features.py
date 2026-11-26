"""자료 어댑터: 07시 파일 + 퀀트센터 파일 → 종목 한 줄(features) + 시장 한 줄(market).
새 자료를 붙이려면 여기에 어댑터 함수 하나를 더한다. 칸 이름은 blocks.yaml 식에서 쓰는 이름."""
import re
import numpy as np
import pandas as pd
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), 'collect', 'data'))
import px_store as PS  # noqa: E402  11/26 의장: 가격·지수는 10년치 데이터베이스 하나에서만 읽음

EVENT = {'방산': ['종전', '휴전', '평화협상', 'ceasefire', 'peace deal', 'truce'],
         '우주': ['종전', '휴전', 'ceasefire'],
         '조선': ['관세', '선박 수수료', 'port fee'],
         '자동차': ['관세', 'tariff'],
         '원전': ['원전 취소', '계약 종료'],
         '화장품': ['관세', 'tariff']}


MISSING = {}   # 11/21 의장 '병렬식': 빠지거나 깨진 자료 {이름: 이유} — 원고는 그 칸만 비우고 계속 만든다


# 11/25 의장: 기준층(S0) 중 블록 판정에 넣는 지수 ETF(QQQM U0-2·U0-2, SPYM U0-1·U0-1). 층 이름 'S0판정' → 'S0' 예외(기준층 표시·매도 제외·성적표 제외)에 걸리지 않음
S0_JUDGE = {'U0-1', 'U0-2'}   # SPYM·QQQM

def report7(d, days=7):
    """최근 7일 증권사 보고서: 같은 증권사 직전 보고서보다 목표가를 올림(rep7_up)·내림(rep7_dn), 보고서 수(rep7_n), 마지막 날(rep7_last)."""
    T = PS.table(d, '투자의견', dtype={'코드': str})
    if T.empty:
        return pd.DataFrame(columns=['코드', 'rep7_up', 'rep7_dn', 'rep7_n', 'rep7_last'])
    T['날짜'] = pd.to_datetime(T['날짜']); T = T.sort_values(['코드', '증권사', '날짜'])
    T['prev'] = T.groupby(['코드', '증권사'])['목표가'].shift()
    cut = T['날짜'].max() - pd.Timedelta(days=days)
    R = T[T['날짜'] > cut]
    g = R.groupby('코드')
    return pd.DataFrame({'rep7_up': g.apply(lambda x: int((x['목표가'] > x['prev']).sum())),
                         'rep7_dn': g.apply(lambda x: int((x['목표가'] < x['prev']).sum())),
                         'rep7_n': g.size(), 'rep7_last': g['날짜'].max().dt.strftime('%m/%d')}).reset_index()


def _fail(name, e):
    if name not in MISSING:
        MISSING[name] = f'{type(e).__name__}: {str(e)[:80]}'
        print(f'[빠진 자료] {name} → 그 칸만 비우고 계속: {MISSING[name]}')


def _r(d, name):
    """자료 하나 읽기. 없거나 비었거나 깨졌으면 빈 표(그 자료를 쓰는 칸만 '자료 없음')."""
    try:
        return pd.read_csv(f'{d}/{name}.csv', encoding='utf-8-sig')
    except FileNotFoundError:
        return pd.DataFrame()
    except Exception as e:   # noqa: BLE001  빈 파일(EmptyDataError)·깨진 파일
        _fail(name, e)
        return pd.DataFrame()


def _num(s):
    return pd.to_numeric(s, errors='coerce')


def _streak(x):
    m = re.match(r'순(매수|매도)\s*(\d+)', str(x))
    return np.nan if not m else (int(m.group(2)) if m.group(1) == '매수' else -int(m.group(2)))


def _px(d):
    try:
        return PS.stocks(d, 'Close', 735)
    except Exception as e:   # noqa: BLE001
        _fail('가격 데이터베이스', e)
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
    # 11/21 의장 "최근 상장한 것은 자료가 없으니 그냥 넘어가": 52주 고점 칸이 빈 종목(상장 1년 안 됨)은 상장 뒤 고점 대비로 채움
    try:
        P_ = _px(d)
        if len(P_) and f['dd52'].isna().any():
            P_ = P_.tail(252)
            dd_ = (P_.ffill().iloc[-1] / P_.max() - 1) * 100
            f['dd52'] = f['dd52'].fillna(f['ticker'].map(dd_.where(P_.notna().sum() >= 20)))
    except Exception as e:   # noqa: BLE001
        _fail('52주 고점 채움', e)
    E = _r(d, '예외검정')
    try:
        if len(E):
            e = pd.DataFrame({'번호': E['번호'], 'layer': E['층'], 'p10': _num(E['10년_하락p']), 'p5': _num(E['5년_하락p']),
                              'p3': _num(E['3년_하락p']), 'res4p': _num(E['잔차4주_하락p']), 'res13p': _num(E['잔차13주_하락p']),
                              'up10_13': _num(E['10년_13주상승p']), 'beta': _num(E['베타(주간2년)']), 'sigma_note': E['예외 정리']})
            f = f.merge(e, on='번호', how='left')
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('예외검정', e)
    if 'layer' not in f:   # 예외검정이 빠지면 층 없이(한 묶음) 계산
        f['layer'] = ''
    # 11/25 22:29 의장 "QQQM, SPYM 추천후보에 넣으라고 말했을 텐데. 블록 판정에 넣으라고": 기준층(S0)이지만 블록 판정·추천 후보·블록점수이력에 넣음
    f.loc[f['번호'].isin(S0_JUDGE) & f['layer'].eq('S0'), 'layer'] = 'S0판정'
    F = _r(d, '국내수급')
    try:
        if len(F):
            q = pd.DataFrame({'번호': F['번호'], 'f5': _num(F['외국인 5일(억원)']), 'f20': _num(F['외국인 20일(억원)']),
                              'inst5': _num(F['기관 5일(억원)']), 'ind5': _num(F['개인 5일(억원)']), 'fstreak': F['외국인 연속'].map(_streak),
                              'dip_buy': F['표시'].astype(str).str.contains('주가↓·외국인↑').astype(int)})
            for c, k in (('외국인 5일 z', 'fz5'), ('기관 5일 z', 'iz5')):   # 11/19 B20 수급 z점수(b09_kflow, 자기 30일 대비)
                q[k] = _num(F[c]) if c in F else np.nan
            f = f.merge(q, on='번호', how='left')
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('국내수급', e)
    V = _r(d, '밸류에이션')
    try:
        if len(V) and '시가총액(억원)' in V:
            f = f.merge(pd.DataFrame({'번호': V['번호'], 'mcap_kr': _num(V['시가총액(억원)'])}), on='번호', how='left')
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('밸류에이션', e)
    try:
        if len(V):
            f = f.merge(pd.DataFrame({'번호': V['번호'], 'pbr': _num(V['PBR']), 'fper': _num(V['선행 PER(야후)']),
                                      'per_kis': _num(V['PER'])}), on='번호', how='left')
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('밸류에이션', e)
    try:
        for name, per, roe in (('DART', 'PER TTM(주가÷EPS)', 'ROE TTM(%)'), ('SEC', 'PER TTM(주가÷EPS)', 'ROE TTM(%)')):
            X = _r(d, name)
            if len(X):
                x = pd.DataFrame({'번호': X['번호'], f'per_{name}': _num(X[per]), f'roe_{name}': _num(X[roe])})
                f = f.merge(x, on='번호', how='left')
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('for name, per, roe in (("DART", "PER TTM', e)
    nan = pd.Series(np.nan, index=f.index)
    # 자기역사 PER 3년·52주 밴드(11/16 의장: 3년치만) — 11/26 10년치 데이터베이스(종가 ÷ EPS 칸, px_store.per_band)
    try:
        f = f.merge(PS.per_band(d), on='ticker', how='left')
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('PER 밴드(데이터베이스)', e)
    for k in ('per_now', 'per_med3', 'per_pct3', 'per_med1', 'per_pct1'):
        if k not in f:
            f[k] = np.nan
    try:   # 11/26 PER은 데이터베이스(종가 ÷ EPS)가 먼저 — 과거 판정(hist_fund)과 같은 값. 없으면 DART·SEC·한투 표
        f['per_ttm'] = f['per_now'].combine_first(f.get('per_DART', nan)).combine_first(f.get('per_SEC', nan)).combine_first(f.get('per_kis', nan))
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["per_ttm"] = f.get("per_DART", nan).co', e)
    try:
        f['roe'] = f.get('roe_DART', nan).combine_first(f.get('roe_SEC', nan))
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["roe"] = f.get("roe_DART", nan).combin', e)
    # 층 안 순위(낮을수록 쌈)
    try:
        for k in ('per_ttm', 'pbr'):
            v = f[k].where(f[k] > 0)
            f[f'{k.split("_")[0]}_rank'] = v.groupby(f['layer']).rank(pct=True)
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('for k in ("per_ttm", "pbr"):', e)
    # 분기 실적·추정치(야후)
    Q = _r(d, '분기실적')
    try:
        if len(Q):
            q = Q.rename(columns={'실적지표': 'kind', '이익_전년비': 'op_yoy', 'OPM_전년비': 'opm_yoy', 'OPM_2연속': 'opm2',
                                  '매출_전년비': 'rev_yoy', '추정_30일': 'est30', '추정_90일': 'est90', '상향30': 'up30',
                                  '하향30': 'dn30', '최근분기': 'last_q', 'OPM': 'opm',
                                  '추정_7일': 'est7', '상향7': 'up7', '하향7': 'dn7'})
            f = f.merge(q[[c for c in ['번호', 'kind', 'op_yoy', 'opm_yoy', 'opm2', 'rev_yoy', 'est30', 'est90', 'up30', 'dn30',
                                       'last_q', 'opm', 'est7', 'up7', 'dn7'] if c in q]], on='번호', how='left')
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('분기실적', e)
    try:   # 11/26 의장 "하나로 통일해": 미국 추정치는 데이터베이스 칸 '이익추정'의 마지막 날 값(매일 아침 받음)이 분기실적보다 우선
        E = PS.table(d, '이익추정', dtype=str)
        if len(E):
            E = E[E['날짜'] == E['날짜'].max()].rename(columns={'추정_7일': 'est7', '추정_30일': 'est30', '추정_90일': 'est90', '상향7': 'up7',
                                                              '하향7': 'dn7', '상향30': 'up30', '하향30': 'dn30'})
            ks = [c for c in ('est7', 'est30', 'est90', 'up7', 'dn7', 'up30', 'dn30') if c in E]
            E[ks] = E[ks].apply(pd.to_numeric, errors='coerce')
            f = f.drop(columns=[c for c in ks if c in f]).merge(E[['번호'] + ks], on='번호', how='left')
    except Exception as e:   # noqa: BLE001
        _fail('이익추정 칸', e)
    try:   # 11/26 의장 "최근 일주일 보고서만 참고해": 한국 종목은 한투 증권사 투자의견 칸(가격10년_투자의견)의 최근 7일 보고서
        r7 = report7(d).rename(columns={'코드': '_code'})
        f['_code'] = f['ticker'].astype(str).str.extract(r'^(\d{6})\.K[SQ]$')[0]
        f = f.merge(r7, on='_code', how='left').drop(columns='_code')
    except Exception as e:   # noqa: BLE001
        _fail('투자의견 7일', e)
    # ETF 자체 자금 유출입(07시 ETF자금, 억원·백만달러)
    A = _r(d, 'ETF자금')
    try:
        if len(A):
            f = f.merge(pd.DataFrame({'번호': A['번호'], 'etf_flow5': _num(A['유입_5일']), 'etf_flow20': _num(A['유입_20일'])}), on='번호', how='left')
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('ETF자금', e)
    # 분기 원자료로 다시 계산: 한국은 DART 3분기 잠정실적을 최신 분기로 붙임(야후에 아직 없음)
    QR = _r(d, '분기원자료')
    try:
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
                fin = g.loc[g['출처'].isin(['야후', '한투', 'DART']), '영업이익'].isna().all()   # 11/21 한국은 한투 분기 손익
                g['x'] = g['순이익'] if fin else g['영업이익']
                g = g[~((g['출처'] == 'DART 잠정') & g['x'].isna())]   # 금융 잠정에 이익 칸 없으면 버림
                # 11/21 의장 "부족한 자료는 다 채우고": 야후가 아직 발표 안 한 분기를 빈 칸으로 붙여 둠(엔비디아·타깃 10/31) → 매출·이익 모두 빈 분기는 버림
                g = g[g[['매출', 'x']].notna().any(axis=1)]
                if not len(g): continue
                if fin:   # 금융: DART 잠정 매출(영업수익 총액)은 야후 매출과 정의가 달라 이익률 비교 안 함
                    g.loc[g['출처'] == 'DART 잠정', '매출'] = np.nan
                g['m'] = g['x'] / g['매출'] * 100
                def yoy(i, col):
                    cur = g.iloc[i]; prev = g[(g['분기'] - cur['분기'] + pd.Timedelta(days=365)).abs() <= pd.Timedelta(days=20)]
                    if not len(prev) or pd.isna(cur[col]) or pd.isna(prev[col].iloc[0]): return np.nan
                    pv = prev[col].iloc[0]
                    if col == 'm': return cur[col] - pv
                    return (cur[col] / pv - 1) * 100 if pv > 0 else (999 if cur[col] > 0 else -999)
                # 11/21: 1년 전 같은 분기가 야후에 비어 있으면(버크셔·신한 2025-09) 직전 분기 전년비로 대신
                fb = lambda col: yoy(-1, col) if not pd.isna(yoy(-1, col)) else (yoy(-2, col) if len(g) > 1 else np.nan)
                r = dict(번호=no, kind='순이익' if fin else '영업이익', last_q=str(g['분기'].iloc[-1].date()), q_src=g['출처'].iloc[-1],
                         op_yoy=fb('x'), opm_yoy=fb('m'), rev_yoy=fb('매출'), opm=g['m'].iloc[-1],
                         prev_op_yoy=yoy(-2, 'x') if len(g) > 1 else np.nan,
                         opm2=int(g['m'].iloc[-1] > g['m'].iloc[-2] > g['m'].iloc[-3]) if len(g) >= 3 and g['m'].tail(3).notna().all() else np.nan)
                rows.append(r)
            RQ = pd.DataFrame(rows)
            f = f.drop(columns=[c for c in ['kind', 'op_yoy', 'opm_yoy', 'opm2', 'rev_yoy', 'last_q', 'opm'] if c in f]).merge(RQ, on='번호', how='left')
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('분기원자료', e)
    # 장기 펀드 13F(fetch_13f.py): 지난 분기 늘렸나·줄였나(미국 상장 주식만)
    LT = _r(d, '장기펀드13F')
    try:
        if len(LT):
            f = f.merge(LT[['ticker', 'lt_funds', 'lt_up', 'lt_dn', 'lt_net', 'lt_net_prev', '분기']].rename(columns={'분기': 'lt_q'}),
                        on='ticker', how='left')
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('장기펀드13F', e)
    C = _r(d, '1달조합')
    try:
        if len(C):
            f = f.merge(pd.DataFrame({'번호': C['번호'], 'combo1m': (C['판정'] == '충족').astype(int)}), on='번호', how='left')
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('1달조합', e)
    # 업종 ETF(섹터 60주·자금): 섹터 ETF 자기 값(11/26 의장 "상위종목 하지마. ETF만" → 상위 10 연결 없음)
    Y = _r(d, '시타델')
    try:
        if len(Y):
            # 11/26 의장 "이건 또 왜 비었어"(B18 전부 자료 없음): 아침 수집엔 시타델에 '자금5일' 칸이 없어 KeyError → 60주 이격까지 통째로 비었음.
            # → 있는 칸만 쓰고, 없는 칸은 비움(60주 이격은 살림). 구분 칸이 없으면 모두 ETF 줄.
            Y = Y.copy()
            Y['ETF'] = Y['ETF'].astype(str)
            if '구분' not in Y:
                Y['구분'] = 'ETF'
            if '티커' not in Y:
                Y['티커'] = Y['ETF']
            etf = Y[Y['구분'] == 'ETF'].drop_duplicates('ETF').set_index('ETF')
            col = lambda k: _num(etf[k]) if k in etf else pd.Series(np.nan, index=etf.index)
            h = Y[Y['구분'].isin(['종목', 'ETF'])][['ETF', '티커']].copy()
            h['티커'] = h['티커'].astype(str).str.upper()
            h['sec_gap60'] = h['ETF'].map(col('60주 이격'))
            h['sec_flow5'] = h['ETF'].map(col('자금5일'))
            h = h.groupby('티커')[['sec_gap60', 'sec_flow5']].first()
            key = f['ticker'].astype(str).str.upper().str.replace(r'\.(KS|KQ)$', '', regex=True)
            f['sec_gap60'] = key.map(h['sec_gap60'])
            f['sec_flow5'] = key.map(h['sec_flow5'])
            # 11/19 완성도: 어떤 업종 ETF 상위 10에도 없는 개별주는 같은 시장·층 종목들이 받은 업종 ETF 값(중앙값)으로 채움
            for c in ('sec_gap60', 'sec_flow5'):
                fill = f.groupby(['시장', 'layer'])[c].transform('median')
                f[c] = f[c].where(f[c].notna() | (f['구분'] != '개별주'), fill)
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('시타델', e)
    # 11/26 의장 "이건 또 왜 비었어"(B20 개별주 전부 자료 없음): B20 '섹터 ETF로 본 수급'은 ETF 자기 자금만 있어 개별주는 늘 비었음
    # → 개별주는 같은 시장·같은 층 ETF들의 5·20일 자금 유입(중앙값) = 그 종목 업종 ETF로 본 수급
    try:
        for c in ('etf_flow5', 'etf_flow20'):
            if c in f:
                src = f[c].where(f['구분'] != '개별주')
                fill = src.groupby([f['시장'], f['layer']]).transform('median')
                f[c] = f[c].where(f['구분'] != '개별주', fill)
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('시타델', e)
    # 재무 건전성·연매출(야후 info, 200종목)
    H = _r(d, '재무건전성')
    try:
        if len(H):
            h = pd.DataFrame({'번호': H['번호'], 'debt': _num(H['총부채']), 'ebitda': _num(H['EBITDA']),
                              'fcf_y': _num(H['FCF']), 'mcap': _num(H['시총'])})
            f = f.merge(h, on='번호', how='left')
            f['debt_ebitda'] = np.where(f['ebitda'] > 0, f['debt'] / f['ebitda'], np.where(f['ebitda'].notna(), 99, np.nan))
            f['ev_ebitda'] = (f['mcap'] + f['debt'].fillna(0)) / f['ebitda'].where(f['ebitda'] > 0)   # 11/24 B15 동료 EV/EBITDA
            for k in ('fcf', 'fcf_yield'):
                if k not in f: f[k] = np.nan
            f['fcf'] = f['fcf'].combine_first(f['fcf_y'])
            f['fcf_yield'] = f['fcf_yield'].combine_first(f['fcf_y'] / f['mcap'] * 100)
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('재무건전성', e)
    FZ = _r(d, 'FZ점수')   # 직접 계산(야후 연간 재무제표, 아침 8시 수집)
    try:
        if len(FZ):
            fz = pd.DataFrame({'번호': FZ['번호'], 'f_y': _num(FZ['F점수']), 'z_y': _num(FZ['Z점수'])})
            f = f.merge(fz, on='번호', how='left')
            for k, y in (('fscore', 'f_y'), ('z', 'z_y')):
                f[k] = (f[k] if k in f else pd.Series(np.nan, index=f.index)).combine_first(f[y])
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('FZ점수', e)
    RV = _r(d, '연매출')
    try:
        if len(RV):
            f = f.merge(pd.DataFrame({'번호': RV['번호'], 'rev_krw': _num(RV['연매출(원)'])}), on='번호', how='left')
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('연매출', e)
    # 10년치 데이터베이스 최근 2년: 종목 위험(변동성·꼬리)
    P = _px(d)
    try:
        if len(P):
            r = np.log(P).diff()
            vol = r.tail(60).std() * np.sqrt(252) * 100
            es = r.tail(252).apply(lambda x: x.dropna().sort_values().head(max(1, int(len(x.dropna()) * 0.05))).mean() * 100)
            f['vol60'] = f['ticker'].map(vol)
            f['es5'] = f['ticker'].map(es)
            # 돈의 방향: 시장(코스피·코스닥·S&P500) 대비 5·20일 상대수익, 같은 층 대비, 50일선
            I = PS.index(d, 735)
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
            f['px_ma200'] = f['ticker'].map(last) / f['ma200']   # 11/20: 엘피스 '200일선×0.95 위' 조건(현재가 ÷ 200일선)
            # 옛 가짜 바닥(제이미 B29, 11/17): 200일선 95% 위 + 데드크로스 속 5일 +5% 반등 아님. 11/19 의장: 근거 없음 → 기록만
            f['survive_ma200'] = ((f['ticker'].map(last) >= f['ma200'] * 0.95) & ~((f['ma50'] < f['ma200']) & (f['ret5'] >= 5))).astype(int).where(f['ma200'].notna())
            # 11/19 의장 "금융공학 공식": Carver EWMAC 추세 예측치, Frog-in-the-pan, 잔차 모멘텀, MAX 효과
            def ewmac(x, fa, sl, k):   # Carver(Systematic Trading): (빠른 EWMA − 느린 EWMA) ÷ 가격 변동성(36일 EW) × 예측 눈금, ±20
                x = x.dropna()
                if len(x) < sl: return np.nan
                sd = x.diff().ewm(span=36).std().iloc[-1]
                return float(np.clip((x.ewm(span=fa).mean().iloc[-1] - x.ewm(span=sl).mean().iloc[-1]) / sd * k, -20, 20)) if sd > 0 else np.nan
            f['ewmac16'] = f['ticker'].map(P.apply(lambda x: ewmac(x, 16, 64, 3.75)))
            f['ewmac32'] = f['ticker'].map(P.apply(lambda x: ewmac(x, 32, 128, 2.65)))
            f['ewmac'] = (f['ewmac16'] + f['ewmac32']) / 2
            # 11/19 의장 가짜 바닥 → 금융공학 공식 두 개(둘 중 하나면 '가짜 바닥 아님')
            # ① Lo·MacKinlay(1988) 분산비 VR(5) = 5일 수익률 분산 ÷ (5 × 1일 수익률 분산), 최근 120일. 1 미만 = 되돌림(평균 회귀), 1 초과 = 한 방향 지속
            def vr(x, q=5, n=120):
                y = np.log(x.dropna()).diff().dropna().tail(n)
                if len(y) < n: return np.nan
                v1 = y.var(); vq = y.rolling(q).sum().dropna().var()
                return float(vq / (q * v1)) if v1 > 0 else np.nan
            f['vr5'] = f['ticker'].map(P.apply(vr))
            # ② Carver EWMAC 16·64 예측치가 5일 전보다 오름(하락 힘이 약해짐)
            f['ewmac16_5'] = f['ticker'].map(P.apply(lambda x: ewmac(x.dropna().iloc[:-5], 16, 64, 3.75)))
            f['ewmac16_up'] = (f['ewmac16'] > f['ewmac16_5']).astype(int).where(f['ewmac16'].notna() & f['ewmac16_5'].notna())
            f['survive'] = ((f['vr5'] < 1) | (f['ewmac16_up'] == 1)).astype(int).where(f['vr5'].notna() | f['ewmac16_up'].notna())
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
            # 11/19 의장 B20 큰돈이 모으나: Chaikin Money Flow(20일)·Money Flow Index(14일), 고가·저가·거래량(10년치 데이터베이스)
            try:
                Hh = PS.stocks(d, 'High', 735)
                Ll = PS.stocks(d, 'Low', 735)
                Vv = PS.stocks(d, 'Volume', 735)
                C_ = P.reindex(index=Hh.index, columns=Hh.columns)
                mfm = ((C_ - Ll) - (Hh - C_)) / (Hh - Ll).replace(0, np.nan)          # 종가가 그날 고가 쪽이면 +1, 저가 쪽이면 −1
                f['cmf20'] = f['ticker'].map((mfm * Vv).tail(20).sum() / Vv.tail(20).sum().replace(0, np.nan))
                tp = (Hh + Ll + C_) / 3; rmf = tp * Vv; up = tp.diff() > 0; dn = tp.diff() < 0
                def mfi(k):
                    pos = rmf.where(up).iloc[-14 - k:len(rmf) - k].sum(); neg = rmf.where(dn).iloc[-14 - k:len(rmf) - k].sum()
                    return 100 - 100 / (1 + pos / neg.replace(0, np.nan))
                f['mfi14'] = f['ticker'].map(mfi(0)); f['mfi14_5'] = f['ticker'].map(mfi(5))
                # 11/20 의장 3-11 거래량: OBV(Granville 1963) 20일 기울기, 상대 거래량(20일 평균 대비) 하락일 투매, 고거래량 프리미엄(Gervais·Kaniel·Mingelgrin 2001)
                ret_ = C_.pct_change(fill_method=None)
                obv = (np.sign(ret_).fillna(0) * Vv.fillna(0)).cumsum()
                x = np.arange(20) - 9.5
                f['obv_slope20'] = f['ticker'].map((obv.tail(20).mul(x, axis=0).sum() / (x ** 2).sum()) / Vv.tail(20).mean().replace(0, np.nan))
                rv = Vv / Vv.rolling(20, min_periods=15).mean().shift(1)
                f['relvol'] = f['ticker'].map(rv.iloc[-1])
                f['capit5'] = f['ticker'].map(((rv >= 2) & (ret_ < 0)).tail(5).any().astype(int).where(rv.tail(5).notna().any()))
                f['hvp'] = f['ticker'].map(Vv.tail(5).mean() / Vv.tail(55).head(50).mean().replace(0, np.nan))
                f['hvp_mpct'] = f.groupby('시장')['hvp'].rank(pct=True)
            except FileNotFoundError:
                f['cmf20'] = np.nan; f['mfi14'] = np.nan; f['mfi14_5'] = np.nan
                f['obv_slope20'] = np.nan; f['relvol'] = np.nan; f['capit5'] = np.nan; f['hvp'] = np.nan; f['hvp_mpct'] = np.nan
            # Bali·Cakici·Whitelaw(2011) MAX: 최근 21일 최대 일간 수익이 큰 종목(복권형)은 이후 수익이 낮음
            f['max21'] = f['ticker'].map(r.tail(21).max() * 100)
            f['max21_mpct'] = f.groupby('시장')['max21'].rank(pct=True)
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('가격 데이터베이스', e)
    # 블룸버그 12개월 선행 EPS(톰스뉴스 표, 미국 상위 30): 1주·YTD 변화, 선행 PER
    BB = _r(d, '블룸버그EPS')
    try:
        if len(BB):
            bb = BB.rename(columns={'1주등락': 'bb_ret1w', 'YTD등락': 'bb_ytd', '1주fwdEPS': 'bb_eps1w', 'YTDfwdEPS': 'bb_epsytd', 'fwdPER': 'bb_fper'})
            k2 = f['ticker'].astype(str).str.upper()
            for c in ['bb_ret1w', 'bb_ytd', 'bb_eps1w', 'bb_epsytd', 'bb_fper']:
                f[c] = k2.map(dict(zip(bb['ticker'], bb[c])))
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('블룸버그EPS', e)
    # 11/19 B20: 공매도 잔고(미국, fetch_short.py) — Boehmer·Jones·Zhang(2008) 공매도 많은 종목은 이후 수익 낮음
    SH = _r(d, '공매도')
    try:
        if len(SH):
            k2 = f['ticker'].astype(str)
            f['short_pf'] = k2.map(dict(zip(SH['ticker'], _num(SH['유통대비(%)']))))
            f['short_chg'] = k2.map(dict(zip(SH['ticker'], _num(SH['전월대비(%)']))))
            f['short_dtc'] = k2.map(dict(zip(SH['ticker'], _num(SH['커버일수']))))
        else:
            f['short_pf'] = np.nan; f['short_chg'] = np.nan; f['short_dtc'] = np.nan
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('공매도', e)
    # 이익률 조건: 금융인데 최신 분기 이익률을 비교할 수 없으면 해당 없음(통과)
    try:
        f['opm_ok'] = ((f['opm_yoy'] >= 0) | ((f['kind'] == '순이익') & f['opm_yoy'].isna())).astype(int).where(f['opm_yoy'].notna() | (f['kind'] == '순이익'))
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["opm_ok"] = ((f["opm_yoy"] >= 0) | ((f', e)
    # 추천 조건용: 돈이 들어온다 / 돌아섰다 (자료 있는 것만으로 판단, 하나도 없으면 NaN)
    def money(r):
        if r['구분'] != '개별주':
            v = r.get('etf_flow5'); return np.nan if pd.isna(v) else int(v > 0)
        if r['시장'] == '한국':
            if pd.isna(r.get('f5')): return np.nan
            return int(r['f5'] > 0 and ((r.get('f20') or 0) > 0 or (r.get('fstreak') or 0) >= 3))
        v = r.get('sec_flow5'); return np.nan if pd.isna(v) else int(v > 0)
    try:
        f['money_ok'] = f.apply(money, axis=1)
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["money_ok"] = f.apply(money, axis=1)', e)
    t2 = (f['osc_w'] > f['osc_w1']) & (f['osc_w1'] > f['osc_w2'])
    try:
        f['turn_ok'] = (t2 | (f.get('above50', pd.Series(0, index=f.index)) == 1)).astype(int)
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["turn_ok"] = (t2 | (f.get("above50", p', e)
    # 한 분기 꺾임 봐주기: 앞 분기 이익 전년비 증가 + 추정치 상향(자료 없으면 0)
    try:
        # 11/24 의장 '애널 추정치 뺌': 한 분기 꺾임 구제(앞 분기 증가 + 추정치 상향)는 추정치를 써서 0으로(과거 이력 earn_ok와 같은 규칙)
        # f['earn_relief'] = ((f.get('prev_op_yoy', np.nan) > 0) & (f['est30'] > 0) & (f['up30'] >= f['dn30'])).astype(int) if 'est30' in f else 0
        f['earn_relief'] = 0
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["earn_relief"] = ((f.get("prev_op_yoy"', e)
    # 11/19 의장: 매출이 늘고 있으면 이익 감소만으로 거르지 않는다(이익률 조건은 거르기에서 뺌). 이익 자료 없으면 비움
    _rv = f['rev_yoy'] if 'rev_yoy' in f else pd.Series(np.nan, index=f.index)
    try:
        f['earn_ok'] = ((f['op_yoy'] > 0) | (_rv > 0) | (f['earn_relief'] == 1)).astype(int).where(f['op_yoy'].notna())
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["earn_ok"] = ((f["op_yoy"] > 0) | (_rv', e)
    # 11/22 의장: 메모리는 사이클 산업이라 B23을 거꾸로 — 이익이 줄 때가 사는 구간, 늘 때는 피한다(목록은 비공개 blocks.yaml 메모리반대)
    try:
        import qc_config as QCC
        _MR = QCC.load_blocks().get('메모리반대', {}) or {}
        _mem = f['번호'].isin(_MR.get('종목', []))
        f['mem_zone'] = ''
        if _mem.any():
            f.loc[_mem, 'earn_ok'] = (f.loc[_mem, 'op_yoy'] < 0).astype(int).where(f.loc[_mem, 'op_yoy'].notna())
            f.loc[_mem & (f['op_yoy'] < 0), 'mem_zone'] = '사는 구간(이익 감소)'
            f.loc[_mem & (f['op_yoy'] > 0), 'mem_zone'] = '피할 구간(이익 증가)'
    except Exception as e:   # noqa: BLE001
        _fail('메모리반대(B23 거꾸로)', e)
    # 동료 비교: 같은 시장·같은 층 개별주 안에서 순위(1에 가까울수록 좋음)
    stk = f['구분'] == '개별주'
    g = [f['시장'], f['layer']]
    try:
        for k, asc in (('est30', True), ('fper', False)):
            if k in f:
                v = f[k].where(stk & (f[k] > 0 if k == 'fper' else True))
                f[f'peer_{k}'] = v.groupby(g).rank(pct=True, ascending=asc)
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('for k, asc in (("est30", True), ("fper",', e)
    # 사건 역풍
    U = _r(d, '유니버스')
    sect = dict(zip(U.get('번호', []), U.get('섹터/테마', pd.Series(dtype=str)).astype(str))) if len(U) else {}
    NW = _r(d, '뉴스')
    heads = ' '.join(' '.join(map(str, r)) for r in NW.itertuples(index=False)).lower() if len(NW) else ''
    hits = []
    try:
        for no in f['번호']:
            s = sect.get(no, '')
            hits.append(','.join(sorted({w for k2, ws in EVENT.items() if k2 in s for w in ws if w.lower() in heads})))
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('for no in f["번호"]:', e)
    # 11/19 의장 B20 '제2의 젠슨 황': 뉴스 감성(FinBERT 영어·KR-FinBERT 한국어, 07시 b09_newssent.py). 업종 낱말·사건상태표는 판정에서 뺌
    NS = _r(d, '뉴스감성')
    try:
        f['news_neg'] = 0.0; f['news_title'] = ''
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["news_neg"] = 0.0; f["news_title"] = "', e)
    try:
        if len(NS):
            NS['부정'] = _num(NS['부정']); low = NS['제목'].fillna('').astype(str).str.lower()
            for i, nm in zip(f.index, f['종목'].astype(str)):
                m = (NS['종목'].astype(str) == nm) | (low.str.contains(nm.lower(), regex=False) if len(nm) >= 4 else False)
                if m.any():
                    j = NS.loc[m, '부정'].idxmax()
                    f.at[i, 'news_neg'] = NS.at[j, '부정']; f.at[i, 'news_title'] = str(NS.at[j, '제목'])[:80]
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('뉴스감성', e)
    try:
        f['news_strong'] = (f['news_neg'] >= 0.9).astype(int)   # 강한 부정 뉴스(부정 확률 0.9 이상)
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["news_strong"] = (f["news_neg"] >= 0.9', e)
    # 제2의 젠슨 황 = 강한 부정 뉴스 + 그 종목 −2σ 급락, 또는 업종 동반 급락(자료 없으면 '증거 없음' = 0)
    sz = f['shock_z5'] if 'shock_z5' in f else pd.Series(np.nan, index=f.index)
    sl = f['shock_layer'] if 'shock_layer' in f else pd.Series(np.nan, index=f.index)
    try:
        f['jensen'] = (((f['news_strong'] == 1) & (sz <= -2)) | (sl == 1)).astype(int)
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["jensen"] = (((f["news_strong"] == 1) ', e)
    # 사건 상태표(손 작성): 11/19부터 판정에 안 쓰고 표시만
    ST = _r(d, '사건상태')
    try:
        if len(ST):
            for i, no in enumerate(f['번호']):
                s2 = sect.get(no, '')
                on = [r['사건'] + '(' + r['상태'] + ')' for _, r in ST.iterrows() if str(r['업종']) in s2]
                if on:
                    hits[i] = ','.join([x for x in [hits[i]] + on if x])
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('사건상태', e)
    try:
        f['event_words'] = hits
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["event_words"] = hits', e)
    # 변수 달력(앞으로 예정된 큰 사건): 거르지 않고 종목마다 '변수'로 표시
    CAL = _r(d, '변수달력')
    var = []
    try:
        for no in f['번호']:
            s2 = sect.get(no, '')
            var.append(' / '.join(f"{r['시기']} {r['사건']} → {r['방향']}" for _, r in CAL.iterrows()
                                  if any(w and w in s2 for w in str(r['영향 업종 낱말']).split('|'))) if len(CAL) else '')
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('for no in f["번호"]:', e)
    try:
        f['변수'] = var
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["변수"] = var', e)
    # 대형 이벤트 앞 수급 경계(11/17 의장): 날짜가 확인된 사건이 7일 안이고 '영향 층'에 들면 event_near = 1
    near = [0] * len(f)
    try:
        if len(CAL) and '날짜' in CAL and '영향 층' in CAL:
            today = pd.Timestamp.now(tz='Asia/Seoul').normalize().tz_localize(None)
            for _, r in CAL.iterrows():
                dt = pd.to_datetime(r['날짜'], errors='coerce')
                if pd.isna(dt) or not (0 <= (dt - today).days <= 7):
                    continue
                lays = str(r['영향 층']).split('|')
                near = [1 if (n or lay in lays) else 0 for n, lay in zip(near, f['layer'].astype(str))]
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('변수달력', e)
    try:
        f['event_near'] = near
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["event_near"] = near', e)
    try:
        f['event_hit'] = f['event_words'] != ''
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["event_hit"] = f["event_words"] != ""', e)
    try:
        if 'shock_z5' in f:   # 가격 충격 설명(매도 신호 칸에 붙음)
            lab = np.where(f['shock_layer'] == 1, '업종 동반 급락', '')
            lab = [', '.join(x for x in (a, f'잔차 {z:.1f}σ' if z <= -3 else '') if x) for a, z in zip(lab, f['shock_z5'].fillna(0))]
            f['event_words'] = [', '.join(x for x in (w, l) if x) for w, l in zip(f['event_words'], lab)]
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('if "shock_z5" in f:', e)
    try:
        f['event_words'] = [', '.join(x for x in (w, f'부정 뉴스 {p:.2f} "{t}"' if p >= 0.9 else '') if x) for w, p, t in zip(f['event_words'], f['news_neg'], f['news_title'])]
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["event_words"] = [", ".join(x for x in', e)
    try:
        f['sector'] = f['번호'].map(sect)
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('f["sector"] = f["번호"].map(sect)', e)
    try:
        _bottom_cols(d, f)
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('_bottom_cols(d, f)', e)
    try:   # 11/24 B24 실제 이익 공식 3개(데이터베이스 EPS 칸, 과거 값과 같은 식 — eps_proxy.py)
        import eps_proxy as EP
        f = EP.apply(f, None, d)
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('eps_proxy', e)
    # 11/21: 보조 자료에 같은 번호가 두 줄이면(새로 넣은 종목) 합칠 때 줄이 불어 엔진이 멈춤 → 번호당 한 줄
    if f['번호'].duplicated().any():
        _fail('번호 중복', ValueError(', '.join(sorted(set(f.loc[f['번호'].duplicated(), '번호'].astype(str))))))
        f = f.drop_duplicates('번호', keep='first').reset_index(drop=True)
    return f


def _bottom_cols(d, f):
    """11/20 의장 B11·B12 = 바닥 블록. 문턱·검정 수치는 비공개 blocks.yaml.
    시장 칸(같은 시장 종목에 같은 값): 지수 50일 이격·RSI, 과매도 종목 비율(B16 앞 네 공식 중 둘), 200일선 아래 비율, VIX·VIX−VIX3M.
    종목 칸: rs_mkt63 = 63일 수익 − 지수 63일 수익. mk_bottom_n = B11 공식 중 켜진 수."""
    def rsi(x):
        dd = x.diff(); up = dd.clip(lower=0).ewm(alpha=1 / 14).mean(); dn = (-dd.clip(upper=0)).ewm(alpha=1 / 14).mean()
        return 100 - 100 / (1 + up / dn)
    try:
        import qc_config as QCC
        SB = QCC.load_blocks().get('종목', {})
    except Exception:   # noqa: BLE001
        SB = {}
    env = lambda r: {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in r.items()}
    def ev(e, r):
        try:
            return bool(eval(e, {'__builtins__': {}}, r))
        except Exception:   # noqa: BLE001
            return None
    rows = [env(r) for r in f.to_dict('records')]
    ose = [x[1] for x in SB.get('B16', {}).get('공식', [])[:4]]   # 과매도 = B16(일봉 과매도) 앞 네 공식 중 둘 이상
    os4 = pd.Series([float(sum(bool(ev(e, r)) for e in ose) >= 2) if r.get('rsi_d') is not None and ose else np.nan for r in rows], index=f.index, dtype=float)
    below = (f['close'] < f['ma200']).astype(float).where(f['ma200'].notna() & f['close'].notna()) if 'ma200' in f else pd.Series(np.nan, index=f.index)
    stock = f['구분'] == '개별주'
    I = PS.index(d, 735)
    R = _r(d, '리스크')
    g = dict(zip(R['항목'], _num(R['값']))) if len(R) else {}
    f['vix'] = g.get('VIX'); f['vix_vix3m'] = g.get('VIX − VIX3M')
    for mk, ix in (('미국', '^GSPC'), ('한국', '^KS11')):
        m = f['시장'] == mk
        f.loc[m, 'mk_os_share'] = float(os4[m & stock].mean() * 100) if (m & stock).any() else np.nan
        f.loc[m, 'mk_below200'] = float(below[m & stock].mean() * 100) if (m & stock).any() else np.nan
        if ix in I:
            x = I[ix].dropna()
            f.loc[m, 'mk_gap50'] = float(x.iloc[-1] / x.tail(50).mean() * 100)
            f.loc[m, 'mk_rsi'] = float(rsi(x).iloc[-1])
            if 'ret63' in f and len(x) > 63:
                f.loc[m, 'rs_mkt63'] = f.loc[m, 'ret63'] - (x.iloc[-1] / x.iloc[-64] - 1) * 100
    try:   # 11/23 의장: 옛 B11(시장 바닥 5개)은 blocks.yaml '시장바닥'으로 옮김. mk_bottom_n = 그 공식 중 켜진 수(B12 조건)
        MB = QCC.load_blocks().get('시장바닥', {})
    except Exception:   # noqa: BLE001
        MB = {}
    be = [x[1] for x in MB.get('공식', [])]   # 자료 있는 공식이 과반일 때만
    rows = [env(r) for r in f.to_dict('records')]
    def cnt(r):
        v = [ev(e, r) for e in be]
        v = [x for x in v if x is not None]
        return float(sum(v)) if be and len(v) * 2 > len(be) else np.nan
    f['mk_bottom_n'] = [cnt(r) for r in rows]
    # 11/23 의장 B11 = '이 종목이 바닥 즈음인가?' — 종목 자기 값 5개(단기 4 + 200일선) 중 켜진 수
    sb = [x[1] for x in SB.get('B11', {}).get('공식', [])]
    f['st_bottom_n'] = [(lambda v: float(sum(v)) if sb and len(v) * 2 > len(sb) else np.nan)([x for x in (ev(e, r) for e in sb) if x is not None]) for r in rows]


def market(d):
    m = {}
    R = _r(d, '리스크')
    try:
        if len(R):
            g = dict(zip(R['항목'], _num(R['값'])))
            m.update(VIX=g.get('VIX'), MOVE=g.get('MOVE'), VIX_VIX3M=g.get('VIX − VIX3M'), HY=g.get('하이일드 스프레드'),
                     STLFSI=g.get('세인트루이스'), SOFR_IORB=g.get('SOFR−IORB'), T10Y2Y=g.get('10년−2년'))
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('리스크', e)
    C = _r(d, '매크로체크리스트')
    try:
        if len(C):
            g = dict(zip(C['항목'], _num(C['값'])))
            m.update(US10Y=g.get('미국 10년물'), REAL10Y=g.get('실질금리(10년 TIPS)'))
            m['REAL10Y_1W'] = dict(zip(C['항목'], _num(C['1주 전']))).get('실질금리(10년 TIPS)')
            # 11/23: 체크리스트 10년물(FRED, 하루 늦음)보다 07시 매크로(야후 ^TNX)가 더 최근이면 그 값 — 같은 날 원고와 B04가 다른 값을 내지 않게
            X = _r(d, '매크로')
            if len(X) and '미국 10년' in set(X['항목']):
                x = X[X['항목'] == '미국 10년'].iloc[0]; c0 = C[C['항목'] == '미국 10년물']
                if not len(c0) or str(x['기준일']) > str(c0['기준일'].iloc[0]):
                    m['US10Y'] = float(_num(pd.Series([x['값']])).iloc[0])
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('매크로체크리스트', e)
    G = _r(d, '공포탐욕')
    try:
        if len(G):
            m['FG'] = float(_num(G.loc[G['구분'] == '종합', '점수']).iloc[0])
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('공포탐욕', e)
    P = _r(d, '수급포지셔닝')
    try:
        if len(P):
            g = dict(zip(P['항목'], _num(P['값'])))
            m.update(CTA=g.get('CTA σ(근사)'), VOLT=g.get('변동성타기팅 노출(배)'), VXN_PCT=g.get('VXN 1년 백분위(%)'),
                     VIX_PCT=g.get('VIX 1년 백분위(%)'), EWNDX_PCT=g.get('비율 1년 백분위(%)'),
                     CTA_BUYN=g.get('추세 신호 매수 수(21·63·100일)'), CTA_UP_PCT=g.get('CTA 매수 전환까지(%)'), CTA_D5=g.get('CTA σ 5일 변화'),
                     VOLT_D5=g.get('변동성타기팅 5일 변화(배)'), SYS_TURN=g.get('시스템 매수 전환'), CTA_PLUS=g.get('CTA 플러스 전환'))
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('수급포지셔닝', e)
    RS = _r(d, '시장위험')   # 11/22 의장: B35 항복(C1·C2·C4), B03 S&P–AAA 회사채 괴리
    try:
        if len(RS):
            import risk_signals as RSG
            m.update(RSG.signals(RS.set_index(pd.to_datetime(RS['날짜'])).drop(columns=['날짜'])))
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식'
        _fail('시장위험', e)
    A = _r(d, 'ETF자금')
    try:
        if len(A):
            safe = A[(A['시장'] == '한국') & A['이름'].astype(str).str.contains('200|커버드콜|미국S&P500|미국나스닥100')]
            m['KR_SAFE_FLOW5'] = float(_num(safe['유입_5일']).sum())
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('ETF자금', e)
    V2 = _r(d, '지수밸류')
    try:
        if len(V2):
            v = V2.iloc[-1]; m['SPX_FPER'] = float(v['선행PER'])
            try:   # 11/23 의장: PER은 오늘 S&P500 ÷ 선행 EPS(지수밸류.csv 값이 옛 날짜로 남는 것 막기)
                ix = PS.index(d)['^GSPC'].dropna()
                eps = float(v['선행EPS'])
                if len(ix) and eps > 0:
                    m['SPX_CLOSE'], m['SPX_CLOSE_DATE'] = float(ix.iloc[-1]), f'{ix.index[-1]:%Y-%m-%d}'
                    m['SPX_FPER'] = round(m['SPX_CLOSE'] / eps, 2)
            except Exception as e:   # noqa: BLE001
                _fail('지수밸류 PER 다시 계산', e)
            if len(V2) >= 6: m['SPX_EPS_UP'] = float(V2['선행EPS'].iloc[-1] - V2['선행EPS'].iloc[-6])
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('지수밸류', e)
    PE = _r(d, '지수선행PE')
    try:   # 11/23 의장 "PER 찾아봐": 우리 수집 b09_valuation(매주 토요일, S&P500 503종목 야후 12개월 선행 EPS 합산)이 지수밸류.csv(손 입력)보다 새로우면 이걸 쓴다
        if len(PE):
            s = PE[PE['지수'] == 'S&P500'].copy()
            s['날짜'] = pd.to_datetime(s['날짜']); s = s.dropna(subset=['선행PE']).sort_values('날짜')
            old = pd.to_datetime(V2['날짜'].iloc[-1]) if len(V2) else pd.Timestamp('1900-01-01')
            if len(s) and s['날짜'].iloc[-1] > old:
                ix = PS.index(d)['^GSPC'].dropna()
                ep = [float(ix.loc[:t].iloc[-1]) / float(p) for t, p in zip(s['날짜'], s['선행PE'])]   # 그날 S&P500 종가 ÷ 선행PE = 지수 선행 EPS
                m['SPX_EPS'], m['SPX_EPS_DATE'] = round(ep[-1], 1), f"{s['날짜'].iloc[-1]:%Y-%m-%d}"
                m['SPX_EPS_SRC'] = f"우리 수집 {s['방법'].iloc[-1]}({int(s['받은 종목수'].iloc[-1])}/{int(s['종목수'].iloc[-1])}종목)"
                m['SPX_CLOSE'], m['SPX_CLOSE_DATE'] = float(ix.iloc[-1]), f'{ix.index[-1]:%Y-%m-%d}'
                m['SPX_FPER'] = round(m['SPX_CLOSE'] / m['SPX_EPS'], 2)
                m['SPX_EPS_UP'] = float(ep[-1] - ep[-6]) if len(ep) >= 6 else None   # 같은 출처끼리만 비교
                if m['SPX_EPS_UP'] is None: m.pop('SPX_EPS_UP')
    except Exception as e:   # noqa: BLE001
        _fail('지수선행PE', e)
    P = _px(d)
    try:
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
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('가격 데이터베이스', e)
    try:   # B01 하락 국면 확률(HMM, hist_market.hmm_bear): 10년치 데이터베이스 지수로 직접 계산(11/26 옛 외부 보고서 읽기 없앰)
        import hist_market as HMK
        for k, c in (('^GSPC', 'US_BEAR'), ('^KS11', 'KR_BEAR')):
            x = HMK.hmm_bear(PS.index(d)[k].dropna()).dropna()
            if len(x):
                m[c] = float(x.iloc[-1])
    except Exception as e:   # noqa: BLE001
        _fail('하락 국면 확률', e)
    try:   # 코스피 50일 이격(의장 기준: 125 과열주의, 130 과열)
        ix = PS.index(d)['^KS11'].dropna()
        m['KS_GAP50'] = float(ix.iloc[-1] / ix.iloc[-50:].mean() * 100)
    except Exception:
        pass
    # B10 세계는 평화로운가: 지정학 위험 지수(GPR, Caldara·Iacoviello) 7일 평균의 10년 백분위(07시 수집 b09_gpr.py)
    GP = _r(d, '지정학위험')
    try:
        if len(GP) and 'GPR_PCT' in GP:
            m['GPR_PCT'] = _num(GP['GPR_PCT']).dropna().iloc[-1] if _num(GP['GPR_PCT']).notna().any() else None
    except Exception as e:   # noqa: BLE001  11/21 의장 '병렬식': 한 자료가 깨져도 나머지는 계속
        _fail('지정학위험', e)
    return m
