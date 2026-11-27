"""스트림릿 화면 모양 (색·글꼴·표)

색 기준: 한국 주식 관례대로 상승 = 빨강, 하락 = 파랑. 가격 선은 상승·하락 색과 겹치지 않게 짙은 회색.
"""
import html

import pandas as pd

UP = "#e0313b"      # 상승
DOWN = "#1f5fd6"    # 하락
LINE = "#1f2937"    # 가격·지수 선
FILL = "rgba(31,41,55,0.06)"
GRID = "#eceff3"
PLOT_BG = "#fbfbfd"
MUTED = "#6b7280"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stCaption, button, input {font-family: 'Noto Sans KR', sans-serif !important;}
.stApp {background: #f4f6f9;}
.block-container {padding-top: 2.2rem; max-width: 1500px;}
h1 {font-size: 1.45rem !important; font-weight: 700; color: #111827; letter-spacing: -0.02em;}
h3 {font-size: 1.15rem !important; font-weight: 700; color: #111827; margin-top: 1.4rem !important;
    padding-bottom: 0.35rem; border-bottom: 2px solid #111827;}
div[class*="st-key-card"] {padding: 18px 20px !important;background: #ffffff; border: 1px solid #e5e7eb !important;
    border-radius: 12px; box-shadow: 0 1px 3px rgba(17,24,39,0.05);}
.hd {display: flex; align-items: baseline; gap: 0.7rem; margin: 0.1rem 0 0.2rem 0;}
.hd .no {font-size: 0.95rem; font-weight: 700; color: #111827;}
.hd .dt {font-size: 0.8rem; color: #6b7280;}
.hd .val {font-size: 1.25rem; font-weight: 700; color: #111827;}
.hd .chg {font-size: 0.85rem; font-weight: 600;}
.note {font-size: 0.75rem; color: #6b7280; margin: 0 0 0.4rem 0;}
table.t {width: 100%; border-collapse: collapse; font-size: 0.8rem; background: #ffffff; border: none !important; margin: 0;}
table.t th, table.t td {border-left: none !important; border-right: none !important; border-top: none !important;}
table.t th {background: #f3f4f6; color: #374151; font-weight: 600; text-align: right; padding: 7px 10px;
    border-bottom: 1px solid #e5e7eb; white-space: nowrap;}
table.t th:first-child, table.t td:first-child {text-align: left;}
table.t td {background: #ffffff !important; padding: 7px 10px; text-align: right; border-bottom: 1px solid #f0f1f4; color: #111827;
    font-variant-numeric: tabular-nums; white-space: nowrap;}
table.t tr:last-child td {border-bottom: none;}
table.t tr:hover td {background: #fafafa;}
table.t td.up {color: #e0313b; font-weight: 600;}
table.t td.down {color: #1f5fd6; font-weight: 600;}
table.t td.dim {color: #9ca3af;}
div[data-testid="stButtonGroup"] button {min-height: 26px !important; padding: 0 10px !important; font-size: 0.75rem !important;}
div[data-testid="stButtonGroup"] button p {font-size: 0.75rem !important;}
.gauge {padding: 4px 2px;}
.jump {display: flex; gap: 8px; margin: -0.4rem 0 1rem 0; position: sticky; top: 3.2rem; z-index: 50;}
.jump a {font-size: 0.85rem; font-weight: 600; color: #111827 !important; text-decoration: none !important;
         background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 6px 14px;}
.jump a:hover {background: #f3f4f6; border-color: #d1d5db;}
.anchor {scroll-margin-top: 4rem;}
.mkt-h {font-size: 1.15rem !important; font-weight: 700; display: flex; align-items: center; gap: 16px; flex-wrap: wrap;}
.top-alert {font-size: 1.35rem; font-weight: 800; color: #ffffff; background: #e0313b; padding: 4px 14px;
            border-radius: 8px; letter-spacing: -0.01em;}
.tl {display: inline-flex; gap: 4px; align-items: center; padding: 4px 6px; margin-right: 10px; background: #1f2937;
     border-radius: 12px; vertical-align: middle; position: relative; top: -2px;}
.tl i {width: 13px; height: 13px; border-radius: 50%; display: inline-block; background: #4b5563;}
.tl i.tl-g.lit {background: #22c55e; box-shadow: 0 0 8px 2px rgba(34,197,94,.75);}
.tl i.tl-r.lit {background: #ef4444; box-shadow: 0 0 8px 2px rgba(239,68,68,.75);}
.gauge .g-top {display: flex; justify-content: space-between; align-items: baseline;}
.gauge .g-name {font-size: 0.95rem; font-weight: 700; color: #111827;}
.gauge .g-dt {font-size: 0.75rem; color: #9ca3af;}
.gauge .g-val {font-size: 3rem; font-weight: 700; color: #111827; line-height: 1.1; margin-top: 6px; letter-spacing: -0.03em;}
.gauge .g-unit {font-size: 1.3rem; font-weight: 600; color: #6b7280; margin-left: 2px;}
.gauge .g-sub {font-size: 0.78rem; color: #6b7280; margin: 4px 0 10px 0;}
.gauge .g-bar {height: 10px; background: #eef0f3; border-radius: 6px; overflow: hidden;}
.gauge .g-fill {height: 100%; background: linear-gradient(90deg, #4ade80, #16a34a); border-radius: 6px;}
.gauge .g-list {margin-top: 14px; display: grid; grid-template-columns: 1fr 1fr; gap: 5px;}
.g-row {display: flex; align-items: center; gap: 6px; font-size: 0.74rem; padding: 6px 8px; border-radius: 7px;
        border-left: 4px solid; min-width: 0;}
.g-row .g-no {font-weight: 700; font-variant-numeric: tabular-nums; flex: none;}
.g-row .g-nm {white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0;}
.g-row .g-lab {font-weight: 700; flex: none; font-size: 0.7rem;}
.g-row.on {background: rgba(34,197,94,0.18); border-color: #22c55e; color: #dcfce7;}
.g-row.on .g-lab {color: #4ade80;}
.g-row.off {background: rgba(239,68,68,0.13); border-color: #ef4444; color: #fecaca;}
.g-row.off .g-lab {color: #f87171;}
.g-row.na {background: rgba(255,255,255,0.05); border-color: #64748b; color: #94a3b8;}
/* 맨 위 '지금 바닥 근처인가?' 칸: 어두운 배경으로 아래 칸과 구분 */
div.st-key-card_mi_lights {background: linear-gradient(160deg, #0f172a 0%, #1e293b 100%) !important;
    border: 1px solid #0f172a !important; box-shadow: 0 6px 18px rgba(15,23,42,0.25) !important;}
div.st-key-card_mi_lights .hd .no {color: #f8fafc; font-size: 1.15rem;}
div.st-key-card_mi_lights .note {color: #94a3b8;}
div.st-key-card_mi_lights .gauge .g-name {color: #f8fafc;}
div.st-key-card_mi_lights .gauge .g-dt {color: #94a3b8;}
div.st-key-card_mi_lights .gauge .g-val {color: #ffffff;}
div.st-key-card_mi_lights .gauge .g-unit {color: #94a3b8;}
div.st-key-card_mi_lights .gauge .g-sub {color: #cbd5e1;}
div.st-key-card_mi_lights .gauge .g-bar {background: rgba(255,255,255,0.1);}
div.st-key-card_mi_lights div[data-testid="stButtonGroup"] button {background: rgba(255,255,255,0.06); color: #e5e7eb;
    border-color: rgba(255,255,255,0.15);}
.warn {background: #fff1f2; color: #b91c1c; border-radius: 8px; padding: 6px 10px; font-size: 0.8rem; margin-bottom: 6px;}
</style>
"""


def sign_class(v):
    s = str(v).strip()
    if s.startswith("+") and s.strip("+0.%σ달러") != "":
        return "up"
    if s.startswith("-") or s.startswith("−"):
        return "down"
    return ""


def table(df, color_cols=(), dim_cols=()):
    """DataFrame → 깔끔한 HTML 표. color_cols 칸은 +면 빨강, −면 파랑."""
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body = []
    for _, r in df.iterrows():
        tds = []
        for c in df.columns:
            v = "" if pd.isna(r[c]) else str(r[c])
            cls = sign_class(v) if c in color_cols else ("dim" if c in dim_cols else "")
            tds.append(f"<td class='{cls}'>{html.escape(v)}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table class='t'><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"
