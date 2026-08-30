r"""El corte de capas de los 21 conversores, ratificado con la referencia al lado.

Directiva del ejecutor 2026-08-30: cerrar las piezas que quedan del desmontaje
de QWeb con el criterio de las dos categorías —*el stack lo trae hecho* frente
a *el stack tiene con qué construirlo*—. Pieza 4 de 8.

:ref:`h-api-932` midió que los conversores no declaraban ``_name``;
:ref:`h-api-933` midió que el análisis proponía formatear en el servidor con
Django mientras el código delegaba al cliente, **sin que ninguno de los dos
dijera cuál regía**. Este archivo cierra las dos mitades:

1. los 21 declaran su ``_name``, y es el de la referencia verbatim;
2. el corte de capas rige el del **código**, y su razón es medible: la
   referencia emite marcado donde nosotros entregamos el valor, porque allá el
   servidor renderiza su propia vista y aquí el API alimenta a ``ui``.

La delegación es **elección, no incapacidad**: que Django traiga
``formats``/``timesince`` lo mide ``test_stack_inventory_without_qweb.py``, que
por eso clasifica el «formateo por locale» como TRAE. Sin ese control, un caso
que sólo comprobara la delegación no distinguiría «se eligió» de «no había con
qué» — el sub-patrón D de ``metrica-decide-la-conclusion.md``.

*Métrica:* el ``_name`` declarado por cada clase, y la **salida real** de
``value_to_html`` al invocarlo, no el texto de su cuerpo.
*Ciega a:* si el formateo que hace ``ui`` coincide con el de la fuente para una
locale dada — eso se mide en ``ui``, no aquí; y a los conversores cuyo contrato
exige una fila de base de datos, que este archivo no construye.
"""
import datetime

import pytest

from addons.base.models import ir_field_converters as conv

#: Los 21 del archivo, con el ``_name`` que la referencia declara. El prefijo
#: ``ir.qweb.field`` se porta **verbatim** aunque este árbol no tenga ese
#: intérprete: es el nombre del modelo en la fuente, y
#: ``atributos-de-clase-de-modelo.md`` manda portarlo tal cual. Es otro eje que
#: el de la pieza 5, donde lo que se renombró fue un **valor de dato**
#: (``view.type``), no el nombre de un modelo.
EXPECTED_NAMES = {
    'IrFieldConverter': 'ir.qweb.field',
    'IrFieldConverterInteger': 'ir.qweb.field.integer',
    'IrFieldConverterFloat': 'ir.qweb.field.float',
    'IrFieldConverterDate': 'ir.qweb.field.date',
    'IrFieldConverterDatetime': 'ir.qweb.field.datetime',
    'IrFieldConverterText': 'ir.qweb.field.text',
    'IrFieldConverterSelection': 'ir.qweb.field.selection',
    'IrFieldConverterMany2one': 'ir.qweb.field.many2one',
    'IrFieldConverterMany2many': 'ir.qweb.field.many2many',
    'IrFieldConverterOne2many': 'ir.qweb.field.one2many',
    'IrFieldConverterHtml': 'ir.qweb.field.html',
    'IrFieldConverterImage': 'ir.qweb.field.image',
    'IrFieldConverterImage_Url': 'ir.qweb.field.image_url',
    'IrFieldConverterMonetary': 'ir.qweb.field.monetary',
    'IrFieldConverterFloat_Time': 'ir.qweb.field.float_time',
    'IrFieldConverterTime': 'ir.qweb.field.time',
    'IrFieldConverterDuration': 'ir.qweb.field.duration',
    'IrFieldConverterRelative': 'ir.qweb.field.relative',
    'IrFieldConverterBarcode': 'ir.qweb.field.barcode',
    'IrFieldConverterContact': 'ir.qweb.field.contact',
    'IrFieldConverterTemplate': 'ir.qweb.field.qweb',
}

#: Los que **no** resuelven aquí, con la palabra que su razón declara. Ninguno
#: calla: el contrato observable es un ``NotImplementedError`` que dice por qué.
#:
#: ``IrFieldConverterMonetary`` **salió de esta tabla** en la tarea #197: su
#: razón —la ausencia de ``babel``— resultó cubrir sólo la mitad de su caso, y
#: el camino del papel no tiene cliente a quien delegar. Ver :ref:`h-api-940`.
DELEGATED = {
    'IrFieldConverterRelative': 'cliente',
    'IrFieldConverterBarcode': 'dependencias',
    'IrFieldConverterImage': None,
    'IrFieldConverterTemplate': None,
}


class TestTheTwentyOneDeclareTheirName:
    """Mitad 1 de la pieza: :ref:`h-api-932`."""

    def test_none_is_missing_its_name(self):
        missing = [c for c in EXPECTED_NAMES if not getattr(conv, c)._name]
        assert missing == []

    def test_each_name_is_the_one_of_the_reference(self):
        for class_name, expected in EXPECTED_NAMES.items():
            assert getattr(conv, class_name)._name == expected, class_name

    def test_the_name_keeps_the_prefix_the_view_type_dropped(self):
        # El control que separa los dos ejes. La pieza 5 quitó ``qweb`` de un
        # **valor de dato**, porque escribirlo afirmaba un sustrato ausente.
        # El ``_name`` es otra cosa: es el identificador del modelo en la
        # fuente, y portarlo verbatim es lo que permite que ``ir.model`` y la
        # extensión por nombre apunten al mismo sitio que allá.
        assert conv.IrFieldConverter._name == 'ir.qweb.field'
        assert conv.IrFieldConverterTemplate._name == 'ir.qweb.field.qweb'


