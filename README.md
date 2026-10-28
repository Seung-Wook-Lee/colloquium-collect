# 콜로키움 자료수집

매일 아침 콜로키움 100 종목과 시장 지표를 모아 의장님 구글 드라이브 `콜로키움 수집데이터/YYYYMMDD/`에 넣는 프로그램입니다.
GitHub Actions가 GitHub 컴퓨터에서 돌리므로 PC를 켜 둘 필요가 없습니다.

## 블록 (레고처럼 순서대로 실행)
| 블록 | 파일 | 하는 일 | 만드는 파일 |
|---|---|---|---|
| 0 | `blocks/b00_setup.py` | 키 읽기, 드라이브에서 유니버스 엑셀·누적 파일 받기 | — |
| 1 | `blocks/b01_prices.py` | 야후 시세 100종목 | `00_가격이력.csv`, `_시세.csv` |
| 2 | `blocks/b02_kis.py` | 한투 PER·PBR (막히면 야후로 대체) + 야후 선행 PER | `_밸류에이션.csv` |
| 3 | `blocks/b03_raw.py` | 야후·FRED·뉴욕연준·일본 재무성·CNN 원자료 | `_연준매크로.csv` |
| 4 | `blocks/b04_macro.py` | 지수·환율·금리·물가·성장·원자재 (YTD, 1달, 사상 최고 대비) | `_매크로.csv` |
| 5 | `blocks/b05_risk.py` | 공포탐욕+7개 지표 해석, 변동성·신용·스트레스·침체·자금 | `_공포탐욕.csv`, `_리스크.csv` |
| 6 | `blocks/b06_dart.py` | 한국 개별주 TTM·연환산 PER (DART) | `_DART실적.csv` |
| 7 | `blocks/b07_sec.py` | 미국 개별주 TTM·연환산 PER (SEC) | `_SEC실적.csv` |
| 8 | `blocks/b08_checklist.py` | 리오팀 체크리스트 1~32 | `_시장지표.csv` |
| 9 | `blocks/b09_news.py` | 간밤 국제 뉴스(연합뉴스), 실적·경제지표 일정(DART·야후·FRED) | `_뉴스.csv`, `_일정.csv` |
| 10 | `blocks/b10_briefing.py` | 오늘 브리핑(텍스트) | `_브리핑.txt` |
| 11 | `blocks/b11_summary.py` | 점검 요약, 드라이브에 올리기 | `_수집점검.txt` |

새 블록은 브리핑(블록 10) 앞 번호로 파일을 만들고, 맨 위 설명 칸을 같은 양식으로 채웁니다.

## 비밀값 (GitHub → Settings → Secrets and variables → Actions)
`KIS_APP_KEY`, `KIS_APP_SECRET`, `FRED_KEY`, `DART_KEY`, `SEC_EMAIL`, `DRIVE_URL`, `DRIVE_TOKEN`
- 계좌번호는 넣지 않습니다. 한투는 조회만 합니다.
- `DRIVE_URL`·`DRIVE_TOKEN`은 `apps_script/Code.gs`(드라이브 창구)를 의장님 구글 계정에 배포해서 얻습니다.

## 실행
- 손으로: Actions → 콜로키움 자료수집 → Run workflow (블록 칸에 `9`처럼 번호를 넣으면 그 블록만 시험으로 돌림, 비우면 전부)
- 매일 아침 7시(한국): `.github/workflows/collect.yml`의 `schedule`로 자동 실행 (2026-10-28 켬, 8시 프리장 전에 끝나도록).

## 화면 (스트림릿)

- 코드: `app/streamlit_app.py` (라이브러리는 `app/requirements.txt`)
- 탭: 오늘 시장 / 종목(보유·관심·시장 거르기, PER 세 칸) / 주봉 차트(20주·60주선) / 수집 점검
- 자료는 수집 프로그램과 같은 드라이브 창구로 읽습니다. 스트림릿 클라우드 Secrets에 `DRIVE_URL`, `DRIVE_TOKEN` 두 줄을 넣습니다.
- PC에서 돌릴 때: `COLLOQ_DATA="(드라이브 데스크톱의 콜로키움 수집데이터 폴더)" streamlit run app/streamlit_app.py`
