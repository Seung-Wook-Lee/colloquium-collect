"""분석 쪽 드라이브 읽기 (analysis 공용). 수집은 source/, 여기는 읽기만 한다.
DRIVE_URL·DRIVE_TOKEN 은 환경 변수 또는 스트림릿 시크릿."""
import base64
import io
import json
import os

import pandas as pd
import requests

DB = "콜로키움 수집데이터/1_data"


def _secret(k):
    if k in os.environ:
        return os.environ[k]
    import streamlit as st
    return st.secrets[k]


def raw(name):
    body = {"token": _secret("DRIVE_TOKEN"), "action": "get", "path": f"{DB}/{name}.csv.gz"}
    out = requests.post(_secret("DRIVE_URL"), data=json.dumps(body), timeout=300).json()
    if not out.get("ok") or not out.get("found"):
        raise RuntimeError(out.get("error") or f"없음: {name}")
    return io.BytesIO(base64.b64decode(out["data"]))


def wide(name):
    """날짜 × 종목 표 (가격10년_종가 등)"""
    d = pd.read_csv(raw(name), compression="gzip", index_col=0)
    d.index = pd.to_datetime(d.index, errors="coerce")
    return d[d.index.notna()].sort_index()


def long(name, **kw):
    """줄 형식 표 (가격10년_SEC재무·국내수급 등)"""
    return pd.read_csv(raw(name), compression="gzip", low_memory=False, **kw)


def layers():
    """유니버스 층(업종 묶음): 코드 → (층, 층 이름). 드라이브 가격10년_유니버스(읽기만)."""
    u = long("가격10년_유니버스", dtype=str)
    key = u["yfinance 티커"].fillna(u["코드"])
    return pd.DataFrame({"층": u["층"].values, "층 이름": u["층 이름"].values, "구분": u["구분"].values}, index=key.values)
