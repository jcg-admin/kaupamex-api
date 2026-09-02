"""AppConfig — ``addons.html_builder`` (familia ``web`` de la referencia)."""
from django.apps import AppConfig


class HtmlBuilderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.html_builder'
    verbose_name = 'HTML Builder'

    #: **Sin ``ready()``**, y es la forma correcta, no un hueco: este addon no
    #: declara ningún modelo ni extiende ninguno — su lado de Python en la
    #: referencia son un ``__init__.py`` vacío y su manifiesto. Un ``ready()``
    #: vacío sugeriría que falta algo por colgar. Ver el docstring del paquete.
