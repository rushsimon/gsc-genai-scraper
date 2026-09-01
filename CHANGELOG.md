# 更新日志 / Changelog

本文件记录仓库对外发布的关键节点。内部数据管线改动不在此列。

## v1.0.0 (2026-09-01)

首次公开发布，让任何人都能在自己的 GSC Dashboard 接入 **Generative AI（AI Overviews / AI Mode）展示量**报告。

- 新增 `scrape_genai.py` + 一键 `run_genai.bat`：Playwright 复用已登录 Chrome，批量抓取全部 GSC 站点的 GenAI 趋势与 Top 页面（rpcid `OLiH4d` / `nDAfwb`）。
- 新增 `frontend/`：面板 HTML + `renderGscGenAi.js` + 接入说明，三步注入看板。
- 新增 `.gitignore`：排除真实抓取数据（`genai_data.json` / `dashboard_data.json`）与 venv，防止个人数据误提交。
- 新增 `example/dashboard_data.example.json`：最小可运行示例。
- 新增中/英文 README（`README.md` / `README.en.md`）、架构图 `architecture.svg`、效果截图 `docs/panel.png`。
- 新增 `LICENSE`（MIT）。
- 新增 WorkBuddy 用户级技能 `skills/gsc-genai-scraper/SKILL.md`。
- 新增 `.github/workflows/validate.yml`：每次 push/PR 自动 `py_compile` + 抽查关键文件齐全。

## 修复 (2026-09-01，紧随 v1.0.0)

- **fix**：`scrape_genai.py:304` f-string 括号不匹配（`({url)` → `({url})`）。
  由 CI 在合并前自动拦截——印证了静态校验门禁的价值。
- **docs**：两份 README 加回 CI 状态徽章；新增中/英文 `CONTRIBUTING.md`，固化「改完脚本先 `python -m py_compile` 再推」的规矩。
