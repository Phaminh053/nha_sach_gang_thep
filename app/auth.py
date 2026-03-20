"""
Authentication utilities for the Nhà sách Gang Thép e-commerce application
"""
import bcrypt
import jwt
from datetime import datetime, timedelta
from flask import current_app, request, jsonify, session
from functools import wraps
from app.db import get_session, close_session
from app.models.user import User
import uuid

# Simple in-memory token blacklist (use Redis in production)
BLACKLISTED_TOKENS = set()

def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, password_hash):
    """Check if password matches the hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def generate_access_token(user_id):
    """Generate JWT access token"""
    expires_config = current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 3600)
    if isinstance(expires_config, timedelta):
        expires_seconds = int(expires_config.total_seconds())
    else:
        expires_seconds = expires_config
        
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(seconds=expires_seconds),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')

def decode_token(token):
    """Decode JWT token"""
    try:
        # Check if token is blacklisted
        if token in BLACKLISTED_TOKENS:
            return None
            
        payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def blacklist_token(token):
    """Add token to blacklist"""
    BLACKLISTED_TOKENS.add(token)

def get_current_user():
    """Get current user from JWT token or session"""
    from sqlalchemy.orm import joinedload
    
    # First, try JWT token authentication (for API)
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        payload = decode_token(token)
        if payload:
            session_db = get_session()
            try:
                user = session_db.query(User).options(joinedload(User.roles)).filter(
                    User.id == payload['user_id']
                ).first()
                if user:
                    # Trigger loading of roles to avoid DetachedInstanceError
                    _ = user.roles  # Access the relationship to load it
                return user
            finally:
                close_session(session_db)
    
    # Fallback to session-based authentication (for web UI)
    user_id = session.get('user_id')
    if user_id:
        session_db = get_session()
        try:
            user = session_db.query(User).options(joinedload(User.roles)).filter(
                User.id == user_id
            ).first()
            if user and user.is_active:
                # Trigger loading of roles to avoid DetachedInstanceError
                _ = user.roles  # Access the relationship to load it
                
                # Update session data if missing
                if not session.get('user_name'):
                    session['user_name'] = user.display_name
                if not session.get('user_email'):
                    session['user_email'] = user.email
                if not session.get('user_full_name'):
                    session['user_full_name'] = user.full_name
                if not session.get('user_phone'):
                    session['user_phone'] = user.phone
                if not session.get('user_role'):
                    session['user_role'] = user.role_code
                
                # Mark session as modified to ensure persistence
                session.modified = True
                
                return user
            else:
                # User not found or inactive, clear session
                session.clear()
        except Exception as e:
            # Database error, clear session for security
            session.clear()
            print(f"Session validation error: {e}")
        finally:
            close_session(session_db)
    
    return None

def login_required(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role for API routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        if user.role_code != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def admin_required_web(f):
    """Decorator to require admin role for web routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import flash, redirect, url_for
        user = get_current_user()
        if not user:
            flash('Vui lòng đăng nhập để tiếp tục', 'error')
            return redirect(url_for('site.login', next=request.url))
        if user.role_code != 'admin':
            flash('Bạn không có quyền truy cập trang này', 'error')
            return redirect(url_for('site.home'))
        return f(*args, **kwargs)
    return decorated_function

def get_cart_session():
    """Get or create cart session ID"""
    cart_session_id = session.get('cart_session_id')
    if not cart_session_id:
        cart_session_id = str(uuid.uuid4())
        session['cart_session_id'] = cart_session_id
    return cart_session_id

def register_user(email, password, full_name, phone):
    """Register a new user"""
    session_db = get_session()
    try:
        # Check if user already exists
        existing_user = session_db.query(User).filter(
            User.email == email
        ).first()
        
        if existing_user:
            return None, "Email already registered"
        
        # Create new user
        password_hash = hash_password(password)
        user_id = str(uuid.uuid4())
        
        # Create new user
        new_user = User(
            id=user_id,
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            phone=phone,
            role_code='customer',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session_db.add(new_user)
        session_db.commit()
        
        return new_user, None
        
    except Exception as e:
        session_db.rollback()
        return None, str(e)
    finally:
        close_session(session_db)

def authenticate_user(email, password):
    """Authenticate user login"""
    from sqlalchemy.orm import joinedload
    
    session_db = get_session()
    try:
        user = session_db.query(User).options(joinedload(User.roles)).filter(
            User.email == email
        ).first()
        
        if user and check_password(password, user.password_hash):
            # Trigger loading of roles to avoid DetachedInstanceError
            _ = user.roles  # Access the relationship to load it
            return user, None
        
        return None, "Invalid email or password"
        
    except Exception as e:
        return None, str(e)
    finally:
        close_session(session_db)