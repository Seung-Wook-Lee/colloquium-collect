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
from plotly.subplots import make_subplots
import requests
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "source", "market"))
import cta as CTA  # noqa: E402

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
        template="plotly_white", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        title=dict(text=title, font=dict(size=14), x=0.01, y=0.98, yanchor="top"), height=height + 30,
        margin=dict(l=10, r=10, t=70, b=10), hovermode="x unified",
        legend=dict(orientation="h", x=0, xanchor="left", y=1.02, yanchor="bottom", font=dict(size=11)),
        xaxis=dict(range=[end - pd.DateOffset(years=1), end], rangeslider=dict(visible=False),
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


def price_cta(name, price, score, freq):
    """위: S&P500 가격, 아래: CTA 포지션 근사(σ) 막대. 두 칸은 날짜 축을 같이 움직인다."""
    price = price.reindex(score.index.union(price.index)).dropna()
    if price.empty or score.empty:
        st.info(f"{name}: 아직 자료가 없습니다.")
        return
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.55, 0.45],
                        subplot_titles=(f"{name} 가격 ({freq})", f"CTA 포지션 근사 (σ, {freq})"))
    fig.add_trace(go.Scatter(x=price.index, y=price.values, name=f"{name} 가격", mode="lines",
                             line=dict(width=1.5, color="#1d4ed8"),
                             hovertemplate="%{x|%Y-%m-%d}  %{y:,.2f}<extra>가격</extra>"), row=1, col=1)
    fig.add_trace(go.Bar(x=score.index, y=score.values, name="CTA σ",
                         marker_color=["#15803d" if v >= 0 else "#b91c1c" for v in score.values],
                         hovertemplate="%{x|%Y-%m-%d}  %{y:.2f}σ<extra>CTA</extra>"), row=2, col=1)
    for v, txt in ((-4, "−4σ 바닥 기준"), (4, "+4σ 고점 기준")):
        fig.add_hline(y=v, line_dash="dash", line_color="#6b7280", line_width=1, annotation_text=txt,
                      annotation_font_size=10, row=2, col=1)
    end = price.index[-1]
    fig.update_layout(template="plotly_white", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", height=560,
                      margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified", showlegend=False, bargap=0.1)
    fig.update_xaxes(range=[end - pd.DateOffset(years=1), end])
    fig.update_xaxes(rangeslider=dict(visible=False))
    fig.update_xaxes(rangeselector=dict(font=dict(size=10), x=1, xanchor="right", y=1.06, buttons=[
        dict(count=1, label="1개월", step="month", stepmode="backward"),
        dict(count=3, label="3개월", step="month", stepmode="backward"),
        dict(count=6, label="6개월", step="month", stepmode="backward"),
        dict(count=1, label="1년", step="year", stepmode="backward"),
        dict(count=3, label="3년", step="year", stepmode="backward"),
        dict(count=10, label="10년", step="year", stepmode="backward"),
        dict(label="전체", step="all")]), row=1, col=1)
    fig.update_yaxes(range=[-6, 6], row=2, col=1)
    fig.update_annotations(font_size=13)
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})


def head(no, name, s, unit="", digits=2):
    """'1-1. 이름 : 날짜 / 숫자' 제목 (마지막 값)"""
    s = s.dropna()
    tail = f" : {s.index[-1]:%Y-%m-%d} / {s.iloc[-1]:,.{digits}f}{unit}" if len(s) else " : 자료 없음"
    st.markdown(f"#### {no}. {name}{tail}")


# ---------------- 화면 ----------------
st.title("스튜디오 톰앤수 회의")
try:
    D = load()
except Exception as e:
    st.error(f"드라이브 자료를 읽지 못했습니다: {e}")
    st.stop()

top = st.columns([1, 1])
freq = top[0].radio("봉", list(RULE), horizontal=True, index=0)
rule = RULE[freq]
top[1].caption(f"자료: 드라이브 가격10년_시장지표 · 마지막 날짜 {D.dropna(how='all').index[-1]:%Y-%m-%d}")

g = lambda k: D[k] if k in D.columns else pd.Series(dtype=float)

