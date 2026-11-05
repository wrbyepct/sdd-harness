# Harness config

這套 harness 的 command 和 agent 不寫死任何專案路徑或指令。凡是「這個專案怎麼跑測試、文件放哪」的事，
都從專案 `CLAUDE.md` 的 `## Harness config` 段讀取。安裝 plugin 後，把下面這段貼進你的 `CLAUDE.md`，改成自己的值。

```markdown
## Harness config

| key | 值 | 說明 |
|---|---|---|
| `base_branch` | `main` | feature 分支要合回的分支；review 範圍＝`<base_branch>..HEAD` |
| `feature_dir` | `features/<name>/` | 每個 feature 的四文件（plan／detailed-plan／test／user_story）放哪；按版本分可寫 `features/v<version>/<name>/` |
| `test_cmd` | `./run test` | 跑測試的指令，可接路徑或 pytest 參數 |
| `isolated_db_env` | `PYTEST_DB_BASE` | 換測試 DB 名稱的環境變數；無人值守的 build／review 一律帶它，避免踩到你手上正在跑的測試 |
| `isolated_db_build` | `app_test_bf` | `/build-and-review` 實作段用的隔離 DB 名 |
| `isolated_db_review` | `app_test_cr` | `/auto-code-review` 用的隔離 DB 名 |
| `test_workers_env` | `PYTEST_WORKERS` | 控制平行 worker 數的環境變數（沒有就留空） |
| `test_busy_check` | `docker top api \| grep pytest` | 「現在有沒有別人在跑測試」的檢查指令（沒有就留空） |
| `lint_cmd` | `uvx pre-commit run --all-files` | lint／型別檢查 |
| `openapi_check_cmd` | `python -c "from app.main import app; app.openapi()"` | 產生 OpenAPI 的指令；端點契約有動就必跑，看**裸 exit code** |
| `api_doc_guide` | `docs/API_DOC_FORMAT.md` | Swagger／API 文件格式的唯一權威 |
| `gotchas_docs` | `docs/SQLALCHEMY_GOTCHAS.md, docs/ALEMBIC_GOTCHAS.md` | 長篇踩雷文件（lessons-recaller 會依 area 打開） |
| `protected_branches` | `main, master` | guard-rails hook 不准直接 commit／push 的分支（逗號分隔；沒設＝`main, master`；設 `-` 關掉） |
| `memory_index` | `memories/MEMORY.md` | 專案長期記憶索引（沒有就留空） |
| `product_principles_doc` | `docs/PRODUCT_PRINCIPLES.md` | 產品原則（範本見 `docs/PRODUCT_PRINCIPLES.md`）；`/user-story` 逐則對照、`/plan-feature` S0.5 當常駐第一 driver。沒有就留空，對照表那列寫「無文件」 |
| `conventions_doc` | `docs/CONVENTIONS.md` | 寫法慣例＋黃金樣本（範本見 `docs/CONVENTIONS.md`）；`/build-feature` 動筆前先讀，`reviewer` 違反算 Low。沒有就留空，`neighbor-finder` 退回每次翻隔壁 |
| `lessons_dir` | `lessons/` | 教訓庫目錄（格式見 `docs/LESSONS.md`）。**不要放在 `.claude/` 底下**：寫 `.claude/` 會觸發 Claude Code 內建的安全確認，無人值守會停 |
```

## 寫檔規則（建議貼進 CLAUDE.md）

無人值守的 `/build-and-review` 會被 Claude Code 內建的安全確認打斷的，實查只有兩種：寫 `.claude/` 底下的檔，
以及用 Bash heredoc（`cat > f <<EOF`、`tee`、`echo >>`、`sed -i`）寫檔。所以：

- 寫檔一律用 Write／Edit 工具；Bash 只拿來跑指令。
- 教訓庫、decisions-pending、review 報告都放在 `.claude/` 外面。

## 裝完要做的兩件事

1. **把你的 `test_cmd`、`lint_cmd`、`test_busy_check` 加進權限白名單**（`.claude/settings.json` 的 `permissions.allow`，例如 `"Bash(./run test:*)"`）。
   command 的 `allowed-tools` 沒辦法預先知道你的指令長怎樣；沒加的話，無人值守的 `/build-and-review` 會卡在權限提示。
2. 選配：如果專案有 backlog 檔（例如 `features/BACKLOG.md`），`spec-gap-hunter` 會讀它找跨 feature 的接縫；沒有就跳過，不用設定。

## 這套 harness 自己會建立的目錄

| 目錄 | 誰寫 | 內容 |
|---|---|---|
| `features/<name>/` | `/user-story`、`/plan-feature`、`/build-feature`、`/decision-handoff` | `research.md`（現況快照）、`user_story.md`、`proposal.md`（兩個架構方案與裁決）、`plan.md`、`detailed-plan.md`、`test.md`、`decisions-pending.md`（實作與 review 期自己選的決策，等你拍板） |
| `code_reviews/` | `reviewer` agent | 每一輪 review 一份報告 |
| `lessons/` | `/auto-code-review` §7、`/build-feature` 收尾 | 一則一檔的教訓庫＋`INDEX.md`，由 `lessons-recaller` 召回 |
| `logs/` | `test-runner` agent | 測試完整輸出 |
