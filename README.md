# D2SlideOS

> **SAP BI → AI Analysis → PPT, fully automated.**

D2SlideOS is an AI-powered report agent that pulls data from SAP BW (or any CSV source), sends it to an LLM for analysis, and generates a polished PowerPoint deck — ready to send to your manager.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        Browser UI                       │
│   Model selector · Language toggle · Job manager        │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP
┌────────────────────▼────────────────────────────────────┐
│                  FastAPI Backend                        │
│                                                         │
│  /api/jobs  ──►  bw_connector.py  ──►  DataFrame        │
│                                            │            │
│                                    agent.py (AI)        │
│                                            │            │
│                                   slide_builder.py      │
│                                            │            │
│                                    output/*.pptx        │
└────────────────────────────────────────────────────────-┘
         │                              │
   SAP AI Core                    SQLite (jobs +
  (GPT / Claude)                   run history)
```

**Data flow per run:**
1. User clicks ▶ Run on a job
2. `bw_connector.py` reads CSV from `mock_data/` (or calls BW OData/RFC in production)
3. `agent.py` sends the raw CSV + prompt to SAP AI Core LLM
4. LLM returns structured plain-text analysis (Key Findings + Recommendations)
5. `slide_builder.py` renders: Title slide → Chart slide → AI Insights slide(s)
6. `.pptx` saved to `output/`, download link appears in history

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + uvicorn |
| Database | SQLite via SQLAlchemy |
| AI | SAP AI Core (`generative-ai-hub-sdk` v4.12.4) |
| Models | GPT-4o mini / GPT-4o / Claude (via LangChain proxy) |
| Slide gen | python-pptx + matplotlib |
| Frontend | Vanilla HTML/CSS/JS (zero dependencies) |
| Deploy | Docker + docker-compose |

---

## Project Structure

```
D2SlideOS/
├── app/
│   ├── main.py              # FastAPI routes
│   ├── agent.py             # SAP AI Core LLM call
│   ├── config.py            # Env var loading
│   ├── models.py            # SQLite: ReportJob + RunHistory
│   └── tools/
│       ├── bw_connector.py  # Data source (mock CSV / OData / RFC)
│       ├── slide_builder.py # PPT generation (auto-paginates insights)
│       └── distributor.py   # SMTP email distribution
├── mock_data/               # *.csv files auto-scanned as report sources
├── output/                  # Generated .pptx files
├── .env.example             # Credential template
├── Dockerfile
└── docker-compose.yml
```

---

## Quick Start

### Local (Python)

```bash
# 1. Clone
git clone <repo-url>
cd D2SlideOS

# 2. Install dependencies
pip install -r requirements.txt

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

# Defaults (overridable from UI at runtime)
AI_MODEL=gpt-4o-mini
CHART_LANG=en

# Data source mode: mock | odata | rfc
BW_MODE=mock

# Email (optional — skip for demo)
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_USER=
EMAIL_PASSWORD=
```

> **Never commit `.env` to git.** It contains real credentials.

---

## Features

### Current
- **Multi-model support** — switch between GPT-4o mini, GPT-4o, Claude from the UI, no restart needed
- **Bilingual output** — English or Chinese AI analysis + chart labels, selectable from UI
- **Auto chart detection** — reads DataFrame columns to pick chart type automatically:
  - `{MONTH, REGIO, NETWR}` → grouped bar (sales by region)
  - `{ON_TIME, LATE, MONTH}` → stacked bar (delivery performance)
  - anything else → horizontal bar (top 10 by value)
- **Auto-paginated insights** — AI analysis slides auto-split across multiple pages (14 lines/slide) so content never overflows
- **Run history** — every run logged with status, timestamp, AI insights preview (expandable), and PPT download
- **One-click job** — create a job, click Run, job auto-deletes after submission, PPT appears in history

### Roadmap
- **BW OData connector** — switch `BW_MODE=odata` to pull live data from SAP BW
- **BW RFC connector** — direct function module calls via PyRFC (requires SAP NW RFC SDK)
- **Screenshot-to-PPT (RPA mode)** — upload a screenshot of a SAP portal report; multimodal LLM extracts the data, feeds it through the same pipeline
- **Email distribution** — SMTP send to recipients on job completion (service account, no OAuth needed for demo; Microsoft Graph API for production)
- **Scheduled runs** — cron-based scheduling (field already in UI, backend execution TBD)

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config/model` | Get current model + available models |
| POST | `/api/config/model` | Switch active model |
| GET | `/api/config/lang` | Get current chart language |
| POST | `/api/config/lang` | Switch language (`en` / `zh`) |
| GET | `/api/reports/available` | List available data sources |
| GET | `/api/jobs` | List active jobs |
| POST | `/api/jobs` | Create a job |
| DELETE | `/api/jobs/{id}` | Delete a job |
| POST | `/api/jobs/{id}/run` | Run a job (async) |
| GET | `/api/history` | List run history |
| DELETE | `/api/history/{id}` | Delete a history entry |
| GET | `/api/history/{id}/download` | Download generated `.pptx` |

---

## SAP AI Core SDK Notes

- Package: `generative-ai-hub-sdk` (not `sap-ai-sdk-gen`)
- GPT models: `from gen_ai_hub.proxy.native.openai.clients import OpenAI`
- Claude models: `from gen_ai_hub.proxy.langchain.openai import ChatOpenAI` (no native Anthropic module in v4.12.4)
- Credentials set via environment variables (see `.env` above)

---

## Adding Mock Data

Drop any `.csv` file into `mock_data/` — it will appear automatically in the data source dropdown. Column names drive chart type detection, so using SAP field names (`NETWR`, `REGIO`, `MONTH`, etc.) gets you the right chart automatically.

---

*Built by Aiden Yang · SAP STAR Intern · Powered by SAP AI Core*
