#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_html.py — data.json + template.html -> index.html
템플릿(레이아웃/CSS/JS)은 그대로 두고 데이터(const D)만 주입한다.
디자인/구조는 template.html 에만 있으니 이 스크립트는 수정할 일이 거의 없다."""
import json, pathlib
HERE = pathlib.Path(__file__).resolve().parent
data = json.loads((HERE/'data.json').read_text(encoding='utf-8'))
template = (HERE/'template.html').read_text(encoding='utf-8')
blob = json.dumps(data, ensure_ascii=False)   # 원본과 동일한 기본 구분자
html = template.replace('@@DATA_JSON@@', blob)
(HERE/'index.html').write_text(html, encoding='utf-8')
print('index.html written:', len(html), 'chars')
