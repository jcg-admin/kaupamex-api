"""Contrato de ``website.page_options.mixin`` y su cableado a ``website.page``.

Tarea **#561**. Adaptación de
``odoo19c: addons/website/models/mixins.py:161-176`` (``odoo-tools@622ddc2a``,
LGPL-3). Contrato medido por AST sobre esas dos clases: **5 atributos de
clase, 5 campos, 0 métodos** — los diez portados.

Los casos cubren tres cosas distintas, y la tercera es la que un porte
silencioso perdería:

1. **La cabecera** — los cinco atributos de clase, verbatim de la fuente.
2. **Los campos y sus defectos** — que ``header_visible``/``footer_visible``
   nacen en ``True`` y el resto en su vacío, como la fuente declara.
3. **La separación de los dos mixins** — que el par de visibilidad NO arrastra
   los tres campos de color. La referencia los separa a propósito (sólo
   ``website_event`` y ``website_blog`` heredan el pequeño); fundirlos aquí
   pasaría los tres tests de arriba y rompería el contrato igual.
"""

import pytest

from addons.base.models.ir_ui_view import IrUiView
from addons.base.models.res_company import ResCompany
from addons.base.models.res_users import ResUsers
from addons.website.models.mixins import (
    WebsitePageOptionsMixin,
    WebsitePageVisibilityOptionsMixin,
)
from addons.website.models.website import Website
from addons.website.models.website_page import WebsitePage

#: Los cinco campos del par, en el orden en que la fuente los declara
#: (``:165-166`` el pequeño, ``:174-176`` el grande). Es la misma lista que
#: la plantilla del layout itera en ``website_templates.xml:271``.
OPTION_FIELDS = [
    'header_visible',
    'footer_visible',
    'header_overlay',
    'header_color',
    'header_text_color',
]

#: Sólo los del mixin pequeño — los que heredan ``website_event`` y
#: ``website_blog`` en la referencia.
VISIBILITY_FIELDS = ['header_visible', 'footer_visible']


class TestMixinContract:
    """La cabecera y los campos son los de la fuente, sin pytest ni base."""

    def test_the_class_attributes_come_from_the_source(self):
        assert (WebsitePageVisibilityOptionsMixin._name
                == 'website.page_visibility_options.mixin')
        assert (WebsitePageVisibilityOptionsMixin._description
                == 'Website page/record specific visibility options')
        assert WebsitePageOptionsMixin._name == 'website.page_options.mixin'
        assert WebsitePageOptionsMixin._inherit == [
            'website.page_visibility_options.mixin']
        assert (WebsitePageOptionsMixin._description
                == 'Website page/record specific options')

    def test_both_mixins_are_abstract(self):
        # Un mixin que creara tabla propia sería un modelo, no un mixin: la
        # fuente los declara ``models.AbstractModel``.
        assert WebsitePageVisibilityOptionsMixin._meta.abstract is True
        assert WebsitePageOptionsMixin._meta.abstract is True

    def test_the_option_mixin_declares_the_five_fields(self):
        declared = [f.name for f in WebsitePageOptionsMixin._meta.get_fields()]
        assert declared == OPTION_FIELDS

    def test_the_visibility_mixin_does_not_carry_the_color_fields(self):
        # La separación es del diseño de la fuente, no un accidente: un
        # evento oculta la cabecera sin poder recolorearla.
        declared = [f.name
                    for f in WebsitePageVisibilityOptionsMixin._meta.get_fields()]
        assert declared == VISIBILITY_FIELDS


class TestPageWiring:
    """``website.page`` hereda el mixin — el ``_inherit`` de la fuente."""

    def test_the_page_inherits_the_option_mixin(self):
        assert issubclass(WebsitePage, WebsitePageOptionsMixin)
        # El ``_inherit`` de la página ya lo nombraba antes de que el mixin
        # existiera; ahora la declaración y el mecanismo coinciden.
        assert 'website.page_options.mixin' in WebsitePage._inherit

    def test_the_page_gains_the_five_columns(self):
        columns = {f.name for f in WebsitePage._meta.get_fields()}
        assert set(OPTION_FIELDS) <= columns

    def test_the_page_keeps_its_own_class_attributes(self):
        # El MRO no debe pisar la cabecera de la página con la del mixin.
        assert WebsitePage._name == 'website.page'
        assert WebsitePage._description == 'Page'

    def test_the_blocked_view_fields_are_not_silently_stubbed(self):
        # ``visibility``/``group_ids``/``track`` NO son de este mixin: los
        # declara la vista (extensión del addon en la fuente). Si alguno
        # aparece sin portar esa extensión, la arista del docstring miente.
        columns = {f.name for f in WebsitePage._meta.get_fields()}
        assert not ({'visibility', 'group_ids', 'track'} & columns)


def _make_website():
    # ``company`` y ``user`` son NOT NULL (cabecera de B1 de website.py).
    company = ResCompany.objects.create(name='Kaupamex P561 QA')
    user = (ResUsers.objects.filter(login='p561@kaupamex.test').first()
            or ResUsers.objects.create_user(login='p561@kaupamex.test'))
    website = Website(name='P561', domain='https://p561.example.test',
                      company=company, user=user)
    website.save()
    return website


def _make_page(website, **overrides):
    view = IrUiView.objects.create(
        name='Página 561', type='template', key='website.pagina-561',
        arch_db='<t><div id="wrap"/></t>')
    values = {'url': '/pagina-561', 'view': view, 'website': website}
    values.update(overrides)
    return WebsitePage.objects.create(**values)


@pytest.mark.django_db
class TestPageOptionDefaults:
    """Los defectos contra PostgreSQL real, que es donde se guardan."""

    def test_a_new_page_shows_header_and_footer(self):
        page = _make_page(_make_website())
        assert page.header_visible is True
        assert page.footer_visible is True

    def test_a_new_page_has_no_overlay_and_no_colors(self):
        page = _make_page(_make_website())
        assert page.header_overlay is False
        assert page.header_color == ''
        assert page.header_text_color == ''

    def test_the_options_survive_a_round_trip(self):
        page = _make_page(_make_website())
        page.header_visible = False
        page.header_overlay = True
        page.header_color = 'bg-o-color-1'
        page.header_text_color = 'text-white'
        page.save()

        stored = WebsitePage.objects.get(pk=page.pk)
        assert stored.header_visible is False
        assert stored.footer_visible is True
        assert stored.header_overlay is True
        assert stored.header_color == 'bg-o-color-1'
        assert stored.header_text_color == 'text-white'
