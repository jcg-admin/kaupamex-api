r"""``account.move`` — lo que ``account_edi`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: account_edi/models/account_move.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 389
líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

Treinta y cinco símbolos (9 campos + 26 métodos) — el desglose
====================================================================

.. list-table::
   :header-rows: 1
   :widths: 32 15 53

   * - Símbolo
     - Estado
     - Nota
   * - ``edi_document_ids``
     - portado
     - **automático** — reverso del ``move`` de ``AccountEdiDocument``
       (``related_name='edi_document_ids'``, ``account_edi_document.py``);
       ningún código en este archivo lo declara
   * - ``edi_state`` / ``edi_error_count`` / ``edi_blocking_level`` /
       ``edi_error_message`` / ``edi_web_services_to_process`` /
       ``edi_show_cancel_button`` / ``edi_show_abandon_cancel_button``
     - portados
     - propiedades no-almacenadas (``compute`` sin ``store=True`` salvo
       ``edi_state`` — DEC-SALE-01, mismo criterio que ``account_payment``)
   * - ``edi_show_force_cancel_button``
     - **bloqueado**
     - delega en ``move._can_force_cancel()``, que no existe en
       ``account/models/account_move.py`` (medido: 0 hits)
   * - ``_prepare_edi_tax_details``
     - portado
     - delega en ``_prepare_invoice_aggregated_taxes``, que **no existe** en
       este árbol (medido: 0 hits) — **bloqueado**, no tiene con qué delegar
   * - ``_is_ready_to_be_sent`` (override)
     - **bloqueado**
     - sin base que sobreescribir (``mail.thread``/envío de correo no
       cableado sobre ``account.move``; medido: 0 hits)
   * - ``_compute_show_reset_to_draft_button`` (override)
     - **bloqueado**
     - ``AccountMove`` no declara ``show_reset_to_draft_button`` (medido: 0
       hits) — sin base que envolver; ``_check_edi_documents_for_reset_to_
       draft`` (la lógica que colgaría de este override) SÍ se porta, ver
       abajo
   * - ``_post`` (override) → ``post`` (envoltura manual, no ``chain_method``)
     - portado
     - crea los ``account.edi.document`` que corresponden a cada
       ``edi_format`` activo del diario y los procesa síncronamente — ver
       ``_wrap_post_with_edi`` para por qué el orden exige NO usar
       ``chain_method`` aquí
   * - ``button_force_cancel``
     - portado (parcial declarado)
     - el ``message_post`` es GAP declarado (``getattr(..., 'message_post',
       None)``, mismo patrón que ``account_document_import_mixin.py``)
   * - ``button_cancel`` (override, chain)
     - portado
     - —
   * - ``_edi_allow_button_draft``
     - portado
     - —
   * - ``button_draft`` (override)
     - **bloqueado**
     - ``AccountMove`` no declara ``button_draft`` (medido: 0 hits) — sin
       base que envolver
   * - ``button_cancel_posted_moves`` / ``button_abandon_cancel_posted_
       posted_moves``
     - portados (parcial declarado)
     - ``_check_fiscal_lock_dates`` no existe (medido: 0 hits) — se omite
       esa llamada, GAP declarado; ``message_post`` GAP igual que arriba
   * - ``_get_edi_document`` / ``_get_edi_attachment``
     - portados
     - —
   * - ``_message_set_main_attachment_id`` (override)
     - **bloqueado**
     - sin base ni ``mail.thread`` (medido: 0 hits)
   * - ``button_process_edi_web_services`` / ``action_process_edi_web_
       services`` / ``_retry_edi_documents_error`` / ``action_retry_edi_
       documents_error``
     - portados
     - —
   * - ``_process_attachments_for_template_post`` (override)
     - **bloqueado**
     - sin base (medido: 0 hits) — plantillas de correo no cableadas sobre
       ``account.move``

``edi_document_ids`` — por qué no hay campo que declarar aquí
====================================================================

La referencia lo declara ``fields.One2many(comodel_name='account.edi.
document', inverse_name='move_id')`` — el lado M2O real vive en
``account.edi.document.move_id``. En Django el M2O ES el que se declara
(``account_edi_document.py``, este mismo addon, campo ``move`` con
``related_name='edi_document_ids'``); el O2M inverso lo crea Django
automáticamente sobre ``account.AccountMove`` **sin tocar**
``account/models/account_move.py`` (fuera del write-set de este agente).
Por eso este archivo no declara ningún campo — sólo cuelga métodos y
propiedades.
"""
import fields
import models
from addons.account.models.account_move import AccountMove
from addons.account_edi.models.account_edi_document import AccountEdiDocument
from exceptions import UserError
from orm.method_chain import chain_method
from tools.translate import _


