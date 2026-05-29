from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aiden_ai.db")
engine = create_engine(f"sqlite:///{_DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class ReportJob(Base):
    __tablename__ = "report_jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    report_type = Column(String, nullable=False)   # URL (screenshot) or csv id or SAC story id
    source = Column(String, default="screenshot")  # screenshot | csv | sac
    recipients = Column(String, default="")        # comma-separated emails
    schedule = Column(String, default="")          # cron expression, empty = manual only
    lang = Column(String, default="zh")            # zh | en
    model = Column(String, default="gpt-4o-mini")  # AI model per task
    email_body = Column(Text, default="")           # custom email body
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RunHistory(Base):
    __tablename__ = "run_history"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, nullable=False)
    job_name = Column(String, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")     # running | success | failed
    file_path = Column(String, nullable=True)
    screenshot_path = Column(String, nullable=True)
    insights = Column(Text, nullable=True)
    error = Column(Text, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)
    # add columns that may not exist in older DBs
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    existing = {c["name"] for c in inspector.get_columns("report_jobs")}
    with engine.connect() as conn:
        for col, default in [("source","'screenshot'"), ("lang","'zh'"), ("model","'gpt-4o-mini'"), ("email_body","''")] :
            if col not in existing:
                conn.execute(text(f"ALTER TABLE report_jobs ADD COLUMN {col} TEXT DEFAULT {default}"))
        existing_run = {c["name"] for c in inspector.get_columns("run_history")}
        if "screenshot_path" not in existing_run:
            conn.execute(text("ALTER TABLE run_history ADD COLUMN screenshot_path TEXT"))
        conn.commit()