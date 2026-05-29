# D2SlideOS

> **SAP BI Report → AI Analysis → PPT, fully automated.**

**Login once. Enter your report URL once. D2SlideOS does the rest.**

D2SlideOS automatically captures your SAP Analytics Cloud stories on a schedule, runs **AI-powered analysis** on every chart, and delivers a **professional PowerPoint report straight to your manager's inbox** — no manual work, no repeated logins, no copy-pasting.

- **One-time login** — authenticate once, and every future run uses your saved session automatically
- **Any SAC story URL** — just paste the link; D2SlideOS handles the screenshot, the analysis, and the slides
- **CSV / Excel upload** — upload a data file instead of a SAC URL; AI analyzes the table and generates slides
- **GPT-4o Vision** — understands charts, trends, and KPIs the same way a human analyst would
- **Natural language scheduling** — type "every Friday at 10:20" and D2SlideOS converts it to a cron schedule automatically
- **Scheduled delivery** — set a schedule and your boss gets the report every Monday morning without you lifting a finger
- **Multi-task** — manage multiple reports across different stories, each with its own schedule, language, AI model, and recipients

---

## How It Works

```
Scheduled trigger / Manual run
        ↓
Playwright (Edge) opens SAC report page
(uses saved login cookies — no repeated login)
        ↓
Screenshot saved as PNG
        ↓
GPT-4o Vision API analyzes the chart
        ↓
python-pptx builds PPT (screenshot + AI insights)
        ↓
(Optional) Resend API emails PPT to recipients
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Browser UI                         │
│   Task card manager · One-time SAC login                │
│   Run history · Screenshot thumbnails · PPT download    │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP
┌────────────────────▼────────────────────────────────────┐
│                  FastAPI Backend                        │
│                                                         │
│  /api/jobs  ──►  screenshot_rpa.py  ──►  PNG            │
│                                            │            │
│                                    agent.py (GPT Vision)│
│                                            │            │
│                                   slide_builder.py      │
│                                            │            │
│                                    output/*.pptx        │
└─────────────────────────────────────────────────────────┘
         │                              │
   SAP AI Core                    SQLite (jobs +
  (GPT / Claude)                   run history)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + uvicorn |
| Scheduler | APScheduler (AsyncIOScheduler, cron-based) |
| Database | SQLite via SQLAlchemy (auto-migration on startup) |
| RPA Screenshots | Playwright (Microsoft Edge, headless=False) |
| AI Analysis | SAP AI Core (`generative-ai-hub-sdk`) |
| Models | GPT-4o mini / GPT-4o / Claude 3.5 / Claude 4.6 |
| Slide generation | python-pptx |
| Email | Resend API (HTTPS, bypasses ISP SMTP blocking) |
| Frontend | Vanilla HTML/CSS/JS (zero dependencies) |

---

## Project Structure

```
D2SlideOS/
├── app/
│   ├── main.py                  # FastAPI routes + APScheduler cron jobs
│   ├── agent.py                 # AI: text analysis + GPT-4o Vision + NL→cron
│   ├── config.py                # Env var loading
│   ├── models.py                # SQLite: ReportJob + RunHistory (auto-migration)
│   └── tools/
│       ├── screenshot_rpa.py    # Playwright RPA: login, screenshot, session check
│       ├── sac_connector.py     # SAC OAuth Client Credentials connector
│       ├── slide_builder.py     # PPT generation: screenshot + insights slides
│       ├── bw_connector.py      # BW data source connector
│       └── distributor.py       # Resend API email distribution
├── app/static/
│   └── index.html               # Single-page frontend
├── output/
│   ├── screenshots/             # Screenshot PNGs (gitignored, auto-created)
│   └── uploads/                 # Uploaded CSV/Excel files (gitignored)
├── rpa_session.json             # Login cookies (gitignored, auto-generated)
├── start_silent.vbs             # Silent background launcher (Windows)
├── .env.example                 # Credential template
└── requirements.txt
```

---

## Quick Start

### Requirements

- Windows machine with **Microsoft Edge** installed
- Python 3.11+
- Network access to SAP AI Core

### Setup

```bash
# 1. Clone
git clone https://github.com/aidensap/D2SlideOS.git
cd D2SlideOS

# 2. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 3. Configure credentials
cp .env.example .env
# Edit .env — fill in SAP AI Core credentials and Resend API key

# 4. Run
py -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# 5. Open browser
# http://localhost:8001
```

---

## Configuration (`.env`)

```env
# SAP AI Core
AICORE_AUTH_URL=https://<your-subaccount>.authentication.<region>.hana.ondemand.com
AICORE_CLIENT_ID=sb-...
AICORE_CLIENT_SECRET=...
AICORE_BASE_URL=https://api.ai.<region>.ml.hana.ondemand.com/v2
AICORE_RESOURCE_GROUP=default

