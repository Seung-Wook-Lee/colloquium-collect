"""PER·EPS·PEG (source/stock)

의장 11/27 지시: 2-1 주요 종목 표에 PER, EPS, PEG.
- PER·EPS: 한투 현재가
    한국: 국내 현재가 FHKST01010100 (per, eps)
    미국: 해외 현재가 상세 HHDFS76200200 (perx, epsx)
- PEG = PER ÷ EPS 증가율(%) (피터 린치 정의). EPS 증가율 = 최근 사업연도 EPS ÷ 그 전 사업연도 EPS − 1.
    한국: 한투 재무비율 FHKST66430300 (연도별 eps)
    미국: 한투에 과거 EPS가 없어 SEC 공시(companyfacts, 희석 EPS, 10-K 연간)에서 받는다(의장 허락 11/27).
- EPS 증가율이 0 이하이거나 PER이 0 이하면 PEG는 정의되지 않으므로 빈칸.
- ETF는 PER·EPS가 없으므로 빈칸.
"""
import time

import pandas as pd
import requests

SEC_UA = {"User-Agent": "colloquium-collect data collector research@colloquium-collect.invalid"}


def num(x):
    try:
        v = float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return float("nan")
    return v


def growth(new, old):
    if pd.isna(new) or pd.isna(old) or old <= 0:
        return float("nan")
    return (new / old - 1) * 100


def peg(per, g):
    if pd.isna(per) or pd.isna(g) or per <= 0 or g <= 0:
        return float("nan")
    return per / g


# ---------------- 한국 (한투) ----------------
def kr_value(kis, code):
    """→ (PER, EPS, EPS 증가율 %)"""
    j = kis.get("/uapi/domestic-stock/v1/quotations/inquire-price", "FHKST01010100", {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code})
    o = j.get("output") or {}
    per, eps = num(o.get("per")), num(o.get("eps"))
    j = kis.get("/uapi/domestic-stock/v1/finance/financial-ratio", "FHKST66430300", {
        "FID_DIV_CLS_CODE": "0", "fid_cond_mrkt_div_code": "J", "fid_input_iscd": code})
    rows = sorted(((x.get("stac_yymm", ""), num(x.get("eps"))) for x in (j.get("output") or [])
                   if x.get("stac_yymm")), reverse=True)
    g = growth(rows[0][1], rows[1][1]) if len(rows) >= 2 else float("nan")
    return per, eps, g


# ---------------- 미국 (한투 + SEC) ----------------
def us_value(kis, symb, excd):
    """→ (PER, EPS)"""
    for ex in [excd] + [e for e in ("NAS", "NYS", "AMS") if e != excd]:
        j = kis.get("/uapi/overseas-price/v1/quotations/price-detail", "HHDFS76200200", {
            "AUTH": "", "EXCD": ex, "SYMB": symb})
        o = j.get("output") or {}
        if o.get("last") not in (None, "", "0", "0.0000"):
            return num(o.get("perx")), num(o.get("epsx"))
    return float("nan"), float("nan")


class Sec:
    def __init__(self):
        r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=SEC_UA, timeout=60)
        r.raise_for_status()
        self.cik = {v["ticker"].upper(): int(v["cik_str"]) for v in r.json().values()}
        print(f"[SEC] 티커 {len(self.cik)}개")

    def eps_growth(self, ticker):
        """최근 사업연도 희석 EPS ÷ 그 전 사업연도 − 1 (%)."""
        cik = self.cik.get(ticker.upper().replace(".", "-")) or self.cik.get(ticker.upper())
        if not cik:
            return float("nan")
        time.sleep(0.15)  # SEC 초당 10건 제한
        r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", headers=SEC_UA, timeout=60)
        if r.status_code != 200:
            return float("nan")
        g = r.json().get("facts", {}).get("us-gaap", {})
        for tag in ("EarningsPerShareDiluted", "EarningsPerShareBasic"):
            pts = (g.get(tag, {}).get("units", {}) or {}).get("USD/shares", [])
            yr = {}
            for p in pts:
                if p.get("form") not in ("10-K", "10-K/A") or not p.get("start"):
                    continue
                days = (pd.Timestamp(p["end"]) - pd.Timestamp(p["start"])).days
                if 350 <= days <= 380:
                    yr[p["end"]] = p["val"]  # 같은 사업연도는 마지막 공시 값
            ends = sorted(yr)
            if len(ends) >= 2:
                return growth(yr[ends[-1]], yr[ends[-2]])
        return float("nan")
