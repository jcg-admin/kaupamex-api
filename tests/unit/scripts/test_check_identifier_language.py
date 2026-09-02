"""Control de la familia de códigos de ``check_identifier_language.py``.

El gate lee ``de`` como preposición española, y en ``check_vat_de`` es el
ISO-3166 de Alemania. El riesgo del arreglo no es dejar pasar ese nombre: es
**absolver de más** — que un identificador español de verdad deje de contar
porque su cola tiene dos letras. Por eso los casos miden las dos direcciones.
"""
import ast
import importlib.util
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def gate():
    ruta = RAIZ / 'scripts' / 'check_identifier_language.py'
    spec = importlib.util.spec_from_file_location('cil', ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


#: La familia real de ``base_vat``: el despachador de la fuente resuelve
#: ``'check_vat_' + cc.lower()``, así que el nombre es su contrato.
FAMILIA_VAT = ['check_vat_de', 'check_vat_mx', 'check_vat_cl', 'check_vat_ie']


class TestATwoLetterTailNeedsItsFamilyToBeExcused:

    def test_alone_it_still_counts_as_a_preposition(self, gate):
        """Sin hermanos no hay evidencia de código: el gate lo marca."""
        assert gate.spanish_words_in('check_vat_de') == ['de']

    def test_with_its_family_it_is_a_country_code(self, gate):
        familias = gate.code_suffix_families(FAMILIA_VAT)
        assert 'check_vat' in familias
        assert gate.spanish_words_in('check_vat_de', familias) == []

    def test_two_siblings_are_not_enough(self, gate):
        """El umbral es tres: dos colas distintas pueden ser coincidencia."""
        assert gate.code_suffix_families(['check_vat_de', 'check_vat_mx']) == set()

    def test_the_family_does_not_excuse_another_prefix(self, gate):
        """La exencion es del prefijo que TIENE familia, no de la cola suelta.

        ``orden`` ademas esta en el lexico, asi que sale con ``de``: el caso
        comprueba que la particula sigue contando, no que sea el unico hit.
        """
        familias = gate.code_suffix_families(FAMILIA_VAT)
        assert gate.spanish_words_in('orden_de', familias) == ['de', 'orden']
        assert gate.spanish_words_in('lista_en', familias) == ['en']


class TestRealSpanishSurvivesTheExemption:
    """Control positivo: el gate tiene que poder fallar.

    Si estos dejaran de marcarse, el arreglo habría convertido el gate en un
    adorno — un verde que no distingue «no hay español» de «no lo puedo ver».
    """

    @pytest.mark.parametrize('nombre, esperado', [
        ('devuelve_el_valor', ['devuelve', 'el', 'valor']),
        ('nombre_del_campo', ['campo', 'del', 'nombre']),
        ('crea_una_orden', ['crea', 'orden', 'una']),
        ('validacion_de_precio', ['de', 'precio', 'validacion']),
    ])
    def test_a_spanish_identifier_is_still_flagged(self, gate, nombre, esperado):
        familias = gate.code_suffix_families(FAMILIA_VAT)
        assert gate.spanish_words_in(nombre, familias) == esperado


class TestTheExemptionIsMeasuredAgainstTheWholeTree:

    def test_it_absolves_exactly_one_identifier(self, gate):
        """Medido sobre 2510 archivos: el arreglo suelta uno y sólo uno.

        La cifra del árbol cambia con cada pase, así que lo que este caso fija
        no es el 2510 sino la FORMA: el conjunto de absueltos es exactamente
        ``check_vat_de``. Si algún día suelta otro, el caso lo nombra.
        """
        absueltos = []
        for ruta in gate.collect([]):
            if 'migrations' in ruta.parts:
                continue
            try:
                arbol = ast.parse(ruta.read_text(encoding='utf-8'))
            except (SyntaxError, UnicodeDecodeError):
                continue
            declarados = list(gate.declared_identifiers(arbol))
            familias = gate.code_suffix_families(n for n, _ in declarados)
            if not familias:
                continue
            for nombre, _ in declarados:
                if gate.spanish_words_in(nombre) and not gate.spanish_words_in(
                        nombre, familias):
                    absueltos.append(nombre)
        assert absueltos == ['check_vat_de'], absueltos
