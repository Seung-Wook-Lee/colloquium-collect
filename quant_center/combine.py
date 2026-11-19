"""블록 점수 합산(Rob Carver pysystemtrade 방식): 블록마다 점수를 같은 눈금으로 맞추고, 가중 평균한 뒤 분산 승수로 보정.

1) 블록 점수 sc(0~1, 공식 통과 비율) → s = (sc − 0.5) × 20  (−10 ~ +10)
2) 눈금 맞추기(forecast scalar): 블록마다 전 종목 |s| 평균이 10이 되도록 k = 10 / 평균|s|, k는 [1/상한, 상한]으로 자름.
   s' = k × s 를 ±점수상한(20)으로 자름.
3) 종목마다 그 종목에 점수가 있는 블록만 가중(blocks.yaml '가중', 기본 1)으로 평균.
4) 분산 승수(FDM) = 1 / sqrt(wᵀ C w). C = 블록 점수 간 상관(전 종목 단면, 음수는 0으로, 표본 부족은 1로 = 보수적).
   블록끼리 같은 말을 하면(상관 높음) 승수 ≈ 1, 서로 다른 말을 하면 승수가 커진다. 상한 '분산승수_상한'.
5) 종합점수 = clip(평균 × FDM, ±점수상한).
"""
import numpy as np
import pandas as pd


def scale(SC, cfg):
    """SC: 종목 × 블록 점수(0~1, 없으면 NaN). 반환: 눈금 맞춘 점수(−20~+20), 블록별 눈금 k."""
    cap = cfg.get('점수상한', 20); kmax = cfg.get('눈금_상한', 2.0); tgt = cfg.get('평균크기', 10)
    s = (SC.astype(float) - 0.5) * 20
    k = {}
    for c in s.columns:
        a = s[c].abs().mean()
        k[c] = 1.0 if (pd.isna(a) or a == 0) else float(np.clip(tgt / a, 1 / kmax, kmax))
    return (s * pd.Series(k)).clip(-cap, cap), k


def corr(S, min_n=20):
    C = S.corr(min_periods=min_n).clip(lower=0)
    return C.fillna(1.0).values   # 상관을 모르면 같은 말을 한다고 보고(1) 승수를 키우지 않음


def combine(SC, W, cfg):
    """SC: 종목 × 블록 점수(0~1). W: 블록별 가중 dict. 반환 DataFrame[종합점수, 분산승수, 합산블록수], 블록 눈금 dict."""
    S, k = scale(SC, cfg)
    C = corr(S, cfg.get('상관_최소표본', 20))
    fmax = cfg.get('분산승수_상한', 2.5); cap = cfg.get('점수상한', 20)
    w_all = np.array([float(W.get(c, 1)) for c in S.columns])
    out = []
    for _, row in S.iterrows():
        m = row.notna().values
        if not m.any():
            out.append((np.nan, np.nan, 0)); continue
        w = w_all[m] / w_all[m].sum()
        avg = float((row.values[m] * w).sum())
        q = float(w @ C[np.ix_(m, m)] @ w)
        fdm = min(fmax, 1 / np.sqrt(q)) if q > 0 else 1.0
        out.append((float(np.clip(avg * fdm, -cap, cap)), round(fdm, 3), int(m.sum())))
    R = pd.DataFrame(out, index=SC.index, columns=['종합점수', '분산승수', '합산블록수'])
    R['종합점수'] = R['종합점수'].round(2)
    return R, k
