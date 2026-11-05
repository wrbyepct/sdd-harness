# Changelog

格式照 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)；版本號照 SemVer。

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
