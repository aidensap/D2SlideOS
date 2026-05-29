import os
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.models import init_db, SessionLocal, ReportJob, RunHistory
from app.tools.bw_connector import get_report, list_available_reports
from app.tools.sac_connector import SACConnector
from app.tools.screenshot_rpa import take_screenshot, has_session, login_interactive, clear_session
from app.agent import analyze_data, analyze_screenshot, natural_language_to_cron
from app.tools.slide_builder import generate_slides, generate_slides_from_screenshot
from app.tools.distributor import send_report
import app.config as cfg

app = FastAPI(title="D2SlideOS")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

UPLOAD_DIR = "output/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

_scheduler = AsyncIOScheduler(timezone='Asia/Shanghai')


def _make_cron_trigger(cron_expr: str):
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return CronTrigger.from_crontab(cron_expr, timezone='Asia/Shanghai')
    minute, hour, day, month, dow = parts
    if dow not in ('*',):
        def remap(w):
            return str((int(w) - 1) % 7)
        if '-' in dow:
            a, b = dow.split('-')
            dow = remap(a) + '-' + remap(b)
        elif ',' in dow:
            dow = ','.join(remap(w) for w in dow.split(','))
        else:
            dow = remap(dow)
    return CronTrigger(minute=minute, hour=hour, day=day, month=month,
                       day_of_week=dow, timezone='Asia/Shanghai')


def _get_sac() -> SACConnector:
    return SACConnector(
        base_url=cfg.SAC_BASE_URL,
        token_url=cfg.SAC_TOKEN_URL,
        client_id=cfg.SAC_CLIENT_ID,
        client_secret=cfg.SAC_CLIENT_SECRET,
    )


@app.on_event("startup")
def startup():
    init_db()
    _scheduler.start()
    _reload_schedules()


@app.on_event("shutdown")
def shutdown():
    _scheduler.shutdown(wait=False)


@app.get("/api/scheduler/jobs")
def scheduler_jobs():
    return [{"id": j.id, "next_run": str(j.next_run_time)} for j in _scheduler.get_jobs()]


@app.get("/")
def index():
    return FileResponse("app/static/index.html")


# ---------- SAC ----------

@app.get("/api/sac/status")
def sac_status():
    if not cfg.SAC_CLIENT_ID or not cfg.SAC_CLIENT_SECRET:
        return {"connected": False, "reason": "credentials_missing"}
    try:
        _get_sac().get_token()
        return {"connected": True}
    except Exception as e:
        return {"connected": False, "reason": str(e)}

@app.post("/api/sac/connect")
def sac_connect():
    if not cfg.SAC_CLIENT_ID or not cfg.SAC_CLIENT_SECRET:
        raise HTTPException(status_code=400, detail="SAC credentials not configured in .env")
    try:
        _get_sac().get_token()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/sac/stories")
def sac_stories():
    if not cfg.SAC_CLIENT_ID:
        raise HTTPException(status_code=401, detail="SAC credentials not configured")
    try:
        return _get_sac().list_stories()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ---------- RPA ----------

@app.get("/api/rpa/session-status")
def rpa_session_status():
    return {"has_session": has_session()}

@app.post("/api/rpa/login")
async def rpa_login(body: dict):
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url required")
    try:
        await asyncio.get_running_loop().run_in_executor(None, login_interactive, url)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rpa/logout")
def rpa_logout():
    clear_session()
    return {"ok": True}


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



@app.post("/api/schedule/parse")
async def parse_schedule(body: dict):
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    try:
        result = await asyncio.get_event_loop().run_in_executor(None, natural_language_to_cron, text)
        return result
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

# ---------- Reports ----------

@app.get("/api/reports/available")
def available_reports():
    return list_available_reports()


# ---------- Upload ----------

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    import shutil, uuid
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("csv", "xlsx", "xls"):
        raise HTTPException(status_code=400, detail="Only CSV/Excel files are supported")
    save_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_DIR, save_name)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": save_path, "filename": file.filename}


