---
description: 端到端的自動 code review，預設不停頓：先查前置（隔離測試 DB / commit 落地方式）→ 派 reviewer 子 agent 以 /code-review 標準產出 findings md → 派 story-lock-auditor 核對 user_story 每則是否被測試鎖住 → 主 agent 逐條修＋補鎖 → 派 dry-auditor／design-auditor 找（只讀），主 agent 施工零疑慮項 → 派 mutation-prover 實證 → 收成 fixup! commit，等工作區乾淨再 autosquash。「讀很多、判斷、回清單」的段落都在子 agent，主 context 只留清單與自己的改動。全程不與並行中的其他工作打架。
allowed-tools: Agent, Bash(git:*), Bash(ls:*), Bash(grep:*), Bash(wc:*), Bash(python3:*), Read, Edit, Write, WebFetch, WebSearch, AskUserQuestion
---

## Context

- Current branch: !`git rev-parse --abbrev-ref HEAD`
- Working tree status: !`git status -s`
- Recent commits: !`git log --oneline -5`
- Remote head: !`git log --oneline -1 origin/$(git rev-parse --abbrev-ref HEAD) 2>/dev/null || echo "(此分支尚未推上 remote)"`
- Harness config: !`grep -A 20 '^## Harness config' CLAUDE.md 2>/dev/null || echo "(CLAUDE.md 沒有 Harness config 段；照 plugin 的 docs/CONFIG.md 補上)"`

下文的 `<base_branch>`、`<test_cmd>`、`<isolated_db_env>` 等角括號名稱，一律指 CLAUDE.md `Harness config` 段的同名 key。

**目標範圍**（一次 review 通常是**一整個 feature、多顆 commit**）：
`$ARGUMENTS` 可以是 feature 分支名／`A..B` 範圍／單顆 hash；沒指定就是 `<base>..HEAD`，
`<base>` ＝ `<base_branch>`。
範圍內每一顆都是「目標 commit」；每條 finding 要**掛到引入那段 code 的那顆**（`git log -S'<片段>' <base>..HEAD` 或 `git blame`），fixup 就 fixup 到那顆。
「搬運型」的 commit（整包複本、只搬不改）只審搬運完整性，不審內容——派工包要指明是哪幾顆。

---

## 這支指令是什麼

`/code-review` 只負責「找出問題並呈現」。`/auto-code-review` 把它包成**一條做到底的
流水線**：協商 → 審查 → 彙整 → 逐條修 → 驗證 → 落地到目標 commit。

原始需求（使用者原話）：

> 對這顆 commit 做嚴格 code review `<commit>`，整理 findings 後彙整到一個 md，
> 然後針對裡面 finding 一個一個照順序修正，全部修正完才 amend no-edit 到那個
> commit。每次想跑測試時請先檢查有沒同時有 test 在跑，有的話請等一下，
> 或者你有沒有辦法弄一個獨立的 test 不會干擾現在在跑的 test？有問題請先提出再開始。

「amend no-edit」在實務上常常做不到（目標 commit 早就不是 HEAD 了），所以落地方式
升級成 **fixup! → autosquash**——見 §6。

---

## §0 先查後做（**預設不停頓**：「預設就是不停頓，除非我有講要停」）

本指令從頭到尾**不用 `AskUserQuestion`**。原本 §0 的三題協商改成**固定預設**直接走，
查到的偏離狀況不停下來，而是在 §7 回報「和你的指示不一樣的一點」那段獨立寫明。
只有參數帶 `--ask`、或 user 在指令裡明說「要停」時，才回到舊的阻塞式三題協商。

### 先查（不要用問的，能查就查）

```bash
<test_busy_check>                  # 有輸出＝有人在跑測試；⚠️ 測試跑在容器裡時 host 的 pgrep 抓不到
git status --porcelain             # 工作區有沒有別人的在製品
git log --oneline <base>..HEAD     # 範圍內有幾顆、各是什麼
git branch -r --contains HEAD      # 範圍推出去了沒
```

`test_busy_check` 留空時視為「無法判斷有沒有人在跑」：照樣用隔離 DB，worker 數取小值（§1）。

### 固定預設（不問）

| 原本要問的 | 預設 | 為什麼可以不問 |
|---|---|---|
| 隔離測試 DB 要不要建 | **用 `<isolated_db_review>`**（§1） | 這是本指令與 user 測試並行的前提，永遠要 |
| 工作區有別人的在製品時怎麼保護 | **只挑檔案 `git add` ＋ `git diff --cached --stat` 目視** | stash 會把程式碼從磁碟抽走；「你先處理」要 user 介入 |
| findings 呈現節奏 | **A：全列 → 寫 md → 一路修完** | 本指令本來就預設 A |

