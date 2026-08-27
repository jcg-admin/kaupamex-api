"""``account.move.send.wizard`` — envío de una factura (diálogo individual).

Adaptación de Odoo ``addons/account/wizard/account_move_send_wizard.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla — mismo patrón que
``AccountDebitNoteWizard``.

Bloqueado por ``account.move.send`` (en porte paralelo)
========================================================

La referencia declara ``_inherit = ['account.move.send',
'mail.composer.mixin']``. La primera mitad la está portando otro agente EN
PARALELO en ``models/account_move_send.py`` (por directiva del orquestador
este archivo NO lo lee ni lo importa); el atributo ``_inherit`` se declara
verbatim y el wiring de la herencia es del orquestador al consolidar. Los
métodos que delegan en el mixin se definen con la llamada verbatim
(``cls._get_default_mail_template_id(...)`` etc.): compilan hoy y resuelven
al componerse — hasta entonces fallan en voz alta (``AttributeError``).

La segunda mitad, ``mail.composer.mixin``, NO está portada (medido:
``ls addons/mail/models/`` no trae composer; ``mail_template.py`` sí). Los
overrides sobre esa mitad se portan donde su cuerpo es autónomo y se
declaran bloqueados donde el cuerpo es sólo el super.

Los campos de la referencia (19) viajan como parámetros de los classmethods
(mismo criterio que el resto de wizards de este directorio); los ``Json``
de checkboxes conservan su forma de dict ``{clave: {'checked': bool,
'label': str}}``.

Treinta y un defs de la referencia — el desglose
=================================================

=====================================  ====================================
Símbolo de la referencia                Qué pasa aquí
=====================================  ====================================
``default_get``                         PORTADO
``_compute_alerts``                     PORTADO (delegación al mixin en
                                         porte paralelo)
``_compute_sending_methods``            PORTADO (pura)
``_inverse_sending_methods``            PORTADO (pura)
``_compute_sending_method_checkboxes``  PORTADO (parcial declarado: el
                                         catálogo de métodos sale de
                                         ``ir.model.fields.
                                         get_field_selection('res.partner',
                                         'invoice_sending_method')`` —
                                         campo de partner no portado; el
                                         catálogo lo pasa el llamador)
``_compute_display_attachments_widget`` PORTADO (delegación)
``_compute_extra_edis``                 PORTADO (pura)
``_inverse_extra_edis``                 PORTADO (pura)
``_compute_extra_edi_checkboxes``       PORTADO (delegación)
``_compute_invoice_edi_format``         PORTADO (delegación)
``_compute_pdf_report_id``              PORTADO (delegación)
``_compute_available_pdf_report_ids``   NO — ``move._get_available_action_
                                         reports`` (catálogo de reportes
                                         ``ir.actions.report`` por modelo)
                                         no portado en ``account.move``.
``_compute_display_pdf_report_id``      NO — deriva del anterior +
                                         ``move.invoice_pdf_report_id``
                                         (no portado).
``_compute_template_id``                PORTADO (delegación)
``_compute_lang``                       PORTADO (parcial declarado:
                                         ``get_lang(self.env)`` → ``None``
                                         cuando no hay plantilla; el
                                         locale de sesión no es superficie
                                         de este árbol)
``_compute_mail_partners``              PORTADO (parcial declarado:
                                         ``commercial_partner_id`` no está
                                         portado — se usa el partner del
                                         asiento)
``_compute_subject``                    PORTADO (delegación)
``_compute_body``                       PORTADO (delegación)
``_compute_mail_attachments_widget``    PORTADO (delegación)
``_compute_res_ids``                    PORTADO (pura)
``_compute_model``                      PORTADO (pura)
``_compute_can_edit_body``              PORTADO (pura)
``_compute_render_model``               PORTADO (pura)
``open_template_creation_wizard``       NO — devuelve un
                                         ``ir.actions.act_window`` sobre
                                         una vista XML de ``mail``
                                         (navegación del cliente Odoo,
                                         misma exclusión que
                                         ``AccountDebitNoteWizard``).
``create_mail_template``                PORTADO (parcial declarado: sin el
                                         ``_reopen`` final — helper de
                                         ``mail.wizard.mail_compose_message``
                                         no portado, y es navegación)
``cancel_save_template``                NO — su único cuerpo es el
                                         ``_reopen`` (navegación).
``_compute_attachments_not_supported``  PORTADO (pura — ``{}`` verbatim)
``_get_selected_checkboxes``            PORTADO (pura)
``_get_sending_settings``               PORTADO (pura)
``_update_preferred_settings``          NO — escribe
                                         ``partner.invoice_template_pdf_
                                         report_id`` (preferencia de
                                         plantilla por partner, campo no
                                         portado).
``_action_download``                    PORTADO (pura — la URL es la del
                                         controller hermano
                                         ``controllers/download_docs.py``)
``action_send_and_print``               PORTADO (delegación; ver su
                                         docstring)
=====================================  ====================================
"""
from addons.mail.models.mail_template import MailTemplate
from exceptions import UserError
from orm.models_transient import TransientModel
from tools.translate import _


