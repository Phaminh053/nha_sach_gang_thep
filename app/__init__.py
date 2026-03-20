"""Flask application factory"""

from flask import Flask
from app.extensions import init_extensions
from config import get_config
import os


def create_app(config_name=None):
    """Create and configure Flask application"""
    
    # Determine config
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    
    # Initialize extensions
    init_extensions(app)
    
    # Initialize custom database
    from app.db import init_db
    init_db(app)
    
    # Register Jinja filters
    @app.template_filter('vnd')
    def format_vnd(amount):
        """Format number as Vietnamese Dong currency"""
        if amount is None:
            return "0₫"
        return f"{int(amount):,}₫".replace(',', '.')
    
    @app.template_filter('vntime')
    def format_vntime(dt, fmt='%d/%m/%Y %H:%M'):
        """Convert UTC datetime to Vietnam timezone (UTC+7) and format"""
        if dt is None:
            return ''
        from datetime import timedelta
        # Add 7 hours to convert from UTC to Vietnam timezone
        vn_time = dt + timedelta(hours=7)
        return vn_time.strftime(fmt)
    
    @app.template_filter('avatar_icon')
    def get_avatar_icon(user):
        """Get avatar icon for user"""
        from app.utils.avatar_utils import get_default_avatar_icon
        return get_default_avatar_icon(user.id, user.username)
    
    @app.template_filter('avatar_color')
    def get_avatar_color(user):
        """Get avatar color for user"""
        from app.utils.avatar_utils import get_default_avatar_color
        return get_default_avatar_color(user.id, user.username)
    
    @app.template_filter('avatar_initials')
    def get_avatar_initials(user):
        """Get avatar initials for user"""
        from app.utils.avatar_utils import get_avatar_initials
        return get_avatar_initials(user.full_name, user.username)
    
    # Add context processor for current user
    @app.context_processor
    def inject_current_user():
        """Inject current user into all templates"""
        from app.auth import get_current_user
        return dict(current_user=get_current_user())
    
    # Import and register blueprints
    from app.api import api_bp
    app.register_blueprint(api_bp)
    
    # Register chatbot API blueprints
    from app.api.chat import chat_bp
    from app.api.backend import backend_bp
    from app.api.inventory import inventory_bp
    app.register_blueprint(chat_bp)
    app.register_blueprint(backend_bp)
    app.register_blueprint(inventory_bp)
    
    # Exempt API routes from CSRF protection
    from app.extensions import csrf
    csrf.exempt(api_bp)
    csrf.exempt(chat_bp)
    csrf.exempt(backend_bp)
    csrf.exempt(inventory_bp)
    
    # Import and register frontend blueprints
    from app.blueprints.site.views import site_bp
    app.register_blueprint(site_bp)
    
    # Import and register admin blueprint
    from app.blueprints.admin import admin_bp
    app.register_blueprint(admin_bp)
    
    # Register error handlers
    from app.api.errors import register_error_handlers
    register_error_handlers(app)
    
    @app.route('/health')
    def health_check():
        return {'status': 'healthy'}, 200
    
    return app
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        return render_template('500.html'), 500
    
    return app