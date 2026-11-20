"""1-6 정제: 1-1 가격을 그 자리에서 검사하고 고친다.
- 이상치: 하루 수익률 |r| > 문턱(분할·자료 오류) → 그날 가격을 비우고 앞뒤로 잇는다. 중앙값 절대편차(MAD) z > 문턱 → 표시만.
- 결측: 거래일인데 값이 없으면 앞 값으로 최대 N일 채움(그 이상은 비움, 상장 전은 그대로 비움).
- 거래량 0·음수 → 비움.
출력: 가격10년_정제.csv.gz, 정제_기록.csv.gz(종목·날짜·무엇·원래값)"""
import numpy as np
import pandas as pd

from .common import read, write


def _cells(mask):
    x = mask.stack()
    return x[x.astype(bool)].index


def run(ctx, c):
    P = ctx.get('P_raw')
    if P is None:
        P = read(ctx, '가격10년_종가.csv.gz', index_col=0, parse_dates=True)
    V = ctx.get('V_raw')
    if V is None:
        V = read(ctx, '가격10년_거래량.csv.gz', index_col=0, parse_dates=True)
    jump, madz, ffl = c.get('하루변동_문턱', 0.5), c.get('MAD_문턱', 10), c.get('채움_최대일', 5)
    log = []
    P = P.copy()
    r = P.pct_change(fill_method=None)
    bad = r.abs() > jump
    # 하루 튀었다 다음날 돌아오는 값(자료 오류)만 지운다. 계속 이어지면 분할 미보정 → 그 날 표시
    back = (r.shift(-1).abs() > jump) & (np.sign(r) != np.sign(r.shift(-1)))
    spike = bad & back
    for (d, t) in _cells(spike):
        log.append((t, d, '튄 값 지움(하루 ±문턱 뒤 되돌림)', P.at[d, t]))
    P = P.mask(spike)
    for (d, t) in _cells(bad & ~back):
        log.append((t, d, '큰 변동(분할·급변, 지우지 않음)', P.at[d, t]))
    r = P.pct_change(fill_method=None)
    med = r.median(); mad = (r - med).abs().median()
    z = (r - med) / (1.4826 * mad.replace(0, np.nan))
    for (d, t) in _cells(z.abs() > madz):
        log.append((t, d, f'MAD z>{madz}(표시만)', P.at[d, t]))
    first = P.apply(lambda s: s.first_valid_index())
    # 자기 시장이 연 날만 결측으로 본다(한국 종목의 미국 휴장일 등은 결측 아님)
    kr = [t for t in P.columns if str(t).endswith(('.KS', '.KQ')) or t in ('^KS11', '^KQ11')]
    open_kr = P['^KS11'].notna() if '^KS11' in P else P[kr].notna().any(axis=1)
    open_us = P['^GSPC'].notna() if '^GSPC' in P else P.drop(columns=kr).notna().any(axis=1)
    cal = pd.DataFrame({t: (open_kr if t in kr else open_us) for t in P.columns}, index=P.index)
    miss = P.isna() & (P.index.values[:, None] >= first.values[None, :]) & cal
    P2 = P.ffill(limit=ffl)
    filled = miss & P2.notna()
    for (d, t) in _cells(filled):
        log.append((t, d, f'결측 앞 값 채움(≤{ffl}일)', np.nan))
    P = P2.where(P.index.values[:, None] >= first.values[None, :])
    if V is not None:
        V = V.mask(V <= 0)
        write(ctx, '거래량10년_정제.csv.gz', V, index=True)
    write(ctx, '가격10년_정제.csv.gz', P, index=True)
    L = pd.DataFrame(log, columns=['ticker', '날짜', '무엇', '원래값'])
    write(ctx, '정제_기록.csv.gz', L)
    ctx['P'] = P; ctx['V'] = V; ctx['정제기록'] = L
    return {k: int(v) for k, v in L['무엇'].value_counts().items()}
