# -*- coding: utf-8 -*-
"""커밋 하나를 깨끗한 트리로 푼다 — 독립 검증은 작업 트리가 아니라 커밋을 검증한다.

``git -c core.autocrlf=false archive <rev>`` 의 tar 를 파이썬 tarfile 로 푼다(줄 끝을 저장소 그대로 둔다 ·
tar 명령이 없어도 된다). 추적하지 않는 파일(데이터 · 캐시 · 키)은 들어가지 않는다 — 그것이 요점이다.
Windows 에서 경로가 길면(260자) 빌드 · 설치 도구가 엉뚱하게 실패한다. ``--subst X:`` 로 짧은 드라이브에 올린다.
"""
from __future__ import annotations

import io
import os
import subprocess
import tarfile


class TreeError(RuntimeError):
    """트리를 풀 수 없다."""


def extract(repo: str, rev: str, out_dir: str) -> str:
    """``rev`` 를 ``out_dir`` 에 푼다. out_dir 은 없거나 비어 있어야 한다. 풀린 커밋 해시를 돌려준다."""
    if os.path.exists(out_dir) and os.listdir(out_dir):
        raise TreeError(f"출력 폴더가 비어 있지 않다: {out_dir} — 새 폴더를 쓴다(지우지 않는다)")
    try:
        full = subprocess.run(["git", "-C", repo, "rev-parse", "--verify", f"{rev}^{{commit}}"], capture_output=True,
                              text=True, check=True, timeout=60).stdout.strip()
        data = subprocess.run(["git", "-C", repo, "-c", "core.autocrlf=false", "archive", "--format=tar", full],
                              capture_output=True, check=True, timeout=1800).stdout
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, bytes) else e.stderr
        raise TreeError(f"git 실패: rev={rev} error={(err or '').strip()[:200]}") from None
    except (OSError, subprocess.TimeoutExpired) as e:
        raise TreeError(f"git 을 부르지 못했다: {e}") from None
    os.makedirs(out_dir, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        try:
            tf.extractall(out_dir, filter="data")
        except TypeError:   # 3.11.4 전 — filter 인자가 없다(git archive 출력은 저장소 안 경로만 담는다)
            tf.extractall(out_dir)
    return full


def subst(letter: str, target: str) -> None:
    """Windows ``subst`` 로 짧은 드라이브를 매핑한다(검증이 끝나면 ``subst X: /d`` 로 푼다)."""
    if os.name != "nt":
        raise TreeError("subst 는 Windows 전용이다")
    letter = letter.rstrip(":\\/").upper()
    if len(letter) != 1 or not letter.isalpha():
        raise TreeError(f"드라이브 문자가 틀렸다: {letter!r}")
    if os.path.exists(f"{letter}:\\"):
        raise TreeError(f"{letter}: 가 이미 있다 — 다른 문자를 쓴다")
    r = subprocess.run(["subst", f"{letter}:", os.path.abspath(target)], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise TreeError(f"subst 실패: {r.stdout.strip()} {r.stderr.strip()}")
