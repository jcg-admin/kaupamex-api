"""Tests unitarios — la FORMA de ``ir.module.*`` contra su fuente (H-API-756).

Estos casos no prueban comportamiento: prueban que el **puerto sigue teniendo la
forma que la referencia declara**. Es el control que faltaba cuando
:ref:`h-api-750` truncó un ``summary`` real contra una columna de 255 que la
fuente no impone.

Las tres afirmaciones vienen de una medición sobre
``odoo19c: odoo/addons/base/models/ir_module.py`` (``odoo-tools@622ddc2a``), no
de memoria:

- sus **16** ``fields.Char`` se declaran **sin** ``size=`` → columna ``varchar``
  sin límite;
- sus tres clases declaran atributos de clase (4 · 7 · 4) que aquí se portan
  verbatim;
- su ``_order`` nombra ``sequence``, que este modelo debe poseer para poder
  cumplirlo.

El tercero es el más general de los tres: un ``_order`` que nombre un campo
inexistente describe un orden que el modelo no puede ejecutar, y ningún gate de
conteo de símbolos lo ve.
"""
import pytest
from django.db import connection

from addons.base.models import IrModule, IrModuleCategory, IrModuleDependency

pytestmark = [pytest.mark.unit]

# Los Char cuyo tope se retiró en la migración 0034. ``category`` NO está en la
# lista a propósito: es un desnormalizado nuestro sin contraparte de esa forma
# en la fuente, y conserva su tope con la razón declarada en el modelo.
UNBOUNDED_CHAR_COLUMNS = [
    ('ir_module_module', 'name'),
    ('ir_module_module', 'shortdesc'),
    ('ir_module_module', 'summary'),
    ('ir_module_module', 'version'),
    ('ir_module_category', 'name'),
    ('ir_module_module_dependency', 'name'),
]


@pytest.mark.django_db
def test_the_ported_char_columns_carry_no_length_limit():
    """El tope se retiró en la base, no sólo en el modelo.

    ``supports_unlimited_charfield`` es ``True`` en el backend PostgreSQL de
    Django 6, así que un ``CharField`` sin ``max_length`` emite ``varchar`` a
    secas — exactamente la columna que produce un ``fields.Char`` sin tamaño en
    la referencia. Sin esta aserción, un ``makemigrations`` futuro podría
    reponer el tope y nadie se enteraría hasta el próximo truncamiento.
    """
    # psycopg 3 no adapta una tupla de tuplas a un ``IN`` de valores-fila, así
    # que se filtra por las dos columnas y se cruza el producto en Python.
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name, column_name, character_maximum_length
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name  = ANY(%s)
               AND column_name = ANY(%s)
            """,
            [
                sorted({t for t, _ in UNBOUNDED_CHAR_COLUMNS}),
                sorted({c for _, c in UNBOUNDED_CHAR_COLUMNS}),
            ],
        )
        wanted = set(UNBOUNDED_CHAR_COLUMNS)
        measured = {
            (t, c): limit
            for t, c, limit in cursor.fetchall()
            if (t, c) in wanted
        }

    assert set(measured) == set(UNBOUNDED_CHAR_COLUMNS), (
        f'columnas no encontradas en el schema: '
        f'{set(UNBOUNDED_CHAR_COLUMNS) - set(measured)}'
    )
    capped = {k: v for k, v in measured.items() if v is not None}
    assert not capped, f'estas columnas recuperaron un tope: {capped}'


def test_the_class_attributes_match_the_reference():
    """Los 4 · 7 · 4 atributos de clase que la fuente declara, verbatim.

    Medidos con AST sobre la referencia; se escriben aquí como literales para
    que el test falle si alguien los cambia sin volver a medir.
    """
    assert IrModuleCategory._name == 'ir.module.category'
    assert IrModuleCategory._description == 'Application'
    assert IrModuleCategory._order == 'sequence, name, id'
    assert IrModuleCategory._allow_sudo_commands is False

    assert IrModule._name == 'ir.module.module'
    assert IrModule._rec_name == 'shortdesc'
    assert IrModule._rec_names_search == ['name', 'shortdesc', 'summary']
    assert IrModule._description == 'Module'
    assert IrModule._order == 'application desc,sequence,name'
    assert IrModule._allow_sudo_commands is False

    assert IrModuleDependency._name == 'ir.module.module.dependency'
    assert IrModuleDependency._description == 'Module dependency'
    assert IrModuleDependency._log_access is False
    assert IrModuleDependency._allow_sudo_commands is False


@pytest.mark.parametrize(
    'model', [IrModule, IrModuleCategory], ids=['ir.module.module', 'ir.module.category'])
def test_every_field_named_by_order_exists_on_the_model(model):
    """``_order`` no puede nombrar un campo que el modelo no declara.

    Es la aserción que destapó el hueco: ``IrModule._order`` nombra
    ``sequence`` y el puerto no lo tenía, así que el atributo describía un orden
    inejecutable. El campo se portó (``odoo19c: …/ir_module.py:294``) en el
    mismo pase.
    """
    declared = {f.name for f in model._meta.get_fields()}
    for segment in model._order.split(','):
        field_name = segment.strip().split()[0]
        if field_name == 'id':
            continue
        assert field_name in declared, (
            f'{model.__name__}._order nombra "{field_name}", que el modelo no declara'
        )


@pytest.mark.django_db
def test_the_display_name_falls_back_when_rec_name_is_empty():
    """``__str__`` consume ``_rec_name`` y no devuelve cadena vacía.

    La referencia etiqueta por ``shortdesc``; aquí ese campo admite vacío, así
    que el respaldo al nombre técnico es lo que evita un registro sin etiqueta.
    """
    with_shortdesc = IrModule(name='sale', shortdesc='Ventas')
    without_shortdesc = IrModule(name='sale', shortdesc='')

    assert str(with_shortdesc) == 'Ventas'
    assert str(without_shortdesc) == 'sale'
