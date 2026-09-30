# -*- coding: utf-8 -*-
"""Phase 세션 프롬프트 조립 — 머리 + 공통 블록 + Phase 블록 (+ 🔴 · 🟡 면 다중 에이전트 블록).

약속(templates/session-prompts.md):
    - 공통 블록 ```cld-common``` 과 다중 에이전트 블록 ```cld-multi``` 는 문서에 하나씩 있다.
    - Phase 절 ``## <id>. <제목>`` 안에 ``권고 모드: X`` 한 줄 · ```cld-head```(머리 — 선택) · ```cld-body```(본문)가 있다.
    - 머리는 ``header_max_lines`` 줄 안쪽이다(구분선 포함).
    - 🔴 세션만 머리 첫 줄에 울트라코드 낱말을 둔다. 🟢 · 🟡 프롬프트 어디에도 그 낱말이 없어야 한다(낱말이 모드를 켠다).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import mdtext

SEP = "=" * 74


class PromptError(ValueError):
    """프롬프트를 만들 수 없다(문서 형식 · 모드 · 길이)."""


@dataclass(frozen=True)
class Built:
    text: str
    mode: str
    head_lines: int
    total_lines: int
    parts: tuple[str, ...]


def _default_head(project: str, sid: str, title: str, mode: str) -> str:
    how = {"🔴": "모든 실질 작업을 워크플로로 돌린다(맨 끝 «다중 에이전트 운용»)",
           "🟡": "구현은 MAX 로 하고, 구현 뒤 검토에서만 워크플로를 한 번 돌린다(맨 끝 «다중 에이전트 운용»)",
           "🟢": "MAX 로 돈다(워크플로 없이)"}[mode]
    return (f"{mode} 이번 세션 = {project} · {sid} — {title}. {how}.\n"
            f"   아래는 공통 블록 → {sid} 블록 순서다. 할 일은 {sid} 블록의 «■ 이번 세션» 절이다.\n")


def build(doc_text: str, sid: str, project: str, mode: Optional[str] = None, header_max_lines: int = 10,
          keyword: str = "ultracode") -> Built:
    """``doc_text``(세션 프롬프트 문서)에서 ``sid`` Phase 의 프롬프트를 만든다."""
    try:
        sec = mdtext.find_section(doc_text, sid)
        common = mdtext.block(doc_text, "cld-common")
        body = mdtext.block(doc_text, "cld-body", sec)
        head = mdtext.optional_block(doc_text, "cld-head", sec)
        declared = mdtext.section_mode(doc_text, sec)
    except mdtext.DocError as e:
        raise PromptError(str(e)) from None
    use = mode or declared
    if use not in mdtext.MODES:
        raise PromptError(f"절 {sid} 에 «권고 모드: 🔴|🟡|🟢» 줄이 없고 --mode 도 없다")
    head = head if head is not None else _default_head(project, sid, sec.title, use)
    kw = keyword.lower()
    if use == "🔴":
        first, _, rest = head.partition("\n")
        if kw not in first.lower():
            head = f"{keyword} · {first}\n{rest}" if rest else f"{keyword} · {first}\n"
    parts = ["head", "common", sid]
    chunks = [head.rstrip("\n") + "\n\n" + SEP + "\n", common, SEP + "\n", body]
    if use in ("🔴", "🟡"):
        try:
            multi = mdtext.block(doc_text, "cld-multi")
        except mdtext.DocError as e:
            raise PromptError(f"{use} 세션은 다중 에이전트 블록이 필요하다: {e}") from None
        chunks += [SEP + "\n", multi]
        parts.append("multi")
    text = "\n".join(c.rstrip("\n") + "\n" for c in chunks)
    head_lines = len(head.rstrip("\n").split("\n")) + 2       # 머리 + 빈 줄 + 구분선
    if head_lines > header_max_lines:
        raise PromptError(f"머리가 {head_lines}줄이다(상한 {header_max_lines} — 빈 줄 · 구분선 포함). 끝난 단계 · 이력 · 일화를 뺀다")
    if use != "🔴":
        for i, line in enumerate(text.split("\n"), 1):
            if kw in line.lower():
                raise PromptError(f"{use} 프롬프트에 «{keyword}» 낱말이 있다(줄 {i}) — 그 낱말은 🔴 모드를 켠다: {line.strip()[:80]}")
    return Built(text=text, mode=use, head_lines=head_lines, total_lines=len(text.rstrip("\n").split("\n")), parts=tuple(parts))
