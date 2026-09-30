# -*- coding: utf-8 -*-
"""대상 저장소에 폐루프 틀을 깐다 — 문서 셋 · tasks · 규칙 · 설정 · 하네스 사본.

있는 파일은 덮지 않는다(``--force`` 일 때만). 무엇을 만들고 무엇을 건너뛰었는지 표로 알린다.
하네스는 대상 저장소 ``.cld/harness/`` 에 사본으로 둔다 — 스킬 · 게이트가 플러그인 설치 여부와 무관하게 같은 경로를 부른다.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import shutil
from dataclasses import dataclass

TOOL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass(frozen=True)
class Planned:
    src: str          # 틀 경로(도구 저장소 기준) 또는 "<harness>"
    dst: str          # 대상 저장소 기준
    render: bool      # 자리표시를 채우는가


def slugify(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_").lower()
    return s or "project"


def plan(name: str, slug: str, date8: str, docs_dir: str, writing_rule: bool) -> tuple[list[Planned], dict]:
    names = {
        "MASTER_PLAN": f"{docs_dir}/PLN-{slug}_master_plan-{date8}.md",
        "SESSION_PROMPTS": f"{docs_dir}/GDE-{slug}_phase_session_prompts-{date8}.md",
        "HANDOVER": f"{docs_dir}/GDE-{slug}_phase_handover-{date8}.md",
        "TASKS_DIR": "tasks",
        "CHANGELOG": "CHANGELOG.md",
    }
    items = [
        Planned("templates/master-plan.md", names["MASTER_PLAN"], True),
        Planned("templates/session-prompts.md", names["SESSION_PROMPTS"], True),
        Planned("templates/handover.md", names["HANDOVER"], True),
        Planned("templates/tasks-README.md", "tasks/README.md", True),
        Planned("templates/task-TEMPLATE.md", "tasks/TEMPLATE.md", True),
        Planned("templates/changelog.md", "CHANGELOG.md", True),
        Planned("templates/config.toml", ".cld/config.toml", True),
        Planned("rules/cld-process.md", ".claude/rules/cld-process.md", True),
        Planned("rules/cld-git.md", ".claude/rules/cld-git.md", True),
        Planned("rules/cld-verification.md", ".claude/rules/cld-verification.md", True),
        Planned("<harness>", ".cld/harness", False),
    ]
    if writing_rule:
        items.insert(-1, Planned("rules/cld-writing.md", ".claude/rules/cld-writing.md", True))
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
        dry_run: bool = False, writing_rule: bool = True, upgrade_harness: bool = False) -> list[tuple[str, str]]:
    """틀을 깐다. 돌려주는 값은 (대상 경로, 결과) 목록."""
    target = os.path.abspath(target)
    if not os.path.isdir(target):
        raise FileNotFoundError(f"대상 폴더가 없다: {target}")
    d = _dt.date.fromisoformat(date) if date else _dt.date.today()
    slug = slug or slugify(name)
    items, names = plan(name, slug, d.strftime("%Y%m%d"), docs_dir.strip("/\\") or "docs", writing_rule)
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
    return out
