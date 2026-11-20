# ======================================================================
# [블록 8-MMF] 미국 머니마켓펀드 잔고 — 리오 (2026-11-05 의장 승인 "네 룰을 포함시키세요")
#   하는 일  : ICI(미국 자산운용협회)가 매주 목요일 내는 전체 MMF 잔고(수요일 기준)를 받아 쌓고, 1주·4주 변화를 낸다.
#              잔고가 줄면 대기 자금이 시장(주식·채권)으로 나가는 쪽, 늘면 현금으로 숨는 쪽. 해석은 리오가 한다.
#   소스     : https://www.ici.org/research/stats/mmf 본문 첫 문장
#              "Total money market fund assets increased by $X billion to $Y trillion for the week ended Wednesday, Month D"
#   만드는 것: 수집데이터/00_누적/00_MMF잔고.csv (주마다 한 줄, 같은 주 다시 받으면 덮어씀)
#              수집데이터/YYYYMMDD/YYYYMMDD_MMF.csv (최근 1줄: 기준일·잔고·1주 변화·4주 변화)
#   주의     : ICI는 GitHub Actions 서버 접속을 막는다(2026-11-05 시험 403). 막히면 '실패'로 남고, 그 주는 뉴스 국장이 웹 검색으로 보고.
#              4주 변화는 기록이 4주 쌓인 뒤부터. 문장 모양이 바뀌면 '실패'로 남는다(고칠 곳 MMF_RE).
#   쓰는 위원: 리오
# ======================================================================
MMF_URL = 'https://www.ici.org/research/stats/mmf'
MMF_RE = (r'Total money market fund assets\s+(?:\d\s+)?(increased|decreased)\s+by\s+\$([\d.,]+)\s+billion\s+to\s+'
          r'\$([\d.,]+)\s+trillion\s+for\s+the\s+[\w\- ]*?(?:week|period)\s+ended\s+(?:Wednesday,\s+)?([A-Z][a-z]+\.?\s+\d{1,2})(?:,\s*(\d{4}))?')
MMF_FILE = f'{KEEP}/00_MMF잔고.csv'
try:
    import re as _re
    r = get(MMF_URL, retry=2)
    if r is None:
        raise RuntimeError('ICI 응답 없음')
    txt = _re.sub(r'\s+', ' ', _re.sub(r'<[^>]+>', ' ', r.text))
    m = _re.search(MMF_RE, txt)
    if not m:
        raise ValueError('문장 못 찾음: ' + (txt[txt.find('Total money market'):][:160] if 'Total money market' in txt else '본문에 없음'))
    sign = 1 if m.group(1) == 'increased' else -1
    chg_b, tot_t = sign * float(m.group(2).replace(',', '')), float(m.group(3).replace(',', ''))
    md = m.group(4).replace('.', '').replace('Sept', 'Sep')
    yr = int(m.group(5)) if m.group(5) else NOW.year
    try:
        wk = dt.datetime.strptime(f'{md} {yr}', '%B %d %Y').date()
    except ValueError:
        wk = dt.datetime.strptime(f'{md} {yr}', '%b %d %Y').date()
    if wk > NOW.date():                  # 연초에 지난해 12월 자료
        wk = wk.replace(year=wk.year - 1)
    cols = ['기준일(수)', '잔고(조달러)', '1주 변화(십억달러)', '받은 날']
    old = pd.read_csv(MMF_FILE, dtype={'기준일(수)': str}, encoding='utf-8-sig') if os.path.exists(MMF_FILE) else pd.DataFrame(columns=cols)
    row = pd.DataFrame([{'기준일(수)': wk.isoformat(), '잔고(조달러)': tot_t, '1주 변화(십억달러)': chg_b, '받은 날': TODAY}])
    h = pd.concat([old[old['기준일(수)'] != wk.isoformat()], row], ignore_index=True).sort_values('기준일(수)')
    h.to_csv(MMF_FILE, index=False, encoding='utf-8-sig')
    # 4주 변화: 잔고(조달러)는 소수 둘째 자리라 거칠다 → 주간 변화(십억달러) 최근 4개 합. 4주가 안 쌓이면 빈칸
    last4 = h.tail(4)
    d4 = round(last4['1주 변화(십억달러)'].astype(float).sum(), 2) if len(last4) == 4 and last4['기준일(수)'].iloc[0] >= (wk - dt.timedelta(days=21)).isoformat() else None
    pd.DataFrame([{'기준일(수)': wk.isoformat(), '잔고(조달러)': tot_t, '1주 변화(십억달러)': chg_b,
                   '4주 변화(십억달러)': d4, '쌓인 주': len(h), '출처': 'ICI 주간 MMF 잔고'}]
                 ).to_csv(f'{DAY}/{TODAY}_MMF.csv', index=False, encoding='utf-8-sig')
    log(f'[8 MMF] {wk} 잔고 {tot_t:.2f}조달러 | 1주 {chg_b:+.1f}십억달러 | 4주 ' + (f'{d4:+.1f}' if d4 is not None else f'기록 {len(h)}주(4주 뒤부터)'))
except Exception as e:
    import traceback
    traceback.print_exc()
    log(f'[8 MMF] 실패: {type(e).__name__} {e}')
