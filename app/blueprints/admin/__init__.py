"""
Admin blueprint initialization
"""
from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Import views after creating blueprint to avoid circular imports
from . import views