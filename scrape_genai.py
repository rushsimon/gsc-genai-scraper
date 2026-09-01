# -*- coding: utf-8 -*-
"""
scrape_genai.py — 用浏览器自动化把 GSC「Generative AI」报告(全站)抓进 genai_data.json

背景：GSC 公开 API(searchanalytics.query) 不开放 Generative AI 维度, 只能用网页 UI 拿。
本脚本把用户已登录的 Chrome profile(连同正确目录布局)复制到临时目录, 用 Playwright 以
真正的 Google Chrome 二进制启动(headless), 循环各站点, 打开 Generative AI 报告,
抓取「近 28 天 AI Impression 趋势」+「Top 10 AI Impression 页面」。

关键坑(已逐一解决)：
- Chrome 127+ App-Bound Encryption：只能用 Google Chrome 本体二进制 + 正确 profile 布局,
  故用 executable_path=CHROME_EXE + 复制整个 User Data 布局(根 Local State + Default/)到临时目录启动。
- 复制时需 Chrome 已关闭(否则 Network/Cookies 被锁)。
- **响应体必须在主线程读取**(绝不能在 page.on("response") 回调里调 resp.body(),
  会触发 "Target page/context closed" 竞态, 间歇失败)。改为：回调只收集 response 对象,
  等网络稳定后在主线程 drain() 读取 body。这是本脚本能稳定跑通的核心修复。
- **OLiH4d(趋势)初次加载可能很慢/不触发**：先轮询至多 25s；若仍无, 点击『28 days』单选
  触发重新拉取(默认范围本就是 28 天, 点击幂等, 同时保证数据到位)。
- 趋势来自 batchexecute 的 OLiH4d rpc(每日 [epoch, [impressions]] 序列)；
  Top 页面来自同批响应里的 nDAfwb rpc(页面行 [url_cell, [null, impressions, ...]])。
  两者都从网络解析, 不依赖 DOM 懒加载, 稳定且快。

数据格式(写入 genai_data.json)：
  { _meta:{is_sample,api_available,updated_at,howto},
    "<站点名>": { updated_at, trend:[{date,impressions}], top_pages:[{page,impressions}] } }

用法(需先关掉 Chrome)：
  run_genai.bat                 # 全站抓取, 写入 genai_data.json(合并, 先备份)
  python scrape_genai.py --limit 3
  python scrape_genai.py --site example.com
  python scrape_genai.py --profile Profile1   # 若 GSC 会话在别的 profile
  python scrape_genai.py --dry-run             # 诊断: dump 解析结果, 不写文件
  python scrape_genai.py --site-url https://example.com/ --only-extra   # 仅补抓指定站, 不依赖 dashboard_data.json

环境变量：
  GENAI_PROXY  浏览器代理地址(默认 http://127.0.0.1:7897；中国大陆访问 Google 通常需要)
"""
import os, sys, io, json, time, shutil, tempfile, urllib.parse, datetime, argparse
from json import JSONDecoder

ROOT = os.path.dirname(os.path.abspath(__file__))
PROXY = os.environ.get("GENAI_PROXY", "http://127.0.0.1:7897")
CHROME_PROFILE = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")  # 根(含 Local State)
CHROME_EXE = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
PROFILE_NAME = "Default"
SITES_JSON = os.path.join(ROOT, "dashboard_data.json")
OUT_JSON = os.path.join(ROOT, "genai_data.json")
SITE_REPORT_URL = "https://search.google.com/search-console/performance/search-analytics/ai?resource_id={rid}"


def log(*a):
    print("[scrape]", *a, flush=True)


def site_domain_of(url):
    """从 GSC 站点 URL 取出用于匹配页面 URL 的域名。
    sc-domain:aigcfomo.com -> aigcfomo.com ; https://aigcfomo.com/ -> aigcfomo.com
    """
    if url.startswith("sc-domain:"):
        return url[len("sc-domain:"):]
    try:
        return urllib.parse.urlparse(url).netloc or url
    except Exception:
        return url


