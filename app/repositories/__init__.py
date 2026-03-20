"""Base repository class"""

from app.extensions import db
from sqlalchemy import and_, or_
from typing import Optional, List, Dict, Any


class BaseRepository:
    """Base repository with common database operations"""
    
    def __init__(self, model_class):
        self.model = model_class
    
    def get_by_id(self, id: int):
        """Get record by ID"""
        return self.model.query.get(id)
    
    def get_all(self, filters: Dict[str, Any] = None, limit: int = None, offset: int = None):
        """Get all records with optional filters"""
        query = self.model.query
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)
        
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
            
        return query.all()
    
    def create(self, **kwargs):
        """Create new record"""
        instance = self.model(**kwargs)
        db.session.add(instance)
        db.session.flush()  # To get the ID
        return instance
    
    def update(self, instance, **kwargs):
        """Update existing record"""
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        return instance
    
    def delete(self, instance):
        """Delete record"""
        db.session.delete(instance)
    
    def count(self, filters: Dict[str, Any] = None) -> int:
        """Count records with optional filters"""
        query = self.model.query
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)
        
        return query.count()
    
    def paginate(self, page: int = 1, per_page: int = 20, filters: Dict[str, Any] = None):
        """Paginate records"""
        query = self.model.query
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)
        
        return query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )