# ======================================================================
# [블록 9-주가뉴스] 오늘의 주가 뉴스 — 후보 20건 + 프로그램이 고른 10건, 긍정·부정 판정 (2026-11-20 의장)
#   하는 일  : 블록 9(뉴스)가 모은 밤사이(어제 18시 이후) 기사 중 ① 미국 매체(CNBC·CNN·블룸버그) ② 미국 뉴스
#              (미국 종목 기사이거나 종목 없는 시장·세계 정세 기사, 한국·일본 종목 기사와 DART는 뺌) ③ 주가 관련(종목 기사,
#              세계 정세 낱말, 시장 낱말)인 것만 남기고, 블록 9-감성(FinBERT)의 확률로 긍정·부정·중립을 붙인다.
#              판정: 긍정 확률 ≥ CUT 이면 긍정, 부정 확률 ≥ CUT 이면 부정, 아니면 중립.
#              고르기: news_pick.py — 의장 판정 누적(뉴스실험실/00_주가뉴스_판정누적.csv)으로 만든 점수표 순.
#                      판정이 모자라면 FinBERT 긍정·부정 확률이 센 순. 같은 종목은 최대 PER_STOCK건.
#              점수 상위 N_CAND건 = 후보(의장이 스트림릿 '주가 뉴스 고르기'에서 10건 고름), 그중 상위 TOP_N건 = 프로그램 선택.
#              종목 기사에는 그 종목의 전일 등락률(_시세.csv)을 붙인다.
#              11/20 01:38 의장 "국내 뉴스보다는 밤새 미국 뉴스에만 집중", 01:41 "20개 주면 내가 10개 고르며 기준을 줄테니 맞춰 고르는 코딩"
#   읽는 것  : YYYYMMDD_뉴스.csv, YYYYMMDD_뉴스감성.csv, YYYYMMDD_시세.csv, 드라이브 판정 누적
#   만드는 것: 수집데이터/YYYYMMDD/YYYYMMDD_주가뉴스후보.csv (20건, 프로그램추천 1/0, 점수)
#              수집데이터/YYYYMMDD/YYYYMMDD_주가뉴스.csv (프로그램이 고른 10건)
#              (순위, 구분(세계 정세/종목/시장), 시각(한국), 판정, 긍정, 부정, 종목, 등락률(%), 제목, 요약, 출처, 링크, 점수)
#   쓰는 위원: 뉴스 국장(회의 원고 meeting/personas.py)
#   고칠 곳  : 건수 TOP_N·N_CAND, 판정 기준 CUT, 미국 매체 MEDIA, 종목 시장 MARKETS, 낱말 GEO·MKT_EN, 명시 규칙은 news_pick.py
#   실패하면 : 점검 파일에 '실패'로 남기고 다음 블록은 계속 실행
# ======================================================================
import news_pick
TOP_N = 10            # 의장 11/20 "10개 정도"
N_CAND = 20           # 의장이 고를 후보 수
CUT = 0.6             # 긍정·부정 판정 확률 기준
PER_STOCK = 2         # 같은 종목 최대 건수
# 의장 11/10 승인 해외 매체(CNBC·CNN·블룸버그) — 출처·링크·제목 끝 (매체)로 확인
MEDIA = r'(?i)cnbc|\bcnn\b|cnn\.com|블룸버그|bloomberg'
MARKETS = ['미국']    # 종목 기사는 이 시장 종목만
# 11/20 01:40 의장 "전세계 뉴스. 전쟁이 나면 알려줘야. 이란·우크라이나" — 세계 정세 기사도 후보에 넣는다. 01:41 "발생할 때" → 자리 따로 두지 않고 의장 판정으로 배운다
GEO = (r'(?i)\bwar\b|warfare|iran|israel|gaza|hamas|hezbollah|houthi|ukrain|russia|putin|zelensky|kremlin|missile|airstrike|'
       r'ceasefire|truce|peace (talks|deal|plan)|invasion|invade|military|troops|nato|taiwan|north korea|pyongyang|'
       r'middle east|red sea|strait of hormuz|sanction|coup|terror|전쟁|이란|이스라엘|가자|우크라|러시아|푸틴|젤렌스키|'
       r'미사일|공습|휴전|종전|평화협상|침공|군사|나토|대만|북한|중동|홍해|호르무즈|제재')
# 11/20 01:44 의장 "전쟁 기사는 발생 때 꼭 넣어야" — 발생 신호(규칙, 점수보다 먼저 맨 위)
#   ① 처음 등장: 그 나라·세력 이름이 지난 7일 누적에 1건 이하 ② 보도 급증: 오늘 밤 3건 이상이고 7일 하루 평균의 3배 이상
#   ③ 발생 동사(OUTBREAK)가 제목에 있음. (①또는②) 그리고 ③ → 발생신호 1. 누적이 GEO_MIN_HIST일 미만이면(첫날) 판단하지 않는다.
#   누적: 수집데이터/00_누적/00_세계정세기사.csv (날짜, 대상, 제목) — 오늘 뉴스.csv 전체 제목에서 대상 이름이 나온 것, 30일 보관
GEO_ACTORS = {'이란': r'iran|tehran|이란', '이스라엘·가자': r'israel|gaza|hamas|이스라엘|가자|하마스',
              '레바논·헤즈볼라': r'lebanon|hezbollah|레바논|헤즈볼라', '예멘·홍해': r'houthi|yemen|red sea|후티|예멘|홍해',
              '우크라이나·러시아': r'ukrain|russia|kremlin|putin|zelensky|우크라|러시아|푸틴|젤렌스키',
              '대만·중국군': r'taiwan|pla\b|south china sea|대만|남중국해', '북한': r'north korea|pyongyang|kim jong|북한|평양|김정은',
              '인도·파키스탄': r'india.{0,20}pakistan|pakistan.{0,20}india|kashmir|카슈미르', '시리아': r'syria|시리아',
              '베네수엘라': r'venezuela|베네수엘라', '호르무즈': r'hormuz|호르무즈'}
OUTBREAK = (r'(?i)launch|invade|invasion|attack|strike|struck|bomb|missile|shell|declare[sd]? war|war (erupt|break)|'
            r'escalat|mobiliz|troops (enter|cross)|offensive|retaliat|shot down|seiz|blockade|'
            r'공습|폭격|침공|공격|개전|선전포고|확전|보복|격추|발사|봉쇄|교전')
