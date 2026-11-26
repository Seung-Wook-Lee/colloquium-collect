"""변곡점 판(11/22 의장): 의장이 고른 그림 9개를 원본(StockCharts 등) 그대로 우리 자료로 매일 다시 그린다.
"지금 준 그래프들의 움직임을 재현해서 앞으로 매일 보여줘. 변곡점을 지나는지, 더 무너져 내리는지 판단하는 중요한 기준."
순서(의장): 1 QQQ:RSP 앵커드 VWAP · 2 S&P 2023~2026 + CTM · 3 S&P 1994~2002 + CTM(고정) · 4 NVDA AVWAP·피보나치 · 5 S&P 1999~2000 이평 묶음(고정)
            6 S&P 2026 이평 묶음 · 7 SPYG:BIL 일목(의장: 뒤집은 쪽이 직관적) · 8 IWF:IWD 월봉 + 2016 추세선 · 9 MGK 주봉 + CTM-MGK
조건(B01·B02)에는 넣지 않는다(그림 본 뒤 의장이 정함). 입력 D = 시장위험.csv(collect/data/fetch_risk_daily.py).
draw(D, out) → out/turn_1.png ~ turn_9.png"""
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

try:
    from . import risk_signals as RS
except ImportError:
    import risk_signals as RS

plt.rcParams.update({'font.size': 7, 'axes.unicode_minus': False, 'axes.grid': True, 'grid.color': '#e8e8e8', 'grid.linewidth': .5})
NAMES = ['QQQ:RSP 앵커드 VWAP', 'S&P 2023~2026 + CTM', 'S&P 1994~2002 + CTM', 'NVDA AVWAP·피보나치', 'S&P 1999~2000 이평 묶음',
         'S&P 2026 이평 묶음', 'SPYG:BIL 일목', 'IWF:IWD 월봉 + 2016 추세선', 'MGK 주봉 + CTM-MGK']
# 그림 2·3의 이평 19개(원본 범례 순서·색)
MA19 = [(425, '#c0392b'), (235, '#8e1b3a'), (410, '#1e6b2e'), (225, '#7d7d7d'), (230, '#1c1f5c'), (125, '#a0a0a0'), (98, '#7b4a2b'), (159, '#d4a017'),
        (190, '#9b8b6b'), (143, '#222222'), (208, '#5dade2'), (169, '#58d68d'), (137, '#2c3e50'), (100, '#8b0000'), (70, '#6c3483'), (121, '#9b59b6'),
        (109, '#af7ac5'), (360, '#b9770e'), (64, '#c8a2c8')]
THICK = {230: 1.6, 410: 1.4, 425: 1.4}


def _real(r, s):
    """주봉·월봉의 마지막 칸 이름을 실제 마지막 거래일로(11/26 의장 "27일이 오지 않았는데 27일 기준?").
    W-FRI·ME로 묶으면 진행 중인 주(월)가 아직 오지 않은 금요일(말일) 날짜로 찍힘."""
    if len(r) and len(s) and r.index[-1] > s.index[-1]:
        r = r.rename(index={r.index[-1]: s.index[-1]})
    return r


def _wk(s, how='last'):
    s = s.dropna()
    return _real(getattr(s.resample('W-FRI'), how)().dropna(), s)


def _raw(D, k):   # StockCharts 비율은 배당 고친 값(IWF:IWD 0.41·일목 값이 원본과 같음 확인) → 고친 값 그대로
    return D[k]


def _hlc(ax, C, H, L, color='#1c1f5c', w=2.0):
    x = C.index
    ax.vlines(x, L.reindex(x), H.reindex(x), color=color, lw=.7)
    ax.hlines(C, x - pd.Timedelta(days=w), x + pd.Timedelta(days=w), color=color, lw=.7)


CAL_A, CAL_B = 8.45, 0.935   # 11/22 원본 그림 16곳으로 맞춘 눈금(ctm_calib.py): 원본 ≈ 8.45 + 0.935 × 우리. 기준(30 등)은 우리 눈금 그대로(의장 승인).


def _ctm_panel(ax, T, a, b, label):
    for lo, hi, c in ((70, 100, '#d5f0d5'), (50, 70, '#e9f7e3'), (30, 50, '#fdfbe3'), (0, 30, '#fde4e4')):
        ax.axhspan(lo, hi, color=c, lw=0)
    for y in (30, 35, 40, 45, 50, 55):
        ax.axhline(y, color='#555', lw=.5, ls=(0, (2, 2)))
    z = T.loc[a:b]; ax.plot(z.index, z, color='k', lw=.9); ax.set_ylim(0, 100); ax.set_yticks([10, 30, 50, 70, 90])
    ax.set_xlim(pd.Timestamp(a), pd.Timestamp(b) if b else z.index[-1] + pd.Timedelta(days=21)); ax.text(.005, .9, f'{label} {z.iloc[-1]:.2f}  (original-chart scale ~{CAL_A + CAL_B * z.iloc[-1]:.1f})', transform=ax.transAxes, fontsize=6.5)


# 11/23 의장: 그림마다 밑에 "대상 값·기준선 값·닿음/돌파" 표 → 그림을 그리면서 같은 선으로 기록(ROWS), draw()가 turn_lines.csv로 남김
ROWS = []
TOUCH = 1.0   # 선과 ±1% 안이면 '닿음'
CROSS_N = 4   # 돌파는 돌파한 봉부터 4봉 동안(64·109주선 상태와 같은 규칙), 그 사이 같은 쪽에 있을 때


def state(P, S):
    """대상 P와 기준선 S(같은 날짜 칸)로 상태: 상향 돌파 / 하향 돌파 / 위에서 닿음 / 아래에서 닿음 / 위 / 아래"""
    x = pd.concat([P, S], axis=1, keys=['p', 's']).dropna()
    if not len(x):
        return None, None
    up = x['p'] >= x['s']; gap = (x['p'].iloc[-1] / x['s'].iloc[-1] - 1) * 100
    k = up.iloc[-(CROSS_N + 1):]
    if len(k) > 1 and (k != k.iloc[-1]).any():
        return ('상향 돌파' if up.iloc[-1] else '하향 돌파'), gap
    if abs(gap) <= TOUCH:
        return ('위에서 닿음' if up.iloc[-1] else '아래에서 닿음'), gap
    return ('위' if up.iloc[-1] else '아래'), gap


def _rec(n, who, P, line, S, fmt='{:,.2f}'):
    """기준선 S는 Series(이평·VWAP 등) 또는 숫자(피보·CTM 30 등). CTM은 점수라 차이를 '점'으로."""
    P = P.dropna()
    if not isinstance(S, pd.Series):
        S = pd.Series(float(S), index=P.index)
    st_, gap = state(P, S)
    sv = S.reindex(P.index).dropna()
    if who.startswith('CTM'):
        gap_s = f'{P.iloc[-1] - sv.iloc[-1]:+.1f}점' if len(sv) else ''
    else:
        gap_s = '' if gap is None else f'{gap:+.1f}%'
    ROWS.append({'그림': n, '기준일': str(P.index[-1].date()), '대상': who, '대상 값': fmt.format(P.iloc[-1]), '기준선': line,
                 '선 값': fmt.format(sv.iloc[-1]) if len(sv) else '', '차이': gap_s, '상태': st_})


def _avwap(P, V, a):
    return ((P * V).loc[a:].cumsum() / V.loc[a:].cumsum())


def _save(fig, out, n):
    fig.savefig(f'{out}/turn_{n}.png', dpi=110, bbox_inches='tight'); plt.close(fig)


