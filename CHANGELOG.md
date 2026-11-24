# Changelog

格式照 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)；版本號照 SemVer。

## [0.4.0] — 2026-11-24

所有工作改從 `/ticket` 進：一項工作一個資料夾、BACKLOG 改成可機械檢查的單表、流程指令改收 `#N`。**還沒用真實工作跑過一輪**，規則都已寫進 command。

### Added
- `commands/ticket.md`：立題。一句需求 → `<feature_dir>/<N>-<name>/ticket.md`（現況／預期／例子／預算與級別／接在哪／原文件／不做／完成條件／待拍＋最後一行開工指令）＋BACKLOG 一列。ticket 只寫要什麼與從哪接，**不寫解法**（先寫會限制更好的解法）。級別 tiny／small／medium／large；large 拆成一張母題（目標／子題與順序／共同決定 E 條）＋數張互相連結的子題。
- `commands/backlog-align.md`：用 git 實查每一項的實際狀態，補漏改的（表與 ticket 檔頭兩處）、結案的移表、列出場外殘留（使用者點頭才刪）。
- `scripts/backlog_check.py`＋6 條測試：表↔ticket 一一對應、無重號、兩處狀態一致、母題子題互連、相對連結不斷、表格無空行；印下一個可用編號。資料夾多包幾層也認。
- `docs/CONFIG.md`「資料夾分層與 BACKLOG」一節。

### Changed
- **`feature_dir` 的意思變了（breaking）**：從「單一 feature 的資料夾樣式 `features/<name>/`」改成「feature 根目錄 `features/`」；每項工作是 `<feature_dir>/<N>-<name>/`。舊的 `features/<name>/` 資料夾仍可用路徑餵給各指令，但不會出現在 BACKLOG。
- `/user-story`：收 `#N`，不再接一句需求、不再自己建資料夾。模式看資料夾內容（只有 `ticket.md`＝需求模式；有 `plan.md`＝複查模式）。需求模式先過兩道門（母題不實作；上游入口還沒回填或母題 E 條待拍就停）、把狀態改「進行中」；複查模式新增 Step 5 收尾：回填下游 ticket 的「接在哪」、標【跨張】的拍定題寫回母題成 E 條、狀態改「完成」移表。
- `/plan-feature`：收 `#N`、進場多讀 `ticket.md`（與母題的共同決定）。small 兩處分岔：S0.5 條件式（沒有兩個真的不一樣的做法就 D0 一行帶過、不寫 `proposal.md`）、detailed-plan 最多 3 個 Inc（超過就停、建議升 medium）。
- `/build-feature`：Step 0 讀 `ticket.md`（「不做」是範圍的籬笆）；有母題的 ticket，新決策點多判一句「另一張一定要跟著一樣嗎」，是就標【跨張】；BACKLOG 狀態不在這裡改。
- `/build-and-review`、`/decision-handoff`：收 `#N`；handoff 的開工指令最後提醒跑 `/user-story #N` 複查。
- 其餘 command／agent／script 的路徑寫法統一成 `<feature_dir>/<N>-<name>/`。
- README：流程圖、關卡表、責任表、使用示範都改成從 `/ticket` 開始。

## [0.3.0] — 2026-11-11

`/build-feature` 的主 agent 改成只協調：每個 Inc（＝一顆 commit）派一個 `implementer` 子 agent 寫 code。起因是一場真實 build：主 agent 自己做完 7 個 Inc，context 從 6 萬漲到 97 萬、auto-compact 兩次，cache_read 佔全部 token 約 3/4。改版後跑了四場真實 feature：主 agent 峰值 24～27 萬、0 次 compact，每顆 commit 的 token 約為原本一半。

