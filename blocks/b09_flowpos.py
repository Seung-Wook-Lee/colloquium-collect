# ======================================================================
# [블록 9-수급] 수급·포지셔닝 — 누가 반드시 사야 하고, 누가 이미 다 팔았나 (2026-11-15 의장, 시타델 GMI 자료)
#   하는 일  : flowpos.py로 매일 계산한다.
#              CTA 포지셔닝 근사 σ(빠른판·보정판), 변동성 타기팅 노출, 실현변동성,
#              동일가중÷나스닥100 비율·1년 백분위·상대 RSI, VIX·VXN 1년 백분위, 내재−실현 차이,
#              대통령 임기 주기(중간선거) 달력, 자사주 블랙아웃 창(어림)
#   소스     : 야후 일봉(^GSPC ^NDX ^RUT ^SPXEW ^VIX ^VXN ^VIX3M), 2000년부터. 비용 0원.
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_수급포지셔닝.csv (항목 한 줄 + 달력 줄)
#              수집데이터/00_누적/00_수급포지셔닝_이력.csv (2018년부터 일별, 매일 새로 계산해 덮어씀)
#   쓰는 위원: 수급·포지셔닝 전담 새 위원(이름은 의장이 정함, 페르소나/수급위원_가칭.txt)
#              (나) DBMF(SG CTA 지수 복제 ETF) 매일 보유 내역: 실제 S&P·나스닥·러셀 선물 계약 수 → 00_누적/00_DBMF보유이력.csv
#                   (11/15 의장 "CTA 근거를 발표하는 데를 찾아야지". 운용사 사이트 형식 미확인 — 첫 실행으로 확인)
#   주의     : CTA σ는 시타델 실제 모형이 아니라 가격 근사(보조 자료). 판정 문턱은 의장 승인 전이라 '룰 미정'.
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
import flowpos

