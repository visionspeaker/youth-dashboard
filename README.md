# 중고등부 사역 대시보드 (송탄영광교회)

GitHub Pages: **https://visionspeaker.github.io/youth-dashboard/**

주간 사역보고서 · 온라인 출석부 데이터를 집계한 중고등부 현황 대시보드입니다.
검색 비노출(noindex) 처리되어 있습니다.

## 구조 (증분 갱신 파이프라인)
```
weeks.json (누적 raw)  ─┐
weeks_incoming.json ────┤─▶ compute.py ─▶ data.json ─▶ build_html.py(+template.html) ─▶ index.html
(신규 주차만)           ┘
```
- **template.html** — 레이아웃·CSS·JS 원본. 데이터 자리는 `@@DATA_JSON@@` 마커. **디자인 수정은 여기서만, 그 외 절대 금지.**
- **weeks.json** — 확정 raw 누적 상태(주차별 출결·헌금·명단 등). 갱신의 원천.
- **weeks_incoming.json** — 이번에 추가할 신규 주차만. compute.py 가 weeks.json 에 병합(멱등)하고, 처리 후 `{}` 로 비우면 됨.
- **compute.py** — weeks.json(+incoming) → data.json. 과거 주차 재계산 안 함. `python3 compute.py`
- **build_html.py** — template.html + data.json → index.html. `python3 build_html.py`
- **index.html** — 배포본(GitHub Pages). 아이콘/매니페스트 동봉.

## 데이터 소스 (2026-08 전환)
출석 데이터의 **주 소스 = 교사앱 출석체크가 쌓이는 원천 탭**(온라인 출석부 스프레드시트,
`날짜|반|출석수|재적수|출석명단|결석명단(사유)|저장시각`). 사역보고서는 **대조 검증용**으로만 사용.
- 검증: 2026 1~8월 31주 전부 원천 탭 = 사역보고서(재적·출석·결석 명단) 일치 확인 완료.
- 재적/출석/결석/장기/명단/새친구 = 원천 탭. 헌금 = 헌금 탭. 교사수 = 사역보고서(원천 탭엔 교사 없음).
- 반→학년: 중2남/중2여 → 중2 합산. **새친구 반은 학년별 차트에 별도 항목**으로 표시(`nfclass`).

## 새 주차 추가 방법 (원천 탭 → 자동 변환)
1. 원천 탭·헌금 탭을 CSV(`raw_attend.csv`,`heonggeum.csv`)로 내보낸다.
2. `python3 ingest_sheet.py raw_attend.csv heonggeum.csv [YYMMDD]` 실행 → 신규 주차의 `weeks_incoming.json`
   초안 + **사역보고서 대조 로그** 출력. (파싱: 괄호 사유 안 쉼표 무시, 이름=첫 '(' 앞, 정창빈→정찬빈)
3. 로그의 `teacher` 는 0 으로 나오므로 **사역보고서에서 교사수 확인해 채운다.** 대조에 ⚠ 뜨면 사용자 컨펌.
4. `python3 compute.py` → `python3 build_html.py`.

`weeks_incoming.json` 형식(수기 편집도 가능):
```json
{
  "report":  { "260726": [월,재적학생,출석학생,결석,장기결석,새친구수, 십일조,감사헌금,주일헌금,특별헌금,선교헌금,지목헌금] },
  "teacher": { "260726": 교사수 },
  "absent":  { "260726": "이름,이름,..." },
  "nfclass": { "260726": [새친구재적, 새친구출석] },
  "offerRows": [ ["2026-07-26","주일헌금",금액,"이름, 이름, ..."], ["2026-07-26","구제/선교",금액,"1명"], ["2026-07-26","기타",금액,"지목/찬조 설명"] ],
  "generated": "2026-07-26"
}
```
- report 배열은 **12개 숫자**(순서 고정). 금액은 정수(콤마 없이).
- absent 는 그 주 결석자 전체 이름(비재적 포함). compute.py 가 현 재적만 표시에 반영.
- `nfclass` = 원천 탭 새친구 반 [재적,출석]. 없으면 새친구 막대 0 처리.
- offerRows 의 `기타`(지목·찬조)는 헌금 합계에서 제외되지만 참여명단엔 표시됨.
- 명부/새친구/장기표시가 바뀌면 `roster` / `newfriends` / `chronic` 전체를 override 로 넣는다.

## 집계 규칙 (compute.py/template.html 에 구현됨)
- 출석률=학생 기준(새친구 포함). 완전개근=1월부터 결석 0회.
- **학년별 출석률**: 중1~고3 + **새친구(별도 막대)**. 새친구는 원천 탭 새친구 반 재적/출석 기준.
- **결석/장기결석 구분**: 시트 표시가 아니라 **연속 결석 주수** — 1~4주=결석, 5주 이상=장기결석(선택주 기준, template 렌더가 계산).
- 헌금 도넛/합계는 **지목헌금 제외**. 항목 표시순서: 십일조·주일헌금·감사헌금·선교헌금.
- 주차 셀렉터는 as-of(선택주까지 누적). 헌금명단 이름 가나다순.

## 검증 & 배포
- 재생성한 index.html 에 다음이 모두 있어야 함(없으면 배포 중단):
  `헌금 참여 명단` `renderOfferList` `setupMotion` `safeUpdate` `minmax(0,1.25fr)` `apple-touch-icon` `주 연속` `noindex`
  또한 직전 index.html 의 90% 미만 크기면 중단.
- 배포: `index.html` 과 `weeks.json` 을 함께 커밋(둘 다 올려야 다음 주 실행이 최신 상태를 받음).
