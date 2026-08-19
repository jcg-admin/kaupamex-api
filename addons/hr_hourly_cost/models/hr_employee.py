"""``hr.employee`` — costo por hora (Odoo ``hr_hourly_cost``).

Adaptación de Odoo ``hr_hourly_cost/models/hr_employee.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 de la referencia
================================================

``odoo19c: addons/hr_hourly_cost/models/hr_employee.py`` (11 líneas): 1
clase (``HrEmployee``, ``_inherit``), 1 campo (``hourly_cost``). Ningún
método.

======================================  ==========================================
Símbolo de la referencia                Dónde queda en este puerto
======================================  ==========================================
``HrEmployee.hourly_cost`` (:9-10)      campo homónimo (``add_to_class``)
======================================  ==========================================

Cuatro kwargs de la referencia, con desenlace declarado por separado
=======================================================================

La firma de la referencia es::

    hourly_cost = fields.Monetary('Hourly Cost', currency_field='currency_id',
        groups="hr.group_hr_user", default=0.0, tracking=True)

- ``'Hourly Cost'`` (label) y ``default=0.0`` → **portados** (``help_text``
  para lo primero; ``default=Decimal('0.00')`` para lo segundo, mismo patrón
  que ``HrVersion.wage`` — ``api: addons/hr/models/hr_version.py:310-311``,
  ``max_digits=14, decimal_places=2``).
- ``currency_field='currency_id'`` — **divergencia de mecanismo**.
  ``fields.Monetary`` en este ORM (``orm/fields_numeric.py:28-38``) es un
  despachador de ``store=`` sobre ``models.DecimalField``; no acepta
  ``currency_field=`` porque no hay columna de moneda por campo. La moneda
  ya se resuelve a nivel de empleado — ``HrEmployee.currency`` (property,
  ``api: addons/hr/models/hr_employee.py:591-593``, ``≙ related=
  'company_id.currency_id'``) — que es exactamente lo que
  ``currency_field='currency_id'`` apuntaba a hacer en la referencia.
- ``groups="hr.group_hr_user"`` — **BLOQUEADO**. Es visibilidad de campo por
  grupo de seguridad del cliente web de Odoo; este stack autoriza por
  CAPACIDAD a nivel de vista DRF (``HasCapability``, ``api/CLAUDE.md``), no
  por grupo a nivel de campo. Greppeado: ``grep -rn "groups=" addons/
  --include=*.py`` → 0 usos de un kwarg ``groups=`` en ningún ``fields.*``
  de este árbol — no es un mecanismo que exista aquí para ningún campo, no
  sólo para este.
- ``tracking=True`` — **BLOQUEADO**. Greppeado
  (``grep -n "tracking=True" src/orm/fields*.py`` → 0): ningún ``Field`` de
  este ORM acepta ``tracking=`` como kwarg. Los usos de ``tracking=True`` que
  sí existen en el árbol (``sale/models/sale_order.py``,
  ``stock/models/stock_picking.py``) son sobre el mecanismo de bitácora
  (chatter) de esos modelos, construido a mano por archivo — no un kwarg de
  campo genérico. Colgar ``hourly_cost`` en un modelo sin ese mecanismo
  cablearía un tracking parcial y sin bitácora real. Sucesor: si
  ``hr.employee`` adopta un chatter propio, se retoma ahí — no hay tarea
  registrada porque el mecanismo mismo no existe todavía en este árbol.
"""
from decimal import Decimal

import fields

from addons.hr.models import HrEmployee


def _add_if_absent(model, name, field):
    """Añade el campo sólo si el modelo no lo tiene ya.

    Idéntico al de ``account``/``account_fleet``/``product_expiry``/
    ``l10n_mx``: el idioma de extensión por ``add_to_class`` no tiene MRO,
    así que dos addons que cuelguen el mismo campo duplicarían la columna.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def apply_hr_hourly_cost_extensions():
    """Cuelga ``hourly_cost`` sobre ``hr.HrEmployee``.

    La llama ``HrHourlyCostConfig.ready()``; los tests la invocan
    explícitamente (mismo criterio que ``account_fleet``).
    """
    _add_if_absent(HrEmployee, 'hourly_cost', fields.Monetary(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Costo por hora del empleado (Odoo hourly_cost). Lo '
                  'consume hr_timesheet para valorizar las horas '
                  'registradas — HrEmployee.currency ya resuelve la moneda '
                  '(divergencia de currency_field, ver docstring del '
                  'módulo).',
    ))
