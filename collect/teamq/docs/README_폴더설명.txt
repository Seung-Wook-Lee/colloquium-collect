Team_Q__chatgpt — 팀 Q 연구용 과거 데이터 (2026-11-02 수집)
raw/       받은 그대로(출처별). processed/ 가공본(백테스트용)
  prices/            일봉 10년(상장 이후). processed: close_raw=당시 실제 가격, adj_close=배당·분할 반영
  fundamentals/      SEC·DART 원본 / 표준 항목(공시일 filed 포함) / TTM·시점값과 사용 가능일(available)
  valuation/         날짜별 PER·PBR·PSR·PCR·EV/EBITDA·ROE·ROA·ROIC·배당·FCF수익률 (그날까지 공시된 재무만 사용)
  corporate_actions/ 배당·분할(야후), DART 공시 목록·배당·주식총수, SEC 공시 목록, 실적 발표일
  etf/               ETF 현재 정보(현재 값, 과거로 쓰지 말 것)
  macro/             FRED(최신 수정값)·ALFRED(발표 당시 값)·야후 지수·환율·변동성·일본 국채
  market_events/     급락·VIX·금리·환율 급변, FOMC·지표 발표일, 기업 이벤트(processed/events)
  metadata/          출처(sources), 실행 결과(run_status), 품질(quality_prices), 재무 확보 기간(coverage_fundamentals), 보고서 txt
미래정보 누수 방지: 재무는 공시일 다음 날부터 사용, 분기말에서 450일 지난 값은 결측. 최신 수정 매크로값 대신 alfred_first_release 사용 권장.
못 구한 값은 비워 두었음(임의로 만들지 않음).
