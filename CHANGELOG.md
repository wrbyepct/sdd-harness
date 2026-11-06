# Changelog

格式照 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)；版本號照 SemVer。

## [0.2.1] — 2026-11-06

`mutation-prover` 提速：實測每次 pytest 啟動的固定成本（app import）遠大於 TC 本身，規則改成「一發一啟動」。同一組 3 靶實測 143.7 s → 60.3 s（2.4×），紅的 TC 集合不變。

### Added
- **mutation-prover 平行模式**：靶 ≥ 6 發時主 agent 用 `scripts/mp_worktree.sh` 開 N 棵拋棄式 worktree（含主樹未 commit 的修正），同時派 N 個 prover，各自 `<test_tree_env>` 掛進拋棄式容器＋自己的 DB 基底名。新設定鍵 `test_tree_env`，做法見 `docs/CONFIG.md`「別棵樹跑測試」。實測兩路並行 13.4 s vs 單路 11.2 s。

### Changed
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
