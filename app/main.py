import os
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.models import init_db, SessionLocal, ReportJob, RunHistory, Contact, ReportAlias
from app.tools.bw_connector import get_report, list_available_reports
from app.tools.sac_connector import SACConnector
# screenshot_rpa disabled on BTP
def take_screenshot(*a, **kw): raise RuntimeError("Screenshot not available on BTP")
def take_screenshots(*a, **kw): raise RuntimeError("Screenshot not available on BTP")
def has_session(): return False
def login_interactive(*a, **kw): raise RuntimeError("Screenshot not available on BTP")
def clear_session(): pass
from app.agent import analyze_data, analyze_screenshot, natural_language_to_cron, parse_task_from_text
from app.tools.slide_builder import generate_slides, generate_slides_from_screenshot, generate_slides_from_screenshots
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

@app.get("/api/sac/models")
def sac_models():
    if not cfg.SAC_CLIENT_ID:
        raise HTTPException(status_code=401, detail="SAC credentials not configured")
    try:
        return _get_sac().list_models()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/sac/models/{model_id}/metadata")
def sac_model_metadata(model_id: str):
    if not cfg.SAC_CLIENT_ID:
        raise HTTPException(status_code=401, detail="SAC credentials not configured")
    try:
        return _get_sac().get_model_metadata(model_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/sac/models/{model_id}/data")
def sac_model_data(model_id: str, top: int = 100):
    if not cfg.SAC_CLIENT_ID:
        raise HTTPException(status_code=401, detail="SAC credentials not configured")
    try:
        df = _get_sac().get_model_data(model_id, top=top)
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/sac/sync-models")
async def sac_sync_models():
    """Fetch all SAC models, use AI to generate friendly aliases, upsert into ReportAlias table."""
    if not cfg.SAC_CLIENT_ID:
        raise HTTPException(status_code=401, detail="SAC credentials not configured")
    try:
        models = _get_sac().list_models()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    try:
        from app.agent import generate_model_aliases
        enriched = generate_model_aliases(models)
        print(f"[sync-models] first alias: {enriched[0]['alias'] if enriched else 'empty'}")
    except Exception as e:
        import traceback
        print(f"[sync-models] alias generation failed: {traceback.format_exc()}")
        enriched = [{"id": m["id"], "name": m["name"], "alias": m["name"]} for m in models]

    db = SessionLocal()
    db.query(ReportAlias).filter(ReportAlias.source == "sac").delete()
    for m in enriched:
        db.add(ReportAlias(name=m["alias"], url=m["id"], source="sac"))
    db.commit()
    db.close()
    return {"added": len(enriched), "updated": 0, "total": len(enriched)}




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



# ---------- Contacts ----------

class ContactCreate(BaseModel):
    name: str
    email: str

@app.get("/api/contacts")
def list_contacts():
    db = SessionLocal()
    rows = db.query(Contact).all()
    db.close()
    return [{"id": r.id, "name": r.name, "email": r.email} for r in rows]

@app.post("/api/contacts")
def create_contact(body: ContactCreate):
    db = SessionLocal()
    c = Contact(name=body.name.strip(), email=body.email.strip())
    db.add(c)
    db.commit()
    db.refresh(c)
    cid = c.id
    db.close()
    return {"id": cid, "name": body.name, "email": body.email}

@app.delete("/api/contacts/{cid}")
def delete_contact(cid: int):
    db = SessionLocal()
    c = db.query(Contact).filter(Contact.id == cid).first()
    if not c:
        db.close()
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(c)
    db.commit()
    db.close()
    return {"ok": True}


# ---------- Report Aliases ----------

class ReportAliasCreate(BaseModel):
    name: str
    url: str
    source: str = "screenshot"

@app.get("/api/report-aliases")
def list_report_aliases():
    db = SessionLocal()
    rows = db.query(ReportAlias).all()
    db.close()
    return [{"id": r.id, "name": r.name, "url": r.url, "source": r.source} for r in rows]

@app.post("/api/report-aliases")
def create_report_alias(body: ReportAliasCreate):
    db = SessionLocal()
    r = ReportAlias(name=body.name.strip(), url=body.url.strip(), source=body.source)
    db.add(r)
    db.commit()
    db.refresh(r)
    rid = r.id
    db.close()
    return {"id": rid, "name": body.name, "url": body.url, "source": body.source}

@app.delete("/api/report-aliases/{rid}")
def delete_report_alias(rid: int):
    db = SessionLocal()
    r = db.query(ReportAlias).filter(ReportAlias.id == rid).first()
    if not r:
        db.close()
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(r)
    db.commit()
    db.close()
    return {"ok": True}


# ---------- NL Task Parse ----------

@app.post("/api/jobs/parse-text")
async def parse_job_from_text(body: dict):
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    db = SessionLocal()
    contacts = [{"name": c.name, "email": c.email} for c in db.query(Contact).all()]
    report_aliases = [{"name": r.name, "url": r.url, "source": r.source} for r in db.query(ReportAlias).all()]
    db.close()
    try:
        parsed = await asyncio.get_running_loop().run_in_executor(
            None, parse_task_from_text, text, contacts, report_aliases
        )
        # resolve cron from schedule_text
        cron = ""
        cron_description = ""
        if parsed.get("schedule_text"):
            try:
                result = await asyncio.get_running_loop().run_in_executor(
                    None, natural_language_to_cron, parsed["schedule_text"]
                )
                cron = result.get("cron", "")
                cron_description = result.get("description", "")
            except Exception:
                pass
        return {
            "name": parsed.get("name", ""),
            "lang": parsed.get("lang", "zh"),
            "report_url": parsed.get("report_url", ""),
            "report_source": parsed.get("report_source", "screenshot"),
            "recipients": ", ".join(parsed.get("recipient_emails", [])),
            "schedule_text": parsed.get("schedule_text", ""),
            "cron": cron,
            "cron_description": cron_description,
            "email_body": parsed.get("email_body", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


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
    filter_field: str = ""
    filter_mappings: str = "[]"
    chart_prompt: str = ""

@app.get("/api/jobs")
def list_jobs():
    db = SessionLocal()
    jobs = db.query(ReportJob).filter(ReportJob.is_active == True).all()
    db.close()
    return [{"id": j.id, "name": j.name, "report_type": j.report_type,
             "source": getattr(j, "source", "screenshot"),
             "recipients": j.recipients, "schedule": j.schedule,
             "lang": getattr(j, "lang", "zh"), "model": getattr(j, "model", "gpt-4o-mini"),
             "email_body": getattr(j, "email_body", ""),
             "filter_field": getattr(j, "filter_field", ""),
             "filter_mappings": getattr(j, "filter_mappings", "[]"),
             "chart_prompt": getattr(j, "chart_prompt", ""),
             "created_at": j.created_at} for j in jobs]

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
            "email_body": getattr(job, "email_body", ""),
            "filter_field": getattr(job, "filter_field", ""),
            "filter_mappings": getattr(job, "filter_mappings", "[]"),
            "chart_prompt": getattr(job, "chart_prompt", "")}
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
            "source": job.source, "lang": job.lang, "model": job.model, "email_body": job.email_body,
            "filter_field": getattr(job, "filter_field", ""),
            "filter_mappings": getattr(job, "filter_mappings", "[]"),
            "chart_prompt": getattr(job, "chart_prompt", "")}
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
        "filter_field": getattr(job, "filter_field", ""),
        "filter_mappings": getattr(job, "filter_mappings", "[]"),
        "chart_prompt": getattr(job, "chart_prompt", ""),
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
                import json as _json
                mappings = _json.loads(job.get("filter_mappings", "[]") or "[]")
                if mappings:
                    # Filter-based personalized distribution
                    fp, last_paths = "", []
                    all_insights = []
                    first_screenshot = None
                    for m in mappings:
                        fv = m.get("value", "")
                        m_email = m.get("email", "")
                        cur_paths = await loop.run_in_executor(
                            None, take_screenshots, job["report_type"],
                            job.get("filter_field", ""), fv
                        )
                        cur_ins = await loop.run_in_executor(None, analyze_screenshot, cur_paths[0], lang)
                        all_insights.append(f"【{fv}】\n{cur_ins}")
                        cur_fp = await loop.run_in_executor(
                            None, generate_slides_from_screenshots,
                            cur_paths, f"{job['name']} — {fv}", [cur_ins], lang
                        )
                        print(f"[Run] filter={fv!r} recipients={m_email!r} file={cur_fp}")
                        if m_email:
                            try:
                                await loop.run_in_executor(
                                    None, send_report, cur_fp, m_email,
                                    f"{job['name']} — {fv}", cur_ins,
                                    job.get("email_body", ""), lang
                                )
                            except Exception as mail_err:
                                run.error = (run.error or "") + f"[{fv} 邮件失败] {mail_err}\n"
                        fp, last_paths = cur_fp, cur_paths
                        if first_screenshot is None:
                            first_screenshot = cur_paths[0]
                    run.file_path = fp
                    run.insights = "\n\n---\n\n".join(all_insights)
                    run.screenshot_path = first_screenshot
                    run.status = "success"
                else:
                    screenshot_paths = await loop.run_in_executor(None, take_screenshots, job["report_type"])
                    run.screenshot_path = screenshot_paths[0]
                    insights_list = []
                    for sp in screenshot_paths:
                        ins = await loop.run_in_executor(None, analyze_screenshot, sp, lang)
                        insights_list.append(ins)
                    insights = "\n\n---\n\n".join(insights_list)
                    file_path = await loop.run_in_executor(
                        None, generate_slides_from_screenshots, screenshot_paths, job["name"], insights_list, lang
                    )
                    run.status = "success"
                    run.insights = insights
                    run.file_path = file_path
                    print(f"[Run] recipients={job.get('recipients')!r} file={file_path}")
                    if job.get("recipients"):
                        try:
                            await loop.run_in_executor(None, send_report, file_path, job["recipients"], job["name"], insights, job.get("email_body", ""), job.get("lang", "zh"))
                        except Exception as mail_err:
                            run.error = f"[邮件发送失败] {mail_err}"
            elif source == "upload":
                import pandas as pd
                file_path_upload = job["report_type"]
                ext = file_path_upload.rsplit(".", 1)[-1].lower()
                if ext == "csv":
                    df = pd.read_csv(file_path_upload)
                else:
                    df = pd.read_excel(file_path_upload)
                insights = await loop.run_in_executor(None, analyze_data, df, lang)
                file_path = await loop.run_in_executor(None, generate_slides, df, job["name"], insights, lang, job.get("chart_prompt", ""))
                run.status = "success"
                run.insights = insights
                run.file_path = file_path
                if job.get("recipients"):
                    try:
                        await loop.run_in_executor(None, send_report, file_path, job["recipients"], job["name"], insights, job.get("email_body", ""), job.get("lang", "zh"))
                    except Exception as mail_err:
                        run.error = f"[邮件发送失败] {mail_err}"
            elif source == "sac":
                sac = _get_sac()
                report_type = job["report_type"]
                df = await loop.run_in_executor(None, sac.get_model_data, report_type)
                if df.empty:
                    raise ValueError(f"SAC 模型 {report_type} 返回空数据，请检查模型是否有数据或权限是否正确")
                from app.agent import infer_column_names
                df = await loop.run_in_executor(None, infer_column_names, df)
                insights = await loop.run_in_executor(None, analyze_data, df, lang)
                file_path = await loop.run_in_executor(None, generate_slides, df, job["name"], insights, lang, job.get("chart_prompt", ""))
                run.status = "success"
                run.insights = insights
                run.file_path = file_path
                if job.get("recipients"):
                    try:
                        await loop.run_in_executor(None, send_report, file_path, job["recipients"], job["name"], insights, job.get("email_body", ""), job.get("lang", "zh"))
                    except Exception as mail_err:
                        run.error = f"[邮件发送失败] {mail_err}"
            else:
                df = await loop.run_in_executor(None, get_report, job["report_type"])
                insights = await loop.run_in_executor(None, analyze_data, df, lang)
                file_path = await loop.run_in_executor(None, generate_slides, df, job["name"], insights, lang, job.get("chart_prompt", ""))
                run.status = "success"
                run.insights = insights
                run.file_path = file_path
                if job.get("recipients"):
                    try:
                        await loop.run_in_executor(None, send_report, file_path, job["recipients"], job["name"], insights, job.get("email_body", ""), job.get("lang", "zh"))
                    except Exception as mail_err:
                        run.error = f"[邮件发送失败] {mail_err}"
        finally:
            cfg.AI_MODEL = original_model
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        run.status = "failed"
        run.error = tb
        print(f"[Run ERROR] {tb}")
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
                    "filter_field": getattr(job, "filter_field", ""),
                    "filter_mappings": getattr(job, "filter_mappings", "[]"),
                    "chart_prompt": getattr(job, "chart_prompt", ""),
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