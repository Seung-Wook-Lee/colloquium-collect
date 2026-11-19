"""계좌 분석·제안 (11/20 의장: "현재 포트폴리오를 분석하고 제안").

입력(금액·수량 없이 비중만): 보유표 csv(계좌, 시장, 종목, 티커, 구분, 전체비중%, 수익률%) — 드라이브 '실전 투자 자료'.
엔진 판정표(out_판정표.csv), 유니버스(층·번호), 나스닥100 바닥 근접도 원점수.

의장 운영 원칙(11/20 0:44):
  ① 한국 커버드콜 분배금을 받아 대부분 투자한다 → 재투자 후보 = 엔진 '추천' 순위점수 순.
  ② 미국 주식은 자산 증식용, 위기 때 고베타 주도주에 투입한다.
     위기 = 나스닥100 바닥 근접도 준비(≥0.5)·경보(≥0.9), 조정 단계표 3단계(−15%).
     고베타 주도주 = 미국 개별주 중 나스닥 1년 베타 상위 1/3 + 주도 업종(B33) + 원칙 '떨어진 우량주'.
     실탄(현금+BOXX 등 현금성)을 단계마다 나눠 넣는다.
숫자 기본값은 cfg(blocks.yaml '계좌')로 바꾼다. 로그에는 비중(%)만 찍는다.
"""
import os
import sys

import numpy as np
import pandas as pd

DEF = dict(재투자_비율=0.8, 단계_나눔=3, 종목_상한=8.0, 후보수=5, 고베타_분위=2 / 3, 준비=0.5, 경보=0.9,
           현금성=['BOXX', 'SGOV', 'SHY', '0043B0.KS'], 주도='1년수익', 층_상한=25.0, 베타_최소=1.0, 층당=2, 고르는법='층별')   # 11/20 의장 "반도체 위주" → 층별: 층 비중 상한(울타리) 넘은 층은 안 사고, 남은 층마다 1종목(층 안 베타 상위 절반 중 순위점수 1등)   # 주도: 'B33'(지금 돈이 도는 업종) 또는 '1년수익'(지난 1년 수익률 상위 1/3 = 이번 상승장 주도주)


def betas(tickers, idx='^NDX'):
    import yfinance as yf
    P = yf.download(sorted(set(tickers) | {idx}), period='1y', auto_adjust=True, progress=False)['Close']
    R = P.pct_change(fill_method=None)
    m = R[idx]
    out = {}
    for t in tickers:
        if t in R:
            x = pd.concat([R[t], m], axis=1).dropna()
            out[t] = x.iloc[:, 0].cov(x.iloc[:, 1]) / x.iloc[:, 1].var() if len(x) > 60 else np.nan
    hi = (P / P.rolling(252, min_periods=60).max() - 1).iloc[-1] * 100
    r1 = (P.ffill().iloc[-1] / P.ffill().bfill().iloc[0] - 1) * 100
    return pd.Series(out), hi, r1


