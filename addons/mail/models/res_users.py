"""El servidor de correo saliente personal que ``mail`` añade a ``res.users``.

Adaptación de Odoo ``mail/models/res_users.py`` (LGPL-3, copia y adaptación
con atribución), ítem A del inventario
``designs/inventory-mail-res-users.md``:

- los campos ``outgoing_mail_server_id``, ``outgoing_mail_server_type`` y
  ``has_external_mail_server`` (``odoo19c: addons/mail/models/
  res_users.py:50-68``) con ``_compute_outgoing_mail_server_id``
  (``:130-149``) y ``_compute_has_external_mail_server`` (``:64-66``);
- su entrada en ``SELF_READABLE_FIELDS`` (``:165-167``);
- ``_gc_personal_mail_servers``, ``_get_mail_server_values``,
  ``action_setup_outgoing_mail_server``, ``action_test_outgoing_mail_server``
  y ``_get_mail_server_setup_end_action`` (``:545-660``).

Se cuelga con :func:`orm.model_classes.extend_model` desde
``MailConfig.ready()``; ``res.users`` no es ``BaseModel``, así que las
acciones ``@api.model`` son ``classmethod`` que leen ``env().user``.

El resto de la extensión de ``res.users`` de ``mail`` (preferencia de
notificación, ausencia, presencia, roles, avisos de seguridad y el
``Store``) son los ítems B-G del inventario, cada uno con su bloqueo nombrado
allí.

Divergencia declarada: ``groups='base.group_user'`` de los dos campos no se
aplica por campo —``res.users`` no es ``BaseModel`` y su lectura no pasa por
``_check_field_access``—; la frontera es la de la API que los exponga.
"""
from django.db import models

import api
import fields
from addons.base.models import ResUsers
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_mail_server import IrMailServer
from addons.mail.models.mail_alias_domain import MailAliasDomain
from exceptions import UserError
from orm.domains import Domain
from orm.environments import env, sudo
from orm.model_classes import extend_model, extend_property
from tools import config
from tools.mail import email_normalize
from tools.translate import _

#: ≙ el ``config_parameter`` de ``base_setup`` que habilita los personales.
EXTERNAL_SERVER_PARAM = 'base_setup.default_external_email_server'

#: Las opciones de ``outgoing_mail_server_type`` (``:56-63``); otros
#: módulos las amplían con ``selection_add``.
OUTGOING_MAIL_SERVER_TYPES = [('default', 'Default')]


def _compute_has_external_mail_server(self):
    """≙ ``_compute_has_external_mail_server`` (``:64-66``)."""
    with sudo():
        value = SystemParameter.get_param(EXTERNAL_SERVER_PARAM)
    self.has_external_mail_server = bool(value)
    return self.has_external_mail_server


def _compute_outgoing_mail_server_id(self):
    """≙ ``_compute_outgoing_mail_server_id`` (``:130-149``).

    El servidor personal del usuario: filtro con correo completo y, además,
    filtro igual a su correo normalizado, ``smtp_user`` igual a su correo o
    dueño él mismo.
    """
    with sudo():
        mail_servers = env()['ir.mail_server'].search(Domain.AND([
            [('from_filter', 'ilike', '_@_')],
            Domain.OR([[
                ('from_filter', '=', email_normalize(self.email or '')),
                ('smtp_user', '=', self.email),
                ('owner_user_id', '=', self.pk),
            ]]),
        ]))
        # el recordset de la fuente lleva ``su`` (``.sudo().search``); aquí
        # ``sudo`` es un bloque, así que toda lectura de esos registros va
        # dentro de él
        mail_servers = {m.owner_user_id.id: m for m in mail_servers}
        server = mail_servers.get(self.pk) or env()['ir.mail_server']
        self.outgoing_mail_server_id = server if server else None
        type_options = [key for key, _label in OUTGOING_MAIL_SERVER_TYPES]
        self.outgoing_mail_server_type = (
            server.smtp_authentication
            if server.smtp_authentication in type_options
            else 'default'
        )
    return server


def SELF_READABLE_FIELDS(self, previous):
    """≙ ``SELF_READABLE_FIELDS`` (``:155-168``) — la parte del ítem A."""
    return previous + [
        'has_external_mail_server',
        'outgoing_mail_server_id',
        'outgoing_mail_server_type',
    ]


@api.autovacuum
def _gc_personal_mail_servers(cls):
    """≙ ``_gc_personal_mail_servers`` (``:545-551``): si el usuario cambia
    de correo, se borran sus servidores personales viejos."""
    with sudo():
        servers = env()['ir.mail_server'].with_context(
            active_test=False).search([('owner_user_id', '!=', False)])
        servers.filtered(
            lambda s: s.owner_user_id.outgoing_mail_server_id != s
            or not s.active
        ).unlink()


def _get_mail_server_values(cls, server_type):
    """≙ ``_get_mail_server_values`` (``:553-555``)."""
    return {}


