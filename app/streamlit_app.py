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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cta as CTA  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "block", "market_index"))
import vote as VOTE  # noqa: E402

import style as S  # noqa: E402

st.set_page_config(page_title="스튜디오 톰앤수 회의", layout="wide")
st.markdown(S.CSS, unsafe_allow_html=True)

DB = "콜로키움 수집데이터/1_data/가격10년_시장지표.csv.gz"
RULE = {"일봉": None, "주봉": "W-FRI", "월봉": "ME"}


def secret(k):
    try:
        return st.secrets[k]
    except Exception:
        return os.environ.get(k)


@st.cache_data(ttl=600, show_spinner="드라이브에서 자료를 읽는 중")
def load(path=DB):
    body = {"token": secret("DRIVE_TOKEN"), "action": "get", "path": path}
    out = requests.post(secret("DRIVE_URL"), data=json.dumps(body), timeout=300).json()
    if not out.get("ok") or not out.get("found"):
        raise RuntimeError(out.get("error") or f"없음: {path}")
    df = pd.read_csv(io.BytesIO(base64.b64decode(out["data"])), compression="gzip", index_col=0)
    df.index = pd.to_datetime(df.index, errors="coerce")
    return df[df.index.notna()].sort_index()


@st.cache_data(ttl=600, show_spinner=False)
def load_flow(path="콜로키움 수집데이터/1_data/가격10년_국내수급.csv.gz"):
    """MI13 외국인 순매수(날짜·코드 줄 형식이라 load()와 따로 읽음)"""
    body = {"token": secret("DRIVE_TOKEN"), "action": "get", "path": path}
    out = requests.post(secret("DRIVE_URL"), data=json.dumps(body), timeout=300).json()
    if not out.get("ok") or not out.get("found"):
        raise RuntimeError(out.get("error") or f"없음: {path}")
    return pd.read_csv(io.BytesIO(base64.b64decode(out["data"])), compression="gzip", dtype={"코드": str, "날짜": str})


def bar(s, rule):
    s = s.dropna()
    return s if rule is None else s.resample(rule).last().dropna()


AXIS = dict(showgrid=True, gridcolor=S.GRID, zeroline=False, linecolor="#d1d5db", tickfont=dict(size=11, color=S.MUTED))
FONT = dict(family="Noto Sans KR, sans-serif", size=12, color="#111827")
CONFIG = {"displayModeBar": False, "scrollZoom": False}
PERIOD = {"1개월": pd.DateOffset(months=1), "3개월": pd.DateOffset(months=3), "6개월": pd.DateOffset(months=6),
          "1년": pd.DateOffset(years=1), "3년": pd.DateOffset(years=3), "5년": pd.DateOffset(years=5),
          "10년": pd.DateOffset(years=10), "전체": None}


def period(key, default="3년"):
    """그래프 위 기간 단추. 고른 기간만 잘라 그려서 세로 눈금이 그 기간에 맞게 잡힌다.
    처음 값 3년(의장 11/27), 공포와 탐욕 지수만 1년."""
    v = st.segmented_control("기간", list(PERIOD), default=default, key=f"p_{key}", label_visibility="collapsed")
    return PERIOD[v or default]


def cut(s, off):
    s = s.dropna()
    return s if off is None or s.empty else s[s.index >= s.index[-1] - off]


def yrange(*ss, pad=0.06):
    v = pd.concat([x.dropna() for x in ss])
    lo, hi = float(v.min()), float(v.max())
    d = (hi - lo) * pad or abs(hi) * 0.05 or 1
    return [lo - d, hi + d]


