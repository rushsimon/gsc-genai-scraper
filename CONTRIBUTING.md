# 贡献指南（Contributing）

感谢你对 **GSC Generative AI 报告抓取模块** 感兴趣！下面是几条让改动顺利合入的规矩。

## 开发前准备

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt      # Windows
# 或：pip install -r requirements.txt
```

## 改动 `scrape_genai.py` 后必做（重要 ⚠️）

CI 的 **Syntax check** 步骤会对 `scrape_genai.py` 跑 `python -m py_compile`，
**任何语法错误都会直接让 CI 失败、PR 无法合入**。请务必在推送前本地先跑一遍：

```bash
python -m py_compile scrape_genai.py
```

> 本项目实战中就曾因一处 f-string 括号不匹配（`scrape_genai.py:304`）
> 被 CI 拦下——这种肉眼极易漏看的错，正是 CI 存在的意义。

## 本地跑抓取（可选，用于验证改动）

```bash
# 1. 先关掉 Chrome，否则 profile 被锁、复制失败
# 2. 跑
python scrape_genai.py
```

完整流程见 [README.md](README.md)。

## 不要提交真实数据 🔒

`.gitignore` 已排除 `genai_data.json`、`dashboard_data.json`、`*.bak`、
`.venv/`、诊断文件。**请勿用 `git add -f` 强制加入这些文件**——
它们包含你的个人站点列表与真实抓取结果，属隐私，不应进入公开仓库。

## 提交信息风格

| 前缀 | 用途 |
|---|---|
| `fix:` | 修 bug（例：`fix: f-string unbalanced paren in scrape_genai.py:304`） |
| `feat:` | 新功能 |
| `docs:` | 文档 |
| `ci:` | CI / 工作流改动 |

## 提 PR 流程

1. fork 或开分支
2. 本地 `python -m py_compile scrape_genai.py` 通过
3. 推到你的分支，开 PR
4. 等 **Validate** workflow 跑绿再合入

## 安全 / 隐私

脚本只读取你本地已登录的 Chrome profile **副本**，不向任何第三方发送数据。
