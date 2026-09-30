# -*- coding: utf-8 -*-
"""마크다운 문서에서 절 · 울타리 블록을 찾는다.

문서 형식의 약속(templates/ 가 SSOT):
    - 절은 ``## <id>. <제목>`` 이다. id 는 공백 · 마침표가 없는 토큰이다(예: ``P1`` · ``7E`` · ``4M-C1``).
    - 세션 프롬프트 문서의 조각은 정보 문자열이 붙은 울타리 블록이다:
      ```cld-common``` · ```cld-multi``` · 각 Phase 절 안의 ```cld-head``` · ```cld-body```.
    - 권고 모드는 Phase 절 안의 ``권고 모드: 🔴|🟡|🟢`` 한 줄이다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
SECTION_RE = re.compile(r"^##\s+(?P<id>[^\s.]+)\.\s+(?P<title>.*?)\s*$")
FENCE_RE = re.compile(r"^(?P<fence>`{3,}|~{3,})\s*(?P<info>[^\s`]*)\s*$")
MODE_RE = re.compile(r"권고\s*모드\s*[:：]\s*(🔴|🟡|🟢)")

MODES = ("🔴", "🟡", "🟢")


class DocError(ValueError):
    """문서가 약속한 형식이 아니다."""


@dataclass(frozen=True)
class Section:
    """``## <id>. <제목>`` 절 하나. ``start``/``end`` 는 줄 번호(0 기준, end 는 다음 절 머리 또는 끝)."""

    id: str
    title: str
    start: int
    end: int


def split_lines(text: str) -> list[str]:
    """줄 끝을 뗀 줄 목록(\\r\\n · \\n 모두)."""
    return text.replace("\r\n", "\n").split("\n")


def sections(text: str) -> list[Section]:
    """문서의 ``## <id>. `` 절 목록(울타리 블록 안의 줄은 무시)."""
    lines = split_lines(text)
    heads: list[tuple[int, str, str]] = []
    fence: Optional[str] = None
    for i, line in enumerate(lines):
        m = FENCE_RE.match(line)
        if m:
            f = m.group("fence")
            if fence is None:
                fence = f[0] * len(f)
            elif f[0] == fence[0] and len(f) >= len(fence) and not m.group("info"):
                fence = None
            continue
        if fence is not None:
            continue
        if line.startswith("## "):
            sm = SECTION_RE.match(line)
            heads.append((i, sm.group("id") if sm else "", sm.group("title") if sm else line[3:].strip()))
    out: list[Section] = []
    for k, (i, sid, title) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        out.append(Section(id=sid, title=title, start=i, end=end))
    return out


def find_section(text: str, sid: str) -> Section:
    """id 가 ``sid`` 인 절 하나. 없거나 둘 이상이면 DocError."""
    hits = [s for s in sections(text) if s.id == sid]
    if len(hits) != 1:
        raise DocError(f"절 `## {sid}. …` 이 {len(hits)}개다(1 이어야 한다)")
    return hits[0]


def fenced_blocks(lines: list[str], start: int = 0, end: Optional[int] = None) -> list[tuple[str, str]]:
    """[start, end) 범위의 울타리 블록 (정보 문자열, 본문) 목록. 본문 끝의 줄바꿈 하나를 둔다."""
    end = len(lines) if end is None else end
    out: list[tuple[str, str]] = []
    i = start
    while i < end:
        m = FENCE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        fence = m.group("fence")
        info = m.group("info")
        body: list[str] = []
        j = i + 1
        while j < end:
            mm = FENCE_RE.match(lines[j])
            if mm and mm.group("fence")[0] == fence[0] and len(mm.group("fence")) >= len(fence) and not mm.group("info"):
                break
            body.append(lines[j])
            j += 1
        if j >= end:
            raise DocError(f"울타리 블록이 닫히지 않았다: 줄 {i + 1} 정보={info!r}")
        out.append((info, "\n".join(body) + "\n"))
        i = j + 1
    return out


def block(text: str, info: str, section: Optional[Section] = None) -> str:
    """정보 문자열이 ``info`` 인 블록 하나(절 안 또는 문서 전체). 없거나 둘 이상이면 DocError."""
    lines = split_lines(text)
    rng = (section.start, section.end) if section else (0, len(lines))
    hits = [b for i, b in fenced_blocks(lines, *rng) if i == info]
    where = f"절 {section.id}" if section else "문서"
    if len(hits) != 1:
        raise DocError(f"{where} 에 ```{info} 블록이 {len(hits)}개다(1 이어야 한다)")
    return hits[0]


def optional_block(text: str, info: str, section: Optional[Section] = None) -> Optional[str]:
    """``block`` 과 같되 없으면 None(둘 이상이면 DocError)."""
    lines = split_lines(text)
    rng = (section.start, section.end) if section else (0, len(lines))
    hits = [b for i, b in fenced_blocks(lines, *rng) if i == info]
    if len(hits) > 1:
        raise DocError(f"```{info} 블록이 {len(hits)}개다(0 또는 1 이어야 한다)")
    return hits[0] if hits else None


def section_mode(text: str, section: Section) -> Optional[str]:
    """절 안의 ``권고 모드: X`` 값(울타리 밖 첫 줄). 없으면 None."""
    lines = split_lines(text)
    fence: Optional[str] = None
    for line in lines[section.start:section.end]:
        m = FENCE_RE.match(line)
        if m:
            fence = None if fence else m.group("fence")
            continue
        if fence:
            continue
        mm = MODE_RE.search(line)
        if mm:
            return mm.group(1)
    return None
