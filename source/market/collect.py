"""회의 자료 수집 (source/market)

7개 자료: 공포와 탐욕 지수, CTM(S&P500·나스닥100 가격으로 계산), VIX, 하이일드 스프레드,
미국채 10년 금리, MOVE 지수, WTI.

- 저장은 드라이브 '콜로키움 수집데이터/1_data/가격10년_시장지표.csv.gz' 한 파일(새 파일 없음).
- 이미 있는 자료는 다시 받지 않는다. 각 칸의 마지막 값 다음 날짜부터만 덧붙인다.
- WTI 칸이 없으면 처음 한 번만 10년치를 받는다.
- 하이일드 스프레드는 FRED가 3년치만 공개 → 3년치로 간다(의장 11/27).
- 한투에 없는 자료라 다른 곳에서 받는다(의장 11/27):
    FRED: 10년 금리(DGS10), 하이일드 스프레드(BAMLH0A0HYM2), WTI(DCOILWTICO)
    Cboe: VIX
    야후: MOVE, S&P500(고가·저가 포함), 나스닥100 (CTM 계산용 가격)
    CNN: 공포와 탐욕 지수

실행: python source/market/collect.py [--dry]
필요한 시크릿: FRED_KEY, DRIVE_URL, DRIVE_TOKEN
"""
import argparse
import base64
import gzip
import io
import json
import os
import time

import pandas as pd
import requests

DB = "콜로키움 수집데이터/1_data/가격10년_시장지표.csv.gz"
UA = {"User-Agent": "Mozilla/5.0"}


# ---------------- 드라이브 창구 ----------------
def drive(action, **kw):
    body = {"token": os.environ["DRIVE_TOKEN"], "action": action, **kw}
    for i in range(4):
        try:
            out = requests.post(os.environ["DRIVE_URL"], data=json.dumps(body), timeout=300).json()
            if out.get("ok"):
                return out
            raise RuntimeError(out.get("error"))
        except Exception as e:
            if i == 3:
                raise
            print(f"[드라이브] {action} 다시 시도 ({e})")
            time.sleep(5 * (i + 1))


# ---------------- 받는 곳 ----------------
def fred(sid, start):
    r = requests.get("https://api.stlouisfed.org/fred/series/observations", timeout=60, params={
        "series_id": sid, "api_key": os.environ["FRED_KEY"], "file_type": "json",
        "observation_start": start})
    r.raise_for_status()
    s = pd.Series({o["date"]: o["value"] for o in r.json()["observations"]})
    return pd.to_numeric(s, errors="coerce").dropna()


def cboe_vix():
    r = requests.get("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
                     headers=UA, timeout=60)
    r.raise_for_status()
    d = pd.read_csv(io.StringIO(r.text))
    d["DATE"] = pd.to_datetime(d["DATE"]).dt.strftime("%Y-%m-%d")
    return d.set_index("DATE")["CLOSE"].astype(float)


def yahoo(sym):
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}", headers=UA,
                     timeout=60, params={"range": "3mo", "interval": "1d"})
    r.raise_for_status()
    x = r.json()["chart"]["result"][0]
    q = x["indicators"]["quote"][0]
    idx = pd.to_datetime(x["timestamp"], unit="s", utc=True).tz_convert(
        x["meta"]["exchangeTimezoneName"]).strftime("%Y-%m-%d")
    d = pd.DataFrame({"close": q["close"], "high": q["high"], "low": q["low"]}, index=idx)
    return d[~d.index.duplicated(keep="last")].dropna(subset=["close"])


def cnn_fear_greed():
    r = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata/", headers={
        **UA, "Referer": "https://edition.cnn.com/", "Origin": "https://edition.cnn.com"}, timeout=60)
    r.raise_for_status()
    pts = r.json()["fear_and_greed_historical"]["data"]
    s = pd.Series({pd.to_datetime(p["x"], unit="ms").strftime("%Y-%m-%d"): float(p["y"]) for p in pts})
    return s[~s.index.duplicated(keep="last")]


# ---------------- 덧붙이기 ----------------
def add_new(df, col, s, log):
    """칸 col의 마지막 값 다음 날짜부터만 덧붙인다. 이미 있는 값은 건드리지 않는다."""
    if col not in df.columns:
        df[col] = float("nan")
    last = df[col].last_valid_index()
    new = s[s.index > last] if last is not None else s
    for d, v in new.items():
        if d not in df.index:
            df.loc[d] = float("nan")
        df.at[d, col] = v
    log.append(f"{col}: 마지막 {last} → 새 {len(new)}일" + (f" (끝 {new.index[-1]} = {new.iloc[-1]:.2f})" if len(new) else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="받기만 하고 드라이브에 쓰지 않음")
    a = ap.parse_args()

    out = drive("get", path=DB)
    if not out.get("found"):
        raise SystemExit(f"없음: {DB}")
    df = pd.read_csv(io.BytesIO(base64.b64decode(out["data"])), compression="gzip", index_col=0)
    df.index = df.index.astype(str)
    name, before = df.index.name, len(df)
    print(f"[읽기] 시장지표 {df.shape}, 마지막 날짜 {df.index[-1]}")

    log, fail = [], []
    start = (pd.Timestamp.today() - pd.Timedelta(days=60)).strftime("%Y-%m-%d")
    jobs = [
        ("DGS10", lambda: fred("DGS10", start)),
        ("BAMLH0A0HYM2", lambda: fred("BAMLH0A0HYM2", start)),
        ("WTI", lambda: fred("DCOILWTICO", start if "WTI" in df.columns and df["WTI"].notna().any()
                             else (pd.Timestamp.today() - pd.DateOffset(years=10)).strftime("%Y-%m-%d"))),
        ("VIX", cboe_vix),
        ("공포탐욕", cnn_fear_greed),
    ]
    for col, f in jobs:
        try:
            add_new(df, col, f(), log)
        except Exception as e:
            fail.append(f"{col}: {e}")
    # 하이일드 칸은 BAMLH0A0HYM2와 같은 값(예전부터 두 칸) → 같이 채운다
    if "하이일드" in df.columns and "BAMLH0A0HYM2" in df.columns:
        add_new(df, "하이일드", df["BAMLH0A0HYM2"].dropna(), log)
    for sym, cols in (("^MOVE", {"close": "MOVE"}),
                      ("^GSPC", {"close": "SPX", "high": "SPX_HIGH", "low": "SPX_LOW"}),
                      ("^NDX", {"close": "NDX"})):
        try:
            d = yahoo(sym)
            for k, col in cols.items():
                add_new(df, col, d[k].dropna(), log)
        except Exception as e:
            fail.append(f"{sym}: {e}")

    df = df.sort_index()
    df.index.name = name
    print("[덧붙임]\n  " + "\n  ".join(log))
    if fail:
        print("[못 받음]\n  " + "\n  ".join(fail))
    print(f"[줄] {before} → {len(df)}")
    if a.dry:
        print("[끝] 시험 실행: 드라이브에 쓰지 않음")
        return
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:
        g.write(df.to_csv().encode("utf-8"))
    drive("put", path=DB, data=base64.b64encode(buf.getvalue()).decode(), mime="application/x-gzip")
    print("[끝] 드라이브에 씀")
    if fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
