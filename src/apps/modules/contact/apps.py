"""
apps.modules.contact — UC-COM (formulario publico de contacto).

Frontera con apps.modules.support (D-001):
  apps.modules.contact  -> mensajes anonimos (no requieren autenticacion) enviados
                  desde el formulario publico de contacto. No hay workflow
                  de estado, solo flags `read` y `replied`. El admin puede
                  responder y la respuesta queda embebida en el propio
                  ContactMessage (`reply_body`, `reply_sent_at`,
                  `reply_sent_by`); no existe hilo de conversacion.
                  Modelo: ContactMessage.
  apps.modules.support  -> tickets estructurados con workflow, hilo de respuestas,
                  notas internas y owner autenticado.

Regla simple:
  captura simple desde sitio publico  -> apps.modules.contact.
  conversacion + estados + ownership -> apps.modules.support.
"""
from django.apps import AppConfig


class ContactConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.modules.contact'
    verbose_name = 'Contacto'