# 1 ── QQQ:RSP 일봉 + 앵커드 VWAP 7개(원본 범례 순서·색). 앵커는 원본 선이 시작하는 자리(비율의 저점·고점).
QR_ANCHORS = [('2020-09-01', '#1f3a93'), ('2022-12-28', '#8b0000'), ('2023-05-31', '#29a9e0'), ('2023-08-11', '#f07f1a'),
              ('2019-01-29', '#7d3c98'), ('2021-11-30', '#5b2c6f'), ('2023-01-05', '#e0306e')]


def fig1(D, out):
    x = pd.concat([_raw(D, 'QQQ'), _raw(D, 'RSP'), D['QQQ_VOL']], axis=1, keys=['q', 'r', 'v']).dropna()
    R = x['q'] / x['r']; z = R.loc['2017-01-01':]
    fig, ax = plt.subplots(figsize=(11, 5.6)); ax.plot(z.index, z, color='k', lw=.8, label=f'QQQ:RSP (Daily) {R.iloc[-1]:.2f}')
    for a, c in QR_ANCHORS:
        t = R.loc[a:].index[0]; s = _avwap(R, x['v'], t); ax.plot(s.index, s, color=c, lw=1.1, label=f'Anchored VWAP {s.iloc[-1]:.2f}')
        _rec(1, 'QQQ:RSP', R, f'앵커드 VWAP({t:%Y-%m-%d})', s.reindex(R.index), '{:.3f}')
    pk = R.loc['2020-06':'2021-06'].max(); _rec(1, 'QQQ:RSP', R, '2021 고점선', pk, '{:.3f}'); ax.axhline(pk, color='#1f5fbf', lw=1.6, ls=(0, (6, 3))); ax.text(z.index[-1], pk, f' {pk:.2f}', va='bottom', fontsize=6.5)
    ax.set_yscale('log'); ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.2f}')); ax.yaxis.set_minor_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.2f}')); ax.yaxis.tick_right()
    ax.set_title(f'QQQ:RSP - Invesco QQQ Trust/Invesco S&P 500 Equal Weight ETF   {R.index[-1]:%d-%b-%Y}', loc='left', fontsize=8)
    ax.legend(loc='upper left', fontsize=6, framealpha=.9); ax.text(.45, .06, 'NASDAQ 100 vs. EQ-WT S&P 500', transform=ax.transAxes, color='#1f5fbf', fontsize=12, weight='bold')
    _save(fig, out, 1)


def _ma_ctm(D, out, n, a, b, title, sub, notes=()):
    c, h, l = D['SPX'], D.get('SPX_HIGH', D['SPX']), D.get('SPX_LOW', D['SPX'])
    C, H, L = _wk(c), _wk(h.fillna(c), 'max'), _wk(l.fillna(c), 'min'); T = RS.ctm(D, 'SPX')
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(11, 6.2), gridspec_kw={'height_ratios': [3.3, 1]}, sharex=True)
    z = slice(a, b); _hlc(ax, C.loc[z], H.loc[z], L.loc[z])
    for p, col in MA19:
        m = C.rolling(p).mean().loc[z]; ax.plot(m.index, m, color=col, lw=THICK.get(p, .6), ls='-' if p in THICK else (0, (1, 1.2)), label=f'MA({p}) {m.iloc[-1]:.2f}')
        _rec(n, 'S&P 주봉', C.loc[z], f'{p}주선', C.rolling(p).mean().loc[z])
    for y in (30, 50):
        _rec(n, 'CTM-$SPX', T.loc[a:b], f'CTM {y}', y)
    if n == 3: ax.set_yscale('log')
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:,.0f}')); ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); ax.yaxis.tick_right()
    lo = min(L.loc[z].min(), C.rolling(230).mean().loc[z].min()) * .97; ax.set_ylim(lo, H.loc[z].max() * 1.03)
    ax.legend(loc='upper left', fontsize=5, ncol=1, framealpha=.85, handlelength=1.5)
    ax.text(.12, .9, title, transform=ax.transAxes, fontsize=13, weight='bold'); ax.text(.12, .84, sub, transform=ax.transAxes, fontsize=8, weight='bold')
    for t, y, s, col in notes:
        ax.annotate(s, (pd.Timestamp(t), y), fontsize=7, color=col, weight='bold', bbox=dict(fc='w', ec='#888', lw=.5))
    ax.set_title(f'$SPX S&P 500 Large Cap Index (Weekly) {C.loc[z].iloc[-1]:.2f}   {C.loc[z].index[-1]:%d-%b-%Y}', loc='left', fontsize=8)
    _ctm_panel(bx, T, a, b, 'CTM-$SPX'); fig.tight_layout(h_pad=.2); _save(fig, out, n)


