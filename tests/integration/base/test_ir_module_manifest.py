"""Tests — la metadata que ``ir.module.module`` lee del manifest.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_module.py``:
``get_module_info`` (``:165-173``), ``_get_latest_version`` (``:211-215``),
``_get`` (``:898-903``) y ``_get_id`` (``:906-909``); más las catorce claves
de ``get_values_from_terp`` (``:752-768``), cuyo análogo puro vive en
``addons/authz/declaration.py::values_from_manifest``.

Ninguno de los cuatro necesita el instalador — leen el árbol y el catálogo.
Qué haría fallar a cada uno se declara en su caso.
"""
import pytest

from addons.authz.declaration import values_from_manifest
from addons.base.models import IrModule

pytestmark = pytest.mark.integration


class TestValuesFromManifest:
    """≙ ``get_values_from_terp`` (``odoo19c: ir_module.py:752-768``)."""

    #: Las catorce que la fuente devuelve. Se enumeran a mano y no se derivan
    #: del propio return: derivarlas haría que el caso pasara siempre, que es
    #: exactamente el verde que no discrimina.
    KEYS_OF_THE_SOURCE = frozenset({
        'description', 'shortdesc', 'author', 'maintainer', 'contributors',
        'website', 'license', 'sequence', 'application', 'auto_install',
        'icon', 'summary', 'url', 'to_buy',
    })

    def test_the_fourteen_keys_of_the_source_are_covered(self):
        """CONTROL de cobertura — el caso que la versión de nueve claves
        habría reprobado.

        ``sequence`` es la única de las catorce que aquí no sale de esta
        función: el modelo la declara con ``default=100``, el mismo valor de la
        fuente, así que el mapeo no la necesita para que la columna lo tenga.
        """
        keys = set(values_from_manifest({}))
        ausentes = self.KEYS_OF_THE_SOURCE - keys - {'sequence'}
        assert ausentes == set(), f'claves de la fuente sin cubrir: {ausentes}'

    def test_an_empty_manifest_yields_the_defaults_of_the_source(self):
        values = values_from_manifest({})
        assert values['license'] == 'LGPL-3'
        assert values['application'] is False
        assert values['auto_install'] is False
        assert values['to_buy'] is False
        assert values['category'] == 'Uncategorized'
        assert values['version'] == '1.0'

    def test_the_author_does_not_fall_back_to_unknown(self):
        """Divergencia declarada frente a la fuente, con su razón.

        La fuente escribe ``'Unknown'``; aquí ``modules.module`` ya rellena el
        autor del proyecto cuando el manifest calla, así que ese literal
        guardaría un dato falso para un addon propio.
        """
        assert values_from_manifest({})['author'] == ''
        assert values_from_manifest({'author': 'Kaupamex'})['author'] == 'Kaupamex'

    def test_the_contributor_list_is_flattened_with_commas(self):
        values = values_from_manifest({'contributors': ['Ana', 'Beto']})
        assert values['contributors'] == 'Ana, Beto'

    def test_without_contributors_the_string_is_empty(self):
        assert values_from_manifest({})['contributors'] == ''

    def test_the_url_falls_back_to_the_live_test_url(self):
        """La fuente lo hace con ``or``, así que un ``url`` vacío también cae."""
        assert values_from_manifest(
            {'live_test_url': 'https://demo'})['url'] == 'https://demo'
        assert values_from_manifest(
            {'url': '', 'live_test_url': 'https://demo'})['url'] == 'https://demo'

    def test_the_url_wins_over_the_live_test_url_when_present(self):
        """CONTROL de la dirección contraria — sin él, un mapeo que SIEMPRE
        devolviera ``live_test_url`` pasaría el caso anterior.
        """
        assert values_from_manifest(
            {'url': 'https://real', 'live_test_url': 'https://demo'}
        )['url'] == 'https://real'

    def test_the_description_is_dedented(self):
        """``dedent`` de la fuente: el manifest suele traer un literal
        triple-comilla indentado, y guardarlo con su sangría rompe el render.
        """
        crudo = '\n    primera\n    segunda\n'
        assert values_from_manifest(
            {'description': crudo})['description'] == '\nprimera\nsegunda\n'

    def test_auto_install_of_a_list_is_true(self):
        """La fuente compara ``is not False``, no la verdad del valor.

        Un manifest declara ``auto_install`` como lista de condiciones; una
        lista vacía es falsa en Python y aun así significa "sí, automático".
        """
        assert values_from_manifest({'auto_install': []})['auto_install'] is True
        assert values_from_manifest(
            {'auto_install': False})['auto_install'] is False


class TestGetModuleInfo:
    """≙ ``get_module_info`` (``odoo19c: ir_module.py:165-173``)."""

    def test_a_real_addon_returns_its_manifest(self):
        info = IrModule.get_module_info('base')
        assert info.get('name')
        assert 'version' in info

    def test_an_addon_that_does_not_exist_returns_an_empty_dict(self):
        assert IrModule.get_module_info('no_existe_este_addon') == {}

    def test_a_dict_is_returned_as_it_stands(self):
        """La segunda forma de la fuente: un manifest ya resuelto pasa entero."""
        ya_resuelto = {'name': 'Ya resuelto', 'version': '9.9'}
        assert IrModule.get_module_info(ya_resuelto) is ya_resuelto

    def test_anything_else_returns_an_empty_dict(self):
        """La tercera forma. Sin este caso, una implementación que sólo
        distinguiera cadena de no-cadena reventaría con ``None``.
        """
        assert IrModule.get_module_info(None) == {}
        assert IrModule.get_module_info(42) == {}


class TestGetLatestVersion:
    """≙ ``_get_latest_version`` (``odoo19c: ir_module.py:211-215``)."""

    def test_it_reads_the_version_from_disk_not_from_the_row(self, db):
        """El punto entero del método: la fila puede estar atrasada.

        Se guarda una versión falsa en el catálogo y se comprueba que el
        método NO la devuelve. Sin esta divergencia entre fila y disco, un
        método que leyera ``self.version`` pasaría igual.
        """
        row = IrModule.objects.create(name='base', version='0.0.0-falsa')
        assert row._get_latest_version() != '0.0.0-falsa'
        assert row._get_latest_version() == IrModule.get_module_info(
            'base')['version']

    def test_an_addon_without_manifest_falls_back_to_one_dot_zero(self, db):
        row = IrModule.objects.create(name='no_existe_este_addon')
        assert row._get_latest_version().endswith('1.0')


class TestGetAndGetId:
    """≙ ``_get`` y ``_get_id`` (``odoo19c: ir_module.py:898-909``)."""

    def test_get_id_returns_the_primary_key(self, db):
        row = IrModule.objects.create(name='modulo_de_prueba')
        assert IrModule._get_id('modulo_de_prueba') == row.pk

    def test_get_id_of_an_absent_name_is_none(self, db):
        assert IrModule._get_id('no_existe_este_addon') is None

    def test_get_returns_the_row(self, db):
        row = IrModule.objects.create(name='modulo_de_prueba')
        assert IrModule._get('modulo_de_prueba') == row

    def test_get_of_an_absent_name_is_none(self, db):
        assert IrModule._get('no_existe_este_addon') is None

    def test_get_of_an_empty_name_is_none_without_touching_the_table(self, db):
        """La fuente corta antes de consultar: ``if name else False``.

        Sin la guarda, un nombre vacío consultaría la tabla y devolvería la
        primera fila que tuviera ``name=''`` — que es un módulo distinto de
        "ninguno".
        """
        IrModule.objects.create(name='')
        assert IrModule._get('') is None
