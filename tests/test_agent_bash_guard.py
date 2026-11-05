"""agent_bash_guard.py 的行為測試：三個 profile 各測「擋」與「放」，加 Harness config 的讀取。

跑法：python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

HOOKS_DIR = pathlib.Path(__file__).resolve().parent.parent / "hooks"
HOOK = HOOKS_DIR / "agent_bash_guard.py"
sys.path.insert(0, str(HOOKS_DIR))
from agent_bash_guard import decide  # noqa: E402

CWD = "/work/booking-app"  # 不存在的目錄 → 沒有 CLAUDE.md → 全用預設（./run test、PYTEST_DB_BASE）
SCR = "/tmp/claude-1000/-work-booking-app/abc/scratchpad"


def bash(agent: str, cmd: str, cwd: str = CWD) -> str | None:
    return decide({"agent_type": agent, "tool_name": "Bash", "cwd": cwd, "tool_input": {"command": cmd}})


def write(agent: str, path: str, tool: str = "Write") -> str | None:
    return decide({"agent_type": agent, "tool_name": tool, "cwd": CWD, "tool_input": {"file_path": path}})


class NotGuarded(unittest.TestCase):
    def test_main_agent_without_agent_type_is_untouched(self):
        self.assertIsNone(decide({"tool_name": "Bash", "cwd": CWD, "tool_input": {"command": "sed -i s/a/b/ app/x.py"}}))

    def test_unknown_agent_is_untouched(self):
        self.assertIsNone(bash("mutation-prover", "python3 - <<'EOF'\nprint(1)\nEOF"))

    def test_unknown_agent_write_is_untouched(self):
        self.assertIsNone(write("some-new-agent", "app/x.py"))


class Reader(unittest.TestCase):
    A = "spec-gap-hunter"

    def test_read_only_pipeline_allowed(self):
        self.assertIsNone(bash(self.A, "grep -rn 'def test_' tests/bookings | head -50 | sort"))

    def test_sed_n_allowed_sed_i_denied(self):
        self.assertIsNone(bash(self.A, "sed -n 120,140p app/bookings/service.py"))
        self.assertIn("sed -i", bash(self.A, "sed -i 's/a/b/' app/bookings/service.py"))

    def test_git_readonly_allowed_git_write_denied(self):
        self.assertIsNone(bash(self.A, "git log --oneline -5 && git show HEAD --stat && git diff origin/main..HEAD -- app"))
        self.assertIn("git commit", bash(self.A, "git commit -m x"))
        self.assertIn("git checkout", bash(self.A, "git checkout -- app/x.py"))
        self.assertIn("git add", bash(self.A, "git add ."))

    def test_git_worktree_list_allowed_add_denied(self):
        self.assertIsNone(bash(self.A, "git worktree list"))
        self.assertIsNotNone(bash(self.A, "git worktree add ../x"))

    def test_redirect_to_repo_denied_to_scratch_allowed(self):
        self.assertIn("重導", bash(self.A, "echo hi > app/x.py"))
        self.assertIn("重導", bash(self.A, "cat a >> features/BACKLOG.md"))
        self.assertIsNone(bash(self.A, f"grep -rn foo app > {SCR}/hits.txt"))
        self.assertIsNone(bash(self.A, "ls > /dev/null"))

    def test_fd_dup_is_not_a_redirect(self):
        self.assertIsNone(bash(self.A, "git log -1 2>&1 | head"))

    def test_heredoc_body_is_not_parsed_as_commands(self):
        self.assertIsNone(bash(self.A, f"cat > {SCR}/probe.txt <<'EOF'\nrm -rf app\ngit push --force\nEOF"))

    def test_heredoc_to_repo_denied(self):
        self.assertIn("重導", bash(self.A, "cat > tests/x.py <<'EOF'\nprint(1)\nEOF"))

    def test_python_c_denied_story_lock_check_allowed(self):
        self.assertIn("python", bash(self.A, "python3 -c 'open(\"app/x.py\",\"w\").write(\"\")'"))
        self.assertIn("python", bash(self.A, "python3 - <<'EOF'\nprint(1)\nEOF"))
        self.assertIsNone(bash(self.A, "python3 /plugins/sdd-harness/scripts/story_lock_check.py features/cancel-booking --json"))

    def test_shell_bypass_denied(self):
        for cmd in ("bash -c 'rm -rf app'", "xargs rm < list", "eval \"$X\"", "curl http://x", "uv run python x.py"):
            self.assertIsNotNone(bash(self.A, cmd), cmd)

    def test_backtick_denied_subst_allowed(self):
        self.assertIn("反引號", bash(self.A, "echo `git rev-parse HEAD`"))
        self.assertIsNone(bash(self.A, "echo $(git rev-parse --short HEAD)"))
        self.assertIsNotNone(bash(self.A, "echo $(git commit -m x)"))

    def test_rm_in_scratch_allowed_in_repo_denied(self):
        self.assertIsNone(bash(self.A, f"rm -f {SCR}/tmp.txt"))
        self.assertIn("rm", bash(self.A, "rm -f app/x.py"))

    def test_find_exec_denied(self):
        self.assertIsNone(bash(self.A, "find app -name '*.py' | wc -l"))
        self.assertIn("find", bash(self.A, "find app -name '*.pyc' -delete"))

    def test_run_test_needs_isolated_db(self):
        self.assertIn("PYTEST_DB_BASE", bash(self.A, "./run test tests/bookings -x"))
        self.assertIsNone(bash(self.A, "PYTEST_DB_BASE=app_test_cr ./run test tests/bookings -x"))
        self.assertIn("./run test", bash(self.A, "./run lint"))

    def test_docker_top_only(self):
        self.assertIsNone(bash(self.A, "docker top api | grep -c 'py[t]est'"))
        self.assertIn("docker", bash(self.A, "docker compose exec api ls"))

    def test_unparseable_denied(self):
        self.assertIn("解析不了", bash(self.A, "echo 'unterminated"))

    def test_write_tool_denied(self):
        self.assertIn("只讀不改", write(self.A, "features/cancel-booking/test.md"))
        self.assertIn("只讀不改", write(self.A, "app/x.py", tool="Edit"))


class ReviewerProfile(unittest.TestCase):
    A = "reviewer"

    def test_write_code_reviews_allowed_src_denied(self):
        self.assertIsNone(write(self.A, "code_reviews/add_cancel_booking.md"))
        self.assertIsNone(write(self.A, f"{CWD}/code_reviews/x.md"))
        self.assertIsNone(write(self.A, f"{SCR}/notes.md"))
        self.assertIn("被擋", write(self.A, "app/x.py"))
        self.assertIn("被擋", write(self.A, "features/cancel-booking/plan.md"))
        self.assertIn("被擋", write(self.A, "code_reviews/x.md", tool="Edit"))

    def test_uv_offline_probe_in_scratch_allowed(self):
        self.assertIsNone(bash(self.A, f"uv run --offline python {SCR}/probe.py"))
        self.assertIsNotNone(bash(self.A, "uv run --offline python app/probe.py"))
        self.assertIsNotNone(bash(self.A, f"uv run python {SCR}/probe.py"))

    def test_reader_cannot_uv(self):
        self.assertIsNotNone(bash("dry-auditor", f"uv run --offline python {SCR}/probe.py"))

    def test_sed_i_on_scratch_probe_still_denied_use_rewrite(self):
        # 擋的是 sed -i 本身（reviewer 改探針請整檔重寫到 scratchpad）
        self.assertIn("sed -i", bash(self.A, f"sed -i 's/a/b/' {SCR}/probe.py"))


class TestRunnerProfile(unittest.TestCase):
    A = "test-runner"

    def test_isolated_run_with_tee_logs_allowed(self):
        self.assertIsNone(bash(self.A, "PYTEST_DB_BASE=app_test_bf PYTEST_WORKERS=2 ./run test 2>&1 | tee logs/test-runner-1.log | tail -5"))

    def test_run_without_prefix_denied(self):
        self.assertIn("PYTEST_DB_BASE", bash(self.A, "./run test tests/rooms"))

    def test_tee_outside_logs_denied(self):
        self.assertIn("tee", bash(self.A, "PYTEST_DB_BASE=x ./run test | tee app/out.log"))

    def test_no_git_no_sed_i_no_python(self):
        self.assertIsNotNone(bash(self.A, "git log -1"))
        self.assertIsNotNone(bash(self.A, "sed -i 's/a/b/' tests/x.py"))
        self.assertIsNotNone(bash(self.A, "python3 scripts/story_lock_check.py x"))

    def test_read_logs_allowed(self):
        self.assertIsNone(bash(self.A, "grep -n FAILED logs/test-runner-1.log | head; sed -n 1,40p logs/test-runner-1.log"))
        self.assertIsNone(bash(self.A, "docker top api | grep -c 'py[t]est'"))
        self.assertIsNone(bash(self.A, "mkdir -p logs"))


class HarnessConfig(unittest.TestCase):
    """test_cmd／isolated_db_env 從專案 CLAUDE.md 的 `## Harness config` 讀。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_config(self, rows: dict[str, str]) -> None:
        lines = ["# proj", "", "## Harness config", "", "| key | 值 | 說明 |", "|---|---|---|"]
        lines += [f"| `{k}` | `{v}` | |" for k, v in rows.items()]
        lines += ["", "## 其他段", "", "| `test_cmd` | `not-this` | 不在 Harness config 段，不該被讀到 |"]
        (self.repo / "CLAUDE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_custom_test_cmd_and_db_env(self):
        self.write_config({"test_cmd": "make test", "isolated_db_env": "TEST_DB"})
        cwd = str(self.repo)
        self.assertIn("TEST_DB", bash("test-runner", "make test tests/bookings", cwd))
        self.assertIsNone(bash("test-runner", "TEST_DB=app_test_bf make test tests/bookings", cwd))
        # 預設的 ./run test 在這個專案不再是測試入口 → 當一般指令走白名單，被擋
        self.assertIsNotNone(bash("test-runner", "PYTEST_DB_BASE=x ./run test", cwd))

    def test_pytest_as_test_cmd(self):
        self.write_config({"test_cmd": "pytest", "isolated_db_env": "PYTEST_DB_BASE"})
        cwd = str(self.repo)
        self.assertIn("PYTEST_DB_BASE", bash("reviewer", "pytest tests/bookings -x", cwd))
        self.assertIsNone(bash("reviewer", "PYTEST_DB_BASE=app_test_cr pytest tests/bookings -x", cwd))

    def test_dash_disables_isolated_db_check(self):
        self.write_config({"test_cmd": "./run test", "isolated_db_env": "-"})
        self.assertIsNone(bash("test-runner", "./run test tests/bookings", str(self.repo)))

    def test_config_is_found_from_subdirectory(self):
        self.write_config({"test_cmd": "make test", "isolated_db_env": "TEST_DB"})
        sub = self.repo / "app" / "bookings"
        sub.mkdir(parents=True)
        self.assertIn("TEST_DB", bash("test-runner", "make test", str(sub)))


class EndToEnd(unittest.TestCase):
    """真的用 stdin JSON 跑 hook：擋下時 stdout 是 deny JSON，放行時沒輸出；exit code 都是 0。"""

    def run_hook(self, payload: dict) -> tuple[int, str]:
        r = subprocess.run([sys.executable, "-I", str(HOOK)], input=json.dumps(payload), capture_output=True, text=True)
        return r.returncode, r.stdout

    def test_deny_emits_json(self):
        code, out = self.run_hook({"agent_type": "reviewer", "tool_name": "Bash", "cwd": CWD,
                                   "tool_input": {"command": "git commit -m x"}})
        self.assertEqual(code, 0)
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("git commit", decision["permissionDecisionReason"])

    def test_allow_emits_nothing(self):
        code, out = self.run_hook({"agent_type": "reviewer", "tool_name": "Bash", "cwd": CWD,
                                   "tool_input": {"command": "git diff --stat"}})
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_garbage_stdin_is_ignored(self):
        r = subprocess.run([sys.executable, "-I", str(HOOK)], input="not json", capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")


if __name__ == "__main__":
    unittest.main()
