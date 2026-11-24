---
description: 對帳 <feature_dir>/BACKLOG.md——用 git 實查每一項的狀態（不照文字相信），把漏改的狀態補上（表上那一列＋ticket 檔頭兩處一起改）、做完的列移到已結案表、沒併的在 ticket 補 ⚠️，再實查場外殘留（tag／分支／worktree），最後跑 backlog_check.py。判準有爭議的集中一次問使用者拍板。
argument-hint: "[不帶參數＝完整對帳] [--dry 只報告不改檔] [--no-cleanup 跳過場外殘留]"
allowed-tools: Bash(git log:*), Bash(git branch:*), Bash(git tag:*), Bash(git fetch:*), Bash(git merge-base:*), Bash(git rev-parse:*), Bash(git ls-remote:*), Bash(git worktree:*), Bash(git show:*), Bash(grep:*), Bash(sed:*), Bash(find:*), Bash(cat:*), Bash(ls:*), Bash(wc:*), Bash(python3:*), Read, Write, Edit, AskUserQuestion
---

對帳 `<feature_dir>/BACKLOG.md`：$ARGUMENTS

專案設定從專案 `CLAUDE.md` 的 `## Harness config` 段讀：`feature_dir`（feature 根目錄，預設 `features/`）、`base_branch`。

## 這件事的本質

狀態由流程節點當下寫（`/ticket` 立題、`/user-story` 需求模式改「進行中」、複查蓋戳改「完成」），
這支指令是**第二道**：節點漏寫、或場外直接 merge 的，由這裡用 git 實查補上。三種實際發生過的謊
（例子換成虛構的會議室預約系統）：

| 謊 | 例 | 只能靠什麼揭穿 |
|---|---|---|
| **狀態註記會過期** | 備註寫「停本地未 push」，其實一週前就合了 | `git merge-base --is-ancestor` |
| **rebase 過的 feature，記的 hash 變幽靈** | ticket 記的 hash 在主分支查無，正本是 rebase 後的另一顆 | 用 **subject** 再搜一次，別直接判「沒併」 |
| **表上那句與 ticket 內文不一致** | 列說「其餘 30 支端點」，ticket 說又收了 5 支 | 把列與 ticket 對讀；**ticket 才是權威** |

⇒ **鐵則：一律用 git／實碼驗證，不照文字相信。** BACKLOG 是索引，不是內容。

## Step −1 — 認清版面

- 對帳對象只有 `<feature_dir>/BACKLOG.md`：主線順序、未結案表、已結案表，七欄 `| # | 標題 | 級別 | 母題 | 依賴 | 狀態 | 備註 |`。
- 每一項＝一個資料夾 `<feature_dir>/<N>-<名>/`（專案可能多包幾層），`ticket.md` 是那一項的權威；
  `#N` 用 `find <feature_dir> -maxdepth 4 -type d -name 'N-*' -not -path '*/archive/*'` 找。
- `<feature_dir>/archive/` 底下是**封存檔，不對帳、不改**。
- 對帳紀錄寫在 `<feature_dir>/BACKLOG-log.md`（沒有就建）。
- **狀態寫兩處**：表上狀態欄＋`ticket.md` 檔頭「級別：…｜狀態：…」那行。改任何一項都兩處一起改。
- **資料夾不搬、不改名**（結案也不搬）；結案只把列從未結案表移到已結案表。

## Step 0 — 取實查基準

```bash
git fetch --prune
git rev-parse --short origin/<base_branch>     # 這一輪的基準，寫進 BACKLOG-log
git log --oneline -3 origin/<base_branch>
```

⚠️ `--prune` 必跑：遠端分支被刪之後，本地的 remote-tracking ref 會留著，會把已不存在的分支當成殘留。

## Step 1 — 讀表、盤出現況

1. 讀 `BACKLOG.md` 兩張表與主線順序、`BACKLOG-log.md` 最上面一輪（上一輪留給使用者沒回答的拍板題在那裡，這一輪一起收）。
2. 對未結案表每一列，判斷它**實際**在哪個階段（下表），不看表上寫什麼：

| 看到 | 實際狀態 |
|---|---|
| 資料夾裡只有 `ticket.md`、沒有對應分支 | 待開工 |
| 有 `research.md`／`user_story.md`／`plan.md` 任一、或有 `feat-*`／`fix-*` 分支在動 | 進行中 |
| `user_story.md` 有「已實作逐則複查 ✅」戳，或 tiny 的修正 commit 已在 `origin/<base_branch>` | 完成 |

## Step 2 — 逐項驗證（不准跳）

對每一個看起來已動工或已完成的項目：

```bash
git merge-base --is-ancestor <hash> origin/<base_branch> && echo "在 <base_branch>"
# 查無 ⇒ 不要馬上判「沒併」，先用 subject 找它 rebase 後的身分：
git log --oneline --grep='<commit subject 的關鍵字>' origin/<base_branch> | head
```

ticket 或備註宣稱「部分完成」「只剩 X」的，一律**去讀實碼**：找出這條規則該掛在哪幾個掛載點，逐點 grep；
對應的 `test.md` 有沒有 TC 是很強的旁證（零 TC ⇒ 幾乎確定沒做）。

