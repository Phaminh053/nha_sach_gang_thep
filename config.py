import os
from datetime import timedelta
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _is_truthy(value):
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _is_railway_environment():
    return bool(os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RAILWAY_PROJECT_ID'))


def _build_mysql_uri_from_parts():
    host = os.environ.get('MYSQLHOST')
    port = os.environ.get('MYSQLPORT', '3306')
    user = os.environ.get('MYSQLUSER')
    password = os.environ.get('MYSQLPASSWORD', '')
    database = os.environ.get('MYSQLDATABASE')

    if not all([host, user, database]):
        return None

    encoded_user = quote_plus(user)
    encoded_password = quote_plus(password)
    auth = encoded_user if not password else f'{encoded_user}:{encoded_password}'
    return f'mysql+pymysql://{auth}@{host}:{port}/{database}?charset=utf8mb4'


def _get_database_uri():
    return (
        os.environ.get('DATABASE_URL')
        or os.environ.get('MYSQL_URL')
        or _build_mysql_uri_from_parts()
        or 'mysql+pymysql://root:@localhost:3306/nha_sach_gang_thep?charset=utf8mb4'
    )


def _get_default_config_name():
    if os.environ.get('FLASK_ENV'):
        return os.environ['FLASK_ENV']
    if _is_railway_environment():
        return 'production'
    return 'development'


def _get_cookie_secure():
    if 'SESSION_COOKIE_SECURE' in os.environ:
        return _is_truthy(os.environ['SESSION_COOKIE_SECURE'])
    return _is_railway_environment() or _get_default_config_name() == 'production'

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    # Supports Railway's MYSQL_URL / MYSQL* variables and local DATABASE_URL overrides.
    SQLALCHEMY_DATABASE_URI = _get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'echo': False  # Set to True for SQL debugging
    }
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)  # 24 hours
    SESSION_COOKIE_NAME = 'nha_sach_gang_thep_session'
    SESSION_COOKIE_SECURE = _get_cookie_secure()
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_USE_SIGNER = True
    
    # Logging configuration
    LOG_LEVEL = 'INFO'
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 24)))
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')
    
    # Pagination defaults
    DEFAULT_PAGE_SIZE = 24
    MAX_PAGE_SIZE = 100
    
    # MoMo Payment Configuration (Sandbox - Public Credentials)
    MOMO_PARTNER_CODE = os.environ.get('MOMO_PARTNER_CODE', 'MOMONPMB20210629')
    MOMO_ACCESS_KEY = os.environ.get('MOMO_ACCESS_KEY', 'Q2XhhSdgpKUlQ4Ky')
    MOMO_SECRET_KEY = os.environ.get('MOMO_SECRET_KEY', 'k6B53GQKSjktZGJBK2MyrDa7w9S6RyCf')
    MOMO_ENDPOINT = os.environ.get('MOMO_ENDPOINT', 'https://test-payment.momo.vn/v2/gateway/api/create')
    MOMO_QUERY_ENDPOINT = os.environ.get('MOMO_QUERY_ENDPOINT', 'https://test-payment.momo.vn/v2/gateway/api/query')
    
    # VNPay Payment Configuration (Sandbox)
    VNPAY_TMN_CODE = os.environ.get('VNPAY_TMN_CODE', 'PPA5QUQ1')
    VNPAY_HASH_SECRET = os.environ.get('VNPAY_HASH_SECRET', 'NV0RWNWJ6D3JEA9KMJE2MSORROA139C6')
    VNPAY_URL = os.environ.get('VNPAY_URL', 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'echo': True  # Enable SQL logging in development
    }

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config(config_name=None):
    """Get configuration class with validation"""
    if config_name is None:
        config_name = _get_default_config_name()
    
    config_class = config.get(config_name, DevelopmentConfig)
    
    # Validate production config
    if config_name == 'production':
        secret_key = os.environ.get('SECRET_KEY')
        if not secret_key:
            raise ValueError("No SECRET_KEY set for production")
        jwt_secret_key = os.environ.get('JWT_SECRET_KEY')
        if not jwt_secret_key:
            raise ValueError("No JWT_SECRET_KEY set for production")
    
    return config_class
