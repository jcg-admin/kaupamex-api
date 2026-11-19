"""La extensión de ``ir.mail_server`` de ``mail``.

Adaptación de Odoo ``mail/models/ir_mail_server.py`` (LGPL-3, copia y
adaptación con atribución): ≙ ``class IrMail_Server(models.Model)``,
``_inherit = 'ir.mail_server'`` (``odoo19c:
addons/mail/models/ir_mail_server.py:10-106``).

Se cuelga con :func:`orm.model_classes.extend_model` desde
``MailConfig.ready()``, como ``res_company.py``: en tiempo de import el
registro de modelos aún no está poblado.

Lo que se porta, símbolo por símbolo:

- ``_email_field = 'smtp_user'``;
- los campos ``owner_user_id``, ``owner_limit_time`` y ``owner_limit_count``
  (sus columnas viven en ``base/0123``, porque el modelo es de ``base``);
- el objeto de tabla ``_unique_owner_user_id``;
- ``_get_default_bounce_address``, ``_get_default_from_address``,
  ``_get_test_email_from``, ``_filter_mail_servers_fallback``,
  ``_find_mail_server_allowed_domain``, ``_check_forced_mail_server`` (lee
  ``outgoing_mail_server_id`` de ``res_users.py`` de este addon) y
  ``_get_personal_mail_servers_limit``.

Pendiente, con su condición de cierre (diseño
``base-ir-mail-server-complete.md``, paso 5):

- ``mail_template_ids`` y la rama de plantillas de ``_active_usages_compute``:
  ``mail.template`` no tiene aún ``mail_server_id`` (inventario
  ``designs/inventory-mail-template.md``); se portan con la adopción de
  ``mail.template``.

Divergencia declarada: ``env.company`` puede ser ``None`` en este árbol
(fuera de una petición no hay empresa activa), así que las dos lecturas de la
empresa se guardan con ``getattr``; la fuente cuenta siempre con una empresa.
"""
from django.db import models

import fields
from addons.base.models import ResUsers
from addons.base.models.ir_config_parameter import SystemParameter
from addons.mail.models.mail_alias_domain import MailAliasDomain
from exceptions import UserError
from orm import table_objects
from orm.domains import Domain
from orm.environments import env, sudo
from orm.model_classes import add_meta_constraint, extend_model
from tools.mail import email_normalize
from tools.translate import _
from tools.misc import ReadonlyDict

#: El parámetro del límite personal — ≙ ``:106``.
PERSONAL_LIMIT_PARAM = 'mail.server.personal.limit.minutes'


def _get_default_bounce_address(cls, previous):
    """≙ ``_get_default_bounce_address`` (``:43-49``)."""
    company = env().company
    if bounce_email := getattr(company, 'bounce_email', None):
        return bounce_email
    return previous()


def _get_default_from_address(previous):
    """≙ ``_get_default_from_address`` (``:51-57``)."""
    company = env().company
    if default_from := getattr(company, 'default_from_email', None):
        return default_from
    return previous()


def _get_test_email_from(self, previous):
    """≙ ``_get_test_email_from`` (``:59-79``)."""
    self.ensure_one()
    if from_filter_parts := [part.strip() for part in
                             (self.from_filter or '').split(",")
                             if part.strip()]:
        # el primer correo completo de las partes del filtro
        if mail_from := next(
                (email for email in from_filter_parts if "@" in email),
                None):
            return mail_from
        # el servidor está configurado para un dominio que coincide con la
        # dirección por defecto
        with sudo():
            alias_domains = list(MailAliasDomain.objects.all())
        matching = next(
            (alias_domain for alias_domain in alias_domains
             if self._match_from_filter(alias_domain.default_from_email,
                                        self.from_filter)),
            False)
        if matching:
            return matching.default_from_email
        # remitente ficticio "odoo@dominio"
        return f"odoo@{from_filter_parts[0]}"
    # sin from_filter o con un dominio distinto del remitente del dominio de
    # alias de la empresa -> respaldo
    return previous()


