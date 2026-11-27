"""매일 가격 수집 (source/stock)

아침 8시(화~토): 밤새 미국 유니버스 종목 하루치
밤 8시(월~금):  그날 한국 유니버스 종목 하루치

- 자료는 한국투자증권(한투) 한 곳에서만 받는다. 한 번 실행 = 한투 접속 1번.
- 유니버스 = 10년치 종가 파일에 있는 종목 칸 그대로(유니버스 파일 따로 없음).
- 드라이브 '콜로키움 수집데이터/1_data/가격10년_{시가,고가,저가,종가,거래량}.csv.gz'
  뒤에 그날 하루치만 붙인다. 이미 값이 있는 칸은 건드리지 않는다. 새 파일은 만들지 않는다.

- PER·EPS·PEG(의장 11/27): 같은 실행에서 같은 날짜로 가격10년_{PER,EPS,PEG}.csv.gz 에 붙인다(source/stock/valuation.py).

실행: python source/stock/collect.py --market us|kr [--dry] [--value-only]
  --dry : 한투에서 받기만 하고 드라이브에는 쓰지 않는다(시험용).
  --value-only : 가격은 건너뛰고 PER·EPS·PEG만 (종가 파일의 그 시장 마지막 날짜로).
필요한 시크릿: KIS_APP_KEY, KIS_APP_SECRET, DRIVE_URL, DRIVE_TOKEN
"""
import argparse
import base64
import gzip
import io
import json
import os
import sys
import time

import pandas as pd
import requests

import valuation as V

KIS = "https://openapi.koreainvestment.com:9443"
DB_DIR = "콜로키움 수집데이터/1_data"
FIELDS = ["시가", "고가", "저가", "종가", "거래량"]
VALUES = ["PER", "EPS", "PEG"]
# 지수(의장 11/27 "코스피·코스닥·S&P500·나스닥은 매일 모아야"): 종가 파일의 '^' 칸에 같이 붙인다.
INDEX = {"kr": {"^KS11": "0001", "^KQ11": "1001"},            # 한투 국내 업종 지수 코드
         "us": {"^GSPC": ("SPX", ".SPX"), "^NDX": ("NDX", ".NDX")}}  # 한투 해외 지수 코드 (앞에서부터 시도)
is_kr = lambda t: t.endswith(".KS") or t.endswith(".KQ")

# 한투 해외 거래소 코드: NAS(나스닥) → NYS(뉴욕) → AMS(아멕스·Arca) 차례로 찾는다.


# ---------------- 드라이브 창구 ----------------
def drive(action, **kw):
    body = {"token": os.environ["DRIVE_TOKEN"], "action": action, **kw}
    for i in range(4):
        try:
            r = requests.post(os.environ["DRIVE_URL"], data=json.dumps(body), timeout=300)
            out = r.json()
            if out.get("ok"):
                return out
            raise RuntimeError(out.get("error"))
        except Exception as e:  # 네트워크 오류는 3번 더 시도
            if i == 3:
                raise
            print(f"[드라이브] {action} 다시 시도 ({e})")
            time.sleep(5 * (i + 1))


def drive_get(path):
    out = drive("get", path=path)
    if not out.get("found"):
        raise FileNotFoundError(path)
    return base64.b64decode(out["data"])


def drive_put(path, raw, mime):
    drive("put", path=path, data=base64.b64encode(raw).decode(), mime=mime)


def load_universe():
    """유니버스 = 10년치 종가 파일에 있는 종목 칸 그대로(의장 11/27, 유니버스 파일 따로 없음).
    '^'로 시작하는 칸(지수)은 종목이 아니라서 뺀다."""
    df = pd.read_csv(io.BytesIO(drive_get(f"{DB_DIR}/가격10년_종가.csv.gz")), compression="gzip",
                     index_col=0, nrows=1)
    cols = [c for c in df.columns if not c.startswith("^")]
    print(f"[유니버스] 10년치 종가 파일 종목 {len(cols)}개")
    return cols


