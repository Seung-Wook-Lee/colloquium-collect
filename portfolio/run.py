"""포트폴리오 회의(매주 목 10:30 KST) — 4개 포트폴리오의 목표 비중(%)을 코드로 만든다(11/20 의장 승인안).

입력: 블록33 판정표(그날 국장전), 회의 발표 json(결론 '지금 살 때인가'), 유니버스(층 L1~L5는 universe_layers 규칙으로 다시 계산),
      지난주 결과(최신_포트폴리오.csv), 야후 가격(공분산·변동성).
규칙: 비공개 portfolio.yaml(포트폴리오별 시장·층·코어·위성 조건·비중 계산법·종목 상한·변동성 목표·회전율 한도).
비중 계산법은 표준 이론 이름 그대로(portfolio/optimize.py).
출력: YYYYMMDD_포트폴리오.csv(포트폴리오·몫·종목·층·비중%·지난주%·차이), YYYYMMDD_포트폴리오.md(표), 최신_포트폴리오.csv.
금액·수량은 다루지 않는다.

  python portfolio/run.py                       # GitHub Actions: 드라이브에서 받고 드라이브에 올림
  python portfolio/run.py --local <폴더>        # 손 시험: <폴더>/판정표.csv·유니버스.csv(·발표.json·지난주_포트폴리오.csv), 결과는 <폴더>/out/
"""
import argparse
import datetime as dt
import io
import json
import os
import sys

import numpy as np
import pandas as pd
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path[:0] = [REPO, os.path.join(REPO, 'block33')]
import qc_config as QCC          # noqa: E402
from data import universe_layers as UL     # noqa: E402
from portfolio import optimize as O  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
D_DATA = '콜로키움 수집데이터'
D_OUT = f'{D_DATA}/포트폴리오회의'
METHODS = {'계층적 위험 균형': 'hrp', '위험 균형': 'rp', '블랙-리터만': 'bl', '점수 × 역변동성': 'siv', '역변동성': 'iv'}


def load_cfg():
    return yaml.safe_load(open(os.path.join(QCC.private_dir(), 'portfolio.yaml'), encoding='utf-8'))


# ---------- 입력 ----------
def pull_drive(today, IN):
    import drive
    d0 = dt.date(int(today[:4]), int(today[4:6]), int(today[6:]))
    got = {}
    for back in range(0, 8):
        day = (d0 - dt.timedelta(days=back)).strftime('%Y%m%d')
        for key, name in (('판정표', f'{day}_판정표.csv'), ('발표', f'{day}_발표.json')):
            if key in got:
                continue
            data = drive.get(f'{D_DATA}/{day}/{name}')
            if data:
                open(f'{IN}/{key}{os.path.splitext(name)[1]}', 'wb').write(data)
                got[key] = day
        if '판정표' in got:
            break
    names = sorted(f['name'] for f in drive.ls('콜로키움/포트폴리오') if f['name'].startswith('콜로키움100_유니버스_') and f['name'].endswith('.csv'))
    if names:
        open(f'{IN}/유니버스.csv', 'wb').write(drive.get(f'콜로키움/포트폴리오/{names[-1]}'))
        got['유니버스'] = names[-1]
    last = drive.get(f'{D_OUT}/최신_포트폴리오.csv')
    if last:
        open(f'{IN}/지난주_포트폴리오.csv', 'wb').write(last)
        got['지난주'] = '있음'
    return got


def buy_state(path):
    """회의 결론 칸 '{시장}: 지금 살 때인가' → {시장: (산다?, 문장)}. 없으면 빈 dict."""
    if not os.path.exists(path):
        return {}
    J = json.load(open(path, encoding='utf-8'))
    out = {mk: (bool(v.get('buy')), str(v.get('act', ''))) for mk, v in (J.get('state') or {}).items()}   # 11/20부터 원고에 매수 문구 없음 → 'state'
    if out:
        return out
    import re
    for m in J.get('members', []):
        for ln in m.get('lines', []) or []:   # 옛 형식: '2. **미국: 지금 살 때인가**: 산다 — ...'
            g = re.match(r'^\d+\. \*\*(.+?): 지금 살 때인가\*\*: (.*?)(\s+\n|$)', ln)
            if g:
                out[g.group(1).strip()] = (g.group(2).startswith('산다'), g.group(2).strip())
        for r in m.get('rows', []) or []:
            t = r.get('항목', '')
            if t.endswith(': 지금 살 때인가'):
                mk = t.split(':')[0].strip()
                out[mk] = (str(r.get('값', '')).startswith('산다'), str(r.get('값', '')))
    return out


