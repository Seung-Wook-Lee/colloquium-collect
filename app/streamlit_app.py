"""스튜디오 톰앤수 회의 화면 (스트림릿)

드라이브 '콜로키움 수집데이터/1_data/가격10년_시장지표.csv.gz' 한 파일만 읽는다.
수집은 source/market/collect.py가 한다(매일 그날 것만 덧붙임).
7개 자료를 움직이는 차트로, 일봉·주봉·월봉으로 바꿔 본다.
"""
import base64
import io
import json
import os
import sys

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "source", "market"))
import ctm as CTM  # noqa: E402

st.set_page_config(page_title="스튜디오 톰앤수 회의", layout="wide")
st.markdown("<style>html, body, [class*='css'] {font-size: 14px;} h1 {font-size: 1.5rem;} "
            "h3 {font-size: 1.1rem; margin-top: 0.6rem;}</style>", unsafe_allow_html=True)

DB = "콜로키움 수집데이터/1_data/가격10년_시장지표.csv.gz"
RULE = {"일봉": None, "주봉": "W-FRI", "월봉": "ME"}


def secret(k):
    try:
        return st.secrets[k]
    except Exception:
        return os.environ.get(k)


@st.cache_data(ttl=3600, show_spinner="드라이브에서 자료를 읽는 중")
def load():
    body = {"token": secret("DRIVE_TOKEN"), "action": "get", "path": DB}
    out = requests.post(secret("DRIVE_URL"), data=json.dumps(body), timeout=300).json()
    if not out.get("ok") or not out.get("found"):
        raise RuntimeError(out.get("error") or f"없음: {DB}")
    df = pd.read_csv(io.BytesIO(base64.b64decode(out["data"])), compression="gzip", index_col=0)
    df.index = pd.to_datetime(df.index, errors="coerce")
    return df[df.index.notna()].sort_index()


def bar(s, rule):
    s = s.dropna()
    return s if rule is None else s.resample(rule).last().dropna()


def chart(series, title, unit="", lines=(), bands=(), height=330):
    """series: {이름: pd.Series}. lines: (값, 글). bands: (아래, 위, 색, 글)."""
    series = {k: v for k, v in series.items() if len(v)}
    if not series:
        st.info(f"{title}: 아직 자료가 없습니다.")
        return
    fig = go.Figure()
    for lo, hi, color, text in bands:
        fig.add_hrect(y0=lo, y1=hi, fillcolor=color, opacity=0.10, line_width=0,
                      annotation_text=text, annotation_position="left", annotation_font_size=10)
    for name, s in series.items():
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=name, mode="lines", line=dict(width=1.6),
                                 hovertemplate="%{x|%Y-%m-%d}  %{y:.2f}" + unit + "<extra>" + name + "</extra>"))
    for v, text in lines:
        fig.add_hline(y=v, line_dash="dash", line_color="#b91c1c", line_width=1,
                      annotation_text=text, annotation_font_size=10)
    end = max(s.index[-1] for s in series.values())
    fig.update_layout(
        title=dict(text=title, font=dict(size=14), x=0.01, y=0.98, yanchor="top"), height=height + 30,
        margin=dict(l=10, r=10, t=70, b=10), hovermode="x unified",
        legend=dict(orientation="h", x=0, xanchor="left", y=1.02, yanchor="bottom", font=dict(size=11)),
        xaxis=dict(range=[end - pd.DateOffset(years=1), end], rangeslider=dict(visible=True, thickness=0.06),
                   rangeselector=dict(font=dict(size=10), x=1, xanchor="right", y=1.02, yanchor="bottom", buttons=[
                       dict(count=1, label="1개월", step="month", stepmode="backward"),
                       dict(count=3, label="3개월", step="month", stepmode="backward"),
                       dict(count=6, label="6개월", step="month", stepmode="backward"),
                       dict(count=1, label="1년", step="year", stepmode="backward"),
                       dict(count=3, label="3년", step="year", stepmode="backward"),
                       dict(count=5, label="5년", step="year", stepmode="backward"),
                       dict(count=10, label="10년", step="year", stepmode="backward"),
                       dict(label="전체", step="all")])),
        yaxis=dict(fixedrange=False, ticksuffix=unit))
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})


def change_table(s, unit="", digits=2):
    """최근 값, 전일·1주 전·1달 전과 비교 (일봉 기준)."""
    s = s.dropna()
    if s.empty:
        st.caption("자료 없음")
        return
    last_d, last = s.index[-1], s.iloc[-1]
    newest = D.index[D.drop(columns=[c for c in ("공포탐욕",) if c in D.columns]).notna().any(axis=1)][-1]
    if (newest - last_d).days > 3:
        st.error(f"{last_d:%Y-%m-%d} 이후 자료 없음 (다른 자료는 {newest:%Y-%m-%d}까지)")
    rows = [("최근", last_d, last, None)]
    for name, off in (("전일", None), ("1주 전", pd.Timedelta(days=7)), ("1달 전", pd.DateOffset(months=1))):
        p = s.iloc[:-1] if off is None else s[s.index <= last_d - off]
        if len(p):
            rows.append((name, p.index[-1], p.iloc[-1], last - p.iloc[-1]))
    t = pd.DataFrame([{"구분": n, "날짜": d.strftime("%Y-%m-%d"), "값": f"{v:.{digits}f}{unit}",
                       "지금과 차이": "" if c is None else f"{c:+.{digits}f}{unit}"} for n, d, v, c in rows])
    st.dataframe(t, hide_index=True, use_container_width=True)