### 查到偏離時的固定處置（不停，照做並記錄）

| 查到 | 處置 |
|---|---|
| 範圍多顆（常態） | 每條修正 fixup 到它掛的那顆；§6 一次 `rebase --autosquash <base>` 全部併回（不 amend） |
| 範圍**已推 remote** | 照常審、修、fixup，但 **§6 不 autosquash**：fixup commit 留在本地不改寫歷史，§7 寫明「已推、未 squash，要不要改寫歷史你決定」 |
| 工作區有**別人的在製品** | 列出檔案清單；全程只碰自己改的檔；型別檢查／lint 噴到別人的檔不修，記進報告 |
| 測試在飛且隔離 DB 建不起來 | 審查照做，施工段（§4／§4b）跳過、報告寫明原因 |

### `--ask`（舊行為）

帶 `--ask` 時，上面三個預設改回用 `AskUserQuestion` 一次問完（選項與推薦同上表），偏離狀況也在問的時候一併報告。

---

## §1 隔離測試 DB（⭐ 本指令的關鍵能力：與 user 的測試真正並行）

常見的鐵則是「不可並行跑測試」——因為兩個 `<test_cmd>` 共用同一組測試 DB，
測試前置每個 test 前都會 reset 全表，並跑會互相清桌造成假紅。**但那條鐵則的根因是
「共用同一顆 DB」，不是「不能同時跑測試」**。給 review 自己一組 DB 就解除了。

若 `<test_cmd>` 本身就是平行（例：pytest-xdist），每個 worker 通常會在基底庫名後再加
`_gwN`。所以這裡只要把**基底名**換成 `<isolated_db_review>`，worker 自己會長成
`<isolated_db_review>_gw0`…。

### 為什麼可行（前提；第一次在專案上用時實查一次，之後不必再推導）

| # | 前提 | 去哪查 |
|---|---|---|
| ① | test engine 只吃一個 DB URL 設定 | 測試的 engine fixture（例：`tests/conftest.py`） |
| ② | migration 工具也只吃同一個設定 | migration 的 env 設定（例：alembic 的 `env.py`） |
| ③ | `<test_cmd>` 讓 `<isolated_db_env>` 覆寫基底庫名，沒有寫死在 settings | `<test_cmd>` 背後的腳本 |

三者合起來 ⇒ 只要換掉注入的那個值，就是完全獨立的一套：schema 自己建、reset
只打自己那組、與主 DB 零交集。兩個測試行程同時跑只搶 CPU 與記憶體。
任一條不成立 → 照 §0「隔離 DB 建不起來」處置。

### 建

理想上不必手動建：測試前置在每個 worker 第一次連線時建庫並跑 migration 到最新。
專案還沒做到這件事，就照專案的方式先建一次。

### 跑（**唯一允許的跑法**）

```bash
<isolated_db_env>=<isolated_db_review> <test_workers_env>=<1|2> <test_cmd> <args>
```

- **不要繞過 `<test_cmd>` 自己進容器注入 DB URL**——`<test_cmd>` 通常已經把 log 檔、cache、其他服務的邏輯庫這些連帶隔離處理掉了，自己注入會漏。
- 用 review 專屬的 `<isolated_db_review>`，不跟 `<isolated_db_build>` 或一般自跑用的庫共用：user 常同時開好幾個 session，review 要有自己的一組才不會跟另一個 session 互相 reset。
- `<test_workers_env>`：user 的全套在飛（`<test_busy_check>` 有輸出）就用 `1`，否則 `2`；兩邊的 worker 加起來可能頂到容器記憶體上限。沒設 `test_workers_env` 就省略這段。
- 專案若有慢測試／契約掃描的開關（例：`--slow`），規矩不變——§1b 基線一定帶。

派工包「隔離 DB 測試指令」那一欄就填上面那一行（把 `<args>` 留著給子 agent 填、worker 數填定值）。

### 收尾

**預設留著、不問**——下次 review 可直接重用，測試前置每輪都會 reset，不會有殘留資料。
要刪只用專案提供的清理指令，而且只勾 `<isolated_db_review>` 那幾顆（清理指令常會連 user 的庫一起列）。不要自己下 `DROP DATABASE`。

