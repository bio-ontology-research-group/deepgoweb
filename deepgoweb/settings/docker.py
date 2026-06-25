"""Docker / container settings — everything operational comes from the environment
so one image runs unchanged in dev and prod. Falls back to the dev defaults in
``base.py`` when a variable is unset.

Selected with ``DJANGO_SETTINGS_MODULE=deepgoweb.settings.docker`` (see the
Dockerfile / docker-compose.yml).
"""
import os

from .base import *  # noqa: F401,F403

# --- core ---
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', SECRET_KEY)  # noqa: F405
DEBUG = os.environ.get('DJANGO_DEBUG', '0') == '1'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if o
]

# --- database (postgres in compose; override entirely via env) ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'deepgoweb'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
        'HOST': os.environ.get('POSTGRES_HOST', 'db'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

# --- static files (collected into the image / a volume, served by whitenoise-less
#     gunicorn behind a reverse proxy, or by the proxy directly) ---
STATIC_ROOT = os.environ.get('DJANGO_STATIC_ROOT', '/app/static')

# --- celery broker / backend ---
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)  # noqa: F405

# --- legacy DeepGOPlus release data (per-Release data_root lives under here) ---
RELEASE_DATA_ROOT = os.environ.get('RELEASE_DATA_ROOT', '/opt-data/extracted/')

# FUSEKI_URL and the DGPP_LIGHT asset knobs are already env-driven in base.py.
