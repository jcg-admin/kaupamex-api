"""Tests — ``IrModuleCategory.xml_id``, el identificador externo (#250).

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_module.py:91-99``
(``xml_id`` + ``_compute_xml_id``).

El campo se declinaba con esta razón: *"se computa desde ``ir.model.data``, el
registro de datos declarativos XML de Odoo, que este árbol no tiene"*. Medido
al barrer la prosa, ``ir.model.data`` **sí** está — ``ir_model.py:2848`` lo
declara con los cuatro campos que el cómputo necesita.

Qué haría fallar a cada control se declara en cada caso.
"""
import pytest

from addons.base.models.ir_model import IrModelData
from addons.base.models.ir_module import IrModuleCategory

pytestmark = pytest.mark.integration


@pytest.fixture
def category(db):
    return IrModuleCategory.objects.create(name='Ventas')


def _external_id(record, module, name):
    return IrModelData.objects.create(
        model=type(record)._meta.label, res_id=record.pk,
        module=module, name=name)


class TestTheExternalIdOfACategory:

    def test_it_joins_the_module_and_the_name(self, category):
        """``:97`` — ``"%s.%s" % (data['module'], data['name'])``.

        Qué lo haría fallar: devolver sólo el ``name``. Un identificador
        externo sin su módulo no es único: dos addons pueden llamar igual a su
        categoría, y quien lo resuelva traería la del otro.
        """
        _external_id(category, 'base', 'module_category_sales')
        assert category.xml_id == 'base.module_category_sales'

    def test_a_category_nobody_declared_reads_empty(self, category):
        """``:99`` — ``xml_ids.get(cat.id, [''])[0]``.

        Qué lo haría fallar: reventar con ``IndexError`` o devolver ``None``.
        La fuente entrega la cadena vacía, que es lo que un serializer puede
        mandar sin ramificar.
        """
        assert category.xml_id == ''

    def test_with_two_ids_it_takes_the_first(self, category):
        """``[0]`` de ``:99`` — la fuente admite varios y entrega uno.

        Comentario de la fuente en su hermano de ``ir.model.data``, verbatim:
        *"a same record can have several external ids"*. Qué lo haría fallar:
        devolver la lista, o concatenarlos. El campo es ``Char``, no
        ``One2many``.
        """
        _external_id(category, 'base', 'module_category_a')
        _external_id(category, 'sale', 'module_category_b')
        assert category.xml_id in ('base.module_category_a',
                                   'sale.module_category_b')
        assert '.' in category.xml_id and ',' not in category.xml_id

    def test_it_does_not_take_the_id_of_another_record(self, category):
        """CONTROL del filtro por ``res_id`` (``:96``).

        Qué lo haría fallar: filtrar sólo por modelo. Toda categoría
        devolvería el identificador de la primera declarada.
        """
        other = IrModuleCategory.objects.create(name='Compras')
        _external_id(other, 'purchase', 'module_category_purchases')
        assert category.xml_id == ''
        assert other.xml_id == 'purchase.module_category_purchases'

    def test_it_does_not_take_the_id_of_another_model(self, category):
        """CONTROL del filtro por modelo (``:96``).

        Qué lo haría fallar: filtrar sólo por ``res_id``. Los ids son
        secuencias por tabla, así que la categoría 3 se llevaría el
        identificador del módulo 3.
        """
        IrModelData.objects.create(model='base.IrModule', res_id=category.pk,
                                   module='base', name='module_sale')
        assert category.xml_id == ''

    def test_the_field_takes_no_column(self):
        """El campo es **no persistido**, como en la fuente
        (``fields.Char(compute=...)`` sin ``store``).

        Qué lo haría fallar: declararlo con columna. La tabla guardaría una
        copia que ``ir.model.data`` puede desmentir en cualquier momento —
        dos fuentes de verdad para el mismo dato.
        """
        columns = {f.name for f in IrModuleCategory._meta.get_fields()}
        assert 'xml_id' not in columns
