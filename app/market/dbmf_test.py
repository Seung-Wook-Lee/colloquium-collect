"""DBMF 검증 (11/23 의장: "DBMF의 의미, 정확도, 추가했을 경우 블록의 정확도 상승 여부 등을 종합해서 보고해. 모두 코딩으로.")

DBMF(iMGP DBi Managed Futures ETF)는 대형 CTA들의 최근 60일 성과를 따라 선물(주식·채권·통화·원자재)을 사고판다.
그래서 DBMF의 주식 노출 = CTA들의 주식 포지션 추정치로 쓸 수 있다.

계산
 ① 일별 DBMF 주식 노출 추정: DBMF 일수익률을 SPY·EFA·EEM·IEF·UUP·GLD·USO에 60일 회귀 → SPY+EFA+EEM 계수 합
 ② 정답 맞춰 보기: SEC N-PORT(분기 보유 내역, 시리즈 S000072813)의 주식 선물 명목금액 ÷ 순자산과 ① 비교(상관)
 ③ 우리 B06 CTA σ(collect/flowpos.cta_sigma)와 상관
 ④ 신호 단독 실력: 63일 뒤 S&P 수익과 순위상관(IC) — 전체 / 52주 고점 −10% 아래 날만, 전반·후반
 ⑤ B06 맞대기: B06 기회 공식 합(CTA ≤ −4, 변동성 목표 < 0.6, JPM 추세 신호 전환)과 DBMF를 더한 합의 IC, 전반·후반 둘 다 오르는지
 ⑥ 사건 검정: DBMF 주식 노출이 하위 10%에 처음 들어간 날(63일 재무장) vs 같은 낙폭의 아무 날
결과: /mnt/project-files/유니버스/start/dbmf/ (csv + 요약 md)
"""
import re
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path[:0] = [str(Path(__file__).resolve().parent)]
OUT = Path('/mnt/project-files/유니버스/start/dbmf/')
UA = {'User-Agent': 'research-client research@example.com'}
EQ_WORDS = re.compile(r'S\+P|S&P|SP 500|E-MINI|EMINI|NASDAQ|RUSSELL|MSCI|EAFE|EMERG|NIKKEI|EURO STOXX|FTSE|DAX|TOPIX', re.I)
H = 63


def nport():
    """SEC N-PORT 분기 보유 내역 → 주식 선물 명목 ÷ 순자산."""
    u = 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=S000072813&type=NPORT-P&count=40&output=atom'
    t = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode()
    rows = []
    for href in re.findall(r'<filing-href>(.*?)</filing-href>', t):
        x = href.replace('-index.htm', '').rsplit('/', 1)[0] + '/primary_doc.xml'
        try:
            d = urllib.request.urlopen(urllib.request.Request(x, headers=UA), timeout=30).read().decode()
        except Exception as e:   # noqa: BLE001
            print('[N-PORT 실패]', x, e)
            continue
        if 'S000072813' not in d:
            continue
        per = re.search(r'<repPdDate>(.*?)</repPdDate>', d).group(1)
        na = float(re.search(r'<netAssets>(.*?)</netAssets>', d).group(1))
        eq = 0.0
        for blk in re.findall(r'<invstOrSec>(.*?)</invstOrSec>', d, re.S):
            nm = ' '.join(re.findall(r'<(?:name|title)>(.*?)</(?:name|title)>', blk))
            if not EQ_WORDS.search(nm) or 'TREAS' in nm.upper():
                continue
            notl = re.search(r'<notionalAmt>(.*?)</notionalAmt>', blk)
            if not notl:
                continue
            v = abs(float(notl.group(1)))
            short = re.search(r'<payOffProf>Short', blk, re.I)
            eq += -v if short else v
        rows.append({'기준일': pd.Timestamp(per), '순자산': na, '주식명목': eq, 'N-PORT 주식노출': eq / na})
    return pd.DataFrame(rows).sort_values('기준일').drop_duplicates('기준일')


def load():
    import yfinance as yf
    t = ['DBMF', 'SPY', 'EFA', 'EEM', 'IEF', 'UUP', 'GLD', 'USO', '^GSPC', '^NDX', '^RUT']
    return yf.download(t, start='2005-01-01', auto_adjust=True, progress=False)['Close']


def dbmf_beta(P, win=60):
    X = ['SPY', 'EFA', 'EEM', 'IEF', 'UUP', 'GLD', 'USO']
    R = P[['DBMF'] + X].pct_change().dropna()
    out = {}
    for i in range(win, len(R) + 1):
        w = R.iloc[i - win:i]
        A = np.column_stack([np.ones(win), w[X].values])
        b = np.linalg.lstsq(A, w['DBMF'].values, rcond=None)[0][1:]
        out[R.index[i - 1]] = dict(zip(X, b))
    B = pd.DataFrame(out).T
    B['주식노출'] = B[['SPY', 'EFA', 'EEM']].sum(axis=1)
    return B


