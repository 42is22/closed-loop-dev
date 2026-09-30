# -*- coding: utf-8 -*-
"""closed-loop-dev 하네스 라이브러리.

모듈 경계:
    config   — ``.cld/config.toml`` 찾기 · 읽기 · 기본값
    mdtext   — 마크다운 절 · 울타리 블록 추출(문서 형식의 SSOT 는 templates/)
    patch    — 정확한 자리 치환(줄 끝 보존 · 한 번만)
    prompt   — Phase 세션 프롬프트 조립 · 검사
    handover — 인수인계 항목 신설 · 네 칸 검사
    status   — 마스터 플랜 표 · 인수인계 최신 항목 요약
    gates    — 설정의 게이트 실행 · 요약
    tree     — 커밋을 깨끗한 트리로 풀기
    verify   — 검증 범위(커밋 · 바뀐 파일 · 관점 제안)
    hooks    — Claude Code 훅 진입점(세션 시작 · git 가드 · 멈출 때 알림)
    initcmd  — 대상 저장소에 틀 깔기
"""

__version__ = "0.1.0"