def _filter_mail_servers_fallback(cls, previous, servers):
    """≙ ``_filter_mail_servers_fallback`` (``:81-83``).

    La fuente no llama a ``super()``: el respaldo excluye los personales.
    """
    return servers.filtered(lambda s: not s.owner_user_id)


def _find_mail_server_allowed_domain(cls, previous):
    """≙ ``_find_mail_server_allowed_domain`` (``:85-89``): sólo los
    servidores públicos."""
    domain = previous()
    domain &= Domain('owner_user_id', '=', False)
    return domain


def _check_forced_mail_server(self, previous, mail_server, allow_archived,
                              smtp_from):
    """≙ ``_check_forced_mail_server`` (``:91-99``): un servidor personal
    sólo se fuerza con el remitente de su dueño, activo y en uso."""
    previous(mail_server, allow_archived, smtp_from)

    if mail_server.owner_user_id:
        if email_normalize(smtp_from) != mail_server.from_filter:
            raise UserError(_(
                'The server "%s" cannot be forced as it belongs to a user.',
                mail_server.display_name))
        if not mail_server.active:
            raise UserError(_(
                'The server "%s" cannot be forced as it belongs to a user '
                'and is archived.', mail_server.display_name))
        if (mail_server.owner_user_id.outgoing_mail_server_id
                != mail_server):
            raise UserError(_(
                'The server "%s" cannot be forced as the owner does not use '
                'it anymore.', mail_server.display_name))


def _get_personal_mail_servers_limit(self):
    """≙ ``_get_personal_mail_servers_limit`` (``:101-106``).

    Correos por minuto de un servidor personal; 0 cae a 30 para no
    bloquearlo.
    """
    with sudo():
        value = SystemParameter.get_param(PERSONAL_LIMIT_PARAM)
    return int(value or 0) or 30


def _install_table_objects(model):
    """``_email_field`` y ``_unique_owner_user_id`` (``:12`` y ``:29-32``).

    El objeto de tabla se registra igual que lo haría el paso 7 de
    ``_setup``: en ``Meta.constraints`` y en ``_table_objects`` por su nombre
    completo.
    """
    model._email_field = 'smtp_user'
    constraint = table_objects.Constraint(
        "UNIQUE(owner_user_id)",
        "owner_user_id must be unique",
    )
    constraint.__set_name__(model, '_unique_owner_user_id')
    add_meta_constraint(model, constraint.to_django(model))
    current = dict(getattr(model, '_table_objects', None) or {})
    current[constraint.full_name(model)] = constraint
    model._table_objects = ReadonlyDict(current)


def apply_mail_server_extensions():
    """≙ ``_inherit = 'ir.mail_server'`` de ``mail``."""
    extend_model(
        'base', 'IrMailServer',
        campos={
            'owner_user_id': fields.Many2one(
                ResUsers, verbose_name='Owner', db_column='owner_user_id',
                null=True, blank=True, on_delete=models.SET_NULL,
                related_name='+', copy=False,
            ),
            'owner_limit_time': fields.Datetime(
                verbose_name='Owner Limit Time', null=True, blank=True,
                copy=False,
            ),
            'owner_limit_count': fields.Integer(
                verbose_name='Owner Limit Count', default=0, copy=False,
            ),
        },
        metodos={
            '_get_personal_mail_servers_limit':
                _get_personal_mail_servers_limit,
        },
        overrides={
            '_get_default_bounce_address': classmethod(
                _get_default_bounce_address),
            '_get_default_from_address': staticmethod(
                _get_default_from_address),
            '_get_test_email_from': _get_test_email_from,
            '_filter_mail_servers_fallback': classmethod(
                _filter_mail_servers_fallback),
            '_find_mail_server_allowed_domain': classmethod(
                _find_mail_server_allowed_domain),
            '_check_forced_mail_server': _check_forced_mail_server,
        },
        luego=_install_table_objects,
    )
