# JobBot 🤖

A free, self-hosted job alerter. It pulls fresh postings from several free job
APIs (plus Rozee.pk for Pakistan), scores each one against **your** skill set,
and emails you **only the new matches** — twice a day, automatically, at zero cost.

Runs on **GitHub Actions**, so there is no server to pay for and your computer
doesn't need to be on.

---

## What it does

1. **Collects** jobs from Remotive, RemoteOK, Arbeitnow, Jobicy (free JSON APIs)
   and scrapes Rozee.pk for Pakistan-local roles.
2. **Scores** every job against the skills in `config.yaml` and filters by role,
   location, freshness, and exclusion keywords.
3. **Remembers** what it already sent (`data/seen_jobs.json`) so you never get
   the same job twice.
4. **Emails** you a clean, ranked digest of new matches.
5. **Publishes** a live dashboard (GitHub Pages) — a searchable, filterable page
   of all current matches that refreshes automatically on every run.

Everything is tunable in `config.yaml` — no code changes needed.

---

## Quick start (5 steps)

### 1. Get a Gmail App Password
JobBot sends email through Gmail's SMTP. You need an **App Password** (a normal
password won't work):

1. Enable 2-Step Verification on your Google account.
2. Go to <https://myaccount.google.com/apppasswords>.
3. Create a password named "JobBot" and copy the 16-character code.

> Not on Gmail? Any SMTP provider works — set `SMTP_HOST` / `SMTP_PORT` and use
> that provider's credentials.

### 2. Put this folder in a GitHub repo
Create a new repository (private is fine) and push this `jobbot/` folder to it.

```bash
git init
git add .
git commit -m "JobBot"
git branch -M main
git remote add origin https://github.com/<you>/jobbot.git
git push -u origin main
```

### 3. Add your secrets
In the repo: **Settings → Secrets and variables → Actions → New repository secret**.
Add three secrets:

| Secret name          | Value                                  |
|----------------------|----------------------------------------|
| `EMAIL_ADDRESS`      | your Gmail address                     |
| `EMAIL_APP_PASSWORD` | the 16-char App Password from step 1   |
| `EMAIL_TO`           | where to receive alerts (can be same)  |

### 4. Turn on Actions & test it
- Go to the **Actions** tab and enable workflows if prompted.
- Open the **JobBot** workflow → **Run workflow** to trigger it manually once.
- Check the run log and your inbox.

### 5. Enable the dashboard (GitHub Pages)
The bot writes matched jobs to `docs/jobs.json`, and `docs/index.html` is a
static dashboard that displays them. To publish it for free:

1. Repo **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **Deploy from a branch**.
3. Branch: **main**, folder: **/docs**. Save.
4. After a minute your dashboard is live at
   `https://<you>.github.io/jobbot/` — searchable, filterable, and auto-updated
   every run.

### 6. Done — it now runs on its own
The schedule (`.github/workflows/jobbot.yml`) fires at **06:00 and 18:00 PKT**
every day. Adjust the `cron` line to change the time (it's in UTC). Each run
emails new matches **and** refreshes the dashboard.

---

## Tuning what you get

Open **`config.yaml`** and edit:

- **`skills`** — the keywords that raise a job's score, with weights.
- **`min_score`** — raise it for fewer/stricter matches, lower it for more.
- **`role_keywords`** — a job must mention at least one of these.
- **`allowed_locations`** / **`require_remote_or_location`** — where you'll work.
- **`negative_keywords`** — things to always exclude (e.g. `internship`).
- **`sources`** — toggle any source on/off.

Commit and push after editing; the next run uses the new settings.

---

## Running it locally (optional)

```bash
pip install -r requirements.txt

# Offline sanity check — runs mock jobs through the whole pipeline, no network:
python main.py --self-test

# Real fetch, print matches, but DON'T email or change state:
python main.py --dry-run

# Real fetch + save an HTML preview of the email:
python main.py --dry-run --preview preview.html
```

For a real local send, copy `.env.example` to `.env`, fill it in, then:

```bash
# load the .env into your shell (Linux/macOS)
export $(grep -v '^#' .env | xargs)
python main.py
```

---

## Adding WhatsApp later

Email is the default because it's free and needs no approval. To add WhatsApp,
the cleanest free-tier route is **Twilio's WhatsApp Sandbox** or the **Meta
WhatsApp Cloud API**. Implement a `send_whatsapp(jobs)` function in
`jobbot/notifier.py` (mirroring `send_email`) and call it from `main.run`.
Ask and this can be wired up.

---

## How much does this cost?

Nothing. GitHub Actions gives free scheduled minutes for this kind of tiny job,
the job APIs are free, and Gmail SMTP is free. No credit card, no server.

## Notes & limits

- **Rozee.pk** is scraped from HTML (no official API), so it's best-effort and
  may need a selector tweak if the site changes. It never breaks the run.
- Respect each site's terms of service and rate limits. Twice-daily is gentle.
- The first run will email a larger batch (everything currently matching); after
  that you only get genuinely new postings.
