#!/usr/bin/env python3
"""guard-rails：PreToolUse(Bash) 守門 hook。

agent 送出的每一條 Bash 指令先經過這裡；違規就 exit 2，stderr 的理由會回給模型，
讓它知道為什麼被擋、該改成什麼。

規則（全部只看指令字串＋幾個唯讀的 git 查詢，不執行指令本身）：
  R1  HEAD 在保護分支時不准 commit／push
  R2  push 的目的地是保護分支不准（refspec 寫明的、`:x`、`--delete x`，以及裸 push 時的追蹤設定）
  R3  `git push --all／--branches／--mirror` 不准
  R4  `git checkout -- <file>`／`git restore` 不准（會把未 commit 的改動整檔退回，連別人的在製品一起沖掉）
  R5  `git rebase` 接 pipe 不准（非互動 rebase 的錯誤會被 pipe 吃掉）
  R6  commit 訊息有以 `#` 開頭的行、又沒加 `--cleanup=verbatim` → 不准（git 會把那行當註解刪掉）
  R7  專案有設 `test_cmd` 時，直接跑 pytest 不准（要走專案的測試入口）
  R8  跑 `test_cmd`／`lint_cmd` 前，`test_busy_check` 有輸出（＝別人正在跑測試）→ 不准，避免互踩

設定從專案 CLAUDE.md 的 `## Harness config` 表讀（見 docs/CONFIG.md）：
  protected_branches  逗號分隔；沒設預設 `main, master`；設成 `-` 整個關掉 R1～R3
  test_cmd／lint_cmd／test_busy_check  給 R7、R8 用；沒設就跳過

失敗策略：hook 自己出錯時，只有 git commit／push 會被擋（fail-closed，並把錯誤原因寫清楚）；
其他指令放行（fail-open），免得守門壞掉讓整個 session 動不了。
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shlex
import subprocess
import sys

SEP = r"(?:^|[\s;&|(])"
GIT = SEP + r"git\s+(?:-C\s+(?P<dir>\"[^\"]+\"|'[^']+'|\S+)\s+)?"
GIT_COMMIT = re.compile(GIT + r"commit(?=\s|$)")
GIT_PUSH = re.compile(GIT + r"push(?=\s|$)(?P<args>[^;&|\n]*)")
GIT_REBASE = re.compile(GIT + r"rebase(?=\s|$)")
GIT_CHECKOUT_FILE = re.compile(GIT + r"(?:checkout\s+(?:\S+\s+)?--\s|restore\s)")
DIRECT_PYTEST = re.compile(SEP + r"(?:uv\s+run\s+pytest|uvx\s+pytest|python3?\s+-m\s+pytest|pytest)(?=\s|$)")
PUSH_ALL_FLAGS = {"--all", "--branches", "--mirror"}
PUSH_FLAGS_WITH_ARG = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
DEFAULT_PROTECTED = ["main", "master"]
CONFIG_ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*`?([^|`]*?)`?\s*\|")

NAME = "guard-rails"


class Blocked(Exception):
    pass


def run_git(args: list[str], cwd: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def git_dir(command: str, cwd: str) -> str:
    """`git -C <dir>` 的 dir；含 shell 變數或不存在時退回 cwd（不猜）。"""
    for pattern in (GIT_COMMIT, GIT_PUSH, GIT_REBASE):
        m = pattern.search(command)
        if m and m.group("dir"):
            d = m.group("dir").strip("\"'")
            if "$" in d:
                return cwd
            p = pathlib.Path(cwd, os.path.expanduser(d))
            return str(p) if p.is_dir() else cwd
    return cwd


def load_config(repo_dir: str) -> dict[str, str]:
    top = run_git(["rev-parse", "--show-toplevel"], repo_dir) or repo_dir
    claude_md = pathlib.Path(top, "CLAUDE.md")
    if not claude_md.is_file():
        return {}
    config: dict[str, str] = {}
    in_section = False
    for line in claude_md.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_section = line.strip() == "## Harness config"
            continue
        if in_section:
            m = CONFIG_ROW.match(line.strip())
            if m:
                config[m.group(1)] = m.group(2).replace("\\|", "|").strip()
    return config


def protected_branches(config: dict[str, str]) -> set[str]:
    raw = config.get("protected_branches")
    if raw is None or raw == "":
        return set(DEFAULT_PROTECTED)
    if raw.strip() == "-":
        return set()
    return {b.strip() for b in raw.split(",") if b.strip()}


def explicit_push_targets(args: str) -> list[str] | str:
    """push 指令寫明的目的分支；`--all` 一類回 'all'；沒寫 refspec 回 []。"""
    try:
        tokens = shlex.split(args)
    except ValueError:
        tokens = args.split()
    positional: list[str] = []
    skip = False
    for tok in tokens:
        if skip:
            skip = False
            continue
        if tok in PUSH_ALL_FLAGS:
            return "all"
        if tok in PUSH_FLAGS_WITH_ARG:
            skip = True
            continue
        if not tok.startswith("-"):
            positional.append(tok)
    targets = []
    for spec in positional[1:]:  # 第一個是 remote
        spec = spec.lstrip("+")
        dest = spec.split(":", 1)[1] if ":" in spec else spec
        targets.append(dest.removeprefix("refs/heads/"))
    return targets


def implicit_push_targets(repo_dir: str) -> list[str]:
    """裸 `git push` 會推去哪：@{push} 與 @{upstream} 都看（push.default 各機器可能不同）。"""
    out = []
    for ref in ("@{push}", "@{upstream}"):
        name = run_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", ref], repo_dir)
        if name:
            out.append(name.split("/", 1)[1] if "/" in name else name)
    return out


def commit_message_has_hash_line(command: str) -> bool:
    body = command.split("\n")[1:]  # 第一行是指令本身；之後是 heredoc／多行 -m
    return any(
        line.lstrip().startswith("#") and not re.fullmatch(r"\s*['\"]?EOF['\"]?\s*\)?\s*", line)
        for line in body
    )


def starts_with_cmd(command: str, cmd: str) -> bool:
    if not cmd:
        return False
    return re.search(SEP + re.escape(cmd) + r"(?=\s|$)", command) is not None


def check(command: str, cwd: str) -> None:
    if GIT_CHECKOUT_FILE.search(command):
        raise Blocked(
            "禁用 `git checkout -- <file>`／`git restore`：會把未 commit 的改動整檔退回 HEAD，"
            "連別人的在製品一起沖掉。要還原自己的改動，用成對的精準字串替換；真的要退檔，請使用者自己執行。"
        )
    if GIT_REBASE.search(command) and "|" in command:
        raise Blocked("`git rebase` 不可接 pipe：非互動 rebase 的錯誤會被吃掉。單獨跑 rebase，輸出另一個指令再看。")

    is_commit = GIT_COMMIT.search(command)
    push = GIT_PUSH.search(command)
    repo = git_dir(command, cwd)
    config = load_config(repo)

    if is_commit or push:
        protected = protected_branches(config)
        if push and protected:
            explicit = explicit_push_targets(push.group("args"))
            if explicit == "all":
                raise Blocked("`git push --all／--branches／--mirror` 會連保護分支一起推。逐條寫明 `git push -u origin <分支>:<分支>`。")
            targets = explicit or implicit_push_targets(repo)
            hit = next((t for t in targets if t in protected), None)
            if hit:
                how = "refspec 寫明" if explicit else "本分支的追蹤設定"
                raise Blocked(
                    f"這次 push 的目的地是保護分支 `{hit}`（{how}）。走 feature 分支 → PR："
                    "寫明 `git push -u origin <feat>:<feat>`；追蹤錯了先 `git branch --unset-upstream`。"
                )
        branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
        if branch is None:
            raise RuntimeError(f"讀不到目前分支（git -C {repo}）")
        if branch in protected:
            raise Blocked(f"HEAD 在保護分支 `{branch}`，不直接 commit／push。先開 feature 分支，或停下來問使用者。")
        if is_commit and commit_message_has_hash_line(command) and "--cleanup=verbatim" not in command:
            raise Blocked("commit 訊息有以 `#` 開頭的行，git 會當註解刪掉。加 `--cleanup=verbatim`，或改寫那一行。")

    test_cmd = config.get("test_cmd", "")
    if test_cmd and "pytest" not in test_cmd and DIRECT_PYTEST.search(command):
        raise Blocked(f"本專案不直接跑 pytest，請用 `{test_cmd} [path]`（見 CLAUDE.md 的 Harness config）。")

    busy_check = config.get("test_busy_check", "")
    if busy_check and (starts_with_cmd(command, test_cmd) or starts_with_cmd(command, config.get("lint_cmd", ""))):
        try:
            r = subprocess.run(busy_check, shell=True, cwd=repo, capture_output=True, text=True, timeout=15)
            busy = r.returncode == 0 and r.stdout.strip() != ""
        except (OSError, subprocess.TimeoutExpired):
            busy = False
        if busy:
            raise Blocked(f"現在有別的測試在跑（`{busy_check}` 有輸出），同時跑會互踩同一組測試 DB。等它結束再跑。")


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if event.get("tool_name") != "Bash":
        return 0
    command = (event.get("tool_input") or {}).get("command", "")
    cwd = event.get("cwd") or os.getcwd()
    try:
        check(command, cwd)
    except Blocked as e:
        print(f"{NAME}: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 — 守門自己壞掉時的保底
        if GIT_COMMIT.search(command) or GIT_PUSH.search(command):
            print(f"{NAME}: 守門自己出錯（{type(e).__name__}: {e}），commit／push 先不放行。請把這條指令貼給使用者判斷。", file=sys.stderr)
            return 2
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