def fig2(D, out):
    _ma_ctm(D, out, 2, '2023-01-01', None, 'S&P 500 2023-2026', 'COMPARE TO 1994-2002 PERIOD')


def fig3(D, out):
    _ma_ctm(D, out, 3, '1994-01-01', '2002-10-11', 'S&P 500 1994-2002', '',
            [('1999-10-01', 1600, 'MAJOR PEAK 2000', '#c0392b'), ('2000-11-01', 680, 'CHANGE IN\nCHARACTER', '#c0392b'), ('2002-04-01', 720, '-49.15%', '#c0392b')])


# 4 ── NVDA 주봉 + 앵커드 VWAP 7개(원본 값과 맞춘 앵커, 대표가격 (H+L+C)/3) + 피보나치(2022 저점 → 이번 고점)
NV_ANCHORS = [('2021-11-04', '#1f3a93', '-'), ('2022-09-15', '#8b0000', '-'), ('2023-08-25', '#29a9e0', '-'), ('2023-08-03', '#f07f1a', '-'),
              ('2023-10-20', '#5b2c6f', '-'), ('2025-01-06', '#7d3c98', ':'), ('2025-03-26', '#e0306e', ':')]


def fig4(D, out):
    x = D[['NVDA', 'NVDA_VOL', 'NVDA_HIGH', 'NVDA_LOW']].dropna(); x = x[x['NVDA_VOL'] > 0]
    P = (x['NVDA_HIGH'] + x['NVDA_LOW'] + x['NVDA']) / 3; C = _wk(x['NVDA']); z = C.loc['2021-01-01':]
    fig, ax = plt.subplots(figsize=(11, 5.4)); ax.plot(z.index, z, color='k', lw=.9, label=f'NVDA (Weekly) {C.iloc[-1]:.2f}')
    for a, c, ls in NV_ANCHORS:
        s = _wk(_avwap(P, x['NVDA_VOL'], a)); ax.plot(s.index, s, color=c, lw=1.2 if ls == '-' else .8, ls=ls, label=f'Anchored VWAP {s.iloc[-1]:.2f}')
        _rec(4, 'NVDA 주봉', C, f'앵커드 VWAP({a})', s.reindex(C.index))
    lo, lt = C.loc['2022-06':'2023-01'].min(), C.loc['2022-06':'2023-01'].idxmin(); hi = C.loc['2023':].max()   # 원본 피보는 주봉 종가
    ax.axvspan(pd.Timestamp('2022-07-01'), lt, color='#ddd', alpha=.6)
    for r in (0, .382, .5, .618, 1):
        y = hi - (hi - lo) * r; ax.hlines(y, pd.Timestamp('2022-07-01'), lt, color='k', lw=.8); ax.text(lt, y, f'{r * 100:.2f}%', fontsize=6, ha='right', va='bottom')
        _rec(4, 'NVDA 주봉', C, f'피보 {r * 100:.1f}%', y)
        if r in (.5, .618):
            ax.axhline(y, color='#1f5fbf', lw=1.8, ls=(0, (5, 3))); ax.text(z.index[-1] + pd.Timedelta(days=30), y, f'{y:.2f}', fontsize=7, va='bottom')
    ax.set_yscale('log'); ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}')); ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter()); ax.yaxis.tick_right()
    ax.set_xlim(pd.Timestamp('2021-01-01'), z.index[-1] + pd.Timedelta(days=160))
    ax.legend(loc='upper left', fontsize=6, framealpha=.9); ax.text(.6, .12, 'NVDA 2021-2026\nWEEKLY AWAPS & FIBS', transform=ax.transAxes, fontsize=13, weight='bold')
    ax.set_title(f'NVDA - NVIDIA Corp.   {C.index[-1]:%d-%b-%Y}', loc='left', fontsize=8); _save(fig, out, 4)


