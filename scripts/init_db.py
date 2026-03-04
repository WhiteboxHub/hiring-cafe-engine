
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_connection import db
from config.settings import settings
from core.logger import logger

def init_database():
    """Initialize DuckDB database with schema and seed data"""
    try:
        logger.info("=" * 60)
        logger.info("Starting database initialization...")
        logger.info("=" * 60)
        
        # Get paths
        db_path = settings.DUCKDB_PATH
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'db',
            'schema.sql'
        )
        
        # Check if schema file exists
        if not os.path.exists(schema_path):
            logger.error(f"Schema file not found: {schema_path}")
            return False
        
        logger.info(f"Database path: {db_path}")
        logger.info(f"Schema file: {schema_path}")
        
        # Execute schema SQL
        logger.info("Executing schema.sql...")
        success = db.execute_sql_file(schema_path)
        
        if success:
            logger.info("=" * 60)
            logger.info("✅ Database initialized successfully!")
            logger.info("=" * 60)
            logger.info("\nNext steps:")
            logger.info("1. Review database at: {db_path}")
            logger.info("2. Test with: python scripts/main.py --dry-run")
            logger.info("3. Check seeded data for Insight Global")
            return True
        else:
            logger.error("Failed to initialize database")
            return False
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    init_database()
