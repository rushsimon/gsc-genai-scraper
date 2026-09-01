# GSC Generative AI Report Scraper

> [![Validate](https://github.com/rushsimon/gsc-genai-scraper/actions/workflows/validate.yml/badge.svg)](https://github.com/rushsimon/gsc-genai-scraper/actions/workflows/validate.yml)

> Add a **Generative AI (AI Overviews / AI Mode) Impression report** to any GSC Dashboard.
> Because Google's public Search Console API **does not expose** this dimension yet, this project
> uses Playwright to reuse your already-logged-in Chrome session, scrape the GenAI report page for
> every site, parse the network responses, write the data into `genai_data.json`, and let the
> frontend render it.

## Why browser scraping (read this first)

Google Search Console's "Generative AI" report (AI Overviews / AI Mode impressions) is **only visible
in the web UI (Beta)**. The `searchanalytics.query` API's `searchAppearance` dimension has no AI-related
value. So:

- ❌ **No API pull** (industry-confirmed: the API is not open for this yet)
- ❌ **Manual per-site CSV export** is unrealistic when you have many sites (dozens)
- ✅ **The only viable route**: use Playwright to reuse your logged-in Chrome and loop over all sites (this repo's approach)

## Features

- Auto-loops every site in `gsc_sites` inside `dashboard_data.json`
- Scrapes each site's last **28-day AI Impression trend** (daily series)
- Scrapes each site's **Top 10 AI Impression pages** (URL + Impressions)
- Supports `--site-url` to scrape any site independently (without polluting your site list)
- Data goes to a standalone `genai_data.json` (independent of the main pipeline, won't be overwritten on refresh)
- Auto-backup before writing

## Directory layout

```
genai-scraper/
├── scrape_genai.py            # core scraper (Playwright)
├── run_genai.bat              # one-click full scrape (Windows)
├── requirements.txt           # playwright==1.62.0
├── .gitignore                 # excludes real data & secrets
├── example/
│   └── dashboard_data.example.json   # minimal site-list example
├── frontend/
│   ├── panel.html             # panel HTML (paste into your template)
│   ├── renderGscGenAi.js      # render function
│   └── README.md              # frontend integration steps
├── architecture.svg           # architecture / data-flow diagram
├── README.md                  # Chinese version
└── README.en.md               # this file
```

## Prerequisites

| Item | Requirement |
|---|---|
| Account | Chrome logged into the **Google account that owns these GSC properties** |
| Network | Browser must reach Google (in mainland China a proxy is needed; default `http://127.0.0.1:7897`, override with `GENAI_PROXY`) |
| Runtime | Python 3.10+; Playwright (`pip install -r requirements.txt`) |
| Chrome | **Google Chrome** installed (not Chromium) — needed to bypass App-Bound Encryption |

## Quick start

```bash
# 1. Install deps (venv recommended)
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt      # Windows
# or: pip install -r requirements.txt

# 2. Prepare site list: put your GSC sites into dashboard_data.json (see example/)
#    or skip it entirely and use --site-url to scrape on the fly (see below)

# 3. Close Chrome (otherwise the profile is locked and the copy fails)

# 4. Run (Windows one-click)
run_genai.bat
# or
python scrape_genai.py
```

This generates / updates `genai_data.json`.

## CLI arguments

| Arg | Description |
|---|---|
| (none) | Scrape all `gsc_sites` from `dashboard_data.json` |
| `--limit N` | Scrape only the first N sites |
| `--site <name or URL>` | Re-scrape a single site only |
| `--profile <name>` | Specify Chrome profile (default `Default`) if the GSC session lives elsewhere |
| `--site-url <URL> [--site-url ...]` | Explicitly scrape a site (e.g. `https://example.com/` or `sc-domain:example.com`); does not write `dashboard_data.json` |
| `--only-extra` | Scrape only the `--site-url` sites, skip `gsc_sites` (avoids a full re-scrape) |
| `--dry-run` | Diagnostic mode: print parse results, don't write files |

Example — top up just two sites (without re-scraping everything):

```bash
python scrape_genai.py --site-url https://example.com/ --site-url sc-domain:example2.com --only-extra
```

## Output format (`genai_data.json`)

```json
{
  "_meta": { "is_sample": false, "api_available": false, "updated_at": "2026-09-01",
             "source": "GSC Generative AI report (browser automation)" },
  "example.com": {
    "updated_at": "2026-09-01",
    "trend": [ { "date": "2026-08-05", "impressions": 12 }, ... ],
    "top_pages": [ { "page": "https://example.com/foo/", "impressions": 34 }, ... ]
  }
}
```

## Frontend integration

To display this data in your dashboard, see **[frontend/README.md](frontend/README.md)** — three steps:
inject `const GENAI` → paste the panel HTML → call `renderGscGenAi()`.

## Architecture / data flow

![architecture](architecture.svg)

## Pitfalls (all solved)

| Pitfall | Symptom | Fix |
|---|---|---|
| Chrome 127+ App-Bound Encryption | copied cookies won't decrypt / login loop | use the **genuine Google Chrome binary** + launch from a temp copy of the whole profile layout; **close Chrome** before running |
| Reading `resp.body()` inside the `response` callback | intermittent "Target page closed", data loss | callback only collects response objects; read bodies in the main thread via `drain()` (core fix) |
| Not clicking the time range | some sites only return 7 days | always **force-click "28 days"** and **don't clear the store** until `len>=27` |
| `sc-domain:foo.com` prefix | Top pages all zero | strip the prefix to `foo.com` with `site_domain_of()` before matching page URLs |
| Switching Google account mid-way | re-scrape hits login / `login_required` | make sure Chrome is logged into the account that owns the GSC properties before running |

## Security / privacy

- `.gitignore` already excludes `genai_data.json`, `dashboard_data.json`, `*.pre_genai_*`, `.venv/`, and diagnostic files —
  **do not commit real scraped data or your personal site list to a public repo**.
- The script only reads a local copy of your logged-in Chrome profile; it sends nothing to any third party.

## License

MIT — see the [`LICENSE`](LICENSE) file at the repo root (free to reuse, modify, and redistribute).
