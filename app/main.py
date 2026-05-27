import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.models import init_db, SessionLocal, ReportJob, RunHistory
from app.tools.bw_connector import get_report, list_available_reports
from app.agent import analyze_data
from app.tools.slide_builder import generate_slides
import app.config as cfg

app = FastAPI(title="D2SlideOS")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def index():
    return FileResponse("app/static/index.html")


# ---------- Config ----------

AVAILABLE_MODELS = [
    {"id": "gpt-4o-mini",                 "label": "GPT-4o mini",       "provider": "OpenAI"},
    {"id": "gpt-4o",                      "label": "GPT-4o",            "provider": "OpenAI"},
    {"id": "anthropic--claude-4.6-sonnet","label": "Claude 4.6 Sonnet", "provider": "Anthropic"},
    {"id": "anthropic--claude-3.5-sonnet","label": "Claude 3.5 Sonnet", "provider": "Anthropic"},
]

class ModelSelect(BaseModel):
    model_id: str

class LangSelect(BaseModel):
    lang: str

@app.get("/api/config/model")
def get_model():
    return {"current": cfg.AI_MODEL, "available": AVAILABLE_MODELS}

@app.post("/api/config/model")
def set_model(body: ModelSelect):
    if body.model_id not in [m["id"] for m in AVAILABLE_MODELS]:
        raise HTTPException(status_code=400, detail="不支持的模型")
    cfg.AI_MODEL = body.model_id
    return {"current": cfg.AI_MODEL}

@app.get("/api/config/lang")
def get_lang():
    return {"current": cfg.CHART_LANG}

@app.post("/api/config/lang")
def set_lang(body: LangSelect):
    if body.lang not in ("zh", "en"):
        raise HTTPException(status_code=400, detail="lang must be zh or en")
    cfg.CHART_LANG = body.lang
    return {"current": cfg.CHART_LANG}


# ---------- Reports ----------

@app.get("/api/reports/available")
def available_reports():
    return list_available_reports()


# ---------- Jobs ----------

class JobCreate(BaseModel):
    name: str
    report_type: str
    recipients: str
    schedule: str = ""

@app.get("/api/jobs")
def list_jobs():
    db = SessionLocal()
    jobs = db.query(ReportJob).filter(ReportJob.is_active == True).all()
    db.close()
    return [{"id": j.id, "name": j.name, "report_type": j.report_type,
             "recipients": j.recipients, "schedule": j.schedule,
             "created_at": j.created_at} for j in jobs]

@app.post("/api/jobs")
def create_job(body: JobCreate):
    db = SessionLocal()
    job = ReportJob(**body.dict())
    db.add(job)
    db.commit()
    db.refresh(job)
    db.close()
    return {"id": job.id, "name": job.name}

@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int):
    db = SessionLocal()
    job = db.query(ReportJob).filter(ReportJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_active = False
    db.commit()
    db.close()
    return {"ok": True}


# ---------- Run ----------

@app.post("/api/jobs/{job_id}/run")
async def run_job(job_id: int):
    db = SessionLocal()
    job = db.query(ReportJob).filter(ReportJob.id == job_id).first()
    if not job:
        db.close()
        raise HTTPException(status_code=404, detail="Job not found")

    run = RunHistory(job_id=job.id, job_name=job.name)
    db.add(run)
    db.commit()
    db.refresh(run)
    run_id = run.id
    job_snapshot = {"report_type": job.report_type, "name": job.name}
    db.close()

    asyncio.create_task(_execute_run(run_id, job_snapshot))
    return {"run_id": run_id, "status": "running"}


async def _execute_run(run_id: int, job: dict):
    db = SessionLocal()
    run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
    try:
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(None, get_report, job["report_type"])
        insights = await loop.run_in_executor(None, analyze_data, df, cfg.CHART_LANG)
        file_path = await loop.run_in_executor(None, generate_slides, df, job["name"], insights, cfg.CHART_LANG)
        run.status = "success"
        run.insights = insights
        run.file_path = file_path
    except Exception as e:
        run.status = "failed"
        run.error = str(e)
    finally:
        run.completed_at = datetime.utcnow()
        db.commit()
        db.close()


# ---------- History ----------

@app.get("/api/history")
def get_history():
    db = SessionLocal()
    runs = db.query(RunHistory).order_by(RunHistory.started_at.desc()).limit(50).all()
    db.close()
    return [{"id": r.id, "job_name": r.job_name, "status": r.status,
             "started_at": r.started_at, "completed_at": r.completed_at,
             "insights": r.insights, "file_path": r.file_path} for r in runs]

@app.delete("/api/history/{run_id}")
def delete_run(run_id: int):
    db = SessionLocal()
    run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    db.delete(run)
    db.commit()
    db.close()
    return {"ok": True}

@app.get("/api/history/{run_id}/download")
def download(run_id: int):
    db = SessionLocal()
    run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
    db.close()
    if not run or not run.file_path:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        run.file_path,
        filename=run.file_path.replace("\\", "/").split("/")[-1],
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