# --------------------------------------------------------------------------
# Propiedades no-almacenadas — DEC-SALE-01
# --------------------------------------------------------------------------

def _edi_state(self):
    """≙ ``_compute_edi_state`` (``odoo19c: :41-53``)."""
    docs_ws = [d for d in self.edi_document_ids.all()
               if d.edi_format._needs_web_services()]
    all_states = {d.state for d in docs_ws}
    if all_states == {'sent'}:
        return 'sent'
    if all_states == {'cancelled'}:
        return 'cancelled'
    if 'to_send' in all_states:
        return 'to_send'
    if 'to_cancel' in all_states:
        return 'to_cancel'
    return None


def _edi_error_count(self):
    """≙ ``_compute_edi_error_count`` (``odoo19c: :63-66``)."""
    return len([d for d in self.edi_document_ids.all() if d.error])


def _edi_error_message(self):
    """≙ la mitad ``edi_error_message`` de ``_compute_edi_error_message``
    (``odoo19c: :68-83``)."""
    return _edi_error_message_and_level(self)[0]


def _edi_blocking_level(self):
    """≙ la mitad ``edi_blocking_level`` del mismo compute."""
    return _edi_error_message_and_level(self)[1]


def _edi_error_message_and_level(self):
    """El par (mensaje, nivel) — evita recalcular dos veces por acceso
    separado a ``edi_error_message``/``edi_blocking_level``. Devuelve
    ``(None, None)`` sin errores, igual que la referencia deja ambos campos
    en ``False``."""
    count = self.edi_error_count
    if count == 0:
        return None, None
    docs = [d for d in self.edi_document_ids.all() if d.error]
    if count == 1:
        return docs[0].error, docs[0].blocking_level
    levels = {d.blocking_level for d in self.edi_document_ids.all()}
    if 'error' in levels:
        return _('%(count)s Electronic invoicing error(s)') % {'count': count}, 'error'
    if 'warning' in levels:
        return _('%(count)s Electronic invoicing warning(s)') % {'count': count}, 'warning'
    return _('%(count)s Electronic invoicing info(s)') % {'count': count}, 'info'


def _edi_web_services_to_process(self):
    """≙ ``_compute_edi_web_services_to_process`` (``odoo19c: :85-93``)."""
    to_process = [
        d for d in self.edi_document_ids.all()
        if d.state in ('to_send', 'to_cancel') and d.blocking_level != 'error'
    ]
    names = sorted({d.edi_format.name for d in to_process
                    if d.edi_format._needs_web_services()})
    return ', '.join(names)


def _check_edi_documents_for_reset_to_draft(self):
    """≙ ``_check_edi_documents_for_reset_to_draft`` (``odoo19c: :98-105``)."""
    for doc in self.edi_document_ids.all():
        applicability = doc.edi_format._get_move_applicability(self)
        if (doc.edi_format._needs_web_services()
                and doc.state in ('sent', 'to_cancel')
                and applicability and applicability.get('cancel')):
            return False
    return True


def _edi_show_cancel_button(self):
    """≙ ``_compute_edi_show_cancel_button`` (``odoo19c: :123-136``)."""
    if self.state != 'posted':
        return False
    for doc in self.edi_document_ids.all():
        applicability = doc.edi_format._get_move_applicability(self)
        if (doc.edi_format._needs_web_services() and doc.state == 'sent'
                and applicability and applicability.get('cancel')):
            return True
    return False


