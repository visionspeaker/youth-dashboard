# -*- coding: utf-8 -*-
# template.html + data.json -> index.html (+ 파일명 사본). 디자인은 template.html 에만 있다. 수정 금지.
import json, os
HERE=os.path.dirname(os.path.abspath(__file__))
def _p(n): return os.path.join(HERE,n)
d=json.load(open(_p("data.json"),encoding="utf-8"))
DATA=json.dumps(d,ensure_ascii=False)
tpl=open(_p("template.html"),encoding="utf-8").read()
assert "@@DATA_JSON@@" in tpl, "template.html 에 @@DATA_JSON@@ 마커가 없습니다"
html=tpl.replace("@@DATA_JSON@@", DATA)
open(_p("index.html"),"w",encoding="utf-8").write(html)
print("index.html 생성:", len(html), "bytes")
