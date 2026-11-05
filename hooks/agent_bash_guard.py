#!/usr/bin/env python3
"""agent-bash-guard：PreToolUse(Bash|Write|Edit|MultiEdit|NotebookEdit) 守門 hook，限制**子 agent** 只能做它那一級該做的事。

一支腳本服務全部子 agent：stdin JSON 的 `agent_type` 是子 agent 名字 → 查 AGENT_PROFILE 選 profile；
主 agent（沒有 `agent_type`）或不在表上的 agent 一律放行，不改變既有行為。
擋下時 stdout 印 `permissionDecision: deny` 的 JSON，理由會回給模型（它知道為什麼、能換做法）。
原則：**預設拒絕**——解析不了、不在白名單、重導到 repo 路徑，都擋。

三個 profile：
- reader       只讀：cat/grep/sed -n/git diff|log|show…；可寫的地方只有 scratchpad 與 logs/
- reviewer     reader ＋ `uv run --offline python <scratchpad>/…` 探針；Write 只准 code_reviews/ 與 scratchpad
- test-runner  只准跑 `<test_cmd>`（必帶 `<isolated_db_env>=…`）、tee logs/、讀 logs、`docker top`
mutation-prover 不在表上（它本來就要改原始碼），由 /auto-code-review §5 派工前後比 `git status` 守。

設定從專案 CLAUDE.md 的 `## Harness config` 表讀（見 docs/CONFIG.md；沒設就用預設）：
  test_cmd          跑測試的入口（預設 `./run test`）。入口是專案腳本（`./run`）時，其他子命令（`./run lint`）一律擋
  isolated_db_env   跑測試必帶的隔離 DB 環境變數（預設 `PYTEST_DB_BASE`；設 `-` 關掉這條檢查）
其他可調的常數都在下面「可調區」：scratchpad 前綴（也可用環境變數 AGENT_GUARD_SCRATCH 覆寫，冒號分隔）、
logs/ 與 code_reviews/ 目錄名、可跑的唯讀腳本。

登記方式見 hooks/hooks.json。獨立測試：`python3 -m unittest discover -s tests`。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shlex
import sys

# ---------- 可調區 ----------

AGENT_PROFILE: dict[str, str] = {
    "lessons-recaller": "reader",
    "codebase-researcher": "reader",
    "spec-gap-hunter": "reader",
    "neighbor-finder": "reader",
    "story-lock-auditor": "reader",
    "semantic-conflict-scanner": "reader",
    "overlap-scanner": "reader",
    "dry-auditor": "reader",
    "design-auditor": "reader",
    "finding-verifier": "reader",
    "reviewer": "reviewer",
    "test-runner": "test-runner",
}

SCRATCH_PREFIXES: tuple[str, ...] = tuple(
    p for p in os.environ.get("AGENT_GUARD_SCRATCH", "/tmp/claude-").split(":") if p
)
LOG_DIRS = ("logs",)  # test-runner 的測試輸出
REVIEW_DIRS = ("code_reviews",)  # reviewer 的報告
RO_SCRIPTS = ("scripts/story_lock_check.py",)  # python3 可跑的唯讀腳本（以路徑結尾比對）
DEFAULT_TEST_CMD = "./run test"
DEFAULT_ISOLATED_DB_ENV = "PYTEST_DB_BASE"

# ---------- 白名單 ----------

# 純讀指令：不碰磁碟（寫入靠重導，另外查）
READ_CMDS = {
    "cat", "head", "tail", "grep", "rg", "egrep", "fgrep", "find", "ls", "wc", "awk", "sort", "uniq",
    "cut", "tr", "diff", "echo", "printf", "true", "false", "test", "[", "stat", "file", "date", "pwd",
    "which", "basename", "dirname", "realpath", "tree", "jq", "column", "nl", "tac", "comm", "paste",
    "md5sum", "sha256sum", "cd", "export", "sleep", "ps", "pgrep", "seq", "expr", "read", "type",
    "strings", "less", "more", "od", "xxd", "hexdump", "env", "printenv", "id", "whoami", "hostname",
    "git",  # 子命令另外查 GIT_RO
    "python3", "python",  # 只放行 RO_SCRIPTS，另外查
}
GIT_RO = {
    "diff", "log", "show", "status", "blame", "branch", "rev-parse", "ls-files", "grep", "describe",
    "shortlog", "name-rev", "merge-base", "cat-file", "rev-list", "ls-tree", "config", "remote", "tag",
    "diff-tree", "for-each-ref", "symbolic-ref", "count-objects", "check-ignore", "var", "version",
}
GIT_RO_ONLY_LIST = {"worktree", "stash", "notes"}  # 只放行 `git <x> list`
SHELL_BYPASS = {"bash", "sh", "zsh", "dash", "eval", "exec", "source", ".", "xargs", "sudo", "nohup", "su",
                "curl", "wget", "ssh", "scp", "rsync", "nc", "python", "python3", "uv", "uvx", "pip", "npm", "npx"}
FILE_CMDS = {"tee", "mkdir", "touch", "rm", "mv", "cp", "ln", "chmod", "truncate"}

PROFILES: dict[str, dict] = {
    "reader": {"cmds": READ_CMDS, "write_dirs": (), "uv_scratch": False, "run_test": True},
    "reviewer": {"cmds": READ_CMDS, "write_dirs": REVIEW_DIRS, "uv_scratch": True, "run_test": True},
    "test-runner": {
        "cmds": {"cat", "head", "tail", "grep", "sed", "wc", "ls", "sleep", "date", "ps", "pgrep", "echo",
                 "mkdir", "true", "cd", "pwd", "export", "printf", "tee", "rm"},
        "write_dirs": (), "uv_scratch": False, "run_test": True,
    },
}

SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "\n", "|&"}
REDIRECTS = {">", ">>", "&>", "&>>", "1>", "2>", "1>>", "2>>", ">|"}
CONFIG_ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*`?([^|`]*?)`?\s*\|")


class Deny(Exception):
    pass


# ---------- 設定 ----------

def load_config(cwd: str) -> dict[str, str]:
    """往上找第一個含 `## Harness config` 的 CLAUDE.md；沒有就回空 dict（全用預設）。"""
    for d in [pathlib.Path(cwd), *pathlib.Path(cwd).parents]:
        claude_md = d / "CLAUDE.md"
        if not claude_md.is_file():
            continue
        try:
            text = claude_md.read_text(encoding="utf-8")
        except OSError:
            continue
        if "## Harness config" not in text:
            continue
        config: dict[str, str] = {}
        in_section = False
        for line in text.splitlines():
            if line.startswith("## "):
                in_section = line.strip() == "## Harness config"
                continue
            if in_section:
                m = CONFIG_ROW.match(line.strip())
                if m:
                    config[m.group(1)] = m.group(2).strip()
        return config
    return {}


def test_settings(config: dict[str, str]) -> tuple[list[str], str | None]:
    """回 (test_cmd 的 tokens, 必帶的隔離 DB 環境變數名或 None)。"""
    try:
        tokens = shlex.split(config.get("test_cmd") or DEFAULT_TEST_CMD)
    except ValueError:
        tokens = DEFAULT_TEST_CMD.split()
    env_name = config.get("isolated_db_env", DEFAULT_ISOLATED_DB_ENV).strip()
    return tokens, (None if env_name in {"", "-"} else env_name)


# ---------- 路徑判斷 ----------

def _abs(path: str, cwd: str) -> str:
    p = os.path.expanduser(path)
    if not os.path.isabs(p):
        p = os.path.join(cwd, p)
    return os.path.normpath(p)


def is_scratch(path: str, cwd: str) -> bool:
    return _abs(path, cwd).startswith(SCRATCH_PREFIXES)


def in_dir(path: str, cwd: str, dirname: str) -> bool:
    a = _abs(path, cwd)
    d = _abs(dirname, cwd)
    return a == d or a.startswith(d + os.sep)


def writable_target(path: str, cwd: str, profile: dict) -> bool:
    if path == "/dev/null" or is_scratch(path, cwd):
        return True
    if any(in_dir(path, cwd, d) for d in LOG_DIRS):
        return True
    return any(in_dir(path, cwd, d) for d in profile["write_dirs"])


def writable_places(profile: dict) -> str:
    places = f"scratchpad（{'、'.join(p + '*' for p in SCRATCH_PREFIXES)}）、{'/、'.join(LOG_DIRS)}/"
    if profile["write_dirs"]:
        places += "、" + "/、".join(profile["write_dirs"]) + "/"
    return places


# ---------- 命令解析 ----------

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def strip_heredocs(cmd: str) -> tuple[str, list[str]]:
    """把 heredoc 本文抽掉（本文不是指令），回 (剩下的指令, [heredoc 本文])。"""
    lines = cmd.split("\n")
    out: list[str] = []
    bodies: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _HEREDOC.search(line)
        if not m:
            out.append(line)
            i += 1
            continue
        out.append(line[: m.start()] + " " + line[m.end():])
        term = m.group(2)
        i += 1
        body: list[str] = []
        while i < len(lines) and lines[i].strip() != term:
            body.append(lines[i])
            i += 1
        bodies.append("\n".join(body))
        i += 1  # 跳過終止行
    return "\n".join(out), bodies


def tokenize(cmd: str) -> list[str]:
    cmd = re.sub(r"(?<!\S)\d?>&\d(?!\S)", " ", cmd)  # 2>&1 之類的 fd 複製不是寫檔
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|<>()")
    lex.whitespace_split = True
    lex.commenters = ""
    return list(lex)  # 引號沒關時丟 ValueError


def segments(tokens: list[str]) -> list[list[str]]:
    segs: list[list[str]] = []
    cur: list[str] = []
    for t in tokens:
        if t in SEPARATORS:
            if cur:
                segs.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        segs.append(cur)
    return segs


def split_redirects(seg: list[str]) -> tuple[list[str], list[str]]:
    """回 (去掉重導的 argv, 重導目標清單)。`<` 輸入重導直接丟掉。"""
    argv: list[str] = []
    targets: list[str] = []
    i = 0
    while i < len(seg):
        t = seg[i]
        if t in REDIRECTS or re.fullmatch(r"\d?>>?", t):
            if i + 1 < len(seg):
                targets.append(seg[i + 1])
            i += 2
            continue
        if t in {"<", "<<", "<<<"}:
            i += 2
            continue
        if t.startswith(">") or t.startswith("&>"):  # `>file` 黏在一起
            targets.append(t.lstrip(">&"))
            i += 1
            continue
        argv.append(t)
        i += 1
    return argv, targets


def strip_env_prefix(argv: list[str]) -> tuple[dict[str, str], list[str]]:
    env: dict[str, str] = {}
    i = 0
    while i < len(argv):
        t = argv[i]
        if t == "env" or t == "timeout" and i + 1 < len(argv) and re.fullmatch(r"\d+[smh]?", argv[i + 1]):
            i += 2 if t == "timeout" else 1
            continue
        m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", t)
        if m:
            env[m.group(1)] = m.group(2)
            i += 1
            continue
        break
    return env, argv[i:]


# ---------- 單段判定 ----------

def check_segment(seg: list[str], cwd: str, profile: dict, profile_name: str, config: dict[str, str]) -> None:
    if any("`" in t for t in seg):
        raise Deny("不准用反引號，改用 $(…)。")
    argv, targets = split_redirects(seg)
    for tgt in targets:
        if not writable_target(tgt, cwd, profile):
            raise Deny(f"重導到 `{tgt}` 被擋：子 agent 只能寫 {writable_places(profile)}。")
    env, argv = strip_env_prefix(argv)
    if not argv:
        return
    cmd = argv[0]
    base = os.path.basename(cmd)
    args = argv[1:]

    # 跑測試：所有 profile 共用的一條規則（test_cmd／isolated_db_env 從 Harness config 來）
    test_tokens, db_env = test_settings(config)
    test_cmd = " ".join(test_tokens)
    if argv[: len(test_tokens)] == test_tokens:
        if not profile["run_test"]:
            raise Deny("這個 agent 不跑測試。")
        if db_env and not env.get(db_env):
            raise Deny(f"跑測試必須帶隔離庫前綴：`{db_env}=<庫名> {test_cmd} …`（不可碰共用測試 DB）。")
        return
    if len(test_tokens) > 1 and "/" in test_tokens[0] and cmd == test_tokens[0]:
        raise Deny(f"`{test_tokens[0]}` 只准 `{test_cmd} …`（其他子命令可能 lint／format／git add，會動到並行工作者的在製品）。")

    if base == "git":
        if "git" not in profile["cmds"]:
            raise Deny("這個 agent 不用 git；它只跑測試、讀 log。")
        sub = next((a for a in args if not a.startswith("-")), "")
        if sub in GIT_RO:
            return
        if sub in GIT_RO_ONLY_LIST and "list" in args:
            return
        raise Deny(f"`git {sub}` 被擋：子 agent 只准唯讀 git（diff/log/show/status/blame/branch/rev-parse/ls-files…）。")

    if base in {"python3", "python"}:
        if "python3" not in profile["cmds"]:
            raise Deny("這個 agent 不跑 python。")
        if args and any(args[0].endswith(s) for s in RO_SCRIPTS):
            return
        raise Deny("子 agent 不准跑任意 python（`-c`、`-`、自寫腳本）；只准 " + "、".join(f"`{s}`" for s in RO_SCRIPTS)
                   + "。要探針就用 `uv run --offline python <scratchpad>/x.py`（reviewer 限定）。")

    if base == "uv":
        if profile["uv_scratch"] and args[:3] == ["run", "--offline", "python"] and len(args) > 3 \
                and is_scratch(args[3], cwd):
            return
        raise Deny("`uv` 只准 reviewer 跑 `uv run --offline python <scratchpad 裡的腳本>`。")

    if base == "docker":
        if args[:1] == ["top"]:
            return
        raise Deny("`docker` 只准 `docker top`（exec／compose 會動到共用 stack）。")

    if base == "sed":
        if any(a == "-i" or a.startswith("-i") or a == "--in-place" for a in args):
            raise Deny("`sed -i` 會改檔；子 agent 只准 `sed -n`。")
        if profile_name == "test-runner" and "-n" not in args:
            raise Deny("test-runner 的 sed 只准 `sed -n` 讀 log。")
        return

    if base == "find":
        if any(a in {"-delete", "-exec", "-execdir", "-ok", "-okdir"} for a in args):
            raise Deny("`find` 不准帶 -delete／-exec。")
        return

    if base in FILE_CMDS:
        paths = [a for a in args if not a.startswith("-")]
        if base in {"mv", "cp", "ln"}:
            bad = [p for p in paths if not (is_scratch(p, cwd) or any(in_dir(p, cwd, d) for d in LOG_DIRS))]
        else:
            bad = [p for p in paths if not writable_target(p, cwd, profile)]
        if bad:
            raise Deny(f"`{base} {' '.join(bad)}` 被擋：只能動 {writable_places(profile)} 底下的檔。")
        return

    if base in SHELL_BYPASS:
        raise Deny(f"`{base}` 被擋：會繞過白名單（另起 shell／跑任意程式／連網）。")

    if base in profile["cmds"]:
        return
    raise Deny(f"`{base}` 不在 {profile_name} 的白名單；只讀指令請用 cat/grep/sed -n/git diff…。")


# ---------- 入口 ----------

def decide(payload: dict) -> str | None:
    """回 None＝放行；回字串＝擋下的理由。"""
    agent = payload.get("agent_type") or ""
    profile_name = AGENT_PROFILE.get(agent)
    if not profile_name:
        return None
    profile = PROFILES[profile_name]
    tool = payload.get("tool_name", "")
    tin = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or os.getcwd()

    if tool in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        path = tin.get("file_path") or tin.get("notebook_path") or ""
        if tool == "Write" and path and writable_target(path, cwd, profile):
            return None
        return (f"[{agent}] {tool} `{path}` 被擋：這個 agent 只讀不改，報告檔只能用 Write 寫到 "
                f"{writable_places(profile)}。要改的事寫成 finding 的 Fix 交給主 agent。")

    if tool != "Bash":
        return None
    cmd = tin.get("command") or ""
    try:
        body, _ = strip_heredocs(cmd)
        toks = tokenize(body)
    except ValueError as e:
        return f"[{agent}] 指令解析不了（{e}），預設擋下；拆成簡單的單行指令再試。"
    config = load_config(cwd)
    try:
        for seg in segments(toks):
            check_segment(seg, cwd, profile, profile_name, config)
    except Deny as d:
        return f"[{agent}／{profile_name}] {d}"
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # 讀不到就不插手
    reason = decide(payload)
    if reason is None:
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