def _edi_show_abandon_cancel_button(self):
    """≙ ``_compute_edi_show_abandon_cancel_button`` (``odoo19c: :138-147``).
    ``move.sudo().edi_document_ids`` → directo (sin ACL de campo, mismo
    criterio del resto de este dominio)."""
    for doc in self.edi_document_ids.all():
        applicability = doc.edi_format._get_move_applicability(self)
        if (doc.edi_format._needs_web_services() and doc.state == 'to_cancel'
                and applicability and applicability.get('cancel')):
            return True
    return False


def _edi_show_force_cancel_button(self):
    """≙ ``_compute_edi_show_force_cancel_button`` (``odoo19c: :57-60``) —
    **bloqueado**: delega en ``move._can_force_cancel()``, que no existe en
    ``account/models/account_move.py`` (medido: ``grep -rn
    "_can_force_cancel" addons/account/models/*.py`` → 0 hits). Ninguna otra
    pieza de este archivo depende de esta propiedad — el bloqueo es local."""
    raise NotImplementedError(
        'edi_show_force_cancel_button: bloqueado — AccountMove._can_force_'
        'cancel no está portado.')


# --------------------------------------------------------------------------
# Export Electronic Document
# --------------------------------------------------------------------------

def _prepare_edi_tax_details(self, filter_to_apply=None, filter_invl_to_apply=None,
                              grouping_key_generator=None):
    """≙ ``_prepare_edi_tax_details`` (``odoo19c: :151-200``) — **bloqueado**:
    delega en ``_prepare_invoice_aggregated_taxes``, que no existe en este
    árbol (medido: ``grep -rn "_prepare_invoice_aggregated_taxes"
    addons/account/models/*.py`` → 0 hits)."""
    raise NotImplementedError(
        '_prepare_edi_tax_details: bloqueado — _prepare_invoice_aggregated_'
        'taxes no está portado en account/models/account_move.py.')


def _create_edi_documents_after_post(self):
    """≙ la mitad de ``_post`` (``odoo19c: :217-249``) que corre DESPUÉS de
    publicar — ver ``_wrap_post_with_edi`` para por qué no se instala con
    ``chain_method``.

    Crea (o reactiva) el ``account.edi.document`` de cada
    ``edi_format`` activo del diario, y procesa síncronamente los que no
    necesitan web-service — ≙ ``posted.edi_document_ids.
    _process_documents_no_web_services()``. El disparo del cron
    (``ir_cron_edi_network._trigger()``) queda bloqueado (no sembrado, ver
    ``account_edi_format.py``).
    """
    for edi_format in self.journal.edi_format_ids.all():
        applicability = edi_format._get_move_applicability(self)
        if not applicability:
            continue
        errors = edi_format._check_move_configuration(self)
        if errors:
            raise UserError(_('Invalid invoice configuration:\n\n%s') % '\n'.join(errors))

        existing = AccountEdiDocument.objects.filter(
            move=self, edi_format=edi_format).first()
        if existing is not None:
            existing.state = 'to_send'
            existing.attachment = None
            existing.save(update_fields=['state', 'attachment'])
        else:
            AccountEdiDocument.objects.create(
                edi_format=edi_format, move=self, state='to_send')

    new_documents = list(self.edi_document_ids.all())
    AccountEdiDocument._process_documents_no_web_services(new_documents)


#: Marca en la función instalada — evita doble envoltura si ``ready()``
#: corre más de una vez (autoreloader, tests que llaman ``apply_*`` a mano).
_POST_WRAPPED_MARK = '_account_edi_post_wraps_base'


def _wrap_post_with_edi():
    """Instala el equivalente de ``_post`` sobre ``AccountMove.post``, en el
    orden correcto — ``chain_method`` NO sirve aquí.

    ``chain_method`` siempre ejecuta la función NUEVA primero y sólo llama a
    la previa si la nueva devuelve ``None`` (``orm/method_chain.py``, la
    semántica de "relevo"). Para la mayoría de las extensiones eso es
    exactamente lo que hace falta; aquí es al revés: la referencia hace
    ``posted = super()._post(soft=soft)`` **primero** (valida el balance y
    fija ``state='posted'``) y sólo DESPUÉS crea los documentos EDI sobre
    los asientos ya publicados. Encadenar con ``chain_method`` crearía
    documentos EDI sobre un asiento que todavía podría fallar el balance o
    seguir en borrador — un bug de orden, no un detalle cosmético.

    Envoltura manual, idempotente por marca (no reutiliza los marcadores
    privados de ``orm/method_chain.py`` — son internos de ese módulo, y
    replicarlos aquí sería acoplarse a un detalle de implementación ajeno
    para un caso que ya es una excepción declarada al patrón general).
    """
    base_post = AccountMove.post
    if getattr(base_post, _POST_WRAPPED_MARK, False):
        return

    def post_then_create_edi_documents(self):
        result = base_post(self)
        self._create_edi_documents_after_post()
        return result

    setattr(post_then_create_edi_documents, _POST_WRAPPED_MARK, True)
    AccountMove.post = post_then_create_edi_documents