def chart(series, title, unit="", lines=(), bands=(), height=330, key=None, yfix=None, default="3년"):
    """series: {이름: pd.Series}. lines: (값, 글). bands: (아래, 위, 색, 글)."""
    series = {k: v for k, v in series.items() if len(v)}
    if not series:
        st.info(f"{title}: 아직 자료가 없습니다.")
        return
    off = period(key or title, default)
    series = {k: cut(v, off) for k, v in series.items()}
    fig = go.Figure()
    for lo, hi, color, text in bands:
        fig.add_hrect(y0=lo, y1=hi, fillcolor=color, opacity=0.09, line_width=0, layer="below",
                      annotation_text=text, annotation_position="left", annotation_font=dict(size=10, color=S.MUTED))
    for name, s in series.items():
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=name, mode="lines", line=dict(width=1.8, color=S.LINE),
                                 hovertemplate="%{x|%Y-%m-%d}  %{y:,.2f}" + unit + "<extra></extra>"))
        fig.add_trace(go.Scatter(x=[s.index[-1]], y=[s.values[-1]], mode="markers", hoverinfo="skip",
                                 marker=dict(size=7, color=S.LINE, line=dict(width=2, color="#ffffff"))))
    for v, text in lines:
        fig.add_hline(y=v, line_dash="dot", line_color=S.UP, line_width=1.2, annotation_text=text,
                      annotation_font=dict(size=10, color=S.UP))
    yr = yfix or yrange(*series.values(), pd.Series([v for v, _ in lines], dtype=float))
    fig.update_layout(
        template="plotly_white", font=FONT, paper_bgcolor="#ffffff", plot_bgcolor=S.PLOT_BG, height=height,
        title=dict(text=title, font=dict(size=13, color="#374151"), x=0.0, y=0.98, yanchor="top"),
        margin=dict(l=8, r=8, t=36, b=8), hovermode="x unified", showlegend=False, dragmode=False,
        hoverlabel=dict(bgcolor="#111827", font=dict(color="#ffffff", size=12), bordercolor="#111827"),
        xaxis=dict(AXIS, rangeslider=dict(visible=False), fixedrange=True),
        yaxis=dict(AXIS, ticksuffix=unit, side="right", range=yr, fixedrange=True))
    st.plotly_chart(fig, width="stretch", config=CONFIG)


def change_table(s, unit="", digits=2):
    """최근 값, 전일·1주 전·1달 전·3달 전·1년 전과 비교 (일봉 기준)."""
    s = s.dropna()
    if s.empty:
        st.caption("자료 없음")
        return
    last_d, last = s.index[-1], s.iloc[-1]
    newest = D.index[D.drop(columns=[c for c in ("공포탐욕",) if c in D.columns]).notna().any(axis=1)][-1]
    if (newest - last_d).days > 3:
        st.markdown(f"<div class='warn'>{last_d:%Y-%m-%d} 이후 자료 없음 (다른 자료는 {newest:%Y-%m-%d}까지)</div>",
                    unsafe_allow_html=True)
    rows = [{"구분": "최근", "날짜": f"{last_d:%Y-%m-%d}", "값": f"{last:,.{digits}f}{unit}", "지금과 차이": ""}]
    for name, off in (("전일", None), ("1주 전", pd.Timedelta(days=7)), ("1달 전", pd.DateOffset(months=1)),
                      ("3달 전", pd.DateOffset(months=3)), ("1년 전", pd.DateOffset(years=1))):
        p = s.iloc[:-1] if off is None else s[s.index <= last_d - off]
        if len(p):
            c = last - p.iloc[-1]
            rows.append({"구분": name, "날짜": f"{p.index[-1]:%Y-%m-%d}", "값": f"{p.iloc[-1]:,.{digits}f}{unit}",
                         "지금과 차이": f"{c:+,.{digits}f}{unit}".replace("-", "−")})
    st.markdown(S.table(pd.DataFrame(rows), color_cols=("지금과 차이",), dim_cols=("날짜",)), unsafe_allow_html=True)


