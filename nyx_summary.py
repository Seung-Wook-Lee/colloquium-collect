# 닉스 요약 — 100종목 닉스 표(_닉스.csv)에서 회의에 필요한 줄만 뽑아 짧은 txt로 만든다(2026-11-05 의장 승인).
#   목적: 클로드가 100종목 × 수십 칸 표를 통째로 읽지 않고, 이 파일만 읽고 닉스 팀 발언을 하게 해 토큰을 줄인다.
#   1부  위원별 신호 목록(콜로키움 100 전체 감시, ★ = 핵심30)
#   2부  핵심30 종목별 7개 기준 한 줄
#   판정 기준은 룰북(미스 차트 v0.8.3, 라케시스 v0.6, 아트로포스 v0.5, 닉스_공통 7장)을 코드로 옮긴 1차 거름망이다.
#   하루치 표만 보므로 '5영업일 안', '3주 안', '2주 연속', 시장 대비 26주 수익률은 여기서 판정하지 않는다(회의에서 확인).
#   룰을 바꾸면 이 파일도 같이 고친다.
import re

import pandas as pd

MAX_ROWS = 15   # 위원별 목록이 길어지면 앞에서 이만큼만 쓰고 나머지는 개수만


def _f(v, nd=1):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return '-'
    if pd.isna(x):
        return '-'
    return f'{x:,.{nd}f}'


def _num(v):
    try:
        x = float(v)
        return None if pd.isna(x) else x
    except (TypeError, ValueError):
        return None


def _name(r, core):
    return ('★' if r['번호'] in core else '') + str(r['정식 종목명'])


def misschart(r):
    """미스 차트 1단계 4조건(일봉) 중 오늘 몇 개 충족인지 + 2단계 ⑤ 주봉 MACD 오실레이터 상승 여부"""
    rsi, x50 = _num(r.get('일_RSI')), _num(r.get('일_50일_이격도'))
    low, dn = _num(r.get('일_저가')), _num(r.get('일_볼린저_하단'))
    mo, mo1 = _num(r.get('일_MACD오실레이터')), _num(r.get('일_MACD오실레이터_1봉전'))
    conds = [('① 일봉 RSI≤30', rsi is not None and rsi <= 30),
             ('② 50일 이격도≤100', x50 is not None and x50 <= 100),
             ('③ 볼린저 하단 터치', low is not None and dn is not None and low <= dn),
             ('④ 일봉 MACD 막대 축소', mo is not None and mo1 is not None and mo < 0 and mo > mo1)]
    ok = [t for t, f in conds if f]
    miss = [t.split(' ', 1)[1] for t, f in conds if not f]
    wmo, wmo1 = _num(r.get('주_MACD오실레이터')), _num(r.get('주_MACD오실레이터_1봉전'))
    w_up = wmo is not None and wmo1 is not None and wmo > wmo1
    return len(ok), miss, w_up, rsi, x50


def _neck_gap(pattern, close):
    """'이중 바닥 넥라인 돌파(넥라인 1,234, 10/28)'에서 넥라인 대비 종가 거리(%)"""
    m = re.search(r'넥라인 ([\d,\.]+)', pattern)
    if not m or not close:
        return None
    neck = float(m.group(1).replace(',', ''))
    return (close / neck - 1) * 100 if neck else None


def lachesis(r):
    hits = []
    close = _num(r.get('종가'))
    v05 = str(r.get('라케시스_v05') or '')
    if v05.startswith('후보'):
        hits.append(f'하락 국면 v0.5 {v05}')
    res = str(r.get('주_저항상태') or '')
    if res.startswith('돌파'):
        hits.append(f'③ 주봉 저항 {res}')
    for p in str(r.get('주_패턴') or '').split(' / '):
        if any(k in p for k in ('이중 바닥', '삼중 바닥', '역헤드앤숄더')) and '넥라인 돌파' in p:
            g = _neck_gap(p, close)
            late = ' → 늦은 자리(+5% 넘음)' if g is not None and g > 5 else ''
            hits.append(f'④ {p} 넥라인 대비 {_f(g)}%{late}')
    return hits


def atropos(r):
    hits = []
    rsi, x20, pb = _num(r.get('주_RSI')), _num(r.get('주_20주_이격도')), _num(r.get('주_볼린저_%B'))
    hot = [t for t, f in ((f'주봉 RSI {_f(rsi)}≥75', rsi is not None and rsi >= 75),
                          (f'20주 이격도 {_f(x20)}≥125', x20 is not None and x20 >= 125),
                          (f'주봉 %B {_f(pb, 2)}>1', pb is not None and pb > 1)) if f]
    if len(hot) >= 2:
        hits.append('과열(새 돈은 눌림 대기): ' + ', '.join(hot))
    x50 = _num(r.get('주_50주_이격도'))
    if x20 is not None:
        if 99 <= x20 <= 101:
            hits.append(f'20주선 걸침(이격도 {_f(x20)})')
        elif x20 < 99:
            if x50 is not None and x50 < 100 and bool(r.get('주_50주선_하락')):
                hits.append(f'이탈 2단계 주의(추가 매수 보류): 20주 {_f(x20)}·50주 {_f(x50)}, 50주선 하락 중 — 3단계(시장 대비 26주 -20%p)는 회의에서 확인')
            else:
                hits.append(f'이탈 1단계 주의: 20주선 아래(이격도 {_f(x20)}, 금요일 종가로 확정)')
    sup = str(r.get('주_지지상태') or '')
    if sup.startswith('이탈'):
        hits.append(f'① 주봉 지지 {sup}')
    for p in str(r.get('주_패턴') or '').split(' / '):
        if any(k in p for k in ('이중 천장', '삼중 천장')) or (p.startswith('헤드앤숄더')):
            hits.append(f'② {p}')
    return hits


