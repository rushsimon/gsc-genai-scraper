# 前端接入说明

`scrape_genai.py` 只负责把数据写进 `genai_data.json`。要让你的看板**显示** Generative AI 报告，
还需在现有 dashboard 模板里加三样东西。下面假设你已有一个用 `DATA`（主数据）驱动的看板。

## 1. 注入数据：加一个占位符

在你的 build 脚本（把 JSON 注入 HTML 的那个）里，把 `genai_data.json` 注入成全局常量。
例如在 `build_html.py`（Python）中：

```python
import json, io
TPL = "dashboard_template.html"   # 你的模板
OUT = "dashboard.html"
GENAI = "genai_data.json"

with io.open(GENAI, "r", encoding="utf-8") as f:
    genai_payload = json.load(f)
inject_genai = "const GENAI = " + json.dumps(genai_payload, ensure_ascii=False) + ";"

with io.open(TPL, "r", encoding="utf-8") as f:
    html = f.read()
if "/*__GENAI__*/" not in html:
    raise SystemExit("ERROR: 模板缺少 /*__GENAI__*/ 占位符")
html = html.replace("/*__GENAI__*/", inject_genai)
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
```

并在模板 `<script>` 顶部放占位符：

```html
<script>
const DATA = /*__DATA__*/;   // 你原有的主数据
const GENAI = /*__GENAI__*/; // ← 新增：Generative AI 数据
```

## 2. 放面板 HTML

把 [`panel.html`](./panel.html) 的内容粘贴进模板里 GSC 面板所在区域（在 `renderGsc()` 渲染的容器内即可）。

## 3. 放渲染函数 + 图表守卫

把 [`renderGscGenAi.js`](./renderGscGenAi.js) 放进模板 `<script>`。它依赖以下辅助函数，
若你模板里没有，补上即可（这是本项目用的**最小实现**）：

```js
const $ = s => document.querySelector(s);
function fmt(n){ n = Number(n)||0; return n.toLocaleString('en-US'); }
function pct(x){ return ((Number(x)||0)*100).toFixed(1) + '%'; }
// 守卫式 Chart.js 封装：库缺失时不报错，确保其他数据照常显示
function drawChart(id, cfg){
  if (typeof Chart === 'undefined'){ console.warn('Chart.js 未加载, 跳过', id); return; }
  try { destroy(id); new Chart(document.getElementById(id), cfg); }
  catch(e){ console.warn('drawChart failed', id, e); }
}
function destroy(id){ try{ const c = Chart.getChart(id); if(c) c.destroy(); }catch(e){} }
```

> Chart.js 用本地文件引入最稳（CDN 离线会失败）：下载 `chart.umd.min.js` 放项目目录，
> 模板用 `<script src="chart.umd.min.js"></script>` 相对路径引用。

## 4. 调用

在 `renderGsc()`（或你的 GSC 渲染入口）里加一行：

```js
renderGscGenAi();
```

完成。刷新页面即可看到 🤖 Generative AI 面板（趋势 + Top 10 页面）。
