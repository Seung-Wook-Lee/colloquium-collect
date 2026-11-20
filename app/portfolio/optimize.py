"""비중 계산법 — 표준 이론 이름 그대로.
- 계층적 위험 균형(HRP, López de Prado 2016): 상관 거리로 종목을 묶고, 묶음을 둘로 나누며 위험 반비례로 나눈다.
- 위험 균형(동일 위험 기여, Maillard·Roncalli·Teïletche 2010)
- 블랙-리터만(Black·Litterman 1992): 사전 비중에 '견해'(블록33 점수)를 섞는다.
- 점수 × 역변동성: 점수가 높고 덜 흔들리는 종목에 더.
- 변동성 목표(Moreira·Muir 2017): 예상 변동성이 목표보다 크면 전체를 줄이고 나머지는 현금.
- 공분산 축소(Ledoit·Wolf 2004)
금액은 다루지 않는다(비중 %만)."""
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform
from sklearn.covariance import LedoitWolf

ANN = 252


def shrunk_cov(R):
    """공분산 축소(연환산)."""
    X = R.dropna(how='all').fillna(0.0)
    return pd.DataFrame(LedoitWolf().fit(X.values).covariance_ * ANN, index=R.columns, columns=R.columns)


def inverse_vol(cov):
    iv = 1 / np.sqrt(np.diag(cov))
    return pd.Series(iv / iv.sum(), index=cov.index)


def hierarchical_risk_parity(cov):
    """계층적 위험 균형(HRP)."""
    sd = np.sqrt(np.diag(cov))
    corr = cov.values / np.outer(sd, sd)
    dist = np.sqrt(np.clip((1 - corr) / 2, 0, None))
    np.fill_diagonal(dist, 0)
    order = list(cov.index[leaves_list(linkage(squareform(dist, checks=False), 'single'))])
    w = pd.Series(1.0, index=order)
    stack = [order]
    while stack:
        c = stack.pop()
        if len(c) < 2:
            continue
        a, b = c[:len(c) // 2], c[len(c) // 2:]
        va, vb = (_cluster_var(cov, x) for x in (a, b))
        k = 1 - va / (va + vb)
        w[a] *= k
        w[b] *= 1 - k
        stack += [a, b]
    return w.reindex(cov.index)


def _cluster_var(cov, names):
    c = cov.loc[names, names]
    iv = inverse_vol(c)
    return float(iv @ c @ iv)


def risk_parity(cov, iters=500):
    """위험 균형(동일 위험 기여): 고정점 반복."""
    S = cov.values
    w = 1 / np.sqrt(np.diag(S))
    w /= w.sum()
    for _ in range(iters):
        rc = w * (S @ w)
        w_new = w * (rc.mean() / np.maximum(rc, 1e-12)) ** 0.5
        w_new /= w_new.sum()
        if np.abs(w_new - w).max() < 1e-9:
            w = w_new
            break
        w = w_new
    return pd.Series(w, index=cov.index)


def black_litterman(cov, prior, views, tau=0.05, view_scale=0.10, risk_aversion=2.5):
    """블랙-리터만: 사전 비중(prior)에서 균형 수익을 거꾸로 구하고, 종목별 절대 견해(views: 연 기대 초과수익)를 섞어 롱온리로 다시 비중을 낸다.
    views는 블록33 점수(0~1)를 (점수−0.5)×view_scale로 바꾼 값을 넣는다."""
    S = cov.values
    pi = risk_aversion * S @ prior.values
    q = views.reindex(cov.index)
    m = q.notna().values
    if m.any():
        P = np.eye(len(S))[m]
        Q = pi[m] + q.values[m]
        Om = np.diag(np.diag(P @ (tau * S) @ P.T))
        A = np.linalg.inv(tau * S) + P.T @ np.linalg.inv(Om) @ P
        mu = np.linalg.solve(A, np.linalg.inv(tau * S) @ pi + P.T @ np.linalg.inv(Om) @ Q)
    else:
        mu = pi
    w = np.linalg.solve(risk_aversion * S, mu)
    w = np.clip(w, 0, None)
    if w.sum() <= 0:
        return prior
    return pd.Series(w / w.sum(), index=cov.index)


def score_inverse_vol(cov, score):
    s = score.reindex(cov.index).fillna(0).clip(lower=0)
    w = s / np.sqrt(np.diag(cov))
    return w / w.sum() if w.sum() > 0 else inverse_vol(cov)


def cap(w, upper):
    """종목 상한: 넘친 몫을 나머지에 비례해 다시 나눈다."""
    w = w.copy()
    for _ in range(50):
        over = w > upper
        if not over.any():
            break
        extra = (w[over] - upper).sum()
        w[over] = upper
        rest = ~over & (w > 0)
        if not rest.any():
            break
        w[rest] += extra * w[rest] / w[rest].sum()
    return w


def vol_target(w, cov, target):
    """변동성 목표: 예상 변동성이 목표를 넘으면 비중을 줄이고 현금 몫을 돌려준다(위험 자산 비율, 현금 비율)."""
    v = float(np.sqrt(w.values @ cov.loc[w.index, w.index].values @ w.values))
    k = min(1.0, target / v) if v > 0 else 1.0
    return w * k, 1 - k, v


def turnover_limit(new, old, limit):
    """회전율 한도: 지난주 대비 바뀐 양(편도)이 한도를 넘으면 한도만큼만 옮긴다."""
    if old is None or old.empty:
        return new
    idx = new.index.union(old.index)
    n, o = new.reindex(idx).fillna(0), old.reindex(idx).fillna(0)
    t = (n - o).abs().sum() / 2
    if t <= limit or t == 0:
        return n
    return o + (n - o) * (limit / t)