def button_force_cancel(self):
    """≙ ``button_force_cancel`` (``odoo19c: :251-256``). ``message_post``
    es GAP declarado — mismo patrón que ``account_document_import_mixin.py``."""
    to_cancel = [d for d in self.edi_document_ids.all() if d.state == 'to_cancel']
    post = getattr(self, 'message_post', None)
    if post is not None and to_cancel:
        names = ', '.join(d.edi_format.name for d in to_cancel)
        post(body=_(
            'This invoice was canceled while the EDIs %s still had a '
            'pending cancellation request.') % names)
    self.button_cancel()
    return None


def button_cancel(self):
    """≙ ``button_cancel`` (``odoo19c: :258-266``), combinación: primero el
    ``button_cancel`` base (``account/models/account_move.py``, que fija
    ``state='cancel'``), luego el ajuste de los documentos EDI."""
    sent = [d for d in self.edi_document_ids.all() if d.state == 'sent']
    not_sent = [d for d in self.edi_document_ids.all() if d.state != 'sent']
    for doc in not_sent:
        doc.state = 'cancelled'
        doc.error = ''
        doc.blocking_level = ''
        doc.save(update_fields=['state', 'error', 'blocking_level'])
    for doc in sent:
        doc.state = 'to_cancel'
        doc.error = ''
        doc.blocking_level = ''
        doc.save(update_fields=['state', 'error', 'blocking_level'])
    AccountEdiDocument._process_documents_no_web_services(list(self.edi_document_ids.all()))
    return None


def _edi_allow_button_draft(self):
    """≙ ``_edi_allow_button_draft`` (``odoo19c: :268-270``)."""
    return not self.edi_show_cancel_button


def button_cancel_posted_moves(self):
    """≙ ``button_cancel_posted_moves`` (``odoo19c: :279-296``).
    ``_check_fiscal_lock_dates`` no existe (medido: 0 hits) — GAP
    declarado, se omite esa llamada; ``message_post`` GAP igual."""
    to_cancel = []
    is_marked = False
    for doc in self.edi_document_ids.all():
        applicability = doc.edi_format._get_move_applicability(self)
        if (doc.edi_format._needs_web_services() and doc.state == 'sent'
                and applicability and applicability.get('cancel')):
            to_cancel.append(doc)
            is_marked = True
    if is_marked:
        post = getattr(self, 'message_post', None)
        if post is not None:
            post(body=_('A cancellation of the EDI has been requested.'))
    for doc in to_cancel:
        doc.state = 'to_cancel'
        doc.error = ''
        doc.blocking_level = ''
        doc.save(update_fields=['state', 'error', 'blocking_level'])


def button_abandon_cancel_posted_posted_moves(self):
    """≙ ``button_abandon_cancel_posted_posted_moves`` (``odoo19c: :298-311``)."""
    documents = []
    is_marked = False
    for doc in self.edi_document_ids.all():
        applicability = doc.edi_format._get_move_applicability(self)
        if doc.state == 'to_cancel' and applicability and applicability.get('cancel'):
            documents.append(doc)
            is_marked = True
    if is_marked:
        post = getattr(self, 'message_post', None)
        if post is not None:
            post(body=_('A request for cancellation of the EDI has been called off.'))
    for doc in documents:
        doc.state = 'sent'
        doc.error = ''
        doc.blocking_level = ''
        doc.save(update_fields=['state', 'error', 'blocking_level'])