CL6 = [(50, '#1f3a93'), (55, '#a93226'), (60, '#1e8449'), (65, '#d63384'), (70, '#9b59b6'), (75, '#e67e22')]


def _cluster(D, out, n, a, b, title, notes=(), fib=None):
    C = _wk(D['SPX']); z = C.loc[a:b]
    fig, ax = plt.subplots(figsize=(11, 5.2)); ax.plot(z.index, z, color='k', lw=1, label=f'$SPX (Weekly) {z.iloc[-1]:.2f}')
    for p, c in CL6:
        m = C.rolling(p).mean().loc[a:b]; ax.plot(m.index, m, color=c, lw=1.1, label=f'MA({p}) {m.iloc[-1]:.2f}')
        _rec(n, 'S&P 주봉', z, f'{p}주선', C.rolling(p).mean().loc[a:b])
    _rec(n, 'S&P 주봉', z, '110주선', C.rolling(110).mean().loc[a:b])
    m = C.rolling(110).mean().loc[a:b]; ax.plot(m.index, m, color='#8b0000', lw=1.1, ls=(0, (1, 1.5)), label=f'MA(110) {m.iloc[-1]:.2f}')
    if fib:
        lo, hi = fib
        for r in (0, .382, .5, .618, 1):
            y = hi - (hi - lo) * r; _rec(n, 'S&P 주봉', z, f'피보 {r * 100:.1f}%', y); ax.axhline(y, color='#777', lw=.6, ls=(0, (2, 2)), xmin=.82); ax.text(z.index[int(len(z) * .83)], y, f'{r * 100:.1f}%: {y:.2f}', fontsize=6, color='#555')
    for t, y, s, col in notes:
        ax.annotate(s, (pd.Timestamp(t), y), fontsize=8, color=col, weight='bold', bbox=dict(fc='w', ec='#888', lw=.5))
    ax.yaxis.tick_right(); ax.legend(loc='upper left', fontsize=6, framealpha=.9)
    ax.text(.03 if not fib else .2, .06 if not fib else .86, title, transform=ax.transAxes, fontsize=14, weight='bold')
    ax.set_title(f'$SPX S&P 500 Large Cap Index   {z.index[-1]:%d-%b-%Y}', loc='left', fontsize=8); _save(fig, out, n)


def fig5(D, out):
    _cluster(D, out, 5, '1999-01-01', '2002-10-11', 'S&P 500 PEAKING PROCESS 1999-2000',
             [('2000-10-15', 1500, 'SLICE THROUGH MA CLUSTER', '#c0392b'), ('2001-01-15', 1460, 'SLOPE ROLLS OVER WITH PRICE BELOW', 'k'),
              ('2001-06-01', 1420, 'FULL BORE BEARISH', '#1e8449'), ('2000-11-01', 1235, 'REJECTED', '#c0392b'), ('2000-12-15', 1120, 'WHITE SPACE', 'k'),
              ('1999-10-01', 1080, 'PRICE HOVERS NEAR MA CLUSTER FOR OVER A\nYEAR (DISTRIBUTION, VULNERABILITY).', '#1f3a93'), ('1999-02-01', 1020, 'FULL BORE BULLISH', '#1e8449')])


def fig6(D, out):
    C = _wk(D['SPX']); lo = C.loc['2026-02':'2026-05'].min(); hi = C.loc['2026-03':].max()   # 주봉 종가
    _cluster(D, out, 6, '2023-11-24', None, 'S&P 500 SAME CHART TODAY', fib=(lo, hi))


