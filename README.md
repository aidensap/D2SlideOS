# D2SlideOS

> **SAP BI Report → AI Analysis → PPT, fully automated.**

**Login once. Enter your report URL once. D2SlideOS does the rest.**

D2SlideOS automatically captures your SAP Analytics Cloud stories on a schedule, runs **AI-powered analysis** on every chart, and delivers a **professional PowerPoint report straight to your manager's inbox** — no manual work, no repeated logins, no copy-pasting.

- **One-time login** — authenticate once, and every future run uses your saved session automatically
- **Any SAC story URL** — just paste the link; D2SlideOS handles the screenshot, the analysis, and the slides
- **GPT-4o Vision** — understands charts, trends, and KPIs the same way a human analyst would
- **Scheduled delivery** — set a cron schedule and your boss gets the report every Monday morning without you lifting a finger
- **Multi-task** — manage multiple reports across different stories, each with its own schedule, language, and AI model

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
(Optional) SMTP email to recipients
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
| Database | SQLite via SQLAlchemy |
| RPA Screenshots | Playwright (Microsoft Edge) |
| AI Analysis | SAP AI Core (`generative-ai-hub-sdk` v4.12.4) |
| Models | GPT-4o mini / GPT-4o / Claude 3.5 / Claude 4.6 |
| Slide generation | python-pptx |
| Frontend | Vanilla HTML/CSS/JS (zero dependencies) |
| Deploy | Docker + docker-compose |

---

## Project Structure

```
D2SlideOS/
├── app/
│   ├── main.py                  # FastAPI routes + APScheduler cron jobs
│   ├── agent.py                 # AI: text analysis + GPT-4o Vision screenshot analysis
│   ├── config.py                # Env var loading
│   ├── models.py                # SQLite: ReportJob + RunHistory (with auto-migration)
│   └── tools/
│       ├── screenshot_rpa.py    # Playwright RPA: login, screenshot, dialog removal
│       ├── sac_connector.py     # SAC OAuth Client Credentials (fallback)
│       ├── slide_builder.py     # PPT generation: screenshot embed + paginated insights
│       ├── bw_connector.py      # BW data source (mock CSV / OData / RFC)
│       └── distributor.py       # SMTP email distribution
├── app/static/
│   └── index.html               # Single-page frontend
├── output/
│   └── screenshots/             # Screenshot PNGs (gitignored, auto-created)
├── rpa_session.json             # Login cookies (gitignored, auto-generated)
├── .env.example                 # Credential template
├── Dockerfile
└── docker-compose.yml
```

---

## Quick Start

### Local (Python)

```bash
# 1. Clone
git clone https://github.com/aidensap/D2SlideOS.git
cd D2SlideOS

# 2. Install dependencies
pip install -r requirements.txt
playwright install msedge

# 3. Configure credentials
cp .env.example .env
# Edit .env — fill in SAP AI Core credentials

# 4. Run
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# 5. Open browser
# http://localhost:8001
```

### Docker

```bash
cp .env.example .env
# Edit .env with your credentials

docker-compose up --build
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

# Email (optional)
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_USER=
EMAIL_PASSWORD=
```

> **Never commit `.env` to git.** It contains real credentials.

---

## Features

### Implemented
- **RPA auto-screenshot** — Playwright drives Edge to open SAC pages, waits for charts to render, removes popups, then screenshots
- **One-time login** — Login once to save cookies; SAP SSO covers all report URLs under the same domain
- **GPT-4o Vision analysis** — Screenshot sent to GPT-4o for chart interpretation, returns structured insights in Chinese or English
- **Auto PPT generation** — Title slide + screenshot slide + AI insights slide, one-click download
- **Per-task model & language** — Each task independently selects model (GPT-4o mini / GPT-4o / Claude) and output language
- **Cron scheduling** — Cron expression per task; schedules survive server restarts
- **Run history** — Every run logged with screenshot thumbnail, expandable AI insights, and PPT download link

### Roadmap
- **Email distribution** — SMTP auto-send PPT to recipients on completion (field already in UI)
- **BW OData connector** — `BW_MODE=odata` to pull live data from SAP BW
- **Docker deployment testing**

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/rpa/session-status` | Check login session status |
| POST | `/api/rpa/login` | Open browser for interactive login, save cookies |
| POST | `/api/rpa/logout` | Clear saved cookies |
| GET | `/api/jobs` | List all tasks |
| POST | `/api/jobs` | Create a task |
| DELETE | `/api/jobs/{id}` | Delete a task |
| POST | `/api/jobs/{id}/run` | Run a task (async) |
| GET | `/api/history` | List run history |
| DELETE | `/api/history/{id}` | Delete a history entry |
| GET | `/api/history/{id}/screenshot` | Get screenshot PNG |
| GET | `/api/history/{id}/download` | Download generated `.pptx` |

---

## SAP AI Core SDK Notes

- Package: `generative-ai-hub-sdk` (not `sap-ai-sdk-gen`)
- GPT models: `from gen_ai_hub.proxy.native.openai.clients import OpenAI`
- Claude models: `from gen_ai_hub.proxy.langchain.openai import ChatOpenAI` (no native Anthropic module in v4.12.4)
- Vision (image analysis) only works with GPT-4o series; Claude via LangChain proxy cannot accept image input

---

*Built by Aiden Yang · SAP STAR Intern · Powered by SAP AI Core*