def run(W, hold, S, U, ndx_raw=None, stage=None, cfg=None):
    C = {**DEF, **(cfg or {})}
    U = U.rename(columns={'yfinance 티커': '티커'})[['번호', '티커', '층', '층 이름']]
    S = S.merge(U[['번호', '티커']], on='번호', how='left')
    H = hold.copy()
    H['티커'] = H['티커'].fillna('').astype(str)
    H = H.merge(S[['티커', '원칙', '추천', '순위점수', 'B33']], on='티커', how='left').merge(U[['티커', '층', '층 이름']], on='티커', how='left')
    H.loc[H['시장'] == '일본', '원칙'] = H.loc[H['시장'] == '일본', '원칙'].fillna('판정 없음(일본은 엔진 밖)')
    H['원칙'] = H['원칙'].fillna(pd.Series(np.where(H['구분'] == '현금', '현금', '판정 없음(유니버스 밖)'), index=H.index))
    H.loc[H['티커'].isin(C['현금성']), '원칙'] = '현금성'
    us = S[(S['시장'] == '미국') & (S['구분'] == '개별주')]
    tick = [t for t in set(us['티커'].dropna()) | set(H.loc[H['티커'] != '', '티커'])]
    beta, hi, r1 = betas(tick)
    H['나스닥베타'] = H['티커'].map(beta).round(2); H['52주고점대비%'] = H['티커'].map(hi).round(1)
    # 계좌 요약
    w = H['전체비중%']
    cash = float(w[H['원칙'].isin(['현금', '현금성'])].sum())
    risk = H[~H['원칙'].isin(['현금', '현금성'])]
    SUM = pd.concat([
        H.groupby('시장')['전체비중%'].sum().rename('비중%').reset_index().assign(묶음='시장').rename(columns={'시장': '항목'}),
        H.groupby('원칙')['전체비중%'].sum().rename('비중%').reset_index().assign(묶음='원칙').rename(columns={'원칙': '항목'}),
        H.dropna(subset=['층 이름']).groupby('층 이름')['전체비중%'].sum().rename('비중%').reset_index().assign(묶음='층').rename(columns={'층 이름': '항목'}),
        pd.DataFrame([dict(묶음='계좌', 항목='실탄(현금+현금성)', **{'비중%': cash}),
                      dict(묶음='계좌', 항목='가중 나스닥베타(현금 제외, 베타 있는 것)',
                           **{'비중%': float((risk['나스닥베타'] * risk['전체비중%']).sum() / risk.loc[risk['나스닥베타'].notna(), '전체비중%'].sum())})])])
    SUM['비중%'] = SUM['비중%'].round(2)
    # 단계
    if ndx_raw is None:
        st = '모름'
    else:
        st = '경보' if ndx_raw >= C['경보'] else '준비' if ndx_raw >= C['준비'] else '평상'
    deep = stage is not None and stage >= 3
    k = {'평상': 0, '준비': 1, '경보': 2, '모름': 0}[st] + (1 if deep else 0)
    put = round(cash * min(k, C['단계_나눔']) / C['단계_나눔'], 2)
    # 고베타 주도주 후보
    us = us.assign(나스닥베타=us['티커'].map(beta), 고점대비=us['티커'].map(hi), 수익1년=us['티커'].map(r1))
    cut = us['나스닥베타'].quantile(C['고베타_분위'])
    lead = (us['B33'] == 1) if C['주도'] == 'B33' else (us['수익1년'] >= us['수익1년'].quantile(2 / 3))
    us = us.merge(U[['티커', '층 이름']], on='티커', how='left')
    lay_w = H.dropna(subset=['층 이름']).groupby('층 이름')['전체비중%'].sum()
    if C['고르는법'] == '층별':
        fine = us[(us['추천'] == '추천') & (us['나스닥베타'] >= C['베타_최소'])].copy()   # 11/20 의장 "잡주는 안 된다" → 엔진 '추천'(떨어짐·우량 관문 통과 + 순위점수 ≥ 0.5)만
        fine['층비중'] = fine['층 이름'].map(lay_w).fillna(0)
        fine = fine[fine['층비중'] < C['층_상한']]
        cand = fine.sort_values('순위점수', ascending=False).groupby('층 이름').head(C['층당'])
    else:
        cand = us[(us['나스닥베타'] >= cut) & lead & (us['원칙'] == '떨어진 우량주')]
    cand = cand.sort_values('순위점수', ascending=False)
    LAY = pd.DataFrame({'층 비중%': lay_w.round(2)}).assign(상한=C['층_상한'])
    LAY['상태'] = np.where(LAY['층 비중%'] >= LAY['상한'], '상한 넘음 → 새로 안 삼', '살 수 있음')
    held = H[H['티커'] != ''].groupby('티커')['전체비중%'].sum()
    n = min(len(cand), C['후보수'])
    each = put / n if n else 0
    BUY = cand.head(C['후보수'])[['번호', '종목', '티커', '층 이름', '추천', '순위점수', '나스닥베타', '고점대비', '수익1년']].copy()
    BUY['보유%'] = BUY['티커'].map(held).fillna(0)
    BUY['이번단계_더살%'] = [round(max(0.0, min(each, C['종목_상한'] - h)), 2) for h in BUY['보유%']]
    BUY['나스닥베타'] = BUY['나스닥베타'].round(2); BUY['고점대비'] = BUY['고점대비'].round(1); BUY['수익1년'] = BUY['수익1년'].round(1)
    # 분배금 재투자 후보(엔진 추천 순)
    RE = S[S['추천'] == '추천'].sort_values('순위점수', ascending=False)[['번호', '종목', '시장', '층', '순위점수']].head(10)
    RE['보유%'] = RE['번호'].map(S.set_index('번호')['티커']).map(held).fillna(0)
    # 보유 점검
    CHK = H[H['원칙'].isin(['우량 아님', '고점 부근(안 떨어짐)'])][['시장', '종목', '티커', '전체비중%', '수익률%', '원칙', '추천']]
    lines = [f'미국 계좌 단계: {st} (나스닥100 바닥 근접도 원점수 {ndx_raw if ndx_raw is not None else "없음"}'
             + (f', 조정 {stage}단계' if stage is not None else '') + ')',
             f'실탄(현금+현금성) {cash:.1f}% → 이번 단계까지 투입 {put:.1f}% (단계 {k}/{C["단계_나눔"]})',
             (f'층별: 층 비중 {C["층_상한"]}% 넘은 층({", ".join(LAY.index[LAY["층 비중%"] >= LAY["상한"]]) or "없음"})은 안 사고, 나머지 층에서 엔진 추천·나스닥베타 {C["베타_최소"]} 이상 중 순위점수 순 층당 {C["층당"]}개 → {n}종목에 {each:.1f}%씩'
              if C['고르는법'] == '층별' else f'고베타 주도주 후보 {len(cand)}개(나스닥베타 {cut:.2f} 이상·주도={C["주도"]}·떨어진 우량주) 중 상위 {n}개에 {each:.1f}%씩') + f', 종목 상한 {C["종목_상한"]}%',
             f'분배금 재투자: 들어온 분배금의 {int(C["재투자_비율"] * 100)}%를 엔진 추천 순위대로',
             f'점검 대상(원칙 밖 보유) {len(CHK)}개, 비중 합 {CHK["전체비중%"].sum():.1f}%']
    LAY.reset_index().to_csv(f'{W}/계좌_층비중.csv', index=False, encoding='utf-8-sig')
    for k_, v in (('계좌_보유판정', H), ('계좌_요약', SUM), ('계좌_고베타후보', BUY), ('계좌_분배금재투자', RE), ('계좌_점검', CHK)):
        v.to_csv(f'{W}/{k_}.csv', index=False, encoding='utf-8-sig')
    open(f'{W}/계좌_할일.txt', 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return H, SUM, BUY, RE, CHK, lines


if __name__ == '__main__':
    # python account.py <보유표.csv> <판정표.csv> <유니버스.csv> <출력폴더> [나스닥 원점수] [조정 단계]
    h, s, u, W = sys.argv[1:5]
    raw = float(sys.argv[5]) if len(sys.argv) > 5 else None
    stg = int(sys.argv[6]) if len(sys.argv) > 6 else None
    os.makedirs(W, exist_ok=True)
    rd = lambda f: pd.read_csv(f, encoding='utf-8-sig')
    run(W, rd(h), rd(s), rd(u), raw, stg)