## §1b 基線一次、派工包一份

### 基線

隔離 DB 建好後，**先在 HEAD 的工作區跑一次全套**（§1 的指令，含慢測試開關）——派 `test-runner` 跑，它只回摘要；§4 修完的全套也派它。記下 `N passed / N failed` 與紅的清單。之後任何紅燈都拿這張清單對：**基線就紅的不是我們改壞的**，不用再逐條猜歸屬。基線有紅時照常往下，報告「Pre-check 執行紀錄」寫明。

**已知必紅**：若專案有測試斷言「測試 DB 基底名恰為預設值」，隔離庫名一定讓它紅——基線表直接標「已知假紅（隔離庫名）」，不算 finding、不修。

### 派工包

子 agent 看不到這段對話，五次派工都要交代同一批事實；現場重打五次就有五次不一致的機會（worker 數、在製品清單漏一個）。所以**只寫一份**，貼在報告檔最前面一節 `## 派工包`，之後每次派工**原封不動貼同一段**，再加該站專屬的一兩行：

```
【派工包】
目標範圍：<base>..HEAD（base=<base_branch>），共 N 顆；每顆一行「hash 一句話」
搬運型 commit（只審搬運完整性）：<hash 或「無」>
歸屬規則：finding 掛到引入那段 code 的那顆（git log -S / blame），fixup 到那顆
是否已推 remote：<是/否>
feature 目錄：<feature_dir>（例：features/<name>/）
報告檔：code_reviews/<name>.md
隔離 DB 測試指令（唯一允許的跑法）：<isolated_db_env>=<isolated_db_review> <test_workers_env>=<1|2> <test_cmd> <args>（不准繞過 test_cmd 自己注入 DB URL）
user 的測試是否在飛：<是/否>（決定了上面的 worker 數）
工作區裡別人的在製品（一律不碰）：<git status --porcelain 的檔案清單，或「無」>
基線：<N passed / N failed；紅的清單或「全綠」>
相關教訓：<lessons-recaller 回的表，原樣；或「無」>
規矩：無人值守、不問問題；只讀的站不碰產品程式碼與 tests/；回報只回清單，不貼 diff／程式碼／測試輸出。
```

**⭐ 硬性步驟：派工包寫好前先派 `lessons-recaller`**，可與基線同時背景派：帶範圍動到的模組、改動類型、關鍵字、feature 目錄。它回的教訓表原樣放進「相關教訓」欄，reviewer／dry／design 都看得到「上次在這附近踩過什麼」。
**「相關教訓」欄是空的、或寫著「無」但這輪沒派過 recaller → 不准派 §2。**「無」只能是 recaller 回的結果，不能是主 agent 自己填的。（實例：曾有一整輪沒派 recaller，近百則的教訓庫一則都沒被讀到。）

---

## §2 審查與故事核對：平行派 `reviewer` ＋ `story-lock-auditor`

兩個都只讀、互不依賴，所以**同時派、背景跑**（Agent 工具 background），等兩個都回來再往下。主 context 不讀 diff。

**派 `reviewer`**（預載 `/code-review` 標準）：派工包 ＋
```
本站：以 code-review 標準審整個範圍，寫報告檔。回報：報告路徑、Findings 總表（# / 嚴重度 / 標題 / 檔案:行 / 掛到哪顆）、一行 Verdict、**範圍地圖**（檔案 → 動到的函式／類別，一行一檔）。
```
範圍地圖之後原樣交給 dry／design 稽核員，三個人看的範圍保證一致、不用各自重算。

**派 `story-lock-auditor`**：派工包 ＋
```
本站：核對 user_story.md 每一則是否被 tests/ 真的鎖住。先跑 python3 ${CLAUDE_PLUGIN_ROOT}/scripts/story_lock_check.py <feature 目錄>，再逐則讀 assert。回報：每則 🔒/🔓/❌ 的表、要補的鎖、要補的標記。
```

它們回來後，主 agent **不要把報告整份 Read 進來**；逐條修（§4）時才讀該 finding 那一節。
審查標準、品質條款四條、「每個 finding 要答得出什麼改壞法會紅」都寫在 reviewer 的定義與 `/code-review` 裡，這裡不重複（複製必漂移）。

---

## §3 報告檔（由 reviewer 寫；主 agent 之後只追加）