def split_frac(text):
    """'산다 — 3번 나눠 1번째' → 1/3. 나눔이 없으면 1."""
    import re
    m = re.search(r'(\d+)번 나눠 (\d+)번째', text or '')
    return min(1.0, int(m.group(2)) / int(m.group(1))) if m else 1.0


def load_last(path):
    if not os.path.exists(path):
        return pd.DataFrame(columns=['포트폴리오', '티커', '비중(%)'])
    return pd.read_csv(path, encoding='utf-8-sig')


# ---------- 계산 ----------
def returns(P, names, years):
    R = P[names].pct_change(fill_method=None)
    R = R[R.index >= R.index.max() - pd.DateOffset(years=years)]
    R = R.where(R.abs() < 0.5)
    return R.dropna(axis=1, thresh=120)


def weigh(method, cov, score, bl=None):
    if method == 'hrp':
        return O.hierarchical_risk_parity(cov)
    if method == 'rp':
        return O.risk_parity(cov)
    if method == 'siv':
        return O.score_inverse_vol(cov, score)
    if method == 'bl':
        prior = bl['prior'].reindex(cov.index).fillna(0)
        prior = prior / prior.sum() if prior.sum() > 0 else O.inverse_vol(cov)
        views = (score.reindex(cov.index) - 0.5) * bl.get('견해_크기', 0.10)
        return O.black_litterman(cov, prior, views, tau=bl.get('tau', 0.05))
    return O.inverse_vol(cov)


def market_caps(tickers):
    import yfinance as yf
    out = {}
    for t in tickers:
        try:
            out[t] = float(yf.Ticker(t).fast_info['market_cap'])
        except Exception:   # noqa: BLE001
            out[t] = np.nan
    return pd.Series(out)


def pick(T, spec, book):
    x = T[T['시장'].isin(book['시장']) & T['층'].isin(book['층'])]
    if spec.get('구분'):
        x = x[x['구분'] == spec['구분']]
    if spec.get('추천'):
        x = x[x['추천'].isin(spec['추천'])]
    if spec.get('원칙'):
        x = x[x['원칙'].isin(spec['원칙'])]
    if spec.get('거르기'):
        x = x.query(spec['거르기'])
    x = x.sort_values('점수', ascending=False).head(spec.get('최대종목', 15))
    add = T[T['티커'].isin(spec.get('더하기', []))]
    ref = book.get('_기준가', {})
    held = book.get('_지난주', set())
    x = pd.concat([x, add]).drop_duplicates('티커')
    return x[np.array([not (t in ref and t not in held and ref[t][1] > ref[t][0]) for t in x['티커']], dtype=bool)]   # 의장 장기 후보: 기준가 위면 새로 담지 않음
    return pd.concat([x, add]).drop_duplicates('티커')


def sleeve(names, share, method, P, years, score, upper=None, bl=None):
    """한 몫(코어·위성·해외ETF)의 비중: 계산법 → 종목 상한 → share 곱하기. 남는 몫은 현금."""
    names = [t for t in names if t in P]
    if not names or share <= 0:
        return pd.Series(dtype=float), share
    R = returns(P, names, years)
    if R.shape[1] == 0:
        return pd.Series(dtype=float), share
    cov = O.shrunk_cov(R)
    if bl is not None:
        bl = {**bl, 'prior': market_caps(list(cov.index))}
    w = weigh(method, cov, score, bl) if len(cov) > 1 else pd.Series(1.0, index=cov.index)
    if upper:
        w = O.cap(w, upper / share)
        w = w.clip(upper=upper / share)
    w = w * share
    return w[w > 1e-6], share - w.sum()


