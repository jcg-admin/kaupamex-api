"""``website``, ``website.menu`` y ``website.page`` sobre ``BaseModel``.

≙ ``odoo19c: addons/website/models/website.py:435-451``,
``odoo19c: addons/website/models/website_menu.py:163-177`` y
``odoo19c: addons/website/models/website_page.py:148-162``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
website-basemodel-u1b.md``.

*Métrica:* la base de cada clase, las filas que deja cada ``unlink`` y las
llamadas a ``_bump_menu_epoch``.
*Ciega a:* el arrastre de los menús con la misma ``url`` bajo
``website.main_menu`` y el sitio por defecto por external ID, que esperan
al registro de datos por módulo (#467).
"""
import pytest

from addons.base.models.ir_ui_view import IrUiView
from addons.website.models import website_menu as website_menu_module
from addons.website.models.website import Website
from addons.website.models.website_menu import WebsiteMenu
from addons.website.models.website_page import WebsitePage
from exceptions import UserError
from orm.environments import sudo
from orm.models import BaseModel
from tests.unit.website.test_website_page import _make_page, _make_website

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _elevated():
    with sudo():
        yield


@pytest.fixture
def epochs(monkeypatch):
    """Registra cada ``_bump_menu_epoch``. Es una función y no un doble de
    ``unittest.mock``: el colector de ``@api.ondelete`` busca en la clase
    los atributos con ``_ondelete`` y un doble responde a cualquiera."""
    calls = []

    def record():
        calls.append(True)

    monkeypatch.setattr(website_menu_module, '_bump_menu_epoch', record)
    return calls


def test_the_three_models_are_base_models():
    assert all(
        issubclass(model, BaseModel)
        for model in (Website, WebsiteMenu, WebsitePage)
    )


def test_the_default_website_cannot_be_unlinked():
    first = Website.objects.order_by('sequence', 'pk').first() or (
        _make_website()
    )
    with pytest.raises(UserError, match='default website'):
        first.unlink()
    assert Website.objects.filter(pk=first.pk).exists()


def test_a_non_default_website_is_unlinked():
    if not Website.objects.exists():
        _make_website(domain='https://u1b-first.example.test')
    other = _make_website(
        name='U1b otro', domain='https://u1b-other.example.test',
        sequence=9999,
    )
    other.unlink()
    assert not Website.objects.filter(pk=other.pk).exists()


def test_unlinking_a_menu_bumps_the_menu_epoch(epochs):
    website = _make_website(domain='https://u1b-menu.example.test')
    menu = WebsiteMenu.objects.create(
        name='U1b', key=f'u1b-{website.pk}', website=website,
    )
    epochs.clear()
    menu.unlink()
    assert not WebsiteMenu.objects.filter(pk=menu.pk).exists()
    assert epochs == [True]


def test_unlinking_a_page_unlinks_its_lonely_view():
    website = _make_website(domain='https://u1b-page.example.test')
    page = _make_page(website, url='/u1b', key='website.u1b')
    view_pk = page.view_id
    page.unlink()
    assert not WebsitePage.objects.filter(pk=page.pk).exists()
    assert not IrUiView.objects.filter(pk=view_pk).exists()


def test_a_view_shared_with_another_page_survives():
    website = _make_website(domain='https://u1b-shared.example.test')
    page = _make_page(website, url='/u1b-a', key='website.u1b-shared')
    sibling = _make_page(website, url='/u1b-b', view=page.view)
    page.unlink()
    assert IrUiView.objects.filter(pk=sibling.view_id).exists()
    assert WebsitePage.objects.filter(pk=sibling.pk).exists()


def test_copy_menu_hierarchy_copies_the_template_tree():
    website = _make_website(domain='https://u1b-copy.example.test')
    top = WebsiteMenu.objects.create(name='Plantilla', key='u1b-tpl-top')
    shop = WebsiteMenu.objects.create(
        name='Tienda', key='u1b-tpl-shop', parent=top, route='/shop',
    )
    WebsiteMenu.objects.create(
        name='Ofertas', key='u1b-tpl-deals', parent=shop, route='/deals',
    )
    website.copy_menu_hierarchy(top)
    copies = WebsiteMenu.objects.filter(website=website).order_by('pk')
    assert [menu.key for menu in copies] == [
        f'u1b-tpl-top-w{website.pk}',
        f'u1b-tpl-shop-w{website.pk}',
        f'u1b-tpl-deals-w{website.pk}',
    ]
    new_top, new_shop, new_deals = copies
    assert new_top.name == f'Top Menu for Website {website.pk}'
    assert new_shop.parent_id == new_top.pk
    assert new_deals.parent_id == new_shop.pk
    assert new_deals.route == '/deals'
    assert WebsiteMenu.objects.filter(website__isnull=True,
                                      key__startswith='u1b-tpl').count() == 3


def test_copy_data_emits_each_field_once_and_honours_its_default():
    """``_fields`` guarda un Many2one bajo su nombre y bajo su ``attname``;
    ``copy_data`` emite una sola clave por campo, como la fuente, y el
    ``default`` gana sea cual sea el nombre con que se dé."""
    website = _make_website(domain='https://u1b-data.example.test')
    menu = WebsiteMenu.objects.create(name='Datos', key='u1b-data')
    by_name = menu.copy_data({'website': website.id, 'key': 'u1b-a'})[0]
    by_attname = menu.copy_data({'website_id': website.id, 'key': 'u1b-b'})[0]
    assert 'website_id' not in by_name
    assert by_name['website'] == website.id
    assert 'website' not in by_attname
    assert by_attname['website_id'] == website.id
    assert not {'create_uid', 'create_uid_id', 'write_uid', 'write_uid_id',
                'parent_path'} & set(by_name)
    assert 'parent_id' not in by_name and by_name['parent'] is False
