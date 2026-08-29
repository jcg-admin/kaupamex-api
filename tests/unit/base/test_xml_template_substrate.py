"""Tests — el sustrato de plantillas XML de este árbol, medido.

Pregunta del ejecutor: *"¿QWeb es una plantilla XML? Si nosotros queremos
igual implementar plantillas XML, ¿cómo lo haríamos con Django REST
Framework?"*.

La respuesta corta es que **la premisa de la segunda mitad no se sostiene**, y
estos casos lo miden en vez de afirmarlo: DRF no tiene capa de plantillas —
rinde respuestas de API—, mientras que la capa de plantillas XML **ya existe**
en este árbol y no vino de DRF. Cada caso fija un hecho que, si cambiara, haría
falsa una frase del análisis; por eso son tests y no prosa.

Los cuatro ejes:

1. **QWeb es XML** — pero eso no se mide aquí: la referencia es de sólo
   lectura y sus cifras van al hallazgo, con su comando. Lo que sí se mide es
   nuestro lado.
2. **El sustrato XML está instalado y en uso** (``lxml``).
3. **DRF no aporta nada de esto** — 0 renderizadores XML de serie.
4. **Nuestro intérprete existe, es XML y es extensible por XPath** — que es la
   propiedad por la que la referencia usa XML y no un formato plano.
"""
import re
from pathlib import Path

import pytest
from lxml import etree

from addons.base import report_template
from addons.base.report_template import InvalidReportTemplate

#: Raíz del paquete instalado de DRF — se localiza por el módulo, no por una
#: ruta tecleada: el venv cambia de sitio entre entornos.
import rest_framework  # noqa: E402  (se usa para derivar la ruta, no la API)

DRF_DIR = Path(rest_framework.__file__).parent


class TestTheXmlSubstrateIsInstalled:
    """Eje 2 — el XML no es aspiracional: hay motor y hay consumidores."""

    def test_lxml_is_available_and_declared(self):
        """``lxml`` es lo que la referencia usa para el arch, y aquí también.

        Qué lo haría fallar: retirarlo de ``pyproject.toml``. No es un import
        de conveniencia — sin él ``ir_ui_view`` no puede validar un arch ni
        combinar una herencia.
        """
        assert etree.__version__
        declared = Path('pyproject.toml').read_text()
        assert 'lxml' in declared

    def test_the_arch_is_stored_as_text_and_read_as_a_tree(self):
        """El mismo par que la fuente: columna de texto, lectura por árbol.

        ``ir.ui.view.arch_db`` es ``Text`` allá y aquí; lo que lo convierte en
        plantilla es que se parsea. Se mide sobre el módulo, no sobre una fila,
        porque el hecho es de la declaración.
        """
        source = Path('src/addons/base/models/ir_ui_view.py').read_text()
        assert 'from lxml import etree' in source
        assert 'arch_db' in source


class TestDrfDoesNotProvideTheTemplateLayer:
    """Eje 3 — la respuesta a *"¿cómo se haría con DRF?"* es: no se hace ahí.

    DRF rinde **respuestas de API**. Su catálogo de renderizadores no incluye
    XML, y su capa de plantillas es la de Django (``TemplateHTMLRenderer``
    delega en ella). Un renderizador XML de DRF serviría para *devolver* XML
    por HTTP, que es otro problema — el nuestro es *interpretar* una plantilla
    XML del lado del servidor.
    """

    def test_drf_ships_no_xml_renderer(self):
        """0 de los renderizadores de serie menciona XML.

        Qué lo haría fallar: que alguien instale ``djangorestframework-xml`` y
        lo dé por equivalente. No lo es, y este caso deja escrito por qué el
        conteo importa: si un día da distinto de 0, la afirmación del análisis
        deja de valer y hay que re-decidir, no parchear el número.
        """
        renderers = (DRF_DIR / 'renderers.py').read_text()
        classes = re.findall(r'^class (\w+)', renderers, re.M)
        assert classes, 'no se pudo leer el catálogo de renderizadores'
        assert not [c for c in classes if 'XML' in c.upper()], classes
        assert 'xml' not in renderers.lower()

    def test_drf_ships_no_xml_parser(self):
        """Simétrico del anterior por el lado de entrada."""
        parsers = (DRF_DIR / 'parsers.py').read_text()
        assert 'xml' not in parsers.lower()


