---
name: cld-init
description: 저장소에 폐루프 개발 틀(마스터 플랜 · Phase 세션 프롬프트 · 인수인계 · tasks · 규칙 · 하네스 · 설정)을 깐다. 사용자가 이 프로세스를 새 프로젝트에 도입하자고 할 때 쓴다.
argument-hint: "[프로젝트 이름]"
---

# 폐루프 틀 깔기

대상 저장소 루트에서 한다. 있는 파일은 덮지 않는다.

## 1. 먼저 확인할 것

- 저장소 루트인가(`git rev-parse --show-toplevel`). 아니면 사용자에게 루트를 묻는다.
- 이미 깔렸는가(`.cld/config.toml` 이 있는가). 있으면 새로 깔지 않는다 — 하네스만 갱신하려면 `--upgrade-harness`.
- 프로젝트 이름(문서 머리에 들어간다)과 파일 이름용 ASCII 이름(`--slug`). 인자로 받지 못했으면 한 번 묻는다.
- 문체 규칙(`cld-writing.md`)을 깔지. 사용자 전역 규칙에 이미 문체 규칙이 있으면 `--no-writing-rule`.

## 2. 깔기

하네스 위치는 설치 방식에 따라 다르다.

| 설치 | 명령 |
|---|---|
| 플러그인 | `python "${CLAUDE_PLUGIN_ROOT}/harness/cld.py" init --target . --name "<이름>" --slug <ascii>` |
| 복사 설치(`scripts/install.py`) | 이미 `.cld/harness/` 가 있다 → `python .cld/harness/cld.py init --target . --name "<이름>" --slug <ascii>` |

먼저 `--dry-run` 으로 무엇을 만들지 보여 주고, 사용자가 괜찮다고 하면 실제로 돈다. 출력 표(만듦 · 건너뜀)를 그대로 보고한다.

깔리는 것:

| 경로 | 무엇 |
|---|---|
| `docs/PLN-<slug>_master_plan-<날짜>.md` | 마스터 플랜(목표 · 완료 기준 · Phase 표 · 결정) |
| `docs/GDE-<slug>_phase_session_prompts-<날짜>.md` | Phase 세션 프롬프트(공통 블록 · 다중 에이전트 블록 · Phase 절) |
| `docs/GDE-<slug>_phase_handover-<날짜>.md` | 인수인계(네 칸 · 최신이 위) |
| `tasks/README.md` · `tasks/TEMPLATE.md` | 과제 인덱스 · 과제 서식 |
| `.claude/rules/cld-*.md` | 프로세스 · git · 검증 · (문체) 규칙 |
| `.cld/config.toml` | 문서 경로 · 게이트 · 가드 · 훅 설정 |
| `.cld/harness/` | 하네스 사본(스킬 · 게이트가 부른다) |
| `CHANGELOG.md` | 없을 때만 |

## 3. 깐 뒤

1. `.cld/config.toml` 의 `[[gates]]` 를 이 저장소의 게이트로 채운다(컴파일 · 시험 · 린트 · 회귀). 사용자에게 무엇을 게이트로 삼을지 묻고, 명령은 인자 목록으로 적는다. `python .cld/harness/cld.py gates list` 로 확인한다.
2. `[hooks].code_paths` 를 이 저장소의 코드 폴더로, `[verify].heavy_processes` 를 에이전트가 띄우면 안 되는 것으로 채운다.
3. `.gitignore` 에 넣을 것은 없다(설정 · 하네스는 추적한다). 검증 스크래치는 저장소 밖에 둔다.
4. `python .cld/harness/cld.py status` 로 상태를 보여 준다.
5. 다음은 마스터 플랜을 채우는 일이다 — 스킬 `cld-plan`.
6. 커밋은 사용자가 한다. 새 파일 목록과 명령(`git add docs tasks .claude/rules .cld CHANGELOG.md; git commit -F <메시지 파일>`)과 메시지 초안을 준다.
