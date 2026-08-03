"""``portal.mixin`` — compartición de un documento por token de acceso.

Adaptación fiel de Odoo ``portal/models/portal_mixin.py`` (LGPL-3, 136 loc,
leído completo). En la referencia es un ``AbstractModel`` que un documento
(``sale.order``, ``account.move``…) hereda para exponerse por link con un
``access_token`` que salta los permisos del destinatario. Aquí es un modelo
**abstracto** Django (``Meta.abstract = True``): el modelo que lo herede
obtiene los campos y métodos.

Qué se porta y qué NO (la referencia mezcla el token con la capa QWeb):

- ``access_token`` + ``_portal_ensure_token`` → **portado** (el token uuid es
  el núcleo).
- ``_get_share_url`` / ``get_portal_url`` → **portados** en su forma de
  armado de URL con ``access_token`` (el ``access_url`` es config del modelo
  que hereda; el redirect a ``/mail/view`` del chatter QWeb no se porta).
- ``_get_access_action`` / ``action_share`` → **NO**: devuelven
  ``ir.actions.act_url``/``act_window`` — acciones del cliente web de Odoo,
  sin análogo en el SPA.
- ``access_warning`` compute → **NO**: se muestra en la plantilla QWeb.
- El chatter con ``pid``/``hash`` (``_sign_token``) → **NO** (gap nombrado:
  la integración mail↔portal es un pase aparte). ``_get_share_url`` conserva
  la firma pero ignora ``pid`` con una nota.

La verificación del token contra el permiso (``_document_check_access``)
vive en ``../services.py`` — es del controlador en la referencia.
"""
import uuid
from urllib.parse import urlencode

import fields
import models


class PortalMixin(models.Model):
    """Mixin abstracto de documento compartible. ≙ ``portal.mixin``.

    El modelo concreto que lo herede debe sobreescribir ``access_url`` (o el
    método ``_compute_access_url``) para apuntar a su ruta del SPA.
    """

    access_token = fields.Char(
        max_length=64, blank=True, default='', db_index=True,
        verbose_name='Token de seguridad',
        help_text='Token que permite el acceso al documento por link, '
                  'saltando los permisos del destinatario (Odoo '
                  'access_token).',
    )

    class Meta:
        abstract = True

    # ``access_url`` es un campo compute en la referencia; aquí es un método
    # que el modelo concreto sobreescribe (Django no tiene campos compute no
    # almacenados de forma nativa sin un property).
    @property
    def access_url(self):
        """URL del documento en el portal. El modelo concreto la
        sobreescribe; el default '#' replica ``_compute_access_url``."""
        return '#'

    def _portal_ensure_token(self):
        """≙ ``_portal_ensure_token`` (portal_mixin.py:29-34): genera el
        token uuid la primera vez y lo devuelve."""
        if not self.access_token:
            self.access_token = str(uuid.uuid4())
            self.save(update_fields=['access_token'])
        return self.access_token

    def get_portal_url(self, suffix=None, query_string=None, anchor=None):
        """≙ ``get_portal_url`` (portal_mixin.py:116-135): la URL del
        documento con su ``access_token``.

        Divergencia declarada: ``report_type``/``download`` de la referencia
        sirven a su motor de reportes QWeb (``_show_report``), no portado —
        se omiten de la firma en vez de arrastrar parámetros muertos.
        """
        url = '%s%s?access_token=%s%s%s' % (
            self.access_url,
            suffix or '',
            self._portal_ensure_token(),
            query_string or '',
            '#%s' % anchor if anchor else '',
        )
        return url

    def _get_share_url(self, redirect=False, share_token=True):
        """≙ ``_get_share_url`` (portal_mixin.py:36-67): la URL de
        compartición con ``access_token``.

        El caller es responsable de haber verificado el permiso de lectura
        (en la referencia ``self.check_access('read')`` antes de emitir el
        token — aquí lo hace la vista/servicio que comparte). ``pid``/``hash``
        del chatter y ``signup_partner`` no se portan en este pase (gaps
        nombrados en ``models/__init__``).
        """
        params = {}
        if share_token and hasattr(self, 'access_token'):
            params['access_token'] = self._portal_ensure_token()
        query = ('?' + urlencode(params)) if params else ''
        return '%s%s' % (self.access_url, query)
