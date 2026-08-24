# -*- coding: utf-8 -*-
"""배포 차단 게이트 — 원천 탭 ↔ weeks.json ↔ index.html 전 필드 재계산 대조.

    python3 verify.py <YYMMDD> [--baseline 직전배포본.html]

하나라도 ERROR 가 나오면 exit 1 → 업로드 금지.
"체크리스트에 적힌 것만" 보지 않고, 원천에 존재하는 모든 값을 다시 계산해 대조한다.
"""
import sys, os, json, csv, re, collections
import parse_lib as P

HERE = os.path.dirname(os.path.abspath(__file__))
def _p(n): return os.path.join(HERE, n)

ERRORS, WARNS, OKS = [], [], []
def err(tag, msg):  ERRORS.append(f"[{tag}] {msg}")
def warn(tag, msg): WARNS.append(f"[{tag}] {msg}")
def ok(tag, msg):   OKS.append(f"[{tag}] {msg}")

# report[6:12] 순서 = 십일조, 감사, 주일, 특별, 선교, 지목
HG_SLOT = {"십일조": 0, "감사헌금": 1, "주일헌금": 2, "구제/선교": 4, "기타": 5}
MUST_HAVE = ["헌금 참여 명단", "renderOfferList", "setupMotion", "safeUpdate",
             "minmax(0,1.25fr)", "apple-touch-icon", "주 연속", "noindex", "새친구"]


def embed(path):
    """index.html 의 const D= 임베드 JSON 과 템플릿 본문(임베드 제외)을 돌려준다."""
    s = open(path, encoding="utf-8").read()
    i = s.find("const D=")
    if i < 0: raise SystemExit(f"{path}: const D= 를 찾을 수 없음")
    raw = s[i + 8: s.find("\n", i)].rstrip().rstrip(";")
    return json.loads(raw), s.replace(raw, ""), s


def names_of(cell):
    """헌금 명단 셀 → (이름집합, 무명여부). compute.py _oparse 와 같은 규칙."""
    t = (cell or "").strip()
    if ":" in t: t = t.split(":", 1)[1].strip()
    if re.fullmatch(r"\d+\s*명", t): return set(), True
    return {p.strip() for p in t.split(",") if p.strip()}, False


def attend_rows(path, iso):
    """해당 날짜의 (반, 출석명단 이름리스트) 목록. 동일 (날짜,반) 중복행은 마지막 값."""
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["날짜"] == iso:
            out[r["반"].strip()] = P.split_names(r.get("출석명단", ""))
    return list(out.items())


def load_hg(path):
    rows = collections.defaultdict(list)
    for r in csv.DictReader(open(path, encoding="utf-8")):
        rows[P.iso2key(r["날짜"])].append(
            (r["항목"].strip(), int((r["금액"] or "0").replace(",", "")), r.get("명단", "")))
    return rows


