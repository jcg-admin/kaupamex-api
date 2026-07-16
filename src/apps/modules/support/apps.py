"""
apps.modules.support — UC-SUPP (tickets de soporte post-venta).

Frontera con apps.modules.contact (D-001):
  apps.modules.support  -> tickets estructurados con workflow de estado
                  (OPEN -> IN_PROGRESS -> AWAITING_USER -> RESOLVED -> CLOSED),
                  hilo de respuestas (SupportTicketReply), notas internas
                  y owner = comprador autenticado (FK a AUTH_USER_MODEL).
                  Modelos: SupportTicket, SupportTicketReply.
  apps.modules.contact  -> mensajes anonimos del formulario publico de contacto,
                  sin workflow, con respuesta opcional del admin embebida
                  en el propio mensaje (no hay hilo).

Regla simple:
  conversacion + estados + ownership -> apps.modules.support.
  captura simple desde sitio publico  -> apps.modules.contact.
"""
from django.apps import AppConfig


class SupportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.modules.support'
    verbose_name = 'Soporte (Tickets)'
