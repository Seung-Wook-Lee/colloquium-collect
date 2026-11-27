"""블록 2 마켓 센터 출력: 시장별 국면 한 줄씩 → 국면.csv (meeting/daily.py가 엔진·원고 뒤에 부른다).
칸: 시장 · 방어 국면(2-14) · 지수 국면 · 시장 블록 부담·기회(2-1~2-10) · 바닥 근접도(2-12) · 카나리아(2-15) · 결론(2-16) · 꺼진 하위 블록."""
import glob
import os

import pandas as pd

from . import canary


def build(IN, W, B, m, M, c=None):
    X = set(B.get('_꺼짐', []))
    rows, extra = [], {}
    can, cs = (None, '적용 안 함') if '2-15' in X else (None, None)
    if cs is None:
        try:
            can, cs = canary.run()
            extra['카나리아.csv'] = can
        except Exception as e:   # noqa: BLE001
            cs = f'계산 실패: {str(e)[:80]}'
    bot = {}
    for p in glob.glob(f'{W}/바닥근접도*.csv'):
        try:
            x = pd.read_csv(p, encoding='utf-8-sig')
            if len(x) and '원점수' in x:
                bot[os.path.basename(p)] = f"{x.iloc[0]['원점수']}(과거 {x.iloc[0].get('과거백분위', '')}백분위)"
        except Exception:   # noqa: BLE001
            pass
    ST = {}
    if c is not None and (c.R or {}).get('결론'):
        try:
            import personas as PER
            _, ST, _ = PER._buy_state(c)
        except Exception:   # noqa: BLE001
            ST = {}
    for mk in ('미국', '한국'):
        Mm = M if M is not None else pd.DataFrame(columns=['방향', '결과'])
        rows.append({'시장': mk,
                     '방어 국면(2-14)': '적용 안 함' if '2-14' in X else ('방어' if m.get(f'DEF_{mk}') else '평상'),
                     '시장 블록 부담': int(((Mm['방향'] == '부담') & (Mm['결과'] == '통과')).sum()) if len(Mm) else None,
                     '시장 블록 기회': int(((Mm['방향'] == '기회') & (Mm['결과'] == '통과')).sum()) if len(Mm) else None,
                     'JPM 추세 신호 전환(2-6)': {1: '예', 0: '아니오'}.get(int(m['SYS_TURN'])) if m.get('SYS_TURN') is not None else '',
                     '바닥 근접도(2-12)': '적용 안 함' if '2-12' in X else ' / '.join(f'{k}: {v}' for k, v in bot.items()),
                     '카나리아(2-15)': cs,
                     '결론(2-16)': '적용 안 함' if '2-16' in X else (ST.get(mk, {}).get('act', '') if ST else ''),
                     '결론 이유': ST.get(mk, {}).get('why', '') if ST else '',
                     '꺼진 하위 블록': ', '.join(k for k in B.get('_꺼짐', []) if k.startswith('2-'))})
    return pd.DataFrame(rows), extra
