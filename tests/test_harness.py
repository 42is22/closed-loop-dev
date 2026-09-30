# -*- coding: utf-8 -*-
"""closed-loop-dev 하네스 시험 — 표준 라이브러리 unittest.

    python -m unittest discover -s tests -v
git 이 필요한 사례(tree · verify scope)는 이 저장소가 git 저장소이고 커밋이 있을 때만 돈다(아니면 skip).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))

from cldlib import config, handover, hooks, initcmd, mdtext, patch, prompt, status  # noqa: E402

CLD = os.path.join(ROOT, "harness", "cld.py")


def _run(args: list[str], cwd: str, stdin: str = "") -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, CLD, *args], cwd=cwd, input=stdin, capture_output=True, text=True,
                          encoding="utf-8", env=env, timeout=120)


class InitedRepo(unittest.TestCase):
    """init 을 돈 임시 저장소(각 시험마다 새로)."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="cld_test_")
        self.res = initcmd.run(self.tmp, "Demo 프로젝트", slug="demo", date="2026-09-30")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cfg(self) -> config.Config:
        return config.load(self.tmp)


class TestInit(InitedRepo):
    def test_files_and_no_overwrite(self):
        made = {d for d, w in self.res if w == "만듦"}
        for rel in ("docs/PLN-demo_master_plan-20260930.md", "docs/GDE-demo_phase_session_prompts-20260930.md",
                    "docs/GDE-demo_phase_handover-20260930.md", "tasks/README.md", ".cld/config.toml",
                    ".claude/rules/cld-process.md", ".claude/rules/cld-git.md", ".cld/harness"):
            self.assertIn(rel, made)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, ".cld", "harness", "cldlib", "prompt.py")))
        again = initcmd.run(self.tmp, "Demo 프로젝트", slug="demo", date="2026-09-30")
        self.assertTrue(all(w.startswith("건너뜀") for _, w in again), again)

    def test_placeholders_filled(self):
        for rel in ("docs/PLN-demo_master_plan-20260930.md", ".cld/config.toml", ".claude/rules/cld-process.md"):
            text = Path(os.path.join(self.tmp, rel)).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"\{\{[A-Z0-9_]+\}\}", rel)
        cfg = self.cfg()
        self.assertEqual(cfg.project, "Demo 프로젝트")
        self.assertTrue(os.path.isfile(cfg.path(cfg.handover)))

    def test_status_reads_template(self):
        st = status.collect(self.cfg())
        self.assertEqual([r.phase for r in st.rows], ["P1"])
        self.assertEqual(st.next_phase.phase, "P1")
        self.assertTrue(st.prompt_section)
        self.assertIsNone(st.handover_top)          # 항목 없음
        self.assertEqual(st.notes, ())