### Added
- `agents/implementer.md`：一次只做一個 Inc。讀 brief → spec-first → 嚴格 TDD 一次一 TC → 只 lint 自己改的檔 → 寫完整 report 檔，只回短回報（`DONE`／`DONE_WITH_CONCERNS`／`NEEDS_CONTEXT`／`BLOCKED`）。不跑全套、不 commit、不派子 agent。**同一條 TC 連 5 次紅就停手**，寫清楚試了什麼，交給主 agent 判斷（防單次派工內無上限空轉）。
- `scripts/inc_brief.py`＋測試：從 detailed-plan 標題的 `（C<n>；plan …；US …）` 機械抽出該 Inc 的規格、TC、plan 決策列、user story 原文；主 agent 只手寫 ③「前面留下的」。重跑會保留 ③，並把 ③ 點名的 `test.md §<節>` 與 `D<n>.<m>` 小節原文抽成 ③'（實測：沒有 ③' 時 implementer 每次都得自己翻 test.md 的共用節）。
- `docs/CONFIG.md`「worktree＋symlink：要設 `additionalDirectories`」：副樹用 symlink 共用主樹目錄時，auto mode 會把經 symlink 的寫入當越界而停下。

### Changed
- `/build-feature` 新增「派工流程」節（抽 brief → 寫 ③ → 再跑一次腳本 → 派 implementer → 照四狀態處理 → test-runner 全套 → mutation-prover → 修正輪最多 3 輪續派同一個 → commit）；Step 2～5 改由 implementer 照做；回報格式與「絕對不要」同步改。`allowed-tools` 加 `SendMessage`。
- `/build-and-review` 第 1 段註明 build 由 implementer 寫；第 3 段派 review 的理由改寫。`allowed-tools` 加 `SendMessage`。
- 子 agent 分模型（判準：做錯會不會被下一步自動抓到）：`test-runner` 加 `model: haiku`、`mutation-prover` 加 `model: sonnet`；判斷類 agent 不設、跟主 agent 同模型。
- `agents/mutation-prover.md`：每一發都要有實際 pytest 結果，不准回 pending；交差回報要單獨一則訊息、不和還原或 pytest 同一則送出（實測：曾在同一則訊息送出還原與「pending」，pytest 一次都沒跑）。`/build-feature` 派工流程第 5 步與 `/auto-code-review` §5 都加「收回報先驗完整，缺的那幾發重派」。
- `/decision-handoff`：檔裡照舊寫完整 user story，**口頭講要短**（情境兩句 → A／B 各一行 → 建議一句 → 一行問句；不放表格、不講 code 路徑），使用者問才展開。
- README：command／agent 責任表加 `implementer`、模型分工；使用示範、目前的限制、未來優化表新增「build 主 agent 只協調」「子 agent 分模型」兩列。

## [0.2.1] — 2026-11-06

`mutation-prover` 提速：實測每次 pytest 啟動的固定成本（app import）遠大於 TC 本身，規則改成「一發一啟動」。同一組 3 靶實測 143.7 s → 60.3 s（2.4×），紅的 TC 集合不變。

### Added
- **mutation-prover 平行模式**：靶 ≥ 6 發時主 agent 用 `scripts/mp_worktree.sh` 開 N 棵拋棄式 worktree（含主樹未 commit 的修正），同時派 N 個 prover，各自 `<test_tree_env>` 掛進拋棄式容器＋自己的 DB 基底名。新設定鍵 `test_tree_env`，做法見 `docs/CONFIG.md`「別棵樹跑測試」。實測兩路並行 13.4 s vs 單路 11.2 s。

