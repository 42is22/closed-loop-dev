# 변경 이력 (Changelog)

형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 기반으로 한다.

## [Unreleased]

## [0.1.1] - 2026-09-30

기존 문서가 있는 저장소에 붙이는 «도입» 방식. 첫 적용 대상은 계획 · 세션 프롬프트 · 인수인계가 이미 있던 저장소다.

- **도입**: `cld.py init --adopt --master-plan … --session-prompts … --handover …` · `install.py --adopt …` — 문서 틀 · tasks · CHANGELOG 를 만들지 않고 설정이 기존 문서를 가리킨다. 인수인계에 삽입 표식이 없으면 알린다. 도입할 문서가 없으면 멈춘다.
- **규칙 고르기**: `--rules process,git,verification,writing`(기본 전부). 기존 규칙과 겹치는 것을 뺀다. Cursor 변환도 고른 것만.
- **계획 표 상태 열**: `[plan] state_column`(기본 «상태»). 상태가 «내용» 칸 머리에 있는 표도 읽는다.
- **status**: 세션 프롬프트 문서가 아직 cld 블록 형식이 아니면 안내(ℹ)만 한다(경고 아님).
- **Stop 알림**: 세션당 한 번(세션 id 표식 — 응답마다 뜨지 않는다).
- **규칙 머리**: 규칙 넷에 `description` · `alwaysApply: true` 머리(Cursor · 규칙 동기화 도구 호환 — Claude Code 는 무시). Cursor 변환이 그 머리를 쓴다.
- **시험**: 34.

## [0.1.0] - 2026-09-30

첫 판. 실제 제품 개발(2026-09)의 폐루프 절차를 프로젝트와 무관한 형태로 떼어 냈다.

- **플러그인**: `.claude-plugin/plugin.json` · 로컬 마켓플레이스 `marketplace.json`(`claude plugin validate` 통과).
- **스킬 일곱**: `cld-init` · `cld-plan` · `cld-prompt` · `cld-implement` · `cld-handover` · `cld-verify` · `cld-close`.
- **에이전트 둘**: `cld-reviewer`(관점 하나 · 읽기 전용) · `cld-refuter`(반증).
- **훅 셋**: SessionStart(상태 주입) · PreToolUse Bash(에이전트 git 쓰기 거부 — 가드레일) · Stop(인수인계 누락 알림 — 막지 않음). 설정 없는 저장소에서는 아무것도 하지 않는다.
- **규칙 넷**(`init` 이 대상 `.claude/rules/` 로): 프로세스 · git · 검증 · 문체.
- **문서 틀**: 마스터 플랜 · Phase 세션 프롬프트 · 인수인계 · tasks 인덱스 · 과제 서식 · CHANGELOG · 설정.
- **하네스** `harness/cld.py`(표준 라이브러리 · Python 3.11+): `init` · `status` · `prompt build` · `handover new|check` · `gates list|run` · `patch` · `tree` · `verify scope` · `hook`.
- **복사 설치** `scripts/install.py`: 스킬 · 에이전트를 `.claude/` 로 · 훅을 `settings.json` 에 합침(보존 · 백업 · 멱등) · `--cursor` 로 `.mdc`.
- **시험**: `tests/test_harness.py` 29(git 커밋이 없으면 1 건너뜀).
- **라이선스**: MIT.
