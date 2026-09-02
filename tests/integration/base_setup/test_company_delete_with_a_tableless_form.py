"""Tests — borrar una empresa con el formulario de ajustes sin tabla.

El formulario ``res.config.settings`` de este árbol no tiene tabla
(``Meta.managed = False``), y declara una FK a ``res.company``. Mientras esa
FK dijo ``PROTECT``, el recolector de borrado de Django la visitaba y
consultaba ``base_setup_siteconfigsettings_unmanaged`` — una relación que
nunca se crea—, así que **borrar cualquier empresa** moría con
``UndefinedTable``. Ver :ref:`h-api-1026`.

Qué haría fallar a cada control
--------------------------------

``TestDeletingACompany::test_it_does_not_query_the_form_without_a_table``
    CONTROL de la conducta. Es el caso que estaba rojo; volver la FK a
    ``PROTECT`` o a cualquier otra política que el recolector visite lo pone
    rojo otra vez.

``TestTheDeclarationSaysWhy::test_the_form_has_no_table``
    CONTROL de la premisa. Si algún día el formulario pasa a tener tabla, la
    razón de ``DO_NOTHING`` desaparece y este caso avisa antes de que nadie
    lea la declaración como una relajación gratuita de la integridad.
"""
import pytest
from django.db.models.deletion import DO_NOTHING

from addons.base.models.res_company import ResCompany
from addons.base_setup.models.res_config_settings import SiteConfigSettings

pytestmark = pytest.mark.integration


class TestTheDeclarationSaysWhy:
    """La premisa de la que cuelga ``DO_NOTHING``."""

    def test_the_form_has_no_table(self):
        assert SiteConfigSettings._meta.managed is False

    def test_the_company_link_is_not_collected(self):
        field = SiteConfigSettings._meta.get_field('company_id')
        assert field.remote_field.on_delete is DO_NOTHING, (
            'una politica que el recolector visita hace consultar una tabla '
            'que no existe')


class TestDeletingACompany:
    """El borrado no cruza al formulario sin tabla."""

    def test_it_does_not_query_the_form_without_a_table(self, db):
        company = ResCompany.objects.create(
            code='kaupamex_test_delete', name='Kaupamex de prueba')
        pk = company.pk

        company.delete()

        assert not ResCompany.objects.filter(pk=pk).exists()
