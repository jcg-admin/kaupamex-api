"""``_slug`` / ``_unslug`` / ``_unslug_url`` — la composición del slug legible.

Los casos miden **conducta** —el texto que entra y el que sale— y no que se
llame a un símbolo concreto: un caso que sólo afirmara «llama a ``slugify``»
pasaría con una implementación que la llamara y tirara el resultado
(``metrica-decide-la-conclusion.md``, sub-patrón D).

Cada clase declara qué haría fallar a sus casos. La medición de esa
declaración —anular la rama y ver caer exactamente los casos que dependen de
ella— está en ``scripts/evidence/neutering-http-routing-*.txt``.
"""
import pytest

from addons.base.models.ir_http import IrHttp


class _Record:
    """El mínimo que ``_slug`` lee de un registro: ``pk`` y ``display_name``.

    Un doble y no un modelo real: ``_slug`` no toca la base, y un modelo real
    obligaría a la marca de base de datos para medir una función pura.
    """

    def __init__(self, pk, display_name):
        self.pk = pk
        self.display_name = display_name


class TestTheNameIsCarriedIntoTheSlug:
    """Falla si ``_slug`` devolviera sólo el id — el ``base.slug`` de siempre."""

    def test_a_record_gives_name_then_id(self):
        assert IrHttp._slug(_Record(42, 'Silla de Oficina')) == 'silla-de-oficina-42'

    def test_a_name_search_tuple_gives_the_same(self):
        # ≙ el ``except AttributeError`` de la fuente: la tupla (id, nombre).
        assert IrHttp._slug((42, 'Silla de Oficina')) == 'silla-de-oficina-42'

    def test_it_is_not_just_the_id(self):
        # Discrimina contra ``base.slug``, que devuelve str(id) y pasaría
        # todos los casos de la clase de abajo.
        assert IrHttp._slug(_Record(42, 'Silla')) != '42'


class TestNonAsciiSurvives:
    """Falla si el ``slugify`` fuera el de Django (``allow_unicode=False``)."""

    @pytest.mark.parametrize('name,expected', [
        ('手工皂', '手工皂-42'),
        ('صابون يدوي', 'صابون-يدوي-42'),
        ('Café Orgánico', 'cafe-organico-42'),
        ('Ñandú_edición 2026', 'nandu-edicion-2026-42'),
    ])
    def test_the_script_is_kept_and_the_accent_is_stripped(self, name, expected):
        assert IrHttp._slug(_Record(42, name)) == expected


class TestTheEmptySlugBranch:
    """``if not slugname: return str(identifier)`` — sin el guion suelto."""

    @pytest.mark.parametrize('name', ['!!!', '---', '   ', '### $$$', ''])
    def test_a_name_without_word_characters_gives_only_the_id(self, name):
        assert IrHttp._slug(_Record(42, name)) == '42'

    def test_none_is_treated_as_the_empty_name(self):
        assert IrHttp._slug(_Record(42, None)) == '42'


class TestTheNonExistentRecordRaises:
    """``if not identifier: raise ValueError`` — la guarda de la fuente."""

    @pytest.mark.parametrize('identifier', [None, 0, False])
    def test_a_record_without_id_cannot_be_slugged(self, identifier):
        with pytest.raises(ValueError, match='Cannot slug non-existent record'):
            IrHttp._slug(_Record(identifier, 'Silla'))


class TestUnslugIsTheInverse:
    """Falla si ``_unslug`` devolviera el entero pelado o perdiera el nombre."""

    @pytest.mark.parametrize('name', [
        'Silla de Oficina', '手工皂', 'Café Orgánico', 'A', 'ab',
    ])
    def test_round_trip_recovers_the_identifier(self, name):
        slug = IrHttp._slug(_Record(7, name))
        assert IrHttp._unslug(slug)[1] == 7

    def test_it_returns_a_two_tuple_with_the_readable_part(self):
        assert IrHttp._unslug('silla-de-oficina-42') == ('silla-de-oficina', 42)

    def test_a_bare_identifier_has_no_readable_part(self):
        assert IrHttp._unslug('42') == (None, 42)

    @pytest.mark.parametrize('value', ['sin-numero', '', 'abc'])
    def test_what_is_not_a_slug_gives_two_nones(self, value):
        assert IrHttp._unslug(value) == (None, None)

    def test_the_shape_is_always_a_pair(self):
        # Discrimina: devolver sólo el entero rompería a quien desempaqueta.
        readable, identifier = IrHttp._unslug('x-1')
        assert (readable, identifier) == ('x', 1)

    def test_a_negative_identifier_is_accepted(self):
        # El patrón admite ``-?\\d+`` — es lo que obliga al ``abs()`` del
        # convertidor.
        assert IrHttp._unslug('cosa--3') == ('cosa', -3)


class TestUnslugUrl:
    """``/blog/mi-super-blog-1`` a ``/blog/1`` — sólo el último segmento."""

    def test_the_last_segment_is_reduced_to_its_identifier(self):
        assert IrHttp._unslug_url('/blog/mi-super-blog-1') == '/blog/1'

    def test_a_url_without_a_slug_is_returned_unchanged(self):
        assert IrHttp._unslug_url('/blog/sin-numero') == '/blog/sin-numero'

    def test_earlier_segments_are_left_alone(self):
        # Discrimina contra una implementación que unslugueara toda la ruta.
        assert IrHttp._unslug_url('/mi-blog-9/entrada-1') == '/mi-blog-9/1'