# ---------------- 한투 ----------------
class Kis:
    def __init__(self):
        self.key = os.environ["KIS_APP_KEY"]
        self.secret = os.environ["KIS_APP_SECRET"]
        r = requests.post(f"{KIS}/oauth2/tokenP", timeout=30, json={
            "grant_type": "client_credentials", "appkey": self.key, "appsecret": self.secret})
        r.raise_for_status()
        self.token = r.json()["access_token"]
        self.excd = {}  # 미국 종목별로 찾은 거래소
        print("[한투] 접속 1번 (토큰 받음)")

    def get(self, path, tr_id, params):
        h = {"authorization": f"Bearer {self.token}", "appkey": self.key,
             "appsecret": self.secret, "tr_id": tr_id, "custtype": "P"}
        for i in range(3):
            r = requests.get(f"{KIS}{path}", headers=h, params=params, timeout=30)
            time.sleep(0.07)  # 초당 20건 제한
            if r.status_code == 200:
                j = r.json()
                if j.get("rt_cd") == "0":
                    return j
                if "초당" not in str(j.get("msg1", "")):
                    return j
            time.sleep(1)
        return {}

    def kr_daily(self, code):
        """국내 일봉 최근 것들 → {날짜: (시가,고가,저가,종가,거래량)}"""
        today = pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y%m%d")
        start = (pd.Timestamp.now(tz="Asia/Seoul") - pd.Timedelta(days=14)).strftime("%Y%m%d")
        j = self.get("/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice", "FHKST03010100", {
            "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": start, "FID_INPUT_DATE_2": today,
            "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"})
        rows = {}
        for x in j.get("output2") or []:
            d = x.get("stck_bsop_date")
            if d and x.get("stck_clpr") not in (None, "", "0"):
                rows[d] = tuple(float(x[k]) for k in
                                ("stck_oprc", "stck_hgpr", "stck_lwpr", "stck_clpr", "acml_vol"))
        return rows

    def kr_index(self, code):
        """국내 지수 일봉 → {날짜: (시가,고가,저가,종가,거래량)} (FHKUP03500100)"""
        today = pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y%m%d")
        start = (pd.Timestamp.now(tz="Asia/Seoul") - pd.Timedelta(days=14)).strftime("%Y%m%d")
        j = self.get("/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice", "FHKUP03500100", {
            "FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": code, "FID_INPUT_DATE_1": start,
            "FID_INPUT_DATE_2": today, "FID_PERIOD_DIV_CODE": "D"})
        rows = {}
        for x in j.get("output2") or []:
            d = x.get("stck_bsop_date")
            if d and x.get("bstp_nmix_prpr") not in (None, "", "0"):
                rows[d] = tuple(float(x.get(k) or "nan") for k in
                                ("bstp_nmix_oprc", "bstp_nmix_hgpr", "bstp_nmix_lwpr", "bstp_nmix_prpr", "acml_vol"))
        return rows

    def us_index(self, codes):
        """해외 지수 일봉 → {날짜: (시가,고가,저가,종가,거래량)} (FHKST03030100)"""
        today = pd.Timestamp.now(tz="America/New_York").strftime("%Y%m%d")
        start = (pd.Timestamp.now(tz="America/New_York") - pd.Timedelta(days=14)).strftime("%Y%m%d")
        for code in codes:
            j = self.get("/uapi/overseas-price/v1/quotations/inquire-daily-chartprice", "FHKST03030100", {
                "FID_COND_MRKT_DIV_CODE": "N", "FID_INPUT_ISCD": code, "FID_INPUT_DATE_1": start,
                "FID_INPUT_DATE_2": today, "FID_PERIOD_DIV_CODE": "D"})
            rows = {}
            for x in j.get("output2") or []:
                d = x.get("stck_bsop_date")
                if d and x.get("ovrs_nmix_prpr") not in (None, "", "0"):
                    rows[d] = tuple(float(x.get(k) or "nan") for k in
                                    ("ovrs_nmix_oprc", "ovrs_nmix_hgpr", "ovrs_nmix_lwpr", "ovrs_nmix_prpr", "acml_vol"))
            if rows:
                return rows
            print(f"[지수] {code} 없음 ({str(j.get('msg1', ''))[:60]})")
        return {}

    def us_daily(self, symb, excd):
        """해외 일봉 최근 것들 → {날짜: (시가,고가,저가,종가,거래량)}"""
        for ex in [excd] + [e for e in ("NAS", "NYS", "AMS") if e != excd]:
            j = self.get("/uapi/overseas-price/v1/quotations/dailyprice", "HHDFS76240000", {
                "AUTH": "", "EXCD": ex, "SYMB": symb, "GUBN": "0", "BYMD": "", "MODP": "1"})
            rows = {}
            for x in j.get("output2") or []:
                d = x.get("xymd")
                if d and x.get("clos") not in (None, "", "0", "0.0000"):
                    rows[d] = tuple(float(x[k]) for k in ("open", "high", "low", "clos", "tvol"))
            if rows:
                self.excd[symb] = ex
                return rows
        return {}


