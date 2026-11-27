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
.gauge .g-top {display: flex; justify-content: space-between; align-items: baseline;}
.gauge .g-name {font-size: 0.95rem; font-weight: 700; color: #111827;}
.gauge .g-dt {font-size: 0.75rem; color: #9ca3af;}
.gauge .g-val {font-size: 3rem; font-weight: 700; color: #111827; line-height: 1.1; margin-top: 6px; letter-spacing: -0.03em;}
.gauge .g-unit {font-size: 1.3rem; font-weight: 600; color: #6b7280; margin-left: 2px;}
.gauge .g-sub {font-size: 0.78rem; color: #6b7280; margin: 4px 0 10px 0;}
.gauge .g-bar {height: 10px; background: #eef0f3; border-radius: 6px; overflow: hidden;}
.gauge .g-fill {height: 100%; background: linear-gradient(90deg, #4ade80, #16a34a); border-radius: 6px;}
.gauge .g-chips {display: flex; flex-wrap: wrap; gap: 5px; margin-top: 12px;}
.chip {font-size: 0.7rem; font-weight: 600; padding: 3px 7px; border-radius: 999px; font-variant-numeric: tabular-nums;}
.chip.on {background: #dcfce7; color: #15803d; border: 1px solid #86efac;}
.chip.off {background: #f3f4f6; color: #9ca3af; border: 1px solid #e5e7eb;}
.chip.na {background: #ffffff; color: #d1d5db; border: 1px dashed #e5e7eb;}
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
