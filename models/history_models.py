"""
SQLAlchemy ORM Models for History Tables
Database: DuckDB (job_engine.duckdb)
"""

from sqlalchemy import Column, Integer, BigInteger, String, Text, Float, Date, TIMESTAMP, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from data.db_connection import Base

class Application(Base):
    """Application submission history"""
    __tablename__ = 'applications'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_site_id = Column(Integer, ForeignKey('job_sites.id'), nullable=False)
    job_listing_id = Column(BigInteger, ForeignKey('job_listings.id'))
    
    # Job Info
    job_title = Column(String(255))
    job_url = Column(Text)
    
    # Result
    status = Column(String(20), nullable=False)  # 'success', 'failed', 'skipped'
    error_message = Column(Text)
    
    applied_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    __table_args__ = (
        CheckConstraint("status IN ('success', 'failed', 'skipped')"),
    )

class Metric(Base):
    """Performance tracking and analytics"""
    __tablename__ = 'metrics'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_date = Column(Date, nullable=False)
    job_site_id = Column(Integer, ForeignKey('job_sites.id'))
    
    # Counters
    total_jobs_found = Column(Integer, default=0)
    total_applications_attempted = Column(Integer, default=0)
    total_applications_successful = Column(Integer, default=0)
    total_applications_failed = Column(Integer, default=0)
    
    # Performance
    avg_application_time_seconds = Column(Float)
    
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