reviewer 已照固定骨架寫好 `code_reviews/<name>.md`（Pre-check 紀錄／做得好／Findings 總表／逐條 What-Where-Why-Fix-Source／Verdict）。
主 agent 之後只**追加**三節：`## story-lock 核對`（§3b）、`## DRY 稽核`／`## 設計稽核`（§4b）、`## Mutation 實證`（§5）。

⚠️ **審查期訂正要留在檔案裡，不要偷偷改掉**。若某個 finding 的論據事後被推翻（見 §5），在該 finding 頂端加一段引言區塊寫明「初評 X → 實測後降級 Y，原論據錯在哪」，Verdict 也加一則誠實紀錄。

---

## §3b 收 story-lock 結果（§2 已平行派出；跑在任何重寫之前）

§4b 的 DRY／設計稽核會重寫 code，「行為不變」的保證全靠既有測試。**沒被測試鎖住的 user_story 則**，重寫可以悄悄弄壞而全綠。所以補鎖在 §4 跟 findings 一起做，早於任何重寫。

主 agent 收到 story-lock 的表後：
- 「要補的鎖」併入 §4 的工作清單（編號前綴 `S-`）：**先改 test.md 加 TC（內容開頭標 `[US n]`）→ 寫測試（docstring 第一行 `TC-XXnn [US n]：…`）→ 先紅後綠**。
- 「要補的標記」直接補（test.md 的 TC 內容欄開頭、tests/ docstring 第一行），文件修正，進同一顆 fixup。
- 每一則 🔒 **都要進 §5 的靶清單至少一發**：mutation 打不紅的降成 🔓 並補鎖。蓋戳是實證，不是子 agent 讀 assert 的意見。
- 這張表（經 §5 修正後）就是 §7「user_story 蓋戳結果」的依據：全部 🔒 才蓋「已實作逐則複查 ✅」，有 🔓／❌ 未補完的則號列 ⚠️。
- 報告追加一節 `## story-lock 核對`，原樣貼表。

---

## §3c Critical／High 先驗再修：派 `finding-verifier`

一條錯的 finding 代價是改 code、寫測試、fixup、再被 mutation 打，整串白做。所以 **Critical 與 High 每條各派一個** `finding-verifier`——**不論是誰找到的**：reviewer、story-lock、§4b 稽核的「另見」、還是主 agent 修別條時自己發現的（報告標「主 agent 補」的那種）都算。主 agent 自己找到的更要驗：它同時是發現者和修的人，最容易看不到反例（實例：曾有兩條 High 都是主 agent 補、都沒驗就修）。主 agent 中途發現新的 Critical／High → 先寫進報告、派 verifier，回來才修（可同時背景派），派工包 ＋ 那條 finding 全文。它是對抗式的：只回「維持／降級／撤銷」＋重現輸入或走不到的原因＋Fix 會不會改可觀察行為。

- 「撤銷」→ 報告該 finding 頂端加引言區塊寫明（§3 的訂正規矩），不修。
- 「降級」→ 改嚴重度，照新嚴重度排進 §4。
- 「Fix 會改可觀察行為」→ 不修，改進 §7 拍板題。
- Medium 以下不驗，直接進 §4。

---

## §4 逐條修（照嚴重度 Critical → Nitpick；含 §3b 的 `S-` 補鎖項）

- 工作清單 ＝ reviewer 的 Findings 總表 ＋ story-lock 的「要補的鎖」。每條要讀細節時才 `Read` 報告檔的那一節，不要整份讀。
- 每條 finding 的「掛到」欄決定 fixup 到哪顆；掛錯顆 autosquash 會把修正併進不相干的 commit
- **一次一條，改完就地確認**，不要一口氣全改再一起跑
- 同一段程式碼的多條 finding 可以合併一次改（例如同一個函式的 Low + 兩個 Nitpick）
- **只碰自己的檔**。並行工作者的在製品：不修、不 stash、不 commit，連 lint 都不要
  順手幫它修
- spec（`<feature_dir>` 底下的 test.md 等）若被 finding 打臉，**一併回寫**——測試矩陣補了
  鏡像案例，test.md 的 TC 表也要補，否則下次照 spec 實作又會缺一次

### lint

用 `<lint_cmd>`，但**範圍收窄到我改的檔**（例：`pre-commit run --all-files` 改成
`pre-commit run --files <只有我改的檔...>`）。任何會 `git add .` 或改到整個工作區的 lint 包裝都不要用——
它會把並行工作者的在製品一起 staged。

型別檢查若在**別人的檔**噴錯（在製品常見：型別未收窄、漏 import），
如實回報「這幾條不是我造成的」，**不要動手修**。

