"""유니버스 생성법 — 층(L1~L5) 분류 (11/20 의장 "니 멋대로 하지 말고, 코딩을 해서 분류를 해").

규칙(숫자는 비공개 blocks.yaml '유니버스'에만 둔다):
  1) 삭제 목록에 있는 종목을 유니버스에서 뺀다.
  2) 종목마다 연 변동성 = 최근 N년 일간 수익률 표준편차 × √252 (하루 ±50% 넘는 값은 분할·자료 오류로 보고 뺀다,
     '제외 구간'(코로나 2020년 3월 등)의 날은 뺀다).
  3) 종류(미국 기업·한국 기업·미국ETF·한국ETF)마다 다른 문턱으로 L1(가장 덜 흔들림)~L5를 정한다.
  4) 의장 지정(종목 → 층)은 규칙보다 우선한다.
출력: 층 표(csv)와 층별 표(마크다운: 미국 | 한국 | 미국ETF | 한국ETF, 괄호에 연 변동성).
실행: python quant_center/universe_layers.py <유니버스.csv> <출력폴더>
"""
import itertools
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qc_config import load_blocks

KINDS = ['미국 기업', '한국 기업', '미국ETF', '한국ETF']
KO = dict(NVDA='엔비디아',GOOGL='알파벳',MSFT='마이크로소프트',META='메타',AAPL='애플',TSLA='테슬라',AMZN='아마존',SPCX='스페이스X',MU='마이크론',TSM='TSMC',MRVL='마벨',AVGO='브로드컴',SNDK='샌디스크',ASML='ASML',AMAT='어플라이드',LITE='루멘텀',PLTR='팔란티어',BE='블룸에너지',JPM='JP모건',GS='골드만삭스',BLK='블랙록',JNJ='J&J',LLY='일라이릴리',KO='코카콜라',MAR='메리어트',CCL='카니발',WMT='월마트',LEU='센트러스',NEE='넥스트에라',GEV='GE버노바',HOOD='로빈후드',MRNA='모더나',MRK='머크',TEM='템퍼스AI',IREN='아이렌',SKHY='SK하이닉스ADR',AMD='AMD',V='비자',UBER='우버',O='리얼티인컴',NFLX='넷플릭스',KMI='킨더모건',COST='코스트코',RCL='로열캐리비안',LUNR='인튜이티브머신스',LRCX='램리서치',TGT='타깃',ETN='이튼',CIEN='시에나',CSCO='시스코',IBM='IBM',VZ='버라이즌',CRM='세일즈포스',AXP='아멕스',UNH='유나이티드헬스',AMGN='암젠',PG='P&G',MCD='맥도날드',NKE='나이키',DIS='디즈니',SBUX='스타벅스',BA='보잉',CAT='캐터필러',MMM='3M',HD='홈디포',HON='하니웰',WM='웨이스트매니지먼트',XOM='엑손모빌',MA='마스터카드',ABBV='애브비',CVX='셰브론',ORCL='오라클',BAC='뱅크오브아메리카',GE='GE에어로',INTC='인텔',PM='필립모리스',MS='모건스탠리',TXN='TI',RTX='RTX',PANW='팔로알토',WFC='웰스파고',LIN='린데',ANET='아리스타',HLT='힐튼',CB='처브')
KO['BRK-B'] = '버크셔'


def kind(r):
    return f"{r['시장']}{'ETF' if r['구분'] == 'ETF' else ' 기업'}"


def prices(tickers, years, end=None):
    import yfinance as yf
    end = pd.Timestamp(end or pd.Timestamp.today().normalize())
    start = end - pd.DateOffset(years=years)
    return yf.download(sorted(set(tickers)), start=start, end=end + pd.Timedelta(days=1), auto_adjust=True, progress=False)['Close']


def vol_from(P, tickers, excl):
    out = {}
    for t in tickers:
        if t not in P:
            out[t] = np.nan
            continue
        r = P[t].dropna().pct_change().dropna()
        r = r[r.abs() < 0.5]
        for a, b in excl:
            r = r[(r.index < pd.Timestamp(a)) | (r.index > pd.Timestamp(b))]
        out[t] = round(r.std() * np.sqrt(252) * 100, 1) if len(r) >= 60 else np.nan
    return out


def vols(tickers, years, excl, end=None):
    return vol_from(prices(tickers, years, end), tickers, excl)


def layer_of(v, edges):
    if pd.isna(v):
        return ''
    for i, e in enumerate(edges):
        if v <= e:
            return f'L{i + 1}'
    return f'L{len(edges) + 1}'


def classify(U, cfg, vol=None):
    U = U[~U['정식 종목명'].isin(cfg.get('삭제', [])) & ~U['yfinance 티커'].isin(cfg.get('삭제', []))].copy()
    U = U[~U['시장'].isin(cfg.get('제외_시장', []))]
    if vol is None:
        vol = vols(U['yfinance 티커'].dropna().tolist(), cfg['변동성_년'], cfg.get('제외_구간', []))
    U['연변동성'] = U['yfinance 티커'].map(vol)
    U['종류'] = U.apply(kind, axis=1)
    U['층'] = [layer_of(v, cfg['문턱'][k]) for v, k in zip(U['연변동성'], U['종류'])]
    U['층_근거'] = '규칙'
    for name, lay in (cfg.get('지정') or {}).items():
        m = (U['정식 종목명'] == name) | (U['yfinance 티커'] == name)
        U.loc[m, '층'] = lay
        U.loc[m, '층_근거'] = '의장 지정'
    return U


def label(r):
    if r['구분'] == 'ETF':
        return r['yfinance 티커'] if r['시장'] == '미국' else r['정식 종목명']
    return KO.get(r['yfinance 티커'], r['정식 종목명']) if r['시장'] == '미국' else r['정식 종목명']


def table(U, lay):
    g = U[U['층'] == lay].sort_values('연변동성')
    cols = []
    for k in KINDS:
        x = g[g['종류'] == k]
        cols.append([f"{label(r)} ({r['연변동성']:.1f}%{', 지정' if r['층_근거'] == '의장 지정' else ''})" for _, r in x.iterrows()])
    head = '| 미국 | 한국 | 미국ETF | 한국ETF |\n|---|---|---|---|\n'
    return head + '\n'.join('| ' + ' | '.join(row) + ' |' for row in itertools.zip_longest(*cols, fillvalue=''))


def main(univ, out):
    cfg = load_blocks()['유니버스']
    U = classify(pd.read_csv(univ, dtype=str, encoding='utf-8-sig'), cfg)
    os.makedirs(out, exist_ok=True)
    U.to_csv(os.path.join(out, '유니버스_층.csv'), index=False, encoding='utf-8-sig')
    md = []
    for i in range(1, 6):
        md.append(f'## L{i}\n\n' + table(U, f'L{i}') + '\n')
    open(os.path.join(out, '유니버스_층표.md'), 'w', encoding='utf-8').write('\n'.join(md))
    print(pd.crosstab(U['종류'], U['층']))
    return U


if __name__ == '__main__':
    main(*sys.argv[1:3])