def _ichi(C, H, L):
    mid = lambda n: (H.rolling(n).max() + L.rolling(n).min()) / 2
    return mid(9), mid(26), ((mid(9) + mid(26)) / 2).shift(26), mid(52).shift(26)


def _cloud(ax, C, H, L, a, b, freq):
    ten, kij, A, B = _ichi(C, H, L)
    ext = pd.date_range(C.index[-1], periods=27, freq=freq)[1:]   # 구름은 26칸 앞까지
    mid = lambda n: (H.rolling(n).max() + L.rolling(n).min()) / 2
    fA = ((mid(9) + mid(26)) / 2).iloc[-26:]; fB = mid(52).iloc[-26:]; fA.index = ext[:26]; fB.index = ext[:26]
    A2, B2 = pd.concat([A, fA]).loc[a:b], pd.concat([B, fB]).loc[a:b]
    ax.fill_between(A2.index, A2, B2, where=A2 >= B2, color='#9fd89f', alpha=.55, lw=0, interpolate=True)
    ax.fill_between(A2.index, A2, B2, where=A2 < B2, color='#f4a6a6', alpha=.55, lw=0, interpolate=True)
    lag = C.shift(-26).loc[a:b]
    ax.plot(ten.loc[a:b].index, ten.loc[a:b], color='#1f3a93', lw=.8); ax.plot(kij.loc[a:b].index, kij.loc[a:b], color='#8b0000', lw=.8)
    ax.plot(lag.index, lag, color='#2e8b57', lw=.7)
    return ten, kij, A2, B2


def fig7(D, out):
    g = _raw(D, 'SPYG').dropna(); b = _raw(D, 'BIL').reindex(g.index).ffill(); R = (g / b).dropna()
    C, H, L = _wk(R), _wk(R, 'max'), _wk(R, 'min'); a, e = '2021-05-01', C.index[-1] + pd.Timedelta(days=200)
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(11, 6), gridspec_kw={'height_ratios': [3, 1.1]}, sharex=True)
    ten, kij, A2, B2 = _cloud(ax, C, H, L, a, e, 'W-FRI'); z = C.loc[a:]
    for nm_, L_ in (('전환선', ten), ('기준선', kij), ('구름 위끝', pd.concat([A2, B2], axis=1).max(axis=1)), ('구름 아래끝', pd.concat([A2, B2], axis=1).min(axis=1))):
        _rec(7, 'SPYG:BIL 주봉', z, f'일목 {nm_}', L_.reindex(z.index), '{:.3f}')
    ax.plot(z.index, z, color='k', lw=1.1, label=f'SPYG:BIL (Weekly) {C.iloc[-1]:.3f}')
    ax.plot([], [], color='#2e8b57', label=f'ICHIMOKU(9,26,52) {ten.iloc[-1]:.3f}, {kij.iloc[-1]:.3f}, {A2.dropna().iloc[-1]:.3f}, {B2.dropna().iloc[-1]:.3f}')
    ax.yaxis.tick_right(); ax.legend(loc='upper left', fontsize=6); ax.text(.45, .9, 'LC GROWTH vs. 1-3 MONTH T-BILLS', transform=ax.transAxes, fontsize=13, weight='bold')
    ax.set_title(f'SPYG:BIL SPDR S&P 500 Growth ETF/SPDR Bloomberg 1-3 Month T-Bill ETF   {C.index[-1]:%d-%b-%Y}  (inverted BIL:SPYG = {1 / C.iloc[-1]:.3f})', loc='left', fontsize=8)
    s = _wk(D['SPX']).loc[a:]; bx.plot(s.index, s, color='k', lw=.9); bx.yaxis.tick_right(); bx.text(.005, .85, f'$SPX {s.iloc[-1]:.2f}', transform=bx.transAxes, fontsize=6.5)
    bx.set_xlim(pd.Timestamp(a), e); fig.tight_layout(h_pad=.2); _save(fig, out, 7)