class TestWhatThisTreeResolvesInTheServer:
    """El API entrega el **valor**; ninguno compone presentación por locale."""

    def test_a_date_comes_out_in_iso_not_in_a_locale_pattern(self):
        assert conv.IrFieldConverterDate.value_to_html(
            datetime.date(2026, 1, 2)) == '2026-01-02'

    def test_a_datetime_comes_out_in_utc_and_the_zone_is_the_clients(self):
        # La fuente convierte a la zona del usuario con ``babel``; aquí el
        # valor viaja en UTC y la zona la aplica quien sabe cuál es.
        assert conv.IrFieldConverterDatetime.value_to_html(
            datetime.datetime(2026, 1, 2, 3, 4, 5)) == '2026-01-02T03:04:05'

    def test_the_numeric_ones_come_out_formatted_without_any_markup(self):
        for converter, sample, expected in (
            (conv.IrFieldConverterInteger, 1234, '1,234'),
            (conv.IrFieldConverterFloat, 1234.5, '1,234.50'),
            (conv.IrFieldConverterFloat_Time, 1.5, '01:30'),
        ):
            out = converter.value_to_html(sample)
            assert out == expected
            assert '<span' not in out and 'class=' not in out

    def test_the_relational_ones_join_names_without_markup(self):
        assert conv.IrFieldConverterMany2many.value_to_html(['a', 'b']) == 'a, b'
        # ``one2many`` hereda de ``many2many``, y eso es fiel: en la fuente los
        # dos cuerpos son el mismo texto — repetido allá porque sus dos clases
        # derivan de ``AbstractModel`` y no pueden heredar una de la otra.
        assert conv.IrFieldConverterOne2many.value_to_html(['a', 'b']) == 'a, b'


class TestTheOnesThatDoNotResolveSayWhy:
    """Delegar sin decirlo sería un hueco; con la razón escrita es un corte."""

    @pytest.mark.parametrize('class_name', sorted(DELEGATED))
    def test_it_refuses_instead_of_returning_something_wrong(self, class_name):
        with pytest.raises(NotImplementedError):
            getattr(conv, class_name).value_to_html('x')

    @pytest.mark.parametrize(
        'class_name, word',
        sorted((c, w) for c, w in DELEGATED.items() if w))
    def test_and_the_refusal_names_the_layer_that_does_resolve_it(
            self, class_name, word):
        with pytest.raises(NotImplementedError) as excinfo:
            getattr(conv, class_name).value_to_html('x')
        assert word in str(excinfo.value).lower(), class_name

    def test_the_calculable_half_of_relative_is_ported_anyway(self):
        # Delegar la **frase** no es delegar el cálculo: lo que depende del
        # idioma se va, lo que no, se queda.
        ahora = datetime.datetime(2026, 1, 2, 0, 0, 0)
        antes = datetime.datetime(2026, 1, 1, 0, 0, 0)
        assert conv.IrFieldConverterRelative.delta_seconds(antes, ahora) == -86400


class TestTheMarkupIsWhereTheReferenceDiffersFromUs:
    """El eje que ratifica el corte, y el control que puede fallar."""

    #: Medido sobre ``odoo19c: odoo/addons/base/models/ir_qweb_fields.py``:
    #: seis conversores emiten marcado allá (``Markup``/``<span>``/``<img>``);
    #: aquí sólo uno. Los cinco de diferencia son ``Barcode``, ``Contact``,
    #: ``Html``, ``Image`` y ``Monetary``.
    ONLY_ONE_EMITS_MARKUP = 'IrFieldConverterImage_Url'

    def test_the_url_image_is_the_only_one_that_adds_a_tag(self):
        assert conv.IrFieldConverterImage_Url.value_to_html('/x.png') == (
            '<img src="/x.png">')

    def test_contact_escapes_instead_of_composing_the_card(self):
        # Allá ``contact`` compone una tarjeta con ``<div>``; aquí el valor
        # sale escapado y la tarjeta la arma ``ui``.
        out = conv.IrFieldConverterContact.value_to_html({'name': 'X'})
        assert '<div' not in out and '&#x27;' in out

    def test_no_resolver_composes_a_styled_span(self):
        # El control que discrimina: si alguien reintroduce presentación por
        # locale en el servidor —el ``<span class="oe_currency_value">`` de la
        # fuente es el caso canónico— este caso cae. Un test que sólo mirara
        # los delegados no lo vería: el riesgo está en los que SÍ resuelven.
        for class_name in EXPECTED_NAMES:
            if class_name in DELEGATED:
                continue
            converter = getattr(conv, class_name)
            for sample in (1234.5, 'texto', ['a'], datetime.date(2026, 1, 2)):
                try:
                    out = converter.value_to_html(sample)
                except Exception:
                    continue
                assert 'class=' not in str(out), (class_name, out)
                assert '<span' not in str(out), (class_name, out)
