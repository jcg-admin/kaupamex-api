r"""Inventario del stack para quitar QWeb, con el criterio de las dos categorías.

Directiva del ejecutor 2026-08-30: aplicar a las cuatro piezas abiertas el
criterio que abrió ``test_native_substrate_for_the_three_pieces.py``,
*"considerando django, Django REST Framework, PostgreSQL, gunicorn, libharu,
cpython, lxml, etc"*.

Las dos categorías, y la frontera entre ellas es lo que este archivo mide:

- **TRAE** — hay un símbolo instalado y basta llamarlo. El trabajo es cablear.
- **CONSTRUYE** — no hay símbolo hecho, pero las primitivas están y no hace
  falta ninguna dependencia de fuera. El trabajo es escribirlo.

Hay un tercer desenlace que NO es ninguna de las dos y se declara aparte:
**EXCLUIDO** — el stack traía la pieza y el proyecto la rechazó por decisión
(``pypdf`` frente al motor propio de libharu, ADR-017). Confundirlo con
«construir» borraría que hubo una elección.

*Métrica:* la presencia y la conducta del símbolo en el binario instalado de
cada componente, ejercida sobre el material que la pieza correspondiente
necesita.
*Ciega a:* el rendimiento de cada mecanismo; y a si el componente cubre todos
los casos de borde de su pieza — mide que existe y que hace lo que la tabla
dice.
"""
import dis
import io
import pathlib
import subprocess
import sys
from opcode import opmap

import django
import gunicorn
import lxml.etree as etree
import pytest
import rest_framework
from rest_framework.response import Response
from django.db import connection
from django.template import Context, Engine
from django.utils import formats

import tools.safe_eval as safe_eval_module
from addons.base.models.ir_ui_view import IrUiView
from addons.base.report_template import interpret_descriptor
from tools import template_inheritance
from tools.pdf import PdfFileReader

#: El inventario que este archivo prueba. La columna que importa es la
#: tercera: dice qué clase de trabajo queda por hacer.
INVENTORY = {
    ('cpython', 'contención por bytecode'): 'CONSTRUYE',
    ('django', 'evaluación y control de flujo'): 'TRAE',
    ('django', 'almacén del arch por key'): 'TRAE',
    ('django', 'formateo por locale'): 'TRAE',
    ('django', 'recorrido del árbol a dict'): 'CONSTRUYE',
    ('drf', 'contrato del endpoint'): 'TRAE',
    ('lxml', 'parseo, XPath y construcción de nodos'): 'TRAE',
    ('lxml', 'herencia entre vistas por XPath'): 'CONSTRUYE',
    ('postgresql', 'guardar y consultar el arch'): 'TRAE',
    ('gunicorn', 'servir el documento'): 'TRAE',
    ('libharu', 'emitir el PDF'): 'CONSTRUYE',
    ('libharu', 'leer y fusionar el PDF'): 'CONSTRUYE',
    ('pypdf', 'leer y fusionar el PDF'): 'EXCLUIDO',
}


class TestTheInventoryIsWhatTheCasesMeasure:
    """El control que impide que la tabla y las pruebas divergan."""

    def test_every_category_is_one_of_the_three(self):
        assert set(INVENTORY.values()) == {'TRAE', 'CONSTRUYE', 'EXCLUIDO'}

    def test_the_split_is_the_one_the_analysis_publishes(self):
        counts = {v: sum(1 for x in INVENTORY.values() if x == v)
                  for v in set(INVENTORY.values())}
        assert counts == {'TRAE': 7, 'CONSTRUYE': 5, 'EXCLUIDO': 1}, counts


