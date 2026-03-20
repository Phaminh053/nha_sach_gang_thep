"""Idempotency utilities for preventing duplicate requests"""

import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


class IdempotencyManager:
    """Manage idempotency keys for requests"""
    
    def __init__(self):
        # In production, use Redis or database for storage
        # For now, use in-memory dict (will reset on restart)
        self._cache = {}
        self._ttl = timedelta(hours=24)  # Keys expire after 24 hours
    
    def generate_key(self) -> str:
        """Generate a new idempotency key"""
        return str(uuid.uuid4())
    
    def is_duplicate_request(self, key: str) -> bool:
        """Check if request with this key has been processed"""
        if not key:
            return False
        
        # Clean expired keys
        self._cleanup_expired()
        
        return key in self._cache
    
    def store_result(self, key: str, result: Any) -> None:
        """Store result for idempotency key"""
        if not key:
            return
        
        self._cache[key] = {
            'result': result,
            'timestamp': datetime.utcnow()
        }
    
    def get_cached_result(self, key: str) -> Optional[Any]:
        """Get cached result for idempotency key"""
        if not key or key not in self._cache:
            return None
        
        entry = self._cache[key]
        
        # Check if expired
        if datetime.utcnow() - entry['timestamp'] > self._ttl:
            del self._cache[key]
            return None
        
        return entry['result']
    
    def _cleanup_expired(self):
        """Remove expired entries from cache"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now - entry['timestamp'] > self._ttl
        ]
        
        for key in expired_keys:
            del self._cache[key]
    
    def validate_key_format(self, key: str) -> bool:
        """Validate idempotency key format (should be UUID)"""
        if not key:
            return False
        
        try:
            uuid.UUID(key)
            return True
        except ValueError:
            return False


# Global instance
idempotency_manager = IdempotencyManager()


def require_idempotency_key(func):
    """Decorator to require idempotency key for endpoints"""
    from functools import wraps
    from flask import request, jsonify
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        key = request.headers.get('Idempotency-Key')
        
        if not key:
            return jsonify({
                'error': {
                    'code': 'MISSING_IDEMPOTENCY_KEY',
                    'message': 'Idempotency-Key header is required for this operation'
                }
            }), 400
        
        if not idempotency_manager.validate_key_format(key):
            return jsonify({
                'error': {
                    'code': 'INVALID_IDEMPOTENCY_KEY',
                    'message': 'Idempotency-Key must be a valid UUID'
                }
            }), 400
        
        # Check for duplicate request
        cached_result = idempotency_manager.get_cached_result(key)
        if cached_result:
            return cached_result
        
        # Process request
        result = func(*args, **kwargs)
        
        # Cache result if successful
        if isinstance(result, tuple):
            response, status = result
            if 200 <= status < 300:
                idempotency_manager.store_result(key, result)
        else:
            idempotency_manager.store_result(key, result)
        
        return result
    
    return wrapper


def handle_idempotency(func):
    """Decorator to handle optional idempotency key"""
    from functools import wraps
    from flask import request
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        key = request.headers.get('Idempotency-Key')
        
        if key:
            # Validate key format
            if not idempotency_manager.validate_key_format(key):
                from flask import jsonify
                return jsonify({
                    'error': {
                        'code': 'INVALID_IDEMPOTENCY_KEY',
                        'message': 'Idempotency-Key must be a valid UUID'
                    }
                }), 400
            
            # Check for duplicate request
            cached_result = idempotency_manager.get_cached_result(key)
            if cached_result:
                return cached_result
        
        # Process request
        result = func(*args, **kwargs)
        
        # Cache result if key provided and successful
        if key and isinstance(result, tuple):
            response, status = result
            if 200 <= status < 300:
                idempotency_manager.store_result(key, result)
        elif key:
            idempotency_manager.store_result(key, result)
        
        return result
    
    return wrapper