def price_cta(name, price, score, freq):
    """위: S&P500 가격, 아래: CTA 근사값(σ) 막대. 두 칸은 날짜 축을 같이 움직인다."""
    price = price.reindex(score.index.union(price.index)).dropna()
    if price.empty or score.empty:
        st.info(f"{name}: 아직 자료가 없습니다.")
        return
    off = period("cta")
    price, score = cut(price, off), cut(score, off)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.55, 0.45],
                        subplot_titles=(f"{name} ({freq})", f"CTA 근사값 σ ({freq})"))
    fig.add_trace(go.Scatter(x=price.index, y=price.values, mode="lines", line=dict(width=1.8, color=S.LINE),
                             hovertemplate="%{x|%Y-%m-%d}  %{y:,.2f}<extra>S&P500</extra>"), row=1, col=1)
    fig.add_trace(go.Bar(x=score.index, y=score.values, marker_line_width=0,
                         marker_color=[S.UP if v >= 0 else S.DOWN for v in score.values],
                         hovertemplate="%{x|%Y-%m-%d}  %{y:.2f}σ<extra>CTA</extra>"), row=2, col=1)
    for v, txt in ((-4, "−4σ 바닥"), (4, "+4σ 고점")):
        fig.add_hline(y=v, line_dash="dot", line_color=S.MUTED, line_width=1, annotation_text=txt,
                      annotation_font=dict(size=10, color=S.MUTED), row=2, col=1)
    for v in (-3.5, 3.5):  # 의장 11/27: ±3.5σ부터 주의 (점선 하나 더)
        fig.add_hline(y=v, line_dash="dash", line_color="#b6bcc6", line_width=0.8,
                      annotation_text=f"{v:+.1f}σ".replace("-", "−"), annotation_position="top left",
                      annotation_font=dict(size=9, color="#9ca3af"), row=2, col=1)
    fig.update_layout(template="plotly_white", font=FONT, paper_bgcolor="#ffffff", plot_bgcolor=S.PLOT_BG,
                      height=560, margin=dict(l=8, r=8, t=30, b=8), hovermode="x unified", showlegend=False,
                      bargap=0.15, dragmode=False,
                      hoverlabel=dict(bgcolor="#111827", font=dict(color="#ffffff", size=12)))
    fig.update_xaxes(AXIS, rangeslider=dict(visible=False), fixedrange=True)
    fig.update_yaxes(AXIS, side="right", fixedrange=True)
    fig.update_yaxes(range=[-6, 6], ticksuffix="σ", row=2, col=1)
    fig.update_yaxes(range=yrange(price), row=1, col=1)
    fig.update_annotations(selector=dict(xref="paper", yref="paper"), font=dict(size=13, color="#374151"),
                           x=0, xanchor="left")
    st.plotly_chart(fig, width="stretch", config=CONFIG)


def head(no, name, s, unit="", digits=2, note=""):
    """'1-1. 이름 : 날짜 / 숫자' 제목 (마지막 값, 전일 대비)"""
    s = s.dropna()
    if len(s):
        chg = ""
        if len(s) > 1:
            c = s.iloc[-1] - s.iloc[-2]
            cls = S.UP if c > 0 else (S.DOWN if c < 0 else S.MUTED)
            chg = f"<span class='chg' style='color:{cls}'>{'▲' if c > 0 else ('▼' if c < 0 else '')} {abs(c):,.{digits}f}</span>"
        tail = (f"<span class='dt'>: {s.index[-1]:%Y-%m-%d} /</span>"
                f"<span class='val'>{s.iloc[-1]:,.{digits}f}{unit}</span>{chg}")
    else:
        tail = "<span class='dt'>: 자료 없음</span>"
    st.markdown(f"<div class='hd'><span class='no'>{f'{no}. ' if no else ''}{name}</span>{tail}</div>"
                + (f"<div class='note'>{note}</div>" if note else ""), unsafe_allow_html=True)


def item(no, name, s, unit="", digits=2, note="", **kw):
    """한 칸: 제목 + 왼쪽 그래프 + 오른쪽 표"""
    with st.container(border=True, key=f"card_{no}_{name}"):
        head(no, name, s, unit, digits, note)
        c1, c2 = st.columns([1, 1], gap="medium")
        with c1:
            chart({name: bar(s, rule)}, kw.pop("title", name), unit=unit, key=f"{no}_{name}", **kw)
        with c2:
            change_table(s, unit=unit, digits=digits)


# ---------------- 화면 ----------------
st.title("스튜디오 톰앤수 회의")
try:
    D = load()
except Exception as e:
    st.error(f"드라이브 자료를 읽지 못했습니다: {e}")
    st.stop()

