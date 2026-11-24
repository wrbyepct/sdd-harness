# 指令與 agent 一覽

[← 回 README](../README.md)

## 裡面有什麼

| 類別 | 內容 |
|---|---|
| commands（11） | `ticket`、`backlog-align`、`user-story`、`plan-feature`、`build-feature`、`build-and-review`、`auto-code-review`、`decision-handoff`、`code-review`、`dry-audit`、`design-audit` |
| agents（12） | review：`reviewer`、`story-lock-auditor`、`finding-verifier`、`dry-auditor`、`design-auditor`、`mutation-prover`；plan：`codebase-researcher`；build：`implementer`、`spec-gap-hunter`、`neighbor-finder`、`test-runner`；共用：`lessons-recaller` |
| hooks | `guard-rails`：擋直接 commit／push 保護分支、`git restore` 整檔退回、測試互撞等（規則見 `hooks/guard_rails.py` 開頭）；`agent_bash_guard`：依子 agent 類型限制 Bash 與寫檔（純讀的不能寫、跑測試的只能跑測試指令且必帶隔離 DB） |
| scripts | `backlog_check.py`（BACKLOG 單表 ↔ ticket 對帳）、`inc_brief.py`（從三文件抽一個 Inc 的 implementer brief）、`story_lock_check.py`（user story ↔ 測試對帳）、`lessons_index.py`（教訓索引）、`add_history_banner.py`（舊 feature 文件加「歷史文件」橫幅）、`scan_sensitive.sh`（公開前掃敏感字） |
| docs 範本 | `CONFIG.md`（設定表）、`LESSONS.md`（教訓格式）、`PRODUCT_PRINCIPLES.md`（產品原則）、`CONVENTIONS.md`（寫法慣例＋黃金樣本） |

### commands（你打的指令）

| command | 什麼時候打 | 做什麼 | 產出 | 會停下來問你的地方 |
|---|---|---|---|---|
| `/ticket [級別] <需求一句>` | 任何工作的第一步 | 只看入口層、一次一題釐清、提議級別；建 `features/<N>-<name>/ticket.md`（現況／預期／例子／接在哪／不做／完成條件／待拍）＋BACKLOG 一列；large 拆成母題＋互相連結的子題 | `ticket.md`、BACKLOG 一列 | 例子、級別、整張定稿 |
| `/user-story #N` | ticket 定稿後（small／medium） | 需求模式：讀 ticket、把狀態改「進行中」、派 `codebase-researcher` 寫現況快照、以快照為據寫白話 user story、逐則對照產品原則 | `research.md`、`user_story.md` | 一則範例的格式用詞；整份拍板；違反原則的則 |
| `/user-story #N`（同一句） | 實作與拍板都結束後 | 複查模式（資料夾裡已有 `plan.md` 就是它）：拿規劃前那份當底稿，對照 plan、test.md、每輪 review、commit 訊息逐則定稿、蓋戳；收尾回填下游 ticket 的「接在哪」、跨張決定寫回母題、狀態改「完成」 | 定稿的 `user_story.md`、結案的 ticket | 每則定稿 |
| `/plan-feature #N` | user story 拍板後；每次 `/clear` 用同一句重入 | 第一次：兩個正交架構方案（small 沒有真的不同的做法可跳過）；第二次：S1–S6 逐決策、寫 plan.md；第三次：detailed-plan、test.md、派 `spec-gap-hunter`、`story_lock_check` 對帳（small 最多 3 個 Inc） | `proposal.md`、`plan.md`、`detailed-plan.md`、`test.md` | 架構 A/B 裁決；每個 D 決策；spec gap 要不要補 |
| `/build-feature #N` | 想自己盯實作時 | 主 agent 只協調：每個 Inc 抽一份 brief、派一個 `implementer` 嚴格 TDD（一次一條 TC 先紅後綠），全套＋mutation 綠了才 commit（一 Inc 一顆）；新決策點不停、寫進 `decisions-pending.md` | commits、`decisions-pending.md` | 只在不可逆的事（刪資料 migration、push、碰別人在製品） |
| `/build-and-review #N` | 平常用這個 | 串接模式跑 `/build-feature` → 自動生 review 開工指令 → 全新 context 子 agent 跑 `/auto-code-review` → 合併報告 → 自動跑 `/decision-handoff` | 上面全部＋拍板 session 開工指令 | 同上 |
| `/auto-code-review` | 想單獨審一段 commit 範圍時 | 無人值守審查：派六個 review agent、修 finding 並 fixup 到引入它的那顆 commit、mutation 證明、寫教訓 | `code_reviews/<name>.md`、`decisions-pending.md` 追加、`lessons/` | 不停（`--ask` 才問） |
| `/decision-handoff #N` | 收工時（`/build-and-review` 會自動跑） | 實查現況、蒐集所有待拍板題、補齊 context，印下一個 session 的逐題拍板開工指令 | `decisions-pending.md`、開工指令 | 不停 |
| `/backlog-align` | 覺得 BACKLOG 跟實際對不上時 | 用 git 實查每一項的狀態（不照表上的文字相信），補漏改的狀態（表與 ticket 檔頭兩處）、結案的移表、列場外殘留，最後跑 `backlog_check.py` | 對齊的 BACKLOG、`BACKLOG-log.md` | 算不算結案的新形狀；要刪的殘留 |
| `/code-review` | 手動審目前的 diff | 單次審查，含範圍外改動與 research 契約對帳；也是 `reviewer` agent 用的標準 | findings 報告 | 拍板題 |
| `/dry-audit`、`/design-audit` | 懷疑重複規則或設計繞路時 | 分別掃「同一條業務規則寫了兩份」與「行為對但寫法繞」，列清單讓你逐條拍 | 排好序的清單 | 每條拍了才動工 |

