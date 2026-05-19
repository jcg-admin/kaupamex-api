"""
config package — PracticaYoruba API.

Importa la Celery app aqui para que `@shared_task` la encuentre
durante el arranque de Django. Ver D-004.
"""
from .celery import app as celery_app

__all__ = ('celery_app',)
