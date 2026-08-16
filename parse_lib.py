# -*- coding: utf-8 -*-
"""중고등부 출석 원천 탭 파싱 공용 로직.
원천 탭 = 교사앱 출석체크가 쌓이는 시트(한 행=한 주차·한 반):
  날짜 | 반 | 출석수 | 재적수 | 출석명단 | 결석명단(사유) | 저장시각
검증: 2026 1~8월 31주 전부 사역보고서 집계와 일치(재적/출석/결석/장기/명단/새친구).
"""
import re, csv, collections

MAIN_BAN = {"중1","중2","중2남","중2여","중3","고1","고2","고3","영어반"}  # 학생 반(새친구 제외)
NF_BAN = "새친구"
# 반 -> 학년 매핑 (중2남/중2여 -> 중2 로 합산)
BAN2GRADE = {"중1":"중1","중2":"중2","중2남":"중2","중2여":"중2","중3":"중3",
             "고1":"고1","고2":"고2","고3":"고3"}
NAME_FIX = {"정창빈":"정찬빈", "반소영":"반잭키", "반재키":"반잭키"}  # 시트 오타 보정(compute.py norm 과 동일)

def norm_name(n):
    n = n.split("(")[0]              # 이름은 항상 첫 '(' 앞 (사유·중첩괄호 제거)
    n = re.sub(r"\s+","",n).strip()  # 한글 이름 내부 공백 제거
    return NAME_FIX.get(n, n)

def split_names(cell):
    """쉼표 분리하되 괄호(사유) 안의 쉼표는 무시. 중첩 괄호 지원."""
    out=[]; buf=""; depth=0
    for ch in (cell or ""):
        if ch=="(": depth+=1; buf+=ch
        elif ch==")": depth=max(0,depth-1); buf+=ch
        elif ch=="," and depth==0: out.append(buf); buf=""
        else: buf+=ch
    if buf.strip(): out.append(buf)
    return [norm_name(x) for x in out if x.strip()]

def iso2key(iso):
    y,m,d = iso.split("-"); return f"{int(y)%100:02d}{int(m):02d}{int(d):02d}"

def load_raw(path):
    """raw_attend.csv -> {YYMMDD: {'ban':{반:(재적,출석,[결석명단])}}}. 중복행(날짜+반)은 마지막 값 채택."""
    wk = collections.defaultdict(dict)
    for r in csv.DictReader(open(path,encoding="utf-8")):
        k = iso2key(r["날짜"]); ban=r["반"].strip()
        jae=int(r["재적수"] or 0); chul=int(r["출석수"] or 0)
        absent = split_names(r.get("결석명단",""))
        wk[k][ban] = (jae, chul, absent)   # 동일 (날짜,반) 재저장 시 최신으로 덮어씀
    return wk

def week_totals(banmap):
    """한 주차 반별 dict -> (재적, 출석, 새친구재적, 새친구출석, [결석명단합])."""
    mj=mc=0; nfj=nfc=0; absent=[]
    for ban,(jae,chul,ab) in banmap.items():
        if ban in MAIN_BAN:
            mj+=jae; mc+=chul; absent+=ab
        elif ban==NF_BAN:
            nfj+=jae; nfc+=chul
    return mj, mc, nfj, nfc, absent

def consec_absent(name, upto_key, absent_by_week):
    """upto_key 주차에서 뒤로 연속 결석 주수."""
    weeks=sorted(absent_by_week)
    if upto_key not in weeks: return 0
    i=weeks.index(upto_key); c=0
    while i>=0 and name in absent_by_week[weeks[i]]:
        c+=1; i-=1
    return c
