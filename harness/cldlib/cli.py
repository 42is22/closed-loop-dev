# -*- coding: utf-8 -*-
"""하네스 명령줄 — 하위 명령을 모듈에 넘긴다. 종료 코드: 0 통과 · 1 검사 실패 · 2 사용법 · 설정 오류."""
from __future__ import annotations

import argparse
import datetime as _dt
import os
from pathlib import Path
import sys
import tempfile

from . import __version__
from . import config as cfgmod
from . import gates as gatesmod
from . import handover as homod
from . import hooks as hookmod
from . import initcmd, patch, prompt, status, tree, verify


def _utf8_stdout() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")   # Windows cp949 콘솔에서 한글 출력이 죽지 않게
        except (AttributeError, ValueError):
            pass


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write_keep_eol(path: str, text_lf: str, original_raw: bytes) -> None:
    crlf = original_raw.count(b"\n") > 0 and original_raw.count(b"\r\n") == original_raw.count(b"\n")
    data = (text_lf.replace("\n", "\r\n") if crlf else text_lf).encode("utf-8")
    tmp = path + ".cldtmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def cmd_init(a) -> int:
    adopt = None
    if a.adopt:
        if not (a.master_plan and a.session_prompts and a.handover):
            print("--adopt 는 --master-plan · --session-prompts · --handover 가 필요하다(저장소 루트 기준 경로)", file=sys.stderr)
            return 2
        adopt = initcmd.Adopt(a.master_plan, a.session_prompts, a.handover, a.tasks_dir, a.changelog, a.plan_state_column)
    rules = [r.strip() for r in a.rules.split(",") if r.strip()] if a.rules else None
    res = initcmd.run(a.target, a.name or os.path.basename(os.path.abspath(a.target)), a.slug, a.date, a.docs_dir,
                      a.force, a.dry_run, not a.no_writing_rule, a.upgrade_harness, adopt, rules)
    for dst, what in res:
        print(f"  {what:<32} {dst}")
    if a.dry_run:
        print("(dry-run — 아무것도 쓰지 않았다)")
    elif a.upgrade_harness:
        print("하네스 사본을 갱신했다(.cld/harness). 문서 · 설정 · 규칙은 건드리지 않았다.")
    elif a.adopt:
        print("다음: 인수인계 표식(⚠ 줄)을 넣고 .cld/config.toml 의 [[gates]] · [hooks].code_paths 를 채운다. 확인은 `cld.py status`.")
    else:
        print("다음: 마스터 플랜의 목표 · 완료 기준 · Phase 표를 채운다(스킬 cld-plan). 게이트는 .cld/config.toml [[gates]].")
    return 0


def cmd_status(a) -> int:
    cfg = cfgmod.load(a.root)
    print(status.render(cfg, status.collect(cfg), short=a.short))
    return 0


def cmd_prompt(a) -> int:
    cfg = cfgmod.load(a.root)
    doc = _read(cfg.path(cfg.session_prompts))
    b = prompt.build(doc, a.phase, cfg.project, a.mode, cfg.header_max_lines, cfg.ultracode_keyword)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(b.text)
        print(f"ok {a.out} · 모드 {b.mode} · {b.total_lines}줄 · 머리 {b.head_lines}줄 · 조각 {' + '.join(b.parts)}")
    else:
        sys.stdout.write(b.text)
    return 0


def cmd_handover(a) -> int:
    cfg = cfgmod.load(a.root)
    path = cfg.path(cfg.handover)
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if a.action == "new":
        if not a.phase or not a.title:
            print("handover new 는 --phase 와 --title 이 필요하다", file=sys.stderr)
            return 2
        new = homod.new_entry(text, a.phase, a.title, a.date or _dt.date.today().isoformat())
        _write_keep_eol(path, new, raw)
        print(f"ok 항목 `## {a.phase}. {a.title}` 을 맨 위에 넣었다 — 자리표시({{{{…}}}})를 채운 뒤 `handover check`")
        return 0
    r = homod.check(text, a.phase, cfg.handover_max_lines)
    print(f"인수인계 항목 {r.section} · {r.lines}줄 · {'OK' if r.ok else 'FAIL'}")
    for p in r.problems:
        print(f"  ✗ {p}")
    for w in r.warnings:
        print(f"  ⚠ {w}")
    return 0 if r.ok else 1


def cmd_patch(a) -> int:
    root = a.root_dir or (cfgmod.find_root(".") or os.getcwd())
    edits = patch.load_spec(a.spec)
    for line in patch.apply(edits, root, check_only=a.check):
        print(f"  {line}")
    print("(check — 쓰지 않았다)" if a.check else "ok 모두 썼다")
    return 0


def cmd_gates(a) -> int:
    cfg = cfgmod.load(a.root)
    if a.action == "list":
        for g in cfg.gates:
            print(f"  group={g.group} {g.name}: {' '.join(g.cmd)}" + (f"  expect={g.expect!r}" if g.expect else ""))
        return 0
    out = a.out or tempfile.mkdtemp(prefix="cld_gates_")
    res = gatesmod.run(cfg, out, a.only.split(",") if a.only else None)
    for r in res:
        print(f"  [{'PASS' if r.ok else 'FAIL'}] {r.name} exit={r.exit} {r.seconds:.0f}s :: {r.note}")
    print(f"결과: {sum(r.ok for r in res)}/{len(res)} PASS · 로그 {out}")
    return 0 if all(r.ok for r in res) else 1


