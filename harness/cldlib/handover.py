# -*- coding: utf-8 -*-
"""인수인계 — 항목 신설(맨 위) · 네 칸 검사.

약속(templates/handover.md):
    - 문서에 ``<!-- cld:handover-insert -->`` 표식이 한 번 있다. 새 항목은 표식 바로 아래(= 맨 위)에 들어간다. 최신이 위다.
    - 항목은 ``## <id>. <제목> (<상태>)`` 절이고, 네 칸 ``### 깨지기 쉬운 것`` · ``### 되돌리는 법`` ·
      ``### 🔴 믿지 말 것`` · ``### 🔴 다음 사람에게`` 를 이 순서로 가진다(🔴 표시는 있어도 없어도 된다).
    - 빈 칸은 «없음» 이라고 적는다. 비워 두면 안 쓴 것인지 없는 것인지 모른다.
    - 틀의 자리표시(``{{…}}``)가 남으면 안 된다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from . import mdtext

MARKER = "<!-- cld:handover-insert -->"
CELLS = ("깨지기 쉬운 것", "되돌리는 법", "믿지 말 것", "다음 사람에게")
PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}")

ENTRY_TEMPLATE = """## {sid}. {title} (**진행 중 — {date}**)

{{{{한두 문장: 이 커밋 · Phase 가 무엇을 바꿨나(자세한 것은 CHANGELOG)}}}}

### 깨지기 쉬운 것

| 무엇 | 어떻게 깨지나 | 지키는 장치 |
|---|---|---|
| {{{{다음 사람이 모르고 깨뜨릴 수 있는 것 — 없으면 «없음» 한 줄}}}} | | |

### 되돌리는 법

{{{{이 커밋만 되돌리려면 무엇을 되돌리나 · 재빌드 · 데이터 이동이 필요한가}}}}

### 🔴 믿지 말 것

| 어디 | 무엇이 틀렸나 |
|---|---|
| {{{{이번에 틀린 것으로 밝혀진 문서 · 주석 · 가정 — 없으면 «없음»}}}} | |

### 🔴 다음 사람에게

{{{{구체적 지시. «조심하라» 가 아니라 «이 함수를 쓰라». 게이트 결과 표는 여기 끝에 둔다}}}}

"""


class HandoverError(ValueError):
    """인수인계 문서 형식이 약속과 다르다."""


@dataclass(frozen=True)
class CheckResult:
    section: str
    ok: bool
    problems: tuple[str, ...]
    warnings: tuple[str, ...]
    lines: int


def new_entry(doc_text: str, sid: str, title: str, date: str) -> str:
    """표식 아래에 새 항목을 넣은 문서 텍스트를 돌려준다(줄 끝은 호출자가 보존)."""
    if doc_text.count(MARKER) != 1:
        raise HandoverError(f"표식 {MARKER} 이 {doc_text.count(MARKER)}개다(1 이어야 한다)")
    if any(s.id == sid for s in mdtext.sections(doc_text)):
        raise HandoverError(f"절 `## {sid}. …` 이 이미 있다 — 같은 Phase 의 다음 커밋은 기존 항목을 고친다")
    entry = ENTRY_TEMPLATE.format(sid=sid, title=title, date=date)
    return doc_text.replace(MARKER, MARKER + "\n\n" + entry.rstrip("\n") + "\n", 1)


def entries(doc_text: str) -> list[mdtext.Section]:
    """표식 뒤의 항목 절(최신이 먼저). 표식이 없으면 HandoverError."""
    lines = mdtext.split_lines(doc_text)
    try:
        mline = next(i for i, l in enumerate(lines) if l.strip() == MARKER)
    except StopIteration:
        raise HandoverError(f"표식 {MARKER} 이 없다") from None
    return [s for s in mdtext.sections(doc_text) if s.start > mline and s.id]


def check(doc_text: str, sid: Optional[str] = None, max_lines: int = 80) -> CheckResult:
    """항목(기본 맨 위) 하나의 네 칸을 검사한다."""
    ents = entries(doc_text)
    if not ents:
        raise HandoverError("인수인계 항목이 하나도 없다")
    if sid is None:
        sec = ents[0]
    else:
        hits = [s for s in ents if s.id == sid]
        if not hits:
            raise HandoverError(f"항목 `## {sid}. …` 이 없다")
        sec = hits[0]
    lines = mdtext.split_lines(doc_text)[sec.start:sec.end]
    problems: list[str] = []
    warnings: list[str] = []
    found: list[tuple[str, int]] = []
    for i, line in enumerate(lines):
        if line.startswith("### "):
            for c in CELLS:
                if c in line:
                    found.append((c, i))
    names = [c for c, _ in found]
    for c in CELLS:
        if names.count(c) == 0:
            problems.append(f"칸 «{c}» 이 없다")
        elif names.count(c) > 1:
            problems.append(f"칸 «{c}» 이 {names.count(c)}번 나온다")
    order = [c for c in names if c in CELLS]
    if not problems and order != list(CELLS):
        problems.append(f"칸 순서가 다르다: {' → '.join(order)}")
    if not problems:
        idx = [i for _, i in found] + [len(lines)]
        for k, c in enumerate(CELLS):
            body = [l for l in lines[idx[k] + 1:idx[k + 1]] if l.strip() and not re.fullmatch(r"\|?[-| :]+\|?", l.strip())]
            body = [l for l in body if not re.fullmatch(r"\|\s*무엇\s*\|.*|\|\s*어디\s*\|.*", l.strip())]
            if not body:
                problems.append(f"칸 «{c}» 이 비었다 — 없으면 «없음» 이라고 적는다")
    for i, line in enumerate(lines):
        if PLACEHOLDER_RE.search(line):
            problems.append(f"자리표시가 남았다(항목 줄 {i + 1}): {line.strip()[:70]}")
    n = len([l for l in lines if l.strip()])
    if n > max_lines:
        warnings.append(f"항목이 {n}줄이다(권고 {max_lines} — 한 쪽). 넘으면 리포트가 섞인 것이다 — 조사 · 측정은 docs/RPT 로 보낸다")
    return CheckResult(section=sec.id, ok=not problems, problems=tuple(problems), warnings=tuple(warnings), lines=n)
