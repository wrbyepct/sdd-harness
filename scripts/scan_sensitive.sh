#!/usr/bin/env bash
# 公開前掃描：用 repo 外的敏感字串清單掃整個 repo，連 git 歷史一起掃。
# 用法：scripts/scan_sensitive.sh <patterns.txt>
# 清單刻意不放在 repo 裡，因為清單本身就含敏感字。
set -u
pat="${1:?usage: scan_sensitive.sh <patterns.txt>}"
root="$(git rev-parse --show-toplevel)"
hits=0

echo "== 工作區"
if grep -rnIE -f "$pat" "$root" --exclude-dir=.git; then hits=1; fi

echo "== git 歷史（所有曾經 commit 過的版本）"
revs="$(git -C "$root" rev-list --all 2>/dev/null)"
if [ -n "$revs" ]; then
  # shellcheck disable=SC2086
  if git -C "$root" grep -nIE -f "$pat" $revs; then hits=1; fi
fi

if [ "$hits" -eq 0 ]; then
  echo "✅ 沒有命中"
else
  echo "❌ 有命中，處理完再公開"
  exit 1
fi
