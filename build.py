#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""개념정리/*.md 8개를 파싱해 단일 자기완결형 학습앱(학습앱.html)을 생성한다."""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "개념정리"
OUT = BASE / "학습앱.html"

FILES = [
    "01_NW보안구축.md",
    "02_시스템보안구축.md",
    "03_SW개발보안구축.md",
    "04_네트워크보안운영.md",
    "05_시스템보안운영.md",
    "06_애플리케이션보안운영.md",
    "07_보안로그분석.md",
    "08_정보시스템진단.md",
]


def clean_term(t: str) -> str:
    t = t.strip()
    t = t.strip("*").strip()
    # 선행 번호/괄호번호 제거: "1. ", "(1) ", "1) "
    t = re.sub(r"^\(?\d+\)?[.)]\s*", "", t)
    return t.strip()


def split_kv(text: str):
    """'용어 : 정의' 분리. 첫 ' : '(공백-콜론-공백) 기준."""
    m = re.search(r"[:：]", text)
    if not m:
        return None
    # 공백으로 감싼 콜론을 우선 분리
    parts = re.split(r"\s[:：]\s", text, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    # 콜론 직후 공백만 있는 경우
    parts = re.split(r"[:：]\s", text, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return None


def parse_file(path: Path):
    title = path.stem.split("_", 1)[-1]
    notes = []
    units = []
    cur_unit = None
    cur_section = None
    cur_group = None
    cur_sub = None

    def ensure_group():
        nonlocal cur_unit, cur_section, cur_group
        if cur_unit is None:
            cur_unit = {"title": "개요", "sections": []}
            units.append(cur_unit)
        if cur_section is None:
            cur_section = {"title": "", "groups": []}
            cur_unit["sections"].append(cur_section)
        if cur_group is None:
            cur_group = {"title": "", "items": []}
            cur_section["groups"].append(cur_group)

    def add_concept(term, definition, sub):
        ensure_group()
        term = clean_term(term)
        if term in ("개념",):
            term = sub or cur_group["title"] or (cur_section["title"] if cur_section else "")
        definition = definition.strip()
        if not term or not definition:
            return
        cur_group["items"].append({"t": "c", "term": term, "def": definition, "sub": sub or ""})

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        s = line.strip()
        if not s or s == "---":
            continue
        if s.startswith("# "):
            ttl = s[2:].strip()
            ttl = re.sub(r"\s*[—-]\s*개념 정리\s*$", "", ttl)
            title = ttl
            continue
        if s.startswith("> "):
            if cur_unit is None:
                notes.append(s[2:].strip())
            else:
                ensure_group()
                cur_group["items"].append({"t": "n", "text": s[2:].strip()})
            continue
        if s.startswith("## "):
            cur_unit = {"title": s[3:].strip(), "sections": []}
            units.append(cur_unit)
            cur_section = None
            cur_group = None
            cur_sub = None
            continue
        if s.startswith("### "):
            cur_section = {"title": s[4:].strip(), "groups": []}
            if cur_unit is None:
                cur_unit = {"title": "", "sections": []}
                units.append(cur_unit)
            cur_unit["sections"].append(cur_section)
            cur_group = None
            cur_sub = None
            continue
        if s.startswith("#### "):
            ensure_unit_section(units)
            cur_group = {"title": s[5:].strip(), "items": []}
            if cur_section is None:
                cur_section = {"title": "", "groups": []}
                cur_unit["sections"].append(cur_section)
            cur_section["groups"].append(cur_group)
            cur_sub = None
            continue
        # 굵은 글씨 줄: 개념(**용어** : 정의) 또는 소그룹 제목(**제목** [— 설명])
        if s.startswith("**"):
            m = re.match(r"\*\*(.+?)\*\*\s*(.*)$", s)
            if m:
                head = m.group(1).strip()
                rest = m.group(2).strip()
                if rest.startswith(":") or rest.startswith("："):
                    add_concept(head, rest.lstrip(":：").strip(), cur_sub)
                    continue
                if rest and rest[0] in "—-–":
                    cur_sub = clean_term(head)
                    desc = rest.lstrip("—-– ").strip()
                    if desc:
                        add_concept(cur_sub, desc, None)
                    continue
                cur_sub = clean_term(head)
                continue
        # 리스트 항목
        mb = re.match(r"^\s*[-*]\s+(.*)$", line)
        if mb:
            content = mb.group(1).strip()
            content = re.sub(r"\*\*(.+?)\*\*", r"\1", content)  # 인라인 볼드 제거
            kv = split_kv(content)
            if kv:
                add_concept(kv[0], kv[1], cur_sub)
            else:
                ensure_group()
                cur_group["items"].append({"t": "n", "text": content})
            continue
        # 그 외 평문: 손실 방지 위해 note 처리
        kv = split_kv(s)
        if kv:
            add_concept(kv[0], kv[1], cur_sub)
        else:
            ensure_group()
            cur_group["items"].append({"t": "n", "text": s})

    # 빈 그룹/섹션/유닛 정리
    for u in units:
        u["sections"] = [sec for sec in u["sections"] if any(g["items"] for g in sec["groups"])]
        for sec in u["sections"]:
            sec["groups"] = [g for g in sec["groups"] if g["items"]]
    units = [u for u in units if u["sections"]]

    n_concepts = sum(
        1 for u in units for sec in u["sections"] for g in sec["groups"] for it in g["items"] if it["t"] == "c"
    )
    return {"id": path.stem[:2], "title": title, "notes": notes, "units": units, "count": n_concepts}


def ensure_unit_section(units):
    if not units:
        units.append({"title": "개요", "sections": []})


def main():
    subjects = []
    for f in FILES:
        p = SRC / f
        if not p.exists():
            print("missing", f)
            continue
        subj = parse_file(p)
        subjects.append(subj)
        print(f"{subj['title']}: 개념 {subj['count']}개")

    total = sum(s["count"] for s in subjects)
    print("총 개념:", total)

    data = {"subjects": subjects}
    template = (BASE / "_template.html").read_text(encoding="utf-8")
    html = template.replace("__STUDY_DATA__", json.dumps(data, ensure_ascii=False))
    OUT.write_text(html, encoding="utf-8")
    (BASE / "app.html").write_text(html, encoding="utf-8")
    (BASE / "index.html").write_text(html, encoding="utf-8")
    print("생성:", OUT, "+ app.html + index.html")


if __name__ == "__main__":
    main()