# ---------------- 화면 ----------------
st.title("스튜디오 톰앤수 회의")
try:
    D = load()
except Exception as e:
    st.error(f"드라이브 자료를 읽지 못했습니다: {e}")
    st.stop()

top = st.columns([3, 2])
freq = top[0].radio("봉", list(RULE), horizontal=True, index=0)
rule = RULE[freq]
top[1].caption(f"자료: 드라이브 가격10년_시장지표 · 마지막 날짜 {D.dropna(how='all').index[-1]:%Y-%m-%d}")

g = lambda k: D[k] if k in D.columns else pd.Series(dtype=float)

# 1. 공포와 탐욕 지수 (CNN 구간: 0~25 극단적 공포, 25~45 공포, 45~55 중립, 55~75 탐욕, 75~100 극단적 탐욕)
st.subheader("1. 공포와 탐욕 지수 (CNN)")
c1, c2 = st.columns([3, 1])
with c1:
    chart({"공포와 탐욕": bar(g("공포탐욕"), rule)}, "공포와 탐욕 지수", bands=[
        (0, 25, "#b91c1c", "극단적 공포"), (25, 45, "#f97316", "공포"), (45, 55, "#9ca3af", "중립"),
        (55, 75, "#65a30d", "탐욕"), (75, 100, "#15803d", "극단적 탐욕")])
with c2:
    change_table(g("공포탐욕"), digits=1)

# 2. CTM
st.subheader("2. CTM (Chande Trend Meter) · S&P500 · 나스닥100")
st.caption("구성은 StockCharts 공개 내용, 무게는 공개되지 않아 추정값(볼린저 위치 8 : RSI 3, 11/22 그림 10곳에 맞춤). "
           "나스닥100은 고가·저가가 없어 종가로 계산. 봉을 바꾸면 그 봉으로 다시 계산.")
ctm_spx = CTM.ctm(g("SPX"), g("SPX_HIGH"), g("SPX_LOW"), rule)
ctm_ndx = CTM.ctm(g("NDX"), None, None, rule)
c1, c2 = st.columns([3, 1])
with c1:
    chart({"S&P500": ctm_spx, "나스닥100": ctm_ndx}, f"CTM ({freq})", height=380)
with c2:
    n = 12
    t = pd.concat([ctm_spx.rename("S&P500"), ctm_ndx.rename("나스닥100")], axis=1).dropna(how="all").tail(n)
    t["S&P500 변화"] = t["S&P500"].diff()
    t["나스닥100 변화"] = t["나스닥100"].diff()
    t = t.iloc[::-1].round(1)
    t.index = t.index.strftime("%Y-%m-%d")
    st.caption(f"최근 {n}개 {freq}")
    st.dataframe(t, use_container_width=True, height=380)
chart({"S&P500": bar(g("SPX"), rule)}, "S&P500 가격", height=260)
chart({"나스닥100": bar(g("NDX"), rule)}, "나스닥100 가격", height=260)

# 3. VIX
st.subheader("3. VIX")
c1, c2 = st.columns([3, 1])
with c1:
    chart({"VIX": bar(g("VIX"), rule)}, "VIX (Cboe)")
with c2:
    change_table(g("VIX"))

# 4. 하이일드 스프레드
st.subheader("4. 하이일드 스프레드")
st.caption("ICE BofA 미국 하이일드 옵션조정 스프레드(FRED BAMLH0A0HYM2). FRED 공개가 최근 3년치뿐.")
c1, c2 = st.columns([3, 1])
with c1:
    chart({"하이일드 스프레드": bar(g("BAMLH0A0HYM2"), rule)}, "하이일드 스프레드", unit="%")
with c2:
    change_table(g("BAMLH0A0HYM2"), unit="%")

# 5. 미국채 10년 금리
st.subheader("5. 미국채 10년 금리")
c1, c2 = st.columns([3, 1])
with c1:
    chart({"10년 금리": bar(g("DGS10"), rule)}, "미국채 10년 금리 (FRED DGS10)", unit="%",
          lines=[(4.8, "의장 기준 4.8%")])
with c2:
    change_table(g("DGS10"), unit="%")

# 6. MOVE
st.subheader("6. MOVE 지수")
c1, c2 = st.columns([3, 1])
with c1:
    chart({"MOVE": bar(g("MOVE"), rule)}, "MOVE 지수 (미국채 변동성)")
with c2:
    change_table(g("MOVE"))

# 7. WTI
st.subheader("7. WTI 유가")
c1, c2 = st.columns([3, 1])
with c1:
    chart({"WTI": bar(g("WTI"), rule)}, "WTI (FRED DCOILWTICO, 달러/배럴)")
with c2:
    change_table(g("WTI"))
