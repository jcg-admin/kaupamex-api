"""Tarea #552 — ``website.configurator.feature``, la pieza que desbloquea B4.

Universo controlado, sin red: una vista QWeb mínima y un módulo del catálogo
L0 para el xor, y ``tmp_path`` como raíz de addons para el SVG del tema (las
raíces reales no tienen temas — la rama ``False`` es la vigente). Cada
default de la fuente se verifica uno a uno (H-API-696), el orden por defecto
contra el ``_order`` declarado, y un test por método portado.
"""
import pytest

from addons.authz.models import Module
from addons.base.models.ir_ui_view import IrUiView
from addons.website.models import website_configurator_feature as wcf_module
from addons.website.models.website_configurator_feature import (
    WebsiteConfiguratorFeature,
)
from exceptions import ValidationError

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def page_view(db):
    """Una vista QWeb mínima — el mismo esqueleto de los tests de IrUiView."""
    return IrUiView.objects.create(
        name='configurator feature page', type='template',
        key='website.test_configurator_feature_page', arch_db='<data/>',
    )


@pytest.fixture
def catalog_module(db):
    """Un módulo del catálogo L0 (``authz.Module`` ≙ ``ir.module.module``)."""
    return (Module.objects.filter(code='configurator_probe').first()
            or Module.objects.create(code='configurator_probe',
                                     name='Sonda del configurador'))


# ── cabecera y defaults ─────────────────────────────────────────────────────

def test_class_attributes_match_the_source_header():
    """Los tres atributos de la fuente (``odoo19c: :10-13``), verbatim."""
    assert WebsiteConfiguratorFeature._name == 'website.configurator.feature'
    assert (WebsiteConfiguratorFeature._description
            == 'Website Configurator Feature')
    assert WebsiteConfiguratorFeature._order == 'sequence'
    assert (WebsiteConfiguratorFeature._meta.db_table
            == 'website_configurator_feature')


def test_creation_defaults_match_the_source(page_view):
    """Cada default se verifica uno a uno (H-API-696): los Integer de la
    fuente leen 0 sin default explícito, los Char leen vacío y el Boolean
    lee False."""
    feature = WebsiteConfiguratorFeature.objects.create(page_view=page_view)
    feature.refresh_from_db()
    assert feature.sequence == 0
    assert feature.name == ''
    assert feature.description == ''
    assert feature.icon == ''
    assert feature.iap_page_code == ''
    assert feature.website_config_preselection == ''
    assert feature.feature_url == ''
    assert feature.menu_sequence == 0
    assert feature.menu_company is False
    assert feature.module_id is None
    assert feature.page_view_id == page_view.pk


def test_default_ordering_derives_from_order(page_view):
    """``Meta.ordering`` ≙ ``_order = 'sequence'`` — y la consulta lo
    respeta aunque la inserción llegue desordenada."""
    assert WebsiteConfiguratorFeature._meta.ordering == ['sequence']
    for seq in (3, 1, 2):
        WebsiteConfiguratorFeature.objects.create(
            name=f'feature {seq}', sequence=seq, page_view=page_view)
    assert list(WebsiteConfiguratorFeature.objects.values_list(
        'sequence', flat=True)) == [1, 2, 3]


# ── _check_module_xor_page_view ─────────────────────────────────────────────

def test_xor_rejects_both_fields_unset():
    feature = WebsiteConfiguratorFeature(name='vacía')
    with pytest.raises(ValidationError):
        feature._check_module_xor_page_view()


def test_xor_rejects_both_fields_set(page_view, catalog_module):
    feature = WebsiteConfiguratorFeature(
        name='doble', page_view=page_view, module=catalog_module)
    with pytest.raises(ValidationError):
        feature._check_module_xor_page_view()


def test_xor_accepts_exactly_one_field(page_view, catalog_module):
    """Cada rama válida del xor, y ``clean()`` como puerta de la
    ``@api.constrains`` (patrón ``website_menu.py``)."""
    with_page = WebsiteConfiguratorFeature(name='página', page_view=page_view)
    with_module = WebsiteConfiguratorFeature(
        name='módulo', module=catalog_module)
    with_page.clean()      # no levanta
    with_module.clean()    # no levanta


def test_clean_invokes_the_constraint():
    with pytest.raises(ValidationError):
        WebsiteConfiguratorFeature(name='vacía').clean()


# ── _process_svg ────────────────────────────────────────────────────────────

def test_process_svg_returns_false_without_theme_file():
    """La rama ``FileNotFoundError → False`` de la fuente — la vigente en
    este árbol, que no tiene addons de tema."""
    assert WebsiteConfiguratorFeature._process_svg(
        'theme_inexistente', {}, {}) is False


def test_process_svg_rejects_non_simple_theme_names():
    """El guard que sustituye el confinamiento de ``tools.file_open``: un
    nombre con separadores no sale de las raíces de addons."""
    assert WebsiteConfiguratorFeature._process_svg('../base', {}, {}) is False
    assert WebsiteConfiguratorFeature._process_svg('', {}, {}) is False


def test_process_svg_replaces_colors_and_images(tmp_path, monkeypatch):
    """La lógica de reemplazo de la fuente (``odoo19c: :41-59``): colores
    conocidos se sustituyen, claves desconocidas se ignoran, y el mapeo de
    imágenes aplica después."""
    theme_dir = tmp_path / 'theme_probe' / 'static' / 'description'
    theme_dir.mkdir(parents=True)
    (theme_dir / 'theme_probe.svg').write_text(
        '<svg fill="#3AADAA" stroke="#MENU_COLOR">'
        '<image href="img_old.jpg"/></svg>')
    monkeypatch.setattr(wcf_module, '_ADDON_ROOTS', (tmp_path,))

    svg = WebsiteConfiguratorFeature._process_svg(
        'theme_probe',
        {'color1': '#111111', 'menu': '#222222', 'desconocida': '#999999'},
        {'img_old.jpg': 'img_new.jpg'},
    )
    assert svg == ('<svg fill="#111111" stroke="#222222">'
                   '<image href="img_new.jpg"/></svg>')