def build(name, book, T, P, common, state, last):
    per = [f'{k} 점수' for k in book.get('점수기간', []) if f'{k} 점수' in T]
    if per:   # 이 포트폴리오의 순위·비중 점수 = 블록 3 기간 점수 평균(예: 법인·배당 = 장기)
        T = T.assign(점수=T[per].mean(axis=1))
    yrs = common.get('공분산_년', 3)
    score = T.set_index('티커')['점수']
    parts, cash, notes = [], 0.0, []
    core = book.get('코어', {})
    fx = book.get('해외ETF', {})
    se = book.get('섹터ETF', {})   # 11/20 의장: 조선처럼 한 회사 고르기 애매한 업종은 섹터 ETF로 담는다
    sat_share = 1 - core.get('비중', 0) - fx.get('비중', 0) - se.get('비중', 0)
    if core:
        w, c = sleeve(core['종목'], core['비중'], 'rp', P, yrs, score)
        parts.append(('코어', w)); cash += c
    if fx:
        w, c = sleeve(fx['종목'], fx['비중'], METHODS.get(fx.get('방식'), 'siv'), P, yrs, score)
        parts.append(('해외ETF', w)); cash += c
    sat = book['위성']
    mk_buy = [state.get(m, (True, '결론 없음')) for m in book['시장']]
    if se:
        if all(b for b, _ in mk_buy):
            skip = set(se.get('제외', [])) | set(fx.get('종목', [])) | set(core.get('종목', []))
            Z = T[T['시장'].isin(book['시장']) & (T['구분'] == 'ETF') & T['추천'].isin(se.get('추천', ['추천', '관찰'])) & ~T['티커'].isin(skip)]
            Z = Z.sort_values('점수', ascending=False).head(se.get('최대종목', 4))
            w, c = sleeve(Z['티커'].tolist(), se['비중'], METHODS.get(se.get('방식'), 'siv'), P, yrs, score, se.get('종목상한'))
            notes.append(f"섹터 ETF 후보 {len(Z)}개(엔진 판정 {'·'.join(se.get('추천', ['추천', '관찰']))}, 점수 순 최대 {se.get('최대종목', 4)}): "
                         + (', '.join(Z['정식 종목명']) or '없음'))
        else:
            w = last[(last['포트폴리오'] == name) & (last['몫'] == '섹터ETF')].set_index('티커')['비중(%)'] / 100 if len(last) else pd.Series(dtype=float)
            c = se['비중'] - w.sum()
        parts.append(('섹터ETF', w)); cash += c
    if all(b for b, _ in mk_buy):
        held = set(last[last['포트폴리오'] == name]['티커']) if len(last) else set()
        C = pick(T, sat, {**book, '_기준가': common.get('_기준가', {}), '_지난주': held})
        for t, r in common.get('_기준가', {}).items():
            if t in T[T['시장'].isin(book['시장'])]['티커'].values and t not in C['티커'].values and t not in held and r[1] > r[0]:
                notes.append(f"{t} 현재 {r[1]:.1f} > 의장 기준가 {r[0]:g} → 새로 담지 않음")
        bl = book.get('블랙리터만') if METHODS.get(sat.get('방식')) == 'bl' else None
        if len(C) < sat.get('최대종목', 15):   # 후보가 모자라면 어디서 걸렸는지(엔진 판정표 그대로) 설명
            Z = T[T['시장'].isin(book['시장']) & T['층'].isin(book['층']) & ((T['구분'] == sat['구분']) if sat.get('구분') else True)]
            wait = Z['원칙'].astype(str).str.contains('추세 확인 대기')
            vc = Z.loc[~wait, '추천'].value_counts()
            top = ', '.join(f'{k} {v}' for k, v in vc.items() if k not in sat.get('추천', []))
            notes.append(f"위성 후보 {len(C)}개(최대 {sat.get('최대종목', 15)}). {'/'.join(book['시장'])} {'·'.join(book['층'])} {sat.get('구분', '')}: "
                         f"관찰(추세 확인 대기: 층별 기준, 추세 블록 아니오) {int(wait.sum())}"
                         + (f" [{', '.join(Z.loc[wait, '정식 종목명'].head(6))}]" if wait.any() else '') + (f", {top}" if top else ''))
        w, c = sleeve(C['티커'].tolist(), sat_share, METHODS.get(sat.get('방식'), 'iv'), P, yrs, score, sat.get('종목상한'), bl)
        cash += c
    else:   # 결론 '사지 않는다': 새로 사지 않고, 지난주 위성은 그대로 둔다. 나머지는 현금(MMF)
        prev = last[(last['포트폴리오'] == name) & (last['몫'] == '위성')].set_index('티커')['비중(%)'] / 100 if len(last) else pd.Series(dtype=float)
        w = prev.copy()
        cash += sat_share - w.sum()
        notes.append(f"결론 '{mk_buy[0][1]}' → 위성 새로 사지 않음(지난주 보유 유지, 나머지 현금)")
    parts.append(('위성', w))
    W = pd.concat([s.rename(k) for k, s in parts], axis=1).fillna(0) if parts else pd.DataFrame()
    risky = W.sum(axis=1) if len(W) else pd.Series(dtype=float)
    vol = np.nan
    if len(risky) and book.get('변동성목표'):
        R = returns(P, [t for t in risky.index if t in P], yrs)
        cov = O.shrunk_cov(R)
        r2 = risky.reindex(cov.index).fillna(0)
        scaled, _, vol = O.vol_target(r2, cov, book['변동성목표'])
        k = scaled.sum() / r2.sum() if r2.sum() > 0 else 1
        if k < 1:
            notes.append(f"예상 변동성 {vol * 100:.1f}% > 목표 {book['변동성목표'] * 100:.0f}% → 위험 자산 ×{k:.2f}, 나머지 현금")
            cash += risky.sum() * (1 - k)
            W = W * k
        vol = min(vol, book['변동성목표'])
    rows = [(part, t, v) for part in W.columns for t, v in W[part].items() if v > 1e-6]
    if cash > 1e-6:
        rows.append(('현금', '현금(MMF)', cash))
    out = pd.DataFrame(rows, columns=['몫', '티커', '비중'])
    if book.get('회전율한도') and len(last):
        old = last[last['포트폴리오'] == name].set_index('티커')['비중(%)'] / 100
        new = out.groupby('티커')['비중'].sum()
        lim = O.turnover_limit(new, old, book['회전율한도'])
        if not lim.equals(new.reindex(lim.index).fillna(0)):
            notes.append(f"회전율 한도 {book['회전율한도'] * 100:.0f}% 적용")
            part = out.set_index('티커')['몫'].to_dict()
            part.update({t: last[(last['포트폴리오'] == name) & (last['티커'] == t)]['몫'].iloc[0] for t in lim.index if t not in part})
            out = pd.DataFrame({'몫': [part[t] for t in lim.index], '티커': lim.index, '비중': lim.values})
            out = out[out['비중'] > 1e-6]
    out.insert(0, '포트폴리오', name)
    return out, vol, notes


