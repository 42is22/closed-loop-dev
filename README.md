# closed-loop-dev

**Phase 단위 폐루프 개발 프로세스를 Claude Code 스킬 · 에이전트 · 훅 · 하네스로 재현하는 도구다.**
마스터 플랜에서 Phase 를 자르고, Phase 마다 독립 세션이 구현하고, 다른 독립 세션이 검증하고, 그 결과가 다시 마스터 플랜으로 돌아간다.
세션 사이의 기억은 문서 셋(마스터 플랜 · 세션 프롬프트 · 인수인계)에만 있다.

실제 제품 개발(2026-09)에서 굳은 절차를 프로젝트와 무관한 형태로 떼어 냈다.

## 루프 한 바퀴

```mermaid
flowchart LR
  A[마스터 플랜<br/>목표 · 완료 기준 · Phase 표] --> B[Phase 세션 프롬프트<br/>하네스가 조립]
  B --> C[구현 세션<br/>독립 세션 · 한 Phase]
  C --> D[인수인계 작성<br/>네 칸 · 맨 위]
  D --> E[독립 검증 세션<br/>깨끗한 트리 · 관점 에이전트]
  E --> F[인수인계 보강<br/>이월 목록 · 믿지 말 것]
  F --> A
```

| 단계 | 스킬 | 하네스 | 누가 |
|---|---|---|---|
| 틀 깔기 | `cld-init` | `cld.py init` | 한 번 |
| 계획 · Phase 나누기 | `cld-plan` | `cld.py status` | 계획 세션 |
| 세션 프롬프트 | `cld-prompt` | `cld.py prompt build <id>` | 검증 세션(다음 것을 만든다) |
| 구현 | `cld-implement` | `cld.py gates run` · `handover new` · `handover check` | 구현 세션 |
| 인수인계 | `cld-handover` | `cld.py handover new` · `check` | 구현 · 검증 세션 |
| 독립 검증 | `cld-verify` | `cld.py verify scope` · `tree` · `gates run` · `patch` | 검증 세션(구현과 다른 세션) |
| 루프 닫기 | `cld-close` | `cld.py prompt build`(조립 확인) | 검증 세션 |

에이전트 둘: `cld-reviewer`(관점 하나 · 읽기 전용 검토) · `cld-refuter`(반증 담당).
훅 셋: 세션 시작 때 상태 주입 · 에이전트의 git 쓰기 거부(가드레일) · 코드가 바뀌었는데 인수인계가 그대로면 멈출 때 알림.

## 왜 이렇게 하나 — 원칙 여섯

1. **세션은 기억을 물려받지 못한다.** 그래서 인수인계가 모든 세션 프롬프트의 «먼저 읽을 것» 1번이다.
2. **안 읽히는 문서는 없는 것보다 나쁘다.** 인수인계는 네 칸 고정(깨지기 쉬운 것 · 되돌리는 법 · 믿지 말 것 · 다음 사람에게)이고 항목 하나가 한 쪽을 넘지 않는다.
3. **검증은 구현과 다른 세션이 한다.** 구현 세션의 검토 워크플로가 놓친 결함을 독립 검증이 찾는다. 평문 게이트가 원리상 못 보는 경로(난독화 · 패키징 · 설치 · 외부 장비)는 산출물로 다시 시험한다.
4. **값 불변 주장은 흔든 입력으로 증명한다.** 기본값이 우연히 같아 가려지는 결함이 있다.
5. **프롬프트는 짧게, 모드는 근거와 먼저.** 🔴 울트라코드 · 🟡 검토 워크플로 한 번 · 🟢 MAX(기본). 머리는 열 줄 안쪽.
6. **결정은 사용자, 기록은 날짜와 함께.** 세션은 결정을 다시 묻지 않는다. Phase 를 늘리지 않는다 — 합치기부터 검토한다.

## 설치

### A. 플러그인(권장 — Claude Code CLI · Desktop)

```
claude plugin marketplace add 42is22/closed-loop-dev
claude plugin install closed-loop-dev@closed-loop-dev
```

클론해 둔 폴더를 쓰려면 `claude plugin marketplace add <클론 경로>` 다.

세션 안에서는 `/plugin marketplace add …` · `/plugin install closed-loop-dev@closed-loop-dev` 이고, 설치 뒤 `/reload-plugins` 또는 새 세션.
스킬은 `/closed-loop-dev:cld-plan` 처럼 부른다(설명이 맞으면 자동으로도 불린다).

그다음 대상 저장소 루트에서 스킬 `cld-init` 을 부르거나 직접:

