"""
User model for authentication
"""
from app.models import BaseModel
from app.extensions import db
from sqlalchemy import Boolean, String, DateTime, ForeignKey, Table
from datetime import datetime


# Association table for user-role many-to-many relationship
user_roles = Table('user_roles', db.Model.metadata,
    db.Column('user_id', db.BigInteger, ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.SmallInteger, ForeignKey('roles.id'), primary_key=True),
    db.Column('assigned_at', DateTime, default=datetime.utcnow)
)


class Role(db.Model):
    """Role model"""
    __tablename__ = 'roles'
    
    id = db.Column(db.SmallInteger, primary_key=True)
    code = db.Column(String(50), unique=True, nullable=False)
    name = db.Column(String(100), nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Role {self.code}>'


class User(BaseModel):
    """User model for authentication"""
    __tablename__ = 'users'
    
    # Basic info
    email = db.Column(String(255), unique=True, nullable=True, index=True)
    username = db.Column(String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(String(255), nullable=False)
    
    # Profile info
    full_name = db.Column(String(150), nullable=True)
    phone = db.Column(String(30), unique=True, nullable=True)
    avatar_url = db.Column(String(1024), nullable=True)
    
    # Account status
    is_active = db.Column(Boolean, default=True, nullable=False)
    email_verified = db.Column(Boolean, default=False, nullable=False)
    last_login_at = db.Column(DateTime, nullable=True)
    
    # Role relationship
    roles = db.relationship('Role', secondary=user_roles, backref='users')
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    @property
    def display_name(self):
        """Get user's display name"""
        return self.full_name or self.username
    
    @property
    def role_code(self):
        """Get user's primary role code for backward compatibility"""
        try:
            if self.roles and len(self.roles) > 0:
                return self.roles[0].code
        except Exception:
            pass
        return 'customer'  # default role
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login_at = datetime.utcnow()
    
    def is_admin(self):
        """Check if user is admin"""
        try:
            return any(role.code == 'admin' for role in self.roles) if self.roles else False
        except Exception:
            return False
    
    def is_customer(self):
        """Check if user is customer"""
        try:
            return any(role.code in ['customer', 'user'] for role in self.roles) if self.roles else True
        except Exception:
            return True
    
    def has_role(self, role_code):
        """Check if user has specific role"""
        try:
            return any(role.code == role_code for role in self.roles) if self.roles else False
        except Exception:
            return False
    
    def to_dict(self):
        """Convert user to dictionary for JSON responses"""
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'full_name': self.full_name,
            'display_name': self.display_name,
            'phone': self.phone,
            'avatar_url': self.avatar_url,
            'is_active': self.is_active,
            'email_verified': self.email_verified,
            'role_code': self.role_code,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }