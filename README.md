# 콜로키움 자료수집

매일 아침 콜로키움 100 종목과 시장 지표를 모아 의장님 구글 드라이브 `콜로키움 수집데이터/YYYYMMDD/`에 넣는 프로그램입니다.
GitHub Actions가 GitHub 컴퓨터에서 돌리므로 PC를 켜 둘 필요가 없습니다.

## 블록 (레고처럼 순서대로 실행)
| 블록 | 파일 | 하는 일 | 만드는 파일 |
|---|---|---|---|
| 0 | `blocks/b00_setup.py` | 키 읽기, 드라이브에서 유니버스 csv·누적 파일 받기 | — |
| 1 | `blocks/b01_prices.py` | 야후 시세 100종목 | `00_가격이력.csv`, `_시세.csv` |
| 2 | `blocks/b02_kis.py` | 한투 PER·PBR (막히면 야후로 대체) + 야후 선행 PER | `_밸류에이션.csv` |
| 3 | `blocks/b03_raw.py` | 야후·FRED·뉴욕연준·일본 재무성·CNN 원자료 | `_연준매크로.csv` |
| 4 | `blocks/b04_macro.py` | 지수·환율·금리·물가·성장·원자재 (YTD, 1달, 사상 최고 대비) | `_매크로.csv` |
| 5 | `blocks/b05_risk.py` | 공포탐욕+7개 지표 해석, 변동성·신용·스트레스·침체·자금 | `_공포탐욕.csv`, `_리스크.csv` |
| 6 | `blocks/b06_dart.py` | 한국 개별주 TTM·연환산 PER, 잠정실적 반영 연환산 PER (DART) | `_DART실적.csv` |
| 7 | `blocks/b07_sec.py` | 미국 개별주 TTM·연환산 PER (SEC) | `_SEC실적.csv` |
| 8 | `blocks/b08_checklist.py` | 리오팀 체크리스트 1~32 | `_시장지표.csv` |
| 8-리오 | `blocks/b08_rio.py` | 리오 매크로 체크리스트: 7개 항목 꺾임, 국면, 반대 신호 n/7 | `_매크로체크리스트.csv` |
| 9 | `blocks/b09_news.py` | 간밤 뉴스(연합뉴스 국제·야후 종목별·CNBC·아침 정리 기사(구글 뉴스 검색) 각 10건), 실적·경제지표 일정(DART·야후·FRED, 간밤 발표 포함) | `_뉴스.csv`, `_일정.csv` |
| 9 | `blocks/b09_nyx.py` (+ `nyx.py`) | 닉스 팀 7개 기준(지지·저항, 볼린저, RSI, CCI, 스토캐스틱 슬로우, 이격도, 일목)과 차트 패턴, 일봉·주봉 | `_닉스.csv` |
| 9 | `blocks/b09_sector.py` (+ `sector.py`) | 닉스 팀 섹터 순환: 한국 섹터 ETF 14개를 TIGER 200과 비교(초과수익·모멘텀 순위·로테이션 사분면·20주선·7개 기준), 라케시스·미스 차트·아트로포스 판정(룰 v1, 2026-10-29 의장 승인) | `_섹터.csv`, `_섹터궤적.csv` |
| 9 | `blocks/b09_japan.py` | 아야카 상(일본 전담, 11/7): 일본 날씨(TOPIX·닛케이·J-REIT 20·60주선, 엔/달러, 일본 10년), 일본 종목 주봉 위치·RSI, 토요일 야후 PER·PBR·배당 스냅숏, 실적 달력, TDnet 자사주·자본비용·배당·실적 공시 | `_일본.csv`, `_일본.txt`, `00_누적/00_일본_밸류스냅숏.csv`·`00_일본_실적달력.csv`·`00_일본공시_누적.csv` |
| 9 | `blocks/b09_heatmap.py` (+ `heatmap.py`) | 스트림릿 '오늘 시장' 히트맵: S&P500(SPDR 섹터 11 × 상위 10, 칸 크기 시총)과 콜로키움 100(층별) 1일·1주·1달 등락 (판정 없음) | `_히트맵.csv` |
| 9 | `blocks/b09_valuation.py` (+ `valuation.py`) | 스트림릿 '1. 시장' 맨 위 지수 밸류·등락: 주요국·미국 지수 이달·연초 이후 등락, 필반 200일 이격도(1995~, 100 기준), S&P500·나스닥100·필반 12개월 선행 P/E(구성종목 합산, 오늘부터 누적; 나스닥100·필반 매일, S&P500 토요일) | `_지수등락.csv`, `_필반이격도.csv`, `_지수선행PE_종목.csv`, `00_누적/00_지수선행PE.csv`·`00_지수구성종목.csv` |
| 9 | `blocks/b09_flow.py` | ETF 자금유입: 국내 ETF 30·미국 ETF 10 + 미국 섹터 비교용(SPDR 섹터 11, SPY·QQQ·SOXX·MAGS). 상장좌수 변화 × NAV로 1·5·20일 유입 (한투 좌수·순자산, 야후 순자산, SPDR 공식 이력) | `_ETF자금.csv`, `00_누적/00_ETF좌수이력.csv` |
| 10 | `blocks/b10_briefing.py` | 오늘 브리핑(텍스트) | `_브리핑.txt` |
| 11 | `blocks/b11_summary.py` | 점검 요약, 드라이브에 올리기 | `_수집점검.txt` |

