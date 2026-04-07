"""
Django settings for cisis project.

Секреты (пароли, ключи) читаются из файла .env в корне проекта.
Файл .env НЕ попадает в Git — у каждого окружения свой.
Шаблон: .env.example
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env из корня проекта
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


# ---------------------------------------------------------------------
# БЕЗОПАСНОСТЬ
# ---------------------------------------------------------------------
_debug_env = os.getenv('DEBUG', 'False')
DEBUG = _debug_env in ('True', 'true', '1')

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-LOCAL-DEV-ONLY-NOT-FOR-PRODUCTION'
    else:
        raise RuntimeError('SECRET_KEY не задан в .env — продакшен не запустится без него')

ALLOWED_HOSTS = [
    h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()
]


# ---------------------------------------------------------------------
# ПРИЛОЖЕНИЯ
# ---------------------------------------------------------------------
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cisis.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'core' / 'templates',
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'cisis.wsgi.application'
ASGI_APPLICATION = 'cisis.asgi.application'   # ⭐ v3.40.0

# ---------------------------------------------------------------------
# БАЗА ДАННЫХ
# ---------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'CISIS'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}


# ---------------------------------------------------------------------
# ВАЛИДАЦИЯ ПАРОЛЕЙ
# ---------------------------------------------------------------------
# Отключена — используется собственная модель User с кастомным
# хешированием паролей.
# ---------------------------------------------------------------------
# ═══ v3.51.0: Валидация паролей ═══
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ---------------------------------------------------------------------
# ИНТЕРНАЦИОНАЛИЗАЦИЯ
# ---------------------------------------------------------------------
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------
# СТАТИКА И МЕДИА
# ---------------------------------------------------------------------
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.getenv('MEDIA_ROOT', str(BASE_DIR / 'media'))

# Максимальный размер загружаемого файла (50 МБ)
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800

ALLOWED_FILE_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.rtf',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff',
    '.mp4', '.avi', '.mov', '.mkv', '.wmv',
    '.zip', '.rar', '.7z',
]


# ---------------------------------------------------------------------
# АУТЕНТИФИКАЦИЯ
# ---------------------------------------------------------------------
AUTH_USER_MODEL = 'core.User'

AUTHENTICATION_BACKENDS = [
    'core.auth_backend.CustomUserBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# LOGIN_URL = '/admin/login/'
LOGIN_URL = '/workspace/login/'
LOGIN_REDIRECT_URL = '/workspace/'

# ⭐ v3.40.0: Channels (чат)
if DEBUG:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [("redis", 6379)],
            },
        }
    }

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# ⭐ v3.51.0: Кеш для rate limiting (brute-force защита)
if DEBUG:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': 'redis://redis:6379/1',
        }
    }
CSRF_TRUSTED_ORIGINS = [
    'https://cisis-workspace.ru',
    'https://www.cisis-workspace.ru',
    'https://cisisworkspace.ru',
]

# ═══ v3.51.0: Безопасность cookies и сессий ═══
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 86400              # 24 часа (вместо 14 дней)
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ═══ S3 Object Storage (REG.Cloud) ═══
AWS_ACCESS_KEY_ID = os.getenv('S3_ACCESS_KEY')
AWS_SECRET_ACCESS_KEY = os.getenv('S3_SECRET_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'cisis-media')
AWS_S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL', 'https://s3.regru.cloud')
AWS_S3_REGION_NAME = 'us-east-1'
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = 'private'
AWS_QUERYSTRING_AUTH = True
AWS_QUERYSTRING_EXPIRE = 3600  # подписанные URL живут 1 час

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_S3_VERIFY = False

S3_ENABLED = os.getenv('S3_ENABLED', '').lower() not in ('false', '0', 'no', '')