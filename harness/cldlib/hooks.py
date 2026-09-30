# -*- coding: utf-8 -*-
"""Claude Code 훅 진입점 — stdin 으로 사건 JSON 을 받고 stdout 으로 JSON 을 낸다.

    session-start : 설정이 있으면 폐루프 상태를 추가 문맥으로 넣는다.
    pre-bash      : 에이전트의 git 쓰기(commit · push · tag 만들기 · reset …)를 거부한다(설정 guard.git_write).
    stop          : 코드가 바뀌었는데 인수인계가 안 바뀌었으면 알린다(막지 않는다).

🔴 git 가드는 실수 방지 가드레일이지 보안 경계가 아니다. 명령 문자열을 토큰으로 볼 뿐이라
``powershell -Command …`` · ``python -c …`` 로 부르면 지나간다. 규칙(.claude/rules/cld-git.md)이 우선이다.
설정이 없는 저장소에서는 세 훅 모두 아무것도 하지 않는다(exit 0 · 출력 없음).
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from typing import Optional

from . import config as cfgmod
from . import status as statusmod

# 에이전트가 하지 않는 git 하위 명령(작업 트리 · 이력 · 원격을 바꾼다)
GIT_WRITE = {"commit", "push", "reset", "clean", "checkout", "restore", "stash", "rebase", "merge", "cherry-pick",
             "switch", "revert", "am", "apply", "pull", "worktree", "filter-branch", "gc", "prune", "update-ref"}
GIT_GLOBAL_OPT_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
SEPARATORS = {"&&", "||", ";", "|", "&", "\n"}
TAG_READ = {"-l", "--list", "--contains", "--no-contains", "--points-at", "--merged", "--no-merged", "-v", "--verify"}


def _read_event() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()


def _tokens(command: str) -> list[str]:
    """명령을 토큰으로 자른다. 구분자(&& · ; · | · 줄바꿈)는 따로 떼어 토큰으로 둔다."""
    spaced = re.sub(r"(&&|\|\||;|\||\n)", r" \1 ", command)
    try:
        return shlex.split(spaced, posix=True)
    except ValueError:
        return spaced.split()


def git_write_reason(command: str) -> Optional[str]:
    """명령 안에 에이전트가 하지 않는 git 쓰기가 있으면 그 사유를, 없으면 None."""
    toks = _tokens(command)
    i = 0
    while i < len(toks):
        t = toks[i]
        base = os.path.basename(t).lower()
        if base in ("git", "git.exe") and (i == 0 or toks[i - 1] in SEPARATORS or toks[i - 1] in ("sudo", "env", "command", "exec", "time")):
            j = i + 1
            while j < len(toks) and toks[j].startswith("-"):
                j += 2 if toks[j] in GIT_GLOBAL_OPT_WITH_ARG else 1
            if j < len(toks):
                sub = toks[j]
                rest = []
                k = j + 1
                while k < len(toks) and toks[k] not in SEPARATORS:
                    rest.append(toks[k])
                    k += 1
                first = rest[0] if rest else ""
                if sub in ("stash", "worktree") and first in ("list", "show"):
                    pass
                elif sub in GIT_WRITE:
                    return f"git {sub}"
                if sub == "tag" and rest and not (first in TAG_READ or first.startswith(("--sort=", "-n", "--format="))):
                    return "git tag(만들기 · 지우기)"
                if sub == "branch" and rest and rest[0] not in ("-a", "-r", "-v", "-vv", "--list", "-l", "--show-current", "--contains", "--merged", "--no-merged") and not rest[0].startswith("--sort"):
                    return "git branch(만들기 · 지우기 · 바꾸기)"
                if sub == "remote" and rest and rest[0] in ("add", "remove", "rm", "rename", "set-url", "prune"):
                    return f"git remote {rest[0]}"
                if sub == "config" and rest and not any(r in ("--get", "--list", "-l", "--get-all", "--show-origin") for r in rest):
                    return "git config(값 쓰기)"
            i = j
        i += 1
    return None


def _deny_extra(cfg: cfgmod.Config, command: str) -> Optional[str]:
    for pat in cfg.guard_extra_deny:
        try:
            if re.search(pat, command):
                return f"설정 guard.extra_deny 에 걸렸다: {pat}"
        except re.error:
            continue
    return None


def _config_for(ev: dict) -> Optional[cfgmod.Config]:
    start = ev.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        return cfgmod.load(start)
    except cfgmod.ConfigError:
        return None


def pre_bash() -> int:
    ev = _read_event()
    cfg = _config_for(ev)
    if cfg is None:
        return 0
    cmd = ((ev.get("tool_input") or {}).get("command") or "")
    reason = (git_write_reason(cmd) if cfg.guard_git else None) or _deny_extra(cfg, cmd)
    if reason:
        _emit({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (f"closed-loop-dev 가드: 에이전트는 {reason} 을 실행하지 않는다(.claude/rules/cld-git.md). "
                                         "읽기 전용 git(status · diff · log · show · blame)은 된다. 커밋 · 푸시 · 태그는 명령 초안만 사용자에게 준다."),
        }})
    return 0


def session_start() -> int:
    ev = _read_event()
    cfg = _config_for(ev)
    if cfg is None or not cfg.hook_session_start:
        return 0
    try:
        st = statusmod.collect(cfg)
        text = statusmod.render(cfg, st, short=True)
    except Exception as e:  # noqa: BLE001 — 훅은 세션을 막지 않는다. 사유는 문맥으로 남긴다
        text = f"[closed-loop-dev] 상태를 읽지 못했다: {type(e).__name__}: {e}"
    text += ("\n  폐루프: 마스터 플랜 → Phase 세션 프롬프트 → 구현 세션(인수인계 맨 위 항목) → 독립 검증 세션(인수인계에 기록)"
             " → 마스터 플랜 · 다음 프롬프트. 규칙: .claude/rules/cld-*.md")
    _emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}})
    return 0


def _changed(cfg: cfgmod.Config) -> Optional[list[str]]:
    try:
        r = subprocess.run(["git", "-C", cfg.root, "-c", "core.quotepath=false", "status", "--porcelain", "--untracked-files=all"], capture_output=True,
                           text=True, encoding="utf-8", timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return [l[3:].strip().strip('"') for l in r.stdout.splitlines() if len(l) > 3]


def stop() -> int:
    ev = _read_event()
    if ev.get("stop_hook_active"):
        return 0
    cfg = _config_for(ev)
    if cfg is None or not cfg.hook_stop_reminder or not cfg.code_paths or not cfg.handover:
        return 0
    changed = _changed(cfg)
    if not changed:
        return 0
    norm = [c.replace("\\", "/") for c in changed]
    code = [c for c in norm if any(c == p.rstrip("/") or c.startswith(p.rstrip("/") + "/") for p in cfg.code_paths)]
    ho = cfg.handover.replace("\\", "/")
    if code and ho not in norm:
        _emit({"systemMessage": (f"[closed-loop-dev] 코드 {len(code)}개 파일이 바뀌었는데 인수인계({cfg.handover})가 그대로다. "
                                 "커밋 전에 맨 위 항목(네 칸)을 쓰거나 고친다 — `cld.py handover new|check`.")})
    return 0


def main(which: str) -> int:
    return {"pre-bash": pre_bash, "session-start": session_start, "stop": stop}[which]()
