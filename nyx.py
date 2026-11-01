# 닉스 팀(클로토·라케시스·아트로포스) 기술적 계산 — 블록 09_nyx가 종목마다 부른다
#   7개 기준: 지지·저항선, 볼린저밴드, RSI, CCI, 스토캐스틱 슬로우, 이격도, 일목균형표
#   + 차트 패턴: 이중·삼중 바닥/천장, 헤드앤숄더, 역헤드앤숄더 (2026-10-28 의장: 판정에 쓴다)
#   계산 규칙 원문: 드라이브 페르소나 스토리/03_00_닉스팀_공통/닉스_공통 (로컬 /mnt/project-files/페르소나/닉스_공통.txt)
#   진행 중인 주·월은 오늘 종가를 마지막 봉으로 넣는다(차트에서 보는 것과 같음).
import numpy as np
import pandas as pd

# 일봉·주봉별 설정: 스윙 판정 앞뒤 봉 수, 띠 폭, 보는 기간, 패턴 기준
CFG = {
    '일': dict(n=5, tol=0.02, look=250, plook=130, gap=10, rise=0.05, pre=20, drop=0.10,
               recent=20, head=0.03, sym=0.05, near=0.02),
    '주': dict(n=3, tol=0.03, look=104, plook=78, gap=4, rise=0.08, pre=8, drop=0.15,
               recent=8, head=0.05, sym=0.07, near=0.02),
}


# ---------- 지표 ----------
def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def rsi_sma(c, n=14):
    """단순평균식 RSI — 키움 등 국내 HTS 차트와 같은 값(참고용, 룰북 판정은 위 와일더식)"""
    d = c.diff()
    up, dn = d.clip(lower=0).rolling(n).mean(), (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + up / dn)


def cci(h, l, c, n=20):
    tp = (h + l + c) / 3
    ma = tp.rolling(n).mean()
    md = tp.rolling(n).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - ma) / (0.015 * md)


def stoch_slow(h, l, c, n=14, k=3, d=3):
    lo, hi = l.rolling(n).min(), h.rolling(n).max()
    sk = ((c - lo) / (hi - lo) * 100).rolling(k).mean()
    return sk, sk.rolling(d).mean()


def macd_osc(c):
    m = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    return m - m.ewm(span=9, adjust=False).mean()


def ichimoku(h, l, c):
    mid = lambda k: (h.rolling(k).max() + l.rolling(k).min()) / 2
    tenkan, kijun = mid(9), mid(26)
    span_a = ((tenkan + kijun) / 2).shift(26)        # 오늘 자리에 그려진 구름
    span_b = mid(52).shift(26)
    return tenkan, kijun, span_a, span_b


def cross(a, b):
    """이번 봉에서 a가 b를 넘었는지: '상향'(골든) / '하향'(데드) / ''"""
    if a.iloc[-1] > b.iloc[-1] and a.iloc[-2] <= b.iloc[-2]:
        return '상향'
    if a.iloc[-1] < b.iloc[-1] and a.iloc[-2] >= b.iloc[-2]:
        return '하향'
    return ''


def candle(o, h, l, c):
    """봉 한 개의 모양(2026-10-31 의장: 양봉·음봉을 보고, 음봉이라도 아랫꼬리가 길면 밑에서 강하게 밀어 올린 것).
    꼬리 길다 = 꼬리가 고저폭의 40% 이상이면서 몸통의 1.5배 이상(가정치)."""
    rng = h - l
    if not rng or not np.isfinite(rng):
        return '', np.nan, np.nan, np.nan
    body = abs(c - o)
    up, dn = h - max(o, c), min(o, c) - l
    kind = '도지' if body <= rng * 0.1 else ('양봉' if c > o else '음봉')
    long_dn = dn >= rng * 0.4 and dn >= body * 1.5
    long_up = up >= rng * 0.4 and up >= body * 1.5
    if long_dn and not long_up:
        note = f'아랫꼬리 긴 {kind}(밑에서 밀어 올림)'
    elif long_up and not long_dn:
        note = f'윗꼬리 긴 {kind}(위에서 밀림)'
    elif long_up and long_dn:
        note = f'위아래 꼬리 긴 {kind}(공방)'
    else:
        note = kind
    return note, round(body / rng * 100), round(up / rng * 100), round(dn / rng * 100)


