"""Contrato de ``website.menu`` tras portar ``website_id`` (tarea **#543**).

Adaptación de ``odoo19c: addons/website/models/website_menu.py``
(``odoo-tools@bf077302``, LGPL-3). Contrato medido de la fuente por AST:
**1 clase, 4 atributos de clase, 15 campos, 15 métodos** en 346 líneas. La
tabla de cobertura —qué se porta y qué se declara fuera con su sucesor— vive
en el docstring de la clase portada.

Los casos cubren, en este orden:

1. **La cabecera entera** — los 4 atributos de clase que la fuente declara
   (``:16-21``), verbatim, como exige ``atributos-de-clase-de-modelo.md``
   v2.0.0 tras :ref:`h-api-580`.
2. **El campo ``website``** — el que #543 porta. Es lo que desbloquea
   ``Website.copy_menu_hierarchy`` (B2, #535): el método existe para poblar
   justo esa columna. Se verifica columna ``website_id``, ``null=True`` (el
   menú plantilla de la fuente no tiene sitio) y ``ondelete='cascade'``.
3. **``_default_sequence``** — el menú nuevo entra al final (``:23-25``).
4. **``parent_path``** — la materialización que sostiene el invariante de
   ``_parent_store`` en ``save()``, con el formato «1/4/9/» de la referencia.
5. **``_validate_parent_menu``** — las 2 de 3 reglas portadas (``:79-108``):
   profundidad máxima y submenú con hijos. La de mega menú cae con los campos
   no portados (divergencia declarada).
6. **``_clean_url``** — la heurística de ``:198-207`` sobre ``route``.
7. **``_compute_display_name``** y **``get_tree``** — ambos consumen el campo
   ``website`` recién portado.
"""

import pytest
from django.db import models as django_models

from addons.base.models.res_company import ResCompany
from addons.base.models.res_users import ResUsers
from addons.website.models.website import Website
from addons.website.models.website_menu import WebsiteMenu
from exceptions import UserError
from orm.environments import company_scope

pytestmark = [pytest.mark.django_db]


@pytest.fixture(autouse=True)
def active_company():
    """Una empresa activada en el entorno, porque ``Website.company`` es
    obligatorio y su ``default=`` la lee del contexto (mismo criterio que
    ``test_website_resolution.py``)."""
    company = ResCompany.objects.create(name='Kaupamex QA Menu')
    with company_scope(company.pk):
        yield company


def _public_user():
    """El usuario público del sitio — requerido por ``Website.user``."""
    existing = ResUsers.objects.filter(login='menu-public@kaupamex.test').first()
    return existing or ResUsers.objects.create_user(
        login='menu-public@kaupamex.test')


def _site(**kwargs):
    """Crea un sitio con lo mínimo que su contrato exige."""
    kwargs.setdefault('name', 'Sitio QA')
    kwargs.setdefault('user', _public_user())
    return Website.objects.create(**kwargs)


def _menu(key, **kwargs):
    """Crea una entrada de menú; ``key`` es único por contrato del seed."""
    kwargs.setdefault('name', key)
    return WebsiteMenu.objects.create(key=key, **kwargs)


# ── 1. Cabecera — los 4 atributos de clase de la fuente ─────────────────────

def test_class_attributes_match_the_source():
    """``odoo19c: website_menu.py:16-21`` declara exactamente estos cuatro."""
    assert WebsiteMenu._name == 'website.menu'
    assert WebsiteMenu._description == "Website Menu"
    assert WebsiteMenu._parent_store is True
    assert WebsiteMenu._order == "sequence, id"


def test_meta_ordering_mirrors_order():
    """``Meta.ordering`` es la forma Django de ``_order`` y deben coincidir."""
    assert WebsiteMenu._meta.ordering == ['sequence', 'id']


# ── 2. El campo ``website`` (#543) ──────────────────────────────────────────