### 跑測試

先跑受影響的目錄（快），最後跑一次全套（慢）。全套的失敗要**逐條歸屬**：
是我改壞的，還是並行工作者的在製品？歸屬錯會浪費彼此的時間。

---

## §4b 稽核延伸：`dry-auditor` → 主施工 → `design-auditor` → 主施工（無人值守，**不停頓**）

§4 的 findings 與補鎖修完、全套綠之後，接著做兩道品質稽核（併入本指令、不停頓）。
每道拆成「找」與「改」：**找（掃整個產品程式碼、三分法／三題判斷）在子 agent，改（抽取／重寫、鎖 TC、測試、fixup）在主 agent**，因為改了什麼要帶到 §6。順序固定 **DRY 先、設計後**（抽掉重複之後再看形狀，否則同一段會被審兩次），所以不能平行。

1. 派 `dry-auditor`（預載 `/dry-audit`）：派工包 ＋ reviewer 的**範圍地圖**。回報三張表：零疑慮可施工／待拍板／刻意不抽（B、C 類）。
2. **主 agent 施工「零疑慮可施工」**：照 `/dry-audit` 無人值守模式的規矩——抽到子 agent 指定的位置、每個消費者改成呼叫它、鎖 TC（結構鎖）先紅後綠、隔離 DB runner、lint 只跑自己的檔、`git commit --fixup=<target>` 只 add 自己的檔。**待拍板的一條都不動**。
3. 派 `design-auditor`（預載 `/design-audit`）：派工包 ＋ 範圍地圖（DRY 施工若新增了函式就補上去），並說明 DRY 施工已完成（它看的是施工後的工作區）。回報：可施工／待拍板／刻意不動。
4. **主 agent 施工「可施工」**：照 `/design-audit` 無人值守模式——先用子 agent 給的證據網確認既有 TC 真的咬住（重寫前 mutation 一發實跑有紅）→ 重寫 → 原樣綠 → fixup。Nitpick 只列不改；期望值要改的一律撤回。
5. 兩支的報告**附在 §3 那份 md 尾端**（`## DRY 稽核（/dry-audit）`、`## 設計稽核（/design-audit）`），Findings 總表補上這兩批（編號前綴 `D-`／`G-`）。待拍板項原樣保留，留給 user 事後用互動模式跑。
6. 任一支在施工前置查到阻塞（測試在飛且無隔離 DB、別人的在製品碰到同檔）就**跳過施工、報告寫明**，不停下來等。

參數 `--no-audit` 可整段跳過（例如純文件 commit）。§7 收尾回報要多一段：兩支稽核各做了幾條、待拍板幾條、量化前後（出處 N→1／分支／往返）。

---

## §5 mutation 實證：派 `mutation-prover`（⭐ 本指令最貴的教訓）

**「這條 mutation 會讓哪些 TC 變紅」必須實跑，不可靠讀程式碼推論。**
實例：某 finding 初評 Medium，論據是「這個 mutation 下原有三條 TC 全綠」。實跑後推翻——其中一條也紅了。推論漏分支的機率遠比想像高，而且錯的方向通常是**高估自己找到的洞**。

幾百行測試輸出不該進主 context，所以實跑交給 `mutation-prover`。主 agent 做的是**開靶清單**：§4 的每條修正與新鎖各一發，**加上 story-lock 表裡每一則 🔒 至少一發**（打不紅的則降 🔓、回 §4 補鎖）。一列一發：

```
編號｜為了抓什麼（F3 的修正／S-2 的鎖／D-1 的結構鎖）｜檔案｜原樣片段 → 改壞後｜預期紅的 TC｜預期不紅的 TC
```

派工訊息 ＝ 派工包 ＋ 靶清單（派工包已含隔離 DB 指令、在製品清單，不要另外重打）＋一行「worker 數 0，照 agent 檔的一發一啟動規則」。「預期紅／不紅的 TC」欄給 nodeid 或測試檔都可以，子 agent 會跑整檔。子 agent 一發一還原（grep＋`git diff --quiet` 雙重確認、**還原後不重跑**）、整輪結束跑一次聯集回綠，回報一張表（被抓到／存活＋原因）。

**成本**：每次 pytest 啟動的固定成本（app import）通常遠大於 TC 本身，xdist 多 worker 反而更慢（見 agent 檔「成本事實」）。靶數是牆鐘的主要變數，**別為了湊數開靶**：同一則 🔒 的多個 assert 合成一發打最弱的那個。

