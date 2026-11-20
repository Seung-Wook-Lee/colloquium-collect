"""종목 진단 — 블록33을 쓰는 순서(11/21 의장).

질문 "지금 ○○를 사도 되나? 26주·52주 뒤는?"에 이 순서로 답한다. 회의 원고와는 별개.
  1 시장   : 신호 둘 중 하나라도 켜지면 '살 때가 가까움'(11/21 의장 "공탐지수가 바닥을 제일 잘 찾는다")
             ① CNN 공포탐욕 종합이 극단 공포 구간 ② 기준지수가 이번 하락의 바닥일 확률(Lunde & Timmermann)이 문턱 이상
             공포탐욕 7개 지표 중 무엇이 끌어내렸는지(가격·심리 공포인지, 신용 공포인지)도 코드가 읽어 말한다
  2 종목   : 52주 고점 대비 낙폭(변동성 단위 포함), 200일선 위치, 12-1개월 모멘텀, RSI, TTM PER과 자기 역사 속 백분위
  3 비슷한 때: 이 종목의 과거(2015~1년 전)에서 지금과 낙폭·200일선·모멘텀이 비슷했던 날을 모아
             26주·52주 뒤 수익률(평균·중앙·승률)과 그 사이 추가로 더 빠진 폭(중앙·하위 25%)
  4 판정   : 비공개 blocks.yaml '진단' 문턱으로 '지금 사도 좋다 / 아직 더 떨어질 수 있다 / 사지 않는다' 중 하나와 근거
  5 서사   : 위 숫자를 사람 말로 — 무슨 일이 있었나(시장 탓·회사 탓 나눔) → 회사 실적 → 값 → 과거엔 → 그래서(11/21 의장 "서사가 없냐")
쓰기: python app/diagnose/run.py GOOGL MSFT MRVL JNJ JPM [--out 폴더] [--fg-csv YYYYMMDD_공포탐욕.csv]
      (--fg-csv 없으면 CNN에서 바로 받음)
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


FGK = {  # CNN 키 / 07시 공포탐욕.csv 지표 이름 → 한글
    'market_momentum_sp500': '모멘텀(S&P 125일선)', 'stock_price_strength': '신고가 강도', 'stock_price_breadth': '거래량 폭',
    'put_call_options': '풋콜 비율', 'market_volatility_vix': '변동성(VIX)', 'safe_haven_demand': '안전자산 선호',
    'junk_bond_demand': '정크본드(신용)'}
FGN = dict(zip(['1. Market Momentum', '2. Stock Price Strength', '3. Stock Price Breadth', '4. Put and Call Options',
                '5. Market Volatility', '6. Safe Haven Demand', '7. Junk Bond Demand'], FGK.values()))


def fear_greed(csv=None):
    """공포탐욕 종합과 7개 지표 점수. csv(07시 수집 파일)가 있으면 그걸, 없으면 CNN에서 바로."""
    try:
        if csv:
            G = pd.read_csv(csv)
            tot = G[G['구분'] == '종합'].iloc[0]
            return dict(종합=float(tot['점수']), 전일=float(tot['전일']), 주전=float(tot['1주 전']), 시각=str(tot.get('CNN 갱신시각', '')),
                        지표={FGN.get(n, n): float(v) for n, v in zip(G.loc[G['구분'] == '지표', '지표'], G.loc[G['구분'] == '지표', '점수'])})
        import requests
        j = requests.get('https://production.dataviz.cnn.io/index/fearandgreed/graphdata', timeout=20,
                         headers={'User-Agent': 'Mozilla/5.0'}).json()
        f = j['fear_and_greed']
        return dict(종합=float(f['score']), 전일=float(f['previous_close']), 주전=float(f['previous_1_week']), 시각=str(f.get('timestamp', '')),
                    지표={v: float(j[k]['score']) for k, v in FGK.items() if k in j})
    except Exception as e:   # noqa: BLE001
        print('공포탐욕 읽기 실패:', e)
        return {}


def fg_read(fg, F):
    """공포탐욕 → 판정과 말(규칙표: 비공개 '진단_공포탐욕')."""
    if not fg:
        return dict(가까움=False, 말='공포탐욕 자료를 못 읽었습니다(판정에서 빠짐).')
    v = fg['종합']
    if v <= F['극단공포']:
        zone, judge = '극단 공포', '살 때가 가까워졌습니다'
    elif v <= F['공포']:
        zone, judge = '공포', '살 준비를 할 때입니다'
    elif v >= F['탐욕']:
        zone, judge = '탐욕', '사람들이 들떠 있어 사기에 부담스러운 때입니다'
    else:
        zone, judge = '보통', '공포탐욕으로는 특별한 신호가 없습니다'
    low = sorted([(n, x) for n, x in fg['지표'].items() if x <= F['지표_바닥']], key=lambda t: t[1])
    t = f"공포탐욕 {v:.0f}(전날 {fg['전일']:.0f}, 1주 전 {fg['주전']:.0f}) — {zone}. {judge}."
    if low:
        t += ' 이번 공포를 만든 건 ' + ', '.join(f'{n} {x:.0f}' for n, x in low) + '입니다.'
    junk = fg['지표'].get('정크본드(신용)')
    if junk is not None and v <= F['공포']:
        t += (f" 정크본드(신용)는 {junk:.0f}로 아직 버팁니다. 가격과 심리가 무너진 공포이고, 돈줄이 막힌 공포는 아닙니다."
              if junk > F['신용_버팀'] else f" 정크본드(신용)도 {junk:.0f}로 무너졌습니다. 돈줄이 막히는 공포라 바닥이 더 멀 수 있습니다.")
    credit_bad = junk is not None and junk <= F['신용_버팀']
    return dict(가까움=v <= F['극단공포'] and not credit_bad, 말=t, 종합=v, 구간=zone)


def cfg():
    B = QCC.load_blocks(switches=False)
    if '진단' not in B:
        raise SystemExit("비공개 blocks.yaml에 '진단' 문턱이 없습니다.")
    C = dict(B['진단'])
    C['공포탐욕'] = B.get('진단_공포탐욕') or {}
    return C


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


def fundamentals(tk):
    """분기 실적: 매출·순이익 전년 같은 분기 대비, 순이익률, 최근 4번 실적 발표의 예상 대비(서프라이즈)."""
    import yfinance as yf
    out = {}
    try:
        q = yf.Ticker(tk).quarterly_income_stmt
        q = q[sorted(q.columns)]
        def yoy(row):
            if row not in q.index:
                return None
            v = q.loc[row].dropna()
            if len(v) < 2:
                return None
            last = v.index[-1]
            prev = [c for c in v.index if abs((last - c).days - 365) <= 25]
            return (last, v.iloc[-1], v[prev[0]]) if prev else None
        r = yoy('Total Revenue'); n = yoy('Net Income')
        if r:
            out.update(분기=r[0].strftime('%Y-%m'), 매출성장=(r[1] / r[2] - 1) * 100)
        if n and r and r[1]:
            out.update(순이익성장=(n[1] / n[2] - 1) * 100 if n[2] > 0 else None, 순이익률=n[1] / r[1] * 100, 순이익률_작년=n[2] / r[2] * 100)
    except Exception:   # noqa: BLE001
        pass
    try:
        E = yf.Ticker(tk).get_earnings_dates(limit=12).dropna(subset=['Reported EPS'])
        E = E[~E.index.duplicated()].sort_index().tail(4)
        if len(E):
            out.update(서프라이즈=[round(x, 1) for x in E['Surprise(%)']], 최근서프라이즈=float(E['Surprise(%)'].iloc[-1]),
                       최근발표=E.index[-1].strftime('%Y-%m-%d'))
    except Exception:   # noqa: BLE001
        pass
    return out


def move(s, b):
    """고점 이후 하락을 시장 탓(베타×기준지수 하락)과 회사 탓(나머지)으로 나눈다."""
    w = s.iloc[-252:]
    hi = w.idxmax()
    rs, rb = s.pct_change().iloc[-756:], b.pct_change().iloc[-756:]
    beta = rs.cov(rb) / rb.var()
    d = s.iloc[-1] / s[hi] - 1
    db = b.iloc[-1] / b.loc[hi] - 1
    m1, b1 = s.iloc[-1] / s.iloc[-22] - 1, b.iloc[-1] / b.iloc[-22] - 1
    return dict(고점일=hi.strftime('%Y-%m-%d'), 고점=float(s[hi]), 주=max(1, round((s.index[-1] - hi).days / 7)), 낙폭=d * 100, 지수낙폭=db * 100,
                베타=beta, 시장탓=beta * db * 100, 회사탓=(d - beta * db) * 100, 한달=m1 * 100, 지수한달=b1 * 100)


BMN = {'^NDX': '나스닥100', '^GSPC': 'S&P500', 'SOXX': '반도체 지수(SOXX)'}
VOICE = {'지금 사도 좋다(나눠서)': '지금 사시면 좋습니다. 다만 한 번에 다 사지 말고 나눠서 사세요.',
         '아직 더 떨어질 수 있다 — 나눠서 천천히': '1년 뒤를 보면 좋은 자리지만, 아직은 더 떨어질 수 있어 보입니다. 지금 조금, 더 빠지면 또 조금씩 나눠서 천천히 사세요.',
         '아직 더 떨어질 수 있다 — 기다린다': '지금은 서두를 이유가 없습니다. 더 떨어지거나 값이 내려올 때까지 기다리시는 게 낫습니다.',
         '사지 않는다': '사지 마세요. 과거에 비슷했던 때 1년 뒤 결과가 좋지 않았습니다.',
         '판단 보류 — 과거에 비슷했던 때가 적음': '판단을 미룹니다. 이 회사가 지금처럼 된 적이 과거에 거의 없어서 통계로 말할 수 없습니다.'}


def story(r):
    """숫자를 문단으로: 무슨 일 → 회사 실적 → 값 → 과거엔 → 그래서."""
    m, f, u, st, mk = r['이동'], r['실적'], r['사용'], r['상태'], r['시장']
    T = []
    T.append(f"**무슨 일이 있었나.** {m['고점일']} 고점 {m['고점']:,.2f}에서 {m['주']}주 만에 {m['낙폭']:.1f}% 빠졌습니다. "
             f"같은 기간 {BMN.get(r['기준지수'], r['기준지수'])}는 {m['지수낙폭']:.1f}%였습니다. 이 회사는 평소 지수가 1% 움직일 때 {m['베타']:.2f}% 움직이므로, "
             f"시장 때문에 빠진 몫이 약 {m['시장탓']:.1f}%이고 회사 자체 이유로 빠진 몫이 약 {m['회사탓']:+.1f}%입니다. "
             + ('대부분 시장 탓입니다.' if abs(m['회사탓']) < abs(m['시장탓']) / 2 else
                ('회사 자체 이유가 더 큽니다.' if m['회사탓'] < m['시장탓'] else '시장보다 덜 빠졌습니다. 회사 쪽은 오히려 버티고 있습니다.'))
             + f" 최근 한 달만 보면 {m['한달']:+.1f}%(지수 {m['지수한달']:+.1f}%)입니다.")
    if f:
        x = []
        if f.get('매출성장') is not None:
            x.append(f"{f['분기']} 분기 매출은 1년 전보다 {f['매출성장']:+.1f}%")
        if f.get('순이익성장') is not None:
            x.append(f"순이익은 {f['순이익성장']:+.1f}%")
        if f.get('순이익률') is not None:
            x.append(f"순이익률 {f['순이익률']:.0f}%(1년 전 {f['순이익률_작년']:.0f}%)")
        t = '**회사는 어떤가.** ' + (', '.join(x) + '입니다. ' if x else '')
        if f.get('서프라이즈'):
            beat = sum(v > 0 for v in f['서프라이즈'])
            t += (f"최근 4번 실적 발표 중 {beat}번 예상을 넘었고, 마지막({f['최근발표']})은 예상보다 {f['최근서프라이즈']:+.1f}%였습니다. ")
        grow = (f.get('매출성장') or 0) > r['C']['서사_매출성장'] and (f.get('순이익성장') or 0) > 0
        t += '실적은 꺾이지 않았습니다. 주가 하락이 실적 때문은 아닙니다.' if grow else '실적 쪽에도 힘이 빠진 신호가 있습니다.'
        T.append(t)
    if st.get('TTM PER') is not None:
        p = st['PER 백분위(2015~)']
        T.append(f"**값은 어떤가.** 지난 1년 이익 기준 PER {st['TTM PER']}배로, 2015년 이후 이 회사가 거래된 날 중 {p}%보다 쌉니다. "
                 + ('역사적으로 싼 자리입니다.' if p <= r['C']['서사_PER싸다'] else '비싼 편입니다.' if p >= r['C']['비쌈_PER백분위'] else '중간쯤입니다.'))
    if u.get('날수'):
        T.append(f"**과거엔 어땠나.** 2015년 이후 이 회사가 지금과 비슷했던 때({u['조건'].lstrip('+ ')})가 {u['사건수']}번 있었습니다. 그때 샀다면 "
                 f"반년(26주) 뒤 절반은 {u['중앙26']:+.1f}% 넘게 올랐고 이익 날 확률은 {u['승률26']:.0f}%, "
                 f"1년(52주) 뒤 절반은 {u['중앙52']:+.1f}% 넘게 올랐고 이익 날 확률은 {u['승률52']:.0f}%였습니다. "
                 f"다만 산 뒤 반년 안에 보통 {u['추가하락중앙']:.1f}% 더 빠졌고, 나쁠 때는 {u['추가하락하위25']:.1f}%까지 빠졌습니다.")
    t = '**시장은.** ' + r['공포탐욕'].get('말', '')
    if mk:
        t += f" {BMN.get(r['시장지수'], r['시장지수'])}는 고점 대비 {mk.get('지금낙폭')}%이고, 이번 하락이 바닥일 확률은 {mk.get('확률')}%입니다(VIX {st.get('VIX')})."
    sig = r['시장신호'].split()
    t += (' 시장 신호(' + '·'.join(sig) + ')가 켜져 있어 시장 쪽은 살 때가 가까운 것으로 판정합니다.') if sig else ' 시장 신호(공포탐욕 극단 공포, 바닥 확률)가 아직 켜지지 않았습니다.'
    T.append(t)
    T.append(f"**그래서.** {VOICE.get(r['판정'], r['판정'])}")
    return T


def diagnose(tk, P, MKT, C, FGR):
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
    # 시장 신호 둘 중 하나라도 켜지면 '살 때가 가까움': ① 공포탐욕 극단 공포(신용 버팀) ② 바닥 확률 문턱 이상
    prob_ok = not mk.get('하락중') or (mk.get('확률') or 0) >= C['시장_바닥확률_준비']
    mkt_bad = not (prob_ok or FGR.get('가까움'))
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
    st['VIX'] = round(now.vix, 1)
    r = dict(종목=tk, 이름=NAMES.get(tk) or info.get('shortName') or tk, 기준지수=bm, 판정=verdict, 근거=why, 상태=st, 비슷한때=rows,
             사용=use, 이동=move(s, b), 실적=fundamentals(tk), 시장=mk if mk.get('하락중') else {}, 시장지수=mbm, 공포탐욕=FGR,
             시장신호=('공포탐욕' if FGR.get('가까움') else '') + (' 바닥확률' if mk.get('하락중') and prob_ok else ''), C=C)
    r['서사'] = story(r)
    return r


def market(bms):
    import lt_bottom as LB
    T = LB.hazard_today(idx_list=tuple(x for x in bms if x in ('^NDX', '^GSPC')) or ('^GSPC',))
    return {r['기준지수']: r.to_dict() for _, r in T.iterrows()}


def render(res, day):
    L = [f'# 종목 진단 {day}', '', '지금 사도 되는지, 반년·1년 뒤는 어떨지. 숫자는 모두 코드로 계산했고, 판정 기준은 비공개 규칙입니다.', '']
    for r in res:
        L += [f"## {r['이름']} ({r['종목']}) — {r['판정']}", '']
        for t in r['서사']:
            L += [t, '']
        L += ['<details><summary>숫자</summary>', '', '| 지금 | 값 |', '|---|---|'] + [f'| {k} | {v} |' for k, v in r['상태'].items()]
        L += ['', '| 과거 비슷했던 때 | 횟수 | 반년 뒤(중간) | 반년 뒤 이익 확률 | 1년 뒤(중간) | 1년 뒤 이익 확률 | 산 뒤 더 빠진 폭(보통) | 나쁠 때 |', '|---|---|---|---|---|---|---|---|']
        for a in r['비슷한때']:
            if not a.get('날수'):
                L.append(f"| {a['조건']} | 0 | | | | | | |"); continue
            L.append(f"| {a['조건']} | {a['사건수']} | {a['중앙26']:+.1f}% | {a['승률26']:.0f}% | {a['중앙52']:+.1f}% | {a['승률52']:.0f}% | {a['추가하락중앙']:.1f}% | {a['추가하락하위25']:.1f}% |")
        L += ['', '</details>', '']
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tickers', nargs='+')
    ap.add_argument('--out', default=os.path.join(HERE, 'out'))
    ap.add_argument('--drive', action='store_true', help='드라이브 수집데이터/종목진단/ 에도 올림')
    ap.add_argument('--fg-csv', default=None, help='07시 수집 YYYYMMDD_공포탐욕.csv (없으면 CNN에서 바로)')
    a = ap.parse_args()
    import yfinance as yf
    C = cfg()
    bms = ['^NDX', '^GSPC', 'SOXX', '^VIX']
    P = yf.download(a.tickers + bms, start='2013-01-01', auto_adjust=True, progress=False)['Close'].ffill()
    MKT = market(bms)
    FGR = fg_read(fear_greed(a.fg_csv), C['공포탐욕']) if C['공포탐욕'] else dict(가까움=False, 말='')
    res = [diagnose(t, P, MKT, C, FGR) for t in a.tickers]
    day = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime('%Y%m%d')
    os.makedirs(a.out, exist_ok=True)
    md = render(res, day)
    open(os.path.join(a.out, f'진단_{day}.md'), 'w', encoding='utf-8').write(md)
    pd.DataFrame([{'종목': r['종목'], '판정': r['판정'], '시장신호': r['시장신호'], **r['상태']} for r in res]).to_csv(os.path.join(a.out, f'진단_{day}.csv'), index=False, encoding='utf-8-sig')
    if a.drive:
        sys.path.insert(0, os.path.join(os.path.dirname(APP), 'collect'))
        import drive
        if drive.ready():
            D = '콜로키움 수집데이터/종목진단'
            drive.put(f'{D}/진단_{day}.md', md.encode('utf-8'))
            drive.put(f'{D}/최신_진단.md', md.encode('utf-8'))
    print(md)


if __name__ == '__main__':
    main()
