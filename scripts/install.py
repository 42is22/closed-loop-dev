# -*- coding: utf-8 -*-
"""복사 설치 — 플러그인을 쓰지 않는(또는 못 쓰는) 저장소에 closed-loop-dev 를 깐다.

플러그인과 같은 것을 저장소 안에 둔다:
    skills/*           → <대상>/.claude/skills/<이름>/
    agents/*.md        → <대상>/.claude/agents/
    hooks/hooks.json   → <대상>/.claude/settings.json 의 hooks 에 합친다(있는 설정은 보존 · 백업 .cldbak)
    harness/           → <대상>/.cld/harness/
    + cld.py init      → 문서 셋 · tasks · 규칙 · 설정(있는 파일은 건너뜀)
    --cursor           → <대상>/.cursor/rules/cld-*.mdc (규칙은 항상 적용 · 스킬은 요청 시)

사용:
    python scripts/install.py --target <저장소> --name "<프로젝트>" [--slug x] [--cursor] [--no-hooks] [--dry-run] [--force]
기존 문서가 있는 저장소(도입):
    python scripts/install.py --target <저장소> --name "<프로젝트>" --adopt --master-plan <경로> --session-prompts <경로> \
        --handover <경로> [--tasks-dir tasks] [--changelog CHANGELOG.md] [--plan-state-column 상태] [--rules process,verification]
표준 라이브러리만 쓴다(Python 3.11+).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

TOOL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(TOOL_ROOT, "harness"))

from cldlib import initcmd  # noqa: E402

HOOK_MARK = "harness/cld.py"      # json.dumps 가 따옴표를 이스케이프하므로 따옴표 없는 조각으로 찾는다
PLUGIN_CMD = "\"${CLAUDE_PLUGIN_ROOT}/harness/cld.py\""
PROJECT_CMD = "\"$CLAUDE_PROJECT_DIR/.cld/harness/cld.py\""


def _frontmatter(text: str) -> tuple[dict, str]:
    """SKILL.md · 에이전트 파일의 머리(간단한 key: value 만)와 본문."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    meta: dict = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, text[end + 5:]


def _copy_tree(src: str, dst: str, force: bool, dry: bool, out: list) -> None:
    for base, _dirs, files in os.walk(src):
        for f in files:
            s = os.path.join(base, f)
            rel = os.path.relpath(s, src)
            d = os.path.join(dst, rel)
            if os.path.exists(d) and not force:
                out.append((os.path.relpath(d), "건너뜀(있다)"))
                continue
            if not dry:
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
            out.append((os.path.relpath(d), "만듦"))


def merge_hooks(settings_path: str, dry: bool) -> str:
    """플러그인 hooks.json 을 프로젝트 settings.json 에 합친다(이미 있으면 그대로)."""
    with open(os.path.join(TOOL_ROOT, "hooks", "hooks.json"), encoding="utf-8") as f:
        plugin = json.load(f)["hooks"]
    settings: dict = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, encoding="utf-8") as f:
                settings = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise SystemExit(f"settings.json 을 읽지 못했다(고치지 않았다): path={settings_path} error={e}")
    hooks = settings.setdefault("hooks", {})
    added = 0
    for event, entries in plugin.items():
        cur = hooks.setdefault(event, [])
        if any(HOOK_MARK in json.dumps(e, ensure_ascii=False) for e in cur):
            continue
        for e in entries:
            cur.append(json.loads(json.dumps(e).replace(json.dumps(PLUGIN_CMD)[1:-1], json.dumps(PROJECT_CMD)[1:-1])))
            added += 1
    if added and not dry:
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        if os.path.exists(settings_path):
            shutil.copy2(settings_path, settings_path + ".cldbak")
        tmp = settings_path + ".cldtmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, settings_path)
    return f"훅 {added}개 더함" if added else "훅 이미 있음(그대로)"


