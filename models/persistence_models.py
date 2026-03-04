from sqlalchemy import Column, Integer, String, Boolean, Text, Enum, ForeignKey, JSON, MetaData, DateTime
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
from sqlalchemy.dialects.mysql import TIMESTAMP as MySQLTimestamp

Base = declarative_base()
metadata = MetaData()

class Application(Base):
    __tablename__ = 'applications'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_listing_id = Column(Integer, ForeignKey('job_listings.id', ondelete='CASCADE'), nullable=False)
    
    # Application state
    status = Column(Enum('pending', 'submitted', 'failed', 'cancelled'), default='pending')
    submission_attempts = Column(Integer, default=0)
    last_error = Column(Text)
    
    # Application data
    application_data = Column(JSON)  # Stores form data, resume info, etc.
    submitted_at = Column(DateTime)
    
    # Tracking
    created_at = Column(MySQLTimestamp, server_default="CURRENT_TIMESTAMP")
    updated_at = Column(MySQLTimestamp, server_default="CURRENT_TIMESTAMP", onupdate="CURRENT_TIMESTAMP")
    
    # Relationships
    job_listing = relationship("JobListing", backref="applications")

class Metric(Base):
    __tablename__ = 'metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_type = Column(String(50), nullable=False)  # e.g., 'application_success_rate', 'scraping_speed'
    metric_value = Column(String(255))  # Numeric or string value
    metric_data = Column(JSON)  # Additional context/data
    
    # Tracking
    created_at = Column(MySQLTimestamp, server_default="CURRENT_TIMESTAMP")
    updated_at = Column(MySQLTimestamp, server_default="CURRENT_TIMESTAMP", onupdate="CURRENT_TIMESTAMP")