def md(df, index=True):
    df = df.reset_index() if index else df
    f = lambda v: f'{v:.3f}' if isinstance(v, float) else (f'{v:%Y-%m-%d}' if isinstance(v, pd.Timestamp) else str(v))
    return '\n'.join(['| ' + ' | '.join(map(str, df.columns)) + ' |', '|' + '---|' * len(df.columns)] + ['| ' + ' | '.join(f(v) for v in r) + ' |' for r in df.itertuples(index=False)])


def ic(sig, fwd, mask=None):
    d = pd.DataFrame({'s': sig, 'f': fwd})
    if mask is not None:
        d = d[mask.reindex(d.index).fillna(False)]
    d = d.dropna()
    return (d['s'].rank().corr(d['f'].rank()), len(d)) if len(d) > 30 else (np.nan, len(d))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    P = load()
    B = dbmf_beta(P)
    import buy_plan as BP
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'collect'))
    Pb = pd.DataFrame({'^GSPC': P['^GSPC'], '^NDX': P['^NDX'], '^RUT': P['^RUT']})
    Pb['^VIX'] = Pb['^VIX3M'] = Pb['^MOVE'] = np.nan
    O, V = BP.blocks(Pb.assign(**{'^VIX': 0.0, '^VIX3M': 0.0, '^MOVE': 0.0}))
    cta = V['CTA']
    s = P['^GSPC'].dropna()
    fwd = s.shift(-H) / s - 1
    dd = s / s.rolling(252, min_periods=1).max() - 1
    D = pd.DataFrame({'DBMF 주식노출': B['주식노출'], 'CTA σ': cta, 'S&P 63일 뒤': fwd, '낙폭': dd,
                      'B06 CTA≤−4': O['B06 CTA ≤ −4'], 'B06 변동성<0.6': O['B06 변동성 목표 노출 < 0.6배'],
                      'B06 JPM 전환': O['B06 JPM 추세 신호 전환']}).dropna(subset=['DBMF 주식노출'])
    D.to_csv(OUT / 'dbmf_일별.csv', encoding='utf-8-sig')
    rep = ['# DBMF 검증 결과 (코드: app/market/dbmf_test.py)', '']

    # ② N-PORT 맞춰 보기
    try:
        N = nport()
        N['회귀 주식노출(그날)'] = [B['주식노출'].asof(d) for d in N['기준일']]
        N.to_csv(OUT / 'dbmf_nport.csv', index=False, encoding='utf-8-sig')
        rep += ['## ② 회귀 추정 vs SEC N-PORT 실제 보유', f"- 분기 {len(N)}개, 상관 {N['N-PORT 주식노출'].corr(N['회귀 주식노출(그날)']):.2f}", '',
                md(N[['기준일', 'N-PORT 주식노출', '회귀 주식노출(그날)']], False), '']
    except Exception as e:   # noqa: BLE001
        rep += [f'## ② N-PORT: 계산 실패 {e}', '']

    # ③ CTA σ 상관
    lv = D[['DBMF 주식노출', 'CTA σ']].dropna()
    ch = D[['DBMF 주식노출', 'CTA σ']].diff(20).dropna()
    rep += ['## ③ 우리 B06 CTA σ와 비교', f"- 수준 상관 {lv.corr().iloc[0, 1]:.2f} (일 {len(lv)}개)", f"- 20일 변화 상관 {ch.corr().iloc[0, 1]:.2f}", '']

    # ④ 단독 IC, ⑤ B06 맞대기
    mid = D.index[len(D) // 2]
    halves = {'전체': D.index == D.index, '전반': D.index < mid, '후반': D.index >= mid}
    halves = {k: pd.Series(v, index=D.index) for k, v in halves.items()}
    cond = {'모든 날': pd.Series(True, index=D.index), 'S&P 고점 −10% 아래': D['낙폭'] <= -0.10}
    z = -(D['DBMF 주식노출'] - D['DBMF 주식노출'].rolling(252, min_periods=60).mean()) / D['DBMF 주식노출'].rolling(252, min_periods=60).std()
    low = (D['DBMF 주식노출'] <= D['DBMF 주식노출'].expanding(120).quantile(0.10)).astype(float)
    b06 = D[['B06 CTA≤−4', 'B06 변동성<0.6', 'B06 JPM 전환']].sum(axis=1)
    rows = []
    for cn, cm in cond.items():
        for hn, hm in halves.items():
            m = cm & hm
            r = {'조건': cn, '기간': hn}
            r['DBMF 단독(낮을수록 기회, z)'], r['날 수'] = ic(z, D['S&P 63일 뒤'], m)
            r['DBMF 하위10% 신호 단독'] = ic(low, D['S&P 63일 뒤'], m)[0]
            r['B06 기존(공식 3개 합)'] = ic(b06, D['S&P 63일 뒤'], m)[0]
            r['B06 + DBMF 하위10%'] = ic(b06 + low, D['S&P 63일 뒤'], m)[0]
            r['B06 연속값(−CTA σ)'] = ic(-D['CTA σ'], D['S&P 63일 뒤'], m)[0]
            r['−CTA σ + DBMF z'] = ic((-D['CTA σ'] / D['CTA σ'].std()) + z / z.std(), D['S&P 63일 뒤'], m)[0]
            r['B06 − DBMF 하위10%(추세 따라가기)'] = ic(b06 - low, D['S&P 63일 뒤'], m)[0]
            rows.append(r)
    q = P['^NDX'].dropna()
    qf = (q.shift(-H) / q - 1).reindex(D.index)
    qd = (q / q.rolling(252, min_periods=1).max() - 1).reindex(D.index)
    for cn, cm in (('나스닥100 모든 날', pd.Series(True, index=D.index)), ('나스닥100 고점 −10% 아래', qd <= -0.10), ('나스닥100 고점 −15% 아래', qd <= -0.15)):
        for hn, hm in halves.items():
            m = cm & hm
            r = {'조건': cn, '기간': hn}
            r['DBMF 단독(낮을수록 기회, z)'], r['날 수'] = ic(z, qf, m)
            r['DBMF 하위10% 신호 단독'] = ic(low, qf, m)[0]
            r['B06 기존(공식 3개 합)'] = ic(b06, qf, m)[0]
            r['B06 + DBMF 하위10%'] = ic(b06 + low, qf, m)[0]
            r['B06 연속값(−CTA σ)'] = ic(-D['CTA σ'], qf, m)[0]
            r['−CTA σ + DBMF z'] = ic((-D['CTA σ'] / D['CTA σ'].std()) + z / z.std(), qf, m)[0]
            r['B06 − DBMF 하위10%(추세 따라가기)'] = ic(b06 - low, qf, m)[0]
            rows.append(r)
    T = pd.DataFrame(rows)
    T.to_csv(OUT / 'dbmf_IC.csv', index=False, encoding='utf-8-sig')
    rep += [f'## ④·⑤ 63일 뒤 S&P 수익과 순위상관(IC), 전반/후반 경계 {mid:%Y-%m-%d}', md(T, False), '']

    # ⑥ 사건 검정
    ev, last = [], None
    for d, v in low.items():
        if v == 1 and (last is None or (D.index.get_loc(d) - D.index.get_loc(last)) > H):
            ev.append(d)
            last = d
    E = D.loc[ev, ['DBMF 주식노출', '낙폭', 'S&P 63일 뒤']]
    E.to_csv(OUT / 'dbmf_사건.csv', encoding='utf-8-sig')
    rep += ['## ⑥ 사건 검정: DBMF 주식노출 하위 10% 처음 들어간 날(63일 재무장)']
    for cn, cm in (('모든 날', None), ('고점 −10% 아래', -0.10)):
        e = E if cm is None else E[E['낙폭'] <= cm]
        base = D if cm is None else D[D['낙폭'] <= cm]
        ef, bf = e['S&P 63일 뒤'].dropna(), base['S&P 63일 뒤'].dropna()
        rep.append(f"- {cn}: 사건 {len(ef)}번, 63일 뒤 평균 {ef.mean() * 100:+.1f}%, 오른 비율 {(ef > 0).mean() * 100:.0f}% | 같은 조건 아무 날 {bf.mean() * 100:+.1f}%, {(bf > 0).mean() * 100:.0f}% (날 {len(bf)})")
    rep += ['', md(E.assign(**{'S&P 63일 뒤': E['S&P 63일 뒤'] * 100, '낙폭': E['낙폭'] * 100})), '',
            f"## 오늘 값", f"- DBMF 주식노출(회귀) {B['주식노출'].iloc[-1]:.2f} (기준 {B.index[-1]:%Y-%m-%d}), 하위 10% 문턱 {D['DBMF 주식노출'].expanding(120).quantile(0.10).iloc[-1]:.2f}",
            f"- CTA σ {cta.dropna().iloc[-1]:.2f}"]
    (OUT / 'dbmf_요약.md').write_text('\n'.join(rep), encoding='utf-8')
    print('\n'.join(rep))


if __name__ == '__main__':
    main()