def cursor_rules(target: str, values: dict, force: bool, dry: bool, out: list, rules: list[str]) -> None:
    """규칙 · 스킬을 Cursor .mdc 로 옮긴다(규칙은 항상 적용, 스킬은 설명으로 요청 시)."""
    dst_dir = os.path.join(target, ".cursor", "rules")
    items: list[tuple[str, str, str, bool]] = []
    for f in sorted(os.listdir(os.path.join(TOOL_ROOT, "rules"))):
        if f.endswith(".md") and f[len("cld-"):-3] in rules:
            meta, body = _frontmatter(Path(os.path.join(TOOL_ROOT, "rules", f)).read_text(encoding="utf-8"))
            items.append((f[:-3], meta.get("description", f"closed-loop-dev 규칙 — {f[:-3]}"), initcmd._render(body, values), True))
    for d in sorted(os.listdir(os.path.join(TOOL_ROOT, "skills"))):
        p = os.path.join(TOOL_ROOT, "skills", d, "SKILL.md")
        if os.path.isfile(p):
            meta, body = _frontmatter(Path(p).read_text(encoding="utf-8"))
            items.append((d, meta.get("description", d), body, False))
    for name, desc, body, always in items:
        dst = os.path.join(dst_dir, f"{name}.mdc")
        if os.path.exists(dst) and not force:
            out.append((os.path.relpath(dst, target), "건너뜀(있다)"))
            continue
        text = f"---\ndescription: {json.dumps(desc, ensure_ascii=False)}\nglobs:\nalwaysApply: {'true' if always else 'false'}\n---\n\n{body.lstrip()}"
        if not dry:
            os.makedirs(dst_dir, exist_ok=True)
            with open(dst, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        out.append((os.path.relpath(dst, target), "만듦"))


def main(argv: list[str]) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description="closed-loop-dev 복사 설치")
    p.add_argument("--target", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--slug", default="")
    p.add_argument("--date", default="")
    p.add_argument("--cursor", action="store_true", help=".cursor/rules/*.mdc 도 만든다")
    p.add_argument("--no-hooks", action="store_true", help=".claude/settings.json 에 훅을 넣지 않는다")
    p.add_argument("--no-writing-rule", action="store_true")
    p.add_argument("--force", action="store_true", help="있는 파일도 덮는다")
    p.add_argument("--adopt", action="store_true", help="기존 문서에 붙는다(문서 틀을 만들지 않는다)")
    p.add_argument("--master-plan", default="")
    p.add_argument("--session-prompts", default="")
    p.add_argument("--handover", default="")
    p.add_argument("--tasks-dir", default="tasks")
    p.add_argument("--changelog", default="CHANGELOG.md")
    p.add_argument("--plan-state-column", default="상태")
    p.add_argument("--rules", default="", help="깔 규칙(쉼표): process,git,verification,writing — 기본 전부")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    target = os.path.abspath(a.target)
    if not os.path.isdir(target):
        print(f"대상 폴더가 없다: {target}", file=sys.stderr)
        return 2
    name = a.name or os.path.basename(target)
    adopt = None
    if a.adopt:
        if not (a.master_plan and a.session_prompts and a.handover):
            print("--adopt 는 --master-plan · --session-prompts · --handover 가 필요하다(저장소 루트 기준 경로)", file=sys.stderr)
            return 2
        adopt = initcmd.Adopt(a.master_plan, a.session_prompts, a.handover, a.tasks_dir, a.changelog, a.plan_state_column)
    rules = [r.strip() for r in a.rules.split(",") if r.strip()] if a.rules else None
    cwd = os.getcwd()
    os.chdir(target)
    out: list[tuple[str, str]] = []
    try:
        for d in sorted(os.listdir(os.path.join(TOOL_ROOT, "skills"))):
            _copy_tree(os.path.join(TOOL_ROOT, "skills", d), os.path.join(target, ".claude", "skills", d), a.force, a.dry_run, out)
        _copy_tree(os.path.join(TOOL_ROOT, "agents"), os.path.join(target, ".claude", "agents"), a.force, a.dry_run, out)
        res = initcmd.run(target, name, a.slug, a.date, "docs", a.force, a.dry_run, not a.no_writing_rule, False, adopt, rules)
        out += res
        if not a.no_hooks:
            out.append((".claude/settings.json", merge_hooks(os.path.join(target, ".claude", "settings.json"), a.dry_run)))
        if a.cursor:
            import datetime as _dt
            dd = _dt.date.fromisoformat(a.date) if a.date else _dt.date.today()
            _items, names = initcmd.plan(name, a.slug or initcmd.slugify(name), dd.strftime("%Y%m%d"), "docs",
                                         not a.no_writing_rule, adopt, rules)
            values = {"PROJECT": name, "DATE": dd.isoformat(), **names}
            chosen = [p.src[len("rules/cld-"):-3] for p in _items if p.src.startswith("rules/")]
            cursor_rules(target, values, a.force, a.dry_run, out, chosen)
    finally:
        os.chdir(cwd)
    for dst, what in out:
        print(f"  {what:<28} {dst}")
    print("(dry-run — 아무것도 쓰지 않았다)" if a.dry_run else
          "다음: .cld/config.toml 의 [[gates]] 를 채우고 `python .cld/harness/cld.py status`. 스킬은 새 세션에서 /cld-plan 등으로 부른다.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