def main(week, baseline=None):
    raw = P.load_raw(_p("raw_attend.csv"))
    hg = load_hg(_p("heonggeum.csv"))
    W = json.load(open(_p("weeks.json"), encoding="utf-8"))
    D, tmpl, full = embed(_p("index.html"))
    iso = f"20{week[:2]}-{week[2:4]}-{week[4:6]}"

    if week not in raw:                err("원천", f"{week} 주차가 원천 탭에 없음"); return
    if week not in W["report"]:        err("weeks", f"{week} 주차가 weeks.json 에 없음"); return
    rep = W["report"][week]

    if week != max(W["report"]):
        print(f"⚠️  {week} 는 최신 주차가 아닙니다. verify.py 는 '이번에 추가한 주차' 전용입니다.\n"
              f"    과거 주차는 당시 집계 규칙으로 확정·동결된 값이라 현재 로직으로 재계산하면 어긋날 수 있습니다.\n"
              f"    (예: 8/16 은 영어반을 재적에 포함하던 시점의 값 47 — 현재 로직 재계산은 44)\n")

    # ── A. 출결: 원천 재계산 ↔ weeks.json ────────────────────────────────
    mj, mc, nfj, nfc, ab = P.week_totals(raw[week])
    roster = {n for n, _g in W["roster"]}
    cur = [n for n in ab if n in roster]
    hist = {k: (set(P.week_totals(raw[k])[4]) if k in raw
                else {x.strip() for x in W["absent"].get(k, "").split(",") if x.strip()})
            for k in sorted(set(list(W["report"]) + list(raw)))}
    jang = [n for n in cur if P.consec_absent(n, week, hist) >= 5]

    for label, got, want in [("재적", rep[1], mj), ("출석", rep[2], mc + nfc),
                             ("결석", rep[3], len(cur) - len(jang)),
                             ("장기", rep[4], len(jang)), ("새친구", rep[5], nfc)]:
        (ok if got == want else err)("출결", f"{label} weeks={got} 원천={want}")

    if W.get("nfclass", {}).get(week) != [nfj, nfc]:
        err("출결", f"nfclass {W.get('nfclass', {}).get(week)} ≠ 원천 [{nfj},{nfc}]")
    else:
        ok("출결", f"nfclass {[nfj, nfc]}")

    # ── A'. parse_lib 에 의존하지 않는 독립 불변식 ───────────────────────
    # (verify 가 parse_lib 로 재계산하므로, 집계 로직 자체가 틀리면 양쪽이 똑같이 틀린다.
    #  아래 검사는 명단 원문만 보므로 로직 버그와 독립적이다.)
    # 출석명단 원문에서 이름 중복 검출 (같은 사람이 두 반에 걸쳐 집계되면 이중계산)
    seen, dup = {}, collections.defaultdict(list)
    src_rows = attend_rows(_p("raw_attend.csv"), iso)
    for ban, present in src_rows:
        if ban not in P.MAIN_BAN and ban != P.NF_BAN: continue
        for n in present:
            if n in seen: dup[n].append(ban)
            else: seen[n] = ban
    if dup:
        for n, bans in dup.items():
            err("이중계산", f"'{n}' 이(가) {seen[n]} 과 {'/'.join(bans)} 에 중복 등장 — 재적·출석 이중계산")
    else:
        ok("이중계산", f"출석명단 {len(seen)}명 중복 없음")

    # 최신 주차라면 재적 == 현재 roster 인원수
    if week == max(W["report"]) and rep[1] != len(roster):
        err("불변식", f"재적 {rep[1]} ≠ roster 인원수 {len(roster)}")
    elif week == max(W["report"]):
        ok("불변식", f"재적 {rep[1]} = roster 인원수")

    # 반별 출석수 합 == 출석명단 인원수 합 (시트 셀 자체 정합성)
    cell_sum = sum(c for b, (j, c, a) in raw[week].items() if b in P.MAIN_BAN or b == P.NF_BAN)
    name_sum = sum(len(pr) for b, pr in src_rows if b in P.MAIN_BAN or b == P.NF_BAN)
    if cell_sum != name_sum:
        err("불변식", f"출석수 셀 합 {cell_sum} ≠ 출석명단 인원수 합 {name_sum}")
    else:
        ok("불변식", f"출석수 셀 = 명단 인원수 ({cell_sum}명)")

    # 결석 명단: 이름 단위 집합 비교
    saved = {P.norm_name(x) for x in W["absent"].get(week, "").split(",") if x.strip()}
    if saved != set(ab):
        err("결석명단", f"원천에만 {sorted(set(ab)-saved)} / weeks에만 {sorted(saved-set(ab))}")
    else:
        ok("결석명단", f"{len(ab)}명 일치")

    # ── B. 헌금: 행 수 · 항목 · 금액 · 명단 ──────────────────────────────
    src = hg.get(week, [])
    dst = [r for r in W["offerRows"] if r[0] == iso]
    if len(src) != len(dst):
        err("헌금행수", f"원천 {len(src)}행 ≠ weeks {len(dst)}행 — 병합 중 행 손실")
    else:
        ok("헌금행수", f"{len(src)}행")

    smap = {}
    for item, amt, lst in src: smap.setdefault(item, []).append((amt, lst))
    dmap = {}
    for r in dst: dmap.setdefault(r[1], []).append((r[2], r[3]))
    for item in sorted(set(smap) | set(dmap)):
        s_, d_ = sorted(smap.get(item, [])), sorted(dmap.get(item, []))
        if [a for a, _ in s_] != [a for a, _ in d_]:
            err("헌금항목", f"{item}: 원천 {[a for a,_ in s_]} ≠ weeks {[a for a,_ in d_]}")
            continue
        for (a, sl), (_, dl) in zip(s_, d_):
            sn, s_anon = names_of(sl); dn, d_anon = names_of(dl)
            if sn != dn or s_anon != d_anon:
                err("헌금명단", f"{item} {a:,}원 · 원천에만 {sorted(sn-dn)} / weeks에만 {sorted(dn-sn)}")
            else:
                ok("헌금명단", f"{item} {a:,}원 {len(sn)}명" + (" (무명)" if s_anon else ""))

    # 불변식: 헌금 행 합 == report 금액 합
    inv_src = sum(a for _i, a, _l in src)
    inv_rep = sum(rep[6:12])
    if inv_src != inv_rep:
        err("불변식", f"원천 헌금합 {inv_src:,} ≠ report 합 {inv_rep:,}")
    else:
        ok("불변식", f"헌금합 {inv_src:,}원 일치")
    # 항목별 슬롯 대조 (라벨 뒤바뀜 감지)
    slot = [0] * 6
    for item, amt, _l in src:
        if item in HG_SLOT: slot[HG_SLOT[item]] += amt
    if slot != list(rep[6:12]):
        err("불변식", f"항목별 금액 원천 {slot} ≠ report {list(rep[6:12])}")
    else:
        ok("불변식", f"항목별 금액 {slot}")

    # ── C. weeks.json ↔ index.html 임베드 ───────────────────────────────
    if len(D["weekly"]) != len(W["report"]):
        err("임베드", f"weekly {len(D['weekly'])}주 ≠ report {len(W['report'])}주")
    wk = D["weekly"][-1]
    lbl = f"{int(week[2:4])}/{int(week[4:6])}"
    if wk["label"] != lbl:
        err("임베드", f"최신주 라벨 {wk['label']} ≠ {lbl}")
    elif (wk["jae"], wk["chul"]) != (rep[1], rep[2]):
        err("임베드", f"{lbl} 재적/출석 {wk['jae']}/{wk['chul']} ≠ weeks {rep[1]}/{rep[2]}")
    else:
        ok("임베드", f"{lbl} 재적 {wk['jae']} 출석 {wk['chul']} ({wk['rate']}%)")

    orows = [r for r in D["offerList"]["rows"] if r["date"] == iso]
    if len(orows) != len(src):
        err("임베드헌금", f"화면 {len(orows)}행 ≠ 원천 {len(src)}행")
    for item, amt, lst in src:
        m = [r for r in orows if r["item"] == item and r["amt"] == amt]
        if not m:
            err("임베드헌금", f"{item} {amt:,}원 행이 화면에 없음"); continue
        sn, anon = names_of(lst)
        shown = set(m[0]["names"])
        missing = {n for n in sn if n not in shown and n not in (m[0].get("note") or "")}
        if missing:
            err("임베드헌금", f"{item} {amt:,}원 · 화면에서 누락된 이름 {sorted(missing)}")
        else:
            ok("임베드헌금", f"{item} {amt:,}원 {len(sn)}명 표시 확인")

    # ── D. 과거 불변성 ─────────────────────────────────────────────────
    if baseline and os.path.exists(baseline):
        B, btmpl, bfull = embed(baseline)
        if btmpl.encode() != tmpl.encode():
            err("불변성", "템플릿 본문이 직전 배포본과 다름 — 디자인 변경 발생")
        else:
            ok("불변성", "템플릿 본문 바이트 동일")
        n = len(B["weekly"])
        if B["weekly"] != D["weekly"][:n]:
            err("불변성", "과거 주차 weekly 가 변경됨")
        else:
            ok("불변성", f"과거 {n}주 weekly 동일")
        for k in ("roster", "singeup", "singeupMeta", "newfriends"):
            if B.get(k) != D.get(k): err("불변성", f"{k} 가 변경됨")
        b_o = [r for r in B["offerList"]["rows"] if r["date"] != iso]
        d_o = [r for r in D["offerList"]["rows"] if r["date"] != iso]
        if b_o != d_o:
            err("불변성", "대상 주차 외 헌금 행이 변경됨")
        else:
            ok("불변성", f"대상주 외 헌금 {len(d_o)}행 동일")
        if len(bfull.encode()) and len(full.encode()) < len(bfull.encode()) * 0.9:
            err("불변성", f"파일 크기 {len(full.encode()):,} < 직전 90% ({len(bfull.encode()):,})")

    # ── E. 필수 문자열 ─────────────────────────────────────────────────
    miss = [t for t in MUST_HAVE if t not in full]
    if miss: err("필수문자열", f"누락 {miss}")
    else:    ok("필수문자열", f"{len(MUST_HAVE)}종 모두 존재")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    base = None
    if "--baseline" in sys.argv:
        base = sys.argv[sys.argv.index("--baseline") + 1]
    if not args:
        raise SystemExit("사용법: python3 verify.py <YYMMDD> [--baseline 직전배포본.html]")
    main(args[0], base)

    for m in OKS:    print("  ✅", m)
    for m in WARNS:  print("  ⚠️ ", m)
    for m in ERRORS: print("  ❌", m)
    print("-" * 60)
    if ERRORS:
        print(f"검증 실패 — ERROR {len(ERRORS)}건. 업로드하지 말 것.")
        sys.exit(1)
    print(f"검증 통과 — 확인 {len(OKS)}건" + (f", 경고 {len(WARNS)}건" if WARNS else "") + ". 업로드 가능.")