def to_week(d):
    g = d.groupby(d.index.to_period('W-FRI'))
    w = g.agg({'시가': 'first', '고가': 'max', '저가': 'min', '종가': 'last', '거래량': 'sum'})
    w.index = g.apply(lambda x: x.index[-1])          # 그 주의 마지막 거래일
    return w


# ---------- 지지·저항선 ----------
def pivots(df, n, m=2):
    """스윙 저점·고점: 앞뒤 n봉 중 최저·최고. 뒤가 덜 찬 최근 점은 m봉 이상 지났으면 '잠정'."""
    lo, hi, L, out = df['저가'].values, df['고가'].values, len(df), []
    for i in range(L):
        a, b = max(0, i - n), min(L, i + n + 1)
        if i < n or (i + n >= L and L - 1 - i < m):
            continue
        conf = i + n < L
        if lo[i] == lo[a:b].min():
            out.append(dict(k='저', i=i, p=lo[i], conf=conf))
        if hi[i] == hi[a:b].max():
            out.append(dict(k='고', i=i, p=hi[i], conf=conf))
    return out


def bands(piv, tol):
    """가격이 tol 안에 모인 스윙 점을 띠로 묶는다"""
    out = []
    for p in sorted(piv, key=lambda x: x['p']):
        if out and p['p'] <= out[-1]['lo'] * (1 + tol):
            out[-1]['pts'].append(p)
        else:
            out.append({'lo': p['p'], 'pts': [p]})
    for b in out:
        b['hi'] = max(p['p'] for p in b['pts'])
        b['touch'] = len(b['pts'])
        b['last'] = max(p['i'] for p in b['pts'])
    return out


def volume_profile(df, look=120, nbin=20):
    t = df.iloc[-look:]
    tp = (t['고가'] + t['저가'] + t['종가']) / 3
    edges = np.linspace(t['저가'].min(), t['고가'].max(), nbin + 1)
    if not np.isfinite(edges).all() or edges[0] == edges[-1]:
        return None, None, None
    vp = t.groupby(pd.cut(tp, edges, include_lowest=True), observed=False)['거래량'].sum()
    top = vp.idxmax()
    return top.left, top.right, vp.max() / vp.sum() * 100


def sr_status(df, bs, cfg, vol_ratio=None):
    """지지·저항 상태: 최근 이탈·지지 반등·돌파·근접 (띠는 터치 2회 이상만)"""
    c, l = df['종가'], df['저가']
    px, prev = c.iloc[-1], c.iloc[-2]
    strong = [b for b in bs if b['touch'] >= 2]
    sup = [b for b in strong if b['hi'] < px * (1 + cfg['tol'])]
    res = [b for b in strong if b['lo'] > px]
    s1 = max(sup, key=lambda b: b['hi']) if sup else None
    r1 = min(res, key=lambda b: b['lo']) if res else None
    st_s, st_r = '', ''
    past = c.iloc[-6:-1]                              # 직전 5봉 종가: 어느 쪽에서 왔는지 본다
    # 지지 이탈: 위에서 내려오던 가격이 이번 봉 종가로 띠 하단 아래 마감
    broke = [b for b in strong if px < b['lo'] <= prev]
    # 저항 돌파: 아래에 있던 가격이 이번 봉 종가로 띠 상단 위 마감
    brk = [b for b in strong if prev <= b['hi'] < px and past.min() < b['lo']]
    if broke:
        b = max(broke, key=lambda b: b['lo'])
        st_s = f"이탈 {b['lo']:,.0f}~{b['hi']:,.0f}(터치{b['touch']})"
    elif (s1 is not None and not any(b is s1 for b in brk) and past.min() >= s1['lo']
          and l.iloc[-3:].min() <= s1['hi'] * (1 + cfg['tol']) and px > s1['hi']):
        st_s = f"반등 {s1['lo']:,.0f}~{s1['hi']:,.0f}(터치{s1['touch']})"
    elif s1 is not None:
        st_s = '위'
    if brk:
        b = min(brk, key=lambda b: b['hi'])
        tag = '' if vol_ratio is None else (' 거래량 동반' if vol_ratio >= 1.5 else ' 거래량 미달')
        st_r = f"돌파 {b['lo']:,.0f}~{b['hi']:,.0f}(터치{b['touch']}){tag}"
    elif r1 is not None and r1['lo'] <= px * (1 + cfg['near']):
        st_r = f"근접 {r1['lo']:,.0f}~{r1['hi']:,.0f}(터치{r1['touch']})"
    return st_s, st_r