def cmd_tree(a) -> int:
    repo = cfgmod.find_root(".") or os.getcwd()
    full = tree.extract(a.repo or repo, a.rev, a.out)
    print(f"ok {a.rev} = {full[:12]} → {a.out}")
    if a.subst:
        tree.subst(a.subst, a.out)
        print(f"ok subst {a.subst.rstrip(':')}: → {a.out} (끝나면 `subst {a.subst.rstrip(':')}: /d`)")
    return 0


def cmd_verify(a) -> int:
    cfg = cfgmod.load(a.root)
    sc = verify.scope(cfg, a.base, a.head)
    scratch = a.scratch or os.path.join(tempfile.gettempdir(), f"cld_verify_{a.head[:12]}")
    text = verify.render(sc, verify.agent_rules(cfg, scratch))
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"ok {a.out} · 커밋 {len(sc.commits)} · 파일 {len(sc.files)} · 관점 {len(sc.lenses)}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_hook(a) -> int:
    return hookmod.main(a.which)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cld.py", description=f"closed-loop-dev 하네스 {__version__}")
    p.add_argument("--root", default=".", help="저장소 안 아무 폴더(설정을 위로 찾는다)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="대상 저장소에 틀을 깐다")
    s.add_argument("--target", default=".")
    s.add_argument("--name", default="")
    s.add_argument("--slug", default="", help="문서 파일 이름에 쓸 ASCII 이름(기본: 이름에서)")
    s.add_argument("--date", default="", help="YYYY-MM-DD(기본 오늘)")
    s.add_argument("--docs-dir", default="docs")
    s.add_argument("--force", action="store_true", help="있는 파일도 덮는다")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--no-writing-rule", action="store_true", help="문체 규칙(cld-writing.md)을 깔지 않는다")
    s.add_argument("--upgrade-harness", action="store_true", help="하네스 사본만 갱신한다")
    s.add_argument("--adopt", action="store_true", help="기존 문서에 붙는다(문서 틀을 만들지 않는다)")
    s.add_argument("--master-plan", default="")
    s.add_argument("--session-prompts", default="")
    s.add_argument("--handover", default="")
    s.add_argument("--tasks-dir", default="tasks")
    s.add_argument("--changelog", default="CHANGELOG.md")
    s.add_argument("--plan-state-column", default="상태", help="Phase 표에서 상태를 읽는 열")
    s.add_argument("--rules", default="", help="깔 규칙(쉼표): process,git,verification,writing — 기본 전부")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("status", help="폐루프 상태 요약")
    s.add_argument("--short", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("prompt", help="Phase 세션 프롬프트")
    s.add_argument("action", choices=["build"])
    s.add_argument("phase")
    s.add_argument("--mode", choices=["🔴", "🟡", "🟢", "red", "yellow", "green"])
    s.add_argument("--out", default="")
    s.set_defaults(fn=cmd_prompt)

    s = sub.add_parser("handover", help="인수인계 항목 신설 · 검사")
    s.add_argument("action", choices=["new", "check"])
    s.add_argument("--phase", default=None)
    s.add_argument("--title", default="")
    s.add_argument("--date", default="")
    s.set_defaults(fn=cmd_handover)

    s = sub.add_parser("patch", help="정확한 자리 치환(줄 끝 보존 · 전부 또는 전무)")
    s.add_argument("spec")
    s.add_argument("--check", action="store_true")
    s.add_argument("--root-dir", default="")
    s.set_defaults(fn=cmd_patch)

    s = sub.add_parser("gates", help="설정의 게이트")
    s.add_argument("action", choices=["run", "list"])
    s.add_argument("--out", default="")
    s.add_argument("--only", default="", help="쉼표로 이름")
    s.set_defaults(fn=cmd_gates)

    s = sub.add_parser("tree", help="커밋을 깨끗한 트리로 푼다")
    s.add_argument("rev")
    s.add_argument("--out", required=True)
    s.add_argument("--repo", default="")
    s.add_argument("--subst", default="", help="Windows 짧은 드라이브(예: T:)")
    s.set_defaults(fn=cmd_tree)

    s = sub.add_parser("verify", help="검증 범위")
    s.add_argument("action", choices=["scope"])
    s.add_argument("base")
    s.add_argument("head")
    s.add_argument("--out", default="")
    s.add_argument("--scratch", default="")
    s.set_defaults(fn=cmd_verify)

    s = sub.add_parser("hook", help="Claude Code 훅 진입점(stdin JSON)")
    s.add_argument("which", choices=["session-start", "pre-bash", "stop"])
    s.set_defaults(fn=cmd_hook)
    return p


MODE_ALIAS = {"red": "🔴", "yellow": "🟡", "green": "🟢"}


def main(argv: list[str]) -> int:
    _utf8_stdout()
    a = build_parser().parse_args(argv)
    if getattr(a, "mode", None) in MODE_ALIAS:
        a.mode = MODE_ALIAS[a.mode]
    try:
        return a.fn(a)
    except (cfgmod.ConfigError, prompt.PromptError, homod.HandoverError, patch.PatchError, tree.TreeError,
            FileNotFoundError, ValueError, RuntimeError) as e:
        if getattr(a, "cmd", "") == "hook":   # 훅은 세션을 막지 않는다
            return 0
        print(f"오류: {e}", file=sys.stderr)
        return 2