# ---------------- 수집 ----------------
def collect(market, kis, sub):
    got, miss = {}, []
    for t in sub:
        if market == "kr":
            rows = kis.kr_daily(t.split(".")[0])
        else:
            rows = kis.us_daily(t.replace("-", "/"), "NAS")
        if rows:
            got[t] = rows
        else:
            miss.append(t)
    print(f"[받기] {market} {len(sub)}개 중 {len(got)}개 받음, 못 받음 {len(miss)}개 {miss}")
    for col, code in INDEX[market].items():
        rows = kis.kr_index(code) if market == "kr" else kis.us_index(code)
        if rows:
            got[col] = rows
            print(f"[지수] {col} {len(rows)}일, 마지막 {max(rows)} 종가 {rows[max(rows)][3]:,.2f}")
        else:
            print(f"[지수] {col} 못 받음")
    if not got:
        raise SystemExit("한 종목도 못 받음 — 드라이브에 쓰지 않음")
    # 하루치 = 받은 자료 중 가장 최근 거래일 하나
    day = max(max(v) for v in got.values())
    late = [t for t, v in got.items() if day not in v]
    print(f"[하루치] {day[:4]}-{day[4:6]}-{day[6:]} (그날 값 없는 종목 {len(late)}개 {late})")
    return pd.Timestamp(day).strftime("%Y-%m-%d"), {t: v[day] for t, v in got.items() if day in v}


def write_day(field, day, vals, dry):
    """가격10년_{field} 의 day 줄에 vals{종목: 값} 중 빈 칸만 채운다. 파일이 없으면 새로 만든다(PER·EPS·PEG)."""
    path = f"{DB_DIR}/가격10년_{field}.csv.gz"
    try:
        df = pd.read_csv(io.BytesIO(drive_get(path)), compression="gzip", index_col=0)
    except FileNotFoundError:
        df = pd.DataFrame(index=pd.Index([], name="Date"), dtype=float)
        print(f"[{field}] 파일 없음 → 새로 만듦")
    name = df.index.name or "Date"
    df.index = df.index.astype(str)
    before = len(df)
    if day not in df.index:
        df.loc[day] = float("nan")
    filled, kept = 0, 0
    for t, v in vals.items():
        if pd.isna(v):
            continue
        if t not in df.columns:
            df[t] = float("nan")
        if pd.isna(df.at[day, t]):
            df.at[day, t] = v
            filled += 1
        else:
            kept += 1
    df = df.sort_index()
    df.index.name = name
    print(f"[{field}] {day} 채움 {filled}칸, 이미 있어 그대로 {kept}칸, 줄 {before}→{len(df)}")
    if dry:
        return
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:
        g.write(df.to_csv().encode("utf-8"))
    drive_put(path, buf.getvalue(), "application/x-gzip")
    print(f"[{field}] 드라이브에 씀")


def append(day, vals, dry):
    for i, field in enumerate(FIELDS):
        write_day(field, day, {t: v[i] for t, v in vals.items()}, dry)