# --------------------------------------------------------------------------- #
# 解析: batchexecute 响应 -> 趋势 / 页面
# --------------------------------------------------------------------------- #
def _decode_rpc(body, rpcid):
    """从响应体找到 rpcid 数据字符串并 json.loads。返回对象或 None。"""
    marker = '"%s","' % rpcid
    i = body.find(marker)
    if i < 0:
        return None
    j = i + len(marker) - 1  # 指向数据字符串的开引号
    try:
        data_str, _ = JSONDecoder().raw_decode(body[j:])
        return json.loads(data_str)
    except Exception:
        return None


def parse_trend(body):
    """OLiH4d -> [(date_str, impressions), ...] 或 []。"""
    data = _decode_rpc(body, "OLiH4d")
    if not data:
        return []
    series = None

    def find_series(o):
        if isinstance(o, list):
            if (len(o) >= 5 and all(isinstance(x, list) and len(x) >= 2
                                    and isinstance(x[0], int) and x[0] > 1.7e12 for x in o)):
                return o
            for x in o:
                r = find_series(x)
                if r:
                    return r
        return None

    series = find_series(data)
    if not series:
        return []
    out = []
    for pt in series:
        epoch = pt[0]
        val = pt[1][0] if isinstance(pt[1], list) and pt[1] else 0
        try:
            d = datetime.datetime.fromtimestamp(epoch / 1000, datetime.UTC).strftime("%Y-%m-%d")
        except Exception:
            d = str(epoch)
        out.append({"date": d, "impressions": int(val)})
    return out


def parse_pages(body, site_domain):
    """nDAfwb -> [(url, impressions), ...] 去重(同 url 取最大), 按 impressions 降序。"""
    results = {}
    start = 0
    while True:
        i = body.find('"nDAfwb","', start)
        if i < 0:
            break
        start = i + 1
        data = _decode_rpc(body[i:], "nDAfwb")
        if not data:
            continue

        def walk(o):
            if isinstance(o, list):
                if (len(o) == 2 and isinstance(o[0], list) and isinstance(o[1], list)
                        and len(o[1]) > 1 and isinstance(o[1][1], int)):
                    url = None
                    for x in o[0]:
                        if isinstance(x, str) and x.startswith("http") and site_domain in x \
                                and "sitemap" not in x and "support.google.com" not in x:
                            url = x
                            break
                    if url:
                        imp = o[1][1]
                        if url not in results or imp > results[url]:
                            results[url] = imp
                for x in o:
                    walk(x)
        walk(data)
    return sorted(results.items(), key=lambda kv: kv[1], reverse=True)


# --------------------------------------------------------------------------- #
# 浏览器/站点
# --------------------------------------------------------------------------- #
def load_sites(limit=None, only=None, extra_urls=None, only_extra=False):
    sites = []
    try:
        d = json.load(open(SITES_JSON, encoding="utf-8"))
    except Exception:
        if not extra_urls:
            raise
        log("（未找到 %s, 仅用 --site-url 指定的站）" % SITES_JSON)
        d = {}
    for s in d.get("gsc_sites", []):
        url = s.get("site_url") or s.get("site") or ""
        if not url:
            continue
        name = s.get("name") or url
        if only and only not in (url, name):
            continue
        sites.append((name, url))
    # 额外显式站点(不污染 dashboard_data.json): 用于补抓核心站/漏网站
    for url in (extra_urls or []):
        name = site_domain_of(url)
        if only and only not in (url, name):
            continue
        if (name, url) not in sites:
            sites.append((name, url))
    # 只抓额外站点(跳过 gsc_sites, 避免全量重抓)
    if only_extra and extra_urls:
        return [(site_domain_of(u), u) for u in extra_urls]
    if limit:
        sites = sites[:limit]
    return sites