# ---------- 차트 패턴 ----------
def multi_extreme(df, piv, cfg, kind='저'):
    """다중 바닥(kind='저') / 다중 천장(kind='고'). 반환: (이름, 상태, 넥라인, 날짜들) 또는 None"""
    sgn = 1 if kind == '저' else -1
    pts = [p for p in piv if p['k'] == kind]
    if not pts:
        return None
    last = pts[-1]
    if len(df) - 1 - last['i'] > cfg['recent']:
        return None
    hl = df['고가'].values if kind == '저' else df['저가'].values
    cl = df['종가'].values
    group = [last]
    band = cfg['tol'] * 1.5
    for p in reversed(pts[:-1]):
        ext = min(q['p'] for q in group) if kind == '저' else max(q['p'] for q in group)
        if sgn * (p['p'] - ext * (1 - sgn * band)) < 0:
            break                                     # 사이에 더 깊은 바닥(더 높은 천장)이 있으면 거기서 끝
        if abs(p['p'] / last['p'] - 1) > band:
            continue
        nxt = group[-1]
        if nxt['i'] - p['i'] < cfg['gap']:
            continue
        seg = hl[p['i']:nxt['i'] + 1]
        swing = seg.max() / max(p['p'], nxt['p']) - 1 if kind == '저' else 1 - seg.min() / min(p['p'], nxt['p'])
        if swing < cfg['rise']:
            continue
        group.append(p)
    group = group[::-1]
    while len(group) >= 2:
        first = group[0]
        seg = hl[first['i']:group[-1]['i'] + 1]
        neck = seg.max() if kind == '저' else seg.min()
        before = hl[max(0, first['i'] - cfg['pre']):first['i']]
        # 앞선 하락(상승): 첫 바닥 전 pre봉 안에 drop% 이상, 그리고 넥라인까지 거리의 절반 이상 떨어져(올라) 와야 한다
        if len(before) and kind == '저' and before.max() >= first['p'] * (1 + cfg['drop']) \
                and before.max() >= first['p'] + (neck - first['p']) * 0.5:
            break
        if len(before) and kind == '고' and before.min() <= first['p'] * (1 - cfg['drop']) \
                and before.min() <= first['p'] - (first['p'] - neck) * 0.5:
            break
        group = group[1:]                             # 맨 앞 점을 빼고 다시
    if len(group) < 2:
        return None
    name = ('삼중' if len(group) >= 3 else '이중') + (' 바닥' if kind == '저' else ' 천장')
    done = cl[-1] > neck if kind == '저' else cl[-1] < neck
    state = ('넥라인 돌파' if kind == '저' else '넥라인 이탈') if done else '형성 중'
    when = '·'.join(df.index[p['i']].strftime('%m/%d') for p in group)
    return name, state, neck, when


def head_shoulders(df, piv, cfg, kind='저'):
    """역헤드앤숄더(kind='저') / 헤드앤숄더(kind='고')"""
    pts = [p for p in piv if p['k'] == kind]
    if len(pts) < 3:
        return None
    a, b, c = pts[-3:]
    if len(df) - 1 - c['i'] > cfg['recent']:
        return None
    if kind == '저':
        ok = b['p'] < a['p'] * (1 - cfg['head']) and b['p'] < c['p'] * (1 - cfg['head'])
    else:
        ok = b['p'] > a['p'] * (1 + cfg['head']) and b['p'] > c['p'] * (1 + cfg['head'])
    if not ok or abs(a['p'] / c['p'] - 1) > cfg['sym']:
        return None
    if min(b['i'] - a['i'], c['i'] - b['i']) < cfg['gap'] // 2:
        return None
    hl = df['고가'] if kind == '저' else df['저가']
    s1, s2 = hl.iloc[a['i']:b['i'] + 1], hl.iloc[b['i']:c['i'] + 1]
    if kind == '저':
        i1, i2 = s1.values.argmax() + a['i'], s2.values.argmax() + b['i']
    else:
        i1, i2 = s1.values.argmin() + a['i'], s2.values.argmin() + b['i']
    p1, p2 = hl.iloc[i1], hl.iloc[i2]
    neck = p2 + (p2 - p1) / (i2 - i1) * (len(df) - 1 - i2) if i2 != i1 else p2   # 두 어깨 사이 고점(저점)을 이은 선
    px = df['종가'].iloc[-1]
    done = px > neck if kind == '저' else px < neck
    name = '역헤드앤숄더' if kind == '저' else '헤드앤숄더'
    state = ('넥라인 돌파' if kind == '저' else '넥라인 이탈') if done else '형성 중'
    when = '·'.join(df.index[p['i']].strftime('%m/%d') for p in (a, b, c))
    return name, state, neck, when


