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
    report_type = Column(String, nullable=False)   # URL (screenshot) or csv id or SAC model id
    source = Column(String, default="screenshot")  # screenshot | upload | sac
    recipients = Column(String, default="")        # comma-separated emails
    schedule = Column(String, default="")          # cron expression, empty = manual only
    lang = Column(String, default="zh")            # zh | en
    model = Column(String, default="gpt-4o-mini")  # AI model per task
    email_body      = Column(Text,   default="")
    filter_field    = Column(String, default="")
    filter_mappings = Column(Text,   default="[]")
    chart_prompt    = Column(Text,   default="")   # natural language chart description
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


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)


class ReportAlias(Base):
    __tablename__ = "report_aliases"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    source = Column(String, default="screenshot")
    original_name = Column(String, default="")


def init_db():
    Base.metadata.create_all(bind=engine)
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    existing = {c["name"] for c in inspector.get_columns("report_jobs")}
    with engine.connect() as conn:
        for col, default in [
            ("source", "'screenshot'"),
            ("lang", "'zh'"),
            ("model", "'gpt-4o-mini'"),
            ("email_body", "''"),
            ("filter_field", "''"),
            ("filter_mappings", "'[]'"),
            ("chart_prompt", "''"),
        ]:
            if col not in existing:
                conn.execute(text(f"ALTER TABLE report_jobs ADD COLUMN {col} TEXT DEFAULT {default}"))
        existing_run = {c["name"] for c in inspector.get_columns("run_history")}
        if "screenshot_path" not in existing_run:
            conn.execute(text("ALTER TABLE run_history ADD COLUMN screenshot_path TEXT"))
        existing_alias = {c["name"] for c in inspector.get_columns("report_aliases")}
        if "original_name" not in existing_alias:
            conn.execute(text("ALTER TABLE report_aliases ADD COLUMN original_name TEXT DEFAULT ''"))
        conn.commit()