// renderGscGenAi.js — Generative AI 面板渲染函数
// 依赖（需在你的看板模板中已存在或自行补上）：
//   const GENAI = {...}        // 由 build 脚本注入 /*__GENAI__*/ 占位符（见 frontend/README.md）
//   const DATA  = {...}        // 看板主数据，需含 gsc_sites[]
//   let selected              // 当前下拉选中的站点（'__all__' = 全部站点）
//   $ (sel)                   // document.querySelector 简写，如 const $ = s => document.querySelector(s)
//   destroy(id)               // 销毁已存在的 chart 实例（防止重复渲染报错）
//   drawChart(id, cfg)        // 守卫式 Chart.js 封装（库缺失时不报错，见 frontend/README.md）
//   fmt(n) / pct(x)           // 数字 / 百分比格式化辅助
// 用法：把本函数放进模板 <script>，并在 renderGsc() 内调用 renderGscGenAi()。
function renderGscGenAi(){
  const panel = $('gscGenAiPanel');
  const G = (typeof GENAI !== 'undefined' && GENAI) ? GENAI : null;
  const meta = (G && G._meta) ? G._meta : {};
  const isSample = !!(meta.is_sample);

  // 收集当前视图（全部站点 / 单站点）下的 genai 条目
  let entries = [];
  if (selected === '__all__') {
    entries = DATA.gsc_sites.map(s => s.name)
      .map(n => (G && G[n]) ? Object.assign({site:n}, G[n]) : null).filter(Boolean);
  } else if (G && G[selected]) {
    entries = [Object.assign({site:selected}, G[selected])];
  }

  // 说明条
  const note = $('gscGenAiNote');
  if (isSample) {
    note.className = 'genai-note sample';
    note.innerHTML = '⚠️ <b>示例数据</b> — Search Console API 目前<b>尚未开放</b> Generative AI 报告数据（仅 GSC UI 可见），以下为占位示例。请运行 <code>scrape_genai.py</code>（一键 <code>run_genai.bat</code>）自动抓取；Google 开放 API 后本文件将被自动拉取覆盖，前端无需改动。';
  } else if (!entries.length) {
    note.className = 'genai-note';
    note.innerHTML = 'ℹ️ 当前视图暂无 Generative AI 数据。该数据由浏览器自动抓取（<code>scrape_genai.py</code> / <code>run_genai.bat</code>，API 暂未开放），请运行抓取脚本刷新，或手动编辑 <code>genai_data.json</code>。';
  } else {
    const upd = entries.map(e => e.updated_at).filter(Boolean).sort().pop();
    note.className = 'genai-note';
    note.innerHTML = `📥 来源：GSC Generative AI 报告（浏览器自动抓取 scrape_genai.py${upd ? ' · 更新于 <b>' + upd + '</b>' : ''}，API 暂未开放）。`;
  }

  if (!entries.length) {
    panel.style.display = '';
    destroy('gscGenAiTrend');
    $('gscGenAiKpis').innerHTML = '';
    $('gscGenAiTag').textContent = '无数据';
    $('gscGenAiPageBody').innerHTML = '<tr><td colspan="3" class="empty">该视图暂无 Generative AI 数据（API 未开放，请用 run_genai.bat 抓取）</td></tr>';
    return;
  }
  panel.style.display = '';

  // 趋势（按日期合并求和）
  const dmap = {};
  entries.forEach(e => (e.trend || []).forEach(t => { dmap[t.date] = (dmap[t.date] || 0) + (Number(t.impressions) || 0); }));
  const dates = Object.keys(dmap).sort();
  const totalImpr = dates.reduce((a, d) => a + dmap[d], 0);
  const peak = dates.length ? Math.max.apply(null, dates.map(d => dmap[d])) : 0;
  const peakDate = dates.length ? dates[dates.map(d => dmap[d]).indexOf(peak)] : '-';

  // Top 页面（跨站点合并、按 impressions 降序）
  const pmap = {};
  entries.forEach(e => (e.top_pages || []).forEach(p => { pmap[p.page] = (pmap[p.page] || 0) + (Number(p.impressions) || 0); }));
  const pages = Object.entries(pmap).map(([k, v]) => ({ page:k, impressions:v }))
    .sort((a, b) => b.impressions - a.impressions).slice(0, 10);

  // KPI
  $('gscGenAiKpis').innerHTML = `
    <div class="kpi"><div class="label">近 30 天 AI 展示总量</div><div class="value" style="color:var(--purple)">${fmt(totalImpr)}</div>
      <div class="sub">${entries.length} 个站点合计</div></div>
    <div class="kpi"><div class="label">单日峰值</div><div class="value">${fmt(peak)}</div><div class="sub">${peakDate ? peakDate.slice(5) : '-'}</div></div>
    <div class="kpi"><div class="label">有展示的页面</div><div class="value">${fmt(pages.length)}</div><div class="sub">Top 10 见下方</div></div>`;

  // 趋势图
  $('gscGenAiTag').textContent = `${dates.length} 天 · 共 ${fmt(totalImpr)} 次展示`;
  drawChart('gscGenAiTrend', { type:'line',
    data:{ labels: dates.map(d => d.slice(5).replace('-', '/')),
      datasets:[{ label:'AI Impressions', data: dates.map(d => dmap[d]),
        borderColor:'#b083f0', backgroundColor:'rgba(176,131,240,.12)', fill:true,
        tension:.35, pointRadius:0, borderWidth:2 }]},
    options:{ responsive:true, maintainAspectRatio:false,
      interaction:{ mode:'index', intersect:false },
      plugins:{ legend:{display:false},
        tooltip:{ callbacks:{ label:(c)=>` AI 展示: ${fmt(c.parsed.y)}` } } },
      scales:{ x:{ticks:{color:'#8b98b8', maxTicksLimit:10}, grid:{color:'rgba(38,49,77,.4)'}},
        y:{ticks:{color:'#8b98b8'}, grid:{color:'rgba(38,49,77,.4)'}, beginAtZero:true} } } });

  // Top 10 表
  $('gscGenAiPageBody').innerHTML = pages.length ? pages.map((p, i) => `
    <tr>
      <td title="${p.page}">${i+1}. ${p.page.replace(/https?:\/\//, '').slice(0, 80)}</td>
      <td class="num" style="font-weight:600">${fmt(p.impressions)}</td>
      <td class="num">${pct(p.impressions / (totalImpr || 1))}</td>
    </tr>`).join('')
    : `<tr><td colspan="3" class="empty">暂无页面级数据</td></tr>`;
}