```
python "<closed-loop-dev>/harness/cld.py" init --target . --name "<프로젝트>" --slug <ascii>
```

⚠ VS Code 확장에서 플러그인 스킬이 보이지 않으면 B(복사 설치)를 쓴다. 복사 설치는 스킬을 저장소의 `.claude/skills/` 에 둔다.

### B. 복사 설치(플러그인 없이 · Cursor)

```
python "<closed-loop-dev>/scripts/install.py" --target <저장소> --name "<프로젝트>" --slug <ascii> [--cursor] [--dry-run]
```

| 넣는 곳 | 무엇 |
|---|---|
| `.claude/skills/cld-*` · `.claude/agents/cld-*.md` | 스킬 · 에이전트(플러그인과 같은 파일) |
| `.claude/settings.json` | 훅 셋을 합친다(있는 설정 보존 · `.cldbak` 백업 · 다시 돌려도 한 번만) |
| `.cursor/rules/cld-*.mdc` | `--cursor` 일 때 — 규칙은 항상 적용, 스킬은 요청 시 |
| 나머지 | A 의 `init` 과 같다 |

### C. 기존 문서가 있는 저장소(도입)

이미 계획 · 세션 프롬프트 · 인수인계 문서가 있으면 새 문서를 만들지 않고 붙인다(병렬 문서를 만들지 않는다).

```
python "<closed-loop-dev>/scripts/install.py" --target <저장소> --name "<프로젝트>" --adopt \
    --master-plan <계획.md> --session-prompts <프롬프트.md> --handover <인수인계.md> \
    [--tasks-dir tasks] [--changelog CHANGELOG.md] [--plan-state-column 상태] [--rules process,verification]
```

- 규칙은 기존 규칙과 겹치지 않는 것만 고른다(예: git · 문체 규칙이 이미 있으면 `--rules process,verification`).
- 인수인계의 «쓰는 법» 절 뒤, 맨 위 항목 앞에 `<!-- cld:handover-insert -->` 한 줄을 넣는다(설치가 없으면 알린다). 그러면 `status` · `handover check` 가 된다.
- 계획 Phase 표의 상태가 «상태» 열이 아니면 `--plan-state-column` 으로 그 열 이름을 준다.
- 세션 프롬프트 문서는 공통 블록을 ```` ```cld-common ```` 으로, Phase 본문을 ```` ```cld-body ```` 로 옮긴 뒤부터 `prompt build` 가 된다. 옮기기 전에는 `status` 가 안내만 한다.

### 깔리는 것(A · B 공통 — C 는 문서 · tasks · CHANGELOG 를 빼고)

| 경로 | 무엇 |
|---|---|
| `docs/PLN-<slug>_master_plan-<날짜>.md` | 마스터 플랜 — 목표 · 완료 기준 · 하지 않는 것 · Phase 표 · 게이트 · 결정 · 리스크 |
| `docs/GDE-<slug>_phase_session_prompts-<날짜>.md` | 세션 프롬프트 — 공통 블록 · 다중 에이전트 블록 · Phase 절 |
| `docs/GDE-<slug>_phase_handover-<날짜>.md` | 인수인계 — 네 칸 · 최신이 위 |
| `tasks/README.md` · `tasks/TEMPLATE.md` | 과제 인덱스(자원 · 의존 대기표) · 과제 서식 |
| `.claude/rules/cld-*.md` | 규칙 — 프로세스 · git · 검증 · 문체(`--no-writing-rule` 로 뺀다) |
| `.cld/config.toml` | 문서 경로 · 게이트 · 가드 · 훅 · 검증 관점 |
| `.cld/harness/` | 하네스 사본 — 스킬 · 게이트가 설치 방식과 무관하게 같은 경로를 부른다 |
| `CHANGELOG.md` | 없을 때만 |

있는 파일은 덮지 않는다(`--force` 일 때만). 하네스만 새 판으로 올리려면 `cld.py init --upgrade-harness`.

## 하네스

Python 3.11+ 표준 라이브러리만 쓴다. 대상 저장소에서 `python .cld/harness/cld.py <명령>`.