# 11/16: 이 블록은 run.py의 공용 이름공간에서 돌아서, 맨 위 변수(u·r·f 등)가 다음 블록의 유니버스 u를 덮어썼음 → 함수 안으로 가둠
def _b09_flowpos():
    try:
        _d = yf.download(list(flowpos.TICKERS.values()), start='2000-01-01', interval='1d', auto_adjust=True,
                         group_by='ticker', threads=False, progress=False)
        FP_CLOSE = {}
        for k, t in flowpos.TICKERS.items():
            try:
                s = _d[t]['Close'].dropna()
                s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
                if len(s) > 300:
                    FP_CLOSE[k] = s
            except Exception:
                pass
        miss = [k for k in flowpos.WEIGHTS if k not in FP_CLOSE]
        if miss:
            raise RuntimeError(f'지수 없음: {miss}')
        FP = flowpos.compute(FP_CLOSE)
        FP.index.name = '날짜'
        FP.to_csv(f'{KEEP}/00_수급포지셔닝_이력.csv', encoding='utf-8-sig')
        tb = flowpos.today_table(FP)
        cyc = flowpos.election_cycle(NOW.date())
        bb = flowpos.buyback_window(NOW.date())
        extra = [{'항목': '대통령 임기 주기', '값': None, '기준일': NOW.strftime('%Y-%m-%d'), '판정': '룰 미정',
                  '무엇': f"{cyc['올해']}" + (f", 선거일 {cyc['선거일']}, 선거 뒤 {cyc['선거 뒤 날수']}일" if cyc['선거 뒤 날수'] is not None else ''),
                  '읽는 법(참고)': 'S&P500 1950~2025: 중간선거 뒤 6달·12달 19번 모두 상승(12달 중앙값 +14.5%). '
                                 '선거일~연말만 보면 평균 +2.6%, 오른 해 68%로 다른 해와 큰 차이 없음 → 긴 기간의 기본값'},
                 {'항목': '자사주 창(어림)', '값': None, '기준일': NOW.strftime('%Y-%m-%d'), '판정': '룰 미정',
                  '무엇': f"{bb['자사주 창(어림)']}, {bb['다음 변화']}",
                  '읽는 법(참고)': '블랙아웃 = 분기 끝 2주 전 ~ 실적 발표 뒤 48시간. 창이 열리면 가장 큰 매수 주체(기업)가 돌아옴'}]
        tb = pd.concat([tb, pd.DataFrame(extra)], ignore_index=True)
        tb['수집시각(KST)'] = stamp()
        tb.to_csv(f'{DAY}/{TODAY}_수급포지셔닝.csv', index=False, encoding='utf-8-sig')
        v = dict(zip(tb['항목'], tb['값']))
        log(f"[9 수급] CTA σ {v.get('CTA σ(근사)')} | "
            f"VT {v.get('변동성타기팅 노출(배)')} | 상대RSI {v.get('상대 RSI(14일)')} · 백분위 {v.get('비율 1년 백분위(%)')} | "
            f"{cyc['올해']} | 자사주 {bb['자사주 창(어림)']}")
    except Exception as e:
        traceback.print_exc()
        log(f'[9 수급] 실패: {type(e).__name__} {e}')


    # (나) DBMF 보유 내역 — CTA 복제 ETF가 실제로 들고 있는 주가지수 선물 (매일 공개)
    DBMF_PAGES = ['https://imgpfunds.com/imgp-dbi-managed-futures-strategy-etf/',
                  'https://www.imgpfunds.com/imgp-dbi-managed-futures-strategy-etf/']
    DBMF_KEYS = ('S&P', 'SP500', 'E-MINI', 'EMINI', 'NASDAQ', 'NDX', 'RUSSELL', 'RTY', 'MSCI', 'NIKKEI', 'TOPIX', 'EURO STOXX')
    try:
        import re as _re
        links, page_err = [], []
        for _url in DBMF_PAGES:
            try:
                r = requests.get(_url, headers=UA, timeout=20)
                r.raise_for_status()
                for h in _re.findall(r'href=["\']([^"\']+)["\']', r.text):
                    if 'olding' in h and _re.search(r'\.(csv|xlsx?)(\?|$)', h, _re.I):
                        links.append(h if h.startswith('http') else requests.compat.urljoin(_url, h))
                if links:
                    break
            except Exception as e:
                page_err.append(f'{_url.split("/")[2]} {type(e).__name__}')
        if not links:
            raise RuntimeError('보유 내역 파일 링크 없음 ' + '; '.join(page_err))
        f = requests.get(links[0], headers=UA, timeout=30)
        f.raise_for_status()
        if links[0].lower().split('?')[0].endswith('.csv'):
            tabs = [pd.read_csv(io.BytesIO(f.content), header=None, dtype=str)]
        else:
            tabs = list(pd.read_excel(io.BytesIO(f.content), header=None, dtype=str, sheet_name=None).values())
        rows = []
        for t in tabs:
            for _, rr in t.fillna('').iterrows():
                line = ' | '.join(str(x).strip() for x in rr if str(x).strip())
                if any(k in line.upper() for k in DBMF_KEYS):
                    rows.append(line)
        hist = f'{KEEP}/00_DBMF보유이력.csv'
        new = pd.DataFrame({'날짜': TODAY, '원문 줄': rows, '파일': links[0]})
        old = pd.read_csv(hist, dtype=str) if os.path.exists(hist) else pd.DataFrame()
        if len(old):
            old = old[old['날짜'] != TODAY]
        pd.concat([old, new], ignore_index=True).to_csv(hist, index=False, encoding='utf-8-sig')
        log(f'[9 수급] DBMF 보유 주가지수 선물 {len(rows)}줄 | {links[0].rsplit("/", 1)[-1]}')
    except Exception as e:
        log(f'[9 수급] DBMF 보유 내역 실패: {type(e).__name__} {e}')


_b09_flowpos()
