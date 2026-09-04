"""El slug del producto sale del ``slugify`` portado, no del de Django.

``ProductListSerializer.get_slug`` decía en su docstring «≙ ``ir.http._slug``»
y usaba ``django.utils.text.slugify``, que **no** es lo que ese símbolo hace.
Medido sobre siete nombres, los dos algoritmos divergen en cinco; en tres el
de Django devuelve cadena vacía y la URL del producto queda en ``-42``:

    ハンドメイド 石鹸  django ''  ·  portado 'ハントメイト-石鹸'
    手工皂             django ''  ·  portado '手工皂'
    صابون يدوي        django ''  ·  portado 'صابون-يدوي'

Su hermano ``website_sale_wishlist`` ya usaba el portado sobre el mismo dato,
así que dos serializers del mismo catálogo producían dos slugs distintos.

Los casos miden **conducta** —el texto que sale— y no que se llame a un
símbolo concreto: un caso que sólo afirmara «llama a ``slugify_one``» pasaría
con una implementación que lo llamara y tirara el resultado.

Ver :ref:`h-api-993`.
"""
import pytest

from addons.base.models.ir_http import IrHttp
from addons.product.models import ProductTemplate
from addons.website_sale.controllers.serializers import ProductListSerializer
from addons.website_sale_wishlist.controllers.serializers import (
    WishlistProductNestedSerializer,
)


def slug_of(name, pk=42):
    """El slug que el serializer del escaparate produce para ese nombre."""
    product = ProductTemplate(name=name)
    product.pk = pk
    return ProductListSerializer().get_slug(product)


class TestTheSlugKeepsWhatDjangoWouldDrop:
    """La razón de portar ``_slugify``: las escrituras no latinas."""

    @pytest.mark.parametrize('name, expected', [
        ('手工皂', '手工皂-42'),
        ('ハンドメイド 石鹸', 'ハントメイト-石鹸-42'),
        ('صابون يدوي', 'صابون-يدوي-42'),
    ])
    def test_a_non_latin_name_survives_in_the_slug(self, name, expected):
        assert slug_of(name) == expected

    def test_a_latin_accent_is_stripped_by_decomposition(self):
        # NFKD: ``é`` da ``e``, no ``e-`` — la otra mitad de la decisión.
        assert slug_of('Café Orgánico') == 'cafe-organico-42'

    def test_an_underscore_is_replaced_like_any_non_word_character(self):
        # ``[\W_]+``: sin el ``_`` explícito quedaría en la URL.
        assert slug_of('Ñandú_edición 2026') == 'nandu-edicion-2026-42'

    def test_a_plain_ascii_name_is_unchanged(self):
        # Control positivo: el caso que ya funcionaba sigue igual.
        assert slug_of('Camisa Azul') == 'camisa-azul-42'


class TestTheEmptySlugBranchOfTheSource:
    """``if not slugname: return str(identifier)`` — sin el guion suelto."""

    @pytest.mark.parametrize('name', ['!!!', '---', '   ', '### $$$'])
    def test_a_name_without_word_characters_gives_only_the_id(self, name):
        assert slug_of(name) == '42'

    def test_the_guard_is_not_reached_by_an_ordinary_name(self):
        # Discrimina: si la rama se disparara siempre, éste daría '42'.
        assert slug_of('Camisa Azul') != '42'


class TestTheTwoSerializersAgreeOnTheSameName:
    """El defecto que esto cierra: dos slugs para el mismo producto."""

    @pytest.mark.parametrize('name', ['手工皂', 'Café Orgánico', 'Camisa Azul'])
    def test_the_showcase_slug_starts_with_the_wishlist_one(self, name):
        variant = ProductTemplate(name=name)
        variant.pk = 42
        wishlist = WishlistProductNestedSerializer().get_slug(variant)
        assert slug_of(name) == f'{wishlist}-42'

    def test_both_come_from_the_ported_slugify(self, ):
        assert slug_of('手工皂') == f'{IrHttp.slugify_one("手工皂")}-42'
