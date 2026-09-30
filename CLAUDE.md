# CLAUDE.md — closed-loop-dev

이 저장소는 폐루프 개발 프로세스를 담은 Claude Code 플러그인이다(README.md). 이 저장소 자체를 고칠 때의 규약이다.

## 구조

- `.claude-plugin/` — `plugin.json` · `marketplace.json`(플러그인 하나 · source `./`)
- `skills/<이름>/SKILL.md` · `agents/*.md` · `hooks/hooks.json` — 플러그인 구성 요소(복사 설치도 같은 파일을 쓴다)
- `rules/` · `templates/` — `cld.py init` 이 대상 저장소로 복사한다. 자리표시는 `{{PROJECT}}` · `{{DATE}}` · `{{MASTER_PLAN}}` · `{{SESSION_PROMPTS}}` · `{{HANDOVER}}` · `{{TASKS_DIR}}` · `{{CHANGELOG}}`
- `harness/cld.py` + `harness/cldlib/` — 표준 라이브러리만(Python 3.11+). 대상 저장소에는 `.cld/harness/` 사본으로 간다
- `scripts/install.py` — 복사 설치 · `tests/test_harness.py` — 시험

## 고칠 때

- 문서 형식(절 `## <id>.` · 블록 `cld-common` · `cld-multi` · `cld-head` · `cld-body` · 표식 `<!-- cld:handover-insert -->` · Phase 표 `Phase` · `상태` 열)을 바꾸면 `templates/` · `harness/cldlib/` · 스킬 · README 를 같은 변경에서 고친다.
- 하네스는 셸을 거치지 않는다(`subprocess` 는 인자 목록). 게이트 `cmd` 도 목록이다.
- 훅은 세션을 막지 않는다 — 예외는 exit 0 으로 삼킨다. 설정이 없으면 출력도 없다.
- 🟢 · 🟡 프롬프트에 울트라코드 영문 낱말이 들어가면 모드가 켜진다. 틀 · 스킬 본문에서 그 낱말을 쓰지 않는다(README · 하네스 기본값만).
- 스킬 · 규칙 · 틀은 한국어다. 식별자 · 명령 · 경로만 영문.

## 게이트

```
python -m unittest discover -s tests -v
claude plugin validate .
claude plugin validate .claude-plugin/plugin.json
```

버전은 `VERSION` · `CHANGELOG.md` · `.claude-plugin/plugin.json` · `marketplace.json` 의 version 을 함께 올린다. 커밋 · 태그는 사용자가 한다.
