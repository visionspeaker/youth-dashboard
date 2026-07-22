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

## 새 주차 추가 방법 (예: 260726 / 7월 4주차)
`weeks_incoming.json` 에 아래 형식으로 신규 주차만 넣고 `compute.py`→`build_html.py` 실행:
```json
{
  "report":  { "260726": [월,재적학생,출석학생,결석,장기결석,새친구수, 십일조,감사헌금,주일헌금,특별헌금,선교헌금,지목헌금] },
  "teacher": { "260726": 교사수 },
  "absent":  { "260726": "이름,이름,..." },
  "offerRows": [ ["2026-07-26","주일헌금",금액,"이름, 이름, ..."], ["2026-07-26","구제/선교",금액,"1명"], ["2026-07-26","기타",금액,"지목/찬조 설명"] ],
  "generated": "2026-07-26"
}
```
- report 배열은 **12개 숫자**(순서 고정). 금액은 정수(콤마 없이).
- absent 는 결석자명단 탭의 그 주 결석자 이름을 쉼표로. (현 재적만 집계에 반영됨)
- offerRows 는 헌금명단 탭 행. `기타`(지목·찬조)는 헌금 합계에서 제외되지만 참여명단엔 표시됨.
- 명부/새친구/장기표시가 바뀌면 `roster` / `newfriends` / `chronic` 전체를 override 로 넣는다.

## 집계 규칙 (compute.py/template.html 에 구현됨)
- 출석률=학생 기준(새친구 포함). 완전개근=1월부터 결석 0회.
- **결석/장기결석 구분**: 시트 표시가 아니라 **연속 결석 주수** — 1~4주=결석, 5주 이상=장기결석(선택주 기준, template 렌더가 계산).
- 헌금 도넛/합계는 **지목헌금 제외**. 항목 표시순서: 십일조·주일헌금·감사헌금·선교헌금.
- 주차 셀렉터는 as-of(선택주까지 누적). 헌금명단 이름 가나다순.

## 검증 & 배포
- 재생성한 index.html 에 다음이 모두 있어야 함(없으면 배포 중단):
  `헌금 참여 명단` `renderOfferList` `setupMotion` `safeUpdate` `minmax(0,1.25fr)` `apple-touch-icon` `주 연속` `noindex`
  또한 직전 index.html 의 90% 미만 크기면 중단.
- 배포: `index.html` 과 `weeks.json` 을 함께 커밋(둘 다 올려야 다음 주 실행이 최신 상태를 받음).
