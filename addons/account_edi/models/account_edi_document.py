r"""``account.edi.document`` — el documento EDI de un asiento (Odoo ``account_edi``).

Adaptación de ``addons/account_edi/models/account_edi_document.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:``,
LGPL-3, 281 líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

Diecinueve símbolos (7 campos + 12 métodos) — el desglose
================================================================

.. list-table::
   :header-rows: 1
   :widths: 32 15 53

   * - Símbolo
     - Estado
     - Nota
   * - ``move_id``
     - portado
     - ``move`` — ``related_name='edi_document_ids'`` (así ``account.move``
       gana el M2O inverso SIN tocar ``account/models/account_move.py``)
   * - ``edi_format_id``
     - portado
     - ``edi_format``
   * - ``attachment_id``
     - portado
     - ``attachment``; el ``groups='base.group_system'`` de la referencia
       (ACL por campo) no tiene contraparte — fuera de este slice
       (``account/models/ir_attachment.py`` ya declara la misma ausencia)
   * - ``state`` / ``error`` / ``blocking_level``
     - portados
     - ``error`` — ``fields.Html``
   * - ``name`` / ``edi_format_name``
     - portados
     - propiedades no-almacenadas (``related=`` sin ``store=True`` en la
       referencia — DEC-SALE-01)
   * - ``edi_content``
     - portado
     - propiedad no-almacenada (compute **sin** ``store=True`` en la
       referencia también — coincide con DEC-SALE-01 sin ninguna divergencia
       extra)
   * - ``_unique_edi_document_by_move_by_format``
     - portado
     - ``Meta.constraints`` (``atributos-de-clase-de-modelo.md``)
   * - ``_compute_edi_content``
     - portado
     - lógica de la propiedad ``edi_content``
   * - ``action_export_xml``
     - **bloqueado**
     - devuelve una acción de UI (``ir.actions.act_url``) para el cliente
       web de Odoo; sin cliente web en este stack
   * - ``_prepare_jobs``
     - portado
     - agrupación de documentos en lotes por ``(formato, estado, empresa,
       [+ batching_key custom])``
   * - ``_process_job``
     - portado (parcial declarado)
     - ``move._send_only_when_ready()`` (context manager de ``mail``) no
       tiene contraparte — se omite el bloqueo de envío concurrente que
       aporta; el resto del método sí se porta
   * - ``_process_documents_no_web_services``
     - portado
     - —
   * - ``_process_documents_web_services``
     - portado
     - ``lock_for_update``/``LockError`` — se construye con
       ``select_for_update(nowait=True)`` + ``OperationalError`` de Django
       (ver ``lock_for_update`` abajo); el ``self.env.cr.commit()`` por lote
       de la referencia se traduce a ``transaction.atomic()`` por job
   * - ``_cron_process_documents_web_services``
     - portado (parcial declarado)
     - la búsqueda y el procesamiento se portan; el
       ``self.env.ref('account_edi.ir_cron_edi_network')._trigger()`` final
       queda **bloqueado** — el cron no existe (sembrarlo exige una
       migración, fuera del alcance de este agente — ver
       ``account_edi_format.py``)
   * - ``_filter_edi_attachments_for_mailing``
     - portado
     - ``self.ensure_one()`` no aplica (una instancia YA es una sola fila en
       este ORM — nunca un recordset); ``self.env.context.get('active_ids')``
       (contexto de sesión web) no tiene contraparte, se omite esa rama

``sudo()`` — divergencia uniforme del módulo
==================================================

Cada ``.sudo()`` de la referencia (``document.sudo().attachment_id``,
``self.sudo().write(...)``) se traduce a acceso/escritura **directos**: este
puerto no tiene ACL a nivel de campo que ``sudo()`` necesite saltarse
(mismo criterio que ``account/models/account_document_import_mixin.py`` y
``account/models/account_move_send.py`` de este mismo dominio).

Sin ``@api.depends`` reactivo
================================

``_compute_edi_content`` corre bajo demanda (acceso a la propiedad), no
reactivamente ante cambios de ``move_id``/``error``/``state`` — mismo criterio
DEC-SALE-01 que el resto de este puerto.
"""
import base64
import logging

from django.db import transaction
from django.db.utils import OperationalError

import fields
import models
from addons.account.models.account_move import AccountMove
from addons.account_edi.models.account_edi_format import AccountEdiFormat
from addons.base.models.ir_attachment import IrAttachment
from exceptions import LockError, UserError
from tools.translate import _

_logger = logging.getLogger(__name__)

DEFAULT_BLOCKING_LEVEL = 'error'


