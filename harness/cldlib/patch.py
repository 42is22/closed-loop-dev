# -*- coding: utf-8 -*-
"""정확한 자리 치환 — 문서 기록(인수인계 · CHANGELOG · 계획 행)을 안전하게 고친다.

규칙:
    - 바꿀 자리(``old``)는 파일에 정확히 ``count`` 번(기본 1) 나와야 한다. 아니면 아무 파일도 쓰지 않는다.
    - 파일의 줄 끝(CRLF · LF)을 보존한다. 스펙의 문자열은 ``\\n`` 으로 쓴다.
    - ``--check`` 는 자리만 대 보고 쓰지 않는다. 모든 파일의 자리가 맞을 때만 쓴다(전부 또는 전무).

스펙(JSON):
    {"edits": [{"path": "docs/X.md", "old": "…", "new": "…", "count": 1}, …]}
경로는 스펙 파일이 아니라 ``--root``(기본 저장소 루트 또는 현재 폴더) 기준이다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from dataclasses import dataclass


class PatchError(ValueError):
    """스펙이 틀렸거나 자리가 맞지 않는다."""


@dataclass(frozen=True)
class Edit:
    path: str
    old: str
    new: str
    count: int = 1


def load_spec(spec_path: str) -> list[Edit]:
    try:
        with open(spec_path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise PatchError(f"스펙을 읽지 못했다: path={spec_path} error={e}") from None
    raw = d.get("edits") if isinstance(d, dict) else d
    if not isinstance(raw, list) or not raw:
        raise PatchError(f"스펙에 edits 목록이 없다: path={spec_path}")
    out: list[Edit] = []
    for i, e in enumerate(raw, 1):
        if not isinstance(e, dict) or not all(isinstance(e.get(k), str) for k in ("path", "old", "new")):
            raise PatchError(f"edits[{i}] 에 문자열 path · old · new 가 있어야 한다")
        if not e["old"]:
            raise PatchError(f"edits[{i}] old 가 비었다: path={e['path']}")
        cnt = e.get("count", 1)
        if not isinstance(cnt, int) or cnt < 1:
            raise PatchError(f"edits[{i}] count 는 1 이상 정수: path={e['path']} count={cnt!r}")
        out.append(Edit(e["path"], e["old"], e["new"], cnt))
    return out


def _is_crlf(raw: bytes) -> bool:
    n = raw.count(b"\n")
    return n > 0 and raw.count(b"\r\n") == n


def apply(edits: list[Edit], root: str, check_only: bool = False) -> list[str]:
    """편집을 적용한다. 돌려주는 값은 파일별 보고 줄. 자리가 하나라도 틀리면 PatchError(아무것도 쓰지 않는다)."""
    by_file: dict[str, list[Edit]] = {}
    for e in edits:
        by_file.setdefault(e.path, []).append(e)
    staged: list[tuple[str, bytes, str]] = []
    problems: list[str] = []
    for rel, es in by_file.items():
        path = os.path.join(root, rel)
        try:
            raw = Path(path).read_bytes()
        except OSError as err:
            problems.append(f"[{rel}] 읽지 못했다: {err}")
            continue
        crlf = _is_crlf(raw)
        if not crlf and b"\r\n" in raw:
            problems.append(f"[{rel}] 줄 끝이 섞였다(CRLF · LF) — 보존할 형식을 정할 수 없다")
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as err:
            problems.append(f"[{rel}] UTF-8 이 아니다: {err}")
            continue
        bom = text.startswith("﻿")
        if crlf:
            text = text.replace("\r\n", "\n")
        for e in es:
            n = text.count(e.old)
            if n != e.count:
                problems.append(f"[{rel}] 자리 {n}번(기대 {e.count}): {e.old[:80]!r}")
                continue
            text = text.replace(e.old, e.new)
        if crlf:
            text = text.replace("\n", "\r\n")
        if bom and not text.startswith("﻿"):
            problems.append(f"[{rel}] 치환이 BOM 을 지웠다")
        staged.append((path, text.encode("utf-8"), f"{rel} ({len(es)}곳 · {'CRLF' if crlf else 'LF'})"))
    if problems:
        raise PatchError("자리가 맞지 않아 아무 파일도 쓰지 않았다:\n  " + "\n  ".join(problems))
    if not check_only:
        for path, data, _ in staged:
            tmp = path + ".cldtmp"
            with open(tmp, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
    return [s for _, _, s in staged]
