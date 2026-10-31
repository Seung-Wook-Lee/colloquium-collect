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
| 9 | `blocks/b09_sector.py` (+ `sector.py`) | 닉스 팀 섹터 순환: 한국 섹터 ETF 14개를 TIGER 200과 비교(초과수익·모멘텀 순위·로테이션 사분면·20주선·7개 기준), 라케시스·클로토·아트로포스 판정(룰 v1, 2026-10-29 의장 승인) | `_섹터.csv`, `_섹터궤적.csv` |
| 9 | `blocks/b09_flow.py` | ETF 자금유입: 국내 ETF 30·미국 ETF 10 + 미국 섹터 비교용(SPDR 섹터 11, SPY·QQQ·SOXX·MAGS). 상장좌수 변화 × NAV로 1·5·20일 유입 (한투 좌수·순자산, 야후 순자산, SPDR 공식 이력) | `_ETF자금.csv`, `00_누적/00_ETF좌수이력.csv` |
| 10 | `blocks/b10_briefing.py` | 오늘 브리핑(텍스트) | `_브리핑.txt` |
| 10 | `blocks/b10_gemini.py` | 제미나이 위원(뉴스 국장, 피터·섹터 데스크, 엘피스) 발언 원고 — 회의실은 그대로 대독. 키 없으면 건너뜀 | `_위원_뉴스국장.txt`, `_위원_피터.txt`, `_위원_엘피스.txt` |
| 11 | `blocks/b11_summary.py` | 점검 요약, 드라이브에 올리기 | `_수집점검.txt` |

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

### 포트폴리오 탭 (계산은 `portfolio.py`)
- 읽는 파일: 드라이브 '실전 투자 자료'(없으면 '콜로키움/포트폴리오')의 `주력포트폴리오_Ver.YYYYMMDD_HHMM.csv`와 `주력포트폴리오_제안비중_Ver.….csv` 최신본. 금액 없이 종목·비중(%)만. 화면에서 csv를 직접 올려도 됩니다(저장 안 함).
- 필수 칸: `종목`, `전체비중%`. 있으면 쓰는 칸: `시장`, `구분`(현금성·지수·주식·ETF), `번호`(콜로키움 100), `마감비율%(시장내)`, `수익률%`, `절세매도후보`. 종목 이름은 `app/portfolio_map.csv`(콜로키움 100 번호·티커·담당 데스크)로 맞춥니다. 유니버스·담당표가 바뀌면 이 파일도 갈아 끼웁니다.
- 보여 주는 것: 첫 목표 진척(기준일 뒤 수익률 vs 연말 +20%) / 1 목표 배분(시장마다 현금성30·지수30·주식40) 대비 / 2 쏠림(데스크·업종·상위 종목·실효 종목 수) / 3 위험도(가중 베타, 1·3년 최대 낙폭, 1년 상관) / 4 보유 종목 닉스 지표(사실만) / 5 매매 후보표(제안·마감 비중과의 차이).
- '실전 투자 자료' 폴더를 읽으려면 `apps_script/Code.gs`를 새 버전으로 배포해야 합니다(ALLOWED에 추가됨).
