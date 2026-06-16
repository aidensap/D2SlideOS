# D2SlideOS — Function Specification

**Version**: 1.0  
**Author**: Aiden Yang  
**Last Updated**: 2026-06-16  
**Deployment**: SAP BTP Cloud Foundry — https://d2slideos.cfapps.eu12.hana.ondemand.com

---

## 1. Overview

D2SlideOS is an AI-powered BI report automation agent. It reads data from SAP Analytics Cloud (SAC), performs AI-driven analysis, generates PowerPoint slides, and distributes reports via email — either on-demand or on a scheduled basis.

**Target Users**: Business analysts, managers, and operations teams who regularly distribute SAC data reports.

---

## 2. Architecture

```
SAC OData API
     ↓
Data Pull (SACConnector)
     ↓
AI Column Inference (infer_column_names)
     ↓
AI Analysis (analyze_data)        AI Chart Generation (generate_chart_code)
     ↓                                        ↓
PPT Generation (slide_builder)  ←────────────┘
     ↓
Email Distribution (distributor)
```

**Stack**:
- Backend: Python 3.10 + FastAPI + APScheduler
- Frontend: Single-page HTML (Vanilla JS, no framework)
- AI: SAP AI Core (GPT-4o / GPT-4o-mini via generative-ai-hub-sdk)
- Charts: Plotly + Kaleido (PNG export)
- DB: SQLite (via SQLAlchemy)
- Deploy: SAP BTP Cloud Foundry (Python Buildpack)

---

## 3. Features

### 3.1 SAC Data Integration

| Feature | Description |
|---------|-------------|
| OAuth Connection | Client Credentials flow to SAC tenant |
| Model Listing | Fetch all available SAC models via OData Dataexport API |
| Data Pull | `GET /api/v1/dataexport/providers/sac/{model_id}/FactData` up to 5000 rows |
| Connection Status | Header indicator — green dot "SAC 已连接" / grey "未登录" |

### 3.2 Report Library (Address Book)

| Feature | Description |
|---------|-------------|
| SAC Model Sync | One-click sync of all SAC models into the report library |
| AI Alias Generation | AI batch-generates friendly Chinese names (e.g. `20241024_Cathaylife_v3` → `国泰人寿v3`) |
| Manual Reports | Users can manually add SAC Story URLs with custom names |
| Duplicate Prevention | Sync uses delete-all + re-insert to prevent duplicates |
| Progress Bar | Visual progress bar during sync (0→100%, animated) |

### 3.3 AI Analysis

| Feature | Description |
|---------|-------------|
| Column Name Inference | AI renames cryptic column names (e.g. `ID_MEASURE_NAME`) to human-readable ones based on sample values |
| Business Insights | AI generates structured findings + recommendations from the data |
| Language Support | Chinese (`zh`) and English (`en`) output |
| Empty Data Guard | If model returns empty data, task fails with clear error (no AI fabrication) |

### 3.4 AI Chart Generation

| Feature | Description |
|---------|-------------|
| Custom Chart Prompt | User can describe the desired chart in natural language |
| Plotly-First | Prefers Plotly (supports heatmaps, maps, sankey, sunburst, 3D) over matplotlib |
| Dark Theme | All charts use `plotly_dark` template to match UI |
| Language Consistency | Chart labels/titles use same language as column names |
| Exec Pattern | AI-generated Python code is executed via `exec()` with the real `df` |

### 3.5 PowerPoint Generation

| Feature | Description |
|---------|-------------|
| Auto Slide Deck | Generates multi-slide PPT: title, insights, chart, data table |
| Download | PPT downloadable from run history |
| Naming | File named after task + timestamp |

### 3.6 Task Management

| Feature | Description |
|---------|-------------|
| Create Task | Name, data source (SAC model), language, chart prompt, recipients, schedule |
| Natural Language Input | Type a description → AI parses into structured task fields |
| Ambiguous Model Detection | If multiple models match (e.g. "国泰人寿" → v1/v3/v4), shows warning and lets user choose |
| Edit / Delete | Inline edit and delete for each task card |
| Manual Run | Run any task immediately on demand |

### 3.7 Scheduling

| Feature | Description |
|---------|-------------|
| Cron Scheduling | Standard 5-field cron expression |
| NL to Cron | AI converts natural language schedule ("每周一上午9点") to cron |
| Schedule Display | Human-readable schedule description shown on task card |
| Persistent | Schedules survive server restarts (loaded from DB on startup) |

### 3.8 Email Distribution

| Feature | Description |
|---------|-------------|
| Address Book | Store contact name + email |
| Send Report | PPT attached, AI-generated email body |
| Provider | Resend API |
| Limitation | Free tier: can only send to verified addresses (not @sap.com) |

### 3.9 Run History

| Feature | Description |
|---------|-------------|
| History Log | Every run recorded: status, timestamp, insights summary |
| PPT Download | Download PPT from history |
| Delete | Delete individual history entries |

---

## 4. Data Flow — SAC Report Task

```
User triggers run (manual or cron)
  → Pull model data from SAC OData API
  → Guard: if empty → fail with error message
  → infer_column_names(df)  [AI rename]
  → analyze_data(df, lang)  [AI insights]
  → generate_chart_code(df, chart_prompt)  [AI plotly code → PNG]
  → generate_slides(df, name, insights, chart)  [PPT]
  → send_report(pptx, recipients)  [email]
  → save RunHistory record
```

---

## 5. Known Limitations

| Issue | Status |
|-------|--------|
| Screenshot / RPA | Disabled on BTP (no GUI environment) |
| Email to @sap.com | Resend free tier blocks SAP domain; needs SMTP relay or Microsoft Graph API |
| User isolation | All users share same SAC Client Credentials token; no per-user auth |
| sync-models reliability | AI alias generation may silently fall back to technical names in async context |
| SQLite on BTP | DB resets on every `cf push`; model sync must be re-run after each deploy |

---

## 6. API Endpoints (Summary)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/sac/status` | SAC connection status |
| POST | `/api/sac/sync-models` | Sync SAC models → report library |
| GET | `/api/report-aliases` | List report library entries |
| POST | `/api/jobs` | Create task |
| POST | `/api/jobs/{id}/run` | Run task now |
| GET | `/api/history` | Run history |
| GET | `/api/history/{id}/download` | Download PPT |
| POST | `/api/jobs/parse-text` | NL → task fields |
| POST | `/api/schedule/parse` | NL → cron expression |

---

## 7. Deployment

```
Platform: SAP BTP Cloud Foundry (eu12)
Org:      CS&D GC Demo_demo-ai-r59tlvcc
Space:    d2slideos
Memory:   256M
Disk:     1G
URL:      https://d2slideos.cfapps.eu12.hana.ondemand.com
```

Required environment variables: `AICORE_*`, `SAC_*`, `RESEND_API_KEY`, `EMAIL_FROM`