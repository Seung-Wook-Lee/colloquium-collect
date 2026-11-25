"""드라이브 저장본 먼저(11/25 의장 규칙, 코드로 심음).

의장: "구글 드라이브에 있는 것으로 계산한다, 라는 걸 코딩으로 심어 놓으라고. 거기 없을 때에만 뭘 받으라고."
      "오늘 가격만 받으면 되지. 월요일마다 뭘 또 받아."

규칙
1. 계산은 드라이브 저장본(00_퀀트입력, 전날 사본)으로 한다.
2. 가격(10년치 데이터베이스 가격10년_*, px_store.py)·시장위험: 저장본 마지막 날 뒤의 값만 받아 덧붙인다.
   과거 전체는 저장본에 없는 종목·칸만 받는다.
3. 재무·13F·공매도(SLOW): 저장본에 없는 것이 생겼을 때만 다시 받는다. '없는 것'은 아래뿐이다.
   - 저장본 파일이 없음
   - 유니버스에 있는데 저장본에 없는 종목(새 종목)
   - 저장본을 받은 날 뒤에 나온 새 실적 공시(07시 DART·SEC 파일의 공시일) → 분기·연매출·재무건전성·FZ
   - 저장본을 받은 날 뒤에 지난 13F 제출 마감일(2/14·5/15·8/14·11/14) → 장기펀드13F
   - 저장본을 받은 날 뒤에 지난 공매도 잔고 기준일(매월 15일·말일) → 공매도
4. 받는 곳은 아침 8시·저녁 8시 수집(supplement.py) 두 곳뿐이다. 회의 코드·블록33은 드라이브만 읽는다(11/26 의장 "따로 받는 코드는 전부 싹 다 지워").
tests/test_store_first.py가 이 규칙을 어기는 코드를 막는다."""
import datetime as dt
import os

import pandas as pd

SLOW = {'분기원자료.csv', '분기실적.csv', '재무건전성.csv', '연매출.csv', 'FZ점수.csv', '장기펀드13F.csv', '공매도.csv'}
EARN = {'분기원자료.csv', '분기실적.csv', '재무건전성.csv', '연매출.csv', 'FZ점수.csv'}
MARK = '보조갱신일.json'


def _read(p):
    try:
        return pd.read_csv(p, encoding='utf-8-sig', low_memory=False)
    except Exception:
        return None


def _universe(IN):
    N = _read(f'{IN}/닉스.csv')
    if N is None or '번호' not in N:
        return set()
    m = N['구분'].eq('개별주') & N['시장'].isin(['한국', '미국']) if {'구분', '시장'} <= set(N.columns) else pd.Series(True, index=N.index)
    return set(N.loc[m, '번호'].astype(str))


def _last_filing(IN):
    """07시 DART·SEC 파일에서 가장 늦은 공시일."""
    out = []
    for f, c in (('DART.csv', '잠정 공시일'), ('SEC.csv', '실적 받은날')):
        D = _read(f'{IN}/{f}')
        if D is not None and c in D:
            d = pd.to_datetime(D[c].astype(str).str[:10], errors='coerce').dropna()
            if len(d):
                out.append(d.max().date())
    return max(out) if out else None


def _passed(since, today, days):
    """since 다음 날부터 today까지 사이에 (월, 일) 날짜가 있었나"""
    d = since + dt.timedelta(days=1)
    while d <= today:
        if (d.month, d.day) in days or (('말일' in days) and (d + dt.timedelta(days=1)).day == 1):
            return True
        d += dt.timedelta(days=1)
    return False


def why_fetch(out, IN, mk, today):
    """받아야 하는 이유(없으면 None = 저장본 그대로)."""
    p = f'{IN}/{out}'
    if not os.path.exists(p):
        return '저장본 없음'
    if out not in mk:
        return '받은 날 기록 없음'
    since = dt.date.fromisoformat(mk[out])
    D = _read(p)
    if D is not None and '번호' in D and out != '장기펀드13F.csv':
        new = _universe(IN) - set(D['번호'].astype(str))
        if new:
            return f'새 종목 {len(new)}개'
    if out in EARN:
        lf = _last_filing(IN)
        if lf and lf > since:
            return f'새 실적 공시({lf})'
    if out == '장기펀드13F.csv' and _passed(since, today, {(2, 14), (5, 15), (8, 14), (11, 14)}):
        return '13F 제출 마감일 지남'
    if out == '공매도.csv' and _passed(since, today, {(m, 15) for m in range(1, 13)} | {'말일'}):
        return '공매도 잔고 기준일 지남'
    return None
