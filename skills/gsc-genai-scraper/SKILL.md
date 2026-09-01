---
name: gsc-genai-scraper
description: 在 GSC Dashboard 接入 Generative AI（AI Overviews/AI Mode 展示量）报告。当 Search Console API 不开放该数据、且站点较多无法手动导出 CSV 时使用：用 Playwright 复用已登录 Chrome 会话批量抓取 GSC Generative AI 报告页，解析网络响应得到每日趋势+Top10 页面，写入看板。
agent_created: true
---

# GSC Generative AI 报告浏览器抓取

## 适用场景
用户想在 GSC Dashboard 展示 **Generative AI** 报告（AI Overviews / AI Mode 展示量趋势 + Top10 页面），但：
- Search Console **Data API 不开放**该数据（`searchanalytics.query` 的 `searchAppearance` 维度无 `AI_OVERVIEW`/`AI_MODE`/`GENERATIVE_AI` 取值）——别再试 API。
- 站点多（几十个），手动从 GSC 后台导出 CSV 不现实。
→ 唯一可行路线：**Playwright 复用已登录 Chrome 会话，批量抓取每个站的 GenAI 报告页，解析 Network 响应**。

## 核心原理（已实测）
GSC Generative AI 报告页的数据藏在 `batchexecute` 的 Network 响应里：
- **`OLiH4d`** = 每日 AI Impression 趋势（series：`[epoch_ms(int>1.7e12), [impressions], null...]`）
- **`nDAfwb`** = Top 页面表（rows：`[url_cell_list, [null, impressions, ...]]`）
- ⚠️ `czrWJf`/`B2IOAd`/`xDwXKd` 是**普通 Search 性能**，不是 GenAI，别混淆。
纯网络解析，不碰 DOM（稳定，不受懒加载影响）。

## 关键坑（务必先讲清再动手）
1. **Chrome 127+ App-Bound Encryption**：cookie 只在 genuine Chrome 二进制 + 正确 profile 布局下才能解密。必须用 `executable_path=真实chrome.exe` + 启动前把 `%LOCALAPPDATA%\Google\Chrome\User Data` 的 `Local State` + `Default/` 复制到 temp 目录 + `launch_persistent_context`。运行前**必须完全关闭 Chrome**（`taskkill /F /IM chrome.exe`），否则 profile 复制锁文件报 `WinError 32`。
2. **绝不在 `page.on('response')` 回调里读 `resp.body()`** —— 与导航竞态，间歇报 `Response.body: Target page, context or browser has been closed` 导致数据丢失。正确做法：回调只把 `resp` 对象 append 到列表，网络稳定后**在主线程 `drain()` 里读 body**。
3. **时间范围不一致**：各站默认范围不同（7/28 天）。每次**强制点「28 days」**（`role=radiogroup` `aria-label="Select time range"` 的 radio），且**不要清空已收集的 store**，等 `len(trend)>=27 or 数量变多` 再读。
4. **`sc-domain:foo.com` 前缀**：Top 页面 URL 是 `https://foo.com/...`，不含 `sc-domain:` 字符串 → 用 `site_domain_of()` 剥前缀成 `foo.com` 再匹配，否则 Top10 全 0。
5. **会话/账号**：抓取用的 Chrome 必须登录**持有这些 GSC 属性的 Google 账号**。中途切账号 → 跳登录（`login_required`），补抓失败。
6. **代理**：浏览器 + git/curl 访问 Google 需代理（本机 `http://127.0.0.1:7897`）；git push 经代理需 `GIT_HTTP_CONNECT_TIMEOUT=60` 否则 ~2s 超时 SIGTERM。

## 标准流程
1. 准备看板：已有 `dashboard_data.json`（`gsc_sites` 站点列表）+ 模板含 `renderGscGenAi()` 与 `/*__GENAI__*/` 注入点。
2. 放脚本：`scrape_genai.py`（读 `gsc_sites` → 抓 `OLiH4d`+`nDAfwb` → 写 `genai_data.json`，备份后写、设 `_meta.is_sample=false`）+ `run_genai.bat`。Playwright 装独立 venv（如 `C:/Users/suson/.workbuddy/binaries/python/envs/pw`）。
3. 关 Chrome → 跑 `run_genai.bat`（约 35–40s/站）。
4. 补抓/重抓：`scrape_genai.py --site <名>`（单站）；`--site-url https://某站/ --only-extra`（补核心站且不重抓全量）。
5. 重建看板：`python build_html.py` 把 `genai_data.json` 注入 `dashboard.html`。
6. 维护：以后刷新只跑 `run_genai.bat` + `build_html.py`；保持 Chrome 登录目标账号。

## 发布给团队复用
- 建独立子目录 `genai-scraper/`，`git init -b main`，提交 `scrape_genai.py / run_genai.bat / requirements.txt / README.md / .gitignore / example/ / frontend/`（面板 HTML + 渲染函数 + 接入说明）。**`.gitignore` 排除 `genai_data.json` 等真实数据**。
- 推 GitHub：`gh auth login` 需 PAT 带 `read:org`（否则失败）。无该 scope 时绕过：用 REST API `POST https://api.github.com/user/repos`（仅需 `repo`）建仓库，再 `git -c http.proxy=... -c url.<user:PAT>@github.com/.insteadOf=https://github.com/ push -u origin main`，推完 `git remote set-url origin https://github.com/<user>/<repo>.git` 还原干净地址。
- 一次性 PAT 用完在 GitHub Settings→Tokens 撤销。

## 参考仓库（已发布）
https://github.com/rushsimon/gsc-genai-scraper
