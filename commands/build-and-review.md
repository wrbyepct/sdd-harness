---
description: /build-feature → /auto-code-review 一條做到底、中間不停：主 agent 以串接模式實作（新決策點選推薦記暫定拍板、隔離 DB、lint 只跑改過的檔），用它的交接包自動生 review 開工指令（不問人），再派一個全新 context 的子 agent 跑 /auto-code-review（它裡面再派六個），主 agent 只收 §7 報告，最後把暫定拍板與 review 拍板題合成一份給 user。做完不 push。
argument-hint: <feature 名（<feature_dir> 底下的目錄名）> [--inc <Inc 名>]
allowed-tools: Agent, Bash(git:*), Bash(docker:*), Bash(uvx:*), Bash(python3:*), Bash(ls:*), Bash(grep:*), Bash(cat:*), Bash(wc:*), Read, Edit, Write, WebFetch, WebSearch, Skill
---

## Context

- Current branch: !`git rev-parse --abbrev-ref HEAD`
- Working tree: !`git status --porcelain | head -20`
- 參數：`$ARGUMENTS`
- 專案設定：從專案 `CLAUDE.md` 的 `## Harness config` 段讀 `base_branch`、`feature_dir`、`test_busy_check`、
  `isolated_db_env`、`isolated_db_build`、`isolated_db_review`（下文的 `<key>` 指那一格的值）。
  開工時先跑一次 `test_busy_check`（有設才跑），記下 user 的 pytest 是否在飛。

## 這支指令是什麼

兩支既有指令的**串接器**，自己不定義任何實作或審查規則：
- 實作規則全在 `/build-feature`（本指令只啟用它的「串接模式」節）
- 審查規則全在 `/auto-code-review` 與它派的 agents
- 開工指令格式見第 2 段的固定骨架；兩題（搬運型、拍板題）不問人，答案來自 build-feature 的交接包

user 出手的地方只有兩處：打這支指令、把最後 `/decision-handoff` 印出的開工指令貼到新 session 逐題拍板（2026-11-05 起；合併報告只是順便看）。中間**不問任何問題**（新決策點選推薦繼續，即使改到已拍板的 user_story 則也照改、最後一起報）。

## 四段

### 第 1 段 — 實作（主 agent，串接模式）

用 Skill 工具執行 `/build-feature $ARGUMENTS --chain`。它會：
- 新決策點選推薦、記「暫定拍板」（plan.md 落地紀錄＋user_story 該則加 ⚠️ 標記）
- 測試走 `<isolated_db_env>=<isolated_db_build> <test_cmd>`，lint 只跑改過的檔
- 一 Inc 一顆 commit、不 push、收尾不停，最後產「交接包」

主 agent 把交接包**原樣保存**（這是第 2 段的唯一輸入）。build-feature 回報的其他內容不要再複述。

### 第 2 段 — 生 review 開工指令（主 agent，不問人）

照下面的固定骨架填（照抄骨架，不在裡面重抄任何規則——規則在指令與 agents 檔裡，抄第二份就會漂移）：

```
/auto-code-review <分支名>

規則以 /auto-code-review 與它派的 agents 為準，下面只給這一輪的事實：

範圍：<base>..HEAD 共 N 顆：<hash 一句話>、<hash 一句話>、…。搬運型（只審搬運完整性）：<hash 或「無」>。<已推 remote／整條未推 remote>。
feature 目錄：<feature_dir>。四文件：<有哪些>。user_story N 則；test.md TC N 條，[US] 未標 N 條。拍板題：<見下表>。
story-lock 起點：腳本表 mapped N／spec-only N／unmapped N（則號：…）。
在製品：<git status --porcelain 的檔或「工作區乾淨」>。user 的 pytest：<在飛／沒有>。
不在本案範圍、不改不 add：<其他指定的檔，沒有就「無」>。
commit 末行 Co-Authored-By: <本機慣用的那一行>。
```

來源對照：

| 欄 | 來源 |
|---|---|
| 範圍、每顆一句話 | 交接包「範圍」；再 `git log --oneline --reverse <base_branch>..HEAD` 核一次 |
| 搬運型 | 交接包「搬運型 commit」 |
| feature 目錄、則數、TC 數、[US] 未標數 | 交接包；再跑一次 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/story_lock_check.py <dir>` 取 mapped／unmapped |
| 拍板題 | **「全定，不可再問；另有暫定拍板 N 條見交接包，review 中碰到相關 code 以暫定為準、不翻案」** |
| story-lock 起點 | 腳本表 |
| 在製品、user 的 pytest | 現場查（`git status --porcelain`、`test_busy_check`） |
| 不在範圍 | user 指定的檔（沒有就「無」） |
| Co-Authored-By | 本機慣用那一行 |

開工指令第一行固定：`/auto-code-review <分支名>`；第二行固定：「規則以 /auto-code-review 與它派的 agents 為準，下面只給這一輪的事實：」。

### 第 3 段 — 審查（全新 context 的子 agent）

主 context 此時裝滿了整個 TDD 過程，不適合審自己的 code。用 **Agent 工具**派一個子 agent（一般型，不指定 agent），prompt ＝ 第 2 段的開工指令全文 ＋ 這一句：

```
請用 Skill 工具執行上面第一行的 /auto-code-review（它會自己派 reviewer／story-lock-auditor／finding-verifier／dry-auditor／design-auditor／mutation-prover）。做完把 §7 的收尾回報**原樣**回給我，不要摘要、不要多加解讀。
```

主 agent **等它回來**，期間不做別的事（它會動工作區）。

### 收尾 — 合併報告（主 agent）

一則訊息，三節，照這個順序：

```markdown
## /build-and-review <feature> 做完了
<build-feature 的 🏁 一行：共 N 顆 commit、停本地未 push> ＋ <auto-code-review §7 的開頭一句：評分、修了幾條、autosquash 結果>

## 待拍板（細節在 decisions-pending.md，這裡只列總表）
<decisions-pending.md §2 總表原樣：# ｜來源（實作期／review）｜一句話｜推薦>

## 細節
<auto-code-review §7 其餘內容原樣：Findings 表、story-lock 蓋戳、mutation、落地、偏離預設的一段、已更新的文件>
```

### 第 4 段 — 交接（主 agent；2026-11-05 起作者拍板）

合併報告印完，**用 Skill 工具執行 `/decision-handoff <feature_dir>/<name>`**：它會補 `decisions-pending.md` 的 §0 現況與 §1 context、
核對實作期（build-feature 即時寫的）與 review 期（auto-code-review §7 追加的）兩批題都在 §2／§3、更新記憶、印出下個 session 的拍板開工指令。
user 出手的第二處就是貼那段開工指令；本 session 到此結束，不在這裡拍任何一題。

## 禁止事項

- ⛔ 不在這裡重抄 build-feature／auto-code-review 的任何規則；它們改了這裡不用動。
- ⛔ 中間不問 user（兩支各自的無人值守規矩負責「不確定的不做、寫待拍板」）。
- ⛔ 第 3 段不准在主 context 自己跑 `/auto-code-review`；一定派子 agent。
- ⛔ 不 push、不開 PR、不刪隔離 DB（`isolated_db_build`／`isolated_db_review` 都預設留著）。
- ⛔ 子 agent 回來的 §7 不准摘要掉「和你的指示不一樣的一點」那段。