def fig8(D, out):
    R = (_raw(D, 'IWF') / _raw(D, 'IWD')).dropna()
    C, H, L = (_real(getattr(R.resample('ME'), f)(), R.dropna()) for f in ('last', 'max', 'min'))
    a, e = '2014-01-01', '2029-06-30'
    fig, ax = plt.subplots(figsize=(11, 5.4)); ten, kij, A2, B2 = _cloud(ax, C, H, L, a, e, 'ME')
    z = slice(a, None); up = C >= C.shift(1)
    for m, col in ((up, 'k'), (~up, '#c0392b')):
        cc = C.loc[z][m.loc[z]]; _hlc(ax, cc, H.reindex(cc.index), L.reindex(cc.index), color=col, w=9)
    t1, t2 = L.loc['2015-01':'2016-12'].idxmin(), L.loc['2022-01':'2023-12'].idxmin(); k = (L[t2] - L[t1]) / (t2 - t1).days
    xs = pd.date_range(t1, e, freq='ME'); ax.plot(xs, L[t1] + k * (xs - t1).days, color='#1f3cd1', lw=2)
    cz = C.loc[z]
    for nm_, L_ in (('전환선', ten), ('기준선', kij), ('구름 위끝', pd.concat([A2, B2], axis=1).max(axis=1)), ('구름 아래끝', pd.concat([A2, B2], axis=1).min(axis=1))):
        _rec(8, 'IWF:IWD 월봉', cz, f'일목 {nm_}', L_.reindex(cz.index), '{:.3f}')
    _rec(8, 'IWF:IWD 월봉', cz, '2016 추세선', pd.Series(L[t1] + k * (cz.index - t1).days, index=cz.index), '{:.3f}')
    ax.annotate('BEAR MARKET ENDS', (t2, L[t2]), xytext=(pd.Timestamp('2024-06-01'), L[t2] * .82), fontsize=12, color='#1f3cd1', weight='bold',
                bbox=dict(fc='w', ec='#888'), arrowprops=dict(arrowstyle='-', color='#888'))
    ax.text(.03, .85, 'GROWTH vs. VALUE\nMONTHLY', transform=ax.transAxes, fontsize=14, color='#1f3cd1', weight='bold'); ax.yaxis.tick_right()
    ax.set_xlim(pd.Timestamp(a), pd.Timestamp(e))
    ax.set_title(f'IWF:IWD iShares Russell 1000 Growth ETF/iShares Russell 1000 Value ETF (Monthly) {C.iloc[-1]:.2f}   ICHIMOKU(9,26,52) '
                 f'{ten.iloc[-1]:.2f}, {kij.iloc[-1]:.2f}, {A2.dropna().iloc[-1]:.2f}, {B2.dropna().iloc[-1]:.2f}   {R.index[-1]:%d-%b-%Y}', loc='left', fontsize=8)
    _save(fig, out, 8)


MGK_MA = [(80, '#a93226', '-'), (90, '#a93226', ':'), (100, '#1e8449', '-'), (110, '#1e8449', ':'), (120, '#1c1f5c', '-'), (130, '#1c1f5c', ':')]


