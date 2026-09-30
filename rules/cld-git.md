# git 정책 (closed-loop-dev)

## 에이전트가 하지 않는 것

- **git commit · push · tag 만들기를 실행하지 않는다.** 사용자가 요청해도 실행하지 않고 명령을 준다.
- 작업 트리 · 이력을 바꾸는 명령도 실행하지 않는다 — `reset` · `clean` · `restore` · `checkout` · `switch` · `stash` · `rebase` · `merge` · `cherry-pick` · `revert` · `pull` · `branch` 만들기 · 지우기.
  특히 `git clean -fdx` 는 `.gitignore` 된 산출물 · 데이터까지 지운다(git 으로 복구 불가).
- 에이전트가 하는 것은 여기까지다: 변경 파일 목록 · `git status` / `git --no-pager diff` 요약 · **Conventional Commits 커밋 메시지 초안**(파일로 쓰고 경로를 준다) · 실행할 명령.
  명령 예: `git add -u; git add <새 파일>; git commit -F "<메시지 파일>"`.
- **읽기 전용 git 은 자유롭게 쓴다** — `status` · `diff` · `log` · `show` · `blame` · `reflog` · `branch`(목록) · `tag`(목록) · `fetch` · `archive`(검증용 깨끗한 트리).

## 가드레일의 성격

- 훅(`closed-loop-dev` PreToolUse 가드)과 `permissions.deny` 는 **실수 방지 가드레일이지 보안 경계가 아니다.** 명령 문자열만 본다 — 다른 셸 · 스크립트로 부르면 지나간다.
- 따라서 가드에 걸리지 않았다고 해도 되는 것이 아니다. 이 규칙이 우선이다.

## 커밋 메시지

- 형식: `<type>(<scope>): <subject>` — type ∈ feat · fix · docs · refactor · perf · test · chore · ci.
- 본문에는 무엇이 바뀌었나 · 게이트 결과 한 줄 · 외부 인지 필요 여부를 적는다. 끝에 협업 표기가 규약이면 따른다.

## 버전

- 버전 · CHANGELOG · 태그는 한 묶음이다. 버전을 끊을 때 에이전트는 태그 명령(`git tag -a vX.Y.Z -m "…"`)을 커밋 명령 옆에 함께 제시한다. 태그는 사용자가 단다.
- 개발 기간에 버전을 고정하는지(예: `X.Y.Z-dev`)는 마스터 플랜 §4 결정 기록을 따른다.
