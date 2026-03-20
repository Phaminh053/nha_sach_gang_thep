"""Standardized error handling for API responses"""

from flask import jsonify
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException
import traceback


class APIError(Exception):
    """Base API error class"""
    
    def __init__(self, message: str, code: str = 'API_ERROR', status_code: int = 400, details: dict = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ValidationAPIError(APIError):
    """Validation error"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=message,
            code='VALIDATION_ERROR',
            status_code=400,
            details=details
        )


class NotFoundError(APIError):
    """Resource not found error"""
    
    def __init__(self, resource: str, identifier: str = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} '{identifier}' not found"
        
        super().__init__(
            message=message,
            code='NOT_FOUND',
            status_code=404
        )


class ConflictError(APIError):
    """Resource conflict error"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=message,
            code='CONFLICT',
            status_code=409,
            details=details
        )


class BusinessLogicError(APIError):
    """Business logic error"""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(
            message=message,
            code='BUSINESS_LOGIC_ERROR',
            status_code=422,
            details=details
        )


class OutOfStockAPIError(BusinessLogicError):
    """Out of stock error"""
    
    def __init__(self, product_name: str, requested: int, available: int):
        super().__init__(
            message=f"Insufficient stock for {product_name}",
            details={
                'product_name': product_name,
                'requested': requested,
                'available': available
            }
        )


def format_error_response(error_code: str, message: str, details: dict = None) -> dict:
    """Format standardized error response"""
    response = {
        'error': {
            'code': error_code,
            'message': message
        }
    }
    
    if details:
        response['error']['details'] = details
    
    return response


def register_error_handlers(app):
    """Register error handlers with Flask app"""
    
    @app.errorhandler(APIError)
    def handle_api_error(error):
        """Handle custom API errors"""
        response = format_error_response(
            error.code,
            error.message,
            error.details
        )
        return jsonify(response), error.status_code
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        """Handle Marshmallow validation errors"""
        response = format_error_response(
            'VALIDATION_ERROR',
            'Request validation failed',
            error.messages
        )
        return jsonify(response), 400
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 errors"""
        response = format_error_response(
            'NOT_FOUND',
            'Resource not found'
        )
        return jsonify(response), 404
    
    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        """Handle 405 errors"""
        response = format_error_response(
            'METHOD_NOT_ALLOWED',
            'Method not allowed for this endpoint'
        )
        return jsonify(response), 405
    
    @app.errorhandler(429)
    def handle_rate_limit(error):
        """Handle rate limit errors"""
        response = format_error_response(
            'RATE_LIMIT_EXCEEDED',
            'Too many requests. Please try again later.'
        )
        return jsonify(response), 429
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        """Handle internal server errors"""
        # Log the error
        app.logger.error(f"Internal server error: {str(error)}")
        app.logger.error(traceback.format_exc())
        
        response = format_error_response(
            'INTERNAL_SERVER_ERROR',
            'An internal server error occurred'
        )
        return jsonify(response), 500
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """Handle other HTTP exceptions"""
        response = format_error_response(
            f'HTTP_{error.code}',
            error.description
        )
        return jsonify(response), error.code


def validate_request_json(schema_class, request_json):
    """Validate request JSON with schema"""
    try:
        schema = schema_class()
        return schema.load(request_json)
    except ValidationError as e:
        raise ValidationAPIError("Request validation failed", e.messages)


def serialize_response(schema_class, data, many=False):
    """Serialize response data with schema"""
    schema = schema_class()
    return schema.dump(data, many=many)