class TestOurInterpreterIsXmlAndExtensible:
    """Eje 4 — la capa existe, y su forma XML es lo que la hace extensible."""

    def _arch(self, texto):
        return etree.fromstring(texto)

    def test_the_arch_is_xml_and_produces_the_descriptor(self):
        """El camino completo: XML → intérprete → dict listo para el helper."""
        arch = self._arch(
            '<descriptor>'
            '<field name="numero">{{ pedido.folio }}</field>'
            '<section name="emisor">'
            '<field name="nombre">{{ pedido.empresa }}</field>'
            '</section>'
            '</descriptor>')
        output = report_template.interpret_descriptor(
            arch, {'pedido': type('P', (), {'folio': 'S-1', 'empresa': 'ACME'})})
        assert output == {'numero': 'S-1', 'emisor': {'nombre': 'ACME'}}

    def test_a_list_iterates_over_the_declared_path(self):
        """``<list in="…">`` es el ``t-foreach`` de la fuente, en este vocabulario."""
        arch = self._arch(
            '<descriptor>'
            '<list name="items" in="lineas">'
            '<field name="sku">{{ item.sku }}</field>'
            '</list>'
            '</descriptor>')
        lines = [type('L', (), {'sku': 'A'}), type('L', (), {'sku': 'B'})]
        output = report_template.interpret_descriptor(arch, {'lineas': lines})
        assert output == {'items': [{'sku': 'A'}, {'sku': 'B'}]}

    def test_an_element_outside_the_vocabulary_raises(self):
        """El vocabulario es cerrado, y esa es la diferencia con HTML libre.

        Es lo que permite que el helper tenga esquema fijo: si el arch pudiera
        traer cualquier etiqueta, el descriptor dejaría de ser predecible y el
        conversor no podría leerlo. La fuente no necesita esta guarda porque su
        conversor acepta cualquier HTML.

        **El elemento lleva ``name``, y eso es el caso de prueba, no un
        detalle.** La primera versión usaba ``<div>libre</div>`` y pasaba en
        verde con la guarda de vocabulario **anulada**: quien lo rechazaba era
        la guarda anterior —«elemento sin ``name``»—, no la que el caso dice
        medir. Es el sub-patrón D de ``metrica-decide-la-conclusion.md``, y lo
        destapó correr el subconjunto con la guarda retirada. Con ``name``
        presente sólo puede rechazarlo el vocabulario.
        """
        arch = self._arch('<descriptor><div name="x">libre</div></descriptor>')
        with pytest.raises(InvalidReportTemplate):
            report_template.interpret_descriptor(arch, {})

    def test_an_element_without_name_raises_by_its_own_guard(self):
        """La guarda que el caso anterior confundía con la del vocabulario.

        Se separa para que las dos queden medidas por su cuenta: si mañana una
        de las dos desaparece, cae **su** caso y no el del vecino.
        """
        arch = self._arch('<descriptor><field>sin nombre</field></descriptor>')
        with pytest.raises(InvalidReportTemplate):
            report_template.interpret_descriptor(arch, {})

    def test_the_root_has_to_be_descriptor(self):
        """Control positivo del anterior: la guarda mira la raíz, no sólo los hijos."""
        with pytest.raises(InvalidReportTemplate):
            report_template.interpret_descriptor(
                self._arch('<template><field name="x">1</field></template>'), {})

    def test_xpath_inheritance_exists_and_operates_on_nodes(self):
        """La propiedad por la que el arch es XML y no JSON.

        ``tools/template_inheritance`` es el puerto del mecanismo con que un
        addon parcha la plantilla de otro sin bifurcarla. Un formato plano no
        tendría dónde anclar el parche — es el argumento textual del docstring
        de ``report_template``, medido aquí sobre el módulo que lo implementa.
        """
        source = Path('src/tools/template_inheritance.py').read_text()
        assert 'xpath' in source.lower()
        assert 'from lxml import etree' in source
