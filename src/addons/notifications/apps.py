from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.notifications'
    verbose_name = 'Notificaciones'

    # Sin ready(): los signals de notificación transaccional
    # (``handlers``/``signals``) se reubicaron a ``addons.mail`` y se registran
    # en ``MailConfig.ready()`` (disolución notifications→mail, slice 3e-2). El
    # addon queda como shell: sin modelos (todos en ``mail``) y sin wiring de
    # signals; conserva por ahora views/serializers/urls (slice 3e-3) y sus
    # migraciones — que ``mail`` referencia en su grafo, por lo que no puede
    # salir de INSTALLED_APPS sin un squash.
