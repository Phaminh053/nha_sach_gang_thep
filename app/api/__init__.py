"""API Blueprint initialization"""

from flask import Blueprint

# Create blueprints
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# Import routes to register them
from app.api import public, auth, chat, backend, inventory