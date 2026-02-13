from pathlib import Path
from decouple import config, Csv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Load from .env file
SECRET_KEY = config('SECRET_KEY')  # No default - must be set in .env
DEBUG = config('DEBUG', default=False, cast=bool)  # Default to False for security
INSTANCE = config('INSTANCE', default='production')

# Parse ALLOWED_HOSTS from .env
# For production: Set ALLOWED_HOSTS in .env like: ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
# For development with ngrok: ALLOWED_HOSTS=localhost,127.0.0.1,*.ngrok-free.dev
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

INSTALLED_APPS = [
    'grappelli',
    'nested_admin',
    'django.contrib.admin',
    'django.contrib.auth',  
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'simple_history',
    'tenants',  # Multi-site support
    'manufacturing',
    'commercial',
    'inventory',
    'costing',
    'transport',
    'compliance',
    'incident_management',
    'product_details',
    'foodlinecontrol',
    'smart_selects',
    'human_resources',
    'easy_select2',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'tenants.middleware.SiteMiddleware',  # Multi-site middleware - after auth
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'foodlinecontrol.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'foodlinecontrol.context_processors.admin_background',
                'foodlinecontrol.context_processors.site_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'foodlinecontrol.wsgi.application'

# Dynamic database configuration based on .env
DATABASE_ENGINE = config('DATABASE_ENGINE', default='django.db.backends.sqlite3')

# Check if using PostgreSQL or SQLite
if 'postgresql' in DATABASE_ENGINE:
    DATABASES = {
        'default': {
            'ENGINE': DATABASE_ENGINE,
            'NAME': config('DATABASE_NAME', default='foodlinecontrol'),
            'USER': config('DATABASE_USER', default='foodlinecontrol_user'),
            'PASSWORD': config('DATABASE_PASSWORD', default=''),
            'HOST': config('DATABASE_HOST', default='localhost'),
            'PORT': config('DATABASE_PORT', default='5432'),
        }
    }
else:
    # SQLite configuration (default)
    DATABASES = {
        'default': {
            'ENGINE': DATABASE_ENGINE,
            'NAME': BASE_DIR / config('DATABASE_NAME', default='db.sqlite3'),
        }
    }

USE_L10N = False  # keep this

DATE_FORMAT = "d-m-Y"
DATETIME_FORMAT = "d-m-Y H:i"

DATETIME_INPUT_FORMATS = [
    "%d-%m-%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
]

DATE_INPUT_FORMATS = [
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
]

# Grappelli date/time formats (used by JS widgets)
GRAPPELLI_DATE_FORMAT = "%d-%m-%Y"
GRAPPELLI_DATETIME_FORMAT = "%d-%m-%Y %H:%M"

# ============================================================================
# SECURITY SETTINGS FOR PRODUCTION
# ============================================================================

# SSL/HTTPS Configuration
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)  # Set True in production
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')  # For reverse proxy/load balancer

# Cookie Security
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)  # Set True in production (HTTPS only)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)  # Set True in production (HTTPS only)
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
CSRF_COOKIE_HTTPONLY = True  # Prevent JavaScript access to CSRF cookie
SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
CSRF_COOKIE_SAMESITE = 'Lax'  # CSRF protection

# HTTP Strict Transport Security (HSTS)
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=0, cast=int)  # Set 31536000 (1 year) in production
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=False, cast=bool)

# Content Security
SECURE_CONTENT_TYPE_NOSNIFF = True  # Prevent MIME-sniffing
X_FRAME_OPTIONS = 'SAMEORIGIN'  # Prevent clickjacking (allows same-origin iframes)

# CSRF & CORS Configuration
# For production: Set CSRF_TRUSTED_ORIGINS in .env like: CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='http://localhost:8000,http://127.0.0.1:8000', cast=Csv())

# ============================================================================
# PASSWORD VALIDATION
# ============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Johannesburg'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]

# Suppress warnings about duplicate static files (Grappelli overrides Django admin files)
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Login URL - redirect to admin login
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/admin/'  # Changed from /hq/ to break redirect loop
LOGOUT_REDIRECT_URL = '/admin/logout/'  # Custom logout view handles redirection

# Development indicator for templates
if INSTANCE == 'development':
    SITE_TITLE = "Goshen ERP (DEV - Test Version)"
else:
    SITE_TITLE = "Goshen ERP (PROD - Original)"