def copy_layout(src_ud, dst_ud, profile=PROFILE_NAME):
    """复制正确布局: 根 Local State + 指定 profile/(排除大缓存), 到临时非默认目录。"""
    os.makedirs(dst_ud, exist_ok=True)
    ls = os.path.join(src_ud, "Local State")
    if os.path.exists(ls):
        shutil.copy2(ls, os.path.join(dst_ud, "Local State"))
    src_p = os.path.join(src_ud, profile)
    dst_p = os.path.join(dst_ud, profile)
    exclude = ("Cache", "GPUCache", "Code Cache", "Service Worker", "optimization_guide",
               "ShaderCache", "GrShaderCache", "SubjectivityDataSource", "Subresource Filter",
               "OnDeviceHeadSuggestModel", "MEIPreload", "Web Storage", "VideoDecodeStats",
               "Search Engines", "Segmentation", "Crashpad")
    shutil.copytree(src_p, dst_p, ignore=shutil.ignore_patterns(*exclude), dirs_exist_ok=True)
    log("profile 布局复制完成:", dst_ud, "| cookie:",
        os.path.exists(os.path.join(dst_p, "Network", "Cookies")))


def setup_browser(pw, profile_dir):
    return pw.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        executable_path=CHROME_EXE,
        headless=True,
        proxy={"server": PROXY},
        args=[f"--profile-directory={PROFILE_NAME}", "--no-first-run",
              "--no-default-browser-check", "--disable-blink-features=AutomationControlled",
              "--proxy-bypass-list=<-loopback>"],
    )


def drain(resps, store):
    """主线程读取收集到的响应体, 把最新 OLiH4d/nDAfwb 存进 store。"""
    for r in resps:
        try:
            s = r.body().decode("utf-8", "replace")
        except Exception:
            continue
        for rid in ("OLiH4d", "nDAfwb"):
            if '"%s","' % rid in s:
                store[rid] = s
    resps.clear()


def click_28_days(page):
    """尝试把时间范围设为 28 days(幂等)。成功返回 True。"""
    selectors = [
        lambda: page.get_by_role("radio", name="28 days").first.click(timeout=5000),
        lambda: page.locator('[aria-label="Select time range"]').get_by_text("28 days", exact=True).click(timeout=5000),
        lambda: page.locator('button:has-text("28 days")').first.click(timeout=5000),
    ]
    for sel in selectors:
        try:
            sel()
            return True
        except Exception:
            continue
    return False


def wait_and_pull(page, resps, store, site_domain, dry_run=False):
    """等待报告加载, 尽量把范围统一到 28 天(点 28 days, 不清除已捕获数据), 解析 trend + pages。
    返回 (trend, pages, note)。
    """
    # 1) 初始轮询 OLiH4d(任意范围)
    for _ in range(60):  # 30s
        if "OLiH4d" in store:
            break
        time.sleep(0.5)
    pre = len(parse_trend(store.get("OLiH4d", "")))
    note = ""
    if click_28_days(page):
        note = "clicked 28 days"
        # 等刷新后的 OLiH4d: 达到 ~28 天, 或点数相比点击前发生变化(说明已重新拉取), 或超时
        for _ in range(40):  # 20s
            t = parse_trend(store.get("OLiH4d", ""))
            if len(t) >= 27 or len(t) > pre:
                break
            time.sleep(0.5)
    else:
        note = "28 days click failed(沿用默认范围)"
    drain(resps, store)
    if dry_run:
        log("  store keys:", list(store.keys()),
            "| nDAfwb len:", len(store.get("nDAfwb", "")))
        open(os.path.join(ROOT, "diag_nDAfwb_body.txt"), "w", encoding="utf-8").write(store.get("nDAfwb", ""))
    trend = parse_trend(store.get("OLiH4d", ""))
    pages = parse_pages(store.get("nDAfwb", ""), site_domain_of(site_domain))
    if dry_run:
        log("  trend 点数=%d(pre=%d) 范围=%s..%s | pages=%d | %s" %
            (len(trend), pre, trend[0]["date"] if trend else "-", trend[-1]["date"] if trend else "-",
             len(pages), note))
        if trend:
            log("  trend 示例:", trend[:3], "...", trend[-2:])
        if pages:
            log("  pages 示例:", pages[:3])
    return trend, pages, note