top = st.columns([2, 2, 1])
freq = top[0].radio("봉", list(RULE), horizontal=True, index=0, label_visibility="collapsed")
rule = RULE[freq]
top[1].caption(f"자료: 드라이브 가격10년_시장지표 · 마지막 날짜 {D.dropna(how='all').index[-1]:%Y-%m-%d}")
if top[2].button("자료 다시 읽기", width="stretch"):
    load.clear()
    st.rerun()

g = lambda k: D[k] if k in D.columns else pd.Series(dtype=float)

st.subheader("1. 마켓 (Market Index)")


def lights(D, P, F=None):
    """MI 초록불 표: 바닥 조건에 맞으면 🟢, 아니면 ⚪, 자료 없으면 빈칸 (block/market_index/vote.py)"""
    us = VOTE.table(D)
    try:
        kr = VOTE.table_kr(D, P, F)
    except Exception:
        kr = None
    vals = VOTE.values(D, P)
    dot = lambda x: "" if pd.isna(x) else ("🟢" if x >= 1 else "⚪")
    fmt = {"MI01": "{:.1f}", "MI02": "{:+.2f}σ", "MI03": "{:.2f}", "MI04": "{:.2f}%", "MI05": "{:+.2f}%p",
           "MI06": "{:.1f}", "MI07": "{:.2f}달러", "MI08": "{:+.1f}%", "MI10": "{:.2f}", "MI11": "{:.2f}",
           "MI12": "{:.1f}"}
    rows = []
    for no, name, rule_txt in VOTE.RULES:
        v = vals.get(no, pd.Series(dtype=float)).dropna()
        if no == "MI13":
            if F is None:
                val, dt = "자료 없음", ""
            else:
                full, _ = VOTE.foreign_week(F)
                val = f"이번 주 {full.iloc[-1]:+,.0f}억 · 전주 {full.iloc[-2]:+,.0f}억"
                dt = f"{pd.to_datetime(F['날짜'].astype(str)).max():%m-%d}"
        elif no == "MI08":
            parts = [("S&P", vals["MI08"]), ("나스닥", vals["MI08 나스닥100"]),
                     ("코스피", vals.get("MI08 코스피", pd.Series(dtype=float)))]
            val = " · ".join(f"{n} {s.dropna().iloc[-1]:+.1f}%" for n, s in parts if len(s.dropna()))
            dt = f"{vals['MI08'].dropna().index[-1]:%m-%d}"
        else:
            val = fmt[no].format(v.iloc[-1]) if len(v) else "자료 없음"
            dt = f"{v.index[-1]:%m-%d}" if len(v) else ""
        rows.append({"번호": no, "지표": name, "초록불 기준": rule_txt, "최근 값": val, "날짜": dt,
                     "미국": "" if no in ("MI12", "MI13") else dot(us[no].iloc[-1]) if no in us else "",
                     "한국": dot(kr[no].iloc[-1]) if kr is not None and no in kr else ""})
    st.markdown(S.table(pd.DataFrame(rows), dim_cols=("날짜",)), unsafe_allow_html=True)
    # 최근 10거래일 켜진 비율
    r = pd.DataFrame({"미국": us["켜진 비율"], "한국": kr["켜진 비율"] if kr is not None else None}).dropna(how="all")
    r = r.tail(10).iloc[::-1]
    cnt = lambda t, d: f"{int(t.at[d, '켜진 수'])}/{int(t.at[d, '자료 수'])}" if t is not None and d in t.index and pd.notna(t.at[d, '켜진 수']) else ""
    tt = pd.DataFrame({"날짜": r.index.strftime("%Y-%m-%d"),
                       "미국 켜진 비율": [f"{x:.1f}% ({cnt(us, d)})" if pd.notna(x) else "" for d, x in r["미국"].items()],
                       "한국 켜진 비율": [f"{x:.1f}% ({cnt(kr, d)})" if pd.notna(x) else "" for d, x in r["한국"].items()]})
    return tt