GEO_DAYS, GEO_MIN_HIST = 7, 1
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
    # 발생 신호 — 오늘 뉴스.csv 전체 제목으로 대상별 건수를 세고 지난 7일 누적과 비교
    nt_glog_f = f'{KEEP}/00_세계정세기사.csv'
    nt_glog = pd.read_csv(nt_glog_f, dtype=str, encoding='utf-8-sig') if os.path.exists(nt_glog_f) else pd.DataFrame(columns=['날짜', '대상', '제목'])
    nt_today = [{'날짜': TODAY, '대상': a_, '제목': t} for t in NWS['제목'].astype(str).unique()
                for a_, pat in GEO_ACTORS.items() if _re.search('(?i)' + pat, t)]
    nt_past = nt_glog[(nt_glog['날짜'] < TODAY) & (nt_glog['날짜'] >= (pd.Timestamp(TODAY) - pd.Timedelta(days=GEO_DAYS)).strftime('%Y%m%d'))]
    nt_hist = nt_glog.loc[nt_glog['날짜'] < TODAY, '날짜'].nunique()
    nt_new = set()
    for a_ in GEO_ACTORS:
        today_n = sum(1 for x in nt_today if x['대상'] == a_)
        past_n = int((nt_past['대상'] == a_).sum())
        if today_n and nt_hist >= GEO_MIN_HIST and (past_n <= 1 or (today_n >= 3 and today_n >= 3 * past_n / GEO_DAYS)):
            nt_new.add(a_)
    def _outbreak(t):
        if not _re.search(OUTBREAK, t):
            return ''
        return ','.join(a_ for a_ in nt_new if _re.search('(?i)' + GEO_ACTORS[a_], t))
    NT_X['발생대상'] = [_outbreak(t) for t in nt_t]
    NT_X['발생신호'] = (NT_X['발생대상'] != '').astype(int)
    NT_X.loc[NT_X['발생신호'] == 1, '구분'] = '세계 정세'
    nt_glog = pd.concat([nt_glog[nt_glog['날짜'] != TODAY], pd.DataFrame(nt_today, columns=['날짜', '대상', '제목'])])
    nt_glog = nt_glog[nt_glog['날짜'] >= (pd.Timestamp(TODAY) - pd.Timedelta(days=30)).strftime('%Y%m%d')]
    nt_glog.to_csv(nt_glog_f, index=False, encoding='utf-8-sig')
    NT_X = NT_X[(NT_X['구분'] != '시장') | nt_t.str.contains(NEWS_KEEP, regex=True) | nt_t.str.contains(MKT_EN, regex=True)]
    NT_X = NT_X[~NT_X['제목'].astype(str).str.contains(NEWS_DROP, regex=True)]
    NT_X['판정'] = ['긍정' if p >= CUT and p > n_ else '부정' if n_ >= CUT else '중립' for p, n_ in zip(NT_X['긍정'], NT_X['부정'])]
    try:
        NT_PX = pd.read_csv(f'{DAY}/{TODAY}_시세.csv', encoding='utf-8-sig')
        nt_chg = dict(zip(NT_PX['정식 종목명'].astype(str), NT_PX['등락률(%)']))
    except Exception:
        nt_chg = {}
    NT_X['등락률(%)'] = [nt_chg.get(k, '') if k else '' for k in NT_X['종목']]
    nt_lab = None
    try:
        nt_b = gdrive.get(news_pick.LABEL_PATH) if not IN_COLAB else open(f'{BASE_DIR}/{news_pick.LABEL_PATH}', 'rb').read()
        nt_lab = pd.read_csv(io.BytesIO(nt_b), encoding='utf-8-sig') if nt_b else None
    except Exception as e:
        log(f'[9 주가뉴스] 판정 누적 읽기 실패: {type(e).__name__} {e}')
    nt_model, nt_why = news_pick.fit(nt_lab)
    NT_X['점수'] = news_pick.score(NT_X, nt_model)
    NT_X.loc[NT_X['발생신호'] == 1, '점수'] = 3.0          # 의장 규칙: 전쟁 발생 기사는 꼭 넣는다(맨 위)
    NT_X = NT_X[NT_X['점수'] >= 0].sort_values(['점수', '시각(한국)'], ascending=[False, False])
    nt_pick, nt_cnt = [], {}
    for _, r in NT_X.iterrows():
        k = r['종목']
        if k and nt_cnt.get(k, 0) >= PER_STOCK:
            continue
        nt_cnt[k] = nt_cnt.get(k, 0) + 1
        nt_pick.append(r)
        if len(nt_pick) >= N_CAND:
            break
    NT_C = pd.DataFrame(nt_pick, columns=NT_X.columns)
    NT_C['프로그램추천'] = [1 if i < TOP_N else 0 for i in range(len(NT_C))]
    NT_C.insert(0, '순위', range(1, len(NT_C) + 1))
    nt_cols = ['순위', '구분', '시각(한국)', '판정', '긍정', '부정', '종목', '등락률(%)', '제목', '요약', '출처', '링크', '점수', '발생신호', '발생대상']
    NT_C[nt_cols + ['프로그램추천']].to_csv(f'{DAY}/{TODAY}_주가뉴스후보.csv', index=False, encoding='utf-8-sig')
    NT_P = NT_C[NT_C['프로그램추천'] == 1][nt_cols]
    NT_P.to_csv(f'{DAY}/{TODAY}_주가뉴스.csv', index=False, encoding='utf-8-sig')
    log(f'[9 주가뉴스] 발생 신호 {sorted(nt_new) or "없음"}(누적 {nt_hist}일). {nt_why}. 대상 {len(NT_X)}건 → 후보 {len(NT_C)}건 → 선택 {len(NT_P)}건(긍정 {int((NT_P["판정"] == "긍정").sum())}, '
        f'부정 {int((NT_P["판정"] == "부정").sum())}, 중립 {int((NT_P["판정"] == "중립").sum())})')
except Exception as e:
    traceback.print_exc()
    log(f'[9 주가뉴스] 실패: {type(e).__name__} {e}')