def values(market, kis, sub):
    """종목별 (PER, EPS, PEG). ETF처럼 없는 값은 빈칸."""
    out = {}
    sec = None
    if market == "us":
        try:
            sec = V.Sec()
        except Exception as e:
            print(f"[SEC] 못 받음 ({e}) → PEG 빈칸")
    for t in sub:
        try:
            if market == "kr":
                per, eps, g = V.kr_value(kis, t.split(".")[0])
            else:
                symb = t.replace("-", "/")
                per, eps = V.us_value(kis, symb, kis.excd.get(symb, "NAS"))
                g = sec.eps_growth(t) if sec else float("nan")
        except Exception as e:
            print(f"[값] {t} 못 받음 ({e})")
            continue
        per = per if per > 0 else float("nan")
        out[t] = (per, eps if eps == eps and eps != 0 else float("nan"), V.peg(per, g))
    n = [sum(1 for v in out.values() if v[i] == v[i]) for i in range(3)]
    print(f"[값] {market} {len(sub)}개 중 PER {n[0]}개, EPS {n[1]}개, PEG {n[2]}개")
    show = [t for t in sub if t in out][:5]
    for t in show:
        print(f"   {t}: PER {out[t][0]:.2f}, EPS {out[t][1]:.2f}, PEG {out[t][2]:.2f}")
    return out


def market_funds(kis, dry):
    """MI14 신용잔고·고객예탁금(억원, 금융투자협회 자료를 한투가 제공, 증시자금 종합 FHKST649100C0)
    → 가격10년_시장지표 '신용잔고'·'고객예탁금' 칸. 마지막 값 다음 날짜부터만 덧붙인다. 값만 보여 주는 자료(의장 11/27)."""
    j = kis.get("/uapi/domestic-stock/v1/quotations/mktfunds", "FHKST649100C0", {"FID_INPUT_DATE_1": ""})
    rows = j.get("output") or []
    if isinstance(rows, dict):
        rows = [rows]
    new = {}
    for x in rows:
        d = x.get("bsop_date")
        if d:
            new[f"{d[:4]}-{d[4:6]}-{d[6:]}"] = (V.num(x.get("crdt_loan_rmnd")), V.num(x.get("cust_dpmn_amt")))
    print(f"[증시자금] {len(new)}일 받음" + (f" {min(new)}~{max(new)}" if new else f" (응답 {str(j)[:200]})"))
    if not new:
        return
    path = f"{DB_DIR}/가격10년_시장지표.csv.gz"
    df = pd.read_csv(io.BytesIO(drive_get(path)), compression="gzip", index_col=0)
    name = df.index.name
    df.index = df.index.astype(str)
    for i, col in enumerate(("신용잔고", "고객예탁금")):
        if col not in df.columns:
            df[col] = float("nan")
        last = df[col].last_valid_index()
        add = {d: v[i] for d, v in new.items() if (last is None or d > last) and v[i] == v[i]}
        for d, v in add.items():
            if d not in df.index:
                df.loc[d] = float("nan")
            df.at[d, col] = v
        print(f"[증시자금] {col}: 마지막 {last} → 새 {len(add)}일")
    df = df.sort_index()
    df.index.name = name
    if dry:
        return
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:
        g.write(df.to_csv().encode("utf-8"))
    drive_put(path, buf.getvalue(), "application/x-gzip")
    print("[증시자금] 드라이브에 씀")


def last_day(market):
    df = pd.read_csv(io.BytesIO(drive_get(f"{DB_DIR}/가격10년_종가.csv.gz")), compression="gzip", index_col=0)
    df = df[[c for c in df.columns if not c.startswith("^") and is_kr(c) == (market == "kr")]]
    return str(df.dropna(how="all").index[-1])[:10]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=["us", "kr"], required=True)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--value-only", action="store_true")
    a = ap.parse_args()
    sub = [t for t in load_universe() if is_kr(t) == (a.market == "kr")]
    kis = Kis()
    if a.value_only:
        day = last_day(a.market)
        print(f"[값만] {day}")
    else:
        day, vals = collect(a.market, kis, sub)
        append(day, vals, a.dry)
    if a.market == "kr":
        try:
            market_funds(kis, a.dry)
        except Exception as e:
            print(f"[증시자금] 못 받음 ({e})")
    val = values(a.market, kis, sub)
    for i, field in enumerate(VALUES):
        write_day(field, day, {t: v[i] for t, v in val.items()}, a.dry)
    print("[끝] 시험 실행: 드라이브에 쓰지 않음" if a.dry else "[끝]")


if __name__ == "__main__":
    sys.exit(main())