class AccountMoveSendWizard(TransientModel):
    """Wizard that handles the sending a single invoice.

    (Docstring verbatim de la referencia.) ≙ ``account.move.send.wizard``.
    """

    _name = 'account.move.send.wizard'
    _inherit = ['account.move.send', 'mail.composer.mixin']
    _description = "Account Move Send Wizard"

    class Meta:
        abstract = True
        managed = False

    # -------------------------------------------------------------------------
    # DEFAULTS
    # -------------------------------------------------------------------------

    @classmethod
    def default_get(cls, move_ids):
        """≙ ``default_get`` — el primer asiento activo es el que se envía."""
        return list(move_ids)[0] if move_ids else None

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------

    @classmethod
    def _compute_alerts(cls, move, sending_methods=None,
                         invoice_edi_format=None, extra_edis=None,
                         mail_partner_ids=None):
        """≙ ``_compute_alerts`` — delegación al mixin en porte paralelo."""
        move_data = {
            move: {
                'sending_methods': sending_methods or {},
                'invoice_edi_format': invoice_edi_format,
                'extra_edis': extra_edis or {},
                'mail_partner_ids': mail_partner_ids,
            }
        }
        return cls._get_alerts(move, move_data)

    @classmethod
    def _compute_sending_methods(cls, sending_method_checkboxes):
        """≙ ``_compute_sending_methods`` — las claves marcadas."""
        return cls._get_selected_checkboxes(sending_method_checkboxes)

    @classmethod
    def _inverse_sending_methods(cls, sending_methods):
        """≙ ``_inverse_sending_methods`` — de lista a checkboxes."""
        return {method_key: {'checked': True}
                for method_key in sending_methods or {}}

    @classmethod
    def _compute_sending_method_checkboxes(cls, move, methods):
        """ Select one applicable sending method given the following priority
        1. preferred method set on partner,
        2. email,

        (Docstring verbatim de la referencia.) ``methods`` es la lista de
        pares ``(clave, etiqueta)`` que allá sale del selection de
        ``res.partner.invoice_sending_method`` (parcial declarado — ver la
        tabla del módulo).
        """
        methods = [method for method in methods if method[0] != 'manual']
        preferred_methods = cls._get_default_sending_methods(move)
        sending_settings = cls._get_default_sending_settings(move)
        return {
            method_key: {
                'checked': (
                    method_key in preferred_methods and (
                        method_key == 'email'
                        or cls._is_applicable_to_move(
                            method_key, move, **sending_settings)
                    )),
                'label': method_label,
            }
            for method_key, method_label in methods
            if cls._is_applicable_to_company(method_key, move.company)
        }

    @classmethod
    def _compute_display_attachments_widget(cls, invoice_edi_format,
                                             sending_methods):
        """≙ ``_compute_display_attachments_widget`` — delegación al mixin
        en porte paralelo."""
        return cls._display_attachments_widget(
            edi_format=invoice_edi_format,
            sending_methods=sending_methods or [],
        )

    @classmethod
    def _compute_extra_edis(cls, extra_edi_checkboxes):
        """≙ ``_compute_extra_edis`` — las claves marcadas."""
        return cls._get_selected_checkboxes(extra_edi_checkboxes)

    @classmethod
    def _inverse_extra_edis(cls, extra_edis):
        """≙ ``_inverse_extra_edis`` — de lista a checkboxes."""
        return {method_key: {'checked': True}
                for method_key in extra_edis or {}}

    @classmethod
    def _compute_extra_edi_checkboxes(cls, move):
        """≙ ``_compute_extra_edi_checkboxes`` — delegación al mixin en
        porte paralelo."""
        all_extra_edis = cls._get_all_extra_edis()
        return {
            edi_key: {'checked': True,
                      'label': all_extra_edis[edi_key]['label'],
                      'help': all_extra_edis[edi_key].get('help')}
            for edi_key in cls._get_default_extra_edis(move)
        }

    @classmethod
    def _compute_invoice_edi_format(cls, move, sending_methods=None):
        """≙ ``_compute_invoice_edi_format`` — delegación al mixin en porte
        paralelo."""
        return cls._get_default_invoice_edi_format(
            move, sending_methods=sending_methods or {})

    @classmethod
    def _compute_pdf_report_id(cls, move):
        """≙ ``_compute_pdf_report_id`` — delegación al mixin en porte
        paralelo."""
        return cls._get_default_pdf_report_id(move)

    @classmethod
    def _compute_template_id(cls, move):
        """≙ ``_compute_template_id`` — delegación al mixin en porte
        paralelo."""
        return cls._get_default_mail_template_id(move)

    @classmethod
    def _compute_lang(cls, move, template):
        """≙ ``_compute_lang`` (override de ``mail.composer.mixin``) —
        parcial declarado: sin plantilla, la referencia cae a
        ``get_lang(self.env).code`` (locale de sesión, no portado) y aquí
        a ``None``."""
        if template:
            return cls._get_default_mail_lang(move, template)
        return None

    @classmethod
    def _compute_mail_partners(cls, move, template=None, lang=None):
        """≙ ``_compute_mail_partners`` — parcial declarado:
        ``commercial_partner_id`` (el padre comercial del contacto) no está
        portado; se parte del partner del asiento."""
        partner = move.partner
        partners = [partner] if partner is not None and getattr(
            partner, 'email', None) else []
        if template:
            partners = cls._get_default_mail_partner_ids(move, template, lang)
        return partners

    @classmethod
    def _compute_subject(cls, move, template, lang=None):
        """≙ ``_compute_subject`` (override de ``mail.composer.mixin``) —
        delegación al mixin en porte paralelo."""
        if template:
            return cls._get_default_mail_subject(move, template, lang)
        return None

    @classmethod
    def _compute_body(cls, move, template, lang=None):
        """≙ ``_compute_body`` (override de ``mail.composer.mixin``) —
        delegación al mixin en porte paralelo."""
        if template:
            return cls._get_default_mail_body(move, template, lang)
        return None

    @classmethod
    def _compute_mail_attachments_widget(cls, move, template,
                                          invoice_edi_format=None,
                                          extra_edis=None, pdf_report=None,
                                          mail_attachments_widget=None):
        """≙ ``_compute_mail_attachments_widget`` — conserva los adjuntos
        manuales y recalcula los derivados (delegación al mixin en porte
        paralelo)."""
        manual_attachments_data = [
            x for x in mail_attachments_widget or [] if x.get('manual')]
        return cls._get_default_mail_attachments_widget(
            move, template,
            invoice_edi_format=invoice_edi_format,
            extra_edis=extra_edis or {},
            pdf_report=pdf_report,
        ) + manual_attachments_data

    @classmethod
    def _compute_res_ids(cls, move):
        """≙ ``_compute_res_ids`` — los ids del documento relacionado."""
        return [move.pk]

    @classmethod
    def _compute_model(cls, model=None, active_model=None):
        """≙ ``_compute_model`` — conserva el ya fijado, o toma el activo."""
        return model or active_model

    @classmethod
    def _compute_can_edit_body(cls, sending_methods):
        """≙ ``_compute_can_edit_body`` — el cuerpo sólo se edita cuando el
        correo es uno de los métodos."""
        return bool(sending_methods) and 'email' in sending_methods

    @classmethod
    def _compute_render_model(cls):
        """≙ ``_compute_render_model`` (override de ``mail.composer.mixin``)
        — el modelo de render es fijo."""
        return 'account.move'

    @classmethod
    def create_mail_template(cls, model, subject, body, template_name=None):
        """ Creates a mail template with the current mail composer's fields.

        (Docstring verbatim de la referencia.) Parcial declarado: sin el
        ``model_id`` de ``ir.model`` (aquí ``MailTemplate.model`` es el
        nombre plano) ni el ``_reopen`` final (navegación del cliente
        Odoo). ``use_default_to``/``user_id`` se conservan donde el modelo
        local los declara.
        """
        if not model:
            raise UserError(_(
                'Template creation from composer requires a valid model.'))
        return MailTemplate.objects.create(
            name=template_name or subject,
            subject=subject or '',
            body_html=body or '',
            model=model,
            use_default_to=True,
        )

    @classmethod
    def _compute_attachments_not_supported(cls):
        """≙ ``_compute_attachments_not_supported`` — verbatim: ``{}`` (el
        hook que las localizaciones EDI llenan)."""
        return {}

    # -------------------------------------------------------------------------
    # CONSTRAINS
    # -------------------------------------------------------------------------

    @classmethod
    def _check_move_id_constraints(cls, move):
        """≙ ``_check_move_id_constraints`` — delegación al mixin en porte
        paralelo."""
        return cls._check_move_constraints(move)

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @classmethod
    def _get_selected_checkboxes(cls, json_checkboxes):
        """≙ ``_get_selected_checkboxes`` — verbatim (incluida su asimetría:
        dict vacío sin entrada, lista de claves con ella)."""
        if not json_checkboxes:
            return {}
        return [checkbox_key
                for checkbox_key, checkbox_vals in json_checkboxes.items()
                if checkbox_vals['checked']]

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------

    @classmethod
    def _get_sending_settings(cls, sending_methods=None,
                               invoice_edi_format=None, extra_edis=None,
                               pdf_report=None, author_user_id=None,
                               author_partner_id=None, mail_template=None,
                               mail_lang=None, mail_body=None,
                               mail_subject=None, mail_partner_ids=None,
                               mail_attachments_widget=None,
                               display_attachments_widget=False):
        """≙ ``_get_sending_settings`` — el dict de ajustes que consume
        ``_generate_and_send_invoices``. El autor viaja por parámetro
        (``self.env.user`` es sesión, no estado del wizard)."""
        send_settings = {
            'sending_methods': sending_methods or [],
            'invoice_edi_format': invoice_edi_format,
            'extra_edis': extra_edis or [],
            'pdf_report': pdf_report,
            'author_user_id': author_user_id,
            'author_partner_id': author_partner_id,
        }
        if sending_methods and 'email' in sending_methods:
            send_settings.update({
                'mail_template': mail_template,
                'mail_lang': mail_lang,
                'mail_body': mail_body,
                'mail_subject': mail_subject,
                'mail_partner_ids': [p.pk for p in mail_partner_ids or []],
            })
        if display_attachments_widget:
            send_settings['mail_attachments_widget'] = mail_attachments_widget
        return send_settings

    # -------------------------------------------------------------------------
    # BUSINESS ACTIONS
    # -------------------------------------------------------------------------

    @classmethod
    def _action_download(cls, attachments):
        """ Download the PDF attachment, or a zip of attachments if there are more than one.

        (Docstring verbatim de la referencia.) La URL es la del controller
        hermano (``controllers/download_docs.py``, portado en este mismo
        pase)."""
        ids = ','.join(str(attachment.pk) for attachment in attachments)
        return {
            'type': 'ir.actions.act_url',
            'url': f'/account/download_invoice_attachments/{ids}',
            'close': True,
        }

    @classmethod
    def action_send_and_print(cls, move, send_settings,
                               allow_fallback_pdf=False):
        """ Create invoice documents and send them.

        (Docstring verbatim de la referencia.) Delegación al mixin en porte
        paralelo (``_generate_and_send_invoices``); sin el
        ``_update_preferred_settings`` previo (bloqueado — ver la tabla del
        módulo) y devolviendo los adjuntos o el dict de descarga en vez de
        ``ir.actions.act_window_close``."""
        alerts = cls._compute_alerts(
            move,
            sending_methods=send_settings.get('sending_methods'),
            invoice_edi_format=send_settings.get('invoice_edi_format'),
            extra_edis=send_settings.get('extra_edis'),
        )
        if alerts:
            cls._raise_danger_alerts(alerts)
        attachments = cls._generate_and_send_invoices(
            move,
            **send_settings,
            allow_fallback_pdf=allow_fallback_pdf,
        )
        sending_methods = send_settings.get('sending_methods') or []
        if attachments and 'manual' in sending_methods:
            return cls._action_download(attachments)
        return attachments
