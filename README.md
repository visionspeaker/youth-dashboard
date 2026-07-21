# 중고등부 대시보드 — 빌드/갱신 파이프라인

송탄영광교회 중고등부 사역 대시보드( https://visionspeaker.github.io/youth-dashboard/ )의
데이터를 **디자인은 그대로 두고** 매주 갱신하기 위한 파일 모음.

## 파일 구성
| 파일 | 역할 | 수정 여부 |
|---|---|---|
| `template.html` | 레이아웃·CSS·JS 원본. 데이터 자리는 `@@DATA_JSON@@` 마커 | **손대지 말 것**(디자인 변경 시에만) |
| `data.json` | 대시보드에 주입되는 집계 데이터(누적 상태) | compute.py가 갱신 |
| `compute.py` | 새 주차만 읽어 data.json에 증분 반영 | 로직 고정 |
| `build_html.py` | data.json + template.html → index.html | 고정 |
| `index.html` | 배포본(GitHub Pages) | build_html.py가 생성 |
| `weeks_incoming.json` | 이번에 반영할 새 주차 원자료(에이전트가 작성) | 매주 교체 |

## 핵심 원칙
- **과거 주차는 재계산하지 않는다.** data.json이 확정 누적치이고, compute.py는 새 주차 델타만 더한다.
- **디자인/레이아웃/카드/애니메이션은 template.html에만 있다.** 데이터 갱신이 이를 건드리지 않는다.
- 이미 반영된 주차(label이 data.json['order']에 존재)는 자동으로 건너뛴다(멱등).

## 매주 갱신 절차
1. 두 구글시트에서 '중고등부' **새(작성완료) 주차**를 읽는다.
   - 주간 사역보고서(`1rXRzno9pE_PYXHR6KX5Hm4FGtrPVVoRUJouxkNmhD5k`): 세 번째 '중고등부' 블록
     → 학생 재적/출석, 교사, 결석(단기), 장기결석, 새친구, 헌금(십일조/감사/주일/선교/지목·금주합계), 작성완료 여부
   - 출석체크(`1-moFQc8npkYh3ARL4SIpIB-Yft60d9srv7YBrmWpXXo`): `결석자명단`(해당주 결석자), `헌금명단`(참여 명단)
   - **미도래/작성중/직전주 복사 주차는 제외.** 마지막 '작성완료' 주가 최신 집계주.
2. 그 주차를 아래 스키마의 dict로 만들어 `weeks_incoming.json`(리스트)에 넣는다.
3. `python3 compute.py`  → data.json 갱신
4. `python3 build_html.py`  → index.html 재생성
5. 검증: index.html에 `헌금 참여 명단 / renderOfferList / setupMotion / safeUpdate / minmax(0,1.25fr) / apple-touch-icon / 주 연속` 이 모두 있고, 크기가 직전 배포본의 90% 이상인지 확인. 하나라도 실패면 **업로드 중단**.
6. index.html을 GitHub( https://github.com/visionspeaker/youth-dashboard )에 업로드·커밋("데이터 갱신 YYYY-MM-DD").

## weeks_incoming.json 한 주차 스키마
```json
{
  "label": "7/26",
  "jae": 43, "chul": 34, "teacher": 15,
  "gyeolseok": 5, "jangkyeol": 8,
  "absents": [ {"name":"홍길동","grade":"고3","chronic":true}, ... ],
  "offering_week_total": 172000,
  "offering_by_cat": {"십일조":0,"감사헌금":0,"주일헌금":92000,"특별헌금":0,"선교헌금":80000},
  "offer_rows": [ {"date":"2026-07-26","item":"주일헌금","amt":92000,"names":["..."],"note":""} ],
  "newfriends_add": [], "newfriend_report": 4,
  "roster": null,
  "note": "260726 작성완료 반영"
}
```
- `chul`은 새친구 포함 학생 출석. `absents`는 재적 기준(결석자명단 행). `gs`는 자동 계산(=len(absents)).
- `offering_by_cat`는 지목헌금 제외(지목은 by_cat에서 자동 제외). `offering_week_total`은 지목 포함 금주합계.
- `roster`는 재적 명부가 바뀐 경우에만 새 리스트로 전달.

## 집계 규칙(고정)
- 출석률 = 학생 기준(chul/jae, 새친구 포함).  KPI '재적' 부제 교사 수 = 보고서 교사값.
- 완전개근(perfect) = 1월부터 결석 0회.  결석 시 자동 제외.
- 헌금 by_cat/total은 지목 제외, KPI offering_total·월별은 지목 포함.  헌금 참여 명단은 가나다순.