class TestWhatCPythonBrings:
    """La contención NO viene hecha: se compone de tres módulos de stdlib."""

    def test_no_installed_symbol_refuses_an_expression_by_opcode(self):
        # `compile` compila cualquier cosa válida; `dis` la lee; `opcode` da el
        # mapa. Ninguno de los tres decide qué se permite — eso lo escribe uno.
        #
        # Medido, no supuesto: en 3.12 `__import__("os")` NO emite
        # `IMPORT_NAME` —ése es del *statement* `import`— sino `LOAD_NAME` +
        # `CALL`, que son opcodes de aspecto inocente. Por eso la contención
        # no puede ser una lista de opcodes «peligrosos»: es un allowlist.
        code = compile('__import__("os").system("x")', '<x>', 'eval')
        emitidos = {i.opname for i in dis.get_instructions(code)}
        assert 'CALL' in emitidos and 'LOAD_NAME' in emitidos
        assert 'IMPORT_NAME' not in emitidos

    def test_the_allowlist_is_ours_and_it_refuses_that(self):
        # Y lo refuta la guarda de nombres, que es la BARRERA EXTERNA de las
        # dos: `assert_no_dunder_name` corre antes que la de opcodes, así que
        # el error es `NameError` y no `ValueError`. Las dos son nuestras.
        with pytest.raises(NameError, match='__import__'):
            safe_eval_module.safe_eval('__import__("os").system("x")', {})

    def test_and_the_opcode_barrier_discriminates_by_tier(self):
        # La segunda barrera es el allowlist, y NO es una sola: son tres
        # niveles con distinta anchura. `safe_eval` es el más ancho —admite
        # llamada y comprensión—, así que medirlo a él haría pasar el caso sin
        # que el allowlist decidiera nada: el sub-patrón D.
        #
        # El nivel que un descriptor necesita es `expr_eval`, y ahí el
        # allowlist SÍ rechaza: una llamada emite `CALL`, que no está.
        assert safe_eval_module.expr_eval('1 + 1') == 2
        with pytest.raises(ValueError, match='forbidden opcode'):
            safe_eval_module.expr_eval('f(1)')

    def test_the_narrowest_tier_refuses_even_arithmetic_free_iteration(self):
        # Y `const_eval`, el más estrecho, rechaza además la comprensión —
        # `GET_ITER` no está en su conjunto. Los tres niveles son nuestros:
        # cpython no trae ninguno.
        assert safe_eval_module.const_eval('[1, 2]') == [1, 2]
        with pytest.raises(ValueError, match='forbidden opcode'):
            safe_eval_module.const_eval('[x for x in (1, 2)]')

    def test_the_opcode_map_is_the_one_of_the_running_interpreter(self):
        # Lo que hace la contención portable entre versiones: los nombres se
        # resuelven contra `opmap` del intérprete que corre, no contra una
        # tabla congelada. Ver `test_safe_eval_across_cpython_versions.py`.
        assert list(safe_eval_module.to_opcodes(['RETURN_VALUE'])) == [opmap['RETURN_VALUE']]
        assert list(safe_eval_module.to_opcodes(['NO_EXISTE_ESTE_OPCODE'])) == []


class TestWhatDjangoBrings:

    def test_dtl_evaluates_and_controls_flow(self):
        out = Engine(autoescape=False).from_string(
            '{% if n %}{% for r in rows %}{{ r }}{% endfor %}{% endif %}'
        ).render(Context({'n': 1, 'rows': [1, 2]}))
        assert out == '12'

    def test_the_orm_stores_and_finds_the_arch_by_key(self):
        assert IrUiView._meta.get_field('key') is not None
        assert IrUiView._meta.get_field('arch_db') is not None

    def test_locale_formatting_is_installed_even_though_the_api_delegates_it(self):
        # TRAE, y el corte de capas lo delega al cliente igualmente (DEC-FW-05):
        # que esté disponible es lo que hace de la delegación una elección.
        assert formats.number_format(1234.5, decimal_pos=2) in ('1234.50', '1,234.50')

    def test_walking_a_tree_into_a_dict_is_not_something_django_brings(self):
        # CONSTRUYE: DTL produce una CADENA. Que un nodo del árbol se omita del
        # dict resultante no es una operación que un motor de texto exponga.
        rendered = Engine(autoescape=False).from_string('{{ a }}').render(
            Context({'a': 1}))
        assert isinstance(rendered, str)
        assert isinstance(interpret_descriptor(
            etree.fromstring('<descriptor/>'), {}), dict)


