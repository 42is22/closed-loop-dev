# -*- coding: utf-8 -*-
"""설정의 게이트를 돌린다 — 같은 group 은 동시에, group 은 오름차순으로.

판정: exit 0 이고(``expect`` 가 있으면) 출력에 그 정규식이 있어야 통과다. 시간 초과는 실패다.
출력: ``<out>/<name>.log`` (stdout+stderr) · ``<out>/summary.txt`` (한 줄씩 — 이름 · 판정 · exit · 초 · 마지막 판정 줄).
게이트 명령은 인자 목록으로 부른다(셸을 거치지 않는다).
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

from .config import Config, Gate

VERDICT_HINT = re.compile(r"(통과|PASS|OK|FAIL|실패|불일치|일치|error|passed|failed)", re.IGNORECASE)


@dataclass(frozen=True)
class GateResult:
    name: str
    ok: bool
    exit: Optional[int]
    seconds: float
    note: str


def _run_one(cfg: Config, g: Gate, out_dir: str) -> GateResult:
    log = os.path.join(out_dir, f"{g.name}.log")
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.update(dict(g.env))
    cwd = cfg.path(g.cwd)
    t0 = time.monotonic()
    try:
        with open(log, "wb") as f:
            p = subprocess.run(list(g.cmd), cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=g.timeout)
        code: Optional[int] = p.returncode
        timed_out = False
    except subprocess.TimeoutExpired:
        code, timed_out = None, True
    except OSError as e:
        with open(log, "ab") as f:
            f.write(f"\n[cld] 실행 실패: {e}\n".encode("utf-8"))
        return GateResult(g.name, False, None, time.monotonic() - t0, f"실행 실패: {e}")
    dt = time.monotonic() - t0
    text = Path(log).read_bytes().replace(b"\x00", b"").decode("utf-8", errors="replace")
    hint = next((l.strip() for l in reversed(text.splitlines()) if VERDICT_HINT.search(l)), "")
    if timed_out:
        return GateResult(g.name, False, None, dt, f"시간 초과 {g.timeout}s")
    ok = code == 0
    note = hint[:160]
    if ok and g.expect and not re.search(g.expect, text):
        ok = False
        note = f"기대 문구 없음 expect={g.expect!r}"
    return GateResult(g.name, ok, code, dt, note)


def run(cfg: Config, out_dir: str, only: Optional[list[str]] = None) -> list[GateResult]:
    """게이트를 돌려 결과 목록을 돌려준다. ``only`` 가 있으면 그 이름만."""
    gates = [g for g in cfg.gates if not only or g.name in only]
    if only:
        missing = sorted(set(only) - {g.name for g in cfg.gates})
        if missing:
            raise ValueError(f"설정에 없는 게이트: {missing}")
    if not gates:
        raise ValueError("돌릴 게이트가 없다 — .cld/config.toml 의 [[gates]] 를 채운다")
    os.makedirs(out_dir, exist_ok=True)
    summary = os.path.join(out_dir, "summary.txt")
    results: list[GateResult] = []
    with open(summary, "w", encoding="utf-8") as s:
        s.write(f"start {time.strftime('%Y-%m-%d %H:%M:%S')} root={cfg.root}\n")
    for grp in sorted({g.group for g in gates}):
        batch = [g for g in gates if g.group == grp]
        with ThreadPoolExecutor(max_workers=len(batch)) as ex:
            res = list(ex.map(lambda g: _run_one(cfg, g, out_dir), batch))
        results += res
        with open(summary, "a", encoding="utf-8") as s:
            for r in res:
                s.write(f"[{'PASS' if r.ok else 'FAIL'}] group={grp} {r.name} exit={r.exit} {r.seconds:.0f}s :: {r.note}\n")
    with open(summary, "a", encoding="utf-8") as s:
        s.write(f"done {time.strftime('%H:%M:%S')} pass={sum(r.ok for r in results)}/{len(results)}\n")
    return results
