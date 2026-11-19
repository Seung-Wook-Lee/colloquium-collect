# ======================================================================
# [블록 9-주가뉴스] 오늘의 주가 뉴스 10 — 주가와 관련된 기사 10건과 긍정·부정 판정 (2026-11-20 의장)
#   하는 일  : 블록 9(뉴스)가 모은 밤사이(어제 18시 이후) 기사 중 ① 미국 매체(CNBC·CNN·블룸버그) ② 미국 뉴스
#              (미국 종목 기사이거나 종목 없는 시장 기사, 한국·일본 종목 기사와 DART는 뺌) ③ 주가 관련(종목 기사이거나
#              제목에 시장 낱말)인 것만 남기고, 블록 9-감성(FinBERT)의 확률로 긍정·부정·중립을 붙여 10건을 고른다.
#              판정: 긍정 확률 ≥ CUT 이면 긍정, 부정 확률 ≥ CUT 이면 부정, 아니면 중립. 사람·AI 판단 없음.
#              순서: 긍정·부정 먼저(중립은 모자랄 때만) → 확률 높은 순. 같은 종목은 최대 PER_STOCK건.
#              세계 정세(전쟁·이란·우크라이나 등) 기사는 GEO_SLOTS 자리를 먼저 받는다(11/20 의장).
#              종목 기사에는 그 종목의 전일 등락률(_시세.csv)을 붙인다.
#   읽는 것  : YYYYMMDD_뉴스.csv, YYYYMMDD_뉴스감성.csv, YYYYMMDD_시세.csv
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_주가뉴스.csv
#              (순위, 구분(세계 정세/종목/시장), 시각(한국), 판정, 긍정, 부정, 종목, 등락률(%), 제목, 출처, 링크)
#   쓰는 위원: 뉴스 국장(회의 원고 meeting/personas.py)
#              11/20 01:38 의장 "국내 뉴스보다는 밤새 미국 뉴스에만 집중"
#   고칠 곳  : 건수 TOP_N, 판정 기준 CUT, 미국 매체 MEDIA, 종목 시장 MARKETS, 시장 낱말은 블록 9의 NEWS_KEEP
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
TOP_N = 10            # 의장 11/20 "10개 정도"
CUT = 0.6             # 긍정·부정 판정 확률 기준
PER_STOCK = 2         # 같은 종목 최대 건수
# 의장 11/10 승인 해외 매체(CNBC·CNN·블룸버그) — 출처·링크·제목 끝 (매체)로 확인
MEDIA = r'(?i)cnbc|\bcnn\b|cnn\.com|블룸버그|bloomberg'
MARKETS = ['미국']    # 종목 기사는 이 시장 종목만
# 11/20 01:40 의장 "전세계 뉴스. 전쟁이 나면 알려줘야. 이란·우크라이나" — 세계 정세 기사는 GEO_SLOTS 자리를 먼저 채운다(감성과 무관)
GEO = (r'(?i)\bwar\b|warfare|iran|israel|gaza|hamas|hezbollah|houthi|ukrain|russia|putin|zelensky|kremlin|missile|airstrike|'
       r'ceasefire|truce|peace (talks|deal|plan)|invasion|invade|military|troops|nato|taiwan|north korea|pyongyang|'
       r'middle east|red sea|strait of hormuz|sanction|coup|terror|전쟁|이란|이스라엘|가자|우크라|러시아|푸틴|젤렌스키|'
       r'미사일|공습|휴전|종전|평화협상|침공|군사|나토|대만|북한|중동|홍해|호르무즈|제재')
GEO_SLOTS = 3         # 10건 중 세계 정세 자리(기사가 없으면 다른 기사로 채움)
# 영어 제목의 시장 낱말(블록 9의 NEWS_KEEP은 한국어 위주)
MKT_EN = (r'(?i)stock|shares|equit|s&p|nasdaq|dow\b|wall street|treasur|yield|bond|\bfed\b|powell|rate cut|rate hike|interest rate|'
          r'inflation|\bcpi\b|\bpce\b|jobs|payroll|unemployment|gdp|recession|earnings|revenue|profit|guidance|forecast|'
          r'oil|crude|opec|gold|dollar|yen|yuan|tariff|trade|export|chip|semiconductor|nvidia|\bai\b|data center|'
          r'ipo|merger|acquisition|takeover|buyback|dividend|bank|credit|debt|default|bankrupt|layoff|market')

