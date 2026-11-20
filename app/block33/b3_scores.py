"""블록 3 Analysis 출력: 종목별 단기·중기·장기 점수 → 종목점수.csv (블록 4 portfolio가 읽는 자리).
기간 묶음은 비공개 subblocks.yaml 블록3 번호표의 '기간'(단기 4주·중기 26주·장기 52주 이상, 재편안 표준 근거).
점수 = 그 기간 하위 블록 점수(0~1)의 평균. 꺼진 하위 블록·자료 없는 블록은 빼고 평균."""
import pandas as pd


def build(S, B):
    T = (B.get('_하위블록') or {}).get('블록3', {}).get('번호', {})
    X = set(B.get('_꺼짐', []))
    per = {}
    for num, v in T.items():
        if v.get('블록') and v.get('기간') and num not in X:
            per.setdefault(v['기간'], []).append(v['블록'])
    cols = ['번호', '종목', '시장', '구분'] + [k for k in ('층L', '추천', '원칙', '순위점수') if k in S]
    out = S[cols].copy()
    for p in ('단기', '중기', '장기'):
        bs = [b for b in per.get(p, []) if b in S]
        out[f'{p} 점수'] = S[bs].apply(pd.to_numeric, errors='coerce').mean(axis=1).round(3) if bs else None
        out[f'{p} 블록'] = ', '.join(bs)
    return out
