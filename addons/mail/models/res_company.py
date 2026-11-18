"""Lo que ``mail`` cuelga a la empresa — ≙ ``_inherit = 'res.company'``.

Adaptación de ``odoo19c: addons/mail/models/res_company.py`` (LGPL-3 según
su ``__manifest__.py``: copia y adaptación con atribución). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
mail-company-extension.md``.

*Métrica:* campos y métodos del cuerpo de ``class ResCompany``, contados por
AST: 8 campos y 4 métodos. Se portan todos. ``_inherit`` se expresa
colgándolos de ``addons.base.models.ResCompany`` con
:func:`~orm.model_classes.extend_model`, como ``purchase/models/
res_company.py``:

- las dos columnas (``alias_domain_id`` y los dos colores) en ``campos``;
- los calculados sin ``store`` en ``propiedades``, porque ``ResCompany`` no
  es ``BaseModel`` y no los recalcula el ORM.
"""
from django.db import models

import fields
from addons.mail.models.mail_alias_domain import MailAliasDomain
from orm.environments import sudo
from orm.model_classes import extend_model
from tools.mail import formataddr


def _default_alias_domain_id():
    """≙ ``_default_alias_domain_id`` (``odoo19c: :10-11``).

    El primer dominio, en el orden del modelo (``sequence``, ``id``), como
    ``search([], limit=1)``. El ``default`` de Django es un invocable sin
    argumentos, así que es una función de módulo.
    """
    return MailAliasDomain.objects.values_list('pk', flat=True).first()


def _compute_bounce(self):
    """≙ ``_compute_bounce`` (``odoo19c: :35-43``): el par de rebote."""
    if not self.alias_domain_id:
        return '', ''
    bounce_email = self.alias_domain_id.bounce_email
    return bounce_email, formataddr((self.name, bounce_email))


def _compute_catchall(self):
    """≙ ``_compute_catchall`` (``odoo19c: :45-53``): el par de catchall."""
    if not self.alias_domain_id:
        return '', ''
    catchall_email = self.alias_domain_id.catchall_email
    return catchall_email, formataddr((self.name, catchall_email))


def _compute_email_formatted(self):
    """≙ ``_compute_email_formatted`` (``odoo19c: :55-62``).

    El del partner si lo tiene, si no el de catchall, si no ``''``. En la
    fuente corre con ``compute_sudo``: un usuario de portal no lee el
    partner, pero sí debe ver la dirección de la empresa.
    """
    with sudo():
        partner_formatted = self.partner.email_formatted
    return partner_formatted or self.catchall_formatted or ''


def _default_from_email(self):
    """≙ ``related='alias_domain_id.default_from_email'`` (``:20-22``)."""
    if not self.alias_domain_id:
        return ''
    return self.alias_domain_id.default_from_email


def apply_mail_company_extensions():
    """≙ ``_inherit = 'res.company'`` de ``mail``.

    La invoca ``MailConfig.ready()``, no el import: en tiempo de import el
    registro de modelos aún no está poblado.
    """
    extend_model(
        'base', 'ResCompany',
        campos={
            'alias_domain_id': fields.Many2one(
                MailAliasDomain, verbose_name='Email Domain',
                db_column='alias_domain_id',
                null=True, blank=True, on_delete=models.SET_NULL,
                related_name='company_ids', index='btree_not_null',
                db_index=False, default=_default_alias_domain_id,
            ),
            'email_primary_color': fields.Char(
                verbose_name='Email Button Text', max_length=7,
                default='#FFFFFF',
            ),
            'email_secondary_color': fields.Char(
                verbose_name='Email Button Color', max_length=7,
                default='#875A7B',
            ),
        },
        propiedades={
            'bounce_email': lambda self: _compute_bounce(self)[0],
            'bounce_formatted': lambda self: _compute_bounce(self)[1],
            'catchall_email': lambda self: _compute_catchall(self)[0],
            'catchall_formatted': lambda self: _compute_catchall(self)[1],
            'default_from_email': _default_from_email,
            'email_formatted': _compute_email_formatted,
        },
    )
