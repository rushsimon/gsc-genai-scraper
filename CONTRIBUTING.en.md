# Contributing

Thanks for your interest in the **GSC Generative AI Report Scraper**! Here are the
rules that keep changes merging smoothly.

## Setup

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt      # Windows
# or: pip install -r requirements.txt
```

## Required after editing `scrape_genai.py` (important ⚠️)

The CI **Syntax check** step runs `python -m py_compile scrape_genai.py` on the file.
**Any syntax error fails CI and blocks the PR.** Always run it locally before pushing:

```bash
python -m py_compile scrape_genai.py
```

> In real use this project was once blocked by CI over a single unbalanced f-string
> parenthesis (`scrape_genai.py:304`) — exactly the kind of typo a human eye misses,
> and exactly why the CI gate exists.

## Run the scraper locally (optional, to verify a change)

```bash
# 1. Close Chrome first, or the profile is locked and the copy fails
# 2. run
python scrape_genai.py
```

Full flow in [README.en.md](README.en.md).

## Do not commit real data 🔒

`.gitignore` already excludes `genai_data.json`, `dashboard_data.json`, `*.bak`,
`.venv/`, and diagnostic files. **Do not force-add them with `git add -f`** —
they contain your personal site list and real scrape results, which are private
and must not enter a public repo.

## Commit message style

| Prefix | Use |
|---|---|
| `fix:` | bug fix (e.g. `fix: f-string unbalanced paren in scrape_genai.py:304`) |
| `feat:` | new feature |
| `docs:` | documentation |
| `ci:` | CI / workflow change |

## PR flow

1. Fork or branch
2. Pass `python -m py_compile scrape_genai.py` locally
3. Push your branch and open a PR
4. Wait for the **Validate** workflow to turn green before merging

## Security / privacy

The script only reads a local copy of your logged-in Chrome profile; it sends
nothing to any third party.
