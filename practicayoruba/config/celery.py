"""
Celery application — PracticaYoruba API (D-004).

Minima inicializacion para que `@shared_task` registre tasks contra
esta app. En tests/dev el broker es `memory://` y
`CELERY_TASK_ALWAYS_EAGER=True`, por lo que no se requiere redis.
"""
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('practicayoruba')

# Lee config desde Django settings, prefijo CELERY_.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubre tasks.py en cada INSTALLED_APP.
app.autodiscover_tasks()
