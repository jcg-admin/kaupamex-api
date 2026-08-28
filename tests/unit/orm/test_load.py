"""``BaseModel.load`` — el importador de filas (#132).

≙ ``odoo19c: odoo/orm/models.py:895-1073``. Recibe la cabecera y la matriz de
un archivo, y devuelve ``{'ids', 'messages', 'nextrow'}``. Lo consume
``tools.convert.convert_csv_import``, que es como un addon declara sus datos
en CSV en vez de en XML.

Qué haría fallar a estos casos
==============================

Un cargador que no carga devuelve ``ids: False`` con sus mensajes, así que un
caso que sólo mirase «no reventó» sería verde con el porte ausente. Cada caso
afirma **el efecto en la base** —la fila existe, o no existe— y no sólo la
forma del resultado.

El caso del error parcial es el que discrimina la decisión más cara de la
fuente: si **algo** falla, se deshace **todo**. Sin el punto de retorno, la
primera fila buena quedaría escrita.
"""
import pytest

from addons.base.models.ir_model import IrModelData
from addons.base.models.ir_module import IrModuleCategory
from orm.environments import context_scope

#: El modelo de prueba: adopta ``RecordLoaderMixin`` —como los 285 que lo
#: hacen vía ``TimeStampedModel``— y sus columnas son escalares, así que el
#: caso mide el cargador y no la relación.


@pytest.mark.django_db
class TestTheHappyPath:
    """La matriz entra y las filas quedan."""

    def test_two_rows_become_two_records(self):
        result = IrModuleCategory.load(['name', 'description'],
                                        [['Contabilidad', 'a'], ['Ventas', 'b']])

        assert result['messages'] == []
        assert len(result['ids']) == 2
        assert IrModuleCategory.objects.filter(name__in=('Contabilidad', 'Ventas')).count() == 2

    def test_the_external_id_is_assigned(self):
        result = IrModuleCategory.load(['id', 'name'],
                                        [['cat_zy', 'Contabilidad']])

        assert result['messages'] == []
        assert IrModelData.objects.filter(
            module='__import__', name='cat_zy').exists()

    def test_the_module_of_the_context_prefixes_the_external_id(self):
        with context_scope(module='l10n_zy'):
            IrModuleCategory.load(['id', 'name'],
                                   [['cat_zy', 'Contabilidad']])

        assert IrModelData.objects.filter(
            module='l10n_zy', name='cat_zy').exists()

    def test_a_second_load_of_the_same_external_id_updates(self):
        IrModuleCategory.load(['id', 'name'], [['cat_zy', 'Contabilidad']])

        with context_scope(mode='update'):
            IrModuleCategory.load(['id', 'name'],
                                  [['cat_zy', 'Contabilidad Nueva']])

        assert IrModuleCategory.objects.filter(
            name='Contabilidad Nueva').count() == 1
        assert IrModuleCategory.objects.filter(name='Contabilidad').count() == 0


@pytest.mark.django_db
class TestTheFailurePath:
    """Si algo falla, no queda nada: una importación es completa o no es."""

    def test_an_unknown_column_is_refused_before_touching_the_base(self):
        with pytest.raises(ValueError):
            IrModuleCategory.load(['no_soy_una_columna'], [['x']])

    def test_a_failing_row_undoes_the_good_ones(self):
        """El punto de retorno: sin él la primera fila quedaría escrita."""
        antes = IrModuleCategory.objects.count()

        result = IrModuleCategory.load(
            ['name', 'sequence'],
            [['Contabilidad', '1'], ['Ventas', 'no-soy-un-entero']])

        assert result['ids'] is False
        assert any(m['type'] == 'error' for m in result['messages'])
        assert IrModuleCategory.objects.count() == antes

    def test_the_message_names_the_row_that_failed(self):
        result = IrModuleCategory.load(
            ['name', 'sequence'],
            [['Contabilidad', '1'], ['Ventas', 'no-soy-un-entero']])

        errores = [m for m in result['messages'] if m['type'] == 'error']
        assert errores and errores[0]['rows']['from'] == 1


@pytest.mark.django_db
class TestTheReferencingColumns:
    """``.id`` y ``id`` seleccionan un registro en vez de crear uno."""

    def test_a_database_id_column_updates_that_record(self):
        category = IrModuleCategory.objects.create(name='Contabilidad')

        result = IrModuleCategory.load(
            ['.id', 'name'], [[str(category.pk), 'Contabilidad Nueva']])

        assert result['messages'] == []
        category.refresh_from_db()
        assert category.name == 'Contabilidad Nueva'

    def test_an_unknown_database_id_is_reported(self):
        result = IrModuleCategory.load(['.id', 'name'], [['99999999', 'Fantasma']])

        assert any(m['field'] == '.id' for m in result['messages'])


@pytest.mark.django_db
class TestTheResultShape:
    """``nextrow`` es lo que la fuente promete: 0 cuando no hay más."""

    def test_nextrow_is_zero_when_the_file_ended(self):
        result = IrModuleCategory.load(['name'], [['Contabilidad']])

        assert result['nextrow'] == 0

    def test_the_limit_stops_and_reports_where(self):
        with context_scope(_import_limit=1):
            result = IrModuleCategory.load(
                ['name'], [['Contabilidad'], ['Ventas']])

        assert result['nextrow'] == 1
        assert IrModuleCategory.objects.filter(name='Ventas').count() == 0
