from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

engine = create_engine("sqlite:///aiden_ai.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class ReportJob(Base):
    __tablename__ = "report_jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    report_type = Column(String, nullable=False)  # sales | delivery | materials
    recipients = Column(String, nullable=False)   # comma-separated emails
    schedule = Column(String, default="")         # cron expression, empty = manual only
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RunHistory(Base):
    __tablename__ = "run_history"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, nullable=False)
    job_name = Column(String, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")    # running | success | failed
    file_path = Column(String, nullable=True)
    insights = Column(Text, nullable=True)
    error = Column(Text, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)
