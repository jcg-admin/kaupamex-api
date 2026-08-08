"""``account.tax`` — clasificación fiscal SAT del impuesto (Odoo ``l10n_mx``).

Adaptado de Odoo Community ``l10n_mx/models/account_tax.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — DEC-KX-03.

Porte completo: la referencia declara **2 campos** y **1 método** sobre
``account.tax``; los tres se cuelgan aquí. Ninguno se omite.

Dos divergencias declaradas, ambas de mecanismo — no de alcance
=================================================================

**No hay ``_inherit`` que extender.** ``api: src/addons/account/models/
account_tax.py`` no declara ``save()`` propio (usa el ``Model.save()`` de
Django sin envoltura): el punto donde la referencia dispara
``_compute_l10n_mx_tax_type`` —cada cambio de ``country_id``— no tiene
análogo de ``super()`` que llamar. El equivalente idiomático ya establecido
en este puerto para colgar comportamiento de OTRO addon sobre un modelo
ajeno, sin tocar su archivo, es una señal Django: ``pre_save`` (mismo patrón
que ``stock: handlers.py::_cache_return_old_status`` y
``account: models/product.py::_inherit_company_default_taxes``).

**``AccountTax`` de este árbol no tiene ``country_id`` propio.** La
referencia deriva el tipo de ``tax.country_id.code`` (un campo del propio
impuesto, ``related`` a la posición fiscal del país). El puerto de
``account.tax`` no porta ese campo — el impuesto no declara país aquí. Se
deriva de la empresa dueña del impuesto: ``instance.company.country_code``
(``base: models/res_company.py:415``, delegado al partner). Es la misma
clase de sustitución que ``account_tax_group.py`` ya declaró para su propio
``country_code`` no portado.

**Rellena, no recalcula (mismo criterio que ``AccountAccount._compute_account_type``).**
La referencia recalcula en cada cambio de dependencia aunque el campo ya
tenga valor — es el patrón ``store=True, readonly=False`` de su ORM: el
compute sigue corriendo, pero la UI deja editarlo, y Odoo no vuelve a pisar
lo que el usuario tecleó en la sesión de edición actual. Este ORM no
rastrea ediciones de sesión entre cómputos, así que el receptor sólo llena
el campo cuando está vacío — un valor puesto explícitamente sobrevive.
"""
from django.db.models.signals import pre_save

import api
import fields
from addons.account.models import AccountTax

#: ≙ Odoo ``l10n_mx_factor_type`` — "TipoFactor" del CFDI 4.0.
L10N_MX_FACTOR_TYPES = [
    ('Tasa', 'Tasa'),
    ('Cuota', 'Cuota'),
    ('Exento', 'Exento'),
]

#: ≙ Odoo ``l10n_mx_tax_type`` — clasificación SAT del impuesto.
L10N_MX_TAX_TYPES = [
    ('isr', 'ISR'),
    ('iva', 'IVA'),
    ('ieps', 'IEPS'),
    ('local', 'Local'),
]


def _add_if_absent(model, name, field):
    """Cuelga el campo sólo si el modelo no lo tiene ya.

    Idempotente a propósito: ``ready()`` puede correr más de una vez en un
    proceso (recarga del autoreloader), y ``add_to_class`` sobre un campo
    que ya existe rompe con ``FieldError``. Mismo helper que
    ``account: models/res_company.py`` y ``account: models/product.py``,
    duplicado aquí por el mismo criterio que ellos: es local al módulo que
    lo usa, no una utilidad compartida.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


@api.depends('company')
def _compute_l10n_mx_tax_type(self):
    """El valor por defecto de ``l10n_mx_tax_type`` — ≙ ``_compute_l10n_mx_tax_type``.

    ≙ ``odoo19c: l10n_mx/models/account_tax.py:31-34`` (``odoo-tools@622ddc2a``).
    Ver las dos divergencias declaradas en el docstring del módulo: la fuente
    del país (empresa, no impuesto) y el criterio de sólo-relleno.
    """
    if self.l10n_mx_tax_type:
        return
    company = self.company
    self.l10n_mx_tax_type = (
        'iva' if company is not None and company.country_code == 'MX' else ''
    )


def _apply_l10n_mx_tax_type(sender, instance, **kwargs):
    """Receptor ``pre_save`` — el punto donde la referencia dispara el compute.

    Se conecta a ``pre_save`` (no a ``post_save``): el campo debe quedar
    resuelto ANTES del ``INSERT``/``UPDATE``, igual que un compute
    ``store=True`` de la referencia se resuelve antes de persistir la fila.
    """
    _compute_l10n_mx_tax_type(instance)


def apply_l10n_mx_extensions():
    """≙ ``_inherit = 'account.tax'`` de ``l10n_mx`` (``odoo19c:
    l10n_mx/models/account_tax.py``).

    Se llama desde ``L10nMxConfig.ready()``, no al importar: en tiempo de
    import el registro de modelos aún no está poblado.
    """
    _add_if_absent(AccountTax, 'l10n_mx_factor_type', fields.Selection(
        max_length=8, choices=L10N_MX_FACTOR_TYPES, default='Tasa',
        help_text='Factor SAT (TipoFactor) para CFDI 4.0: indica cómo se '
                  'aplica el monto sobre la base del impuesto (Odoo '
                  'l10n_mx_factor_type).',
    ))
    _add_if_absent(AccountTax, 'l10n_mx_tax_type', fields.Selection(
        max_length=8, choices=L10N_MX_TAX_TYPES, blank=True, default='',
        help_text='Clasificación SAT del impuesto — ISR/IVA/IEPS/Local. Se '
                  'rellena en "iva" cuando la empresa dueña del impuesto es '
                  'mexicana y el campo está vacío (Odoo l10n_mx_tax_type, '
                  'compute).',
    ))
    pre_save.connect(
        _apply_l10n_mx_tax_type, sender=AccountTax,
        dispatch_uid='l10n_mx.account_tax.tax_type',
    )