class TestPrompt(InitedRepo):
    def doc(self) -> str:
        cfg = self.cfg()
        return Path(cfg.path(cfg.session_prompts)).read_text(encoding="utf-8")

    def test_build_green(self):
        b = prompt.build(self.doc(), "P1", "Demo")
        self.assertEqual(b.mode, "🟢")
        self.assertEqual(b.parts, ("head", "common", "P1"))
        self.assertIn("■ 먼저 읽을 것", b.text)
        self.assertIn("P1 을 수행한다", b.text)
        self.assertNotIn("다중 에이전트 운용 —", b.text)
        self.assertLessEqual(b.head_lines, 10)

    def test_yellow_attaches_multi_red_adds_keyword(self):
        y = prompt.build(self.doc(), "P1", "Demo", mode="🟡")
        self.assertIn("multi", y.parts)
        self.assertNotIn("ultracode", y.text.lower())
        r = prompt.build(self.doc(), "P1", "Demo", mode="🔴")
        self.assertTrue(r.text.split("\n")[0].lower().startswith("ultracode"))

    def test_keyword_in_green_rejected(self):
        doc = self.doc().replace("P1 을 수행한다.", "P1 을 수행한다. ultracode", 1)
        with self.assertRaises(prompt.PromptError):
            prompt.build(doc, "P1", "Demo")

    def test_long_head_rejected(self):
        doc = self.doc().replace("```cld-head\n", "```cld-head\n" + "줄\n" * 12, 1)
        with self.assertRaises(prompt.PromptError):
            prompt.build(doc, "P1", "Demo")

    def test_missing_section(self):
        with self.assertRaises(prompt.PromptError):
            prompt.build(self.doc(), "P9", "Demo")

    def test_cli_build(self):
        out = os.path.join(self.tmp, "p.txt")
        r = _run(["prompt", "build", "P1", "--out", out], self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(Path(out).read_text(encoding="utf-8").startswith("🟢"))


class TestHandover(InitedRepo):
    def path(self) -> str:
        cfg = self.cfg()
        return cfg.path(cfg.handover)

    def test_new_then_check(self):
        text = Path(self.path()).read_text(encoding="utf-8")
        new = handover.new_entry(text, "P1", "첫 Phase", "2026-09-30")
        r = handover.check(new)
        self.assertFalse(r.ok)
        self.assertTrue(any("자리표시" in p for p in r.problems))
        filled = handover.PLACEHOLDER_RE.sub("없음", new)
        r2 = handover.check(filled)
        self.assertTrue(r2.ok, r2.problems)
        with self.assertRaises(handover.HandoverError):
            handover.new_entry(filled, "P1", "또", "2026-09-30")

    def test_missing_cell_and_empty(self):
        text = Path(self.path()).read_text(encoding="utf-8")
        filled = handover.PLACEHOLDER_RE.sub("없음", handover.new_entry(text, "P1", "첫", "2026-09-30"))
        no_cell = filled.replace("### 되돌리는 법\n\n없음\n", "")
        self.assertTrue(any("되돌리는 법" in p for p in handover.check(no_cell).problems))
        empty = filled.replace("### 되돌리는 법\n\n없음\n", "### 되돌리는 법\n\n")
        self.assertTrue(any("비었다" in p for p in handover.check(empty).problems))

    def test_cli_new_keeps_crlf(self):
        p = self.path()
        raw = Path(p).read_bytes().replace(b"\n", b"\r\n")
        Path(p).write_bytes(raw)
        r = _run(["handover", "new", "--phase", "P1", "--title", "첫"], self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        after = Path(p).read_bytes()
        self.assertEqual(after.count(b"\r\n"), after.count(b"\n"))
        self.assertEqual(_run(["handover", "check"], self.tmp).returncode, 1)   # 자리표시가 남았다


class TestPatch(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="cld_patch_")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def w(self, name: str, data: bytes) -> str:
        p = os.path.join(self.tmp, name)
        Path(p).write_bytes(data)
        return p

    def test_crlf_preserved_and_all_or_nothing(self):
        a = self.w("a.md", "하나\r\n둘\r\n".encode())
        b = self.w("b.md", "셋\n".encode())
        edits = [patch.Edit("a.md", "하나\n둘", "하나\n둘\n더"), patch.Edit("b.md", "없는 자리", "x")]
        with self.assertRaises(patch.PatchError):
            patch.apply(edits, self.tmp)
        self.assertEqual(Path(a).read_bytes(), "하나\r\n둘\r\n".encode())    # 아무것도 쓰지 않았다
        patch.apply(edits[:1], self.tmp)
        self.assertEqual(Path(a).read_bytes(), "하나\r\n둘\r\n더\r\n".encode())

    def test_count_and_check(self):
        self.w("c.md", b"x x\n")
        with self.assertRaises(patch.PatchError):
            patch.apply([patch.Edit("c.md", "x", "y")], self.tmp)
        patch.apply([patch.Edit("c.md", "x", "y", 2)], self.tmp, check_only=True)
        self.assertEqual(Path(os.path.join(self.tmp, "c.md")).read_bytes(), b"x x\n")

    def test_mixed_eol_refused(self):
        self.w("m.md", b"a\r\nb\n")
        with self.assertRaises(patch.PatchError):
            patch.apply([patch.Edit("m.md", "a", "z")], self.tmp)

    def test_spec_file(self):
        self.w("d.md", b"old\n")
        spec = self.w("s.json", json.dumps({"edits": [{"path": "d.md", "old": "old", "new": "new"}]}).encode())
        r = _run(["patch", spec, "--root-dir", self.tmp], self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(Path(os.path.join(self.tmp, "d.md")).read_bytes(), b"new\n")


class TestGitGuard(unittest.TestCase):
    DENY = ["git commit -m x", "git -C repo commit -F m.txt", "git -c core.x=1 push origin main", "cd a && git reset --hard",
            "echo hi; git checkout -- f", "git tag -a v1 -m x", "git tag v1", "git branch new", "git branch -D x",
            "git stash", "git clean -fdx", "/usr/bin/git merge x", "git switch main", "git restore f",
            "git remote add o url", "git config user.name x", "git pull"]
    ALLOW = ["git status", "git --no-pager diff", "git log --oneline -n 5", "git show HEAD", "git tag", "git tag -l",
             "git branch", "git branch -a", "git stash list", "git blame f", "git fetch", "git config --get user.name",
             "git archive HEAD", "echo git commit", "grep -n 'git commit' f", "git remote -v", "python -c 'x'"]

    def test_matrix(self):
        for c in self.DENY:
            self.assertIsNotNone(hooks.git_write_reason(c), c)
        for c in self.ALLOW:
            self.assertIsNone(hooks.git_write_reason(c), c)


class TestHooks(InitedRepo):
    def test_pre_bash_deny_and_allow(self):
        ev = {"cwd": self.tmp, "tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}
        r = _run(["hook", "pre-bash"], self.tmp, json.dumps(ev))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        ev["tool_input"]["command"] = "git status"
        r = _run(["hook", "pre-bash"], self.tmp, json.dumps(ev))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_no_config_is_silent(self):
        empty = tempfile.mkdtemp(prefix="cld_empty_")
        try:
            for which in ("pre-bash", "session-start", "stop"):
                r = _run(["hook", which], empty, json.dumps({"cwd": empty, "tool_input": {"command": "git commit"}}))
                self.assertEqual((r.returncode, r.stdout), (0, ""), which)
        finally:
            shutil.rmtree(empty, ignore_errors=True)

    def test_session_start_context(self):
        r = _run(["hook", "session-start"], self.tmp, json.dumps({"cwd": self.tmp}))
        self.assertEqual(r.returncode, 0, r.stderr)
        ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("다음: ① P1", ctx)

    def test_stop_reminds_only_when_handover_untouched(self):
        import contextlib
        import io
        cfg = self.cfg()
        ev = json.dumps({"cwd": self.tmp, "stop_hook_active": False})
        cases = [(["src/a.py"], True), (["src/a.py", cfg.handover], False), (["README.md"], False), ([], False)]
        orig = hooks._changed
        try:
            for changed, expect in cases:
                hooks._changed = lambda _cfg, c=changed: c
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    sys_stdin, sys.stdin = sys.stdin, io.StringIO(ev)
                    try:
                        self.assertEqual(hooks.stop(), 0)
                    finally:
                        sys.stdin = sys_stdin
                self.assertEqual("systemMessage" in buf.getvalue(), expect, changed)
            hooks._changed = lambda _cfg: ["src/a.py"]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                sys_stdin, sys.stdin = sys.stdin, io.StringIO(json.dumps({"cwd": self.tmp, "stop_hook_active": True}))
                try:
                    hooks.stop()
                finally:
                    sys.stdin = sys_stdin
            self.assertEqual(buf.getvalue(), "")          # 멈춤 훅이 이미 돈 뒤에는 조용하다(고리 방지)
        finally:
            hooks._changed = orig

    def test_bad_stdin_does_not_block(self):
        r = _run(["hook", "pre-bash"], self.tmp, "not json")
        self.assertEqual(r.returncode, 0)


class TestGates(InitedRepo):
    def test_run_groups_expect_and_fail(self):
        cfgp = os.path.join(self.tmp, ".cld", "config.toml")
        py = sys.executable.replace("\\", "/")
        with open(cfgp, "a", encoding="utf-8") as f:
            f.write(f'\n[[gates]]\nname = "ok"\ncmd = ["{py}", "-c", "print(\'결과: 3/3 PASS\')"]\ngroup = 1\nexpect = "PASS"\n'
                    f'\n[[gates]]\nname = "noexpect"\ncmd = ["{py}", "-c", "print(1)"]\ngroup = 1\nexpect = "PASS"\n'
                    f'\n[[gates]]\nname = "bad"\ncmd = ["{py}", "-c", "import sys; sys.exit(3)"]\ngroup = 2\n')
        from cldlib import gates
        out = os.path.join(self.tmp, "g")
        res = {r.name: r for r in gates.run(self.cfg(), out)}
        self.assertTrue(res["ok"].ok)
        self.assertFalse(res["noexpect"].ok)
        self.assertEqual((res["bad"].ok, res["bad"].exit), (False, 3))
        self.assertIn("pass=1/3", Path(os.path.join(out, "summary.txt")).read_text(encoding="utf-8"))

    def test_cmd_must_be_list(self):
        cfgp = os.path.join(self.tmp, ".cld", "config.toml")
        with open(cfgp, "a", encoding="utf-8") as f:
            f.write('\n[[gates]]\nname = "s"\ncmd = "echo hi"\n')
        with self.assertRaises(config.ConfigError):
            self.cfg()


class TestAdopt(unittest.TestCase):
    """기존 문서가 있는 저장소에 붙는다 — 문서를 만들지 않고 설정이 기존 문서를 가리킨다."""

    PLAN = ("# 계획\n\n| 순번 | Phase | 내용 | 특이 검증 |\n|---|---|---|---|\n"
            "| ① | **0** | 🟢 **완료(2026-09-21)** — 기준선 | x |\n"
            "| ② | **7** | 🟢 **T-87 완료(abc)** · 다음 = 7E | y |\n"
            "| ③ | **8** | 문서 정리 | z |\n")
    HANDOVER = ("# 인수인계\n\n## 1. 쓰는 법\n\n네 칸.\n\n"
                "## 2. Phase 7E — 편집 (완료)\n\n### 깨지기 쉬운 것\n\n없음\n\n### 되돌리는 법\n\n없음\n\n"
                "### 🔴 믿지 말 것\n\n없음\n\n### 🔴 다음 사람에게 (7-4 C4)\n\n하나.\n")

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="cld_adopt_")
        os.makedirs(os.path.join(self.tmp, "docs"))
        Path(self.tmp, "docs", "PLN-x.md").write_text(self.PLAN, encoding="utf-8")
        Path(self.tmp, "docs", "GDE-p.md").write_text("# 프롬프트\n\n## 11. Phase 7\n\n```\n옛 블록\n```\n", encoding="utf-8")
        Path(self.tmp, "docs", "GDE-h.md").write_text(self.HANDOVER, encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def adopt(self) -> initcmd.Adopt:
        return initcmd.Adopt("docs/PLN-x.md", "docs/GDE-p.md", "docs/GDE-h.md", state_column="내용")

    def test_no_docs_and_rules_chosen(self):
        res = initcmd.run(self.tmp, "X", adopt=self.adopt(), rules=["process", "verification"])
        made = {d for d, w in res if w == "만듦"}
        self.assertEqual(made, {".cld/config.toml", ".claude/rules/cld-process.md", ".claude/rules/cld-verification.md", ".cld/harness"})
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "tasks")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "CHANGELOG.md")))
        self.assertTrue(any(w.startswith("⚠ 표식 없음") for _, w in res))
        rule = Path(self.tmp, ".claude", "rules", "cld-process.md").read_text(encoding="utf-8")
        self.assertIn("docs/GDE-h.md", rule)
        cfg = config.load(self.tmp)
        self.assertEqual((cfg.master_plan, cfg.handover, cfg.plan_state_column), ("docs/PLN-x.md", "docs/GDE-h.md", "내용"))

    def test_missing_doc_and_bad_rule(self):
        with self.assertRaises(FileNotFoundError):
            initcmd.run(self.tmp, "X", adopt=initcmd.Adopt("docs/none.md", "docs/GDE-p.md", "docs/GDE-h.md"))
        with self.assertRaises(ValueError):
            initcmd.run(self.tmp, "X", adopt=self.adopt(), rules=["nope"])

    def test_status_on_legacy_docs(self):
        initcmd.run(self.tmp, "X", adopt=self.adopt(), rules=["process"])
        h = Path(self.tmp, "docs", "GDE-h.md")
        h.write_text(self.HANDOVER.replace("## 2. Phase 7E", handover.MARKER + "\n\n## 2. Phase 7E"), encoding="utf-8")
        st = status.collect(config.load(self.tmp))
        self.assertEqual([r.done for r in st.rows], [True, False, False])     # «T-87 완료» 는 Phase 7 의 완료가 아니다
        self.assertEqual(st.next_phase.phase, "7")
        self.assertEqual(st.handover_top, "2. Phase 7E — 편집 (완료)")
        self.assertTrue(st.handover_ok)
        self.assertIsNone(st.prompt_section)
        self.assertTrue(any("cld 블록 형식이 아니다" in i for i in st.infos))
        self.assertEqual(st.notes, ())

    def test_cli_adopt_requires_paths(self):
        r = _run(["init", "--target", self.tmp, "--adopt"], self.tmp)
        self.assertEqual(r.returncode, 2)


