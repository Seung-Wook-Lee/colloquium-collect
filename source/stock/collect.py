"""매일 가격 수집 (source/stock)

아침 8시(화~토): 밤새 미국 유니버스 종목 하루치
밤 8시(월~금):  그날 한국 유니버스 종목 하루치

- 자료는 한국투자증권(한투) 한 곳에서만 받는다. 한 번 실행 = 한투 접속 1번.
- 유니버스 파일(드라이브 '콜로키움/포트폴리오/콜로키움100_유니버스_*.csv' 중 가장 최신)에 있는 종목만.
- 드라이브 '콜로키움 수집데이터/1_data/가격10년_{시가,고가,저가,종가,거래량}.csv.gz'
  뒤에 그날 하루치만 붙인다. 이미 값이 있는 칸은 건드리지 않는다. 새 파일은 만들지 않는다.

실행: python source/stock/collect.py --market us|kr [--dry]
  --dry : 한투에서 받기만 하고 드라이브에는 쓰지 않는다(시험용).
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

KIS = "https://openapi.koreainvestment.com:9443"
UNIV_DIR = "콜로키움/포트폴리오"
UNIV_PREFIX = "콜로키움100_유니버스_"
DB_DIR = "콜로키움 수집데이터/1_data"
FIELDS = ["시가", "고가", "저가", "종가", "거래량"]

# 유니버스 '거래소' 칸 → 한투 해외 거래소 코드. 비면 나머지 코드로 차례로 다시 찾는다.
US_EXCD = {"NASDAQ": "NAS", "NYSE": "NYS", "NYSE Arca": "AMS", "NYSE American": "AMS", "Cboe BZX": "AMS"}


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
    files = [f["name"] for f in drive("list", path=UNIV_DIR)["files"]
             if f["name"].startswith(UNIV_PREFIX) and f["name"].endswith(".csv")]
    if not files:
        raise FileNotFoundError(f"{UNIV_DIR}/{UNIV_PREFIX}*.csv")
    name = max(files)
    u = pd.read_csv(io.BytesIO(drive_get(f"{UNIV_DIR}/{name}")), dtype=str, encoding="utf-8-sig")
    print(f"[유니버스] {name} {len(u)}개")
    return u


# ---------------- 한투 ----------------
class Kis:
    def __init__(self):
        self.key = os.environ["KIS_APP_KEY"]
        self.secret = os.environ["KIS_APP_SECRET"]
        r = requests.post(f"{KIS}/oauth2/tokenP", timeout=30, json={
            "grant_type": "client_credentials", "appkey": self.key, "appsecret": self.secret})
        r.raise_for_status()
        self.token = r.json()["access_token"]
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
                return rows
        return {}


# ---------------- 수집 ----------------
def collect(market):
    u = load_universe()
    kis = Kis()
    got, miss = {}, []
    if market == "kr":
        sub = u[u["시장"] == "한국"]
        for _, r in sub.iterrows():
            t = str(r["yfinance 티커"]).strip()
            rows = kis.kr_daily(str(r["코드"]).strip())
            if rows:
                got[t] = rows
            else:
                miss.append(t)
    else:
        sub = u[u["시장"] == "미국"]
        for _, r in sub.iterrows():
            t = str(r["yfinance 티커"]).strip()
            rows = kis.us_daily(t.replace("-", "/"), US_EXCD.get(str(r["거래소"]).strip(), "NAS"))
            if rows:
                got[t] = rows
            else:
                miss.append(t)
    print(f"[받기] {market} 유니버스 {len(sub)}개 중 {len(got)}개 받음, 못 받음 {len(miss)}개 {miss}")
    if not got:
        raise SystemExit("한 종목도 못 받음 — 드라이브에 쓰지 않음")
    # 하루치 = 받은 자료 중 가장 최근 거래일 하나
    day = max(max(v) for v in got.values())
    late = [t for t, v in got.items() if day not in v]
    print(f"[하루치] {day[:4]}-{day[4:6]}-{day[6:]} (그날 값 없는 종목 {len(late)}개 {late})")
    return pd.Timestamp(day).strftime("%Y-%m-%d"), {t: v[day] for t, v in got.items() if day in v}


def append(day, vals, dry):
    for i, field in enumerate(FIELDS):
        path = f"{DB_DIR}/가격10년_{field}.csv.gz"
        df = pd.read_csv(io.BytesIO(drive_get(path)), compression="gzip", index_col=0)
        name = df.index.name
        df.index = df.index.astype(str)
        before = len(df)
        if day not in df.index:
            df.loc[day] = float("nan")
        filled, kept = 0, 0
        for t, v in vals.items():
            if t not in df.columns:
                df[t] = float("nan")
                print(f"[{field}] 새 종목 칸 {t}")
            if pd.isna(df.at[day, t]):
                df.at[day, t] = v[i]
                filled += 1
            else:
                kept += 1
        df = df.sort_index()
        df.index.name = name
        print(f"[{field}] {day} 채움 {filled}칸, 이미 있어 그대로 {kept}칸, 줄 {before}→{len(df)}")
        if dry:
            continue
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:
            g.write(df.to_csv().encode("utf-8"))
        drive_put(path, buf.getvalue(), "application/x-gzip")
        print(f"[{field}] 드라이브에 씀")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=["us", "kr"], required=True)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    day, vals = collect(a.market)
    append(day, vals, a.dry)
    print("[끝] 시험 실행: 드라이브에 쓰지 않음" if a.dry else "[끝]")


if __name__ == "__main__":
    sys.exit(main())