# ---------- Jobs ----------

class JobCreate(BaseModel):
    name: str
    report_type: str
    recipients: str = ""
    schedule: str = ""
    source: str = "screenshot"
    lang: str = "zh"
    model: str = "gpt-4o-mini"
    email_body: str = ""

@app.get("/api/jobs")
def list_jobs():
    db = SessionLocal()
    jobs = db.query(ReportJob).filter(ReportJob.is_active == True).all()
    db.close()
    return [{"id": j.id, "name": j.name, "report_type": j.report_type,
             "source": getattr(j, "source", "screenshot"),
             "recipients": j.recipients, "schedule": j.schedule,
             "lang": getattr(j, "lang", "zh"), "model": getattr(j, "model", "gpt-4o-mini"),
             "email_body": getattr(j, "email_body", ""), "created_at": j.created_at} for j in jobs]

@app.post("/api/jobs")
def create_job(body: JobCreate):
    db = SessionLocal()
    data = body.dict()
    job = ReportJob(**{k: v for k, v in data.items() if hasattr(ReportJob, k)})
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    job_name = job.name
    schedule = job.schedule
    snap = {"report_type": job.report_type, "name": job.name, "recipients": job.recipients,
            "source": getattr(job, "source", "screenshot"),
            "lang": getattr(job, "lang", "zh"), "model": getattr(job, "model", "gpt-4o-mini"),
            "email_body": getattr(job, "email_body", "")}
    db.close()

    if schedule:
        try:
            _scheduler.add_job(
                _run_scheduled_job,
                _make_cron_trigger(schedule),
                id=f"job_{job_id}",
                replace_existing=True,
                args=[job_id, snap],
            )
        except Exception:
            pass

    return {"id": job_id, "name": job_name}

