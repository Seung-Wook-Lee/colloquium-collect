"""시장 판단 L01~L20 검증 (11/26 의장: "6월 23일 이후 한국 시장 무너짐 — 6/23~7/1 사이 붕괴 신호가 나오는지,
4월 이후 급등 — 4/1~4/15 사이 긍정 신호가 나오는지 돌려봐. 안 나오거나 약하면 비중 조정 방법을 찾아봐. 자료는 모두 구글 드라이브").

자료: 드라이브 10년치 데이터베이스 칸만 읽음(1_data/가격10년_시장지표·지수장기·종가, 유니버스 칸). 아무것도 받지 않음.
계산: hist_market.main(엔진과 같은 변수·공식 판정)을
  ① 검증 구간 영업일마다(dates) ② 2000년부터 매주 금요일 — 둘 다 그날까지 알 수 있던 값만.
출력(실행 기록에 표로만, 새 파일 만들지 않음):
  1) 코스피 흐름(검증 구간 앞뒤)
  2) 구간별 L 공식마다 신호 나온 날 수 / 구간 날 수, 날마다 부담·기회 개수
  3) 비중 조정 방법 비교(주별, 2000~): 같은 무게 / 과거 정보계수(IC) 무게 / 능선 회귀(ridge) — 모두 그 해 전 자료로만 무게를 정하고
     다음 해에 적용(걸어가며 검증). 목표 = 코스피·S&P500 4주 뒤 수익. 각 방법의 표본 밖 정보계수와 두 구간 점수.
실행: python check_layers.py <폴더(드라이브 칸 받아 둘 곳)> <blocks.yaml>"""
import os
import sys

import numpy as np
import pandas as pd
import yaml

H = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(H))
sys.path[:0] = [H, os.path.join(REPO, 'collect'), os.path.join(REPO, 'collect', 'data')]
import hist_market as HM  # noqa: E402
import px_store as PS  # noqa: E402

WIN = {'붕괴 구간 2026-06-23~07-01': ('2026-06-23', '2026-07-01', '부담'),
       '상승 구간 2026-04-01~04-15': ('2026-04-01', '2026-04-15', '기회')}
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 400); pd.set_option('display.max_colwidth', 90)


def pull(d):
    import drive
    D = '콜로키움 수집데이터'
    M = PS.market(drive, None, d)   # 시장 지표 칸(칸이 아직 없으면 옛 1_data/장기 파일로 만듦 — 11/26 의장 '저장본의 칸으로 합침')
    print(PS.name('시장지표'), M.shape)
    print(PS.name('지수장기'), '받음' if PS.fetch(drive, '지수장기', d) else '없음')
    b = drive.get(f'{D}/1_data/{PS.name("종가")}')
    if b:
        open(f'{d}/{PS.name("종가")}', 'wb').write(b)
    print(PS.name('종가'), '받음' if b else '없음')
    U = PS.universe(drive)
    if len(U):
        U.to_csv(f'{d}/유니버스.csv', index=False, encoding='utf-8-sig')


def formulas(y):
    B = yaml.safe_load(open(y, encoding='utf-8'))['시장']
    return [(bid, f'{bid}-{k + 1}', n, side) for bid, b in B.items() for k, (n, e, side) in enumerate(b['공식'])], B


def kospi_path(d):
    ks = PS.index(d)['^KS11'].dropna()
    x = ks.loc['2026-03-01':'2026-08-31']
    print('\n=== 1) 코스피 흐름 (드라이브 지수 칸) ===')
    for t in ('2026-03-31', '2026-04-01', '2026-04-15', '2026-05-29', '2026-06-22', '2026-06-23', '2026-07-01', '2026-07-31'):
        v = x.loc[:t]
        if len(v):
            print(f'{t}  {v.iloc[-1]:,.1f}  (그날 기준 마지막 거래일 {v.index[-1].date()})')
    print(f"4월 이후 최고 {x.loc['2026-04-01':'2026-06-30'].max():,.1f} ({x.loc['2026-04-01':'2026-06-30'].idxmax().date()}),"
          f" 6/23 이후 최저 {x.loc['2026-06-23':].min():,.1f} ({x.loc['2026-06-23':].idxmin().date()})")
    return ks


