# ======================================================================
# [블록 8-리오] 매크로 체크리스트 — 8개 항목의 '꺾임'과 반대 신호 n/8 (11/5 하이일드 실효수익률 추가)
#   하는 일  : 하이일드(스프레드·실효수익률)·MOVE·10년물·실질금리·유가·공포탐욕·금융 스트레스가 최근 20영업일(스트레스는 4주)
#              고점·저점에서 꺾였는지 센다. 국면(나쁨·중립·좋음)을 정하고, 그 국면의 반대 신호 수를 적는다.
#              (2026-10-29 의장 "좋을 때는 나빠질 것을, 나쁠 때는 좋아질 것을 찾도록". 기획안/리오_역할강화안_20261029.txt)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_매크로체크리스트.csv (항목 8줄 + 요약 1줄)
#   쓰는 위원: 리오 (회의 둘째 순서)
#   고칠 곳  : 문턱 값은 RIO_ITEMS 표, 국면 기준은 rio_phase (모두 v1 가정치, 복기 때 조정)
# ======================================================================
RIO_WIN = 20   # 일간 항목은 최근 20영업일 고점·저점

# (항목, 시계열 찾기, 단위, 나쁜 쪽 'up'=오르면 나쁨 'down'=내리면 나쁨, 문턱, 문턱 종류 'pp'=차이 'pct'=%, 출처)
RIO_ITEMS = [
    ('하이일드 스프레드', lambda: FS.get('BAMLH0A0HYM2'), '%', 'up', 0.15, 'pp', 'FRED BAMLH0A0HYM2'),
    # 2026-11-05 의장 "위기 관리용 지표 추가": 하이일드 실효수익률(회사가 실제로 내는 금리 = 국채금리 + 스프레드)
    ('하이일드 실효수익률', lambda: FS.get('BAMLH0A0HYM2EY'), '%', 'up', 0.25, 'pp', 'FRED BAMLH0A0HYM2EY'),
    ('MOVE', lambda: YS.get('MOVE'), '', 'up', 10, 'pct', '야후 ^MOVE'),
    # 11/23: FRED는 야후보다 하루 늦음 → 엔진 B04가 11/19 값 5.04, 원고 07시 표는 11/20 값 4.912로 서로 달랐음. 더 최근 날짜 쪽을 씀
    ('미국 10년물', lambda: max((x for x in (FS.get('DGS10'), YS.get('미국 10년')) if x is not None and len(x.dropna())),
                            key=lambda x: x.dropna().index[-1], default=None), '%', 'up', 0.15, 'pp',
     'FRED DGS10·야후 ^TNX 중 더 최근 날짜'),
    ('실질금리(10년 TIPS)', lambda: FS.get('DFII10'), '%', 'up', 0.15, 'pp', 'FRED DFII10'),
    ('유가(WTI)', lambda: YS.get('WTI'), '$', 'up', 8, 'pct', '야후 CL=F'),
    # 공포탐욕은 거꾸로 본다(2026-11-02 의장): 공포 쪽으로 내려가면 오를 때가 다가오는 것, 탐욕 쪽으로 오르면 조정이 다가오는 것
    ('공포탐욕', lambda: RIO_FG, '', 'up', 10, 'pp', 'CNN (역발상: 오르면 나쁨)'),
    ('금융 스트레스', lambda: FS.get('STLFSI4') if FS.get('STLFSI4') is not None else FS.get('NFCI'), '', 'up', None, 'week',
     'FRED STLFSI4 (없으면 NFCI), 주간'),
]


def rio_fg_series():
    hist = ((CNN or {}).get('fear_and_greed_historical') or {}).get('data') or []
    if not hist:
        return None
    s = pd.Series({pd.to_datetime(p['x'], unit='ms').normalize(): float(p['y']) for p in hist}).sort_index()
    return s[~s.index.duplicated(keep='last')]


def rio_turn(s, bad, thr, kind):
    """(좋아질 기미, 나빠질 기미, 20일 고점, 20일 저점, 문턱 설명). s는 기준일까지 자른 시계열"""
    s = s.dropna()
    if kind == 'week':   # 최근 4주 고점보다 내려가고 2주 연속 하락 = 좋아질 기미 (반대도 같음)
        w = s.iloc[-4:]
        if len(w) < 3:
            return None, None, None, None, ''
        d = s.diff().iloc[-2:]
        good = bool(s.iloc[-1] < w.max() and (d < 0).all())
        worse = bool(s.iloc[-1] > w.min() and (d > 0).all())
        return good, worse, w.max(), w.min(), '4주 고점·저점 + 2주 연속'
    w = s.iloc[-RIO_WIN:]
    if len(w) < 5:
        return None, None, None, None, ''
    v, hi, lo = s.iloc[-1], w.max(), w.min()
    if kind == 'pct':
        down, up = v <= hi * (1 - thr / 100), v >= lo * (1 + thr / 100)
        txt = f'20일 고점·저점 대비 ±{thr:g}%'
    else:
        down, up = v <= hi - thr, v >= lo + thr
        txt = f'20일 고점·저점 대비 ±{thr:g}' + ('%p' if bad == 'up' else '점')
    good, worse = (down, up) if bad == 'up' else (up, down)
    return bool(good), bool(worse), hi, lo, txt


