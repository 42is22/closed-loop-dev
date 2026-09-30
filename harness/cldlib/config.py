# -*- coding: utf-8 -*-
"""``.cld/config.toml`` 을 찾고 읽는다.

설정은 대상 저장소 루트의 ``.cld/config.toml`` 하나다. 없으면 하네스 명령은 멈추고(ConfigError),
훅은 조용히 아무것도 하지 않는다(설치하지 않은 저장소를 방해하지 않는다).
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from typing import Optional

CONFIG_REL = os.path.join(".cld", "config.toml")


class ConfigError(RuntimeError):
    """설정이 없거나 틀렸다."""


@dataclass(frozen=True)
class Gate:
    """게이트 한 단계. ``cmd`` 는 인자 목록이다(셸을 거치지 않는다)."""

    name: str
    cmd: tuple[str, ...]
    group: int = 1
    expect: str = ""          # 정규식 — 비어 있지 않으면 출력에 있어야 통과
    timeout: int = 1800       # 초
    cwd: str = "."            # 저장소 루트 기준
    env: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Config:
    """읽은 설정. 경로는 모두 저장소 루트 기준 상대 경로 그대로 둔다."""

    root: str
    project: str
    lang: str
    master_plan: str
    session_prompts: str
    handover: str
    tasks_dir: str
    changelog: str
    header_max_lines: int
    ultracode_keyword: str
    handover_max_lines: int
    guard_git: bool
    guard_extra_deny: tuple[str, ...]
    hook_session_start: bool
    hook_stop_reminder: bool
    code_paths: tuple[str, ...]
    heavy_processes: tuple[str, ...]
    lenses: tuple[tuple[str, str], ...]      # (glob, 관점 이름)
    gates: tuple[Gate, ...] = field(default_factory=tuple)
    plan_state_column: str = "상태"          # 마스터 플랜 Phase 표에서 상태를 읽는 열(기존 문서에 붙일 때 바꾼다)

    def path(self, rel: str) -> str:
        """저장소 루트 기준 상대 경로를 절대 경로로."""
        return os.path.normpath(os.path.join(self.root, rel))


def find_root(start: str) -> Optional[str]:
    """``start`` 에서 위로 올라가며 ``.cld/config.toml`` 이 있는 폴더를 찾는다. 없으면 None."""
    cur = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(cur, CONFIG_REL)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def _get(d: dict, dotted: str, default):
    node = d
    for k in dotted.split("."):
        if not isinstance(node, dict) or k not in node:
            return default
        node = node[k]
    return node


def _gate(raw: dict, idx: int) -> Gate:
    name = raw.get("name") or f"gate{idx}"
    cmd = raw.get("cmd")
    if not isinstance(cmd, list) or not cmd or not all(isinstance(c, str) for c in cmd):
        raise ConfigError(f"게이트 cmd 는 문자열 목록이어야 한다(셸을 거치지 않는다): gate={name} cmd={cmd!r}")
    env = raw.get("env", {})
    if not isinstance(env, dict):
        raise ConfigError(f"게이트 env 는 표여야 한다: gate={name}")
    group = raw.get("group", 1)
    timeout = raw.get("timeout", 1800)
    if not isinstance(group, int) or not isinstance(timeout, int) or timeout <= 0:
        raise ConfigError(f"게이트 group · timeout 은 정수(timeout > 0)여야 한다: gate={name} group={group!r} timeout={timeout!r}")
    return Gate(name=name, cmd=tuple(cmd), group=group, expect=str(raw.get("expect", "")), timeout=timeout,
                cwd=str(raw.get("cwd", ".")), env=tuple((str(k), str(v)) for k, v in env.items()))


def load(start: str = ".") -> Config:
    """설정을 읽는다. 없으면 ConfigError."""
    root = find_root(start)
    if root is None:
        raise ConfigError(f"{CONFIG_REL} 을 찾지 못했다(시작={os.path.abspath(start)}) — 먼저 `cld.py init` 을 돌린다")
    path = os.path.join(root, CONFIG_REL)
    try:
        with open(path, "rb") as f:
            d = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"설정을 읽지 못했다: path={path} error={e}") from None
    gates_raw = d.get("gates", [])
    if not isinstance(gates_raw, list):
        raise ConfigError(f"[[gates]] 는 표의 배열이어야 한다: path={path}")
    lenses_raw = _get(d, "verify.lenses", {})
    if not isinstance(lenses_raw, dict):
        raise ConfigError(f"[verify.lenses] 는 표여야 한다(glob = 관점): path={path}")
    return Config(
        root=root,
        project=str(_get(d, "project.name", os.path.basename(root))),
        lang=str(_get(d, "project.lang", "ko")),
        master_plan=str(_get(d, "docs.master_plan", "")),
        session_prompts=str(_get(d, "docs.session_prompts", "")),
        handover=str(_get(d, "docs.handover", "")),
        tasks_dir=str(_get(d, "docs.tasks_dir", "tasks")),
        changelog=str(_get(d, "docs.changelog", "CHANGELOG.md")),
        header_max_lines=int(_get(d, "prompt.header_max_lines", 10)),
        ultracode_keyword=str(_get(d, "prompt.ultracode_keyword", "ultracode")),
        handover_max_lines=int(_get(d, "handover.max_section_lines", 80)),
        guard_git=bool(_get(d, "guard.git_write", True)),
        guard_extra_deny=tuple(str(x) for x in _get(d, "guard.extra_deny", [])),
        hook_session_start=bool(_get(d, "hooks.session_start", True)),
        hook_stop_reminder=bool(_get(d, "hooks.stop_reminder", True)),
        code_paths=tuple(str(x) for x in _get(d, "hooks.code_paths", [])),
        heavy_processes=tuple(str(x) for x in _get(d, "verify.heavy_processes", [])),
        lenses=tuple((str(k), str(v)) for k, v in lenses_raw.items()),
        gates=tuple(_gate(g, i) for i, g in enumerate(gates_raw, 1)),
        plan_state_column=str(_get(d, "plan.state_column", "상태")),
    )