def windows(out, F, B):
    print('\n=== 2) 구간별 신호 ===')
    for nm, (a, b, want) in WIN.items():
        X = out.loc[a:b]
        print(f'\n--- {nm} ({len(X)}일, 이 구간에서 기대하는 쪽: {want}) ---')
        rows = []
        for bid, col, n, side in F:
            v = X[col]
            rows.append({'L': bid, '제목': B[bid]['질문'][:28], '공식': n[:70], '쪽': side,
                         '신호 날': int((v == 1).sum()), '자료 있는 날': int(v.notna().sum())})
        T = pd.DataFrame(rows)
        print(T.to_string(index=False))
        print('\n날짜별 부담·기회 개수(표시 제외):')
        print(X[['시장부담', '시장기회']].astype('Int64').T.to_string())


def weighting(W, F):
    """비중 조정 방법 비교(걸어가며 검증, 그 해 전 자료로 무게 → 그 해 적용)."""
    print('\n=== 3) 비중 조정 방법 비교 (주별, 표본 밖) ===')
    cols = [c for _, c, _, side in F if side in ('부담', '기회')]
    sign = {c: (-1 if side == '부담' else 1) for _, c, _, side in F}
    X = W[cols].astype(float)
    res = []
    for tgt in ('KS11_4주', 'SPX_4주'):
        y = W[tgt]
        yrs = sorted(set(W.index.year))
        S = {k: pd.Series(np.nan, index=W.index) for k in ('같은 무게', '정보계수 무게', '능선 회귀')}
        for yr in yrs:
            tr = (W.index.year < yr) & y.notna()
            te = W.index.year == yr
            if tr.sum() < 260 or not te.any():
                continue
            Xt = X[tr].fillna(0); yt = y[tr]
            S['같은 무게'][te] = sum(X.loc[te, c].fillna(0) * sign[c] for c in cols)
            ic = {c: (Xt[c].corr(yt, method='spearman') if Xt[c].std() > 0 else 0) for c in cols}
            ic = {c: (0 if pd.isna(v) else v) for c, v in ic.items()}
            S['정보계수 무게'][te] = sum(X.loc[te, c].fillna(0) * ic[c] for c in cols)
            A = Xt.to_numpy(); lam = 10.0
            beta = np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ (yt.to_numpy() - yt.mean()))
            S['능선 회귀'][te] = X.loc[te].fillna(0).to_numpy() @ beta
            if yr == 2026:
                last_w = (ic, dict(zip(cols, beta)))
        for k, s in S.items():
            m = s.notna() & y.notna()
            ic_all = s[m].corr(y[m], method='spearman')
            res.append({'목표': tgt, '방법': k, '표본 밖 정보계수': round(ic_all, 3), '주 수': int(m.sum()),
                        **{f'{nm[:5]} 점수': round(float(s.loc[a:b].mean()), 3) if s.loc[a:b].notna().any() else None for nm, (a, b, _) in WIN.items()}})
        if tgt == 'KS11_4주' and 'last_w' in dir():
            ic, be = last_w
            print('\n2026년에 쓴 무게(코스피 4주 목표, 2025년까지 자료로 정함):')
            print(pd.DataFrame({'정보계수 무게': ic, '능선 회귀 무게': be}).round(3).to_string())
    print('\n' + pd.DataFrame(res).to_string(index=False))
    print('읽는 법: 표본 밖 정보계수가 클수록 4주 뒤 수익을 잘 맞춤. 구간 점수는 붕괴 구간에서 낮을수록, 상승 구간에서 높을수록 맞음.')


def main(d, y):
    F, B = formulas(y)
    kospi_path(d)
    days = pd.bdate_range('2026-03-02', '2026-07-31')
    out = HM.main(d, y, dates=days, save=False)
    windows(out, F, B)
    W = HM.main(d, y, start='2000-01-07', save=False)
    weighting(W, F)


if __name__ == '__main__':
    d = sys.argv[1]; os.makedirs(d, exist_ok=True)
    if os.environ.get('DRIVE_URL'):
        pull(d)
    main(d, sys.argv[2])