## Step 3 — 判準（預設值；使用者當場改口就照他的）

| 判準 | 內容 | 落地 |
|---|---|---|
| **結案＝實作做完，不必等 merge** | 修正停在未併分支也算完成 | ticket 的「完成條件」段下面**必須**補一行 `> ⚠️ 還沒進 <base_branch>（<分支>＝<hash>），拿 <base_branch> 部署仍會踩` |
| **只剩非實作尾巴 ⇒ 結案** | 只剩「轉交一封回報」「一段說明文字」「低優先冷門狀況」 | 尾巴寫成該 ticket 內一行 `> ⬜` 備註 |
| **有了實作單 ⇒ 收編成一筆** | 規格落成、實作單已是另一個編號 | 原項狀態改「收編進 #N」、移到已結案表 |

目的只有一個：讓未結案表上剩下的每一列，都是**真的要動工的事**。
判準套不下去、或這一項是新的形狀 ⇒ 先放著，進 Step 5 一次問。

## Step 4 — 改檔（`--dry` 只列出會改什麼）

逐項，表與 ticket 檔頭**兩處一起改**：

1. **漏改成「進行中」的**：表上狀態欄改「進行中」；`ticket.md` 檔頭那行同步。
2. **完成的**：表上狀態欄改「完成」→ 整列剪下、照編號插進已結案表；`ticket.md` 檔頭同步；備註欄寫 `PR #x`（或「未併，見 ticket」）＋日期。
   連結**不用改**（資料夾不搬）。
3. **完成但沒併的**：照 Step 3 第一列在 ticket 補 ⚠️。
4. **作廢／收編**：狀態寫「作廢」或「收編進 [#N](路徑)」，移到已結案表，備註欄一句理由。
5. **備註欄過期的**（「等 X」而 X 已發生、「排在 #N 之後」而 #N 已完成）：改成現在的一句話。備註只准一句，細節寫回 ticket。
6. **主線順序**：做完的整列搬到 `BACKLOG-log.md` 的「已完成」最上面；被收編的格改成指向實作單。
7. **large 的母題**：子題全數完成 ⇒ 母題一起改「完成」移表；母題 ticket「子題與順序」各行標上 ✅。
8. **`BACKLOG-log.md` 的「對帳紀錄」最上面加一行**：`- YYYY-MM-DD 第 N 輪、基準 origin/<base_branch>＝<hash>：補「進行中」#…；結案 #…（依據）；…`，
   下面接兩小段：改了狀態的每一項＋依據（# / 項目 / 原狀態→新狀態 / 依據）、留給使用者的拍板題（沒收掉的要寫，下一輪才接得住）。

## Step 5 — 拍板題：集中一次問

Step 3 套不下去的、以及上一輪留著沒回答的，用 `AskUserQuestion` **一次問完**（不要邊做邊問，也不要替使用者決定「算不算結案」）。

🔴 **問之前先把白話情境備好，而且先驗那條路走得到**（例：替「候補名單沒檢查人數上限」編情境時說「有人能靠候補多訂一間」，
實查發現候補遞補根本不走那條路，整個情境不成立）。情境編得出來不代表它會發生；替「還沒實作的缺口」講故事前先 grep 那條路。
發現這種事要**寫回該項的 ticket**，不要只在對話裡講完就算。

使用者拍完之後才回到 Step 4 把決定寫進檔案。

## Step 6 — 場外殘留實查（`--no-cleanup` 時跳過）

```bash
git tag -l                                       # 備份 tag
git branch --merged origin/<base_branch>         # 已併的本地分支
git branch -r                                    # prune 後仍在的遠端
git worktree list
```

**先列出來給使用者看，他點頭的才刪。** 刪之前**逐條**驗：

```bash
git merge-base --is-ancestor <branch-tip> origin/<base_branch>   # 過了才刪
git branch -d <branch>     # 🔴 一律 -d，不用 -D——讓 git 當第二道關
```

使用者說要留的，記在 `BACKLOG-log.md` 最上面一行「⭐ 保留勿刪：…」，下一輪先讀它再動手。

## Step 7 — 收尾自我檢查（真的跑，不准目視）

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/backlog_check.py <feature_dir>/BACKLOG.md
```

全部 ✅ 且 exit code 0 才算對完（表與 ticket 一一對應、兩處狀態一致、母題子題互連、連結沒斷、表格沒空行）。

## 禁止事項

- ⛔ 不准憑「表上寫著」就下結論——那正是這支指令存在的原因。
- ⛔ 不准動 `<feature_dir>/archive/` 底下的封存檔。
- ⛔ 不准搬動或改名任何 `<N>-<名>/` 資料夾（連結靠它不動）。
- ⛔ 不准只改表不改 ticket 檔頭（或反過來）。
- ⛔ 不准自己決定一項「算不算結案」的新形狀——判準三條之外的，一律問使用者。
- ⛔ 不准用 `git branch -D` 或 `git checkout` 清殘留；刪任何東西前先 `--is-ancestor` 驗過。