# ---------- 한 종목 ----------
def frame_row(df, tf, pre=''):
    """일봉(tf='일') 또는 주봉(tf='주') 한 묶음의 칸을 만든다"""
    cfg, out = CFG[tf], {}
    c, h, l = df['종가'], df['고가'], df['저가']
    px = c.iloc[-1]
    p = pre
    # 지지·저항선
    piv = pivots(df.iloc[-cfg['look']:], cfg['n'])
    sub = df.iloc[-cfg['look']:]
    bs = bands(piv, cfg['tol'])
    sup = sorted([b for b in bs if b['hi'] < px], key=lambda b: -b['hi'])[:2]
    res = sorted([b for b in bs if b['lo'] > px], key=lambda b: b['lo'])[:2]
    for tag, lst, ref in (('지지', sup, 'hi'), ('저항', res, 'lo')):
        for k in range(2):
            b = lst[k] if k < len(lst) else None
            out[f'{p}{tag}{k + 1}'] = f"{b['lo']:,.0f}~{b['hi']:,.0f}" if b else ''
            out[f'{p}{tag}{k + 1}_터치'] = b['touch'] if b else np.nan
            out[f'{p}{tag}{k + 1}_거리(%)'] = round((b[ref] / px - 1) * 100, 1) if b else np.nan
    lows = [q for q in piv if q['k'] == '저']
    out[f'{p}최근저점'] = (f"{lows[-1]['p']:,.0f} {sub.index[lows[-1]['i']]:%m/%d}"
                       + ('' if lows[-1]['conf'] else '(잠정)')) if lows else ''
    vol_ratio = None
    if tf == '주':
        vol_ratio = df['거래량'].iloc[-1] / df['거래량'].iloc[-21:-1].mean()
        out[f'{p}거래량_20주평균대비'] = round(vol_ratio, 2)
    s, r = sr_status(sub, bs, cfg, vol_ratio)
    out[f'{p}지지상태'], out[f'{p}저항상태'] = s, r
    # 패턴
    pats = []
    for fn, kind in ((multi_extreme, '저'), (head_shoulders, '저'), (multi_extreme, '고'), (head_shoulders, '고')):
        piv_p = [q for q in piv if q['i'] >= len(sub) - cfg['plook']]
        res_p = fn(sub, piv_p, cfg, kind)
        if res_p:
            name, state, neck, when = res_p
            pats.append(f'{name} {state}(넥라인 {neck:,.0f}, {when})')
    out[f'{p}패턴'] = ' / '.join(pats)
    # 볼린저(20,2)
    ma20, sd = c.rolling(20).mean(), c.rolling(20).std(ddof=0)
    up, dn = ma20 + 2 * sd, ma20 - 2 * sd
    out[f'{p}볼린저_상단'], out[f'{p}볼린저_중심'], out[f'{p}볼린저_하단'] = up.iloc[-1], ma20.iloc[-1], dn.iloc[-1]
    out[f'{p}볼린저_%B'] = round((px - dn.iloc[-1]) / (up.iloc[-1] - dn.iloc[-1]), 2)
    out[f'{p}볼린저_밴드폭(%)'] = round((up.iloc[-1] - dn.iloc[-1]) / ma20.iloc[-1] * 100, 1)
    walk_dn = (c <= dn * 1.01)[::-1].cumprod().sum()
    walk_up = (c >= up * 0.99)[::-1].cumprod().sum()
    out[f'{p}볼린저_하단워킹'] = int(walk_dn)
    out[f'{p}볼린저_상단워킹'] = int(walk_up)
    # RSI(14)와 시그널(6)
    r = rsi(c)
    out[f'{p}RSI'] = round(r.iloc[-1], 1)
    out[f'{p}RSI_시그널'] = round(r.rolling(6).mean().iloc[-1], 1)
    out[f'{p}RSI_단순평균식'] = round(rsi_sma(c).iloc[-1], 1)
    out[f'{p}RSI_시그널교차'] = cross(r, r.rolling(6).mean())
    # CCI(20)와 시그널(10)
    cc = cci(h, l, c)
    out[f'{p}CCI'] = round(cc.iloc[-1], 0)
    out[f'{p}CCI_시그널'] = round(cc.rolling(10).mean().iloc[-1], 0)
    out[f'{p}CCI_시그널교차'] = cross(cc, cc.rolling(10).mean())
    # 스토캐스틱 슬로우(14,3,3)
    sk, sdd = stoch_slow(h, l, c)
    out[f'{p}STO_K'], out[f'{p}STO_D'] = round(sk.iloc[-1], 1), round(sdd.iloc[-1], 1)
    out[f'{p}STO_교차'] = {'상향': '골든크로스', '하향': '데드크로스'}.get(cross(sk, sdd), '')
    # 이격도
    for m in ((20, 50, 60, 120) if tf == '일' else (20, 50, 60)):
        ma = c.rolling(m).mean().iloc[-1]
        out[f'{p}{m}{"일" if tf == "일" else "주"}선'] = ma
        out[f'{p}{m}{"일" if tf == "일" else "주"}_이격도'] = round(px / ma * 100, 1)
    # 일목균형표(9,26,52)
    tk, kj, sa, sb = ichimoku(h, l, c)
    top, bot = max(sa.iloc[-1], sb.iloc[-1]), min(sa.iloc[-1], sb.iloc[-1])
    out[f'{p}일목_전환선'], out[f'{p}일목_기준선'] = tk.iloc[-1], kj.iloc[-1]
    out[f'{p}일목_구름상단'], out[f'{p}일목_구름하단'] = top, bot
    out[f'{p}일목_구름위치'] = '위' if px > top else ('아래' if px < bot else '안') if np.isfinite(bot) else ''
    out[f'{p}일목_전환기준'] = '전환>기준' if tk.iloc[-1] > kj.iloc[-1] else ('전환<기준' if tk.iloc[-1] < kj.iloc[-1] else '같음')
    out[f'{p}일목_전환기준교차'] = {'상향': '호전', '하향': '역전'}.get(cross(tk, kj), '')
    out[f'{p}일목_후행스팬'] = ('26봉 전 종가 위' if px > c.iloc[-27] else '26봉 전 종가 아래') if len(c) > 27 else ''
    # MACD 오실레이터(클로토 2단계용, 이번·지난·2봉 전)
    mo = macd_osc(c)
    out[f'{p}MACD오실레이터'] = round(mo.iloc[-1], 2)
    out[f'{p}MACD오실레이터_1봉전'] = round(mo.iloc[-2], 2)
    out[f'{p}MACD오실레이터_2봉전'] = round(mo.iloc[-3], 2)
    # 봉 모양(이번 봉 + 최근 3봉)
    o = df['시가']
    note, b_, u_, d_ = candle(o.iloc[-1], h.iloc[-1], l.iloc[-1], px)
    out[f'{p}봉모양'] = note
    out[f'{p}봉_몸통(%)'], out[f'{p}봉_윗꼬리(%)'], out[f'{p}봉_아랫꼬리(%)'] = b_, u_, d_
    out[f'{p}최근3봉'] = ' → '.join(candle(o.iloc[i], h.iloc[i], l.iloc[i], c.iloc[i])[0] for i in (-3, -2, -1))
    return out


def analyze(d):
    """d: 한 종목 일봉(날짜 인덱스, 시가·고가·저가·종가·거래량). 반환: 한 줄 dict"""
    d = d[(d['고가'] > d['저가']) | (d['거래량'] > 0)].dropna(subset=['종가'])
    if len(d) < 130:
        return {}
    w = to_week(d)
    row = {'기준일': d.index[-1].date(), '종가': d['종가'].iloc[-1],
           '52주고점대비(%)': round((d['종가'].iloc[-1] / d['고가'].iloc[-250:].max() - 1) * 100, 1)}
    row.update(frame_row(d, '일', '일_'))
    if len(w) >= 60:
        row.update(frame_row(w, '주', '주_'))
    mon = d['종가'].groupby(d.index.to_period('M')).last()
    row['월_5개월선'] = mon.rolling(5).mean().iloc[-1]
    return row
