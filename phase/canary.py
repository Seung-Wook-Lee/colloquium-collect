"""2-15 카나리아(VWO·BND) — Keller·Keuning(2018) 방어적 자산 배분(DAA)의 '카나리아'.
13612W 모멘텀 = (12×1개월 + 4×3개월 + 2×6개월 + 1×12개월 수익률) ÷ 4. 하나라도 0 아래면 '나쁨'(DAA: 방어 자산으로).
여기서는 국면 표시만 한다(산다·사지 않는다 결론은 2-16 규칙이 정함)."""
import pandas as pd

ASSETS = {'VWO': '신흥국 주식', 'BND': '미국 채권 종합'}


def m13612w(px):
    """월말 종가 → 13612W"""
    me = px.resample('ME').last().dropna()
    if len(me) < 13:
        return None
    r = lambda k: me.iloc[-1] / me.iloc[-1 - k] - 1   # noqa: E731
    return float((12 * r(1) + 4 * r(3) + 2 * r(6) + r(12)) / 4)


def run(P=None):
    """P: 일별 종가 DataFrame(VWO·BND 열). 없으면 야후에서 2년치."""
    if P is None or not all(t in P for t in ASSETS):
        import yfinance as yf
        P = yf.download(list(ASSETS), period='2y', auto_adjust=True, progress=False)['Close']
        P.index = pd.to_datetime(P.index).tz_localize(None)
    rows = []
    for t, nm in ASSETS.items():
        v = m13612w(P[t].dropna()) if t in P else None
        rows.append({'자산': t, '이름': nm, '13612W(%)': None if v is None else round(v * 100, 2),
                     '상태': '자료 없음' if v is None else ('나쁨' if v < 0 else '좋음')})
    D = pd.DataFrame(rows)
    bad = (D['상태'] == '나쁨').any()
    return D, ('방어(카나리아 나쁨: ' + ', '.join(D.loc[D['상태'] == '나쁨', '자산']) + ')') if bad else '공격(카나리아 둘 다 좋음)'