# Defaults (overridable per task from the UI)
AI_MODEL=gpt-4o-mini
CHART_LANG=zh

# Email (Resend API)
RESEND_API_KEY=re_...
EMAIL_FROM=D2SlideOS <onboarding@resend.dev>
```

> **Never commit `.env` to git.** It contains real credentials.

---

## Features

- **RPA auto-screenshot** — Playwright drives Edge to open SAC pages, waits for charts to render, removes popups, then screenshots
- **One-time login** — Login once to save cookies; SAP SSO covers all report URLs under the same domain; session expiry is detected automatically
- **CSV / Excel analysis** — Upload a spreadsheet; AI reads the table and generates slides without any browser automation
- **GPT-4o Vision analysis** — Screenshot sent to GPT-4o for chart interpretation, returns structured insights in Chinese or English
- **Natural language scheduling** — Type "every Friday at 10:20" or "每周五10:20"; GPT converts it to a cron expression
- **Auto PPT generation** — Title slide + screenshot slide + AI insights slide, one-click download
- **Per-task configuration** — Each task independently selects model, language, recipients, schedule, and custom email body
- **Cron scheduling** — APScheduler runs tasks on schedule; schedules survive server restarts
- **Email delivery** — Resend API sends PPT as attachment; email failure does not affect task status
- **Inline task editing** — Expand any task card to edit URL, schedule, recipients, or email body without recreating the task
- **Run history** — Every run logged with screenshot thumbnail, expandable AI insights, and PPT download link

---

## Deploying to Other Users

### What each user needs

| Requirement | Details |
|-------------|---------|
| Windows PC with Edge | Screenshot RPA requires a real browser; headless mode is blocked by SAP SSO |
| Python 3.11+ | Install from python.org |
| SAP AI Core credentials | Each user needs their own `.env` with valid AICORE_* values |
| Resend API key | Free tier supports up to 3,000 emails/month |
| Network access | Must reach SAP AI Core API and SAC system URL |

### Per-user setup steps

1. Copy the project folder to the user's machine
2. Run `pip install -r requirements.txt` and `playwright install chromium`
3. Fill in `.env` with the user's credentials
4. Start the server: double-click `start_server.bat`
5. Open `http://localhost:8001` in the browser
6. Click **登录 SAC** once to save the SAP session

### Auto-start on Windows login (optional)

To have the server start automatically when the user logs in:

1. Press `Win + R`, type `shell:startup`, press Enter
2. Copy `start_silent.vbs` into the folder that opens
3. The server will start silently in the background on every login

### Known limitations

- **Server must be running** for scheduled tasks to fire. If the machine is off or the server is stopped, missed schedules are not retried.
- **Email sender domain** — `onboarding@resend.dev` (Resend test domain) is silently dropped by SAP enterprise mail servers. To send to corporate addresses, register a custom domain (e.g. `d2slideos.com`, ~$10/year) and verify it in Resend.
- **No cloud deployment** — The screenshot pipeline requires a local Edge browser with an interactive SAP login session. Cloud hosting (Docker, Azure, etc.) is not supported for the screenshot source; CSV/Excel upload source works in any environment.
- **SAC session expiry** — SAP sessions typically expire after 8–24 hours. When detected, the UI prompts the user to log in again.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/rpa/session-status` | Check login session status |
| POST | `/api/rpa/login` | Open browser for interactive login, save cookies |
| POST | `/api/rpa/logout` | Clear saved cookies |
| GET | `/api/jobs` | List all tasks |
| POST | `/api/jobs` | Create a task |
| PATCH | `/api/jobs/{id}` | Update a task (name, URL, schedule, recipients, etc.) |
| DELETE | `/api/jobs/{id}` | Delete a task |
| POST | `/api/jobs/{id}/run` | Run a task immediately (async) |
| GET | `/api/history` | List run history |
| DELETE | `/api/history/{id}` | Delete a history entry |
| GET | `/api/history/{id}/screenshot` | Get screenshot PNG |
| GET | `/api/history/{id}/download` | Download generated `.pptx` |
| POST | `/api/schedule/parse` | Convert natural language to cron expression |
| GET | `/api/scheduler/jobs` | List active scheduled jobs and next run times |

---

## SAP AI Core SDK Notes

- Package: `generative-ai-hub-sdk` (not `sap-ai-sdk-gen`)
- GPT models: `from gen_ai_hub.proxy.native.openai.clients import OpenAI`
- Claude models: `from gen_ai_hub.proxy.langchain.openai import ChatOpenAI` (no native Anthropic module)
- Vision (image analysis) only works with GPT-4o series; Claude via LangChain proxy cannot accept image input

---

*Built by Aiden Yang · SAP STAR Intern · Powered by SAP AI Core*