def lock_for_update(queryset):
    """``SELECT ... FOR UPDATE NOWAIT`` — ≙ ``self.lock_for_update()`` (Odoo).

    Construido sobre la primitiva nativa de PostgreSQL vía
    ``QuerySet.select_for_update(nowait=True)`` (``porte-completo-no-parcial.
    md``: "si el stack no trae el mecanismo, se construye"). Django re-emite
    el ``LockNotAvailable`` de psycopg como ``django.db.utils.
    OperationalError`` — se traduce a nuestro ``LockError`` (Odoo
    ``LockError``).

    Debe llamarse **dentro** de un bloque ``transaction.atomic()`` abierto
    por el llamador: el lock vive mientras dure esa transacción, igual que
    en la referencia vive mientras dure el ``cr`` de la petición.
    """
    try:
        list(queryset.select_for_update(nowait=True))
    except OperationalError as error:
        raise LockError(
            'Otra transacción ya bloqueó estas filas; no se puede procesar '
            'ahora.') from error


class AccountEdiDocument(models.Model):
    """``account.edi.document`` — el estado de un formato EDI para un asiento.

    Una fila = "este ``move`` necesita procesarse en este ``edi_format``".
    """

    _name = 'account.edi.document'
    _description = 'Electronic Document for an account.move'

    STATES = [
        ('to_send', 'Por enviar'),
        ('sent', 'Enviado'),
        ('to_cancel', 'Por cancelar'),
        ('cancelled', 'Cancelado'),
    ]
    BLOCKING_LEVELS = [
        ('info', 'Info'),
        ('warning', 'Advertencia'),
        ('error', 'Error'),
    ]

    # == Campos almacenados ==
    move_id = fields.Many2one(
        'account.AccountMove', on_delete=models.CASCADE, db_index=True,
        related_name='edi_document_ids',
        help_text='Asiento contable (Odoo move_id, requerido). related_name '
                  'da a account.move el M2O inverso sin tocar su archivo.',
        db_column='move_id',
    )
    edi_format_id = fields.Many2one(
        AccountEdiFormat, on_delete=models.PROTECT, related_name='documents',
        help_text='Formato EDI (Odoo edi_format_id, requerido).',
        db_column='edi_format_id',
    )
    attachment_id = fields.Many2one(
        'base.IrAttachment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='edi_documents',
        help_text='Archivo generado por edi_format al postear el asiento '
                  '(Odoo attachment_id).',
        db_column='attachment_id',
    )
    state = fields.Selection(
        max_length=9, choices=STATES, blank=True, default='',
        help_text='Odoo state.',
    )
    error = fields.Html(
        blank=True, default='',
        help_text='Texto del último error EDI (Odoo error).',
    )
    blocking_level = fields.Selection(
        max_length=7, choices=BLOCKING_LEVELS, blank=True, default='',
        help_text='Severidad del bloqueo (Odoo blocking_level).',
    )

    class Meta:
        db_table = 'account_edi_document'
        verbose_name = 'Documento EDI'
        verbose_name_plural = 'Documentos EDI'
        constraints = [
            # ≙ ``_unique_edi_document_by_move_by_format``
            # (``odoo19c: account_edi_document.py:38-41``).
            models.UniqueConstraint(
                fields=['edi_format_id', 'move_id'], name='uniq_edi_doc_move_format',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.edi_format_id_id}#{self.move_id_id}={self.state}'

    # == Campos no-almacenados (DEC-SALE-01: propiedades, no fields.*) ==

    @property
    def name(self):
        """≙ ``name`` (``related='attachment_id.name'``)."""
        return self.attachment_id.name if self.attachment_id_id else None

    @property
    def edi_format_name(self):
        """≙ ``edi_format_name`` (``related='edi_format_id.name'``)."""
        return self.edi_format_id.name

    @property
    def edi_content(self):
        """≙ ``edi_content`` — dispara ``_compute_edi_content`` al acceder."""
        return self._compute_edi_content()

    def _compute_edi_content(self):
        """≙ ``_compute_edi_content`` (``odoo19c: :44-56``)."""
        if self.state not in ('to_send', 'to_cancel'):
            return b''
        move = self.move_id
        config_errors = self.edi_format_id._check_move_configuration(move)
        if config_errors:
            return base64.b64encode('\n'.join(config_errors).encode('UTF-8'))
        move_applicability = self.edi_format_id._get_move_applicability(move)
        if move_applicability and move_applicability.get('edi_content'):
            return base64.b64encode(move_applicability['edi_content'](move))
        return b''

    def action_export_xml(self):
        """≙ ``action_export_xml`` (``odoo19c: :58-63``) — **bloqueado**:
        acción de UI del cliente web (``ir.actions.act_url``), sin
        contraparte en este stack (REST + React, no vistas server-side)."""
        raise NotImplementedError(
            'action_export_xml es una acción del cliente web de Odoo; '
            'este stack expone el contenido vía un endpoint REST propio, '
            'fuera del alcance de este porte.')

    @classmethod
    def _prepare_jobs(cls, documents):
        """≙ ``_prepare_jobs`` (``odoo19c: :65-96``).

        ``self`` de la referencia es un recordset — aquí, ``documents`` es
        un iterable explícito (mismo criterio que el resto del puerto).
        Devuelve ``[{'documents': [...], 'method_to_call': callable|None}]``.
        """
        to_process = {}
        for state, edi_flow in (('to_send', 'post'), ('to_cancel', 'cancel')):
            batch = [d for d in documents
                     if d.state == state and d.blocking_level != 'error']
            for edi_doc in batch:
                edi_format = edi_doc.edi_format_id
                move = edi_doc.move_id
                move_applicability = edi_format._get_move_applicability(move) or {}

                batching_key = [edi_format.pk, state, move.company_id]
                custom_batching_key = f'{edi_flow}_batching'
                if move_applicability.get(custom_batching_key):
                    batching_key += list(move_applicability[custom_batching_key](move))
                else:
                    batching_key.append(move.pk)

                job = to_process.setdefault(tuple(batching_key), {
                    'documents': [],
                    'method_to_call': move_applicability.get(edi_flow),
                })
                job['documents'].append(edi_doc)

        return list(to_process.values())

    @classmethod
    def _process_job(cls, job):
        """≙ ``_process_job`` (``odoo19c: :98-152``), parcial declarado.

        ``moves._send_only_when_ready()`` (context manager de
        ``mail.thread``) no tiene contraparte — se omite; el resto se
        porta símbolo a símbolo.
        """
        def _postprocess_post_edi_results(documents, edi_result):
            attachments_to_unlink = []
            for document in documents:
                move = document.move_id
                move_result = edi_result.get(move, {})
                if move_result.get('attachment'):
                    old_attachment = document.attachment_id
                    document.attachment_id = move_result['attachment']
                    document.save(update_fields=['attachment_id'])
                    if old_attachment and not old_attachment.res_model and not old_attachment.res_id:
                        attachments_to_unlink.append(old_attachment)
                if move_result.get('success') is True:
                    document.state = 'sent'
                    document.error = ''
                    document.blocking_level = ''
                else:
                    document.error = move_result.get('error') or ''
                    document.blocking_level = (
                        move_result.get('blocking_level', DEFAULT_BLOCKING_LEVEL)
                        if 'error' in move_result else '')
                document.save(update_fields=['state', 'error', 'blocking_level'])

            # Los adjuntos sin traceability a un modelo de negocio se
            # pueden retirar — ≙ el mismo criterio de la referencia.
            for attachment in attachments_to_unlink:
                attachment.delete()

        def _postprocess_cancel_edi_results(documents, edi_result):
            move_ids_to_cancel = set()
            attachments_to_unlink = []
            for document in documents:
                move = document.move_id
                move_result = edi_result.get(move, {})
                if move_result.get('success') is True:
                    old_attachment = document.attachment_id
                    document.state = 'cancelled'
                    document.error = ''
                    document.attachment_id = None
                    document.blocking_level = ''
                    document.save(update_fields=['state', 'error', 'attachment_id', 'blocking_level'])

                    if move.state == 'posted' and all(
                        d.state == 'cancelled' or not d.edi_format_id._needs_web_services()
                        for d in move.edi_document_ids.all()
                    ):
                        move_ids_to_cancel.add(move.pk)

                    if old_attachment and not old_attachment.res_model and not old_attachment.res_id:
                        attachments_to_unlink.append(old_attachment)
                else:
                    document.error = move_result.get('error') or ''
                    document.blocking_level = (
                        move_result.get('blocking_level', DEFAULT_BLOCKING_LEVEL)
                        if move_result.get('error') else '')
                    document.save(update_fields=['error', 'blocking_level'])

            if move_ids_to_cancel:
                # Divergencia declarada: la referencia hace dos pasos
                # (``invoices.button_draft(); invoices.button_cancel()``)
                # porque su máquina de estados exige pasar por 'draft' antes
                # de 'cancel'. ``AccountMove`` (este árbol) no declara
                # ``button_draft`` (medido: 0 hits en
                # ``addons/account/models/account_move.py``) — sólo el
                # segundo paso tiene contraparte real.
                for move in AccountMove.objects.filter(pk__in=move_ids_to_cancel):
                    move.button_cancel()

            for attachment in attachments_to_unlink:
                attachment.delete()

        documents = job['documents']
        method_to_call = job['method_to_call'] or (
            lambda moves: {move: {'success': True} for move in moves})

        edi_formats = {d.edi_format_id for d in documents}
        companies = {d.move_id.company_id for d in documents}
        states = {d.state for d in documents}
        if len(edi_formats) != 1 or len(companies) != 1 or len(states) != 1:
            raise ValueError(
                'Todos los documentos de un job deben compartir formato, '
                'empresa y estado.')

        state = documents[0].state
        moves = list({d.move_id for d in documents})
        if state == 'to_send':
            edi_result = method_to_call(moves)
            _postprocess_post_edi_results(documents, edi_result)
        elif state == 'to_cancel':
            edi_result = method_to_call(moves)
            _postprocess_cancel_edi_results(documents, edi_result)

    @classmethod
    def _process_documents_no_web_services(cls, documents):
        """≙ ``_process_documents_no_web_services`` (``odoo19c: :154-158``)."""
        batch = [d for d in documents if not d.edi_format_id._needs_web_services()]
        for job in cls._prepare_jobs(batch):
            cls._process_job(job)

    @classmethod
    def _process_documents_web_services(cls, documents, job_count=None, with_commit=True):
        """≙ ``_process_documents_web_services`` (``odoo19c: :160-186``).

        ``self.env.cr.commit()`` por lote → cada job corre dentro de su
        propio ``transaction.atomic()`` (equivalente de commit incremental:
        al salir del bloque sin excepción, Django comitea esa transacción).
        """
        batch = [d for d in documents if d.edi_format_id._needs_web_services()]
        all_jobs = cls._prepare_jobs(batch)
        jobs_to_process = all_jobs[0:job_count] if job_count else all_jobs

        for job in jobs_to_process:
            documents_in_job = job['documents']
            move_ids = {d.move_id for d in documents_in_job}
            attachment_ids = {
                d.attachment_id for d in documents_in_job
                if d.attachment_id_id and not d.attachment_id.res_model and not d.attachment_id.res_id
            }
            try:
                with transaction.atomic():
                    lock_for_update(cls.objects.filter(pk__in=[d.pk for d in documents_in_job]))
                    lock_for_update(AccountMove.objects.filter(pk__in=move_ids))
                    if attachment_ids:
                        lock_for_update(IrAttachment.objects.filter(pk__in=attachment_ids))
                    cls._process_job(job)
            except LockError:
                _logger.debug(
                    'Otra transacción ya bloqueó estos documentos; se '
                    'omite este job.')
                if not with_commit:
                    raise UserError(_(
                        'This document is being sent by another process '
                        'already. ')) from None
                continue

        return len(all_jobs) - len(jobs_to_process)

    @classmethod
    def _cron_process_documents_web_services(cls, job_count=None):
        """≙ ``_cron_process_documents_web_services`` (``odoo19c: :188-198``),
        parcial declarado: el disparo del cron al final queda bloqueado (ver
        el docstring del módulo)."""
        edi_documents = list(cls.objects.filter(
            state__in=('to_send', 'to_cancel'),
            move_id__state='posted',
        ).exclude(blocking_level='error'))
        nb_remaining_jobs = cls._process_documents_web_services(
            edi_documents, job_count=job_count)
        if nb_remaining_jobs > 0:
            _logger.info(
                'account_edi: quedan %s jobs por procesar; el cron '
                '(bloqueado, sin sembrar) los recogería en la próxima '
                'corrida — ver el docstring del módulo.', nb_remaining_jobs)
        return nb_remaining_jobs

    def _filter_edi_attachments_for_mailing(self):
        """≙ ``_filter_edi_attachments_for_mailing`` (``odoo19c: :263-281``).

        ``self.env.context.get('active_ids')`` (multi-selección en la UI
        del cliente web) no tiene contraparte — se omite esa rama; siempre
        se devuelve el ``attachment_id`` directo, que es la rama que SÍ
        aplica fuera del cliente web de Odoo.
        """
        attachment = self.attachment_id
        if not attachment:
            return {}
        if not (attachment.res_model and attachment.res_id):
            return {}
        return {'attachment_ids': [attachment.pk]}


def apply_account_edi_extensions():
    """No aplica — ``AccountEdiDocument`` es un modelo NUEVO (``_name``, no
    ``_inherit``). Se define por uniformidad con ``AccountEdiConfig.
    ready()``."""
    return None