class TestStopOnce(InitedRepo):
    def test_once_per_session(self):
        import contextlib
        import io
        sid = f"t{os.getpid()}x{id(self)}"
        mark = hooks._once_marker({"session_id": sid})
        if mark and os.path.exists(mark):
            os.remove(mark)
        orig = hooks._changed
        outs = []
        try:
            hooks._changed = lambda _cfg: ["src/a.py"]
            for _ in range(2):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    old, sys.stdin = sys.stdin, io.StringIO(json.dumps({"cwd": self.tmp, "session_id": sid}))
                    try:
                        hooks.stop()
                    finally:
                        sys.stdin = old
                outs.append(buf.getvalue())
        finally:
            hooks._changed = orig
            if mark and os.path.exists(mark):
                os.remove(mark)
        self.assertIn("systemMessage", outs[0])
        self.assertEqual(outs[1], "")


class TestMdText(unittest.TestCase):
    def test_fences_hide_headings(self):
        doc = "## A. 하나\n```text\n## B. 가짜\n```\n## C. 둘\n"
        self.assertEqual([s.id for s in mdtext.sections(doc)], ["A", "C"])

    def test_unclosed_fence(self):
        with self.assertRaises(mdtext.DocError):
            mdtext.fenced_blocks(["```cld-body", "x"])


