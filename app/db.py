from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker
from flask import current_app
import logging

logger = logging.getLogger(__name__)

# Global variables for database components
engine = None
Session = None
Base = None

def init_db(app):
    """Initialize database connection and automap models"""
    global engine, Session, Base
    
    try:
        # Create engine
        engine = create_engine(
            app.config['SQLALCHEMY_DATABASE_URI'],
            **app.config['SQLALCHEMY_ENGINE_OPTIONS']
        )

        # Create session factory
        Session = sessionmaker(bind=engine)

        # Create automap base
        Base = automap_base()

        # Reflect the database schema
        Base.prepare(autoload_with=engine)

        logger.info("Database connection and automap initialization successful")

    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise

def get_session():
    """Get a new database session"""
    if Session is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return Session()

def get_db_session():
    """Get a new database session (alias for get_session)"""
    return get_session()

def close_session(session):
    """Close a database session"""
    try:
        session.close()
    except Exception as e:
        logger.error(f"Error closing session: {str(e)}")

def get_engine():
    """Get the database engine"""
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return engine

def get_base():
    """Get the automap base"""
    if Base is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return Base