主 agent 收到後：
- **先驗回報完整**：每一發都有「實際紅」與「結果」、結尾有「打 N 發…pytest 啟動 N 次」那行；缺表或寫 pending／未跑的發 ⇒ 那幾發重派，不算被抓到（作者實測：換成較小模型的 prover 曾經沒跑 pytest 就回 "pending"）。
- **存活且原因是「鎖沒咬住」** → 回 §4 補 assert，再派一次只打那幾發。
- **存活且是等價 mutation** → 報告寫明刪了什麼，不算洞。
- **預期不紅卻紅** → 對應 finding 的論據要訂正（§3 的引言區塊規矩）。
- 子 agent 回報「工作區可能髒了」→ 立刻 `git diff` 親自確認還原，再往下。

**平行模式（CLAUDE.md `Harness config` 有填 `test_tree_env` 才啟用）**：pytest 啟動成本固定，所以多開幾個 prover 同時打是線性加速（實測兩路並行 13.4 s vs 單路 11.2 s）。**何時開樹**——兩個理由任一成立就開：
- **加速**：靶 ≥ 6 發。
- **主樹不停手**：prover 在飛的期間主 agent 要動主樹（寫下一題、跑測試、commit）——即使靶 < 6 也開 **1 棵**。單路模式下 prover 改的是主樹，期間動工作區可能把改壞的碼夾進 commit（實例：prover 交回報告時還有背景工作沒停，主 agent 先提交了兩顆 fixup，事後查證才確定沒夾帶）；開樹後主樹不在它的作用範圍，這條風險整個消失。
- ⚠️ 樹＝開樹那一刻的快照：主 agent 只能往**下一題**走，不可回頭改 prover 正在驗的那一題（它驗的會是舊版）。
做法：
1. N = min(3, ⌈靶數 ÷ 6⌉)，「主樹不停手」理由開樹時 N 至少 1（每個 prover 一個拋棄式容器，看主機記憶體；`test_busy_check` 有人在跑就 N=1、不開樹——此時 prover 在飛期間主 agent 不動主樹，等它標 completed）。
2. 每份 `scripts/mp_worktree.sh add <n>` 開一棵拋棄式 worktree（內容＝主樹此刻工作區，**含 §4 未 commit 的修正與新 TC**；裸 `git worktree add HEAD` 帶不到，別自己開）。
3. 靶清單平均切 N 份，**同一則訊息裡同時派 N 個 `mutation-prover`**，每個派工訊息＝派工包＋自己那份靶清單＋一行「你的樹：`<test_tree_env>=<mp_worktree.sh path n>`、`<isolated_db_env>=<isolated_db_review>_mp<n>`」。
4. 全部回來後合併 N 張表成一張；`mp_worktree.sh remove <n>` 逐棵收掉；主樹 `git status --porcelain` 前後比對相同（平行模式主樹本來就不該被碰，這是保險）。
存活要補鎖再打的那幾發，量少就不開樹、照單路模式在主樹打（主 agent 等它標 completed 再動主樹）。`test_tree_env` 背後要什麼見 `docs/CONFIG.md`「別棵樹跑測試」。
**不在 /auto-code-review 裡、臨時派 prover 時（例如翻案施工的重構實證）也照本節判斷開不開樹**——本節是 mutation-prover 派工的唯一出處。

**派工前後各拍一次工作區快照**（單路模式；2026-11-04 起；mutation-prover 是唯一本來就要改 src 的子 agent，`hooks/agent_bash_guard.py` 對它不擋寫 src，所以要靠快照兜底）：
派之前 `git status --porcelain > <scratchpad>/mp-before.txt`，回來後再拍一次 `diff` 兩份；多出或少掉任何一行＝它沒還原乾淨，
先 `git diff -- <那幾個檔>` 看是哪一發留在檔裡，手動反向還原後**整輪 mutation 結論作廢重派**（殘留的突變會汙染後面每一發）。

報告追加 `## Mutation 實證` 一節，原樣貼表。

---

## §6 落地：fixup! → autosquash

「全部修正完才 amend no-edit」的**意圖**是：修正必須併回目標 commit、訊息一字不改。
但 `git commit --amend` 只能改 HEAD，而 review 期間 HEAD 常常已經往前跑了。

### 第一步：現在就落地成 fixup（不改寫任何歷史）