def label_of(T, t):
    r = T[T['티커'] == t]
    if t == '현금(MMF)' or not len(r):
        return t
    r = r.iloc[0]
    if r['구분'] == 'ETF':   # 11/20 의장: ETF는 티커. 미국은 티커만, 한국은 '이름 (종목코드)'
        return t if r['시장'] == '미국' else f"{r['정식 종목명']} ({r['코드'] or t.split('.')[0]})"
    return UL.label(r.rename({'티커': 'yfinance 티커'}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date'); ap.add_argument('--local')
    a = ap.parse_args()
    today = a.date or dt.datetime.now(KST).strftime('%Y%m%d')
    if a.local:
        IN = os.path.abspath(a.local); OUT = os.path.join(IN, 'out'); got = {}
    else:
        IN = os.path.join(REPO, 'work_portfolio', 'in'); OUT = os.path.join(REPO, 'work_portfolio', 'out')
        os.makedirs(IN, exist_ok=True)
        got = pull_drive(today, IN)
        if '판정표' not in got:
            sys.exit('최근 8일 판정표가 드라이브에 없습니다.')
    os.makedirs(OUT, exist_ok=True)
    cfg = load_cfg()
    common = cfg.get('공통', {})
    ucfg = QCC.load_blocks()['유니버스']

    S = pd.read_csv(f'{IN}/판정표.csv', encoding='utf-8-sig', dtype={'번호': str})
    U = pd.read_csv(f'{IN}/유니버스.csv', encoding='utf-8-sig', dtype=str)
    U = U[~U['정식 종목명'].isin(ucfg.get('삭제', [])) & ~U['yfinance 티커'].isin(ucfg.get('삭제', [])) & ~U['시장'].isin(ucfg.get('제외_시장', []))]
    books = cfg['포트폴리오']
    BLK = QCC.load_blocks()
    X = set(BLK.get('_꺼짐', []))   # 11/20 의장: 블록 4 하위 블록 켜기·끄기(subblocks.yaml)
    FALL = {'4-3': '계층적 위험 균형', '4-4': '위험 균형', '4-5': '블랙-리터만', '4-6': '점수 × 역변동성'}
    for b in books.values():
        for k in ('위성', '해외ETF', '섹터ETF'):
            s = b.get(k)
            if not s:
                continue
            if '4-7' in X:
                s.pop('종목상한', None)
            if any(FALL[n] == s.get('방식') for n in FALL if n in X):
                s['방식'] = '역변동성'   # 꺼진 계산법 → 역변동성
        if '4-8' in X:
            b.pop('변동성목표', None)
        if '4-9' in X:
            b.pop('회전율한도', None)
        if '4-10' in X:
            b['나눠사기'] = False
    if '4-2' in X:
        O.shrunk_cov = lambda R: R.dropna(how='all').fillna(0.0).cov() * O.ANN   # 공분산 축소 꺼짐 → 표본 공분산
    extra = sorted({t for b in books.values() for k in ('코어', '해외ETF') for t in b.get(k, {}).get('종목', [])})
    tick = sorted(set(U['yfinance 티커'].dropna()) | set(extra))
    P = UL.prices(tick, max(ucfg['변동성_년'], common.get('공분산_년', 3)))
    PL = UL.asof(P, ucfg)   # '재분류: 월' → 층은 지난달 마지막 거래일 기준
    U = UL.classify(U, ucfg, UL.vol_from(PL[PL.index >= PL.index.max() - pd.DateOffset(years=ucfg['변동성_년'])], tick, ucfg.get('제외_구간', [])))

    cand = (BLK.get('의장 장기 후보') or {}) if '4-13' not in X else {}
    num2t = U.set_index('번호')['yfinance 티커'].to_dict()
    common['_기준가'] = {num2t[k]: (v['기준가'], float(P[num2t[k]].dropna().iloc[-1])) for k, v in cand.items()
                        if k in num2t and num2t[k] in P and v.get('기준가')}
    sc = common.get('점수칸', '순위점수')
    S = S.drop(columns=['층'], errors='ignore').rename(columns={sc if sc in S else '점수': '_점수'})
    T = U[['번호', '정식 종목명', '시장', '구분', '코드', 'yfinance 티커', '층', '연변동성']].rename(columns={'yfinance 티커': '티커'}).merge(
        S[['번호', '_점수', '추천', '원칙'] + [c for c in S.columns if c.startswith('B') and c[1:].isdigit()]], on='번호', how='left')
    T = T.rename(columns={'_점수': '점수'})
    T['점수'] = pd.to_numeric(T['점수'], errors='coerce')
    try:   # 11/20 재편: 블록 3 기간별 점수(단기·중기·장기)를 포트폴리오가 받는다(portfolio.yaml '점수기간')
        from block33 import b3_scores as B3
        PS = B3.build(S.rename(columns={'_점수': '순위점수'}), BLK).set_index('번호')
        for k in ('단기', '중기', '장기'):
            T[f'{k} 점수'] = pd.to_numeric(T['번호'].map(PS[f'{k} 점수']), errors='coerce')
    except Exception as e:   # noqa: BLE001
        print(f'[기간 점수] 실패: {e}')

    state = buy_state(f'{IN}/발표.json')
    last = load_last(f'{IN}/지난주_포트폴리오.csv')
    allout, head = [], []
    for name, book in books.items():
        out, vol, notes = build(name, book, T, P, common, state, last)
        allout.append(out)
        mk = ', '.join(f"{m} {state.get(m, (None, '결론 없음'))[1]}" for m in book['시장'])
        head.append((name, book.get('설명', ''), mk, vol, notes))
    A = pd.concat(allout, ignore_index=True)
    A['종목'] = [label_of(T, t) for t in A['티커']]
    A['층'] = A['티커'].map(T.drop_duplicates('티커').set_index('티커')['층']).fillna('')
    A['비중(%)'] = (A['비중'] * 100).round(1)
    prev = last.set_index(['포트폴리오', '티커'])['비중(%)'] if len(last) else pd.Series(dtype=float)
    A['지난주(%)'] = [prev.get((p, t), 0.0) for p, t in zip(A['포트폴리오'], A['티커'])]
    gone = last[~last.set_index(['포트폴리오', '티커']).index.isin(A.set_index(['포트폴리오', '티커']).index)] if len(last) else last
    if len(gone):
        g = gone[['포트폴리오', '몫', '티커', '종목', '층', '비중(%)']].rename(columns={'비중(%)': '지난주(%)'})
        g['비중(%)'] = 0.0
        A = pd.concat([A, g], ignore_index=True)
    A['차이(%p)'] = (A['비중(%)'] - A['지난주(%)']).round(1)
    A['이번주 집행(%)'] = A['비중(%)']
    for name, book in books.items():   # 결론 '산다 — N번 나눠 K번째': 늘리는 몫은 K/N만 이번 주에, 나머지 현금(MMF). 정기 적립 포트폴리오는 제외
        if book.get('나눠사기', True) is False:
            continue
        fr = [split_frac(state.get(m, (None, ''))[1]) for m in book['시장']]
        f = min(fr) if fr else 1.0
        if f >= 1:
            continue
        m = (A['포트폴리오'] == name) & (A['몫'] != '현금')
        A.loc[m, '이번주 집행(%)'] = (A.loc[m, '지난주(%)'] + (A.loc[m, '비중(%)'] - A.loc[m, '지난주(%)']).clip(lower=0) * f
                                   + (A.loc[m, '비중(%)'] - A.loc[m, '지난주(%)']).clip(upper=0)).round(1)
        c = (A['포트폴리오'] == name) & (A['몫'] == '현금')
        rest = round(100 - A.loc[m, '이번주 집행(%)'].sum(), 1)
        if c.any():
            A.loc[c, '이번주 집행(%)'] = rest
        else:
            A = pd.concat([A, pd.DataFrame([{'포트폴리오': name, '몫': '현금', '티커': '현금(MMF)', '종목': '현금(MMF)', '층': '', '비중(%)': 0.0,
                                             '지난주(%)': prev.get((name, '현금(MMF)'), 0.0), '이번주 집행(%)': rest}])], ignore_index=True)
            A['차이(%p)'] = (A['비중(%)'] - A['지난주(%)']).round(1)
        next(h for h in head if h[0] == name)[4].append(f'결론이 나눠 사기 → 늘리는 몫의 {f:.0%}만 이번 주 집행, 나머지 현금(MMF)')
    order = {'코어': 0, '해외ETF': 1, '섹터ETF': 2, '위성': 3, '현금': 4}
    A = A.sort_values(['포트폴리오', '몫', '비중(%)'], key=lambda s: s.map(order) if s.name == '몫' else (s.map(list(books).index) if s.name == '포트폴리오' else -s))
    A = A[['포트폴리오', '몫', '종목', '티커', '층', '비중(%)', '지난주(%)', '차이(%p)', '이번주 집행(%)']]

    md = [f'# 포트폴리오 회의 {today[:4]}-{today[4:6]}-{today[6:]}', '',
          '비중(%)만 표시. 지난주 대비 차이. 규칙: portfolio.yaml, 계산법: 표준 이론(계층적 위험 균형·위험 균형·블랙-리터만·점수 × 역변동성·변동성 목표·공분산 축소).', '']
    for name, desc, mk, vol, notes in head:
        g = A[A['포트폴리오'] == name]
        md += [f'## {name}', '', f'- {desc}', f'- 결론: {mk}', f"- 예상 연 변동성: {vol * 100:.1f}%" if pd.notna(vol) else '- 예상 연 변동성: 계산 못함']
        md += [f'- {n}' for n in notes] + ['', '| 몫 | 종목 | 층 | 목표 비중(%) | 지난주(%) | 차이(%p) | 이번 주 집행(%) |', '|---|---|---|---|---|---|---|']
        md += [f"| {r['몫']} | {r['종목']} | {r['층']} | {r['비중(%)']:.1f} | {r['지난주(%)']:.1f} | {r['차이(%p)']:+.1f} | {r['이번주 집행(%)']:.1f} |" for _, r in g.iterrows()]
        md += [f"| 합계 | | | {g['비중(%)'].sum():.1f} | {g['지난주(%)'].sum():.1f} | | {g['이번주 집행(%)'].sum():.1f} |", '']
    txt = '\n'.join(md)
    outs = {f'{today}_포트폴리오.csv': A.to_csv(index=False).encode('utf-8-sig'), f'{today}_포트폴리오.md': txt.encode('utf-8')}
    for k, v in outs.items():
        open(f'{OUT}/{k}', 'wb').write(v)
    print(txt)
    if not a.local:
        import drive
        for k, v in outs.items():
            drive.put(f'{D_OUT}/{k}', v)
        drive.put(f'{D_OUT}/최신_포트폴리오.csv', A[A['비중(%)'] > 0].to_csv(index=False).encode('utf-8-sig'))
        drive.put(f'{D_OUT}/최신_포트폴리오.md', txt.encode('utf-8'))
        print(f'[드라이브] {D_OUT}/ 에 올림 · 입력 {got}')


if __name__ == '__main__':
    main()