# 1. 공포와 탐욕 지수 (CNN 구간: 0~25 극단적 공포, 25~45 공포, 45~55 중립, 55~75 탐욕, 75~100 극단적 탐욕)
st.subheader("1. 마켓")
head("1-1", "공포와 탐욕 지수", g("공포탐욕"), digits=1)
c1, c2 = st.columns([1, 1])
with c1:
    chart({"공포와 탐욕": bar(g("공포탐욕"), rule)}, "공포와 탐욕 지수", bands=[
        (0, 25, "#b91c1c", "극단적 공포"), (25, 45, "#f97316", "공포"), (45, 55, "#9ca3af", "중립"),
        (55, 75, "#65a30d", "탐욕"), (75, 100, "#15803d", "극단적 탐욕")])
with c2:
    change_table(g("공포탐욕"), digits=1)

# 2. CTA
cta_d = CTA.cta(pd.DataFrame({k: g(k) for k in ("SPX", "NDX", "RUT")}))
cta_s = cta_d["CTA σ"]
head("1-2", "CTA (추세추종 펀드) 포지션 근사", cta_s, unit="σ")
st.caption("실제 CTA 포지션은 공개되지 않아 가격으로 흉내 낸 근사 값(σ). S&P500 20%·나스닥100 60%·러셀2000 20%, "
           "2·4·8개월과 1·2·3개월 추세, 2018년 이후 눈금, 시타델 그림 27점에 맞춘 배율. −4σ 바닥·+4σ 고점 기준은 11/23 회의 기준.")
if rule is not None:
    cta_s = cta_s.resample(rule).last().dropna()
c1, c2 = st.columns([1, 1])
with c1:
    price_cta("S&P500", bar(g("SPX"), rule), cta_s, freq)
with c2:
    t = cta_d.tail(12).iloc[::-1].copy()
    t.index = t.index.strftime("%Y-%m-%d")
    t["CTA σ"] = t["CTA σ"].round(2)
    t["CTA σ 5일 변화"] = t["CTA σ 5일 변화"].round(2)
    t["매수 전환까지(%)"] = t["매수 전환까지(%)"].round(1)
    t["추세 신호 매수 수"] = t["추세 신호 매수 수"].astype(int).astype(str) + "/3"
    st.caption("최근 12일 (추세 신호 = S&P500이 21·63·100일 전보다 높은 개수, 매수 전환까지 = 다음 신호가 매수로 바뀌려면 오를 %)")
    st.dataframe(t, use_container_width=True, height=420)

# 3. VIX
head("1-3", "VIX", g("VIX"))
c1, c2 = st.columns([1, 1])
with c1:
    chart({"VIX": bar(g("VIX"), rule)}, "VIX (Cboe)")
with c2:
    change_table(g("VIX"))

# 4. 하이일드 스프레드
head("1-4", "하이일드 스프레드", g("BAMLH0A0HYM2"), unit="%")
st.caption("ICE BofA 미국 하이일드 옵션조정 스프레드(FRED BAMLH0A0HYM2). FRED 공개가 최근 3년치뿐.")
c1, c2 = st.columns([1, 1])
with c1:
    chart({"하이일드 스프레드": bar(g("BAMLH0A0HYM2"), rule)}, "하이일드 스프레드", unit="%")
with c2:
    change_table(g("BAMLH0A0HYM2"), unit="%")

# 5. 미국채 10년 금리
head("1-5", "미국채 10년 금리", g("DGS10"), unit="%")
c1, c2 = st.columns([1, 1])
with c1:
    chart({"10년 금리": bar(g("DGS10"), rule)}, "미국채 10년 금리 (FRED DGS10)", unit="%",
          lines=[(4.8, "의장 기준 4.8%")])
with c2:
    change_table(g("DGS10"), unit="%")

# 6. MOVE
head("1-6", "MOVE 지수", g("MOVE"))
c1, c2 = st.columns([1, 1])
with c1:
    chart({"MOVE": bar(g("MOVE"), rule)}, "MOVE 지수 (미국채 변동성)")
with c2:
    change_table(g("MOVE"))

# 7. WTI
head("1-7", "WTI 유가", g("WTI"), unit="달러")
c1, c2 = st.columns([1, 1])
with c1:
    chart({"WTI": bar(g("WTI"), rule)}, "WTI (FRED DCOILWTICO, 달러/배럴)")
with c2:
    change_table(g("WTI"))