```bash
git branch --show-current          # ⭐ 先確認還在派工包寫的那條分支（user 會在 session 之間切分支）；不是就停
git add <只有我改的檔...>          # 逐一列出，不要 git add .
git diff --cached --stat           # ⭐ 目視確認範圍，看到別人的檔就停下來
git commit --fixup=<這條 finding 掛到的那顆> --no-verify
```

- `--fixup` 產生標題為 `fixup! <目標的標題>` 的 commit，git 靠這串認親
- `--no-verify` 只在「pre-commit hook 因**別人的在製品**而失敗」時使用，且必須**已經**
  用收窄到自己檔案的 `<lint_cmd>` 單獨驗過。不要無條件加

```bash
git status --porcelain             # 收尾確認：並行工作者的檔一個都沒被吃掉
git rev-parse HEAD^{tree}          # ⭐ 記下來，§6 第二步驗證要用
```

### 第二步：等工作區乾淨再併回（可以是下一個 session）

```bash
git status --porcelain             # 必須是空的（別用 --autostash 繞過）
git tag backup-before-autosquash HEAD                 # 還原點
GIT_SEQUENCE_EDITOR=true GIT_EDITOR=true git rebase -i --autosquash <base>   # base＝<base_branch>；一次把範圍內所有 fixup 併回各自那顆
```

- ⚠️ git < 2.44 時 `--autosquash` 不加 `-i` **什麼都不做**（2.44 起才不用 `-i`；在 git 2.43 實測過）。Claude Code 環境不支援真互動 rebase，所以用 no-op editor 讓 `-i` 實際上非互動（上面那行就是）。
  跑完 `git log --oneline <base>..HEAD` 裡不能再有任何 `fixup!`，有就是沒併
- `fixup` 的語意就是 `amend --no-edit`；`squash` 才會叫你合併訊息
- 併回前先確認每顆 fixup commit 與它跨過的那幾顆（它掛的那顆之後的所有顆）**檔案零重疊**
  （`git show --stat --format="" <每一顆>`），有重疊就預期會衝突

### 驗證（三件都要做）

```bash
git rev-parse HEAD^{tree}          # ⭐ 必須與第一步記下的完全相同（rebase 只搬 commit）
git log -1 --format="%s" <new sha> # 訊息一字未改
git show <new sha> | grep -c "<每項修正的特徵字串>"   # 每項修正逐一抽驗都在裡面
```

tree hash 對不上 → `git rebase --abort`（過程中）或 `git reset --hard backup-before-autosquash`。

備份 tag **預設留著、不問**；§7 回報寫「要刪跟我說」。

---

## §7 收尾

1. **journal**（若專案有 journal）：`journal/YYYY-MM-DD/code-review-<主題>.md`——寫評分、findings 總表、
   fixup→autosquash 的前後對照與 tree hash 驗證。
1b. **lessons**：這輪有普遍性的教訓
   （不是「這個 feature 的 bug」，是「下次在這附近寫 code 會再踩的」）每則一檔寫到 `<lessons_dir>/<area>/<日期>-<slug>.md`，
   照 `${CLAUDE_PLUGIN_ROOT}/docs/LESSONS.md` 的 frontmatter 與三段格式，`source` 指回本輪 review md 的 finding 編號；更新 `<lessons_dir>/INDEX.md`
   （可用 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lessons_index.py` 重建）。
   通常 1–3 則；沒有就寫「本輪無普遍性教訓」在 journal，不要湊。這些檔進同一顆 fixup（掛到範圍內最後一顆）。
2. **清理**：隔離 DB（`<isolated_db_review>`）與備份 tag **預設留著、不問**；回報裡寫一句「要刪跟我說」
3. **回報**：最終測試數字、lint 狀態、新舊 commit hash 對照、還有哪些是**並行工作者**
   該接手的（例如你順手發現的既有測試連動）。**格式固定照下面的範本**。

### 回報範本（照抄骨架，內容換掉）

```markdown
<feature> 的 `/auto-code-review` 做完了：評分 X.X，修了 N 條 finding 和 N 條 DRY，都已經 fixup 併回原 commit。
修正後的 N 顆停在本地，沒 push、也沒開 PR。全套（含慢測試）從 A 變成 B passed（1 skipped），
lint 全過，`<openapi_check_cmd>` 的 exit code 是 0。

**Findings（都已修）**

| # | 嚴重度 | 問題 | 怎麼修 | 掛到 |
|---|---|---|---|---|
| F1 | High | <白話講後果：誰、在什麼情況、會怎樣> | <一句話修法> | C1 |
| D-1 | DRY | <哪條規則寫了兩份> | <統一到哪> | C1＋C2 |

