"""``convert_csv_import`` — el cargador de datos en CSV (#132).

≙ ``odoo19c: odoo/tools/convert.py:704-759``. Es como un addon declara sus
datos en CSV en vez de en XML; su cuerpo estuvo declarado BLOQUEADO por
``BaseModel.load`` hasta esta tarea.

Qué haría fallar a estos casos
==============================

El nombre del archivo **nombra el modelo**, y las filas acaban en la base: un
caso que sólo mirase «no reventó» sería verde con el cuerpo ausente, que era
justo lo que había —un ``NotImplementedError``—. Cada caso afirma el efecto en
la base, o el error concreto que la fuente promete.
"""
import pytest

from addons.base.models.ir_model import IrModelData
from addons.base.models.ir_module import IrModuleCategory
from tools.convert import convert_csv_import


@pytest.mark.django_db
class TestTheFileNamesTheModel:
    """``ir.module.category-extra.csv`` carga ``ir.module.category``."""

    def test_the_rows_land_in_the_model_the_name_says(self):
        convert_csv_import(
            'base', 'ir.module.category.csv',
            b'name,description\nContabilidad,a\nVentas,b\n')

        assert IrModuleCategory.objects.filter(
            name__in=('Contabilidad', 'Ventas')).count() == 2

    def test_the_suffix_after_the_dash_is_ignored(self):
        convert_csv_import('base', 'ir.module.category-extra.csv',
                           b'name\nContabilidad\n')

        assert IrModuleCategory.objects.filter(name='Contabilidad').exists()

    def test_an_unknown_model_is_refused_by_name(self):
        with pytest.raises(ValueError):
            convert_csv_import('base', 'no.existe.csv', b'name\nx\n')


@pytest.mark.django_db
class TestTheExternalIdColumn:
    """La columna ``id`` asigna el identificador externo del módulo."""

    def test_the_module_prefixes_the_external_id(self):
        convert_csv_import('base', 'ir.module.category.csv',
                           b'id,name\ncat_zy,Contabilidad\n')

        assert IrModelData.objects.filter(module='base',
                                          name='cat_zy').exists()


@pytest.mark.django_db
class TestTheThreeDecisionsOfTheSource:
    """Modo, traducciones y filas vacías — verbatim de la fuente."""

    def test_update_without_the_id_column_is_abandoned(self):
        """Sin ``id`` no hay a qué fila referirse: se abandona el archivo."""
        convert_csv_import('base', 'ir.module.category.csv',
                           b'name\nContabilidad\n', mode='update')

        assert not IrModuleCategory.objects.filter(name='Contabilidad').exists()

    def test_a_translation_column_is_removed(self):
        """Las columnas con ``@`` tienen su propio camino de importación."""
        convert_csv_import('base', 'ir.module.category.csv',
                           b'name,name@es_MX\nContabilidad,Contabilidad ES\n')

        category = IrModuleCategory.objects.get(name='Contabilidad')
        assert category.name == 'Contabilidad'

    def test_an_empty_row_is_discarded(self):
        convert_csv_import('base', 'ir.module.category.csv',
                           b'name\nContabilidad\n\n')

        assert IrModuleCategory.objects.filter(name='Contabilidad').count() == 1


@pytest.mark.django_db
class TestAFailingFileAbortsTheInstall:
    """Si ``load`` devuelve algún error, se levanta: no se instala a medias."""

    def test_a_bad_row_raises_and_leaves_nothing(self):
        before = IrModuleCategory.objects.count()

        with pytest.raises(Exception, match='no se pudo procesar'):
            convert_csv_import(
                'base', 'ir.module.category.csv',
                b'name,sequence\nContabilidad,1\nVentas,no-soy-un-entero\n')

        assert IrModuleCategory.objects.count() == before
