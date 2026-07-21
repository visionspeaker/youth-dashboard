#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compute.py — 중고등부 대시보드 데이터(data.json) 증분 갱신기

설계 원칙(중요)
- 과거 주차는 절대 재계산하지 않는다. data.json 은 "현재까지 누적된 확정 상태"이며,
  이 스크립트는 '새 주차'만 읽어 그 델타만 반영한다(1~6월 등 확정치 불변).
- 시트를 직접 읽지 않는다. 구글시트 접근 권한이 없으므로, 에이전트(Claude)가 매주
  두 시트에서 '중고등부' 새 주차를 읽어 아래 스키마의 dict 로 만들어
  weeks_incoming.json (리스트) 에 넣은 뒤 이 스크립트를 실행한다.
- 이미 반영된 주차(label 이 data.json['order'] 에 존재)는 건너뛴다(멱등).

실행:  python3 compute.py            # weeks_incoming.json 의 새 주차들을 반영
       python3 compute.py --dry     # 계산만 하고 저장하지 않음

weeks_incoming.json 예시(한 주차 dict): README 참고.
"""
import json, sys, datetime, pathlib

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data.json"
INCOMING = HERE / "weeks_incoming.json"

def month_of(label):
    return f"{int(label.split('/')[0])}월"

def recompute_month(D, mon):
    ws = [w for w in D["weekly"] if month_of(w["label"]) == mon]
    if not ws: return
    n = len(ws)
    entry = {"month": mon,
             "avg_chul": round(sum(w["chul"] for w in ws)/n, 1),
             "avg_jae":  round(sum(w["jae"]  for w in ws)/n, 1),
             "rate":     round(sum(w["rate"] for w in ws)/n, 1),
             "weeks": n}
    for i, m in enumerate(D["monthly"]):
        if m["month"] == mon:
            D["monthly"][i] = entry; return
    D["monthly"].append(entry)
    D["monthly"].sort(key=lambda m: int(m["month"][:-1]))

def add_week(D, wk):
    label = wk["label"]
    if label in D["order"]:
        print(f"  · {label}: 이미 반영됨 → 건너뜀"); return False
    jae, chul = wk["jae"], wk["chul"]
    absents = wk.get("absents", [])
    gs = len(absents)
    rate = round(chul/jae*100, 1) if jae else 0.0
    if wk.get("roster"): D["roster"] = wk["roster"]
    sizes = {}
    for r in D["roster"]: sizes[r["grade"]] = sizes.get(r["grade"], 0) + 1
    n_prev = len(D["order"])

    D["weekly"].append({"label": label, "jae": jae, "chul": chul, "gs": gs, "rate": rate})
    D["order"].append(label)
    recompute_month(D, month_of(label))

    om = {m["month"]: m for m in D["offering"]["monthly"]}
    mon = month_of(label)
    if mon in om: om[mon]["total"] += wk.get("offering_week_total", 0)
    else:
        D["offering"]["monthly"].append({"month": mon, "total": wk.get("offering_week_total", 0)})
        D["offering"]["monthly"].sort(key=lambda m: int(m["month"][:-1]))
    bycat = {c["cat"]: c for c in D["offering"]["by_cat"]}
    for cat, amt in wk.get("offering_by_cat", {}).items():
        if cat in D["excludeCats"]: continue
        if cat in bycat: bycat[cat]["amt"] += amt
        else: D["offering"]["by_cat"].append({"cat": cat, "amt": amt})
    D["offering"]["total"] = sum(c["amt"] for c in D["offering"]["by_cat"])

    freq = {e["name"]: e for e in D["abs_freq"]}
    for a in absents:
        if a["name"] in freq: freq[a["name"]]["cnt"] += 1
        else: D["abs_freq"].append({"name": a["name"], "grade": a["grade"], "cnt": 1})
    D["abs_freq"].sort(key=lambda e: -e["cnt"])
    D["near"] = sorted([e for e in D["abs_freq"] if e["cnt"] == 1], key=lambda e: e["name"])

    absset = {a["name"] for a in absents}
    D["perfect"] = [p for p in D["perfect"] if p["name"] not in absset]

    order_idx = {r["name"]: i for i, r in enumerate(D["roster"])}
    la = sorted(absents, key=lambda a: order_idx.get(a["name"], 999))
    D["latest_absent"] = [{"name": a["name"], "grade": a["grade"], "chronic": bool(a.get("chronic"))} for a in la]

    absN = {}
    for a in absents: absN[a["grade"]] = absN.get(a["grade"], 0) + 1
    gl = []; week_rate = {}
    for g in D["grade_order"]:
        sz = sizes.get(g, 0); ab = absN.get(g, 0); pr = sz - ab
        r = round(pr/sz*100, 1) if sz else 0.0
        week_rate[g] = r
        gl.append({"grade": g, "size": sz, "present": pr, "absent": ab, "rate": r})
    D["grade_latest"] = gl

    ga = {x["grade"]: x for x in D["grade_avg"]}
    for g in D["grade_order"]:
        old = ga[g]["rate"] if g in ga else 0.0
        new = round((old*n_prev + week_rate[g])/(n_prev+1), 1)
        if g in ga: ga[g]["rate"] = new
        else: D["grade_avg"].append({"grade": g, "rate": new})

    idx = len(D["order"]) - 1
    for row in wk.get("offer_rows", []):
        D["offerList"]["rows"].append({"date": row.get("date",""), "wk": label,
            "item": row["item"], "amt": row.get("amt",0),
            "names": sorted(row.get("names", [])), "note": row.get("note",""), "idx": idx})
        if row["item"] not in D["offerList"]["itemOrder"]:
            D["offerList"]["itemOrder"].append(row["item"])

    for nf in wk.get("newfriends_add", []):
        if not any(x["name"] == nf["name"] for x in D["newfriends"]):
            D["newfriends"].append(nf)
    if "newfriend_report" in wk:
        D["newfriend_report_sum"] = D.get("newfriend_report_sum", 0) + wk["newfriend_report"]

    D["kpi"].update({
        "jaejeok": jae, "chulseok": chul, "rate": rate,
        "gyeolseok": wk.get("gyeolseok", gs),
        "jangkyeol": wk.get("jangkyeol", D["kpi"]["jangkyeol"]),
        "newfriend_total": len(D["newfriends"]),
        "offering_total": sum(m["total"] for m in D["offering"]["monthly"]),
        "perfect_cnt": len(D["perfect"]),
    })
    D["latest_week"] = label
    D["generated"] = datetime.date.today().isoformat()
    if wk.get("note"): D["note_latest"] = wk["note"]
    print(f"  · {label} 반영: 재적{jae} 출석{chul} 결석{gs} 출석률{rate}%")
    return True

def main():
    dry = "--dry" in sys.argv
    D = json.loads(DATA.read_text(encoding="utf-8"))
    weeks = []
    if INCOMING.exists():
        weeks = json.loads(INCOMING.read_text(encoding="utf-8"))
        if isinstance(weeks, dict): weeks = [weeks]
    if not weeks:
        print("weeks_incoming.json 없음/비어있음 — 반영할 새 주차가 없습니다."); return
    print(f"새 주차 후보 {len(weeks)}건 처리:")
    changed = False
    for wk in weeks: changed |= add_week(D, wk)
    if not changed:
        print("반영된 새 주차 없음."); return
    if dry:
        print("[--dry] 저장하지 않음."); return
    DATA.write_text(json.dumps(D, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"data.json 저장 완료. 최신주차={D['latest_week']} 총 {len(D['order'])}주.")

if __name__ == "__main__":
    main()