def rio_phase(risk_rows, fg):
    """나쁨: 리스크 표 빨강·주황 3개 이상 또는 공포탐욕 75 이상(극단 탐욕) / 좋음: 빨강 0이고 주황 1개 이하, 공포탐욕 75 미만 / 그 밖 중립
    공포탐욕이 낮은 것(공포)은 나쁨으로 치지 않는다(2026-11-02 의장 "공포는 오를 시점이 다가온 것")."""
    red = sum(r['신호'] == '빨강' for r in risk_rows)
    warm = sum(r['신호'] in ('빨강', '주황') for r in risk_rows)
    if warm >= 3 or (fg is not None and fg >= 75):
        ph = '나쁨'
    elif red == 0 and warm <= 1:
        ph = '좋음'
    else:
        ph = '중립'
    return ph, red, warm


def rio_count(rows, ph):
    g = sum(r['좋아질 기미'] == '예' for r in rows)
    b = sum(r['나빠질 기미'] == '예' for r in rows)
    return g, b, (g if ph == '나쁨' else b if ph == '좋음' else None)


try:
    RIO_FG = rio_fg_series()
    if RIO_FG is not None and FG:   # 이력 끝에 오늘 점수
        RIO_FG.loc[pd.Timestamp(NOW.date())] = float(FG['score'])
        RIO_FG = RIO_FG.sort_index()
    rows, prev = [], []
    for name, fetch, unit, bad, thr, kind, src in RIO_ITEMS:
        s = fetch()
        r = {'항목': name, '나쁜 쪽': '오르면' if bad == 'up' else '내리면', '값': '데이터 없음', '기준일': None,
             '1주 전': None, '1달 전': None, '최근 고점': None, '최근 저점': None,
             '좋아질 기미': '', '나빠질 기미': '', '문턱(가정치)': '', '출처': src}
        if s is not None and len(s.dropna()) >= 3:
            s = s.dropna().sort_index()
            d = s.index[-1]
            good, worse, hi, lo, txt = rio_turn(s, bad, thr, kind)
            dec = 1 if name in ('MOVE', '공포탐욕', '유가(WTI)') else 3
            r.update({'값': round(float(s.iloc[-1]), dec), '기준일': d.strftime('%Y-%m-%d'),
                      '1주 전': at_or_before(s, d - pd.Timedelta(days=7)), '1달 전': at_or_before(s, d - pd.DateOffset(months=1)),
                      '최근 고점': None if hi is None else round(float(hi), dec),
                      '최근 저점': None if lo is None else round(float(lo), dec),
                      '좋아질 기미': '예' if good else '', '나빠질 기미': '예' if worse else '', '문턱(가정치)': txt})
            for k in ('1주 전', '1달 전'):
                r[k] = None if r[k] is None else round(r[k], dec)
            # 어제(직전 관측일) 기준으로 다시 세어 '어제보다 +n' 계산
            p = rio_turn(s.iloc[:-1], bad, thr, kind) if len(s) > 3 else (None, None)
            prev.append({'좋아질 기미': '예' if p[0] else '', '나빠질 기미': '예' if p[1] else ''})
        rows.append(r)

    ph, red, warm = rio_phase(globals().get('RISK') or [], FG.get('score') if FG else None)
    g, b, opp = rio_count(rows, ph)
    pg, pb, popp = rio_count(prev, ph)
    have = sum(r['값'] != '데이터 없음' for r in rows)
    N = len(RIO_ITEMS)
    if opp is None:
        line = f'국면 중립 | 좋아질 기미 {g}/{N}, 나빠질 기미 {b}/{N}'
    else:
        line = (f'국면 {ph} | 반대 신호({"좋아질" if ph == "나쁨" else "나빠질"} 기미) {opp}/{N}'
                + (f', 어제보다 {opp - popp:+d}' if prev else ''))
    line += f' | 리스크 표 빨강 {red}·주황 포함 {warm}개, 공포탐욕 {FG["score"]:.1f}' if FG else f' | 리스크 표 빨강 {red}·주황 포함 {warm}개'
    RIO = {'국면': ph, '좋아질': g, '나빠질': b, '반대 신호': opp, '한 줄': line}
    rows.append({'항목': '요약', '나쁜 쪽': '', '값': line, '기준일': TODAY, '1주 전': None, '1달 전': None,
                 '최근 고점': None, '최근 저점': None, '좋아질 기미': g, '나빠질 기미': b,
                 '문턱(가정치)': '국면: 빨강·주황 3개 이상 또는 공포탐욕 ≥ 75 = 나쁨, 빨강 0·주황 1개 이하 = 좋음 (공포탐욕은 역발상)',
                 '출처': '계산'})
    rio = pd.DataFrame(rows)
    rio['수집시각(KST)'] = stamp()
    rio.to_csv(f'{DAY}/{TODAY}_매크로체크리스트.csv', index=False, encoding='utf-8-sig')
    log(f'[8 매크로 체크리스트] {line} | 데이터 {have}/{N}')
except Exception as e:
    traceback.print_exc()
    log(f'[8 매크로 체크리스트] 실패: {type(e).__name__} {e}')