def action_setup_outgoing_mail_server(cls, server_type):
    """≙ ``action_setup_outgoing_mail_server`` (``:557-634``)."""
    user = env().user
    if not user.has_external_mail_server:
        raise UserError(_(
            'You are not allowed to create a personal mail server.'))

    if not user._is_internal():
        raise UserError(_(
            'Only internal users can configure a personal mail server.'))

    with sudo():
        existing_mail_server = env()['ir.mail_server'].with_context(
            active_test=False).search([('owner_user_id', '=', user.id)])

    if server_type == 'default':
        # el servidor por defecto
        if existing_mail_server:
            with sudo():
                existing_mail_server.unlink()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": _("Switching back to the default server."),
                "type": "warning",
            },
        }

    email = user.email
    if not email:
        raise UserError(_(
            "Please set your email before connecting your mail server."))

    normalized_email = email_normalize(email)
    if (
        not normalized_email
        or "@" not in normalized_email
        # que ``ir.mail_server`` lo lea igual
        or IrMailServer._parse_from_filter(normalized_email)
        != [normalized_email]
    ):
        raise UserError(_("Wrong email address %s.", email))

    # el correo no puede ser el de un ``mail.alias.domain``: se filtrarían
    # los correos salientes
    with sudo():
        alias_domains = list(MailAliasDomain.objects.all())
    cli_default_from = config.email_from()
    match_from_filter = IrMailServer._match_from_filter
    if (
        any(match_from_filter(domain.default_from_email, normalized_email)
            for domain in alias_domains)
        or (cli_default_from
            and match_from_filter(cli_default_from, normalized_email))
    ):
        raise UserError(_(
            "Your email address is used by an alias domain, and so you can "
            "not create a mail server for it."))

    if (
        server_type == user.outgoing_mail_server_type
        and user.outgoing_mail_server_id.from_filter == normalized_email
        and user.outgoing_mail_server_id.smtp_user == normalized_email
    ):
        # reconectar la cuenta
        return cls._get_mail_server_setup_end_action(
            user.outgoing_mail_server_id)

    if existing_mail_server:
        with sudo():
            existing_mail_server.unlink()

    values = {
        # se desarchiva al iniciar sesión; un servidor personal archivado lo
        # borra el barrido para limpiar conexiones que no terminaron
        "active": False,
        "name": _("%s's outgoing email", user.name),
        "smtp_user": normalized_email,
        "smtp_pass": False,
        "from_filter": normalized_email,
        "smtp_port": 587,
        "smtp_encryption": "starttls",
        "owner_user_id": user.id,
        **cls._get_mail_server_values(server_type),
    }
    with sudo():
        smtp_server = env()['ir.mail_server'].create(values)
    return cls._get_mail_server_setup_end_action(smtp_server)


def action_test_outgoing_mail_server(cls):
    """≙ ``action_test_outgoing_mail_server`` (``:636-655``)."""
    user = env().user
    if not user.has_external_mail_server:
        raise UserError(_(
            'You are not allowed to test personal mail servers.'))

    if not user.has_group('base.group_user'):
        raise UserError(_(
            'Only internal users can configure personal mail servers.'))

    with sudo():
        server_sudo = user.outgoing_mail_server_id
        if not server_sudo:
            raise UserError(_('No mail server configured'))
        server_sudo.test_smtp_connection()
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'message': _('Connection Test Successful!'),
            'type': 'success',
        },
    }


def _get_mail_server_setup_end_action(cls, smtp_server):
    """≙ ``_get_mail_server_setup_end_action`` (``:657-659``): abstracto,
    lo implementan los módulos de cada proveedor."""
    raise NotImplementedError()


def _extend_self_field_lists(model):
    extend_property(model, 'SELF_READABLE_FIELDS', SELF_READABLE_FIELDS)


def apply_mail_user_extensions():
    """≙ ``_inherit = 'res.users'`` de ``mail`` — el ítem A."""
    extend_model(
        'base', 'ResUsers',
        campos={
            'outgoing_mail_server_id': fields.Many2one(
                IrMailServer, store=False,
                compute='_compute_outgoing_mail_server_id',
                on_delete=models.SET_NULL, related_name='+',
                string='Outgoing Mail Server',
            ),
            'outgoing_mail_server_type': fields.Selection(
                OUTGOING_MAIL_SERVER_TYPES, store=False,
                compute='_compute_outgoing_mail_server_id',
                required=True, default='default',
                string='Outgoing Mail Server Type',
            ),
            'has_external_mail_server': fields.Boolean(
                store=False, compute='_compute_has_external_mail_server',
            ),
        },
        metodos={
            '_compute_outgoing_mail_server_id':
                _compute_outgoing_mail_server_id,
            '_compute_has_external_mail_server':
                _compute_has_external_mail_server,
            '_gc_personal_mail_servers': classmethod(
                _gc_personal_mail_servers),
            '_get_mail_server_values': classmethod(_get_mail_server_values),
            'action_setup_outgoing_mail_server': classmethod(
                action_setup_outgoing_mail_server),
            'action_test_outgoing_mail_server': classmethod(
                action_test_outgoing_mail_server),
            '_get_mail_server_setup_end_action': classmethod(
                _get_mail_server_setup_end_action),
        },
        luego=_extend_self_field_lists,
    )
