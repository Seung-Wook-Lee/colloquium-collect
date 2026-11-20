"""3-30 바닥 신호 세밀 점수: 11/20 의장 "54개인데 5표로 분류? 조금 더 디테일해야".
같은 자료(켜진 기법이 최근 창일 안에 켜졌나, 0/1)로 집계 방식 4가지를 앞 7년에 맞추고 뒤 3년에서 비교한다.
 ① 갈래 표(현행)                 — 볼린저 다중공선성 규칙, 갈래마다 1표
 ② 켜진 기법 수                  — 단순 합(겹침 무시, 비교용)
 ③ 증거 가중치(Weight of Evidence) — Good(1950)·신용평가 표준. 기법마다 log(앞 7년 바닥즈음 배율),
                                    갈래 안에서는 가장 큰 것 하나만(중복 방지), 갈래끼리 더함
 ④ 로지스틱 회귀 확률            — Cox(1958), L2 축소(겹친 기법 무게를 스스로 나눔). 앞 7년으로 맞춤
비교: 뒤 3년 AUC(무작위 0.5), 점수 상위 10%·1%의 바닥즈음 배율.
  python -m analysis.b3_30_score --data <1_data> --universe <유니버스.csv> --out <폴더>
"""
import argparse
import os

import numpy as np
import pandas as pd

from . import b3_30_ta_library as LIB
from . import b3_30_ta_test as TT
from . import b3_30_votes as VO


def frame(SIG, techs, win, T):
    """종목·날짜별 0/1 기법 칸 + 정답(3%)."""
    out = []
    for t, (c, sig) in SIG.items():
        X = pd.DataFrame({k: sig[k].astype(int).rolling(win, min_periods=1).max() for k in techs})
        X['z'] = TT.zone(c, T['허용폭'][0], T['앞뒤일'], T['낙폭'])
        X['ticker'] = t
        out.append(X)
    return pd.concat(out)


def auc(y, s):
    from sklearn.metrics import roc_auc_score
    m = ~np.isnan(y)
    return roc_auc_score(y[m], s[m])


def top_lift(y, s, q):
    m = ~np.isnan(y)
    y, s = y[m], s[m] + np.random.default_rng(0).uniform(0, 1e-9, m.sum())
    cut = np.quantile(s, 1 - q)
    return y[s >= cut].mean() / y.mean()


def fit(F, techs, split):
    from sklearn.linear_model import LogisticRegression
    G = VO.groups(techs)
    tr = F[(F.index < split) & F['z'].notna()]
    base = tr['z'].mean()
    lift = {k: (tr.loc[tr[k] == 1, 'z'].mean() / base if (tr[k] == 1).sum() >= 30 else 1.0) for k in techs}
    woe = {k: float(np.log(max(v, 1e-3))) for k, v in lift.items()}
    lr = LogisticRegression(C=1.0, max_iter=2000).fit(tr[techs].values, tr['z'].values.astype(int))
    return G, woe, lr


def scores(F, techs, G, woe, lr):
    S = pd.DataFrame(index=F.index)
    S['① 갈래 표'] = sum((F[ks].max(axis=1) > 0).astype(int) for ks in G.values())
    S['② 켜진 기법 수'] = F[techs].sum(axis=1)
    S['③ 증거 가중치'] = sum((F[ks] * pd.Series({k: max(woe[k], 0) for k in ks})).max(axis=1) for ks in G.values())
    S['④ 로지스틱 확률'] = lr.predict_proba(F[techs].values)[:, 1]
    return S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True); ap.add_argument('--universe', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    C3 = TT.private_cfg(); T = C3['시험']; win = (C3.get('집계') or {}).get('창일', 5)
    split = pd.Timestamp(T['나눔날'])
    C, O, H, L, V, cty, cal = TT.load(a.data, a.universe)
    rows, wt = [], []
    for nm in ('미국', '한국'):
        techs = VO.on_list(C3, nm)
        SIG = VO.ticker_signals(C, O, H, L, V, cty[nm], cal[nm])
        F = frame(SIG, techs, win, T)
        G, woe, lr = fit(F, techs, split)
        te = F[F.index >= split]
        S = scores(te, techs, G, woe, lr)
        y = te['z'].values
        for m in S.columns:
            s = S[m].values.astype(float)
            rows.append({'나라': nm, '방식': m, '뒤3년 AUC': round(auc(y, s), 3),
                         '상위 10% 배율': round(top_lift(y, s, 0.10), 2), '상위 1% 배율': round(top_lift(y, s, 0.01), 2)})
        for k in techs:
            wt.append({'나라': nm, '번호': k, '기법': LIB.META.at[k, '기법'], '갈래': LIB.META.at[k, '갈래'],
                       '증거 가중치(앞7년)': round(woe[k], 3), '로지스틱 계수(앞7년)': round(float(lr.coef_[0][techs.index(k)]), 3)})
    os.makedirs(a.out, exist_ok=True)
    R = pd.DataFrame(rows); W = pd.DataFrame(wt)
    R.to_csv(os.path.join(a.out, '바닥점수_방식비교.csv'), index=False, encoding='utf-8-sig')
    W.to_csv(os.path.join(a.out, '바닥점수_기법가중치.csv'), index=False, encoding='utf-8-sig')
    print(R.to_string())


if __name__ == '__main__':
    main()
