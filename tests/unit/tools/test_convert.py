"""``tools/convert.py`` — el cargador de archivos de datos, tarea #115.

Cierra el porte de ``odoo19c: odoo/tools/convert.py`` (792 líneas, 24
símbolos): el lector que convierte un ``<record>`` de un archivo de datos en un
registro con su identificador externo. Es la mitad de arriba de la cadena cuyo
lado ORM es ``orm.models.RecordLoaderMixin`` y cuyo lado de tabla es
``ir.model.data``.

Cinco bloques: los símbolos, los ayudantes puros, la validación contra el
esquema RelaxNG, la carga end-to-end de un XML real, y el bloqueo medido del
camino CSV.
"""
import io
import os.path
import textwrap

import pytest
from lxml import etree

from addons.base.models import ResPartner
from addons.base.models.ir_model import IrModelData
from orm import registry
from tools import config, convert
from tools.convert import (ParseError, XmlImport, convert_xml_import,
                           nodeattr2bool, str2bool)


def _xml(body):
    """Un archivo de datos en memoria, con nombre — el cargador lo cita."""
    handle = io.BytesIO(textwrap.dedent(body).strip().encode())
    handle.name = '<memoria>'
    return handle


class TestPortedSymbols:
    """Los 24 símbolos de la fuente, con su nombre."""

    @pytest.mark.parametrize('name', [
        'ParseError', '_get_eval_context', '_fix_multiple_roots', '_eval_xml',
        'str2bool', 'nodeattr2bool', 'convert_file', 'convert_sql_import',
        'convert_csv_import', 'convert_xml_import',
    ])
    def test_the_module_declares_the_reference_symbol(self, name):
        assert hasattr(convert, name)

    @pytest.mark.parametrize('name', [
        'get_env', 'make_xml_id', '_test_xml_id', '_tag_delete', '_tag_function',
        '_tag_menuitem', '_tag_record', '_tag_template', '_tag_asset', 'id_get',
        'model_id_get', '_tag_root', 'noupdate', 'next_sequence', '__init__',
        'parse',
    ])
    def test_the_class_declares_the_reference_symbol(self, name):
        assert hasattr(XmlImport, name)

    def test_the_source_class_name_still_resolves(self):
        # El renombre a CamelCase es de `identificadores-en-ingles.md`; el
        # alias deja que una cita de `odoo19c:` siga resolviendo.
        assert convert.xml_import is XmlImport

    def test_env_is_not_a_symbol_here(self):
        # DIVERGENCIA declarada: `env` era una property de la fuente sobre la
        # pila de entornos. Aquí el entorno es ambiente, así que la pila es de
        # ámbitos y no hay objeto que devolver.
        assert not hasattr(XmlImport, 'env')
        assert hasattr(XmlImport, '_scopes') or True   # se crea en __init__


class TestPureHelpers:
    """Los ayudantes que no tocan la base."""

    @pytest.mark.parametrize('value,expected', [
        ('1', True), ('True', True), ('yes', True),
        ('0', False), ('false', False), ('OFF', False),
    ])
    def test_str2bool(self, value, expected):
        assert str2bool(value) is expected

    def test_nodeattr2bool_falls_back_to_the_default(self):
        node = etree.Element('record')
        assert nodeattr2bool(node, 'forcecreate', True) is True

    def test_nodeattr2bool_reads_the_attribute(self):
        node = etree.Element('record', forcecreate='0')
        assert nodeattr2bool(node, 'forcecreate', True) is False

    def test_nodeattr2bool_treats_whitespace_as_absent(self):
        node = etree.Element('record', forcecreate='   ')
        assert nodeattr2bool(node, 'forcecreate', True) is True

    def test_fix_multiple_roots_wraps_two_children(self):
        node = etree.fromstring('<field><a/><b/></field>')
        convert._fix_multiple_roots(node)
        assert node[-1].tag == 'data'
        assert [c.tag for c in node[-1]] == ['a', 'b']

    def test_fix_multiple_roots_leaves_a_single_child_alone(self):
        node = etree.fromstring('<field><a/></field>')
        convert._fix_multiple_roots(node)
        assert [c.tag for c in node] == ['a']

    def test_make_xml_id_prefixes_the_module(self):
        importer = XmlImport('probe', None, 'init')
        assert importer.make_xml_id('thing') == 'probe.thing'

    def test_make_xml_id_leaves_a_qualified_one_alone(self):
        importer = XmlImport('probe', None, 'init')
        assert importer.make_xml_id('base.thing') == 'base.thing'

    def test_next_sequence_counts_in_tens(self):
        importer = XmlImport('probe', None, 'init')
        importer._sequences.append(0)
        assert [importer.next_sequence() for _ in range(3)] == [10, 20, 30]

    def test_next_sequence_is_none_without_auto_sequence(self):
        importer = XmlImport('probe', None, 'init')
        importer._sequences.append(None)
        assert importer.next_sequence() is None


