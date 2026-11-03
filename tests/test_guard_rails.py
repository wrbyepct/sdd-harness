"""guard_rails.py 的行為測試：每條規則各測「擋」與「放」。

跑法：python3 -m unittest discover -s tests
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

HOOK = pathlib.Path(__file__).resolve().parent.parent / "hooks" / "guard_rails.py"


def git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class GuardRailsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = pathlib.Path(self._tmp.name)
        self.remote = root / "remote.git"
        self.repo = root / "repo"
        git(root, "init", "-q", "--bare", "-b", "main", str(self.remote))
        git(root, "init", "-q", "-b", "main", str(self.repo))
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "a.txt").write_text("a\n")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-q", "-m", "init")
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "push", "-q", "origin", "main")
        git(self.repo, "switch", "-q", "-c", "feat-x")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_config(self, rows: dict[str, str]) -> None:
        lines = ["# proj", "", "## Harness config", "", "| key | 值 | 說明 |", "|---|---|---|"]
        lines += [f"| `{k}` | `{v}` | |" for k, v in rows.items()]
        (self.repo / "CLAUDE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run_hook(self, command: str) -> tuple[int, str]:
        event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(self.repo)}
        r = subprocess.run(
            [sys.executable, "-I", str(HOOK)], input=json.dumps(event), capture_output=True, text=True
        )
        return r.returncode, r.stderr

    def assertBlocked(self, command: str, needle: str = "") -> None:
        code, err = self.run_hook(command)
        self.assertEqual(code, 2, f"應該被擋：{command}")
        self.assertIn(needle, err)

    def assertAllowed(self, command: str) -> None:
        code, err = self.run_hook(command)
        self.assertEqual(code, 0, f"應該放行：{command}\n{err}")

    # R1
    def test_commit_on_protected_branch_is_blocked(self) -> None:
        git(self.repo, "switch", "-q", "main")
        self.assertBlocked('git commit -m "x"', "main")

    def test_commit_on_feature_branch_passes(self) -> None:
        self.assertAllowed('git commit -m "x"')

    # R2
    def test_push_refspec_to_protected_is_blocked(self) -> None:
        for cmd in (
            "git push origin feat-x:main",
            "git push -u origin HEAD:refs/heads/main",
            "git push origin +feat-x:main",
            "git push origin :main",
            "git push origin --delete main",
            "git fetch -q && git push -o ci.skip origin main",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked(cmd, "`main`")

    def test_bare_push_tracking_protected_is_blocked(self) -> None:
        git(self.repo, "branch", "-q", "--set-upstream-to=origin/main")
        self.assertBlocked("git push", "追蹤設定")

    def test_push_feature_to_itself_passes(self) -> None:
        self.assertAllowed("git push -u origin feat-x:feat-x")

    def test_custom_protected_branches(self) -> None:
        self.write_config({"protected_branches": "release, staging"})
        self.assertBlocked("git push origin feat-x:release", "release")
        self.assertAllowed("git push origin feat-x:main")  # 自訂後 main 不再預設保護

    def test_protection_can_be_disabled(self) -> None:
        self.write_config({"protected_branches": "-"})
        git(self.repo, "switch", "-q", "main")
        self.assertAllowed('git commit -m "x"')

    # R3
    def test_push_all_is_blocked(self) -> None:
        self.assertBlocked("git push --all origin", "--all")
        self.assertBlocked("git push --mirror origin")

    # R4
    def test_checkout_file_and_restore_are_blocked(self) -> None:
        for cmd in ("git checkout -- src/x.py", "git checkout HEAD -- src/x.py", "git restore src/x.py"):
            with self.subTest(cmd=cmd):
                self.assertBlocked(cmd, "restore")

    def test_checkout_branch_passes(self) -> None:
        self.assertAllowed("git checkout feat-x")

    # R5
    def test_rebase_with_pipe_is_blocked(self) -> None:
        self.assertBlocked("git rebase main | tail -5", "pipe")

    # R6
    def test_commit_message_hash_line(self) -> None:
        self.assertBlocked("git commit -F - <<'EOF'\ntitle\n\n#1 fix\nEOF", "--cleanup=verbatim")
        self.assertAllowed("git commit --cleanup=verbatim -F - <<'EOF'\ntitle\n\n#1 fix\nEOF")

    # R7
    def test_direct_pytest_blocked_only_when_test_cmd_set(self) -> None:
        self.assertAllowed("uv run pytest tests/")
        self.write_config({"test_cmd": "./run test"})
        self.assertBlocked("uv run pytest tests/", "./run test")
        self.assertBlocked("pytest -x")

    # R8
    def test_test_cmd_blocked_while_busy(self) -> None:
        self.write_config({"test_cmd": "./run test", "test_busy_check": "echo pytest-running"})
        self.assertBlocked("./run test tests/x.py", "別的測試")
        self.write_config({"test_cmd": "./run test", "test_busy_check": "true"})
        self.assertAllowed("./run test tests/x.py")

    # 目標 repo 的判斷：hook 收到的 cwd 是 session 的目錄，不是指令裡 cd 過去的那個
    def make_other_repo_on_main(self) -> pathlib.Path:
        other = pathlib.Path(self._tmp.name) / "other"
        git(other.parent, "init", "-q", "-b", "main", str(other))
        return other

    def test_cd_into_another_repo_on_main_is_blocked(self) -> None:
        other = self.make_other_repo_on_main()
        self.assertBlocked(f'cd {other} && git commit -m "x"', "`main`")
        self.assertBlocked(f"cd {other}; git push origin HEAD:feat-y", "`main`")
        self.assertBlocked(f'git -C {other} commit -m "x"', "`main`")

    def test_cd_sequence_is_followed_in_order(self) -> None:
        other = self.make_other_repo_on_main()
        self.assertAllowed(f'cd {other} && ls && cd {self.repo} && git commit -m "x"')
        self.assertBlocked(f'cd {self.repo} && cd ../other && git commit -m "x"', "`main`")

    def test_unresolvable_target_blocks_only_commit_and_push(self) -> None:
        self.assertBlocked('cd "$WORK" && git commit -m "x"', "判斷不出")
        self.assertBlocked('git -C "$root" push', "判斷不出")
        self.assertBlocked('cd - && git commit -m "x"', "判斷不出")
        # 不是 commit／push 的照常放行（守門也不能因此崩潰）
        self.assertAllowed('root=/tmp; git -C "$root" rev-list --all | grep -q .')
        self.assertAllowed('cd "$WORK" && ls')

    def test_ordinary_command_passes(self) -> None:
        self.assertAllowed("ls -la src/")


if __name__ == "__main__":
    unittest.main()
