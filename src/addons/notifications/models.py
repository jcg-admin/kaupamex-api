"""Models — addons.notifications (en disolución hacia ``mail``).

Todos los modelos del addon se reubicaron a su hogar Odoo ``addons.mail``
(disolución notifications→mail):

- ``Notification`` + ``NotificationType`` (buzón, UC-NOT-01..05) — slice 3a.
- ``NotificationPreference`` (opt-in/opt-out, UC-NOT-06) — slice 3b.
- ``ManualNotification`` + fan-out (broadcast admin, UC-NOT-07) — slice 3c.
- ``EmailTask`` (cola legacy) — **retirada** en slice 3d: sus datos ya se
  copiaron a ``mail.mail`` (``mail.0009``) y la tabla
  ``notifications_emailtask`` se elimina en ``notifications.0006``.

Este módulo ya no define modelos. El addon conserva por ahora sus
views/serializers/urls (consumen los modelos de ``mail``); su retiro completo
es el slice 3e.
"""
