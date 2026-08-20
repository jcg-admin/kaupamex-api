"""Tests unitarios — la FORMA de los ``Char`` de ``hr`` contra su fuente (H-API-757).

Estos casos no prueban comportamiento: prueban que el **puerto sigue teniendo la
forma que la referencia declara**. Son el hermano de
``tests/unit/base/test_ir_module_reference_shape.py``, que nació de
:ref:`h-api-750` — un ``summary`` real truncado contra una columna de 255 que la
fuente no impone.

La afirmación viene de una medición sobre ``odoo19c: addons/hr/`` (``odoo-tools``
en su commit ``622ddc2a``), no de memoria::

    grep -rho 'fields\\.Char(' addons/hr/models/*.py | wc -l   -> 93
    grep -rn  'size='        addons/hr/           | wc -l      ->  0

Es decir: **93 de 93 sin tamaño**. Y no es una peculiaridad de ``hr`` — el
``Char`` de la referencia deriva su columna de ``pg_varchar(self.size)``
(``odoo19c: odoo/orm/fields_textual.py:496``), y ``pg_varchar`` devuelve un
``VARCHAR`` sin límite cuando el tamaño es nulo (``odoo/tools/sql.py:644-654``).
El ``Selection`` va más lejos: su columna es ``('varchar', pg_varchar())``
literal (``odoo/orm/fields_selection.py:63``), sin tamaño posible.

El tope, por tanto, no se sube: **se retira**. ``supports_unlimited_charfield``
es ``True`` en el backend PostgreSQL de Django 6, así que un ``CharField`` sin
``max_length`` emite el mismo ``varchar`` a secas.
"""
import pytest
from django.apps import apps
from django.db import connection

pytestmark = [pytest.mark.unit]

#: Modelos cuyos ``Char`` deben salir sin tope. Se enumeran por etiqueta en vez
#: de barrer la app entera para que un modelo **nuevo** entre por decisión y no
#: por omisión: quien lo añada mide su contraparte y lo suma aquí.
HR_LABELS = [
    'hr.HrContractType',
    'hr.HrDepartment',
    'hr.HrDepartureReason',
    'hr.HrEmployee',
    'hr.HrEmployeeCategory',
    'hr.HrEmployeePublic',
    'hr.HrJob',
    'hr.HrPayrollStructureType',
    'hr.HrVersion',
    'hr.HrWorkLocation',
]

#: El campo que ``hr`` cuelga de ``res.company`` por extensión. Su columna vive
#: en ``base``, no en ``hr``, y por eso su migración salió en ``base``; pero es
#: uno de los 57 y se mide con los demás.
COMPANY_FIELD = ('base.ResCompany', 'hr_presence_control_ip_list')

#: Campos con tope **declarado y justificado**. Hoy está vacío a propósito: los
#: 57 tenían contraparte en la referencia y ninguna llevaba ``size=``. Un campo
#: propio del L0 sin contraparte puede entrar aquí con su razón, igual que
#: ``IrModule.category`` en :ref:`h-api-756`.
CAPPED_BY_DECISION: dict[tuple[str, str], str] = {}


def _char_fields(label):
    model = apps.get_model(label)
    return [
        f for f in model._meta.get_fields()
        if getattr(f, 'get_internal_type', None) and f.get_internal_type() == 'CharField'
    ]


@pytest.mark.parametrize('label', HR_LABELS)
def test_no_hr_char_field_declares_a_cap(label):
    """Ningún ``Char`` de ``hr`` lleva ``max_length`` — el modelo, no la base.

    Es la aserción que cierra el grifo: un campo nuevo con tope la rompe aquí,
    antes de que llegue a una columna. Si el tope es deliberado (un campo propio
    del L0 sin contraparte), su sitio es ``CAPPED_BY_DECISION`` con la razón
    escrita, no un ``max_length`` suelto.
    """
    capped = {
        f.name: f.max_length
        for f in _char_fields(label)
        if getattr(f, 'max_length', None)
        and (label, f.name) not in CAPPED_BY_DECISION
    }
    assert not capped, (
        f'{label} declara tope en {capped}; la referencia declara sus 93 '
        f'fields.Char sin size= (odoo19c: addons/hr/, odoo-tools@622ddc2a)'
    )


def test_the_company_field_hung_by_hr_declares_no_cap():
    """``hr`` extiende ``res.company`` — el campo es suyo aunque la tabla no.

    ``odoo19c: addons/hr/models/res_company.py:10`` lo declara
    ``fields.Char(string="Valid IP addresses")``, sin tamaño.
    """
    label, name = COMPANY_FIELD
    field = apps.get_model(label)._meta.get_field(name)
    assert field.max_length is None, (
        f'{label}.{name} declara max_length={field.max_length}'
    )


@pytest.mark.django_db
def test_the_hr_char_columns_carry_no_length_limit():
    """El tope se retiró en la base, no sólo en el modelo.

    Sin esta aserción, una migración futura podría reponer el límite —o
    quedarse sin generar— y nadie se enteraría hasta el próximo truncamiento,
    que es exactamente cómo se destapó :ref:`h-api-750`.

    Los modelos **no gestionados** quedan fuera: ``hr.employee.public`` declara
    ``managed = False`` porque la referencia lo declara ``_auto = False``
    (``odoo19c: addons/hr/models/hr_employee_public.py:14``) — es una vista, no
    una tabla, y no tiene columna propia que medir. Su forma la cubre el caso
    de modelo de arriba.
    """
    expected = {
        (apps.get_model(label)._meta.db_table, f.column)
        for label in HR_LABELS
        if apps.get_model(label)._meta.managed
        for f in _char_fields(label)
        if getattr(f, 'column', None) and (label, f.name) not in CAPPED_BY_DECISION
    }
    company_table = apps.get_model(COMPANY_FIELD[0])._meta.db_table
    expected.add((company_table, COMPANY_FIELD[1]))

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name, column_name, character_maximum_length
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name  = ANY(%s)
            """,
            [sorted({t for t, _ in expected})],
        )
        measured = {
            (t, c): limit
            for t, c, limit in cursor.fetchall()
            if (t, c) in expected
        }

    assert set(measured) == expected, (
        f'columnas no encontradas en el schema: {expected - set(measured)}'
    )
    capped_columns = {k: v for k, v in measured.items() if v is not None}
    assert not capped_columns, (
        f'columnas con varchar(n) tras la migración: {capped_columns}'
    )
