r"""``account.move.send`` — la clase compartida por los asistentes de envío de facturas.

Adaptación de ``addons/account/models/account_move_send.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, 863 líneas, LGPL-3 — atribución y
aviso de licencia preservados, DEC-KX-03). La referencia la describe en su
propio docstring: *"Shared class between the two sending wizards"* —
``account.move.send.batch.wizard`` (async) y ``account.move.send.wizard``
(síncrono), ninguno de los dos portado en este árbol (no están en la lista
de archivos de este pase).

Clase Python, no ``AbstractModel`` — mismo criterio que los otros mixins
============================================================================

``_name = 'account.move.send'`` sin campos propios (medido: 0 ``fields.``
en la fuente) — comportamiento puro. Mismo criterio que
``account_document_import_mixin.py``/``product_catalog_mixin.py`` de este
pase: se preservan ``_name``/``_description`` como atributos de clase
Python.

Cincuenta símbolos — catorce con lógica real, treinta y seis bloqueados
===========================================================================

**Bloqueados como GRUPO, por piezas concretas ausentes, medidas antes de
escribir este archivo:**

1. **El registro de formatos EDI de facturación** (``_get_all_extra_edis``
   deliberadamente vacío en la referencia misma — terminal, no bloqueo
   nuestro; pero todo lo que orquesta un EDI concreto SÍ está bloqueado:
   ningún addon ``l10n_*_edi``/``account_edi_*`` está portado, medido en
   ``account_document_import_mixin.py`` de este mismo pase).
2. **Los campos de socio que estos métodos leen** — ``commercial_partner_id``
   ``invoice_sending_method``, ``invoice_edi_format``, ``sending_data`` —
   pertenecen a la extensión de ``res.partner`` que ``account/models/
   partner.py`` (este mismo pase) aporta; algunos de ellos SÍ se portan ahí
   (ver su docstring para el mapa completo campo-a-campo).
3. **El widget de adjuntos del formulario de envío**
   (``mail_attachments_widget`` — un JSON para un componente OWL de
   selección de adjuntos) — mismo GAP de cliente web que
   ``account_journal_dashboard.py``.
4. **Cron/web-service hooks EDI** (``_call_web_service_before/after_invoice
   _pdf_render``) — terminal en la referencia (no hacen nada por defecto),
   se portan tal cual.

Los catorce con lógica real usan sólo infraestructura confirmada presente:
``src/addons/base/models/ir_actions_report.py::IrActionsReport`` (motor de
reportes, SÍ portado — corrige una suposición inicial: no todo lo que
suena a "reporte PDF" está bloqueado) y
``addons/mail/models/email_executor.py::send_thread_email`` (envío real de
correo, condicionado a que el consumidor tenga ``message_post`` — GAP
declarado igual que en ``account_document_import_mixin.py``).
"""
import logging
import sys

from addons.base.models.ir_actions_report import IrActionsReport
from addons.base.models.ir_attachment import IrAttachment
from addons.mail.models.email_executor import send_thread_email
from exceptions import UserError
from tools.translate import _

_logger = logging.getLogger(__name__)


class SendActionBlocked(NotImplementedError):
    """Paso del flujo de envío bloqueado — ver el docstring del módulo."""


def _blocked(method_name, missing):
    raise SendActionBlocked(
        f'{method_name}: bloqueado — {missing} (ver el docstring de '
        f'account_move_send.py).')


