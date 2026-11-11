# ======================================================================
# [블록 9-밸류] 스트림릿 맨 위 '지수 밸류·등락' 자료 (2026-11-11 의장 "이 내용을 우리 자료로, 처음에 볼 수 있게")
#   하는 일  : (가) 주요국 5개·미국 5개 지수의 이달·연초 이후 등락률(%)
#              (나) 필라델피아 반도체 지수 200일 이격도(100 기준) 1995-10-16부터 매일
#              (다) S&P500·나스닥100·필반 12개월 선행 P/E (구성종목 합산, valuation.py 설명 참고)
#                   나스닥100·필반은 매일, S&P500(500종목)은 토요일(미국 금요일 마감)에만 — 야후 요청 수를 줄인다.
#                   과거 컨센서스는 무료로 없어 00_누적에 오늘부터 쌓는다. 판정은 하지 않는다.
#   소스     : 야후(키 없음; 블록 3이 받아 둔 지수 일봉을 먼저 쓴다), 위키백과 구성종목 표(S&P500·나스닥100)
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_지수등락.csv, YYYYMMDD_필반이격도.csv, YYYYMMDD_지수선행PE_종목.csv
#              수집데이터/00_누적/00_지수선행PE.csv (날짜·지수별 한 줄, 같은 날 다시 돌리면 덮어씀)
#              수집데이터/00_누적/00_지수구성종목.csv (위키백과가 막힐 때 쓰는 이전 목록)
#   쓰는 곳  : 스트림릿 '1. 시장' 맨 위 (위원 발언에는 쓰지 않음)
#   실패하면 : (가)·(나)·(다) 따로 점검 파일에 남기고 다음 블록은 계속 실행
# ======================================================================
import valuation as vmod

_YS = globals().get('YS', {})
_YT = globals().get('YF_SERIES', {})
_have = {_YT[k]: s for k, s in _YS.items() if k in _YT}

# (가) 지수 등락
try:
    vb = vmod.bars(yf, _have)
    vb.to_csv(f'{DAY}/{TODAY}_지수등락.csv', index=False, encoding='utf-8-sig')
    log(f'[9 밸류] 지수 등락 {len(vb)}/10 | ' + ', '.join(f'{r.지수} 이달 {r.이달:+.1f}% 연초 {r["연초 이후"]:+.1f}%'
                                                    for _, r in vb[vb['묶음'] == '미국'].iterrows()
                                                    if pd.notna(r.이달) and pd.notna(r['연초 이후'])))
except Exception as e:
    traceback.print_exc()
    log(f'[9 밸류] 지수 등락 실패: {type(e).__name__} {e}')

# (나) 필반 200일 이격도
try:
    sox = _have.get('^SOX')
    vd = vmod.disparity(sox) if sox is not None and sox.index[0] < pd.Timestamp('1995-06-01') else vmod.sox_disparity(yf)
    vd.to_csv(f'{DAY}/{TODAY}_필반이격도.csv', index=False, encoding='utf-8-sig')
    st_ = vmod.disp_stats(vd)
    log(f'[9 밸류] 필반 이격도 {vd["날짜"].iloc[0]}~{vd["날짜"].iloc[-1]} {len(vd)}일 | 현재 {st_["현재"]:.1f} '
        f'평균 {st_["평균"]:.1f} ±1σ {st_["-1σ"]:.1f}~{st_["+1σ"]:.1f} '
        f'(자문사 C 캡처 평균 {vmod.DISP_REF["평균"]} ±1σ {vmod.DISP_REF["-1σ"]}~{vmod.DISP_REF["+1σ"]})')
except Exception as e:
    traceback.print_exc()
    log(f'[9 밸류] 필반 이격도 실패: {type(e).__name__} {e}')

# (다) 지수 12개월 선행 P/E
try:
    _pf, _mf = f'{KEEP}/00_지수선행PE.csv', f'{KEEP}/00_지수구성종목.csv'
    _vold = pd.read_csv(_pf, encoding='utf-8-sig') if os.path.exists(_pf) else pd.DataFrame(columns=vmod.PE_COLS)
    _vmem = pd.read_csv(_mf, encoding='utf-8-sig') if os.path.exists(_mf) else pd.DataFrame(columns=['지수', '티커', '받은 날'])
    have_spx = (_vold['지수'] == 'S&P500').any()
    _vtodo = ['나스닥100', '필반지수'] + (['S&P500'] if NOW.weekday() == 5 or not have_spx else [])
    day_ = NOW.date()
    _vsum, _vdet, _vmsg = [], [], []
    for nm in _vtodo:
        _vtick = vmod.members(get, nm, _vmem.loc[_vmem['지수'] == nm, '티커'].tolist())
        if not _vtick:
            _vmsg.append(f'{nm} 구성종목 없음')
            continue
        if nm != '필반지수':
            _vmem = pd.concat([_vmem[_vmem['지수'] != nm],
                             pd.DataFrame({'지수': nm, '티커': _vtick, '받은 날': TODAY})], ignore_index=True)
        s, d = vmod.index_pe(yf, nm, _vtick, day_)
        _vsum.append(s)
        _vdet.append(d)
        _vmsg.append(f'{nm} {s["선행PE"]}배({s["받은 종목수"]}/{s["종목수"]}종목, 비중 {s["받은 비중(%)"]}%, '
                   f'캡처 {vmod.REF[nm]["캡처값"]})')
    if _vsum:
        _vnew = pd.DataFrame(_vsum, columns=vmod.PE_COLS)
        _vkey = set(zip(_vnew['날짜'], _vnew['지수']))
        _vold = _vold[[(a, b) not in _vkey for a, b in zip(_vold['날짜'], _vold['지수'])]]
        pd.concat([_vold, _vnew], ignore_index=True).sort_values(['지수', '날짜']).to_csv(_pf, index=False, encoding='utf-8-sig')
        pd.concat(_vdet, ignore_index=True).round(3).to_csv(f'{DAY}/{TODAY}_지수선행PE_종목.csv', index=False,
                                                         encoding='utf-8-sig')
        _vmem.to_csv(_mf, index=False, encoding='utf-8-sig')
    log('[9 밸류] 선행 P/E ' + ' | '.join(_vmsg))
except Exception as e:
    traceback.print_exc()
    log(f'[9 밸류] 선행 P/E 실패: {type(e).__name__} {e}')