設計稽核：<幾條達門檻、其餘只記報告>。每條修正都有新測試鎖住（TC-…）。

**Mutation**：新打 N 發，N 發被抓到、N 發存活（<存活的是哪發、為什麼——等價就說刪了什麼>）。

**落地**：N 顆 fixup 都帶著修正說明，autosquash 前後 tree hash 都是 `xxxxxxxx`，新 commit 是
`aaaaaaaa..bbbbbbbb`。舊 hash 已失效。備份 tag `<名>` 先留著，要刪跟我說。

**和你的指示不一樣的一點**：<偏離協商的地方＋原因；沒有就整段拿掉>

**請你拍板的題**（每題 user story 格式：角色／情境／動作／預期行為（現在的做法）／為什麼／
另一個選項／我建議）——**同時追加進 `<feature_dir>/<name>/decisions-pending.md`**（2026-11-05 起：§2 總表一列＋§3 一題，來源欄
「review」、含「翻案要動哪裡」；檔案已有實作期的題就接著編號，不重排、不動已填的「拍板結果」；沒有檔就照 `decision-handoff.md` Step 3 骨架建）。
拍板由 user 之後跑 `/decision-handoff` 開新 session 做，這裡不等。

**已更新的文件**：<review md 路徑、user_story 蓋戳結果（依 §3b 的表：幾則 🔒、哪則 ⚠️ 未補完）、test.md、
其他受影響的文件（前端通知、backlog）、journal 路徑>

接下來：<一句話>
```

範本要點（為什麼是這個形狀）：
- **開頭一句講完結論**（評分、修幾條、停在哪、測試數字），細節往下放。
- **Findings 表的「問題」欄寫業務後果**，不是程式碼描述——user 看表就知道嚴重在哪。
- **「掛到」欄**＝fixup 落在哪顆，讓 PR 審的人知道去哪顆看。
- **偏離協商必獨立一段**，不藏在細節裡。
- **拍板題一律 user story 格式**＋「我建議」，不彈選項框。

---

## 不可違反的十二條

| # | 規矩 | 為什麼 |
|---|---|---|
| 1 | 動工前先**查**，預設不停；偏離預設的狀況照 §0 固定處置做，並在 §7 獨立一段報告。只有 `--ask` 或 user 明說要停才問 | 使用者明示：「預設就是不停頓，除非我有講要停」 |
| 2 | 查並行測試用 `<test_busy_check>`，不是 host `pgrep` | 測試跑在容器裡時 host 看不到；共用測試 DB 並跑會互相 TRUNCATE 造成假紅 |
| 3 | lint 只跑自己改的檔；不用會 `git add .` 的 lint 包裝 | 後者會吃掉別人的在製品 |
| 4 | `git add` 逐檔列出 + `git diff --cached --stat` 目視 | commit 範圍是唯一能親眼確認的東西 |
| 5 | 不 stash 別人的在製品 | stash 會把程式碼從磁碟抽走，背景程序／編輯器會受害 |
| 6 | mutation 的「應紅清單」必須實跑 | 讀程式碼推論會漏分支，且偏向高估自己 |
| 7 | mutation 必須同一輪還原並重跑回綠 | 工作區是共用的 |
| 8 | rebase 的驗證＝ tree hash 不變 | 唯一能證明「只搬 commit、沒改內容」的不變量 |
| 9 | 論據被推翻就在 md 裡明寫訂正 | 悄悄改掉等於湮滅判斷過程，下次還會犯同一個錯 |
| 10 | §4b 兩支稽核不停頓；不確定的不做、寫「待拍板」 | user 明示併入流程且過程不該停頓；停頓的替代品是更嚴的準入門檻 |
| 11 | 「讀很多、判斷、回清單」的段落（§2 審查＋story-lock、§3c 驗 finding、§4b 找、§5 mutation）一律派子 agent；派工訊息＝§1b 的派工包原樣＋該站一兩行，不現場重打；子 agent 只回清單，主 agent 不整份 Read 報告 | 子 agent 不繼承對話；主 context 留給「改了什麼」，整輪跑完 §7 還清醒 |
| 12 | 一次 review ＝ 一整個 feature 的範圍（多顆）；每條 finding 必掛到引入它的那顆，fixup 到那顆、autosquash 一次回 base | 掛錯顆＝把修正併進不相干的 commit，PR 審的人看不懂 |