## 따로 도는 작업
- 유튜브 공부자료: `.github/workflows/youtube.yml` + `youtube/` (매일 08:30·21:00, 설명 `youtube/읽는법.txt`)

새 블록은 브리핑(블록 10) 앞 번호로 파일을 만들고, 맨 위 설명 칸을 같은 양식으로 채웁니다.

## 비밀값 (GitHub → Settings → Secrets and variables → Actions)
`KIS_APP_KEY`, `KIS_APP_SECRET`, `FRED_KEY`, `DART_KEY`, `SEC_EMAIL`, `DRIVE_URL`, `DRIVE_TOKEN`, `GEMINI_API_KEY`
- `GEMINI_API_KEY`는 Google AI Studio 무료 키. 위원 기준은 드라이브 '페르소나 스토리/위원총괄_Ver.…txt' 최신을 읽고, 창구가 그 폴더를 못 열면 `prompts/위원총괄.txt`를 씁니다.
- 계좌번호는 넣지 않습니다. 한투는 조회만 합니다.
- `DRIVE_URL`·`DRIVE_TOKEN`은 `apps_script/Code.gs`(드라이브 창구)를 의장님 구글 계정에 배포해서 얻습니다.

## 실행
- 손으로: Actions → 콜로키움 자료수집 → Run workflow (블록 칸에 `9`처럼 번호를 넣으면 그 블록만 시험으로 돌림, 비우면 전부)
- 매일 아침 7시(한국): `.github/workflows/collect.yml`의 `schedule`로 자동 실행 (2026-10-28 켬, 8시 프리장 전에 끝나도록).

## 화면 (스트림릿)

- 코드: `app/streamlit_app.py` (라이브러리는 `app/requirements.txt`)
- 탭: 오늘 시장 / 회의록 / 종목(보유·관심·시장 거르기, PER 세 칸) / 포트폴리오(아래) / 섹터 순환(사분면 그림·8주 궤적·판정 표) / 주봉 차트(20주·60주선) / 수집 점검
- 자료는 수집 프로그램과 같은 드라이브 창구로 읽습니다. 스트림릿 클라우드 Secrets에 `DRIVE_URL`, `DRIVE_TOKEN` 두 줄을 넣습니다.
- PC에서 돌릴 때: `COLLOQ_DATA="(드라이브 데스크톱의 콜로키움 수집데이터 폴더)" streamlit run app/streamlit_app.py`

## 차트 실험실 (2026-11-13)
보조지표만으로 하는 기술적 분석 실험은 `chart_lab/`(설명 `chart_lab/README.md`). Actions → 차트 실험실 실행 → 실험 이름. 07시 수집과 별개, 결과는 드라이브 `콜로키움 수집데이터/차트실험실/`.

## 회의 원고 자동 생성 (2026-11-17)

위원 발언과 '오늘의 한 종목'은 AI가 쓰지 않고 코드가 만든다. 07시 수집이 끝나면 `.github/workflows/meeting.yml`이 `meeting/daily.py`를 돌린다.

- 순서: 드라이브 07시 파일 받기 → 사건상태·변수달력(`meeting/events.py`, 승인 매체 RSS·07시 일정.csv 규칙) → 야후 보조 자료(`quant_center/fetch_*.py`) → 퀀트센터 엔진 → 위원 원고(`meeting/personas.py`) → 드라이브.
- 결과: `콜로키움 수집데이터/YYYYMMDD/YYYYMMDD_회의원고.txt`, `_발표.json`(스트림릿 회의 발표 화면), `_오늘의한종목.csv`, `_판정표.csv`, `_시장블록.csv`, `_사건상태.csv`, `_변수달력.csv`, `최신_회의원고.txt`.
- 전날 보조 자료·사건 로그는 `콜로키움 수집데이터/00_퀀트입력/`에 이어 쓴다(처음엔 `meeting/seed/`).
- 위원을 고칠 때: 숫자·낱말·순서·한 종목 규칙은 `meeting/rules.yaml`, 문장 틀은 `meeting/personas.py`의 그 위원 함수만 고친다.
- 손 시험: `python meeting/daily.py --local <입력 폴더> --skip-fetch`.
- 돌발 질문(원고에 없는 질문): `python meeting/ask.py --dir <그날 드라이브 폴더> "질문"` — 종목 이름이면 담당 위원이 그날 판정표 줄, 위원 이름·낱말이면 원고 그 위원 칸, 없으면 '룰 미정' + 장부(`회의록/돌발질문_장부.csv`). 규칙은 rules.yaml `돌발질문`. 그날 폴더에 `YYYYMMDD_종목색인.csv`(별칭·담당 데스크)도 올라간다.
- 팀Q(비공개 저장소) 아침보고·퀀트자료를 매일 받으려면 Secrets에 `TEAMQ_TOKEN`(team_q 읽기 권한)을 넣는다. 없으면 전날 사본을 쓰고 원고 머리에 기준일을 적는다.
