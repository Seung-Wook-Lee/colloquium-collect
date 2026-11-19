# ======================================================================
# [블록 9-GPR] 세계는 평화로운가 — 지정학 위험 지수(GPR) (2026-11-19 의장, 퀀트센터 B10)
#   하는 일  : Caldara·Iacoviello(미 연준 이사회 연구진) 일간 지정학 위험 지수(GPRD)를 받아
#              7일 평균과 그 값이 최근 10년 중 몇 백분위인지 계산한다. 신문 기사에서 전쟁·테러·군사 긴장 낱말 빈도로 만든 지수.
#   소스     : https://www.matteoiacoviello.com/gpr.htm (data_gpr_daily_recent.xls, 무료)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_지정학위험.csv (날짜, GPRD, GPRD_MA7, GPR_PCT)
#   쓰는 곳  : 퀀트센터 B10 공식(GPR_PCT ≥ 90·97 부담)
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
GPR_URL = 'https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls'

try:
    import io
    raw = get(GPR_URL).content
    g = pd.read_excel(io.BytesIO(raw))
    g.columns = [str(c).strip() for c in g.columns]
    dcol = next(c for c in g.columns if c.lower() in ('date', 'day'))
    g['날짜'] = pd.to_datetime(g[dcol].astype(str).str[:10], errors='coerce', format='mixed')
    g = g.dropna(subset=['날짜']).sort_values('날짜')
    g['GPRD'] = pd.to_numeric(g['GPRD'], errors='coerce')
    g['GPRD_MA7'] = g['GPRD'].rolling(7, min_periods=5).mean()
    w = g[g['날짜'] >= g['날짜'].max() - pd.Timedelta(days=3653)]['GPRD_MA7'].dropna()
    last = g['GPRD_MA7'].dropna().iloc[-1]
    pct = float((w <= last).mean() * 100)
    out = g[['날짜', 'GPRD', 'GPRD_MA7']].tail(400).copy()
    out['GPR_PCT'] = None
    out.iloc[-1, out.columns.get_loc('GPR_PCT')] = round(pct, 1)
    out['날짜'] = out['날짜'].dt.strftime('%Y-%m-%d')
    out.to_csv(f'{DAY}/{TODAY}_지정학위험.csv', index=False, encoding='utf-8-sig')
    log(f'[9 GPR] {out["날짜"].iloc[-1]} 7일 평균 {last:.0f}, 10년 백분위 {pct:.0f}%')
except Exception as e:
    traceback.print_exc()
    log(f'[9 GPR] 실패: {type(e).__name__} {e}')
