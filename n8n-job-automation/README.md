# Daily Job Scraper → Google Sheet (n8n)

An n8n workflow that runs every day at **08:00 Europe/Paris**, pulls fresh job listings from **Google for Jobs** (via SerpAPI) for the keywords/location you set, summarizes each posting with **Gemini (free tier)**, and appends new rows to a Google Sheet. Already-seen jobs are skipped automatically.

---

## What you'll need (all free tiers)

| Service | Why | Sign up |
|---|---|---|
| **n8n Cloud** | Runs the workflow on a schedule | https://n8n.io (free trial → $24/mo) |
| **SerpAPI key** | Fetches Google Jobs results | https://serpapi.com (100 searches/mo free) |
| **Gemini API key** | Summarizes job descriptions | https://aistudio.google.com/apikey (free) |
| **Google account** | For the Sheet + OAuth | already have one |

> **Cheaper alternative to n8n Cloud:** self-host n8n via Docker on Railway (~$5/mo) — same workflow JSON, same setup steps.

---

## Step 1 — Create the Google Sheet

1. Make a new blank Google Sheet. Name it anything (e.g., `Job Pipeline`).
2. Create **two tabs** with these exact names: `Config` and `Jobs`.

### `Config` tab — paste these as the first two columns:

| key | value |
|---|---|
| keywords | product manager, growth PM |
| location | Paris, France |
| max_results_per_keyword | 20 |
| posted_within | past_week |

> Edit anytime — the workflow re-reads this on every run.
> `posted_within` accepts: `past_24_hours`, `past_week`, `past_month`.

### `Jobs` tab — paste this header row in row 1:

```
Title | Company | Job Description Summary | Link to Apply | Eligibility | Location | Pay Range | Source | Date Added | Status
```

(One header per cell, A1 through J1.)

3. Copy the **Sheet ID** from the URL:
   `https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`

---

## Step 2 — Get your API keys

### SerpAPI
1. Sign up at https://serpapi.com
2. Dashboard → copy your **Private API Key**

### Gemini
1. Go to https://aistudio.google.com/apikey
2. Click **Create API key** → copy it

---

## Step 3 — Set up n8n

1. Sign up at https://n8n.io and create a new workflow.
2. Top-right **⋯ menu → Import from File** → select `workflow.json`.
3. Open **Settings → Variables (Environment)** and add three env vars:
   - `SHEET_ID` = your Sheet ID from Step 1
   - `SERPAPI_KEY` = your SerpAPI key
   - `GEMINI_API_KEY` = your Gemini key
4. Click any **Google Sheets** node → **Credential to connect with** → **Create New** → sign in with Google and authorize. (Do this once; the other Sheets nodes will auto-pick it up.)
5. Click **Save**, then toggle **Active** ON in the top-right.

---

## Step 4 — Test it

1. Open the workflow and click **Execute Workflow** (top bar) to run it once manually.
2. Check the `Jobs` tab — new rows should appear within ~30 seconds.
3. If anything errors, click the red node to see the message.

---

## Daily operation

- Runs automatically at **08:00 Europe/Paris** every day.
- Your friend only needs to:
  - **Edit the `Config` tab** to change keywords/location.
  - **Update the `Status` column** in the `Jobs` tab as she applies (`New` → `Applied` / `Skip` / `Interview`).
- Duplicate jobs (same apply link) are filtered out across runs.

---

## Cost ceiling

With 2 keywords × daily runs:
- SerpAPI: ~60 searches/mo (free tier = 100)
- Gemini: ~600 summaries/mo (well under free tier)
- **$0/mo** as long as you stay within these limits.

If you push past free tiers, SerpAPI is $50/mo for 5,000 searches.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No keywords found in Config tab` | Make sure column A is `keywords` (lowercase) and column B has at least one keyword. |
| Sheets node fails with permission error | Re-do the OAuth in the credential, make sure your Google account has access to the Sheet. |
| 0 new rows after run | All jobs were duplicates (good), or `posted_within` is too narrow — try `past_month`. |
| Gemini returns garbage | Free model occasionally fails; the workflow falls back to a description snippet. Safe to ignore. |
| SerpAPI 401 | `SERPAPI_KEY` env var typo. |

---

## Extending later (v2 ideas)

- Add a Slack/email notification with the day's new rows.
- Add a "filter out" tab — skip jobs from companies you don't want.
- Score each job 1–10 against your CV using Gemini.
- Add more sources (RemoteOK API, Wellfound, We Work Remotely RSS) as parallel branches in the workflow.
