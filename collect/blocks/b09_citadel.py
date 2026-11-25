# ======================================================================
# [블록 9-시타델] 섹터 ETF 주봉과 섹터 지도(미스 시타델 수급 자료)
#   11/26 의장 "상위종목 하지마. ETF만 해. 유니버스에 없는 것은 하지마. 그리고 병합해. DB"
#   하는 일  : 섹터 ETF(해외 SPDR 11개 · 국내 12개, 유니버스에 있는 것만)의 주봉을 10년치 데이터베이스 일봉으로 만들고,
#              60·20주선 이격·첫 터치·하향돌파 뒤 상향돌파·RSI·주봉 MACD 기울기·월봉 5개월선 이격으로 섹터 지도를 만든다.
#              ETF 줄에 ETF 자금(5·20일)을 붙인다.
#   소스     : 10년치 데이터베이스(1_data/가격10년_시가·고가·저가·종가·거래량, b01_prices가 같은 실행에서 {DATA}/1_data_가격에 둠), citadel/(목록·CFG),
#              오늘 폴더 _ETF자금.csv. 한투 접속 없음, 따로 저장하는 파일 없음.
#   만드는 것: YYYYMMDD/YYYYMMDD_시타델.csv(섹터 지도, 시장 칸으로 해외·국내 구분)
#   쓰는 곳  : B18 업종 ETF 60주선 이격·업종 자금(엔진), 미스 시타델 수급 해석, 스트림릿 섹터 지도
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
import sys as _sys
_sys.path.insert(0, 'citadel')                    # run.py는 collect/ 에서 돈다
import citadel as ct


def _v(x, f='{:+,.0f}'):
    return '-' if x is None or pd.isna(x) else f.format(x)


try:
    _sys.path.insert(0, os.path.abspath('data'))
    import px_store as PS
    _PXD = f'{DATA}/1_data_가격'; os.makedirs(_PXD, exist_ok=True)
    if not IN_COLAB:   # 같은 실행에서 b01_prices가 받아 두지 않았으면 드라이브 데이터베이스에서
        for _k in ('Open', 'High', 'Low', 'Close', 'Volume'):
            if not os.path.exists(f'{_PXD}/{PS.name(_k)}'):
                _b = gdrive.get(f'{D_DATA}/1_data/{PS.name(_k)}')
                if _b: open(f'{_PXD}/{PS.name(_k)}', 'wb').write(_b)
    hus = pd.read_csv('citadel/etfs_us.csv'); hus['시장'] = '해외'
    ekr = pd.read_csv('citadel/etfs_kr.csv', dtype={'ETF': str}); ekr['시장'] = '국내'
    have = {ct.code(t): t for t in PS.frame(_PXD, 'Close').columns}   # 데이터베이스 = 유니버스
    out_u = [e for e in list(hus.ETF) + list(ekr.ETF) if e not in have]   # 유니버스에 없는 것은 하지 않음
    hus, ekr = hus[hus.ETF.isin(have)], ekr[ekr.ETF.isin(have)]
    store = ct.weekly(PS.long(_PXD, [have[e] for e in list(hus.ETF) + list(ekr.ETF)]))
    if not IN_COLAB:   # 병합 끝: 따로 있던 주봉 칸과 옛 창고 파일은 휴지통(한 번, 없으면 0)
        for _o in (f'1_data/{PS.name("섹터주봉")}', '00_누적/00_시타델_주봉.csv'):   # 옛 주봉 칸·옛 창고
            if gdrive.trash(f'{D_DATA}/{_o}'):
                log(f'[9 시타델] 따로 있던 {_o} → 데이터베이스로 병합, 휴지통')
    # 지금판 + 수급
    names = dict(zip(ekr.ETF, ekr.이름))
    Tus, cus = ct.now_table(store, hus); Tus['시장'] = '해외'; Tus['ETF이름'] = Tus.ETF.map(dict(zip(hus.ETF, hus.이름))).fillna('')
    Tkr, ckr = ct.now_table(store, ekr) if len(ekr) else (pd.DataFrame(), [])
    if len(Tkr): Tkr['시장'] = '국내'; Tkr['ETF이름'] = Tkr.ETF.map(names).fillna('')
    fp = f'{DAY}/{TODAY}_ETF자금.csv'
    if os.path.exists(fp):
        fl = pd.read_csv(fp, dtype={'코드': str}).set_index('코드')
        for T in (Tus, Tkr):
            if len(T):
                T['자금5일'] = [fl['유입_5일'].get(e) for e in T.ETF]
                T['자금20일'] = [fl['유입_20일'].get(e) for e in T.ETF]
    T = pd.concat([Tus, Tkr], ignore_index=True)
    T.to_csv(f'{DAY}/{TODAY}_시타델.csv', index=False, encoding='utf-8-sig')
    log(f'[9 시타델] 섹터 ETF {store.티커.nunique()}개·주봉 {len(store)}줄(데이터베이스) | 해외 60주 첫 터치 {",".join(cus) or "없음"} | 국내 {",".join(ckr) or "없음"} | '
        f'유니버스에 없어 뺌 {",".join(out_u) or "없음"}')
except Exception as e:
    traceback.print_exc()
    log(f'[9 시타델] 실패: {type(e).__name__} {e}')
