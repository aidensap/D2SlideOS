# D2SlideOS

> **SAC Model Data → AI Analysis → PPT, fully automated.**

D2SlideOS connects directly to **SAP Analytics Cloud (SAC)** via OData API, pulls model data, runs AI-powered analysis, generates a professional PowerPoint report, and delivers it to recipients on a schedule — deployed on **SAP BTP Cloud Foundry**, no local setup required.

**Live**: https://d2slideos.cfapps.eu12.hana.ondemand.com

---

## How It Works

```
SAC OData Dataexport API
         ↓
   Pull model data (up to 5000 rows)
         ↓
AI column inference (ID_xxx → human-readable names)
         ↓
AI business analysis (insights + recommendations)
         ↓
AI chart generation (Plotly — heatmaps, maps, sankey, etc.)
         ↓
python-pptx builds PowerPoint deck
         ↓
(Optional) Resend API emails PPT to recipients
```

---

## Features

| Feature | Description |
|---------|-------------|
| **SAC Model Sync** | One-click sync of all SAC models into report library; AI generates friendly Chinese aliases |
| **AI Column Inference** | Renames cryptic column names (e.g. `ID_MEASURE_NAME`) based on sample values |
| **AI Chart Generation** | Describe your chart in natural language; AI writes and executes Plotly code |
| **AI Business Analysis** | Structured findings + actionable recommendations from the data |
| **Natural Language Tasks** | Type "每周一发国泰人寿报表给张经理" — AI parses into a structured task |
| **Ambiguous Model Detection** | If multiple models match (e.g. "国泰人寿" → v1/v3/v4), warns user to choose manually |
| **Cron Scheduling** | APScheduler with NL-to-cron conversion ("每周五上午9点" → `0 9 * * 5`) |
| **Email Distribution** | PPT attached, AI-written email body, via Resend API |
| **Run History** | Every run logged with downloadable PPT and AI insights |
| **Address Book** | Save contacts (name + email) for quick recipient selection |

---

## Architecture

```
┌──────────────────────────────────────────┐
│             Browser UI (SPA)             │
│  Task cards · Report library · History   │
└──────────────────┬───────────────────────┘
                   │ HTTP
┌──────────────────▼───────────────────────┐
│           FastAPI Backend                │
│                                          │
│  SACConnector → DataFrame                │
│       ↓                                  │
│  agent.py (SAP AI Core / GPT-4o)         │
│    infer_column_names()                  │
│    analyze_data()                        │
│    generate_chart_code()  → PNG          │
│       ↓                                  │
│  slide_builder.py → .pptx                │
│       ↓                                  │
│  distributor.py → email                  │
└──────────────────────────────────────────┘
         │                    │
   SAP AI Core           SQLite DB
  (GPT-4o-mini)       (jobs + history +
                        report aliases)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10 + FastAPI + uvicorn |
| Scheduler | APScheduler (AsyncIOScheduler, cron) |
| Database | SQLite via SQLAlchemy |
| SAC Integration | OData Dataexport API (Client Credentials OAuth) |
| AI | SAP AI Core — `generative-ai-hub-sdk` (GPT-4o / GPT-4o-mini) |
| Charts | Plotly + Kaleido (PNG export) |
| Slides | python-pptx |
| Email | Resend API |
| Frontend | Vanilla HTML/CSS/JS (zero dependencies) |
| Deploy | SAP BTP Cloud Foundry (Python Buildpack) |

---

## Project Structure

```
D2SlideOS/
├── app/
│   ├── main.py              # FastAPI routes + APScheduler
│   ├── agent.py             # AI: analysis, chart gen, column inference, NL parsing
│   ├── config.py            # Env var loading
│   ├── models.py            # SQLite: ReportJob, RunHistory, Contact, ReportAlias
│   └── tools/
│       ├── sac_connector.py # SAC OAuth + OData data pull
│       ├── slide_builder.py # PPT generation
│       ├── distributor.py   # Resend email
│       ├── bw_connector.py  # BW data source (mock mode)
│       └── screenshot_rpa.py# RPA (local only, disabled on BTP)
├── app/static/
│   └── index.html           # Single-page frontend
├── manifest.yml             # BTP CF deployment config
├── .env.example             # Credential template
├── requirements.txt
├── FUNCTION_SPEC.md         # Full feature specification
└── MEETING_CHECKLIST.md     # Meeting prep checklist
```

---

## Deployment (BTP Cloud Foundry)

```bash
# Login
cf login -a https://api.cf.eu12.hana.ondemand.com --sso

# Deploy
cf push

# Set environment variables (required after every push)
cf set-env d2slideos AICORE_AUTH_URL "..."
cf set-env d2slideos AICORE_CLIENT_ID "..."
cf set-env d2slideos AICORE_CLIENT_SECRET "..."
cf set-env d2slideos AICORE_BASE_URL "..."
cf set-env d2slideos SAC_CLIENT_ID "..."
cf set-env d2slideos SAC_CLIENT_SECRET "..."
cf set-env d2slideos SAC_TOKEN_URL "..."
cf set-env d2slideos SAC_BASE_URL "..."
cf set-env d2slideos RESEND_API_KEY "..."
cf set-env d2slideos EMAIL_FROM "D2SlideOS <noreply@yourdomain.com>"
cf restage d2slideos
```

> **Note**: SQLite DB resets on every `cf push`. Re-run SAC model sync after each deploy.

---

## Local Development

```bash
# 1. Clone
git clone https://github.com/aidensap/D2SlideOS.git
cd D2SlideOS

# 2. Install
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Fill in .env with your credentials

# 4. Run
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# 5. Open
# http://localhost:8001
```

---

## Configuration (`.env`)

```env
# SAP AI Core
AICORE_AUTH_URL=https://<subaccount>.authentication.<region>.hana.ondemand.com
AICORE_CLIENT_ID=sb-...
AICORE_CLIENT_SECRET=...
AICORE_BASE_URL=https://api.ai.<region>.ml.hana.ondemand.com/v2
AICORE_RESOURCE_GROUP=default
AI_MODEL=gpt-4o-mini

# SAP Analytics Cloud
SAC_BASE_URL=https://<tenant>.analytics.sapcloud.cn
SAC_TOKEN_URL=https://<tenant>.authentication.<region>.sapcloud.cn/oauth/token
SAC_CLIENT_ID=...
SAC_CLIENT_SECRET=...

# Email
RESEND_API_KEY=re_...
EMAIL_FROM=D2SlideOS <noreply@yourdomain.com>
```

> **Never commit `.env` to git.**

---

## Known Limitations

| Issue | Notes |
|-------|-------|
| Screenshot / RPA | Disabled on BTP; only available in local mode with Edge browser |
| Email to @sap.com | Resend free tier cannot send to SAP corporate addresses |
| User isolation | All users share the same SAC Client Credentials token |
| DB persistence | SQLite resets on `cf push`; needs HANA Cloud for production use |

---

*Built by Aiden Yang · SAP CS&D GC · Powered by SAP AI Core & BTP*  
Contact: aiden.yang@sap.com