# -*- coding: utf-8 -*-
# 중고등부 대시보드 집계기: weeks.json(누적 raw) + weeks_incoming.json(신규 주차) -> data.json
# ⚠️ 계산 로직은 검증됨. 새 주차는 weeks_incoming.json 로만 추가하고, 과거는 재계산하지 않는다.
import json, collections, os, re
HERE=os.path.dirname(os.path.abspath(__file__))
def _p(n): return os.path.join(HERE,n)
DATA_PATH=_p("data.json")
W=json.load(open(_p("weeks.json"),encoding="utf-8"))
# ---- 신규 주차 병합 (멱등: 같은 주차/헌금행 중복 방지) ----
_incp=_p("weeks_incoming.json")
if os.path.exists(_incp):
    try: INC=json.load(open(_incp,encoding="utf-8"))
    except Exception: INC={}
    for _k in ("report","teacher","absent"):
        if isinstance(INC.get(_k),dict): W[_k].update(INC[_k])
    if isinstance(INC.get("offerRows"),list):
        _seen={(r[0],r[1]) for r in W["offerRows"]}
        for r in INC["offerRows"]:
            if (r[0],r[1]) not in _seen: W["offerRows"].append(r); _seen.add((r[0],r[1]))
    for _k in ("roster","newfriends","joinWeek","excludeCats","chronic","generated"):
        if INC.get(_k): W[_k]=INC[_k]
    json.dump(W,open(_p("weeks.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
# ---- unpack (기존 로직이 기대하는 변수들) ----
roster=[tuple(x) for x in W["roster"]]
grade_of={n:g for n,g in roster}
grade_order=["중1","중2","중3","고1","고2","고3"]
grade_size=collections.Counter(g for n,g in roster)
join_week=dict(W["joinWeek"])
chronic=set(W.get("chronic",[]))
def norm(n): return "정찬빈" if n=="정창빈" else n
absent_raw=W["absent"]
weeks=list(absent_raw.keys())
teacher_jae={k:int(v) for k,v in W["teacher"].items()}
absent={w:[norm(x.strip()) for x in absent_raw[w].split(",")] for w in weeks}
report={k:tuple(v) for k,v in W["report"].items()}
NF_SRC=[dict(x) for x in W["newfriends"]]
OFFER_ROWS=[list(r) for r in W["offerRows"]]
EXCLUDE_CATS=list(W.get("excludeCats",["지목헌금"]))
GEN=W.get("generated","2026-07-18")

def wlabel(w): # 260712 -> 7/12
    m=int(w[2:4]); d=int(w[4:6]); return f"{m}/{d}"

# ===== 1) 월별 출석 =====
month_names={1:"1월",2:"2월",3:"3월",4:"4월",5:"5월",6:"6월",7:"7월"}
mon=collections.defaultdict(lambda:[0,0,0])  # month -> [sum출석, sum재적, cnt]
for w,(m,jae,chul,gs,jk,sc,*rest) in report.items():
    mon[m][0]+=chul; mon[m][1]+=jae; mon[m][2]+=1
monthly=[]
for m in sorted(mon):
    s,j,c=mon[m]
    monthly.append({"month":month_names[m],"avg_chul":round(s/c,1),"avg_jae":round(j/c,1),"rate":round(s/j*100,1),"weeks":c})

# 주차별(라인용)
weekly_series=[{"label":wlabel(w),"jae":report[w][1],"chul":report[w][2],"gs":report[w][3]+report[w][4],
                "rate":round(report[w][2]/report[w][1]*100,1)} for w in report]

# ===== 2) 결석자 명단 (최신 완결주 260712) =====
latest="260712"
def is_current(n): return n in grade_of
latest_absent=[]
for n in absent[latest]:
    if is_current(n):
        latest_absent.append({"name":n,"grade":grade_of[n],"chronic":n in chronic})
# 누적 결석횟수(현 재적)
abs_count=collections.Counter()
for w in weeks:
    for n in set(absent[w]):
        if is_current(n): abs_count[n]+=1

# ===== 3) 완전개근자 (28주 전체 결석 0회, 현 재적) =====
perfect=[]
for n,g in roster:
    jw=join_week.get(n)
    # 신규편입자는 등반 이후 주 대상
    applicable=[w for w in weeks if (jw is None or w>=jw)]
    cnt=sum(1 for w in applicable if n in absent[w])
    if cnt==0:
        perfect.append({"name":n,"grade":g,"note":("신규편입("+wlabel(jw)+")" if jw else "")})
# 준개근 1회
near=[{"name":n,"grade":grade_of[n],"cnt":abs_count[n]} for n,_ in roster if abs_count.get(n,0)==1]

# ===== 4) 헌금 항목별 (완결 28주 누적) =====
cats=["십일조","감사헌금","주일헌금","특별헌금","선교헌금","지목헌금"]
csum={c:0 for c in cats}
for w,v in report.items():
    _,_,_,_,_,_,t,th,su,sp,mi,ji=v
    csum["십일조"]+=t; csum["감사헌금"]+=th; csum["주일헌금"]+=su
    csum["특별헌금"]+=sp; csum["선교헌금"]+=mi; csum["지목헌금"]+=ji
offering_total=sum(csum.values())
# 월별 헌금 합계
mon_off=collections.defaultdict(int)
for w,v in report.items():
    m=v[0]; s=sum(v[6:12]); mon_off[m]+=s
monthly_off=[{"month":month_names[m],"total":mon_off[m]} for m in sorted(mon_off)]

# ===== 5) 새친구 =====
newfriends=[{"name":x["name"],"grade":x["grade"],"date":x["date"],"note":x["note"]} for x in NF_SRC]
newfriend_count_total=sum(report[w][5] for w in report)

# ===== 6) 학년별 출석률 =====
# 최신주(260712) 기준: 재적 - (현재적 결석자수) / 재적
def grade_rate_week(w):
    ga=collections.Counter()
    for n in absent[w]:
        if is_current(n): ga[grade_of[n]]+=1
    out=[]
    for g in grade_order:
        size=grade_size[g]; ab=ga[g]; pres=size-ab
        out.append({"grade":g,"size":size,"present":pres,"absent":ab,"rate":round(pres/size*100,1)})
    return out
grade_latest=grade_rate_week(latest)
# 기간평균: 각 주 현재적 출석/재적 평균 (단순평균)
gsum=collections.defaultdict(lambda:[0,0])
for w in weeks:
    ga=collections.Counter()
    for n in absent[w]:
        if is_current(n): ga[grade_of[n]]+=1
    for g in grade_order:
        gsum[g][0]+=(grade_size[g]-ga[g]); gsum[g][1]+=grade_size[g]
grade_avg=[{"grade":g,"rate":round(gsum[g][0]/gsum[g][1]*100,1)} for g in grade_order]

out={
 "generated":GEN,
 "latest_week":wlabel(latest),
 "note_latest":"260719주는 미집계(작성중)로 260712까지 반영",
 "kpi":{
   "jaejeok":report[latest][1],"chulseok":report[latest][2],
   "rate":round(report[latest][2]/report[latest][1]*100,1),
   "gyeolseok":report[latest][3],"jangkyeol":report[latest][4],
   "newfriend_total":len(newfriends),"offering_total":offering_total,
   "perfect_cnt":len(perfect),
 },
 "monthly":monthly,"weekly":weekly_series,
 "latest_absent":latest_absent,"abs_freq":sorted([{"name":n,"grade":grade_of[n],"cnt":c} for n,c in abs_count.items()],key=lambda x:(-x["cnt"],x["name"])),
 "perfect":perfect,"near":near,
 "offering":{"by_cat":[{"cat":c,"amt":csum[c]} for c in cats],"total":offering_total,"monthly":monthly_off},
 "newfriends":newfriends,"newfriend_report_sum":newfriend_count_total,
 "grade_latest":grade_latest,"grade_avg":grade_avg,
}
with open(DATA_PATH,"w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False)

# ===== 주차별 상세 (주차 선택용) =====
weekly_detail={}
for w in report:
    m,jae,chul,gs,jk,sc,t,th,su,sp,mi,ji=report[w]
    al=[{"name":n,"grade":grade_of[n],"chronic":n in chronic} for n in absent.get(w,[]) if is_current(n)]
    # 학년별(해당주)
    ga=collections.Counter()
    for n in absent.get(w,[]):
        if is_current(n): ga[grade_of[n]]+=1
    gr=[{"grade":g,"size":grade_size[g],"present":grade_size[g]-ga[g],"absent":ga[g],
         "rate":round((grade_size[g]-ga[g])/grade_size[g]*100,1)} for g in grade_order]
    weekly_detail[wlabel(w)]={
      "jae":jae,"chul":chul,"gs":gs,"jk":jk,"sc":sc,"tea":teacher_jae.get(w,0),
      "oc":[t,th,su,sp,mi,ji],
      "offeringAll":t+th+su+sp+mi+ji,
      "rate":round(chul/jae*100,1),
      "offering":t+th+su+sp+mi,
      "absent":al,"grade":gr}
# as-of 누적 계산용 부가 데이터
order_labels=[wlabel(w) for w in report]
def widx(lbl):
    return order_labels.index(lbl)
# 신규 편입 인덱스
join_idx={n:widx(wlabel(w)) for n,w in join_week.items() if wlabel(w) in order_labels}
out["grade_order"]=grade_order
out["roster"]=[{"name":n,"grade":g,"joinIdx":join_idx.get(n,0)} for n,g in roster]
# 새친구 등록 주차 인덱스
nf_week={x["name"]:x["wk"] for x in NF_SRC}
for nf in out["newfriends"]:
    nf["wk"]=widx(nf_week.get(nf["name"],order_labels[-1]))
EXCLUDE=EXCLUDE_CATS
out["excludeCats"]=EXCLUDE
_ex={c for c in EXCLUDE}
out["offering"]["by_cat"]=[x for x in out["offering"]["by_cat"] if x["cat"] not in _ex]
out["offering"]["total"]=sum(x["amt"] for x in out["offering"]["by_cat"])
_ji=cats.index("지목헌금")
for _m in out["offering"]["monthly"]:
    pass
out["categories"]=cats
out["weekly_detail"]=weekly_detail
out["order"]=[wlabel(w) for w in report]
with open(DATA_PATH,"w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False)
print("OK weekly_detail weeks:",len(weekly_detail))

# ===== 「헌금명단」 탭 (출석부) → 참여 명단 =====
import re as _re
OFFER_RAW=[tuple(r) for r in OFFER_ROWS]
_roster={n for n,_g in roster}
def _olab(iso):
    _y,_m,_d=iso.split("-"); return f"{int(_m)}/{int(_d)}"
def _oparse(t):
    t=t.strip(); note=""
    if ":" in t:
        h,tail=t.split(":",1); note=h.strip(); t=tail.strip()
    if _re.fullmatch(r"\d+\s*명", t): return [], f"무명 {t}"
    parts=[p.strip() for p in t.split(",") if p.strip()]
    names=[p for p in parts if p in _roster]
    others=[p for p in parts if p not in _roster]
    if others: note=(note+" · " if note else "")+" ".join(others)
    return names, note
_orows=[]
for _iso,_item,_amt,_lst in OFFER_RAW:
    _L=_olab(_iso); _n,_note=_oparse(_lst)
    _orows.append({"date":_iso,"wk":_L,"item":_item,"amt":_amt,"names":_n,"note":_note,
                   "idx":out["order"].index(_L) if _L in out["order"] else -1})
_orows.sort(key=lambda r:(r["date"], r["item"]))
out["offerList"]={"rows":_orows,"itemOrder":["주일헌금","감사헌금","구제/선교","기타"]}

with open(DATA_PATH,"w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False)
print("offerList 편입 완료:",len(_orows),"행")
