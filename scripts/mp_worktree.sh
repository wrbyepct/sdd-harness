#!/usr/bin/env bash
# mutation-prover 平行用的拋棄式 worktree（2026-11-06）。
#
#   scripts/mp_worktree.sh add <n>      # 開 ../<主樹名>-mp<n>，內容＝主樹「現在的工作區」
#   scripts/mp_worktree.sh remove <n>   # 收掉
#   scripts/mp_worktree.sh list
#
# 為什麼不是裸 `git worktree add HEAD`：/auto-code-review §5 跑在 §6 之前，§4 的修正與新 TC 還沒
# commit，HEAD 沒有它們。這裡開在 HEAD 之後再把 `git diff HEAD`（含 binary）與未追蹤檔一起帶過去，
# 樹裡看到的就是主樹此刻的樣子。被 .gitignore 的東西（logs/、.venv/ 之類）不帶，測試不需要。
#
# 跑法（在 worktree 裡的 code、拋棄式容器、自己的 DB）：
#   <test_tree_env>=$(mp_worktree.sh path <n>) <isolated_db_env>=<isolated_db_review>_mp<n> <test_workers_env>=0 <test_cmd> …
set -euo pipefail

main_tree="$(git rev-parse --show-toplevel)"
name="$(basename "$main_tree")"

path_of() { echo "$(dirname "$main_tree")/${name}-mp${1}"; }

cmd="${1:-}"; n="${2:-}"
case "$cmd" in
    add)
        [ -n "$n" ] || { echo "用法：mp_worktree.sh add <n>" >&2; exit 1; }
        wt="$(path_of "$n")"
        [ ! -e "$wt" ] || { echo "已存在：$wt（先 remove）" >&2; exit 1; }
        git -C "$main_tree" worktree add --detach --quiet "$wt" HEAD
        # 已追蹤檔的未 commit 改動（含 staged）
        if ! git -C "$main_tree" diff --quiet HEAD -- . ':!.claude'; then
            git -C "$main_tree" diff HEAD --binary -- . ':!.claude' | git -C "$wt" apply --whitespace=nowarn
        fi
        # 未追蹤、未被 ignore 的新檔（新 TC 檔多半在這）
        git -C "$main_tree" ls-files --others --exclude-standard -z \
            | rsync -a --from0 --files-from=- "$main_tree/" "$wt/"
        echo "$wt"
        ;;
    remove)
        [ -n "$n" ] || { echo "用法：mp_worktree.sh remove <n>" >&2; exit 1; }
        wt="$(path_of "$n")"
        git -C "$main_tree" worktree remove --force "$wt"
        echo "removed $wt"
        ;;
    path)
        [ -n "$n" ] || { echo "用法：mp_worktree.sh path <n>" >&2; exit 1; }
        path_of "$n"
        ;;
    list)
        git -C "$main_tree" worktree list | grep -- "-mp[0-9]" || true
        ;;
    *)
        sed -n '2,15p' "$0" >&2; exit 1 ;;
esac
