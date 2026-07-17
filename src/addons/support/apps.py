"""
addons.support — UC-SUPP (tickets de soporte post-venta).

Frontera con addons.contact (D-001):
  addons.support  -> tickets estructurados con workflow de estado
                  (OPEN -> IN_PROGRESS -> AWAITING_USER -> RESOLVED -> CLOSED),
                  hilo de respuestas (SupportTicketReply), notas internas
                  y owner = comprador autenticado (FK a AUTH_USER_MODEL).
                  Modelos: SupportTicket, SupportTicketReply.
  addons.contact  -> mensajes anonimos del formulario publico de contacto,
                  sin workflow, con respuesta opcional del admin embebida
                  en el propio mensaje (no hay hilo).

Regla simple:
  conversacion + estados + ownership -> addons.support.
  captura simple desde sitio publico  -> addons.contact.
"""
from django.apps import AppConfig


class SupportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.support'
    verbose_name = 'Soporte (Tickets)'