class AccountMoveSend:
    """≙ ``account.move.send`` (``odoo19c: account_move_send.py:13-19``).

    Clase Python de comportamiento — ver "Clase Python, no ``AbstractModel``"
    en el docstring del módulo.
    """

    _name = 'account.move.send'
    _description = 'Account Move Send'

    # -------------------------------------------------------------------------
    # DEFAULTS — cuatro con lógica real, dos bloqueados
    # -------------------------------------------------------------------------

    @classmethod
    def _get_default_sending_methods(cls, move):
        """≙ ``_get_default_sending_methods`` (``odoo19c: :26-28``).

        Portado en su forma: lee ``invoice_sending_method`` del socio
        comercial. Sin ``commercial_partner_id``/``with_company`` en este
        árbol, se usa el socio directo del asiento.
        """
        partner = getattr(move, 'partner', None)
        method = getattr(partner, 'invoice_sending_method', None) if partner else None
        return {method or 'email'}

    @classmethod
    def _get_all_extra_edis(cls):
        """≙ ``_get_all_extra_edis`` (``odoo19c: :30-34``, terminal —
        sobreescribir; la referencia también la devuelve vacía por
        defecto)."""
        return {}

    @classmethod
    def _get_default_extra_edis(cls, move):
        """≙ ``_get_default_extra_edis`` (``odoo19c: :36-39``). Portado —
        no depende de ninguna pieza bloqueada."""
        extra_edis = cls._get_all_extra_edis()
        return {key for key, vals in extra_edis.items() if vals['is_applicable'](move)}

    @classmethod
    def _get_default_invoice_edi_format(cls, move, **kwargs):
        """≙ ``_get_default_invoice_edi_format`` (``odoo19c: :41-43``)."""
        partner = getattr(move, 'partner', None)
        return getattr(partner, 'invoice_edi_format', None) if partner else None

    @classmethod
    def _get_default_pdf_report_id(cls, move):
        """≙ ``_get_default_pdf_report_id`` (``odoo19c: :45-58``).

        Sin xmlid (``self.env.ref('account.account_invoices')``, ver el GAP
        ya documentado en varios archivos de este pase), se localiza el
        reporte por ``report_name`` en vez de por xmlid —
        ``IrActionsReport.get_report_from_name`` sí existe y es la vía
        equivalente.
        """
        partner = getattr(move, 'partner', None)
        partner_default = getattr(partner, 'invoice_template_pdf_report_id', None) if partner else None
        if partner_default:
            return partner_default
        journal = getattr(move, 'journal', None)
        journal_default = getattr(journal, 'invoice_template_pdf_report_id', None) if journal else None
        if journal_default:
            return journal_default
        report = IrActionsReport.get_report_from_name('account.report_invoice')
        if report is not None:
            return report
        raise UserError(_('No hay ninguna plantilla que aplique a este tipo de asiento.'))

    @classmethod
    def _get_default_mail_template_id(cls, move):
        """≙ ``_get_default_mail_template_id`` (``odoo19c: :64-65``) —
        **bloqueado**: delega en ``move._get_mail_template()``, que
        ``AccountMove`` de este árbol no declara."""
        _blocked('_get_default_mail_template_id',
                 "AccountMove._get_mail_template() no está portado")

    @classmethod
    def _get_default_sending_settings(cls, move, from_cron=False, **custom_settings):
        """≙ ``_get_default_sending_settings`` (``odoo19c: :68-109``) —
        **bloqueado como orquestador**: compone los seis métodos
        ``_get_default_mail_*``/``_get_default_mail_attachments_widget``,
        todos bloqueados (ver el docstring del módulo, puntos 2-3)."""
        _blocked('_get_default_sending_settings',
                 "orquesta _get_default_mail_* y el widget de adjuntos, "
                 "ambos bloqueados")

    # -------------------------------------------------------------------------
    # ALERTAS
    # -------------------------------------------------------------------------

    @classmethod
    def _get_alerts(cls, moves, moves_data):
        """≙ ``_get_alerts`` (``odoo19c: :111-161``) — **bloqueado**: cruza
        ``sending_methods``/``extra_edis`` por asiento, ninguno de los dos
        con datos reales sin el registro EDI (punto 1 del docstring del
        módulo)."""
        _blocked('_get_alerts', 'registro EDI ausente')

    @classmethod
    def _raise_danger_alerts(cls, alerts):
        """≙ ``_raise_danger_alerts`` (``odoo19c: :325-330``). Portable: no
        depende de nada bloqueado, sólo filtra y levanta."""
        danger = [a for a in alerts.values() if a.get('level') == 'danger']
        if danger:
            raise UserError('\n'.join(a.get('message', '') for a in danger))

    # -------------------------------------------------------------------------
    # PLANTILLA DE CORREO — GANCHOS (bloqueados, requieren mail_template)
    # -------------------------------------------------------------------------

    @classmethod
    def _get_mail_default_field_value_from_template(cls, mail_template, lang, move, field, **kwargs):
        """≙ ``odoo19c: :162-169`` — **bloqueado**: sin motor de
        renderizado de plantillas (``mail_template.py`` de este pase no
        porta un motor de expresión Jinja/QWeb, sólo el modelo)."""
        _blocked('_get_mail_default_field_value_from_template',
                 'motor de renderizado de mail.template ausente')

    @classmethod
    def _get_default_mail_lang(cls, move, mail_template):
        """≙ ``odoo19c: :170-173``."""
        partner = getattr(move, 'partner', None)
        return getattr(partner, 'lang', None) or 'es'

    @classmethod
    def _get_default_mail_body(cls, move, mail_template, mail_lang):
        _blocked('_get_default_mail_body', 'motor de renderizado de mail.template ausente')

    @classmethod
    def _get_default_mail_subject(cls, move, mail_template, mail_lang):
        _blocked('_get_default_mail_subject', 'motor de renderizado de mail.template ausente')

    @classmethod
    def _get_default_mail_partner_ids(cls, move, mail_template, mail_lang):
        """≙ ``odoo19c: :193-227``. Portable en su forma mínima: el socio
        del asiento, sin la resolución de destinatarios de la plantilla."""
        partner = getattr(move, 'partner', None)
        return [partner] if partner is not None else []

    @classmethod
    def _get_default_mail_attachments_widget(cls, move, mail_template, invoice_edi_format=None, extra_edis=None, pdf_report=None):
        _blocked('_get_default_mail_attachments_widget', 'widget OWL de adjuntos ausente')

    @classmethod
    def _get_placeholder_mail_attachments_data(cls, move, invoice_edi_format=None, extra_edis=None, pdf_report=None):
        _blocked('_get_placeholder_mail_attachments_data', 'widget OWL de adjuntos ausente')

    @classmethod
    def _get_placeholder_mail_template_dynamic_attachments_data(cls, move, mail_template, pdf_report=None):
        _blocked('_get_placeholder_mail_template_dynamic_attachments_data', 'widget OWL de adjuntos ausente')

    @classmethod
    def _get_invoice_extra_attachments(cls, move):
        """≙ ``odoo19c: :289-292``. Portable: los adjuntos ya vinculados al
        asiento, vía ``ir.attachment`` genérico."""
        model_label = type(move).__module__ + '.' + type(move).__name__
        return list(IrAttachment.objects.filter(res_model=model_label, res_id=move.pk))

    @classmethod
    def _get_invoice_extra_attachments_data(cls, move):
        _blocked('_get_invoice_extra_attachments_data', 'widget OWL de adjuntos ausente')

    @classmethod
    def _get_mail_template_attachments_data(cls, mail_template):
        _blocked('_get_mail_template_attachments_data', 'widget OWL de adjuntos ausente')

    @classmethod
    def _display_attachments_widget(cls, edi_format, sending_methods):
        """≙ ``odoo19c: :378-384``. Portable — sólo evalúa si el método
        'email' está entre los seleccionados."""
        return bool(sending_methods) and 'email' in sending_methods

    # -------------------------------------------------------------------------
    # VALIDACIÓN
    # -------------------------------------------------------------------------

    @classmethod
    def _check_move_constraints(cls, moves):
        """≙ ``_check_move_constraints`` (``odoo19c: :331-336``). Portable:
        recolecta ``_get_move_constraints`` por asiento y levanta si hay
        alguna."""
        errors = []
        for move in moves:
            errors.extend(cls._get_move_constraints(move))
        if errors:
            raise UserError('\n'.join(errors))

    @classmethod
    def _get_move_constraints(cls, move):
        """≙ ``_get_move_constraints`` (``odoo19c: :337-345``, terminal —
        sobreescribir). Un asiento publicado es la única restricción
        portable sin EDI/reportes concretos."""
        errors = []
        if getattr(move, 'state', None) != 'posted':
            errors.append(_('El asiento %s no está publicado.') % getattr(move, 'name', move.pk))
        return errors

    @classmethod
    def _check_invoice_report(cls, moves, **custom_settings):
        _blocked('_check_invoice_report', 'IrActionsReport.render() requiere plantilla QWeb portada')

    # -------------------------------------------------------------------------
    # FORMATEO DE ERRORES
    # -------------------------------------------------------------------------

    @classmethod
    def _format_error_text(cls, error):
        """≙ ``_format_error_text`` (``odoo19c: :356-364``). Portable."""
        return '%s\n%s' % (error.get('error_title', ''),
                            '\n'.join(error.get('errors', [])))

    @classmethod
    def _format_error_html(cls, error):
        """≙ ``_format_error_html`` (``odoo19c: :366-376``). Portable —
        sin ``Markup``/HTML de plantilla QWeb, texto plano con saltos."""
        return cls._format_error_text(error)

    # -------------------------------------------------------------------------
    # APLICABILIDAD
    # -------------------------------------------------------------------------

    @classmethod
    def _is_applicable_to_company(cls, method, company):
        """≙ ``_is_applicable_to_company`` (``odoo19c: :386-389``, terminal
        — sobreescribir)."""
        return True

    @classmethod
    def _is_applicable_to_move(cls, method, move, **move_data):
        """≙ ``_is_applicable_to_move`` (``odoo19c: :391-396``, terminal —
        sobreescribir)."""
        return True

    # -------------------------------------------------------------------------
    # GANCHOS DE RENDERIZADO PDF
    # -------------------------------------------------------------------------

    @classmethod
    def _hook_invoice_document_before_pdf_report_render(cls, invoice, invoice_data):
        """≙ ``odoo19c: :398-406``, terminal — sobreescribir (no-op en la
        referencia)."""
        return None

    @classmethod
    def _prepare_invoice_pdf_report(cls, invoices_data):
        _blocked('_prepare_invoice_pdf_report', 'IrActionsReport.render() requiere plantilla QWeb de factura')

    @classmethod
    def _prepare_invoice_proforma_pdf_report(cls, invoice, invoice_data):
        _blocked('_prepare_invoice_proforma_pdf_report', 'IrActionsReport.render() requiere plantilla QWeb de proforma')

    @classmethod
    def _hook_invoice_document_after_pdf_report_render(cls, invoice, invoice_data):
        """≙ ``odoo19c: :455-463``, terminal — sobreescribir (no-op)."""
        return None

    @classmethod
    def _link_invoice_documents(cls, invoices_data):
        _blocked('_link_invoice_documents', 'requiere el resultado de _prepare_invoice_pdf_report')

    # -------------------------------------------------------------------------
    # ÉXITO / ERROR
    # -------------------------------------------------------------------------

    @classmethod
    def _hook_if_errors(cls, moves_data, allow_raising=True):
        """≙ ``odoo19c: :485-496``. Portable: recolecta y opcionalmente
        levanta los errores acumulados por asiento."""
        errors = {move: data['error'] for move, data in moves_data.items() if data.get('error')}
        if errors and allow_raising:
            raise UserError('\n'.join(
                cls._format_error_text(err) if isinstance(err, dict) else str(err)
                for err in errors.values()))
        return errors

    @classmethod
    def _hook_if_success(cls, moves_data, from_cron=False):
        """≙ ``odoo19c: :497-527``. Portable en su núcleo: marca cada
        asiento como enviado, sin la notificación de socio (bloqueada
        abajo)."""
        for move in moves_data:
            if hasattr(move, 'is_move_sent'):
                move.is_move_sent = True
                move.save()

    @classmethod
    def _send_notifications_to_partners(cls, moves_grouped_by_author_partner_id, is_success=True):
        _blocked('_send_notifications_to_partners', 'canal de notificación (bus) al autor no cableado para este flujo')

    # -------------------------------------------------------------------------
    # ENVÍO DE CORREO
    # -------------------------------------------------------------------------

    @classmethod
    def _send_mail(cls, move, mail_template, **kwargs):
        """≙ ``_send_mail`` (``odoo19c: :555-582``).

        Portable, condicionado: usa ``email_executor.send_thread_email`` si
        el asiento tiene ``message_post`` (mixin ``mail.thread`` cableado) —
        hoy ``AccountMove`` no lo tiene (medido, ver docstring del módulo),
        así que en la práctica es un no-op documentado hasta que se cablee.
        """
        post = getattr(move, 'message_post', None)
        partner = getattr(move, 'partner', None)
        if post is None or partner is None:
            _logger.info(
                'account.move.send._send_mail: sin message_post/partner '
                'en %s, no se envía (GAP declarado).', move)
            return None
        return send_thread_email(
            move, partner,
            subject=kwargs.get('mail_subject', ''),
            body=kwargs.get('mail_body', ''),
        )

    @classmethod
    def _get_mail_layout(cls):
        """≙ ``odoo19c: :583-586``, terminal — sobreescribir."""
        return None

    @classmethod
    def _get_mail_params(cls, move, move_data):
        _blocked('_get_mail_params', 'orquesta _get_default_mail_* y el widget de adjuntos, ambos bloqueados')

    @classmethod
    def _generate_dynamic_reports(cls, moves_data):
        _blocked('_generate_dynamic_reports', 'IrActionsReport.render() requiere plantilla QWeb')

    @classmethod
    def _send_mails(cls, moves_data):
        """≙ ``_send_mails`` (``odoo19c: :657-696``). Portable en su forma:
        itera y delega en ``_send_mail`` (arriba, con su propio GAP
        declarado)."""
        for move, data in moves_data.items():
            cls._send_mail(move, data.get('mail_template'), **data)

    @classmethod
    def _can_commit(cls):
        """≙ ``_can_commit`` (``odoo19c: :697-703``). Mismo criterio que
        ``account_document_import_mixin.py::_can_commit`` — detección de
        pytest en vez de la bandera de test de Odoo."""
        return 'pytest' not in sys.modules

    # -------------------------------------------------------------------------
    # GANCHOS DE SERVICIO WEB (EDI) — terminal, no-op en la referencia
    # -------------------------------------------------------------------------

    @classmethod
    def _call_web_service_before_invoice_pdf_render(cls, invoices_data):
        """≙ ``odoo19c: :704-709``, terminal — sobreescribir (no-op)."""
        return None

    @classmethod
    def _call_web_service_after_invoice_pdf_render(cls, invoices_data):
        """≙ ``odoo19c: :710-715``, terminal — sobreescribir (no-op)."""
        return None

    # -------------------------------------------------------------------------
    # ORQUESTADORES DE ALTO NIVEL — bloqueados (dependen de lo bloqueado arriba)
    # -------------------------------------------------------------------------

    @classmethod
    def _generate_invoice_documents(cls, invoices_data, allow_fallback_pdf=False):
        _blocked('_generate_invoice_documents', 'orquesta _prepare_invoice_pdf_report + EDI, ambos bloqueados')

    @classmethod
    def _generate_invoice_fallback_documents(cls, invoices_data):
        _blocked('_generate_invoice_fallback_documents', 'IrActionsReport.render() requiere plantilla QWeb')

    @classmethod
    def _check_sending_data(cls, moves, **custom_settings):
        """≙ ``_check_sending_data`` (``odoo19c: :804-815``). Portable: la
        única parte no bloqueada de la validación previa al envío."""
        cls._check_move_constraints(moves)

    @classmethod
    def _generate_and_send_invoices(cls, moves, from_cron=False, allow_raising=True, allow_fallback_pdf=False, **custom_settings):
        _blocked('_generate_and_send_invoices',
                 'orquesta _generate_invoice_documents (bloqueado) + _send_mails')


def apply_account_extensions():
    """No aplica — ``AccountMoveSend`` es un modelo NUEVO (``_name``), no
    cuelga sobre otro addon. Se define por uniformidad con el resto del
    pase.

    Sin consumidor todavía: ni ``account.move.send.wizard`` ni
    ``account.move.send.batch.wizard`` están portados en este árbol —
    fuera del alcance de este pase (no están en la lista de archivos a
    escribir).
    """
    return None
