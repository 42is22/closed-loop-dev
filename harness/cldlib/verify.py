# -*- coding: utf-8 -*-
"""독립 검증의 범위를 잡는다 — 커밋 목록 · 바뀐 파일 · 관점 제안 · 에이전트 공통 규칙.

관점 제안은 설정 ``[verify.lenses]`` 의 glob → 관점 이름 표를 바뀐 파일에 대 본다. 표가 비면 기본 관점 넷을 낸다.
에이전트 공통 규칙은 검증 에이전트(에이전트는 세션 프롬프트를 못 본다)마다 넣을 문장이다.
"""
from __future__ import annotations

import fnmatch
import subprocess
from dataclasses import dataclass

from .config import Config

DEFAULT_LENSES = (
    "정합성 — 바뀐 코드가 주장대로 도는가(재현 스크립트로 증명)",
    "게이트가 타지 않는 입구 — 스위치 · 설정 조각 · 도구 인자 · 설치 · 배포 경로",
    "값 불변 주장 — 흔든 입력으로 전후 트리의 결과를 대 본다",
    "문서 대조 — 인수인계 · CHANGELOG · 계획의 주장이 코드 · 시험 결과와 맞는가",
)


@dataclass(frozen=True)
class Scope:
    base: str
    head: str
    commits: tuple[str, ...]
    files: tuple[str, ...]
    lenses: tuple[str, ...]


def _git(cfg: Config, *args: str) -> str:
    r = subprocess.run(["git", "-C", cfg.root, "-c", "core.quotepath=false", *args], capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 실패: {r.stderr.strip()[:200]}")
    return r.stdout


def scope(cfg: Config, base: str, head: str) -> Scope:
    commits = tuple(l for l in _git(cfg, "log", "--format=%h %ad %s", "--date=format:%m-%d %H:%M", f"{base}..{head}").splitlines() if l)
    files = tuple(l for l in _git(cfg, "diff", "--name-only", base, head).splitlines() if l)
    hits: list[str] = []
    for pat, lens in cfg.lenses:
        if any(fnmatch.fnmatch(f, pat) for f in files) and lens not in hits:
            hits.append(lens)
    lenses = tuple(hits) if hits else DEFAULT_LENSES
    return Scope(base=base, head=head, commits=commits, files=files, lenses=lenses)


def agent_rules(cfg: Config, scratch: str) -> str:
    """검증 에이전트 프롬프트마다 넣는 공통 규칙."""
    heavy = " · ".join(cfg.heavy_processes) if cfg.heavy_processes else "(설정 [verify].heavy_processes 가 비었다 — 메인이 돌리는 게이트 · 빌드 · 서버)"
    return (
        "규칙(반드시 지킨다):\n"
        f"- 저장소({cfg.root}) 파일을 고치지 않는다. git 은 읽기 전용(status · diff · log · show · grep · blame)만 쓴다.\n"
        f"- 무거운 프로세스를 띄우지 않는다: {heavy}. 메인 세션이 게이트와 빌드를 돌리고 있다.\n"
        "- 저장소의 시험 스크립트를 저장소 위치에서 돌리지 않는다(메인이 돌린다). 돌연변이 · 재현은 사본 트리에서 한다:\n"
        f"  `git -C {cfg.root} -c core.autocrlf=false archive <rev> | tar -x -C <폴더>/tree` (또는 `cld.py tree <rev> --out <폴더>/tree`).\n"
        f"- 파일은 {scratch} 아래 관점 폴더에만 쓴다.\n"
        "- 발견마다 심각도(🔴 운용 · 안전 · 데이터 손실 / 🟡 실제 결함이나 도달 조건이 좁다 / ⚪ 문서 · 표기 · 시험 빈틈),\n"
        "  파일:줄, 인용, 재현 출력 또는 도달 경로를 단다. 인수인계에 이미 적힌 한계는 발견이 아니다.\n"
        "- 반증 담당은 의심이 기본값이다. 재현되지 않으면 REFUTED, 근거는 맞지만 도달이 입증되지 않으면 PLAUSIBLE 이다.\n"
        "- 보고는 결론 먼저. 발견이 없으면 «없음» 과 무엇을 봤는지 적는다.\n"
    )


def render(sc: Scope, rules: str) -> str:
    out = [f"# 검증 범위 {sc.base}..{sc.head}", "", f"## 커밋 {len(sc.commits)}"]
    out += [f"- {c}" for c in sc.commits] or ["- (없음)"]
    out += ["", f"## 바뀐 파일 {len(sc.files)}"]
    out += [f"- {f}" for f in sc.files[:200]]
    if len(sc.files) > 200:
        out.append(f"- … 외 {len(sc.files) - 200}개(잘렸다)")
    out += ["", "## 제안 관점(에이전트 하나에 관점 하나 · 넷 ~ 여섯)"]
    out += [f"- {l}" for l in sc.lenses]
    out += ["", "## 에이전트 공통 규칙(프롬프트마다 넣는다)", "", "```text", rules.rstrip("\n"), "```", ""]
    return "\n".join(out)
