"""
DuckDB Connection Manager (Singleton Pattern)
Handles all database connections for both configuration and history.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from config.settings import settings
import logging
import os

logger = logging.getLogger(__name__)

# Base class for ORM models
Base = declarative_base()

class DuckDBConnection:
    """Singleton connection manager for DuckDB"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DuckDBConnection, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize DuckDB connection and session factory"""
        try:
            # Ensure directory exists
            db_path = settings.DUCKDB_PATH
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            # Create DuckDB engine
            # SQLAlchemy URL format: duckdb:///path/to/file
            db_url = f"duckdb:///{db_path}"
            
            self.engine = create_engine(
                db_url,
                echo=False,  # Set to True for SQL debugging
                connect_args={'read_only': False}
            )
            
            # Create session factory
            self.SessionLocal = scoped_session(
                sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=self.engine
                )
            )
            
            logger.info(f"DuckDB connection initialized at: {db_path}")
            
        except Exception as e:
            logger.critical(f"Failed to initialize DuckDB connection: {e}")
            raise
    
    def get_session(self):
        """Get a new database session"""
        return self.SessionLocal()
    
    def close_session(self, session):
        """Close a database session"""
        if session:
            session.close()
    
    def execute_sql_file(self, sql_file_path):
        """Execute SQL file (for initialization)"""
        try:
            import duckdb
            
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Use DuckDB directly for initialization (more reliable than SQLAlchemy for DDL)
            db_path = settings.DUCKDB_PATH
            conn = duckdb.connect(db_path)
            
            try:
                # Execute the entire SQL file at once
                conn.execute(sql_content)
                logger.info(f"Successfully executed SQL file: {sql_file_path}")
                return True
            finally:
                conn.close()
            
        except Exception as e:
            logger.error(f"Error executing SQL file {sql_file_path}: {e}")
            import traceback
            traceback.print_exc()
            return False

# Singleton instance
db = DuckDBConnection()