class TestWhatDRFBrings:

    def test_the_response_contract_is_installed(self):
        assert Response({'a': 1}).data == {'a': 1}
        assert rest_framework.VERSION


class TestWhatLxmlBrings:

    def test_parsing_xpath_and_node_construction(self):
        doc = etree.fromstring('<doc><line price="10.5"/></doc>')
        assert doc.xpath('string(/doc/line/@price)') == '10.5'
        node = etree.Element('linea')
        node.set('importe', '21.00')
        assert etree.tostring(node) == b'<linea importe="21.00"/>'

    def test_inheritance_between_views_is_built_on_top_of_it(self):
        # CONSTRUYE: lxml da el XPath; aplicar un parche de una vista sobre
        # otra —`position="after"`, `replace`, `attributes`— es nuestro.
        assert hasattr(template_inheritance, 'apply_inheritance_specs')


class TestWhatPostgreSQLBrings:
    """El almacén, y una capacidad que el árbol NO usa: XML nativo."""

    @pytest.mark.django_db
    def test_it_brings_an_xml_type_with_xpath(self):
        with connection.cursor() as cur:
            cur.execute("select xpath('/a/b/text()', '<a><b>hola</b></a>'::xml)::text")
            assert cur.fetchone()[0] == '{hola}'

    @pytest.mark.django_db
    def test_and_the_arch_is_stored_as_text_not_as_xml(self):
        # La divergencia declarada: el `arch_db` es texto, como en la fuente.
        # Guardarlo como `xml` daría validación y `xpath()` en el motor, y
        # costaría que el `arch` inválido dejara de poder guardarse —que es
        # justo lo que el asistente de vistas necesita poder hacer—.
        assert IrUiView._meta.get_field('arch_db').get_internal_type() == 'TextField'


class TestWhatGunicornBrings:

    def test_it_is_installed_and_it_is_the_server_of_record(self):
        # TRAE: el WSGI que sirve el documento. La fuente usa Werkzeug, que es
        # la exclusión declarada del stack.
        assert gunicorn.__version__
        assert 'werkzeug' not in sys.modules


class TestWhatLibharuBrings:
    """El motor de PDF es NUESTRO, construido sobre la biblioteca."""

    HELPERS = pathlib.Path(__file__).resolve().parents[3] / 'src' / 'tools' / 'pdf'

    def test_the_library_is_vendored_and_the_helpers_are_ours(self):
        assert (self.HELPERS / 'vendor' / 'libharu').is_dir()
        assert (self.HELPERS / 'pdf_report.c').is_file()
        assert (self.HELPERS / 'pdf_receipt.c').is_file()

    def test_the_reader_is_built_here_because_pypdf_is_excluded(self):
        # EXCLUIDO, no ausente: la fuente envuelve `pypdf`, y el proyecto lo
        # rechaza por tener motor propio. Excluida la biblioteca, el lector se
        # construye — es la postura de `porte-completo-no-parcial`.
        assert PdfFileReader is not None
        with pytest.raises(Exception):
            PdfFileReader(io.BytesIO(b'no soy un pdf')).getNumPages()

    def test_pypdf_is_not_installed_and_that_is_the_decision(self):
        with pytest.raises(ImportError):
            __import__('pypdf')


class TestTheVersionsAreTheOnesMeasured:
    """Toda cifra de este archivo cuelga de estas versiones."""

    def test_the_stack_versions_are_declared(self):
        assert django.get_version().startswith('6.')
        assert etree.LIBXML_VERSION >= (2, 9)
        assert sys.version_info >= (3, 12)

    @pytest.mark.django_db
    def test_the_database_is_postgresql(self):
        assert connection.vendor == 'postgresql'