def fig9(D, out):
    c = D['MGK'].dropna(); C = _wk(c); hi_, lo_ = D.get('MGK_HIGH', c).fillna(c), D.get('MGK_LOW', c).fillna(c); T = RS.ctm(D, 'MGK'); a = '2017-01-01'
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(11, 6.2), gridspec_kw={'height_ratios': [3.3, 1]}, sharex=True)
    z = C.loc[a:]; ax.plot(z.index, z, color='#1c1f5c', lw=1, label=f'MGK (Weekly) {C.iloc[-1]:.2f}')
    for p, col, ls in MGK_MA:
        m = C.rolling(p).mean().loc[a:]; ax.plot(m.index, m, color=col, lw=.9, ls=ls, label=f'MA({p}) {m.iloc[-1]:.2f}')
        _rec(9, 'MGK 주봉', z, f'{p}주선', C.rolling(p).mean().loc[a:])
    t1, t2 = C.loc['2022-06':'2023-03'].idxmin(), C.loc['2025-03':'2025-05'].idxmin(); k = (C[t2] - C[t1]) / (t2 - t1).days
    xs = pd.date_range(t1, z.index[-1] + pd.Timedelta(days=60), freq='W-FRI'); ax.plot(xs, C[t1] + k * (xs - t1).days, color='#1f3cd1', lw=2.2)
    _rec(9, 'MGK 주봉', z, '2022~2025 저점 추세선', pd.Series(C[t1] + k * (z.index - t1).days, index=z.index).where(z.index >= t1))
    for (l0, l1), (h0, h1), x0 in ((('2020-02', '2020-04'), ('2021-06', '2022-01'), '2020-03-01'), (('2022-09', '2023-01'), ('2024-06', '2025-03'), '2022-12-01'),
                                   (('2025-03', '2025-05'), ('2025-06', None), '2025-04-01')):
        lo, hi = C.loc[l0:l1].min(), C.loc[h0:h1].max()   # 원본 피보는 주봉 종가
        for r in (0, .382, .5, .618, 1):
            y = hi - (hi - lo) * r; ax.hlines(y, pd.Timestamp(x0), pd.Timestamp(x0) + pd.Timedelta(days=640), color='#1c1f5c', lw=.8)
            if x0 == '2025-04-01':
                _rec(9, 'MGK 주봉', z, f'피보(2025) {r * 100:.1f}%', y)
            ax.text(pd.Timestamp(x0) + pd.Timedelta(days=640), y, f'{r * 100:.1f}%: {y:.2f}', fontsize=5.5, ha='right', va='bottom', color='#444')
    ax.set_yscale('log'); ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}')); ax.yaxis.set_minor_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v:.0f}' if v in (15, 25, 35, 45, 55, 65, 75, 85) else '')); ax.yaxis.tick_right()
    ax.legend(loc='upper left', fontsize=6, framealpha=.9); ax.text(.1, .62, 'MGK (HEAVY MAG 7)\nWEEKLY 2017-2026', transform=ax.transAxes, fontsize=13, weight='bold')
    ax.set_title(f'MGK Vanguard Mega Cap Growth ETF   {C.index[-1]:%d-%b-%Y}', loc='left', fontsize=8)
    for y in (30, 50):
        _rec(9, 'CTM-MGK', T.loc[a:], f'CTM {y}', y)
    _ctm_panel(bx, T, a, None, 'CTM-MGK'); bx.set_xlim(pd.Timestamp(a), z.index[-1] + pd.Timedelta(days=60)); fig.tight_layout(h_pad=.2); _save(fig, out, 9)


FIGS = [fig1, fig2, fig3, fig4, fig5, fig6, fig7, fig8, fig9]


def draw(D, out, only=None):
    """그림 9개를 그린다. 하나가 실패해도 나머지는 그린다. 돌려줌: {번호: '그림'|'실패: …'}"""
    os.makedirs(out, exist_ok=True); D = D.sort_index(); res = {}; ROWS.clear()
    for i, f in enumerate(FIGS, 1):
        if only and i not in only: continue
        try:
            f(D, out); res[i] = '그림'
        except Exception as e:   # noqa: BLE001
            res[i] = f'실패: {str(e)[:120]}'
    pd.DataFrame(ROWS).to_csv(f'{out}/turn_lines.csv', index=False, encoding='utf-8-sig')
    return res


if __name__ == '__main__':
    import sys
    D = pd.read_csv(sys.argv[1], index_col=0, parse_dates=True)
    print(draw(D, sys.argv[2] if len(sys.argv) > 2 else '.', [int(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 else None))