try:
    NWS = pd.read_csv(f'{DAY}/{TODAY}_뉴스.csv', encoding='utf-8-sig').fillna('')
    SEN = pd.read_csv(f'{DAY}/{TODAY}_뉴스감성.csv', encoding='utf-8-sig')
    SEN = SEN.drop_duplicates('제목')[['제목', '긍정', '부정', '중립']]
    NT_X = NWS.drop_duplicates('제목').merge(SEN, on='제목', how='inner')
    nt_names = set(u['정식 종목명'].astype(str))
    nt_us = set(u.loc[u['시장'].isin(MARKETS), '정식 종목명'].astype(str))

    def _media_ok(r):
        tail = _re.search(r'\(([^()]*)\)\s*$', str(r['제목']))
        where = ' '.join([str(r['출처']), str(r['링크']), tail.group(1) if tail else '',
                          str(r['종목']) if r['출처'] == '아침 정리' else ''])
        return bool(_re.search(MEDIA, where))

    NT_X = NT_X[NT_X.apply(_media_ok, axis=1)]
    NT_X = NT_X[~NT_X['종목'].astype(str).isin(nt_names - nt_us)]                  # 한국·일본 종목 기사 빼기
    NT_X['종목'] = NT_X['종목'].where(NT_X['종목'].astype(str).isin(nt_us), '')       # 매체 이름 등은 종목이 아님
    nt_t = NT_X['제목'].astype(str)
    NT_X['구분'] = ['세계 정세' if _re.search(GEO, t) else '종목' if k else '시장' for t, k in zip(nt_t, NT_X['종목'])]
    NT_X = NT_X[(NT_X['구분'] != '시장') | nt_t.str.contains(NEWS_KEEP, regex=True) | nt_t.str.contains(MKT_EN, regex=True)]
    NT_X = NT_X[~NT_X['제목'].astype(str).str.contains(NEWS_DROP, regex=True)]
    NT_X['판정'] = ['긍정' if p >= CUT and p > n_ else '부정' if n_ >= CUT else '중립' for p, n_ in zip(NT_X['긍정'], NT_X['부정'])]
    NT_X['강도'] = NT_X[['긍정', '부정']].max(axis=1)
    NT_X['_중립'] = (NT_X['판정'] == '중립').astype(int)
    NT_X = NT_X.sort_values(['_중립', '강도'], ascending=[True, False])
    nt_pick, nt_cnt = [], {}
    nt_geo = NT_X[NT_X['구분'] == '세계 정세'].sort_values('강도', ascending=False).head(GEO_SLOTS)
    nt_pick += [r for _, r in nt_geo.iterrows()]
    for _, r in NT_X.drop(nt_geo.index).iterrows():
        k = r['종목']
        if k and nt_cnt.get(k, 0) >= PER_STOCK:
            continue
        nt_cnt[k] = nt_cnt.get(k, 0) + 1
        nt_pick.append(r)
        if len(nt_pick) >= TOP_N:
            break
    NT_P = pd.DataFrame(nt_pick, columns=NT_X.columns)
    try:
        NT_PX = pd.read_csv(f'{DAY}/{TODAY}_시세.csv', encoding='utf-8-sig')
        nt_chg = dict(zip(NT_PX['정식 종목명'].astype(str), NT_PX['등락률(%)']))
    except Exception:
        nt_chg = {}
    NT_P['등락률(%)'] = [nt_chg.get(k, '') if k else '' for k in NT_P['종목']]
    NT_P.insert(0, '순위', range(1, len(NT_P) + 1))
    NT_P = NT_P[['순위', '구분', '시각(한국)', '판정', '긍정', '부정', '종목', '등락률(%)', '제목', '출처', '링크']]
    NT_P.to_csv(f'{DAY}/{TODAY}_주가뉴스.csv', index=False, encoding='utf-8-sig')
    log(f'[9 주가뉴스] 후보 {len(NT_X)}건 중 {len(NT_P)}건(긍정 {int((NT_P["판정"] == "긍정").sum())}, '
        f'부정 {int((NT_P["판정"] == "부정").sum())}, 중립 {int((NT_P["판정"] == "중립").sum())})')
except Exception as e:
    traceback.print_exc()
    log(f'[9 주가뉴스] 실패: {type(e).__name__} {e}')
