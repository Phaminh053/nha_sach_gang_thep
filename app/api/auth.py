"""Authentication API endpoints"""

from flask import request, jsonify, session
from app.api import api_bp
from app.api.errors import ValidationAPIError, NotFoundError, BusinessLogicError
from app.auth import authenticate_user, register_user, generate_access_token, get_current_user, login_required, blacklist_token
from marshmallow import Schema, fields, validate


class LoginSchema(Schema):
    """Schema for user login"""
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=6))


class RegisterSchema(Schema):
    """Schema for user registration"""
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=6))
    full_name = fields.String(required=True, validate=validate.Length(min=2, max=100))
    phone = fields.String(required=True, validate=validate.Length(min=10, max=30))


@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    """API login endpoint"""
    try:
        if not request.is_json:
            raise ValidationAPIError("Request must be JSON")
        
        # Validate request data
        schema = LoginSchema()
        try:
            data = schema.load(request.get_json())
        except Exception as e:
            raise ValidationAPIError(f"Validation error: {str(e)}")
        
        # Authenticate user
        user, error = authenticate_user(data['email'], data['password'])
        if error:
            raise NotFoundError("User", "Invalid email or password")
        
        # Generate JWT token
        access_token = generate_access_token(user.id)
        
        return jsonify({
            'access_token': access_token,
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'phone': user.phone,
                'role_code': user.role_code
            }
        }), 200
        
    except Exception as e:
        if isinstance(e, (ValidationAPIError, NotFoundError)):
            raise
        raise BusinessLogicError(f"Login failed: {str(e)}")


@api_bp.route('/auth/register', methods=['POST'])
def api_register():
    """API registration endpoint"""
    try:
        if not request.is_json:
            raise ValidationAPIError("Request must be JSON")
        
        # Validate request data
        schema = RegisterSchema()
        try:
            data = schema.load(request.get_json())
        except Exception as e:
            raise ValidationAPIError(f"Validation error: {str(e)}")
        
        # Register user
        user, error = register_user(
            email=data['email'],
            password=data['password'],
            full_name=data['full_name'],
            phone=data['phone']
        )
        
        if error:
            if "already registered" in error:
                raise ValidationAPIError(error)
            raise BusinessLogicError(error)
        
        # Generate JWT token
        access_token = generate_access_token(user.id)
        
        return jsonify({
            'access_token': access_token,
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'phone': user.phone,
                'role_code': user.role_code
            }
        }), 201
        
    except Exception as e:
        if isinstance(e, (ValidationAPIError, BusinessLogicError)):
            raise
        raise BusinessLogicError(f"Registration failed: {str(e)}")


@api_bp.route('/auth/logout', methods=['POST'])
@login_required
def api_logout():
    """API logout endpoint"""
    try:
        # Get the token from Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            # Add token to blacklist
            blacklist_token(token)
        
        return jsonify({
            'message': 'Logged out successfully'
        }), 200
        
    except Exception as e:
        raise BusinessLogicError(f"Logout failed: {str(e)}")


@api_bp.route('/auth/me', methods=['GET'])
@login_required
def api_get_current_user():
    """Get current authenticated user info"""
    try:
        user = get_current_user()
        
        return jsonify({
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'phone': user.phone,
                'role_code': user.role_code
            }
        }), 200
        
    except Exception as e:
        raise BusinessLogicError(f"Failed to get user info: {str(e)}")