def _get_edi_document(self, edi_format):
    """≙ ``_get_edi_document`` (``odoo19c: :313-314``)."""
    return AccountEdiDocument.objects.filter(move=self, edi_format=edi_format).first()


def _get_edi_attachment(self, edi_format):
    """≙ ``_get_edi_attachment`` (``odoo19c: :316-317``)."""
    doc = self._get_edi_document(edi_format)
    return doc.attachment if doc is not None else None


def button_process_edi_web_services(self):
    """≙ ``button_process_edi_web_services`` (``odoo19c: :330-332``)."""
    self.action_process_edi_web_services(with_commit=False)


def action_process_edi_web_services(self, with_commit=True):
    """≙ ``action_process_edi_web_services`` (``odoo19c: :334-336``)."""
    docs = [d for d in self.edi_document_ids.all()
            if d.state in ('to_send', 'to_cancel') and d.blocking_level != 'error']
    return AccountEdiDocument._process_documents_web_services(docs, with_commit=with_commit)


def _retry_edi_documents_error(self):
    """≙ ``_retry_edi_documents_error`` (``odoo19c: :338-341``)."""
    for doc in self.edi_document_ids.all():
        doc.error = ''
        doc.blocking_level = ''
        doc.save(update_fields=['error', 'blocking_level'])


def action_retry_edi_documents_error(self):
    """≙ ``action_retry_edi_documents_error`` (``odoo19c: :343-345``)."""
    self._retry_edi_documents_error()
    self.action_process_edi_web_services()


def apply_account_edi_extensions():
    """≙ ``_inherit = 'account.move'`` de ``account_edi``.

    Ocho propiedades no-almacenadas (guard ``hasattr`` — son campos, no
    overrides) + los métodos de negocio vía ``chain_method`` (``button_
    cancel`` combina con la base; el resto son nuevos, sin colisión, pero se
    instalan igual por ``chain_method`` por consistencia con el resto del
    árbol — ver ``account_payment/models/account_journal.py`` para el mismo
    criterio). ``post`` es la única excepción: usa ``_wrap_post_with_edi``
    (orden importa, ver su docstring), no ``chain_method``.
    """
    for name, getter in (
        ('edi_state', _edi_state),
        ('edi_error_count', _edi_error_count),
        ('edi_error_message', _edi_error_message),
        ('edi_blocking_level', _edi_blocking_level),
        ('edi_web_services_to_process', _edi_web_services_to_process),
        ('edi_show_cancel_button', _edi_show_cancel_button),
        ('edi_show_abandon_cancel_button', _edi_show_abandon_cancel_button),
        ('edi_show_force_cancel_button', _edi_show_force_cancel_button),
    ):
        if not hasattr(AccountMove, name):
            setattr(AccountMove, name, property(getter))

    chain_method(AccountMove, '_prepare_edi_tax_details', _prepare_edi_tax_details)
    chain_method(AccountMove, '_check_edi_documents_for_reset_to_draft',
                 _check_edi_documents_for_reset_to_draft)
    chain_method(AccountMove, '_create_edi_documents_after_post',
                 _create_edi_documents_after_post)
    _wrap_post_with_edi()
    chain_method(AccountMove, 'button_force_cancel', button_force_cancel)
    chain_method(AccountMove, 'button_cancel', button_cancel)
    chain_method(AccountMove, '_edi_allow_button_draft', _edi_allow_button_draft)
    chain_method(AccountMove, 'button_cancel_posted_moves', button_cancel_posted_moves)
    chain_method(AccountMove, 'button_abandon_cancel_posted_posted_moves',
                 button_abandon_cancel_posted_posted_moves)
    chain_method(AccountMove, '_get_edi_document', _get_edi_document)
    chain_method(AccountMove, '_get_edi_attachment', _get_edi_attachment)
    chain_method(AccountMove, 'button_process_edi_web_services', button_process_edi_web_services)
    chain_method(AccountMove, 'action_process_edi_web_services', action_process_edi_web_services)
    chain_method(AccountMove, '_retry_edi_documents_error', _retry_edi_documents_error)
    chain_method(AccountMove, 'action_retry_edi_documents_error', action_retry_edi_documents_error)
