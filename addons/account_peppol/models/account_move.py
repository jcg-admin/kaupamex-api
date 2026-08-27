"""``account.move`` extendido por ``account_peppol`` — el estado del envío.

Adaptación de Odoo ``account_peppol/models/account_move.py``
(``odoo19c: addons/account_peppol/models/account_move.py``, 102 líneas, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: el asiento visto desde Peppol — su identificador de mensaje en la red,
el estado de su envío y las acciones de cancelación.

Medido por AST en la fuente: 1 clase (``_inherit``), **3 campos** y
**7 métodos**.

Porte símbolo por símbolo — 10 símbolos: 6 portados, 4 bloqueados
===================================================================

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo (línea)
     - Desenlace
   * - ``peppol_message_uuid`` (``:11``)
     - **portado** — ``copy=False`` de la fuente no tiene contraparte: este
       árbol no declara un ``copy()`` genérico de modelo (medido, y ya
       declarado por ``account_debit_note``).
   * - ``peppol_move_state`` (``:12-24``)
     - **portado** — los seis valores verbatim, incluido ``skipped``, que la
       fuente marca con un ``TODO`` de retirada. Se conserva porque es el
       contrato con las filas ya escritas.
   * - ``peppol_is_sent`` (``:25``)
     - **portado** como ``property`` — es un ``compute`` sin ``store``.
   * - ``_compute_peppol_is_sent`` (``:67-70``)
     - **portado** — el cuerpo de esa ``property``. La regla es verbatim:
       enviado = el estado NO está en ``{False, 'ready', 'to_send', 'error'}``.
   * - ``action_cancel_peppol_documents`` (``:32-38``)
     - **portado parcialmente** — la guarda y el borrado del estado sí; la
       línea ``self.sending_data = False`` queda fuera: ``sending_data`` **no
       es un campo de este árbol** (medido: ``grep -n "sending_data"
       addons/account/models/account_move.py`` → 0 hits; sólo aparece como
       concepto en el docstring de ``account_move_send.py``, que lo declara
       parte de la extensión de contacto todavía no portada).
   * - ``action_peppol_cancel_and_remove_sequence`` (``:94-96``)
     - **portado** — cancela y devuelve el nombre a ``'/'``, que es como este
       modelo marca «sin número asignado». ``button_cancel`` sí existe
       (``addons/account/models/account_move.py:380``).
   * - ``action_peppol_reset_documents`` (``:98-102``)
     - **portado parcialmente** — la rama de borradores y la de borrado sí; la
       de «devolver a borrador lo publicado» queda fuera, BLOQUEADA por
       ``AccountMove.button_draft`` (medido: 0 hits de ``def button_draft`` en
       ``addons/account/models/``). Recibe el conjunto de asientos, ya que
       aquí no hay ``self`` de recordset (divergencia 2).
   * - ``_compute_peppol_move_state`` (``:47-65``)
     - BLOQUEADO por ``ResPartner.commercial_partner_id`` **como campo del
       asiento**: la condición central es
       ``move.commercial_partner_id.peppol_verification_state == 'valid'``, y
       medido, ``commercial_partner`` no existe en
       ``addons/account/models/account_move.py`` (sí en
       ``account/models/account_move_send.py`` como concepto, y en
       ``base/models/res_partner.py``). Bloqueador de segundo orden:
       ``is_sale_document`` (0 hits). Sucesor: tarea PENDIENTE DE ASIGNAR.
   * - ``action_send_and_print`` (``:27-30``)
     - BLOQUEADO por ``button_account_peppol_check_partner_endpoint`` (ver
       ``models/res_partner.py``: bloqueado por ``account_edi_ubl_cii``) y por
       ``commercial_partner_id``.
   * - ``_compute_display_send_button`` (``:40-45``)
     - BLOQUEADO por ``AccountMove.display_send_button`` y
       ``_is_exportable_as_self_invoice`` — medido, **0 hits** de ambos en
       este árbol; los declara ``account`` en la referencia.
   * - ``_notify_by_email_prepare_rendering_context`` (``:72-92``)
     - BLOQUEADO por ``PEPPOL_MAILING_COUNTRIES``
       (``odoo19c: account/models/company.py``, 0 hits aquí) y por el propio
       gancho de notificación de ``mail.thread``, que este árbol no porta con
       esa firma.

Divergencias declaradas
=========================

1. **Los ``compute … store=True`` van en ``save()``**, y los ``compute`` sin
   ``store`` van como ``property`` — criterio del árbol.
2. **Los métodos de conjunto reciben el conjunto.** ``action_peppol_reset_
   documents`` opera sobre varios asientos (``self.filtered(...)`` en la
   fuente); aquí es un ``classmethod`` que recibe el queryset, porque este
   ORM no tiene recordsets.
3. **``self.env['account.move'].browse(ids).unlink()`` → ``delete()``** sobre
   el queryset, que es lo mismo.
"""
import fields
from addons.account.models.account_move import AccountMove
from exceptions import UserError
from orm.method_chain import chain_method
from orm.model_classes import add_field_if_absent
from tools.translate import _

