#!/usr/bin/env python3
"""
Database initialization script for Nha Sach Gang Thep
"""
import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import *
from app.models.user import User
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """Initialize database connection and models"""
    try:
        # Create Flask app
        app = create_app()
        
        with app.app_context():
            # Create all tables
            logger.info("Creating database tables...")
            db.create_all()
            
            logger.info("Database initialization completed successfully!")
            logger.info("Available tables:")
            
            # List available tables
            for table_name in db.metadata.tables.keys():
                logger.info(f"  - {table_name}")
                
            return True
            
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        return False

if __name__ == '__main__':
    success = init_database()
    sys.exit(0 if success else 1)