def run(limit, only, dry_run, profile_name, extra_urls=None, only_extra=False):
    global PROFILE_NAME
    PROFILE_NAME = profile_name
    from playwright.sync_api import sync_playwright

    sites = load_sites(limit, only, extra_urls, only_extra)
    log(f"待处理站点: {len(sites)} | profile={profile_name} | 解释器={sys.executable}")

    profile_dir = tempfile.mkdtemp(prefix="gsc_ud_")
    copy_layout(CHROME_PROFILE, profile_dir, profile_name)
    results = {}
    try:
        with sync_playwright() as pw:
            ctx = setup_browser(pw, profile_dir)
            page = ctx.new_page()
            resps = []
            store = {}
            page.on("response", lambda r: resps.append(r) if "batchexecute" in r.url else None)

            for name, url in sites:
                rid = urllib.parse.quote(url, safe="")
                target = SITE_REPORT_URL.format(rid=rid)
                log(f"→ {name} ({url})")
                store.clear()
                resps.clear()
                try:
                    page.goto(target, timeout=30000, wait_until="domcontentloaded")
                except Exception as e:
                    log("  goto 失败:", str(e)[:120])
                    results[name] = {"error": str(e)[:200]}
                    continue
                # 登录检查
                if "accounts.google.com" in page.url:
                    log("  ⚠️ 跳登录(会话失效/该 profile 无 GSC 会话)。")
                    results[name] = {"error": "login_required"}
                    if dry_run:
                        break
                    continue
                trend, pages, note = wait_and_pull(page, resps, store, url, dry_run)
                if not trend and not pages:
                    results[name] = {"empty": True, "updated_at": datetime.date.today().isoformat(), "note": note}
                    log("  无数据(可能该站无 Generative AI 报告)。")
                    continue
                results[name] = {
                    "updated_at": datetime.date.today().isoformat(),
                    "trend": trend,
                    "top_pages": [{"page": u, "impressions": i} for u, i in pages[:10]],
                }
            ctx.close()
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)

    if not dry_run and results:
        merge_into_out(results)
    log("完成。")


def merge_into_out(results):
    # 写入前先备份
    if os.path.exists(OUT_JSON):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = OUT_JSON + f".pre_genai_{ts}"
        shutil.copy2(OUT_JSON, bak)
        log("已备份:", bak)
    data = {}
    if os.path.exists(OUT_JSON):
        try:
            data = json.load(open(OUT_JSON, encoding="utf-8"))
        except Exception:
            data = {}
    meta = data.get("_meta", {})
    meta["source"] = "GSC Generative AI 报告(浏览器自动化抓取)"
    meta["api_available"] = False
    meta["is_sample"] = False
    meta["updated_at"] = datetime.date.today().isoformat()
    meta["howto"] = "由 scrape_genai.py 自动抓取写入; Google 开放 API 后可由后端覆盖, 前端无需改动。"
    data["_meta"] = meta
    for name, val in results.items():
        data[name] = val
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log("已写入/合并:", OUT_JSON, "| 站点数:", len([k for k in data if k != "_meta"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--site", default=None)
    ap.add_argument("--dry-run", action="store_true", help="诊断模式: 打印解析结果, 不写文件")
    ap.add_argument("--profile", default="Default", help="Chrome profile 目录名(默认 Default)")
    ap.add_argument("--site-url", action="append", default=None,
                    help="显式补抓的 GSC 站点 URL(如 https://example.com/ 或 sc-domain:example.com), "
                         "可多次; 不写入 dashboard_data.json")
    ap.add_argument("--only-extra", action="store_true",
                    help="只抓 --site-url 指定的站, 跳过 gsc_sites(避免全量重抓)")
    a = ap.parse_args()
    run(a.limit, a.site, a.dry_run, profile_name=a.profile, extra_urls=a.site_url, only_extra=a.only_extra)
