# -*- coding: utf-8 -*-
"""대상 저장소에 폐루프 틀을 깐다 — 문서 셋 · tasks · 규칙 · 설정 · 하네스 사본.

«도입(adopt)» 은 이미 계획 · 세션 프롬프트 · 인수인계 문서가 있는 저장소에 붙는다. 문서 틀을 만들지 않고,
설정이 기존 문서를 가리키게 한다(병렬 문서를 만들지 않는다). 인수인계에 삽입 표식이 없으면 알린다.

있는 파일은 덮지 않는다(``--force`` 일 때만). 무엇을 만들고 무엇을 건너뛰었는지 표로 알린다.
하네스는 대상 저장소 ``.cld/harness/`` 에 사본으로 둔다 — 스킬 · 게이트가 플러그인 설치 여부와 무관하게 같은 경로를 부른다.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import shutil
from dataclasses import dataclass
from typing import Optional

TOOL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass(frozen=True)
class Planned:
    src: str          # 틀 경로(도구 저장소 기준) 또는 "<harness>"
    dst: str          # 대상 저장소 기준
    render: bool      # 자리표시를 채우는가


RULES = ("process", "git", "verification", "writing")


@dataclass(frozen=True)
class Adopt:
    """기존 문서에 붙인다(저장소 루트 기준 경로)."""

    master_plan: str
    session_prompts: str
    handover: str
    tasks_dir: str = "tasks"
    changelog: str = "CHANGELOG.md"
    state_column: str = "상태"


def slugify(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_").lower()
    return s or "project"


def plan(name: str, slug: str, date8: str, docs_dir: str, writing_rule: bool, adopt: Optional[Adopt] = None,
         rules: Optional[list[str]] = None) -> tuple[list[Planned], dict]:
    if adopt is not None:
        names = {"MASTER_PLAN": adopt.master_plan, "SESSION_PROMPTS": adopt.session_prompts, "HANDOVER": adopt.handover,
                 "TASKS_DIR": adopt.tasks_dir, "CHANGELOG": adopt.changelog, "PLAN_STATE_COLUMN": adopt.state_column}
    else:
        names = {
        "MASTER_PLAN": f"{docs_dir}/PLN-{slug}_master_plan-{date8}.md",
        "SESSION_PROMPTS": f"{docs_dir}/GDE-{slug}_phase_session_prompts-{date8}.md",
        "HANDOVER": f"{docs_dir}/GDE-{slug}_phase_handover-{date8}.md",
        "TASKS_DIR": "tasks",
        "CHANGELOG": "CHANGELOG.md",
        "PLAN_STATE_COLUMN": "상태",
    }
    selected = list(rules) if rules else ["process", "git", "verification"] + (["writing"] if writing_rule else [])
    bad = [r for r in selected if r not in RULES]
    if bad:
        raise ValueError(f"모르는 규칙: {bad} — 고를 수 있는 것: {', '.join(RULES)}")
    docs = [] if adopt is not None else [
        Planned("templates/master-plan.md", names["MASTER_PLAN"], True),
        Planned("templates/session-prompts.md", names["SESSION_PROMPTS"], True),
        Planned("templates/handover.md", names["HANDOVER"], True),
        Planned("templates/tasks-README.md", "tasks/README.md", True),
        Planned("templates/task-TEMPLATE.md", "tasks/TEMPLATE.md", True),
        Planned("templates/changelog.md", "CHANGELOG.md", True),
    ]
    items = docs + [Planned("templates/config.toml", ".cld/config.toml", True)]
    items += [Planned(f"rules/cld-{r}.md", f".claude/rules/cld-{r}.md", True) for r in RULES if r in selected]
    items.append(Planned("<harness>", ".cld/harness", False))
    return items, names


def _render(text: str, values: dict) -> str:
    def rep(m: re.Match) -> str:
        k = m.group(1)
        return values[k] if k in values else m.group(0)
    return re.sub(r"\{\{([A-Z0-9_]+)\}\}", rep, text)


def _copy_harness(dst_dir: str) -> None:
    src = os.path.join(TOOL_ROOT, "harness")
    os.makedirs(os.path.join(dst_dir, "cldlib"), exist_ok=True)
    shutil.copy2(os.path.join(src, "cld.py"), os.path.join(dst_dir, "cld.py"))
    for f in sorted(os.listdir(os.path.join(src, "cldlib"))):
        if f.endswith(".py"):
            shutil.copy2(os.path.join(src, "cldlib", f), os.path.join(dst_dir, "cldlib", f))
    with open(os.path.join(dst_dir, "README.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("closed-loop-dev 하네스 사본 — `cld.py init --upgrade-harness` 가 갱신한다. 손으로 고치지 않는다.\n")


def run(target: str, name: str, slug: str = "", date: str = "", docs_dir: str = "docs", force: bool = False,
        dry_run: bool = False, writing_rule: bool = True, upgrade_harness: bool = False, adopt: Optional[Adopt] = None,
        rules: Optional[list[str]] = None) -> list[tuple[str, str]]:
    """틀을 깐다. 돌려주는 값은 (대상 경로, 결과) 목록."""
    target = os.path.abspath(target)
    if not os.path.isdir(target):
        raise FileNotFoundError(f"대상 폴더가 없다: {target}")
    if adopt is not None:
        missing = [p for p in (adopt.master_plan, adopt.session_prompts, adopt.handover) if not os.path.isfile(os.path.join(target, p))]
        if missing:
            raise FileNotFoundError(f"도입할 문서가 없다(저장소 루트 기준): {missing}")
    d = _dt.date.fromisoformat(date) if date else _dt.date.today()
    slug = slug or slugify(name)
    items, names = plan(name, slug, d.strftime("%Y%m%d"), docs_dir.strip("/\\") or "docs", writing_rule, adopt, rules)
    values = {"PROJECT": name, "SLUG": slug, "DATE": d.isoformat(), "DATE8": d.strftime("%Y%m%d"), **names}
    out: list[tuple[str, str]] = []
    for it in items:
        dst = os.path.join(target, it.dst)
        if it.src == "<harness>":
            exists = os.path.isdir(dst)
            if exists and not (force or upgrade_harness):
                out.append((it.dst, "건너뜀(있다 — --upgrade-harness 로 갱신)"))
                continue
            if not dry_run:
                _copy_harness(dst)
            out.append((it.dst, "갱신" if exists else "만듦"))
            continue
        if upgrade_harness:
            continue
        existed = os.path.exists(dst)
        if existed and not force:
            out.append((it.dst, "건너뜀(있다)"))
            continue
        with open(os.path.join(TOOL_ROOT, it.src), encoding="utf-8") as fh:
            text = fh.read()
        if it.render:
            text = _render(text, values)
        if not dry_run:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        out.append((it.dst, "덮어씀" if existed else "만듦"))
    if adopt is not None and not upgrade_harness:
        from .handover import MARKER
        with open(os.path.join(target, adopt.handover), encoding="utf-8") as fh:
            if MARKER not in fh.read():
                out.append((adopt.handover, f"⚠ 표식 없음 — «쓰는 법» 절 뒤, 맨 위 항목 앞에 {MARKER} 한 줄을 넣는다"))
    return out