### Changed
- `/auto-code-review` §5 平行模式新增「何時開樹」：除了靶 ≥ 6 發，**主 agent 在 prover 跑的期間要動主樹時，靶再少也開 1 棵**（避免把改壞的碼夾進 commit）；開了樹只能往下一題走、不可回頭改正在驗的那題；不開樹時主 agent 要等 prover 標 completed 才動主樹。臨時派 prover（不在 /auto-code-review 裡）也照這節判斷，`agents/mutation-prover.md` description 同步註明。
- `agents/mutation-prover.md`：每發只跑一次測試（整檔而非單條 nodeid；整檔與單條同價）、worker 數一律 0（xdist 每個 worker 重 import，單 TC 反而慢一倍）、不加 `-x`；還原後**不重跑**，改以 `grep`＋`git diff --quiet -- <檔>` 雙重確認；只在存活時補跑該模組整個測試資料夾；整輪結束跑一次聯集回綠。新增「成本事實」一節，說明規則的依據。
- `/auto-code-review` §5：派工時加一行 worker 數 0；靶清單的 TC 欄可給測試檔；提醒別為了湊數開靶（靶數仍是主要變數）。

## [0.2.0] — 2026-11-05

流程改版：user story 前置、架構先比兩案、實作到審查全程不停。**還沒用真實 feature 跑過一輪**，規則都已寫進 command。

### Added
- `agents/codebase-researcher.md`：只讀的現況研究 agent，產出 `research.md`（每條現況有編號，後面所有文件引用編號）。
- `commands/decision-handoff.md`：把 build／review 期間 agent 自己選的決策整理成 `decisions-pending.md`，印出下一個 session 的逐題拍板開工指令。
- `hooks/agent_bash_guard.py`＋測試：依子 agent 類型（純讀／寫報告／跑測試）限制 Bash 與寫檔；接進 `hooks/hooks.json`。
- `scripts/add_history_banner.py`：給舊 feature 文件加「歷史文件」橫幅，避免 agent 把過時的 plan 當現況。
- `docs/PRODUCT_PRINCIPLES.md`、`docs/CONVENTIONS.md` 兩份範本；`docs/CONFIG.md` 新增 `product_principles_doc`、`conventions_doc`、`lessons_dir` 三個設定鍵與「寫檔規則」一節。

### Changed
- `/user-story` 分成**需求模式**（規劃前：派 researcher → 寫 story → 對照產品原則 → 拍板 → 交接給 `/plan-feature`）與**複查模式**（實作後逐則定稿、蓋戳）。權威順序改為「產品原則 > user story > plan 三文件」。
- `/plan-feature` 只接 feature 路徑、支援 `/clear` 後重入；新增 S0.5「兩個正交架構方案」（`proposal.md`、對照表、`D0`）；S8 寫 detailed-plan 後自掃空話與名稱一致、test.md 後派 `spec-gap-hunter`、收尾跑 `story_lock_check.py`。plan.md 範本加歷史橫幅、權威分工、`D0` 列。
- `/build-feature`：新決策點**不停**，當下寫進 `decisions-pending.md` 一題、選最好的做下去；只在不可逆的事（刪資料 migration、push、碰別人在製品）停。動筆前先讀 `conventions_doc` 黃金樣本，`neighbor-finder` 退為慣例沒涵蓋時才派。
- `/build-and-review` 收尾自動接 `/decision-handoff`；使用者只出手兩次（打指令、貼拍板開工指令）。
- `/auto-code-review` §7 的拍板題追加進同一份 `decisions-pending.md`。
- `/code-review` pre-check 加範圍外改動與 research 契約對帳。
- `reviewer`／`design-auditor`／`neighbor-finder`／`story-lock-auditor`／`lessons-recaller`／`mutation-prover` 依上述接線微調（違反慣例算 Low、暫定改寫以暫定為準、mutation-prover 不給 Edit）。
- README 流程圖、人工關卡、使用示範全部改寫成新流程。

### Fixed
- 無人值守會被 Claude Code 內建安全確認打斷的兩個來源（寫 `.claude/`、Bash heredoc 寫檔）：教訓庫預設路徑改為 `lessons/`（不在 `.claude/` 下），command 一律用 Write／Edit 寫檔。

## [0.1.0] — 2026-11-03

第一版：plan → user story → 嚴格 TDD → 多 agent 審查（finding 對抗驗證、mutation 實跑證明）。8 個 command、10 個 agent、guard-rails hook、對帳與索引腳本。