def test_website_field_contract():
    """``website_id = fields.Many2one('website', ondelete='cascade')``
    (``odoo19c: :47``): columna ``website_id``, opcional, borrado en cascada.
    """
    field = WebsiteMenu._meta.get_field('website')
    assert field.column == 'website_id'
    assert field.null is True
    assert field.remote_field.model is Website
    assert field.remote_field.on_delete is django_models.CASCADE


def test_menu_without_website_is_the_shared_template():
    """Un menú sin sitio es la plantilla que ``copy_menu_hierarchy`` clona —
    el ``null`` no es un descuido, es el contrato de la fuente."""
    template = _menu('tpl-shared')
    assert template.website_id is None

    site = _site(domain='https://menus.kaupamex.test')
    owned = _menu('tpl-owned', website=site)
    assert owned.website_id == site.pk
    assert list(site.menus.all()) == [owned]


def test_deleting_the_site_cascades_to_its_menus():
    """``ondelete='cascade'`` observado, no sólo declarado.

    El borrado se ejerce sobre un sitio **no** default: B1 porta
    ``_unlink_except_default_website`` y el default (primero por
    ``sequence, pk``) no se puede borrar — ese contrato ya lo cubre
    ``test_website_resolution.py``; aquí lo probado es la cascada.
    """
    _site(name='Sitio default', sequence=1)
    site = _site(domain='https://cascade.kaupamex.test', sequence=99)
    _menu('cascade-menu', website=site)
    site.delete()
    assert not WebsiteMenu.objects.filter(key='cascade-menu').exists()


# ── 3. ``_default_sequence`` ────────────────────────────────────────────────

def test_default_sequence_is_zero_on_an_empty_tree():
    assert WebsiteMenu._default_sequence() == 0


def test_default_sequence_puts_the_new_menu_at_the_end():
    """≙ ``search([], limit=1, order="sequence DESC")`` (``odoo19c: :24``)."""
    _menu('seq-a', sequence=7)
    assert WebsiteMenu._default_sequence() == 7
    late = _menu('seq-b')  # sin sequence: ejercita el default del campo
    assert late.sequence == 7


# ── 4. ``parent_path`` — el invariante de ``_parent_store`` ─────────────────

def test_parent_path_uses_the_source_format():
    """«1/4/9/»: ids de ancestros y el propio, con ``/`` final, para que
    «descendiente de» sea un ``startswith`` (formato de la referencia)."""
    root = _menu('path-root')
    child = _menu('path-child', parent=root)
    grandchild = _menu('path-grandchild', parent=child)

    root.refresh_from_db()
    child.refresh_from_db()
    grandchild.refresh_from_db()

    assert root.parent_path == f'{root.pk}/'
    assert child.parent_path == f'{root.pk}/{child.pk}/'
    assert grandchild.parent_path == f'{root.pk}/{child.pk}/{grandchild.pk}/'
    assert grandchild.parent_path.startswith(root.parent_path)


def test_parent_path_follows_a_reparent_on_save():
    root_a = _menu('re-root-a')
    root_b = _menu('re-root-b')
    moved = _menu('re-moved', parent=root_a)

    moved.parent = root_b
    moved.save()
    moved.refresh_from_db()
    assert moved.parent_path == f'{root_b.pk}/{moved.pk}/'


# ── 5. ``_validate_parent_menu`` ────────────────────────────────────────────

def test_hierarchy_deeper_than_two_levels_is_rejected():
    """≙ «Menus cannot have more than two levels of hierarchy»
    (``odoo19c: :99``)."""
    root = _menu('depth-root')
    child = _menu('depth-child', parent=root)
    grandchild = _menu('depth-grandchild', parent=child)

    too_deep = WebsiteMenu(name='depth-4', key='depth-4', parent=grandchild,
                           sequence=0)
    with pytest.raises(UserError):
        too_deep._validate_parent_menu()