@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int):
    db = SessionLocal()
    job = db.query(ReportJob).filter(ReportJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_active = False
    db.commit()
    db.close()
    try:
        _scheduler.remove_job(f"job_{job_id}")
    except Exception:
        pass
    return {"ok": True}


@app.patch("/api/jobs/{job_id}")
def update_job(job_id: int, body: JobCreate):
    db = SessionLocal()
    job = db.query(ReportJob).filter(ReportJob.id == job_id).first()
    if not job:
        db.close()
        raise HTTPException(status_code=404, detail="Job not found")
    for k, v in body.dict().items():
        if hasattr(job, k):
            setattr(job, k, v)
    db.commit()
    db.refresh(job)
    schedule = job.schedule
    snap = {"report_type": job.report_type, "name": job.name, "recipients": job.recipients,
            "source": job.source, "lang": job.lang, "model": job.model, "email_body": job.email_body}
    db.close()
    try:
        _scheduler.remove_job(f"job_{job_id}")
    except Exception:
        pass
    if schedule:
        try:
            _scheduler.add_job(
                _run_scheduled_job,
                _make_cron_trigger(schedule),
                id=f"job_{job_id}",
                replace_existing=True,
                args=[job_id, snap],
            )
        except Exception:
            pass
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
    job_snapshot = {
        "report_type": job.report_type,
        "name": job.name,
        "recipients": job.recipients,
        "source": getattr(job, "source", "screenshot"),
        "lang": getattr(job, "lang", "zh"),
        "model": getattr(job, "model", "gpt-4o-mini"),
        "email_body": getattr(job, "email_body", ""),
    }
    db.close()

    asyncio.create_task(_execute_run(run_id, job_snapshot))
    return {"run_id": run_id, "status": "running"}


async def _run_scheduled_job(job_id: int, job_snapshot: dict):
    db = SessionLocal()
    run = RunHistory(job_id=job_id, job_name=job_snapshot["name"])
    db.add(run)
    db.commit()
    db.refresh(run)
    run_id = run.id
    db.close()
    await _execute_run(run_id, job_snapshot)


async def _execute_run(run_id: int, job: dict):
    db = SessionLocal()
    run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
    try:
        loop = asyncio.get_event_loop()
        source = job.get("source", "screenshot")
        lang = job.get("lang", "zh")
        model = job.get("model", "gpt-4o-mini")
        original_model = cfg.AI_MODEL
        cfg.AI_MODEL = model
        try:
            if source == "screenshot":
                screenshot_path = await loop.run_in_executor(None, take_screenshot, job["report_type"])
                run.screenshot_path = screenshot_path
                insights = await loop.run_in_executor(None, analyze_screenshot, screenshot_path, lang)
                file_path = await loop.run_in_executor(
                    None, generate_slides_from_screenshot, screenshot_path, job["name"], insights, lang
                )
            elif source == "upload":
                import pandas as pd
                file_path_upload = job["report_type"]
                ext = file_path_upload.rsplit(".", 1)[-1].lower()
                if ext == "csv":
                    df = pd.read_csv(file_path_upload)
                else:
                    df = pd.read_excel(file_path_upload)
                insights = await loop.run_in_executor(None, analyze_data, df, lang)
                file_path = await loop.run_in_executor(None, generate_slides, df, job["name"], insights, lang)
            elif source == "sac":
                sac = _get_sac()
                df = await loop.run_in_executor(None, sac.export_story_data, job["report_type"])
                insights = await loop.run_in_executor(None, analyze_data, df, lang)
                file_path = await loop.run_in_executor(None, generate_slides, df, job["name"], insights, lang)
            else:
                df = await loop.run_in_executor(None, get_report, job["report_type"])
                insights = await loop.run_in_executor(None, analyze_data, df, lang)
                file_path = await loop.run_in_executor(None, generate_slides, df, job["name"], insights, lang)
        finally:
            cfg.AI_MODEL = original_model
        run.status = "success"
        run.insights = insights
        run.file_path = file_path
        if job.get("recipients"):
            try:
                await loop.run_in_executor(None, send_report, file_path, job["recipients"], job["name"], insights, job.get("email_body", ""), job.get("lang", "zh"))
            except Exception as mail_err:
                run.error = f"[邮件发送失败] {mail_err}"
    except Exception as e:
        run.status = "failed"
        run.error = str(e)
    finally:
        run.completed_at = datetime.utcnow()
        db.commit()
        db.close()


def _reload_schedules():
    db = SessionLocal()
    jobs = db.query(ReportJob).filter(ReportJob.is_active == True, ReportJob.schedule != "").all()
    for job in jobs:
        try:
            _scheduler.add_job(
                _run_scheduled_job,
                _make_cron_trigger(job.schedule),
                id=f"job_{job.id}",
                replace_existing=True,
                args=[job.id, {
                    "report_type": job.report_type,
                    "name": job.name,
                    "recipients": job.recipients,
                    "source": getattr(job, "source", "csv"),
                }],
            )
        except Exception:
            pass
    db.close()


# ---------- History ----------

@app.get("/api/history")
def get_history():
    db = SessionLocal()
    runs = db.query(RunHistory).order_by(RunHistory.started_at.desc()).limit(50).all()
    db.close()
    return [{"id": r.id, "job_name": r.job_name, "status": r.status,
             "started_at": r.started_at, "completed_at": r.completed_at,
             "insights": r.insights, "file_path": r.file_path,
             "has_screenshot": bool(getattr(r, "screenshot_path", None))} for r in runs]

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


@app.get("/api/history/{run_id}/screenshot")
def get_screenshot(run_id: int):
    db = SessionLocal()
    run = db.query(RunHistory).filter(RunHistory.id == run_id).first()
    db.close()
    path = getattr(run, "screenshot_path", None) if run else None
    if not path:
        raise HTTPException(status_code=404, detail="No screenshot")
    return FileResponse(path, media_type="image/png")

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