with st.container(border=True, key="card_mi_lights"):
    st.markdown("<div class='hd'><span class='no'>MI 초록불</span></div>"
                "<div class='note'>바닥 조건에 맞으면 🟢 · 켜진 비율 = 켜진 수 ÷ 자료가 있는 기준 수 · "
                "미국 10개(MI01~MI08·MI10·MI11), 한국 12개(MI08은 코스피, MI12·MI13 더함) · MI09 뺌 · "
                "MI14·MI15 기준 정하는 중</div>", unsafe_allow_html=True)
    try:
        try:
            F = load_flow()
        except Exception:
            F = None
        tt = lights(D, load("콜로키움 수집데이터/1_data/가격10년_종가.csv.gz"), F)
        st.markdown("<div class='note' style='margin-top:14px'>최근 10거래일 켜진 비율</div>", unsafe_allow_html=True)
        st.markdown(S.table(tt), unsafe_allow_html=True)
    except Exception as e:
        st.error(f"초록불 계산 실패: {e}")
# 1-1 공포와 탐욕 (CNN 구간: 0~25 극단적 공포, 25~45 공포, 45~55 중립, 55~75 탐욕, 75~100 극단적 탐욕)
item("MI01", "공포와 탐욕 지수", g("공포탐욕"), digits=1, title="공포와 탐욕 지수 (CNN)", yfix=[0, 100], default="1년", bands=[
    (0, 25, "#dc2626", "극단적 공포"), (25, 45, "#f97316", "공포"), (45, 55, "#9ca3af", "중립"),
    (55, 75, "#84cc16", "탐욕"), (75, 100, "#16a34a", "극단적 탐욕")])

# 1-2 CTA
cta_d = CTA.cta(pd.DataFrame({k: g(k) for k in ("SPX", "NDX", "RUT")}))
cta_s = cta_d["CTA σ"]
with st.container(border=True, key="card_1-2"):
    head("MI02", "CTA 근사값", cta_s, unit="σ",
         note="S&P500 20%·나스닥100 60%·러셀2000 20% 가격 추세로 계산. −4σ 바닥·+4σ 고점 기준(11/23 회의), ±3.5σ부터 주의(11/27).")
    cs = cta_s if rule is None else cta_s.resample(rule).last().dropna()
    c1, c2 = st.columns([1, 1], gap="medium")
    with c1:
        price_cta("S&P500", bar(g("SPX"), rule), cs, freq)
    with c2:
        t = cta_d.tail(14).iloc[::-1]
        tt = pd.DataFrame({"날짜": t.index.strftime("%Y-%m-%d"),
                           "CTA σ": [f"{v:+.2f}".replace("-", "−") for v in t["CTA σ"]],
                           "5일 변화": [f"{v:+.2f}".replace("-", "−") for v in t["CTA σ 5일 변화"]],
                           "추세 신호 매수 수": [f"{int(v)}/3" for v in t["추세 신호 매수 수"]]})
        st.markdown("<div class='note'>최근 14일 · 추세 신호 = S&P500이 21·63·100일 전보다 높은 개수</div>",
                    unsafe_allow_html=True)
        st.markdown(S.table(tt, color_cols=("CTA σ", "5일 변화")), unsafe_allow_html=True)

item("MI03", "VIX", g("VIX"), title="VIX (Cboe)")
item("MI04", "하이일드 스프레드", g("BAMLH0A0HYM2"), unit="%",
     note="ICE BofA 미국 하이일드 옵션조정 스프레드(FRED BAMLH0A0HYM2). FRED 공개가 최근 3년치뿐.")
item("MI05", "미국채 10년 금리", g("DGS10"), unit="%", title="미국채 10년 금리 (FRED DGS10)")
item("MI05", "10년 금리 − 연준 기준금리", VOTE.rate_gap(D), unit="%p", title="10년 금리 − 연준 기준금리 (IOER→IORB)",
     lines=[(0.52, "+0.52%p 이상 초록불")])
item("MI06", "MOVE 지수", g("MOVE"), title="MOVE 지수 (미국채 변동성)")
item("MI07", "WTI 유가", g("WTI"), title="WTI (FRED DCOILWTICO, 달러/배럴)")
# 고객예탁금: 값만 보여 줌(의장 11/27). 신용잔고는 의장 11/27 20:06 "기준에서 빼세요"로 화면에서 뺌(수집은 계속).
item("", "고객예탁금", g("고객예탁금"), unit="억원", digits=0, title="고객예탁금 (억원)",
     note="한투 증시자금 종합(금융투자협회 자료). 기준 없이 값만 봅니다.")