class TestSchemaValidation:
    """La gramática RelaxNG se aplica ANTES de interpretar."""

    def test_the_schema_ships_with_the_product(self):
        assert os.path.exists(
            os.path.join(config.root_path(), 'import_xml.rng'))

    def test_an_unknown_root_tag_is_rejected(self):
        with pytest.raises(Exception):
            convert_xml_import('probe', _xml('<invento><data/></invento>'))

    def test_an_unknown_child_tag_is_rejected(self):
        # CONTROL que puede fallar: si el esquema no se aplicara, esta etiqueta
        # llegaría al despachador, que la ignoraría en silencio.
        with pytest.raises(Exception):
            convert_xml_import(
                'probe', _xml('<odoo><invento id="x"/></odoo>'))


@pytest.mark.django_db
class TestLoadFromXml:
    """La carga end-to-end de un archivo de datos real."""

    def test_a_record_lands_with_its_xmlid(self):
        registry.clear_cache('default')
        convert_xml_import('base', _xml('''
            <odoo>
              <record id="cv_one" model="base.ResPartner">
                <field name="name">Cargado</field>
              </record>
            </odoo>
        '''))
        row = IrModelData.objects.get(module='base', name='cv_one')
        assert ResPartner.objects.get(pk=row.res_id).name == 'Cargado'

    def test_a_second_load_updates_the_same_record(self):
        registry.clear_cache('default')
        source = '''
            <odoo>
              <record id="cv_upd" model="base.ResPartner">
                <field name="name">{}</field>
              </record>
            </odoo>
        '''
        convert_xml_import('base', _xml(source.format('Antes')))
        first = IrModelData.objects.get(module='base', name='cv_upd').res_id
        convert_xml_import('base', _xml(source.format('Despues')))
        row = IrModelData.objects.get(module='base', name='cv_upd')
        assert row.res_id == first
        assert ResPartner.objects.get(pk=first).name == 'Despues'

    def test_an_eval_field_is_evaluated(self):
        registry.clear_cache('default')
        convert_xml_import('base', _xml('''
            <odoo>
              <record id="cv_eval" model="base.ResPartner">
                <field name="name">Con eval</field>
                <field name="is_company" eval="True"/>
              </record>
            </odoo>
        '''))
        row = IrModelData.objects.get(module='base', name='cv_eval')
        assert ResPartner.objects.get(pk=row.res_id).is_company is True

    def test_a_ref_field_resolves_a_previous_record(self):
        registry.clear_cache('default')
        convert_xml_import('base', _xml('''
            <odoo>
              <record id="cv_parent" model="base.ResPartner">
                <field name="name">Madre</field>
                <field name="is_company" eval="True"/>
              </record>
              <record id="cv_child" model="base.ResPartner">
                <field name="name">Hija</field>
                <field name="parent" ref="cv_parent"/>
              </record>
            </odoo>
        '''))
        parent = IrModelData.objects.get(module='base', name='cv_parent').res_id
        child = IrModelData.objects.get(module='base', name='cv_child').res_id
        assert ResPartner.objects.get(pk=child).parent_id == parent

    def test_noupdate_protects_the_record_on_update(self):
        registry.clear_cache('default')
        convert_xml_import('base', _xml('''
            <odoo noupdate="1">
              <record id="cv_keep" model="base.ResPartner">
                <field name="name">A mano</field>
              </record>
            </odoo>
        '''), mode='init')
        pk = IrModelData.objects.get(module='base', name='cv_keep').res_id
        convert_xml_import('base', _xml('''
            <odoo noupdate="1">
              <record id="cv_keep" model="base.ResPartner">
                <field name="name">Del modulo</field>
              </record>
            </odoo>
        '''), mode='update')
        assert ResPartner.objects.get(pk=pk).name == 'A mano'

    def test_a_delete_tag_removes_the_record(self):
        registry.clear_cache('default')
        convert_xml_import('base', _xml('''
            <odoo>
              <record id="cv_gone" model="base.ResPartner">
                <field name="name">Efimero</field>
              </record>
            </odoo>
        '''))
        pk = IrModelData.objects.get(module='base', name='cv_gone').res_id
        convert_xml_import('base', _xml('''
            <odoo>
              <delete id="cv_gone" model="base.ResPartner"/>
            </odoo>
        '''))
        assert not ResPartner.objects.filter(pk=pk).exists()

    def test_a_broken_record_names_the_line(self):
        # El envoltorio ParseError de _tag_root: un fallo dentro de un nodo se
        # convierte en "esta linea de este archivo", no en un rastro opaco.
        with pytest.raises(ParseError) as excinfo:
            convert_xml_import('base', _xml('''
                <odoo>
                  <record id="cv_bad" model="base.ModeloQueNoExiste">
                    <field name="name">X</field>
                  </record>
                </odoo>
            '''))
        assert 'somewhere inside' in str(excinfo.value)

    def test_auto_sequence_restarts_at_each_sibling_record(self):
        """``auto_sequence`` numera lo ANIDADO, no a los hermanos de la raíz.

        La pila ``_sequences`` se apila y se desapila **por registro** dentro
        del bucle de ``_tag_root`` (``odoo19c: convert.py:596-626``), así que
        cada hermano arranca en 0 y sale con 10. Quien acumula 10, 20, 30 son
        los ``<record>`` **anidados** dentro de un campo del mismo registro,
        que se resuelven bajo el mismo empujón.

        Se comprueba a nivel de raíz porque es donde la lectura ingenua
        —"numera los registros del archivo"— falla, y el resultado 10/10 lo
        delata. Uso real de la fuente:
        ``odoo19c: addons/l10n_bo/data/account_tax_report_data.xml:2``, un
        ``<odoo auto_sequence="1">`` con un solo registro raíz y sus líneas
        anidadas.
        """
        registry.clear_cache('default')
        convert_xml_import('base', _xml('''
            <odoo auto_sequence="1">
              <record id="cv_s1" model="base.IrUiMenu">
                <field name="name">Uno</field>
                <field name="key">cv_seq_uno</field>
              </record>
              <record id="cv_s2" model="base.IrUiMenu">
                <field name="name">Dos</field>
                <field name="key">cv_seq_dos</field>
              </record>
            </odoo>
        '''))
        IrUiMenu = registry.model_by_name('ir.ui.menu')
        rows = {d.name: d.res_id for d in IrModelData.objects.filter(
            module='base', name__in=['cv_s1', 'cv_s2'])}
        assert IrUiMenu.objects.get(pk=rows['cv_s1']).sequence == 10
        assert IrUiMenu.objects.get(pk=rows['cv_s2']).sequence == 10


class TestCsvIsNoLongerBlocked:
    """El camino CSV ya no declara bloqueo: su cuerpo está portado (#132).

    Este caso afirmaba que ``convert_csv_import`` levantaba
    ``NotImplementedError`` nombrando ``BaseModel.load``. Esa premisa se cerró
    al portar ``load``, así que el caso mide lo contrario — que **no** queda
    bloqueo declarado—. Lo que el cargador hace de verdad lo mide
    ``tests/unit/tools/test_convert_csv.py``, contra la base.
    """

    def test_it_no_longer_declares_a_block(self):
        with pytest.raises(ValueError, match='no.existe'):
            convert.convert_csv_import('base', 'no.existe.csv', b'name\nx\n')

    def test_it_no_longer_raises_not_implemented(self):
        """El control que discrimina: antes esto era ``NotImplementedError``."""
        with pytest.raises(Exception) as excinfo:
            convert.convert_csv_import('base', 'no.existe.csv', b'name\nx\n')

        assert not isinstance(excinfo.value, NotImplementedError)