def core_line(r):
    return (f"{r['번호']} {r['정식 종목명']} | 종가 {_f(r.get('종가'), 2)} (52주 고점 {_f(r.get('52주고점대비(%)'))}%)"
            f" | RSI 일 {_f(r.get('일_RSI'))}·주 {_f(r.get('주_RSI'))}"
            f" | %B 일 {_f(r.get('일_볼린저_%B'), 2)}·주 {_f(r.get('주_볼린저_%B'), 2)}"
            f" | CCI 일 {_f(r.get('일_CCI'), 0)}·주 {_f(r.get('주_CCI'), 0)}"
            f" | STO 일 {_f(r.get('일_STO_K'))}/{_f(r.get('일_STO_D'))}"
            f" | 이격 50일 {_f(r.get('일_50일_이격도'))}·20주 {_f(r.get('주_20주_이격도'))}"
            f" | 일목 일 {r.get('일_일목_구름위치') or '-'}·주 {r.get('주_일목_구름위치') or '-'}"
            f" | 주봉 지지 {r.get('주_지지상태') or '-'}·저항 {r.get('주_저항상태') or '-'}"
            + (f" | 패턴 {r.get('주_패턴')}" if str(r.get('주_패턴') or '') not in ('', 'nan') else ''))


def build(nx, core_ids, stamp):
    """nx: _닉스.csv 표(DataFrame), core_ids: 핵심30 번호 집합, stamp: 계산 시각 문자열"""
    nx = nx[nx['종가'].notna()].copy()
    core = set(core_ids)
    L = [f'닉스 요약 — 계산 {stamp} KST, 콜로키움 100 중 {len(nx)}종목 계산(★ = 핵심30)',
         '판정은 이 파일 숫자로. 1차 거름망이라 5영업일·3주 창, 2주 연속, 시장 대비 수익률은 회의에서 확인.', '']

    def section(title, rows, empty):
        L.append(f'■ {title}')
        if not rows:
            L.append(f'  {empty}')
        rows = sorted(rows, key=lambda x: (not x[0].startswith('★'), x[1]))
        for name, _, text in rows[:MAX_ROWS]:
            L.append(f'  - {name}: {text}')
        if len(rows) > MAX_ROWS:
            L.append(f'  … 외 {len(rows) - MAX_ROWS}종목(_닉스.csv에서 확인)')
        L.append('')

    c_full, c_near, best = [], [], None
    for _, r in nx.iterrows():
        n, miss, w_up, rsi, x50 = misschart(r)
        w = ' / 주봉 MACD 오실레이터 상승 중(⑤ 후보)' if w_up else ''
        if n == 4:
            c_full.append((_name(r, core), 0, f'1단계 충족(RSI {_f(rsi)}, 50일 이격 {_f(x50)}){w}'))
        elif n == 3:
            c_near.append((_name(r, core), 1, f'1단계 3/4(미충족: {", ".join(miss)}){w}'))
        if best is None or n > best[0]:
            best = (n, _name(r, core), miss)
    section('미스 차트 — 1단계(일봉 4조건 오늘 동시 충족)', c_full, '오늘 1단계 충족 종목 없음')
    near_empty = (f'3/4 근접 없음. 가장 근접: {best[1]}({best[0]}/4, 미충족: {", ".join(best[2])})'
                  if best else '없음')
    section('미스 차트 — 1단계 근접(3/4)', c_near, near_empty)

    lk = [(_name(r, core), 0, ' / '.join(h)) for _, r in nx.iterrows() if (h := lachesis(r))]
    section('라케시스 — 돌파·바닥 패턴 완성·하락 국면 후보', lk, '오늘 라케시스 신호 없음')

    at = [(_name(r, core), 0, ' / '.join(h)) for _, r in nx.iterrows() if (h := atropos(r))]
    section('아트로포스 — 과열·이탈·천장', at, '오늘 아트로포스 신호 없음')

    L.append('■ 핵심30 7개 기준 한 줄(일봉·주봉)')
    cr = nx[nx['번호'].isin(core)]
    for _, r in cr.iterrows():
        L.append('  ' + core_line(r))
    missing = sorted(core - set(cr['번호']))
    if missing:
        L.append(f'  계산 없음: {", ".join(missing)}')
    return '\n'.join(L) + '\n'
