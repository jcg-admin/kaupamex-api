"""``mail.tracking.value`` colgado por ``account`` — protección del rastro de auditoría.

Adaptación de ``addons/account/models/mail_tracking_value.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03). Dos símbolos, los dos portados:

======================  ==========================================
Símbolo                 Estado
======================  ==========================================
``_except_audit_log``   portado — delega en ``MailMessage._except_audit_log``
``write``               portado — dispara la guarda antes de escribir
======================  ==========================================

**Bloqueado por pieza concreta ausente (transitivo).** El guardián real vive
en ``account/models/mail_message.py::_except_audit_log`` de este mismo pase,
que a su vez está bloqueado porque ``res.company`` no declara
``restrictive_audit_trail`` (medido: ``grep -rn restrictive_audit_trail
src/ addons/`` → 0 hits antes de este pase). Este archivo delega fielmente en
ese guardián — la cadena de protección queda **completa en estructura** y
**inerte en efecto** hasta que ``restrictive_audit_trail`` exista. Ver el
docstring de ``mail_message.py`` para la medición completa y el sucesor.

``@api.ondelete(at_uninstall=True)`` → ``delete()``
====================================================

Mismo criterio que ``account_account_tag.py::delete()`` (``odoo19c:
account_account_tag.py:110-120``, adaptado aquí): el punto equivalente en
este stack para una guarda de Odoo enganchada a ``@api.ondelete`` es el
``delete()`` del modelo Django. ``at_uninstall=True`` en la referencia
significa que el guard corre incluso durante la desinstalación de un módulo
— aquí no hay ese concepto (no hay instalación/desinstalación de apps en
caliente), así que el guard corre siempre, que es el superconjunto correcto.
"""
from addons.mail.models.mail_tracking_value import MailTrackingValue
from orm.method_chain import chain_method


def _except_audit_log(self):
    """≙ ``odoo19c: account/models/mail_tracking_value.py:9-10``.

    Delega en el mensaje asociado — el valor rastreado no decide por sí
    mismo si está protegido, lo decide el mensaje que lo contiene.
    """
    self.message._except_audit_log()


def delete(self, *args, **kwargs):
    """≙ ``@api.ondelete(at_uninstall=True) def _except_audit_log`` +
    ``write`` (``odoo19c: mail_tracking_value.py:9-15``).

    La referencia separa el guard de borrado (``@api.ondelete``) del guard
    de escritura (``write``). Aquí ``delete()`` es el punto de borrado; la
    escritura se cubre abajo con ``chain_method`` sobre ``save()`` — ver
    ``apply_account_extensions``.

    Devuelve ``None`` a propósito: bajo ``chain_method`` (semántica de
    relevo) eso hace que se invoque la implementación previa —el
    ``delete()`` real de Django— después de que la guarda ya corrió y no
    lanzó. Llamar a ``super()`` aquí directamente saltaría la cadena de
    otros addons que también extiendan ``delete`` (ver el docstring de
    ``orm/method_chain.py``).
    """
    self._except_audit_log()


def save(self, *args, **kwargs):
    """≙ ``write`` (``odoo19c: mail_tracking_value.py:12-14``).

    La referencia sobreescribe ``write`` (nunca ``create``: un valor
    rastreado nuevo no puede violar todavía un rastro existente). Aquí el
    punto equivalente es ``save()``, que en Django cubre tanto INSERT como
    UPDATE — se ejecuta la guarda solo cuando ya existe fila (``self.pk``),
    que es el caso que ``write`` cubre en la referencia. Devuelve ``None``
    por la misma razón de relevo que ``delete()``.
    """
    if self.pk is not None:
        self._except_audit_log()


def apply_account_extensions():
    """Cuelga la guarda de auditoría sobre ``mail.tracking.value`` — ≙ ``_inherit``.

    **Todavía no cableado** en ``AccountConfig._EXTENSIONES`` — mismo estado
    que los cuatro ``account_analytic_*``/``account_code_mapping`` que el
    docstring de ``account/models/__init__.py`` ya declara como "todavía no
    cableados". Sucesor: sumar ``'addons.account.models.mail_tracking_value'``
    a esa tupla en el mismo pase que se cablee ``mail_message`` (comparten el
    mismo guardián), y wire ``AccountMove``/consumidores para heredar el
    guard efectivamente cuando ``restrictive_audit_trail`` exista.
    """
    chain_method(MailTrackingValue, '_except_audit_log', _except_audit_log)
    chain_method(MailTrackingValue, 'delete', delete)
    chain_method(MailTrackingValue, 'save', save)