#: ≙ el ``selection`` de ``peppol_move_state`` (``odoo19c: :13-20``).
#: ``skipped`` lleva un ``TODO`` de retirada en la fuente; se conserva porque
#: es el contrato con las filas ya escritas.
PEPPOL_MOVE_STATES = [
    ('ready', 'Listo para enviar'),
    ('to_send', 'En cola'),
    ('skipped', 'Omitido'),
    ('processing', 'Recepción pendiente'),
    ('done', 'Hecho'),
    ('error', 'Error'),
]

#: ≙ el conjunto de ``_compute_peppol_is_sent`` (``odoo19c: :70``) — los
#: estados en los que el documento **todavía no** salió a la red.
PEPPOL_NOT_SENT_STATES = {'', 'ready', 'to_send', 'error'}


def _campos():
    """Los dos campos que este addon cuelga sobre ``account.AccountMove``."""
    return {
        'peppol_message_uuid': fields.Char(
            max_length=255, blank=True, default='',
            verbose_name='ID de mensaje PEPPOL',
            help_text='Identificador del mensaje en la red Peppol (Odoo '
                      'peppol_message_uuid, copy=False).',
        ),
        'peppol_move_state': fields.Selection(
            max_length=16, choices=PEPPOL_MOVE_STATES, blank=True, default='',
            verbose_name='Estado PEPPOL',
            help_text='Estado del envío por Peppol (Odoo peppol_move_state, '
                      'compute store=True, copy=False).',
        ),
    }


def peppol_is_sent(self):
    """≙ ``_compute_peppol_is_sent`` (``odoo19c: :67-70``) — ¿ya salió a la
    red? Regla verbatim: enviado = el estado no está entre los cuatro que
    significan «todavía no»."""
    return self.peppol_move_state not in PEPPOL_NOT_SENT_STATES


def action_cancel_peppol_documents(self):
    """≙ ``action_cancel_peppol_documents`` (``odoo19c: :32-38``).

    Un documento que ya salió a la red no se puede cancelar: el proxy lo tiene
    en curso o entregado.

    Sin la línea ``self.sending_data = False`` de la fuente: ese campo no
    existe en este árbol (ver la tabla del módulo).
    """
    if self.peppol_is_sent:
        raise UserError(_(
            'No se puede cancelar un asiento que ya se envió a PEPPOL',
        ))
    self.peppol_move_state = ''
    self.save(update_fields=['peppol_move_state'])


def action_peppol_cancel_and_remove_sequence(self):
    """≙ ``action_peppol_cancel_and_remove_sequence`` (``odoo19c: :94-96``) —
    cancela el asiento y le quita el número, dejándolo en ``'/'``."""
    self.button_cancel()
    self.name = '/'
    self.save(update_fields=['name'])


def action_peppol_reset_documents(cls, moves, ids_to_delete=None):
    """≙ ``action_peppol_reset_documents`` (``odoo19c: :98-102``).

    Quita el número a los que ya estaban en borrador y borra los que se
    indiquen. La rama intermedia de la fuente —devolver a borrador lo
    publicado sin sello de integridad— está BLOQUEADA por
    ``AccountMove.button_draft`` (0 hits medidos); ver la tabla del módulo.

    :param moves: el queryset de asientos (divergencia 2).
    :param ids_to_delete: ids a eliminar, si los hay.
    """
    for move in moves.filter(state='draft'):
        move.action_peppol_cancel_and_remove_sequence()
    if ids_to_delete:
        cls.objects.filter(pk__in=ids_to_delete).delete()


def apply_account_peppol_account_move_extensions():
    """Cuelga sobre ``account.AccountMove`` el estado Peppol del asiento — ≙
    ``_inherit = 'account.move'``. La llama ``AccountPeppolConfig.ready()``."""
    for name, field in _campos().items():
        add_field_if_absent(AccountMove, name, field)

    if not hasattr(AccountMove, 'peppol_is_sent'):
        AccountMove.peppol_is_sent = property(peppol_is_sent)

    for name, function in (
        ('action_cancel_peppol_documents', action_cancel_peppol_documents),
        ('action_peppol_cancel_and_remove_sequence',
         action_peppol_cancel_and_remove_sequence),
        ('action_peppol_reset_documents', classmethod(action_peppol_reset_documents)),
    ):
        chain_method(AccountMove, name, function)


__all__ = [
    'PEPPOL_MOVE_STATES',
    'PEPPOL_NOT_SENT_STATES',
    'apply_account_peppol_account_move_extensions',
]