def _has_git_head() -> bool:
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "--verify", "HEAD"], capture_output=True, timeout=20).returncode == 0
    except OSError:
        return False


@unittest.skipUnless(_has_git_head(), "이 저장소에 git 커밋이 없다")
class TestTree(unittest.TestCase):
    def test_extract_head(self):
        from cldlib import tree
        out = tempfile.mkdtemp(prefix="cld_tree_")
        try:
            full = tree.extract(ROOT, "HEAD", os.path.join(out, "t"))
            self.assertEqual(len(full), 40)
            self.assertTrue(os.path.isfile(os.path.join(out, "t", "harness", "cld.py")))
            with self.assertRaises(tree.TreeError):
                tree.extract(ROOT, "HEAD", os.path.join(out, "t"))   # 비어 있지 않은 폴더
        finally:
            shutil.rmtree(out, ignore_errors=True)


class TestInstall(unittest.TestCase):
    def test_copy_install(self):
        tmp = tempfile.mkdtemp(prefix="cld_install_")
        try:
            settings = os.path.join(tmp, ".claude", "settings.json")
            os.makedirs(os.path.dirname(settings))
            Path(settings).write_text(json.dumps({"permissions": {"deny": ["Bash(git push:*)"]}}), encoding="utf-8")
            r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "install.py"), "--target", tmp, "--name", "X",
                                "--slug", "x", "--date", "2026-09-30", "--cursor"], capture_output=True, text=True,
                               encoding="utf-8", timeout=120, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.isfile(os.path.join(tmp, ".claude", "skills", "cld-verify", "SKILL.md")))
            self.assertTrue(os.path.isfile(os.path.join(tmp, ".claude", "agents", "cld-reviewer.md")))
            self.assertTrue(os.path.isfile(os.path.join(tmp, ".cursor", "rules", "cld-process.mdc")))
            mdc = Path(os.path.join(tmp, ".cursor", "rules", "cld-process.mdc")).read_text(encoding="utf-8")
            self.assertEqual(mdc.count("\n---\n"), 1)                      # 머리가 두 번 들어가지 않는다
            self.assertIn("alwaysApply: true", mdc)
            s = json.loads(Path(settings).read_text(encoding="utf-8"))
            self.assertEqual(s["permissions"]["deny"], ["Bash(git push:*)"])       # 있던 설정 보존
            cmds = json.dumps(s["hooks"], ensure_ascii=False)
            self.assertIn("$CLAUDE_PROJECT_DIR/.cld/harness/cld.py", cmds)
            self.assertNotIn("CLAUDE_PLUGIN_ROOT", cmds)
            r2 = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "install.py"), "--target", tmp, "--name", "X"],
                                capture_output=True, text=True, encoding="utf-8", timeout=120,
                                env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            self.assertIn("훅 이미 있음", r2.stdout)
            self.assertEqual(len(json.loads(Path(settings).read_text(encoding="utf-8"))["hooks"]["PreToolUse"]), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestManifests(unittest.TestCase):
    def test_json_and_skill_frontmatter(self):
        for rel in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "hooks/hooks.json"):
            json.loads(Path(os.path.join(ROOT, rel)).read_text(encoding="utf-8"))
        for d in os.listdir(os.path.join(ROOT, "skills")):
            text = Path(os.path.join(ROOT, "skills", d, "SKILL.md")).read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), d)
            head = text.split("\n---\n", 1)[0]
            self.assertIn(f"name: {d}", head)
            self.assertIn("description:", head)
        for f in os.listdir(os.path.join(ROOT, "rules")):
            head = Path(os.path.join(ROOT, "rules", f)).read_text(encoding="utf-8").split("\n---\n", 1)[0]
            self.assertTrue(head.startswith("---\ndescription: ") and "alwaysApply: true" in head, f)   # Cursor · 규칙 동기화 도구 호환
        for f in os.listdir(os.path.join(ROOT, "agents")):
            head = Path(os.path.join(ROOT, "agents", f)).read_text(encoding="utf-8").split("\n---\n", 1)[0]
            self.assertIn("description:", head)
            self.assertNotIn("Write", head.split("tools:", 1)[1].split("\n", 1)[0])   # 읽기 전용


if __name__ == "__main__":
    unittest.main()
