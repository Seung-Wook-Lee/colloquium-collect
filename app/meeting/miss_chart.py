"""5 기술적 분석 · 미스 차트 (11/26 의장): SPYM·QQQM·TIGER 200 세 개만 보조지표로 설명한다. 종목 추천은 하지 않는다.

자료: 10년치 데이터베이스(가격10년_시가·고가·저가·종가·거래량) 하나만 읽는다(px_store.frame).
지표 계산은 07시 닉스 팀과 같은 함수(collect/nyx.py: 지지·저항, 볼린저, 일목, MACD 오실레이터, 봉 모양)를 쓰고,
아래 것만 더한다. 숫자 문턱은 rules.yaml '미스 차트 지표'.

  ① 일봉 셋업(10/29 의장 미스 차트 정의): RSI(14) 과매도, 50일 이격도 100 아래, 볼린저 %B 0 이하(하단 터치), MACD 하락 막대 줄어듦
  ② 주봉 시점: 주봉 MACD 오실레이터 기울기가 양(11/26 의장 "그냥 양으로 바뀌었으면" — 셋업 뒤 기간 제한 없음)
  ③ 큰 추세: 월봉 5개월선 위·아래
  볼린저 보강: %B, 밴드폭 6개월 백분위(낮으면 스퀴즈, Bollinger 2001), 하단 밖→안 복귀, 밴드 타기(상단·하단 연속)
  일목 보강: 구름 위치·색(양운·음운)·두께, 전환선·기준선, 후행스팬, 삼역호전·삼역역전(세 조건 모두)
  캔들(Nison 1991, TA-Lib 판정): 일봉 최근 5봉·주봉 최근 2봉에 나온 모양
  지지선·저항선: 일봉·주봉 둘 다(11/26 의장)
주봉 패턴(이중 바닥 등)·넥라인은 쓰지 않는다(11/9 의장)."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(ROOT, 'collect'), os.path.join(ROOT, 'collect', 'data')]
import nyx as NX  # noqa: E402
import px_store as PS  # noqa: E402

# 캔들 이름(TA-Lib 함수, 한글 이름). 값 +100 = 상승형, -100 = 하락형. 이름이 하나뿐인 모양은 부호로 상승·하락을 붙인다.
CANDLES = [
    ('CDLENGULFING', '장악형'), ('CDLHARAMI', '잉태형'), ('CDLHARAMICROSS', '십자 잉태형'),
    ('CDLHAMMER', '망치형'), ('CDLINVERTEDHAMMER', '역망치형'), ('CDLHANGINGMAN', '교수형'), ('CDLSHOOTINGSTAR', '유성형'),
    ('CDLMORNINGSTAR', '샛별형'), ('CDLEVENINGSTAR', '석별형'), ('CDLPIERCING', '관통형'), ('CDLDARKCLOUDCOVER', '먹구름형'),
    ('CDL3WHITESOLDIERS', '적삼병'), ('CDL3BLACKCROWS', '흑삼병'), ('CDLDOJI', '도지'),
]
SIDED = {'장악형', '잉태형', '십자 잉태형'}   # 상승·하락 둘 다 있는 모양


def ohlcv(d, tk):
    """데이터베이스에서 한 티커 일봉(시가·고가·저가·종가·거래량)."""
    cols = {}
    for k, nm in (('Open', '시가'), ('High', '고가'), ('Low', '저가'), ('Close', '종가'), ('Volume', '거래량')):
        f = PS.frame(d, k)
        if tk not in f:
            return pd.DataFrame()
        cols[nm] = pd.to_numeric(f[tk], errors='coerce')
    x = pd.DataFrame(cols).dropna(subset=['종가'])
    x['시가'] = x['시가'].fillna(x['종가'])
    x['고가'] = x[['고가', '시가', '종가']].max(axis=1)
    x['저가'] = x[['저가', '시가', '종가']].min(axis=1)
    x['거래량'] = x['거래량'].fillna(0)
    return x


def candles(df, last):
    """최근 last봉 안에 나온 캔들 모양(가장 최근 것부터). [(날짜, 이름)]"""
    import talib
    O, H, L, C = (df[k].astype(float).values for k in ('시가', '고가', '저가', '종가'))
    out = []
    for fn, nm in CANDLES:
        v = getattr(talib, fn)(O, H, L, C)
        for i in range(len(v) - 1, max(len(v) - 1 - last, -1), -1):
            if v[i]:
                side = ('상승 ' if v[i] > 0 else '하락 ') if nm in SIDED else ''
                out.append((df.index[i], side + nm))
    return sorted(out, key=lambda x: x[0], reverse=True)


def _pct_rank(s, look):
    t = s.dropna().iloc[-look:]
    return float((t <= t.iloc[-1]).mean() * 100) if len(t) > 20 else np.nan


def one(df, R):
    """한 ETF의 지표 한 줄(dict)."""
    row = NX.analyze(df)
    if not row:
        return {}
    c, h, l = df['종가'], df['고가'], df['저가']
    # ① 일봉 셋업
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    hist = macd - macd.ewm(span=9, adjust=False).mean()
    row['일_MACD막대_줄어듦'] = bool(hist.iloc[-1] < 0 and hist.iloc[-1] > hist.iloc[-2])
    row['일_볼린저_터치'] = bool(df['저가'].iloc[-1] <= row['일_볼린저_하단'])
    setup = {
        f"RSI {R['RSI_과매도']} 이하": row['일_RSI'] <= R['RSI_과매도'],
        '50일 이격도 100 아래': row['일_50일_이격도'] < 100,
        '볼린저 하단 터치': row['일_볼린저_%B'] <= 0 or row['일_볼린저_터치'],
        'MACD 하락 막대 줄어듦': row['일_MACD막대_줄어듦'],
    }
    row['셋업'] = setup
    # ② 주봉 MACD 오실레이터 기울기
    mo1, mo0 = row.get('주_MACD오실레이터'), row.get('주_MACD오실레이터_1봉전')
    row['주봉_기울기양'] = bool(mo1 is not None and mo0 is not None and mo1 > mo0)
    row['주봉_이번주전환'] = bool(row['주봉_기울기양'] and mo0 <= row.get('주_MACD오실레이터_2봉전', mo0))
    # ③ 월봉 5개월선
    row['월_5개월선_위'] = bool(c.iloc[-1] > row['월_5개월선'])
    # 볼린저 보강
    ma20, sd = c.rolling(20).mean(), c.rolling(20).std(ddof=0)
    bw = (4 * sd / ma20) * 100
    row['일_밴드폭_백분위'] = _pct_rank(bw, R['밴드폭_기간'])
    dn = ma20 - 2 * sd
    row['일_하단복귀'] = bool(c.iloc[-2] < dn.iloc[-2] and c.iloc[-1] >= dn.iloc[-1])
    # 일목 보강(일봉)
    tk, kj, sa, sb = NX.ichimoku(h, l, c)
    row['일_일목_구름색'] = '양운' if sa.iloc[-1] >= sb.iloc[-1] else '음운'
    row['일_일목_구름두께(%)'] = round(abs(sa.iloc[-1] - sb.iloc[-1]) / c.iloc[-1] * 100, 1)
    cond = [row['일_일목_전환기준'] == '전환>기준', str(row['일_일목_후행스팬']).endswith('위'), row['일_일목_구름위치'] == '위']
    condd = [row['일_일목_전환기준'] == '전환<기준', str(row['일_일목_후행스팬']).endswith('아래'), row['일_일목_구름위치'] == '아래']
    row['일_삼역'] = '삼역호전' if all(cond) else ('삼역역전' if all(condd) else f'호전 조건 {sum(cond)}/3')
    # 지지·저항(일봉·주봉, 그림과 같은 띠)
    for tf, x in (('일', df), ('주', NX.to_week(df))):
        sup, res = sr_bands(x, tf)
        row[f'{tf}_지지띠'], row[f'{tf}_저항띠'] = sup, res
    # 캔들
    row['일_캔들'] = candles(df, R['캔들_일봉'])
    row['주_캔들'] = candles(NX.to_week(df), R['캔들_주봉'])
    return row


def run(d, R):
    """rules.yaml '미스 차트 지표' R → {이름: 한 줄 dict}. 자료 없는 ETF는 빈 dict."""
    return {nm: (one(x, R) if len(x := ohlcv(d, tk)) >= 300 else {}) for nm, tk in R['대상']}


def band_txt(lst, px):
    """가장 가까운 띠 하나: '가격~가격(거리%)'. 1000 넘는 가격(원화)은 소수점 없이."""
    if not lst:
        return '없음'
    lo, hi, _ = lst[0]
    fmt = (lambda v: f'{v:,.0f}') if px >= 1000 else (lambda v: f'{v:,.2f}')
    mid = hi if hi < px else lo
    rng = fmt(lo) if fmt(lo) == fmt(hi) else f"{fmt(lo)}~{fmt(hi)}"
    return f"{rng}({(mid / px - 1) * 100:+.1f}%)"


def _f(v, d=1):
    return '-' if v is None or (isinstance(v, float) and not np.isfinite(v)) else f'{v:,.{d}f}'


def explain(nm, r, R):
    """코드가 만드는 한 줄 설명(문장 틀 고정, 숫자만 바뀜)."""
    if not r:
        return '데이터베이스에 자료 없음'
    n_set = sum(r['셋업'].values())
    on = [k for k, v in r['셋업'].items() if v]
    s1 = f"일봉 셋업 4개 중 {n_set}개 신호 나옴" + (f"({', '.join(on)})" if on else '')
    s2 = ('주봉 MACD 오실레이터 기울기 양' + ('(이번 주 전환)' if r['주봉_이번주전환'] else '')) if r['주봉_기울기양'] else '주봉 MACD 오실레이터 기울기 음 — 전환 신호 나오지 않음'
    s3 = '월봉 5개월선 위' if r['월_5개월선_위'] else '월봉 5개월선 아래'
    return f"{s1} · {s2} · {s3} · 일목 {r['일_삼역']}"


def table(res):
    """세 ETF 표: 줄 = 지표, 칸 = ETF(세 개뿐이라 옆으로 나란히)."""
    names = ['종가', '52주 고점 대비(%)', '일봉 RSI(14)', '50일 이격도', '볼린저 %B', '밴드폭 6개월 백분위', '일봉 MACD 막대', '주봉 MACD 오실레이터',
             '월봉 5개월선', '일목 구름(위치·색·두께)', '일목 삼역', '일봉 지지', '일봉 저항', '주봉 지지', '주봉 저항', '최근 캔들(일봉)', '최근 캔들(주봉)']
    col = {}
    for nm, r in res.items():
        if not r:
            col[nm] = ['자료 없음'] + [''] * (len(names) - 1); continue
        sr = lambda p, k: band_txt(r[f'{p[0]}_{k}띠'], r['종가'])
        cd = lambda xs: ', '.join(f"{t:%m/%d} {n}" for t, n in xs[:3]) or '없음'
        col[nm] = [_f(r['종가'], 2), _f(r['52주고점대비(%)']), _f(r['일_RSI']), _f(r['일_50일_이격도']), _f(r['일_볼린저_%B'], 2),
                   _f(r['일_밴드폭_백분위'], 0), '하락 막대 줄어듦' if r['일_MACD막대_줄어듦'] else '-',
                   '기울기 양' if r['주봉_기울기양'] else '기울기 음', '위' if r['월_5개월선_위'] else '아래',
                   f"{r['일_일목_구름위치']}·{r['일_일목_구름색']}·{_f(r['일_일목_구름두께(%)'])}%", r['일_삼역'],
                   sr('일_', '지지'), sr('일_', '저항'), sr('주_', '지지'), sr('주_', '저항'), cd(r['일_캔들']), cd(r['주_캔들'])]
    cols = ['지표'] + list(col)
    rows = [[k] + [col[nm][i] for nm in col] for i, k in enumerate(names)]
    return cols, rows


# ---------------------------------------------------------------- 그림(11/26 의장 "그래프로, 선도 지지선·저항선도, 큼지막하게")
def sr_bands(df, tf):
    """지지·저항 띠(닉스 팀과 같은 규칙): 지금 가격 아래 지지 2개, 위 저항 2개. [(lo, hi, 터치)]"""
    cfg = NX.CFG[tf]
    sub = df.iloc[-cfg['look']:]
    bs = NX.bands(NX.pivots(sub, cfg['n']), cfg['tol'])
    px = df['종가'].iloc[-1]
    sup = sorted([b for b in bs if b['hi'] < px], key=lambda b: -b['hi'])[:2]
    res = sorted([b for b in bs if b['lo'] > px], key=lambda b: b['lo'])[:2]
    return [(b['lo'], b['hi'], b['touch']) for b in sup], [(b['lo'], b['hi'], b['touch']) for b in res]


def _font():
    import matplotlib
    from matplotlib import font_manager as fm
    for nm in ('NanumGothic', 'Noto Sans CJK KR', 'Noto Sans KR', 'Malgun Gothic', 'AppleGothic'):
        if any(f.name == nm for f in fm.fontManager.ttflist):
            matplotlib.rcParams['font.family'] = nm
            break
    matplotlib.rcParams['axes.unicode_minus'] = False


def draw(df, r, name, path, R):
    """ETF 한 장: ① 일봉 캔들 + 20·50·200일선 + 볼린저 + 일목 구름 + 월봉 5개월선 + 일봉·주봉 지지·저항 + 캔들 모양
    ② 거래량 ③ RSI(14) ④ 일봉 MACD 막대 ⑤ 주봉 MACD 오실레이터. 한국식 색(오르면 빨강, 내리면 파랑)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    _font()
    UP, DN = '#d62728', '#1f5fbf'
    c, h, l = df['종가'], df['고가'], df['저가']
    ma = {k: c.rolling(k).mean() for k in (20, 50, 200)}
    m20, sd = c.rolling(20).mean(), c.rolling(20).std(ddof=0)
    tk, kj, sa, sb = NX.ichimoku(h, l, c)
    mon = c.groupby(c.index.to_period('M')).last()
    m5 = mon.rolling(5).mean()
    m5d = pd.Series(m5.reindex(c.index.to_period('M')).values, c.index)
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    hist = macd - macd.ewm(span=9, adjust=False).mean()
    w = NX.to_week(df)
    wo = NX.macd_osc(w['종가'])
    rsi = NX.rsi(c)
    n = R.get('그림_일수', 190)
    D = df.iloc[-n:]
    x0 = D.index[0]
    sl = lambda s: s[s.index >= x0]
    fig, ax = plt.subplots(5, 1, figsize=(16, 15), sharex=True, gridspec_kw={'height_ratios': [6, 1.1, 1.6, 1.6, 1.6], 'hspace': 0.06})
    a = ax[0]
    # 일목 구름
    A, B = sl(sa), sl(sb)
    a.fill_between(A.index, A, B, where=A >= B, color='#f4b6b6', alpha=.35, lw=0, label='일목 구름(양운)')
    a.fill_between(A.index, A, B, where=A < B, color='#b6c8f4', alpha=.35, lw=0, label='일목 구름(음운)')
    a.plot(sl(tk).index, sl(tk), color='#9467bd', lw=.8, label='전환선(9)')
    a.plot(sl(kj).index, sl(kj), color='#8c564b', lw=.8, label='기준선(26)')
    # 볼린저
    up, dn = sl(m20 + 2 * sd), sl(m20 - 2 * sd)
    a.plot(up.index, up, color='#7f7f7f', lw=.8, ls='--', label='볼린저 상단·하단(20, 2)')
    a.plot(dn.index, dn, color='#7f7f7f', lw=.8, ls='--')
    a.fill_between(up.index, dn, up, color='#cccccc', alpha=.12, lw=0)
    # 이동평균·월봉 5개월선
    for k, col in ((20, '#ff7f0e'), (50, '#2ca02c'), (200, '#111111')):
        a.plot(sl(ma[k]).index, sl(ma[k]), color=col, lw=1.4, label=f'{k}일선')
    a.step(sl(m5d).index, sl(m5d), where='post', color='#e377c2', lw=1.6, label='월봉 5개월선')
    # 캔들
    wid = 0.6
    for t, o_, h_, l_, c_ in zip(D.index, D['시가'], D['고가'], D['저가'], D['종가']):
        col = UP if c_ >= o_ else DN
        xd = matplotlib.dates.date2num(t)
        a.vlines(xd, l_, h_, color=col, lw=.8)
        a.add_patch(Rectangle((xd - wid / 2, min(o_, c_)), wid, max(abs(c_ - o_), 1e-9), color=col))
    # 지지·저항(일봉 = 가는 띠·점선, 주봉 = 굵은 띠·실선). 지금 가격에서 15% 넘게 먼 띠는 그리지 않는다.
    px = c.iloc[-1]
    xe = D.index[-1] + pd.Timedelta(days=4)
    ylo, yhi = D['저가'].min(), D['고가'].max()
    for tf, alpha, lw in (('일', .16, 1.0), ('주', .28, 2.4)):
        sup, res = r.get(f'{tf}_지지띠', []), r.get(f'{tf}_저항띠', [])
        for kind, lst, col in (('지지', sup, '#1b8a2e'), ('저항', res, '#c8372d')):
            for i, (lo, hi, tch) in enumerate(lst, 1):
                if abs((lo + hi) / 2 / px - 1) > 0.15:
                    continue
                ylo, yhi = min(ylo, lo), max(yhi, hi)
                a.axhspan(lo, hi if hi > lo else lo * 1.001, color=col, alpha=alpha, lw=0)
                a.axhline((lo + hi) / 2, color=col, lw=lw, ls='-' if tf == '주' else ':')
                a.text(xe, (lo + hi) / 2, f" {tf}봉 {kind}{i}  {band_txt([(lo, hi, tch)], px).split('(')[0]} (닿은 횟수 {tch})", fontsize=10, color=col, va='center', ha='left',
                       bbox=dict(facecolor='white', edgecolor='none', alpha=.8, pad=1))
    # 캔들 모양(최근 10봉, 같은 날은 한 줄로)
    marks = {}
    for t, nm in candles(df, 10):
        marks.setdefault(t, []).append(nm)
    for j, (t, nms) in enumerate(sorted(marks.items())):
        bear = sum(nm.startswith('하락') or nm in ('교수형', '유성형', '석별형', '먹구름형', '흑삼병') for nm in nms)
        bull = bear * 2 < len(nms) or (bear == 0)
        col = UP if bull else DN
        a.annotate('\n'.join(nms), (t, df.loc[t, '저가'] if bull else df.loc[t, '고가']), xytext=(0, (-30 - 14 * (j % 2)) if bull else (30 + 14 * (j % 2))),
                   textcoords='offset points', ha='center', va='top' if bull else 'bottom', fontsize=9, color=col,
                   arrowprops=dict(arrowstyle='->', color=col, lw=.8), bbox=dict(facecolor='white', edgecolor=col, alpha=.85, pad=1.5, lw=.5))
    a.set_xlim(x0 - pd.Timedelta(days=2), D.index[-1] + pd.Timedelta(days=75))
    a.set_ylim(ylo * 0.97, yhi * 1.03)
    a.legend(loc='upper left', fontsize=9, ncol=4, framealpha=.9)
    a.set_title(f"{name} 일봉  ·  {D.index[-1]:%Y-%m-%d} 종가 {c.iloc[-1]:,.2f}  ·  52주 고점 대비 {r.get('52주고점대비(%)', float('nan')):+.1f}%\n{explain(name, r, R)}",
                loc='left', fontsize=13)
    a.grid(color='#eeeeee', lw=.6)
    # 거래량
    ax[1].bar(D.index, D['거래량'], color=[UP if c_ >= o_ else DN for o_, c_ in zip(D['시가'], D['종가'])], width=.6)
    ax[1].plot(D.index, D['거래량'].rolling(20).mean(), color='#555', lw=1, label='20일 평균')
    ax[1].set_ylabel('거래량', fontsize=10); ax[1].legend(loc='upper left', fontsize=8)
    ax[1].yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f'{v / 1e6:,.1f}백만' if v >= 1e6 else f'{v / 1e3:,.0f}천'))
    # RSI
    ax[2].plot(sl(rsi).index, sl(rsi), color='#333', lw=1.3)
    for v, col in ((70, UP), (30, DN)):
        ax[2].axhline(v, color=col, lw=.8, ls='--')
    ax[2].fill_between(sl(rsi).index, 30, sl(rsi), where=sl(rsi) < 30, color=DN, alpha=.25)
    ax[2].fill_between(sl(rsi).index, 70, sl(rsi), where=sl(rsi) > 70, color=UP, alpha=.25)
    ax[2].set_ylim(0, 100); ax[2].set_ylabel(f'RSI(14) {rsi.iloc[-1]:.0f}', fontsize=10)
    # 일봉 MACD 막대
    hh = sl(hist)
    cols = [(UP if v >= 0 else DN) if i == 0 or abs(v) >= abs(hh.iloc[i - 1]) else ('#f4a6a6' if v >= 0 else '#a6c0f4') for i, v in enumerate(hh)]
    ax[3].bar(hh.index, hh, color=cols, width=.6); ax[3].axhline(0, color='#999', lw=.8)
    ax[3].set_ylabel('일봉 MACD 막대\n(옅은 색 = 줄어듦)', fontsize=10)
    # 주봉 MACD 오실레이터
    ww = wo[wo.index >= x0]
    wc = [(UP if v >= 0 else DN) if i == 0 or v >= ww.iloc[i - 1] else ('#f4a6a6' if v >= 0 else '#a6c0f4') for i, v in enumerate(ww)]
    ax[4].bar(ww.index, ww, color=wc, width=4); ax[4].axhline(0, color='#999', lw=.8)
    ax[4].set_ylabel('주봉 MACD 오실레이터\n(진한 색 = 기울기 양)', fontsize=10)
    for x in ax:
        x.tick_params(labelsize=10)
        x.grid(color='#eeeeee', lw=.6)
    fig.savefig(path, dpi=110, bbox_inches='tight')
    plt.close(fig)


def draw_all(d, R, out_dir):
    """세 ETF 그림 → out_dir/미스차트_1.png …(rules.yaml 대상 순서). 반환: [(번호, 이름, 파일)]"""
    res = []
    for i, (nm, tk) in enumerate(R['대상'], 1):
        x = ohlcv(d, tk)
        if len(x) < 300:
            continue
        r = one(x, R)
        p = os.path.join(out_dir, f'미스차트_{i}.png')
        draw(x, r, nm, p, R)
        res.append((i, nm, p))
    return res
