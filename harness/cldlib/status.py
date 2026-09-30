# -*- coding: utf-8 -*-
"""폐루프 상태 요약 — 마스터 플랜의 Phase 표 · 인수인계 맨 위 항목 · 세션 프롬프트 절 유무.

마스터 플랜의 Phase 표는 머리에 ``Phase`` 와 ``상태`` 열이 있는 첫 표다(templates/master-plan.md).
상태 값의 첫 낱말이 ``완료`` 면 끝난 행이다. 끝나지 않은 첫 행이 «다음» 이다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from . import handover, mdtext
from .config import Config

DONE_RE = re.compile(r"^\W*(완료|done|✅)", re.IGNORECASE)


@dataclass(frozen=True)
class PhaseRow:
    order: str
    phase: str
    what: str
    state: str

    @property
    def done(self) -> bool:
        return bool(DONE_RE.match(self.state.replace("*", "").strip()))


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def phase_rows(plan_text: str) -> list[PhaseRow]:
    """Phase 표의 행. 표가 없으면 빈 목록."""
    lines = mdtext.split_lines(plan_text)
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        head = _cells(line)
        if "Phase" in head and "상태" in head and i + 1 < len(lines) and re.fullmatch(r"\|?[-| :]+\|?", lines[i + 1].strip()):
            ip, ist = head.index("Phase"), head.index("상태")
            io = 0
            iw = next((k for k, h in enumerate(head) if h in ("무엇", "내용", "범위")), ip)
            rows: list[PhaseRow] = []
            for row in lines[i + 2:]:
                if not row.lstrip().startswith("|"):
                    break
                c = _cells(row)
                if len(c) < len(head):
                    c += [""] * (len(head) - len(c))
                rows.append(PhaseRow(order=c[io], phase=c[ip].replace("*", ""), what=c[iw], state=c[ist]))
            return rows
    return []


@dataclass(frozen=True)
class Status:
    rows: tuple[PhaseRow, ...]
    next_phase: Optional[PhaseRow]
    handover_top: Optional[str]
    handover_ok: Optional[bool]
    prompt_section: Optional[bool]
    notes: tuple[str, ...]


def _read(path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def collect(cfg: Config) -> Status:
    notes: list[str] = []
    plan = _read(cfg.path(cfg.master_plan)) if cfg.master_plan else None
    if plan is None:
        notes.append(f"마스터 플랜을 읽지 못했다: {cfg.master_plan or '(설정 없음)'}")
    rows = tuple(phase_rows(plan)) if plan else ()
    if plan is not None and not rows:
        notes.append("마스터 플랜에 «Phase · 상태» 열이 있는 표가 없다")
    nxt = next((r for r in rows if not r.done), None)
    top, ok = None, None
    ho = _read(cfg.path(cfg.handover)) if cfg.handover else None
    if ho is None:
        notes.append(f"인수인계 문서를 읽지 못했다: {cfg.handover or '(설정 없음)'}")
    else:
        try:
            ents = handover.entries(ho)
            if ents:
                top = f"{ents[0].id}. {ents[0].title}"
                ok = handover.check(ho, None, cfg.handover_max_lines).ok
        except handover.HandoverError as e:
            notes.append(f"인수인계: {e}")
    sp = _read(cfg.path(cfg.session_prompts)) if cfg.session_prompts else None
    has_prompt: Optional[bool] = None
    if sp is None:
        notes.append(f"세션 프롬프트 문서를 읽지 못했다: {cfg.session_prompts or '(설정 없음)'}")
    elif nxt is not None:
        pid = nxt.phase.split()[0] if nxt.phase else ""
        has_prompt = any(s.id == pid for s in mdtext.sections(sp))
    return Status(rows=rows, next_phase=nxt, handover_top=top, handover_ok=ok, prompt_section=has_prompt, notes=tuple(notes))


def render(cfg: Config, st: Status, short: bool = False) -> str:
    out = [f"[closed-loop-dev] {cfg.project} — 폐루프 상태"]
    done = sum(1 for r in st.rows if r.done)
    out.append(f"  Phase {done}/{len(st.rows)} 완료")
    if st.next_phase:
        n = st.next_phase
        out.append(f"  다음: {n.order} {n.phase} — {n.what[:70]} (상태: {n.state[:40]})")
        if st.prompt_section is False:
            out.append(f"  ⚠ 세션 프롬프트 문서에 `## {n.phase.split()[0]}. …` 절이 없다 — cld-prompt 로 만든다")
    elif st.rows:
        out.append("  다음: 없음(모든 Phase 완료)")
    if st.handover_top:
        mark = "네 칸 OK" if st.handover_ok else "⚠ 네 칸 검사 실패 — `cld.py handover check`"
        out.append(f"  인수인계 맨 위: {st.handover_top[:90]} · {mark}")
    for n in st.notes:
        out.append(f"  ⚠ {n}")
    if not short:
        out.append(f"  문서: 마스터 플랜 {cfg.master_plan} · 세션 프롬프트 {cfg.session_prompts} · 인수인계 {cfg.handover}")
        out.append("  하네스: python .cld/harness/cld.py <status|prompt|handover|gates|patch|tree|verify>")
    return "\n".join(out)