# ---------------- 2. 종목 ----------------
PX = "콜로키움 수집데이터/1_data/가격10년_종가.csv.gz"
US = [("SPYM", "SPYM"), ("QQQM", "QQQM"), ("NVDA", "NVDA"), ("AAPL", "AAPL"), ("MSFT", "MSFT"), ("META", "META"),
      ("AMZN", "AMZN"), ("MU", "MU"), ("MRVL", "MRVL"), ("JNJ", "JNJ"), ("LLY", "LLY"), ("KO", "KO"), ("BLK", "BLK"),
      ("JPM", "JPM"), ("SPCX", "SPCX"), ("TSLA", "TSLA"), ("SOXQ", "SOXQ")]
KR = [("005930.KS", "삼성전자"), ("000660.KS", "SK하이닉스"), ("009150.KS", "삼성전기"), ("005380.KS", "현대차"),
      ("006400.KS", "삼성SDI"), ("278470.KS", "에이피알"), ("298040.KS", "효성중공업"), ("316140.KS", "우리금융지주"),
      ("033780.KS", "KT&G"), ("282330.KS", "BGF리테일")]


def rsi14(c):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def last_val(V, t):
    if V is None or t not in V.columns:
        return float("nan")
    v = V[t].dropna()
    return v.iloc[-1] if len(v) else float("nan")


def fmt(v, d=2):
    return "" if pd.isna(v) else f"{v:,.{d}f}"


def stock_table(P, VAL, names, money):
    rows = []
    for t, n in names:
        c = P[t].dropna() if t in P.columns else pd.Series(dtype=float)
        if len(c) < 2:
            rows.append({"종목": n, "날짜": "", "가격": "자료 없음", "전일 대비": "", "PER": "", "EPS": "", "PEG": "",
                         "RSI(14일)": ""})
            continue
        ch = (c.iloc[-1] / c.iloc[-2] - 1) * 100
        rows.append({"종목": n, "날짜": f"{c.index[-1]:%m-%d}", "가격": money(c.iloc[-1]),
                     "전일 대비": f"{ch:+.2f}%".replace("-", "−"),
                     "PER": fmt(last_val(VAL["PER"], t), 1), "EPS": money(last_val(VAL["EPS"], t))
                     if not pd.isna(last_val(VAL["EPS"], t)) else "",
                     "PEG": fmt(last_val(VAL["PEG"], t), 2), "RSI(14일)": f"{rsi14(c).iloc[-1]:.1f}"})
    st.markdown(S.table(pd.DataFrame(rows), color_cols=("전일 대비",), dim_cols=("날짜",)),
                unsafe_allow_html=True)


st.subheader("2. 종목")
try:
    P = load(PX)
except Exception as e:
    st.error(f"종가 파일을 읽지 못했습니다: {e}")
    st.stop()
VAL = {}
for k in ("PER", "EPS", "PEG"):
    try:
        VAL[k] = load(f"콜로키움 수집데이터/1_data/가격10년_{k}.csv.gz")
    except Exception:
        VAL[k] = None
with st.container(border=True, key="card_2-1"):
    st.markdown("<div class='hd'><span class='no'>2-1. 주요 종목 상황</span></div>"
                "<div class='note'>가격 = 드라이브 10년치 종가 파일 마지막 값 · 전일 대비 = 앞 거래일 종가 대비 · "
                "PER·EPS = 한투, PEG = PER ÷ EPS 증가율(최근 사업연도, 미국은 SEC 공시, 증가율 0 이하면 빈칸) · "
                "RSI = 14일 와일더 방식</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1], gap="medium")
    with c1:
        st.markdown("<div class='note'><b>미국</b> (달러)</div>", unsafe_allow_html=True)
        stock_table(P, VAL, US, lambda v: f"{v:,.2f}")
    with c2:
        st.markdown("<div class='note'><b>한국</b> (원)</div>", unsafe_allow_html=True)
        stock_table(P, VAL, KR, lambda v: f"{v:,.0f}")
