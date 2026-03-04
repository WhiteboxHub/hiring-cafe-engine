"""
SQLAlchemy ORM Models for Configuration Tables
Database: DuckDB (job_engine.duckdb)
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP, ForeignKey, JSON, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from data.db_connection import Base

class AtsPlatform(Base):
    """Defines automation strategies (e.g., Workday, Greenhouse, Custom)"""
    __tablename__ = 'ats_platforms'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    class_handler = Column(String(100), nullable=False)  # Python class path
    is_headless_required = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    job_sites = relationship("JobSite", back_populates="platform")
    selectors = relationship("SiteSelector", back_populates="ats_platform")

class JobSite(Base):
    """Company/job site configurations"""
    __tablename__ = 'job_sites'
    
    id = Column(Integer, primary_key=True)
    company_name = Column(String(100), nullable=False)
    domain = Column(String(255), unique=True, nullable=False)
    ats_platform_id = Column(Integer, ForeignKey('ats_platforms.id'))
    category = Column(String(50), nullable=False)
    
    # Navigation
    search_url_template = Column(Text, nullable=False)
    apply_url_template = Column(Text)
    
    # Bot Defense
    cf_clearance_required = Column(Boolean, default=False)
    proxy_region = Column(String(10), default='US')
    
    # Operational
    is_active = Column(Boolean, default=True)
    max_applications_per_run = Column(Integer, default=10)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    platform = relationship("AtsPlatform", back_populates="job_sites")
    selectors = relationship("SiteSelector", back_populates="job_site")
    listings = relationship("JobListing", back_populates="job_site")
    
    __table_args__ = (
        CheckConstraint("category IN ('System integrator', 'Consulting firm', 'Staffing vendor', 'Product Company')"),
    )

class SiteSelector(Base):
    """CSS/XPath selectors stored as JSON"""
    __tablename__ = 'site_selectors'
    
    id = Column(Integer, primary_key=True)
    ats_platform_id = Column(Integer, ForeignKey('ats_platforms.id'))
    job_site_id = Column(Integer, ForeignKey('job_sites.id'))
    type = Column(String(20), nullable=False)  # 'listing' or 'application'
    config_json = Column(JSON, nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    ats_platform = relationship("AtsPlatform", back_populates="selectors")
    job_site = relationship("JobSite", back_populates="selectors")
    
    __table_args__ = (
        CheckConstraint("type IN ('listing', 'application')"),
    )

class JobListing(Base):
    """Discovered jobs queue"""
    __tablename__ = 'job_listings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_site_id = Column(Integer, ForeignKey('job_sites.id'), nullable=False)
    
    # Job Data
    external_job_id = Column(String(100), nullable=False)
    job_title = Column(String(255))
    job_url = Column(Text, nullable=False)
    
    # Pipeline State
    status = Column(String(20), default='discovered')
    attempts = Column(Integer, default=0)
    last_error = Column(Text)
    
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    job_site = relationship("JobSite", back_populates="listings")
    
    __table_args__ = (
        CheckConstraint("status IN ('discovered', 'ready_to_apply', 'applied', 'failed', 'blacklisted')"),
    )
