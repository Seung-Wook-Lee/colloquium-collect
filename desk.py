# 섹터 데스크 수급 계산 — 블록 09_desk가 부른다 (2026-10-31 의장 "각 분야 전문가가 그 분야 특징, 돈이 몰리는 수급을 줄줄 말해야")
#   데스크 5곳마다 '업종 대표 ETF'와 '담당 종목'의 돈 흐름을 숫자로 만든다.
#   상대강도: 1·4·12주 초과수익(시장 대비), 섹터 로테이션 사분면(RRG, sector.py와 같은 식)
#   거래대금 배율: 최근 5일 평균 거래대금 ÷ 60일 평균 (1보다 크면 평소보다 돈이 많이 오감)
#   20주선 위·아래
#   시장 기준: 한국 = TIGER 200(K21), 미국 = SPYM(G41), 일본 = 닛케이225(^N225)
#   담당표는 위원총괄·데스크별_담당표(2026-10-31 의장)와 같다. 데스크가 바뀌면 DESKS를 고친다.
import numpy as np
import pandas as pd

import sector

# 데스크: (스튜디오 톰앤수 100 번호 목록, 유니버스 밖 업종 대표 ETF 목록[(티커, 이름)])
DESKS = {
    '미스 세마이(반도체·하드웨어)': (
        'K01 K02 K11 G01 G09 G10 G11 G12 G13 G14 G15 G16 G31 G34 G35 G40 K24 K25 K26 K27 K28 K37 K41 G43 G44 G45',
        [('SOXX', 'iShares 반도체'), ('XSD', 'SPDR 반도체(동일가중)')]),
    '미스터 빅스(빅테크)': (
        'G02 G03 G04 G05 G07 G17 K10 K29 K30 G49',
        [('XLK', 'SPDR 기술'), ('XLC', 'SPDR 커뮤니케이션'), ('MAGS', 'Roundhill 매그니피센트7')]),
    '미스 파이낸스(금융·지주·전력·산업재·방산)': (
        'K12 K13 K14 K06 K07 G19 G20 G21 G51 G36 G39 K18 K19 G18 G28 G29 G30 K17 K05 K31 K32 K33 K34 K38 K39 G48',
        [('XLF', 'SPDR 금융'), ('KBE', 'SPDR 은행'), ('XLU', 'SPDR 유틸리티'), ('XLI', 'SPDR 산업재'),
         ('ITA', 'iShares 항공우주·방산'), ('URA', 'Global X 우라늄')]),
    '일라이 존슨(소재·바이오·소비재)': (
        'G33 G32 K04 K15 K16 K20 G22 G23 G24 G25 G26 G27 K36 G47',
        [('XBI', 'SPDR 바이오'), ('XLP', 'SPDR 필수소비재'), ('XLY', 'SPDR 경기소비재'), ('XLB', 'SPDR 소재')]),
    '미스터 로보(로봇·모빌리티·우주·배터리)': (
        'G06 G08 K08 K09 G37 G38 K03 K35',
        [('BOTZ', 'Global X 로봇·AI'), ('DRIV', 'Global X 자율주행·전기차'), ('LIT', 'Global X 리튬·배터리'),
         ('UFO', 'Procure 우주')]),
}
BENCH = {'한국': 'K21', '미국': 'G41', '일본': '^N225'}
WEEKS = (1, 4, 12)


def extra_tickers():
    return sorted({t for _, ex in DESKS.values() for t, _ in ex} | {'^N225'})


