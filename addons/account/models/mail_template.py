r"""``mail.template`` colgado por ``account`` — protege las plantillas de envío EDI.

Adaptación de ``addons/account/models/mail_template.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03). Un símbolo, portado con divergencia
declarada:

======================================  ==========================================
Símbolo                                 Estado
======================================  ==========================================
``_unlink_except_master_mail_template``  portado — xmlid → nombre (ver abajo)
======================================  ==========================================

``get_external_id()`` → nombre de plantilla (divergencia de mecanismo)
==========================================================================

La referencia resuelve el identificador externo de cada plantilla que se
intenta borrar (``self.get_external_id().values()``) y lo cruza contra dos
xmlids maestros (``account.email_template_edi_invoice``,
``account.email_template_edi_credit_note``). Este monolito **no** tiene
``ir.model.data``/resolución por xmlid (medido:
``grep -rn "get_external_id\|ir.model.data" src/ addons/`` → 0 hits fuera de
docs) — mismo hueco que ``onboarding_onboarding_step.py`` ya documenta para
``env.ref``.

El sustituto es el **nombre** de la plantilla, con el mismo criterio que
``OnboardingOnboarding.route_name`` sustituye al xmlid como identificador
estable (ver su docstring: "identificador estable... sin panel web, no
define una ruta HTTP aquí"). Las dos plantillas maestras no tienen fila
sembrada todavía en este árbol (no hay cargador de datos declarativos —
mismo gap), así que la guarda queda **estructuralmente completa** y sin
efecto observable hasta que exista un seed real con esos nombres. Sucesor:
sembrar las dos plantillas EDI de facturación cuando exista el flujo de
envío (``account_move_send.py`` de este mismo pase, también con su propio
GAP de infraestructura declarado).
"""
from addons.mail.models.mail_template import MailTemplate
from exceptions import UserError
from orm.method_chain import chain_method
from tools.translate import _

#: Sustituto de los dos xmlids maestros de la referencia
#: (``odoo19c: account/models/mail_template.py:8-9``) — ver el docstring del
#: módulo para por qué el identificador es el nombre y no un xmlid.
MASTER_TEMPLATE_NAMES = (
    'account.email_template_edi_invoice',
    'account.email_template_edi_credit_note',
)


def delete(self, *args, **kwargs):
    """≙ ``_unlink_except_master_mail_template`` (``odoo19c:
    mail_template.py:9-14``, ``@api.ondelete(at_uninstall=False)``).

    Mismo punto de traducción que ``account_account_tag.py::delete()``:
    ``@api.ondelete`` → ``delete()`` del modelo Django.
    """
    if self.name in MASTER_TEMPLATE_NAMES:
        raise UserError(_(
            'No se puede eliminar esta plantilla de correo, se usa en el '
            'flujo de envío de facturas.'))


def apply_account_extensions():
    """Cuelga la guarda de borrado sobre ``mail.template`` — ≙ ``_inherit``.

    **Todavía no cableado** en ``AccountConfig._EXTENSIONES`` — mismo estado
    declarado que ``mail_message.py``/``mail_tracking_value.py`` de este
    mismo pase.
    """
    chain_method(MailTemplate, 'delete', delete)
