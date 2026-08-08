# -*- coding: utf-8 -*-
"""원천 탭(출석) + 헌금 탭 → weeks_incoming.json (신규 주차만).
주 소스=원천 탭. compute.py 스키마로 변환하고, 기존 weeks.json 과 대조해 검증 로그를 출력한다.

사용:  python3 ingest_sheet.py raw_attend.csv heonggeum.csv [YYMMDD ...]
  - 주차 인자를 주면 그 주만, 없으면 weeks.json 에 없는 '신규' 주차를 자동 선택.
  - 교사수(teacher)는 원천 탭에 없으므로 사역보고서에서 확인해 수기 입력해야 함(0 으로 표기, 로그 경고).
헌금 매핑(헌금탭 항목 → report[6:12] 순서 [십일조,감사,주일,특별,선교,지목]):
  십일조→십일조, 감사헌금→감사, 주일헌금→주일, 구제/선교→선교, 기타→지목. (특별헌금 소스 없음=0)
"""
import sys, json, os, collections, csv, re
import parse_lib as P

HERE=os.path.dirname(os.path.abspath(__file__))
def _p(n): return os.path.join(HERE,n)

def load_heonggeum(path):
    rows=collections.defaultdict(list)  # YYMMDD -> [(iso,항목,금액,명단)]
    for r in csv.DictReader(open(path,encoding="utf-8")):
        k=P.iso2key(r["날짜"]); rows[k].append((r["날짜"],r["항목"].strip(),int(r["금액"] or 0),r.get("명단","").strip()))
    return rows

HG_MAP={"십일조":0,"감사헌금":1,"주일헌금":2,"구제/선교":4,"기타":5}  # report[6:12] 상대 인덱스
HG_ITEM_TO_OFFER={"주일헌금":"주일헌금","감사헌금":"감사헌금","십일조":"주일헌금","구제/선교":"구제/선교","기타":"기타"}

def month_of(key): return int(key[2:4])

def build(raw_path, hg_path, weeks_path, only=None):
    raw=P.load_raw(raw_path)
    hg=load_heonggeum(hg_path)
    W=json.load(open(weeks_path,encoding="utf-8"))
    existing=set(W["report"].keys())
    # 결석 이력(과거 weeks.json + 원천 전체)로 연속결석 계산
    absent_hist={}
    for k in sorted(set(list(existing)+list(raw.keys()))):
        if k in raw:
            _,_,_,_,ab=P.week_totals(raw[k]); absent_hist[k]=set(ab)
        elif k in W["absent"]:
            absent_hist[k]={x.strip() for x in W["absent"][k].split(",") if x.strip()}
    roster={n for n,g in W["roster"]}
    targets = only if only else sorted(k for k in raw if k not in existing)
    inc={"report":{},"teacher":{},"absent":{},"offerRows":[],"nfclass":{},
         "generated":""}
    log=[]
    for k in sorted(targets):
        if k not in raw: log.append(f"[{k}] 원천 탭에 없음 — 건너뜀"); continue
        mj,mc,nfj,nfc,ab=P.week_totals(raw[k])
        cur=[n for n in ab if n in roster]
        jang=[n for n in cur if P.consec_absent(n,k,absent_hist)>=5]
        gyeol=[n for n in cur if n not in jang]
        # 헌금
        hg6=[0,0,0,0,0,0]  # 십일조,감사,주일,특별,선교,지목
        for iso,item,amt,lst in hg.get(k,[]):
            if item in HG_MAP: hg6[HG_MAP[item]]+=amt
        rep=[month_of(k), mj, mc+nfc, len(gyeol), len(jang), nfc]+hg6
        inc["report"][k]=rep
        inc["teacher"][k]=0  # ⚠ 사역보고서에서 확인해 채울 것
        inc["absent"][k]=",".join(ab)  # 전체 명단 저장(비재적 포함); compute.py 가 현재적만 표시
        inc["nfclass"][k]=[nfj,nfc]
        for iso,item,amt,lst in hg.get(k,[]):
            inc["offerRows"].append([iso, HG_ITEM_TO_OFFER.get(item,item), amt, lst])
        log.append(f"[{k}] 재적{mj} 출석{mc+nfc}(학생{mc}+새친구{nfc}) 결석{len(gyeol)} 장기{len(jang)} "
                   f"새친구{nfc} 헌금{sum(hg6[:5])+hg6[5]}  ⚠교사수=사역보고서확인 필요")
        # ---- 사역보고서 대조 (기존 weeks.json 에 이미 있으면) ----
        if k in existing:
            old=W["report"][k]; oab={P.norm_name(x) for x in W["absent"][k].split(",") if x.strip()}
            diff=[]
            if old[1]!=mj: diff.append(f"재적 원천{mj}≠사역{old[1]}")
            if old[2]!=mc+nfc: diff.append(f"출석 원천{mc+nfc}≠사역{old[2]}")
            if set(ab)!=oab: diff.append(f"명단 원천-{sorted(set(ab)-oab)} 사역-{sorted(oab-set(ab))}")
            # 결석계는 현재적 기준(원천) vs 원본 report 숫자 — 참고용
            if old[3]+old[4]!=len(cur): diff.append(f"결석계(현재적) 원천{len(cur)}≠사역report{old[3]+old[4]}")
            log.append("   대조: "+("일치 ✅" if not diff else " / ".join(diff)+" ⚠"))
        else:
            log.append("   (신규 주차 — 사역보고서 교차확인 권장)")
    return inc, log

if __name__=="__main__":
    raw=sys.argv[1] if len(sys.argv)>1 else _p("raw_attend.csv")
    hgp=sys.argv[2] if len(sys.argv)>2 else _p("heonggeum.csv")
    only=[a for a in sys.argv[3:]] or None
    inc,log=build(raw,hgp,_p("weeks.json"),only)
    print("\n".join(log))
    print("\n=== weeks_incoming(미리보기) ===")
    print(json.dumps(inc,ensure_ascii=False,indent=1)[:1500])