def _row(desk, kind, no, nm, mkt, d, b):
    c, bc = d['종가'].dropna(), b['종가'].dropna()
    r = {'데스크': desk, '구분': kind, '번호': no, '종목': nm, '시장': mkt, '기준일': c.index[-1].date()}
    cw, bw = sector.weekly(c), sector.weekly(bc)
    for w in WEEKS:
        if len(cw) > w and len(bw) > w:
            mine = (cw.iloc[-1] / cw.iloc[-1 - w] - 1) * 100
            r[f'초과_{w}주(%p)'] = round(mine - (bw.iloc[-1] / bw.iloc[-1 - w] - 1) * 100, 1)
        else:
            r[f'초과_{w}주(%p)'] = np.nan
    ratio, mom = sector.rrg(c, bw)
    r['RRG_사분면'] = sector.quad(ratio.iloc[-1], mom.iloc[-1]) if len(ratio) else ''
    r['RRG_4주전'] = sector.quad(ratio.iloc[-5], mom.iloc[-5]) if len(ratio) > 5 else ''
    amt = (d['종가'] * d['거래량']).dropna()
    r['거래대금배율(5일/60일)'] = round(amt.iloc[-5:].mean() / amt.iloc[-60:].mean(), 2) if len(amt) >= 60 and amt.iloc[-60:].mean() > 0 else np.nan
    ma20 = cw.rolling(20).mean()
    r['20주선'] = '' if pd.isna(ma20.iloc[-1]) else ('위' if cw.iloc[-1] > ma20.iloc[-1] else '아래')
    return r


def analyze(px, u):
    """px: {티커: 일봉 DataFrame(종가·거래량 등, 날짜 인덱스)}, u: 유니버스 표(번호 인덱스 아님)
    반환: (상세 표, 데스크 요약 표)"""
    uu = u.set_index('번호')
    bench = {m: px.get(uu.loc[no, 'yfinance 티커'] if no in uu.index else no) for m, no in BENCH.items()}
    rows = []
    for desk, (nos, extra) in DESKS.items():
        for no in nos.split():
            if no not in uu.index:
                continue
            t, mkt = uu.loc[no, 'yfinance 티커'], uu.loc[no, '시장']
            b = bench.get(mkt)
            if t in px and b is not None and len(px[t]) > 60:
                kind = 'ETF' if uu.loc[no, '구분'] == 'ETF' else '종목'
                rows.append(_row(desk, kind, no, uu.loc[no, '정식 종목명'], mkt, px[t], b))
        for t, nm in extra:
            if t in px and bench['미국'] is not None and len(px[t]) > 60:
                rows.append(_row(desk, '업종 ETF(유니버스 밖)', t, nm, '미국', px[t], bench['미국']))
    df = pd.DataFrame(rows)
    summ = []
    for desk, g in df.groupby('데스크', sort=False) if len(df) else []:
        s = g[g['구분'] == '종목']
        flow = g.dropna(subset=['거래대금배율(5일/60일)', '초과_4주(%p)'])
        hot = flow[(flow['거래대금배율(5일/60일)'] >= 1.2) & (flow['초과_4주(%p)'] > 0)].sort_values('초과_4주(%p)', ascending=False)
        cold = flow[(flow['거래대금배율(5일/60일)'] >= 1.2) & (flow['초과_4주(%p)'] < 0)].sort_values('초과_4주(%p)')
        q = g['RRG_사분면'].value_counts()
        summ.append({
            '데스크': desk, '종목 수': len(s), 'ETF 수': len(g) - len(s),
            '담당 종목 초과_4주 중앙값(%p)': round(s['초과_4주(%p)'].median(), 1),
            '담당 종목 초과_12주 중앙값(%p)': round(s['초과_12주(%p)'].median(), 1),
            '20주선 위(종목)': f"{int((s['20주선'] == '위').sum())}/{len(s)}",
            'RRG 선도·개선·약화·침체': '·'.join(str(int(q.get(k, 0))) for k in ('선도', '개선', '약화', '침체')),
            '거래대금 늘며 오른 것': ', '.join(f"{r['종목']}({r['초과_4주(%p)']:+.1f}%p, {r['거래대금배율(5일/60일)']}배)" for _, r in hot.head(3).iterrows()) or '없음',
            '거래대금 늘며 빠진 것': ', '.join(f"{r['종목']}({r['초과_4주(%p)']:+.1f}%p, {r['거래대금배율(5일/60일)']}배)" for _, r in cold.head(3).iterrows()) or '없음',
        })
    return df, pd.DataFrame(summ)