def test_menu_with_children_cannot_hang_under_a_submenu():
    """≙ «Menus with child menus cannot be added as a submenu»
    (``odoo19c: :108``)."""
    root = _menu('sub-root')
    submenu = _menu('sub-child', parent=root)
    container = _menu('sub-container')
    _menu('sub-leaf', parent=container)

    # Bajo una raíz sin padre y sin nietos propios: permitido (la fuente
    # sólo rechaza cuando el padre ya es submenú o hay nietos).
    container.parent = root
    container._validate_parent_menu()  # no levanta

    # Bajo un submenú (el padre ya tiene padre): rechazado.
    container.parent = submenu
    with pytest.raises(UserError):
        container.clean()  # la puerta de la ``@api.constrains``

    # Con nietos propios, ni siquiera bajo una raíz.
    grandchild_holder = _menu('sub-mid', parent=container)
    _menu('sub-grand', parent=grandchild_holder)
    container.parent = root
    with pytest.raises(UserError):
        container._validate_parent_menu()


def test_two_level_tree_is_valid():
    root = _menu('ok-root')
    child = _menu('ok-child', parent=root)
    child._validate_parent_menu()  # no levanta


# ── 6. ``_clean_url`` ───────────────────────────────────────────────────────

@pytest.mark.parametrize('given,expected', [
    ('/account/orders', '/account/orders'),   # ya relativa: intacta
    ('#top', '#top'),                         # ancla especial: intacta
    ('#bottom', '#bottom'),
    ('ventas@kaupamex.test', 'mailto:ventas@kaupamex.test'),
    ('mailto:ventas@kaupamex.test', 'mailto:ventas@kaupamex.test'),
    ('https://externo.test', 'https://externo.test'),
    ('shop', '/shop'),                        # sin esquema ni barra: relativa
])
def test_clean_url_heuristics(given, expected):
    """≙ ``_clean_url`` (``odoo19c: :198-207``), sobre ``route``."""
    menu = WebsiteMenu(name='clean', key='clean', route=given, sequence=0)
    assert menu._clean_url() == expected


# ── 7. ``_compute_display_name`` y ``get_tree`` ─────────────────────────────

def test_display_name_appends_the_site_when_asked():
    """≙ ``_compute_display_name`` (``odoo19c: :61-69``): el sufijo
    ``[Sitio]`` sólo aparece al pedir desambiguar."""
    site = _site(name='Sitio B', domain='https://b.kaupamex.test')
    menu = _menu('dn-menu', name='Tienda', website=site)
    assert menu._compute_display_name() == 'Tienda'
    assert menu._compute_display_name(display_website=True) == 'Tienda [Sitio B]'

    orphan = _menu('dn-orphan', name='Suelta')
    assert orphan._compute_display_name(display_website=True) == 'Suelta'


def test_get_tree_serializes_the_site_menu():
    """≙ ``get_tree`` (``odoo19c: :265-288``): mismo esquema de la fuente
    (``fields`` + ``children`` + ``is_homepage``) menos ``is_mega_menu``, cuyo
    campo no está portado (divergencia declarada en el modelo)."""
    site = _site(domain='https://tree.kaupamex.test')
    root = _menu('tree-root', website=site)
    home = _menu('tree-home', website=site, parent=root, route='/', sequence=1)
    shop = _menu('tree-shop', website=site, parent=root, route='/shop',
                 sequence=2, new_window=True)

    tree = WebsiteMenu.get_tree(site.pk)
    assert tree['fields']['id'] == root.pk
    assert [c['fields']['id'] for c in tree['children']] == [home.pk, shop.pk]
    assert tree['children'][0]['is_homepage'] is True
    assert tree['children'][1]['is_homepage'] is False
    assert tree['children'][1]['fields']['new_window'] is True
    assert tree['children'][1]['fields']['url'] == '/shop'
    assert 'is_mega_menu' not in tree['fields']


def test_get_tree_without_menus_returns_none():
    """Sin árbol que serializar no se fabrica uno — divergencia declarada
    frente al ``browse`` de la fuente, que asume que el sitio siempre tiene
    su ``menu_id``."""
    site = _site(domain='https://empty.kaupamex.test')
    assert WebsiteMenu.get_tree(site.pk) is None
