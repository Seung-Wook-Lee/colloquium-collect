"""11/26 의장(에이피알): "난 실적을 믿었어. 특히 수출. 지난 실적 발표 때 비용 운운하면서 빠졌는데 그건 일회성이라고 봤지.
한국 기업가들은 어떻게든 (이익을) 낮출 거거든" → 이 판단을 우리 10년치 데이터베이스로 검정한다(파일로 남기지 않고 표만 찍음).

사건 = 분기 실적 공시(공시일). 같은 분기 1년 전과 비교:
  A 매출↑ 이익↓ : 매출 +10% 이상인데 영업이익은 줄어든 분기(비용 때문에 이익만 꺾임 — 의장이 본 경우)
  B 매출↓ 이익↓ : 매출도 이익도 줄어든 분기(장사 자체가 나빠짐)
  C 매출↑ 이익↑ : 둘 다 늘어남
주가 반응 = 공시일 전날 → 10거래일 뒤 수익. '빠짐' = −10% 이하.
뒤 수익 = 10거래일 뒤부터 13주(63거래일)·26주(126거래일). 다음 분기 이익 회복 = 다음 분기 영업이익이 1년 전보다 늘었나.
입력 폴더 d: 가격10년_종가.csv.gz, 가격10년_DART재무.csv.gz, 가격10년_SEC재무.csv.gz(있으면)."""
import os
import sys

import numpy as np
import pandas as pd

H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(H)), 'collect', 'data'))
import px_store as PS  # noqa: E402

REV_UP, DROP, REACT, F13, F26 = 10.0, -10.0, 10, 63, 126


def events(F, P):
    F = F[F['항목'].isin(['매출', '영업이익'])].copy()
    F['분기말'] = pd.to_datetime(F['분기말']); F['공시일'] = pd.to_datetime(F['공시일']); F['값'] = pd.to_numeric(F['값'], errors='coerce')
    W = F.pivot_table(index=['ticker', '분기말'], columns='항목', values='값', aggfunc='first')
    D = F.groupby(['ticker', '분기말'])['공시일'].min()
    W = W.join(D).reset_index().dropna(subset=['매출', '영업이익', '공시일'])
    rows = []
    for t, g in W.groupby('ticker'):
        if t not in P:
            continue
        s = P[t].dropna()
        g = g.set_index('분기말').sort_index()
        for q, r in g.iterrows():
            ly = g.loc[(g.index >= q - pd.Timedelta(days=380)) & (g.index <= q - pd.Timedelta(days=350))]
            if not len(ly) or ly['매출'].iloc[0] <= 0:
                continue
            rev = (r['매출'] / ly['매출'].iloc[0] - 1) * 100
            opd = r['영업이익'] - ly['영업이익'].iloc[0]
            i = s.index.searchsorted(r['공시일'])
            if i < 1 or i + REACT >= len(s):
                continue
            p0, p1 = s.iloc[i - 1], s.iloc[i + REACT]
            nxt = g.loc[g.index > q + pd.Timedelta(days=60)].head(1)
            rec = np.nan
            if len(nxt):
                q2 = nxt.index[0]
                ly2 = g.loc[(g.index >= q2 - pd.Timedelta(days=380)) & (g.index <= q2 - pd.Timedelta(days=350))]
                if len(ly2):
                    rec = float(nxt['영업이익'].iloc[0] > ly2['영업이익'].iloc[0])
            rows.append(dict(ticker=t, 분기말=q.date(), 공시일=r['공시일'].date(), 매출증가=round(rev, 1), 이익증감=opd,
                             반응=(p1 / p0 - 1) * 100,
                             뒤13주=(s.iloc[i + REACT + F13] / p1 - 1) * 100 if i + REACT + F13 < len(s) else np.nan,
                             뒤26주=(s.iloc[i + REACT + F26] / p1 - 1) * 100 if i + REACT + F26 < len(s) else np.nan,
                             다음분기회복=rec))
    E = pd.DataFrame(rows)
    E['갈래'] = np.select([(E.매출증가 >= REV_UP) & (E.이익증감 < 0), (E.매출증가 < 0) & (E.이익증감 < 0), (E.매출증가 >= 0) & (E.이익증감 >= 0)],
                        ['A 매출↑ 이익↓', 'B 매출↓ 이익↓', 'C 매출↑ 이익↑'], '그 밖')
    return E


def table(E, mk):
    out = [f'\n### {mk} (사건 {len(E)}건, 종목 {E.ticker.nunique()}개)', '| 경우 | 건수 | 13주 뒤 중앙 | 13주 오른 확률 | 26주 뒤 중앙 | 26주 오른 확률 | 다음 분기 이익 회복 |', '|---|---|---|---|---|---|---|']
    def line(nm, x):
        y13, y26 = x['뒤13주'].dropna(), x['뒤26주'].dropna()
        out.append(f"| {nm} | {len(x)} | {y13.median():+.1f}% | {(y13 > 0).mean() * 100:.0f}% | {y26.median():+.1f}% | {(y26 > 0).mean() * 100:.0f}% | "
                   f"{x['다음분기회복'].mean() * 100:.0f}% |" if len(x) else f'| {nm} | 0 | | | | | |')
    line('모든 실적 발표', E)
    line('발표 뒤 −10% 이상 빠짐(전부)', E[E.반응 <= DROP])
    for k in ('A 매출↑ 이익↓', 'B 매출↓ 이익↓', 'C 매출↑ 이익↑'):
        line(f'{k} + 빠짐', E[(E.갈래 == k) & (E.반응 <= DROP)])
    line('A 매출↑ 이익↓ (빠지든 말든)', E[E.갈래 == 'A 매출↑ 이익↓'])
    print('\n'.join(out))


def main(d):
    P = PS.frame(d, 'Close')
    for k, mk in (('DART재무', '한국'), ('SEC재무', '미국')):
        F = PS.table(d, k, dtype={'ticker': str})
        if not len(F):
            print(f'{mk}: {k} 칸 없음'); continue
        E = events(F, P)
        table(E, mk)
        if mk == '한국':
            a = E[E.ticker == '278470.KS'].tail(8)
            print('\n### 에이피알 최근 실적 발표\n' + a[['분기말', '공시일', '매출증가', '이익증감', '반응', '뒤13주', '갈래', '다음분기회복']].round(1).to_string(index=False))
    s = P.get('278470.KS')
    if s is not None:
        s = s.dropna()
        print(f"\n에이피알 종가: 마지막 {s.index[-1].date()} {s.iloc[-1]:,.0f}원, 8/31 이후 최저 {s.loc['2026-08-31':].min():,.0f}원({s.loc['2026-08-31':].idxmin().date()}), "
              f"최저 대비 {(s.iloc[-1] / s.loc['2026-08-31':].min() - 1) * 100:+.1f}%")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