| 명령 | 하는 일 |
|---|---|
| `status [--short]` | Phase 표(완료 · 다음) · 인수인계 맨 위 항목 · 다음 Phase 의 프롬프트 절 유무 |
| `prompt build <id> [--mode 🔴\|🟡\|🟢] [--out f]` | 머리 + 공통 블록 + Phase 블록(+ 🔴 · 🟡 면 다중 에이전트 블록). 머리 열 줄 초과 · 🟢/🟡 의 울트라코드 낱말 · 블록 누락을 막는다 |
| `handover new --phase <id> --title <t>` · `handover check [--phase id]` | 맨 위에 네 칸 틀 · 네 칸 유무 · 순서 · 빈 칸 · 자리표시 · 길이 |
| `gates list` · `gates run [--out d] [--only a,b]` | `[[gates]]` 를 group 순서로(같은 group 은 동시) · 로그 · `summary.txt` · 하나라도 실패면 exit 1 |
| `patch <spec.json> [--check]` | 정확한 자리 치환 — 자리는 정확히 N번 · 줄 끝(CRLF · LF) 보존 · 전부 또는 전무 |
| `tree <rev> --out d [--subst T:]` | 커밋을 깨끗한 트리로(`git archive` · 추적 파일만) · Windows 긴 경로면 짧은 드라이브 |
| `verify scope <base> <head> [--out f]` | 커밋 · 바뀐 파일 · 제안 관점 · 에이전트 공통 규칙 문장 |
| `hook session-start\|pre-bash\|stop` | 훅 진입점(stdin JSON). 설정이 없는 저장소에서는 아무것도 하지 않는다 |

`patch` 스펙:

```json
{"edits": [{"path": "docs/X.md", "old": "바꿀 자리(정확히)", "new": "새 글", "count": 1}]}
```

## 문서 형식의 약속

- 절은 `## <id>. <제목>` 이다. id 는 공백 · 마침표가 없는 토큰(`P1` · `7E` · `4M-C1`).
- 세션 프롬프트의 조각은 정보 문자열 붙은 울타리 블록이다: `cld-common`(하나) · `cld-multi`(하나) · Phase 절 안의 `cld-head`(선택) · `cld-body`. 모드는 Phase 절의 `권고 모드: 🔴|🟡|🟢` 한 줄이다.
- 인수인계 새 항목은 `<!-- cld:handover-insert -->` 표식 바로 아래(맨 위)에 들어간다.
- 마스터 플랜 Phase 표는 머리에 `Phase` 와 `상태` 열이 있는 첫 표다. 상태의 첫 낱말이 `완료` 면 끝난 행이다.

## 설정 `.cld/config.toml`

| 표 | 키 | 뜻 |
|---|---|---|
| `[docs]` | `master_plan` · `session_prompts` · `handover` · `tasks_dir` · `changelog` | 문서 경로(저장소 루트 기준) |
| `[plan]` | `state_column`(«상태») | Phase 표에서 상태를 읽는 열 |
| `[prompt]` | `header_max_lines`(10) · `ultracode_keyword` | 머리 상한 · 🔴 에만 들어가는 낱말 |
| `[handover]` | `max_section_lines`(80) | 항목 권고 상한(넘으면 경고) |
| `[guard]` | `git_write`(true) · `extra_deny`(정규식 목록) | PreToolUse 가드 |
| `[hooks]` | `session_start` · `stop_reminder` · `code_paths` | 훅 켜고 끄기 · «코드» 경로 |
| `[verify]` | `heavy_processes` · `[verify.lenses]`(glob = 관점) | 에이전트 금지 프로세스 · 관점 제안 |
| `[[gates]]` | `name` · `cmd`(인자 목록) · `group` · `expect`(정규식) · `timeout` · `cwd` · `env` | 게이트 |

## 한계 · 주의

- **git 가드는 실수 방지 가드레일이지 보안 경계가 아니다.** 명령 문자열을 토큰으로 볼 뿐이라 다른 셸 · 스크립트로 부르면 지나간다. 규칙(`cld-git.md`)이 우선이다.
- 훅은 `python` 을 부른다. PATH 에 Python 3.11+ 가 없으면 훅이 실패하고(막지 않는 오류) 가드가 열린다. Windows 에서 훅은 Git Bash 로 돈다.
- 하네스는 문서 형식의 약속에 기댄다. 형식을 바꾸면 `templates/` 와 `harness/cldlib/mdtext.py` 를 함께 고친다.
- 스킬 · 규칙은 한국어다.

## 라이선스

MIT — `LICENSE`.

## 개발

```
python -m unittest discover -s tests -v      # 하네스 시험
claude plugin validate .                     # 마켓플레이스 매니페스트
claude plugin validate .claude-plugin/plugin.json
```

구조: `.claude-plugin/`(매니페스트) · `skills/` · `agents/` · `hooks/` · `rules/`(init 이 복사) · `templates/`(init 이 복사) · `harness/`(`cld.py` + `cldlib/`) · `scripts/install.py` · `tests/`.