### agents（command 派出去的子 agent）

| agent | 誰派、什麼時候 | 做什麼 | 回什麼 | 工具 |
|---|---|---|---|---|
| `codebase-researcher` | `/user-story` 需求模式 | 照固定順序讀（API 文件 → 測試名稱 → code＋決策標籤 → 沿標籤進 feature 文件），只記現況、不提方案 | `research.md`：有編號的契約表、隱含規則、舊文件不一致處、沒有測試鎖的行為 | 只讀 |
| `lessons-recaller` | `/plan-feature`、`/build-feature`、`/auto-code-review` 開工前 | 依模組與關鍵字翻 `lessons/`，再翻專案記憶的硬規則；太薄才翻舊 review | 最多十條「這次會踩到的教訓」＋怎麼套用 | 只讀 |
| `spec-gap-hunter` | `/plan-feature` S8、`/build-feature` Step 1 | 對七項死角清單找「有承諾、沒有鎖」的地方（邊界、並行、順序、跨表） | gap 清單＋建議 TC | 只讀 |
| `neighbor-finder` | `/build-feature` Step 3，慣例文件沒涵蓋時才派 | 找最相似的既有實作，回「照哪個檔哪個函式」；順便建議慣例該補哪條 | 樣本指標＋三行要點 | 只讀 |
| `implementer` | `/build-feature` 派工流程，每個 Inc 一個 | 讀 brief → spec-first → 嚴格 TDD 一次一條 TC → 只 lint 自己改的檔；同一條 TC 連 5 次紅就停手回報。不跑全套、不 commit、不派子 agent | 四狀態短回報（`DONE`／`DONE_WITH_CONCERNS`／`NEEDS_CONTEXT`／`BLOCKED`）＋完整 report 檔（介面、mutation 靶、新決策點） | 讀寫 code（跟主 agent 一樣不受 hook 限制） |
| `test-runner` | `/build-feature`、`/auto-code-review` 要跑測試時 | 用指定的那一行指令（隔離 DB）跑，幾百行輸出留在自己這邊。`model: haiku`（做錯會被下一步自動抓到的工作用輕量模型） | passed／failed 計數、每條紅的 nodeid＋第一行錯誤、是否基線就紅 | Bash 只准測試指令 |
| `reviewer` | `/auto-code-review` 每顆 commit | 以 `/code-review` 標準審，**要實跑探針重現**，違反慣例算 Low | `code_reviews/<name>.md`＋ findings 總表 | 讀＋寫報告目錄 |
| `story-lock-auditor` | `/auto-code-review`，與 reviewer 平行 | 三方對帳：user story 每一則 ↔ test.md 的 `[US n]` ↔ 測試裡實際的 assert；標 ⚠️ 暫定改寫的則以暫定為準 | 每則「鎖住／部分／沒鎖＋缺什麼」 | 只讀 |
| `finding-verifier` | `/auto-code-review`，每條 Critical／High | 對抗式驗證：「在現在的 code 這真的會發生嗎？給我重現輸入」，答不出就降級 | 維持／降級＋重現輸入 | 只讀 |
| `dry-auditor` | `/auto-code-review` §4b | 掃這顆 commit 動到的業務規則，往整個 codebase 追第二份出處 | 零疑慮可施工清單＋待拍板清單 | 只讀 |
| `design-auditor` | `/auto-code-review` §4b，dry-auditor 之後 | 看動到的函式形狀對不對得上業務規則，跟慣例文件的黃金樣本比 | 可施工清單＋待拍板清單 | 只讀 |
| `mutation-prover` | `/auto-code-review` §5，每條修正與鎖 | 實際改壞原始碼、跑相關測試檔一次、立刻還原；改完要 grep 確認突變真的在檔裡。每發只啟動一次 pytest（固定成本遠大於 TC 本身，實測 2.4×）。`model: sonnet`；每一發都要有實際 pytest 結果，主 agent 收到先驗完整 | 每發「被抓到／存活」 | 唯一會暫時改 src 的 agent，主 agent 前後拍快照兜底 |

分工原則：**找問題的 agent 不改 code，寫 code 的不審自己**（build 由 implementer 寫、review 由全新 context 的子 agent 審）；判斷類 agent 不設 `model`、跟主 agent 同一個模型；每個 agent 的 Bash 與寫檔範圍由 `hooks/agent_bash_guard.py` 依名字擋。
