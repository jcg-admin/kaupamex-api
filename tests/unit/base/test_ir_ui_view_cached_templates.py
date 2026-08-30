"""``ir.ui.view`` — la resolución de plantillas (tarea #544).

Contrato de ``_get_template_view`` / ``_get_cached_template_info`` (fuente
``odoo19c: base/models/ir_ui_view.py:1130-1166``), que ``Website.get_template``
/ ``viewref`` / ``is_view_active`` consumen. El porte NO cachea — la
divergencia y su motivo (4 workers prefork sin invalidación compartida) están
declarados en el docstring del módulo portado; estos tests fijan la
**semántica de resolución**, que es idéntica con o sin caché.
"""
import pytest

from addons.base.models.ir_model import IrModelData
from addons.base.models.ir_ui_view import IrUiView
from exceptions import MissingError
from orm.environments import context_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def make_view(name, *, key=None, view_type='template', priority=16, active=True):
    """Una vista mínima; ``key`` por defecto deriva del nombre (QWeb la exige)."""
    if key is None:
        key = f'test.{name}'
    return IrUiView.objects.create(
        name=name, type=view_type, key=key, arch_db='<data/>',
        priority=priority, active=active,
    )


class TestGetTemplateViewById:
    def test_resolves_an_existing_id(self):
        view = make_view('home')
        assert IrUiView._get_template_view(view.id) == view

    def test_missing_id_raises_missing_error(self):
        with pytest.raises(MissingError):
            IrUiView._get_template_view(99999999)

    def test_missing_id_without_raise_returns_none(self):
        """La fuente devuelve un recordset vacío; aquí ese vacío es ``None``."""
        assert IrUiView._get_template_view(
            99999999, raise_if_not_found=False) is None

    def test_archived_view_resolves_by_id(self):
        """Por id no interviene ``active_test`` — como el ``browse`` de la fuente."""
        view = make_view('old', active=False)
        assert IrUiView._get_template_view(view.id) == view


class TestGetTemplateViewByKey:
    def test_resolves_by_key(self):
        view = make_view('home', key='website.homepage')
        assert IrUiView._get_template_view('website.homepage') == view

    def test_missing_key_raises_missing_error(self):
        with pytest.raises(MissingError):
            IrUiView._get_template_view('website.no_existe')

    def test_lowest_priority_wins_between_same_key(self):
        """El orden es ``priority, id`` — la primera del orden gana la ``key``."""
        make_view('generic', key='website.header', priority=32)
        specific = make_view('specific', key='website.header', priority=1)
        assert IrUiView._get_template_view('website.header') == specific

    def test_archived_view_is_not_found_by_key_by_default(self):
        """Con ``active_test`` por defecto, la archivada no se resuelve por ``key``."""
        make_view('old', key='website.retired', active=False)
        with pytest.raises(MissingError):
            IrUiView._get_template_view('website.retired')

    def test_archived_view_is_found_with_active_test_off(self):
        """``viewref`` entra con ``active_test=False`` para ver archivadas."""
        view = make_view('old', key='website.retired', active=False)
        with context_scope(active_test=False):
            assert IrUiView._get_template_view('website.retired') == view

    def test_digit_string_keeps_the_source_quirk(self):
        """Verbatim de la fuente: ``"5"`` se reindexa como entero en el preload
        y la clave original no aparece — sale el ``SyntaxError`` literal."""
        view = make_view('home')
        with pytest.raises(SyntaxError):
            IrUiView._get_template_view(str(view.id))


class TestModelDataFallback:
    def test_resolves_via_external_identifier(self):
        """Segundo escalón: la ``xmlid`` sin ``key`` sale de ``ir.model.data``."""
        view = make_view('plain', key='', view_type='form')
        IrModelData.set_xmlid(view, 'website.plain_view')
        assert IrUiView._get_template_view('website.plain_view') == view

    def test_stale_external_identifier_is_a_missing_error(self):
        """Una fila que apunta a una vista borrada no resuelve nada."""
        view = make_view('plain', key='', view_type='form')
        IrModelData.set_xmlid(view, 'website.gone_view')
        view.delete()
        with pytest.raises(MissingError):
            IrUiView._get_template_view('website.gone_view')


class TestGetCachedTemplateInfo:
    def test_info_shape_matches_the_prefetched_keys(self):
        """La forma la fija ``_get_cached_template_prefetched_keys``, que es un
        punto de extensión: ``website`` le suma ``visibility`` y ``track``,
        verbatim de la fuente. El contrato de ``base`` es que **sus** tres
        claves salgan con el valor de la vista, más ``error`` — no que no haya
        más. Afirmar igualdad exacta sería afirmar que ningún addon extiende,
        que es falso en este árbol y en la referencia con ``website``
        instalado."""
        view = make_view('home', key='website.homepage')
        info = IrUiView._get_cached_template_info('website.homepage')
        for clave in IrUiView._get_cached_template_prefetched_keys():
            assert clave in info
        assert info['id'] == view.id
        assert info['key'] == 'website.homepage'
        assert info['active'] is True
        assert info['error'] is False

    def test_active_flag_for_an_archived_view(self):
        """El uso de ``is_view_active``: bajo ``active_test=False`` devuelve
        el campo ``active`` real de la archivada."""
        make_view('old', key='website.retired', active=False)
        with context_scope(active_test=False):
            info = IrUiView._get_cached_template_info('website.retired')
        assert info['active'] is False
        assert info['error'] is False

    def test_missing_key_reports_the_error_without_raising(self):
        """``is_view_active`` lee ``.get('active')`` sin atrapar nada: la
        ausencia viaja en ``error``, no como excepción."""
        info = IrUiView._get_cached_template_info('website.no_existe')
        assert info['id'] is None
        assert info['active'] is None
        assert isinstance(info['error'], MissingError)

    def test_view_shortcut_skips_the_lookup(self):
        """``_view`` puebla el resultado sin consultar — el atajo de la fuente.

        La vista se borra de la base antes de preguntar (sólo ésa: un
        ``all().delete()`` choca con el ``PROTECT`` de ``inherit_id`` sobre
        las vistas sembradas) y la clave consultada no existe — si el atajo
        no operara, la respuesta sería el ``MissingError`` del lookup.
        """
        view = make_view('home')
        view.delete()
        info = IrUiView._get_cached_template_info('cualquier.cosa', _view=view)
        assert info['id'] == view.id
        assert info['error'] is False

    def test_view_false_marks_a_known_miss(self):
        """``_view=False`` — campos ``None`` y ``error`` falso, verbatim.

        Se afirma sobre **todas** las claves publicadas, no sobre una lista
        fija: la extensión de ``website`` suma las suyas y también deben salir
        ``None``. Ver ``test_info_shape_matches_the_prefetched_keys``."""
        info = IrUiView._get_cached_template_info('website.x', _view=False)
        assert info['error'] is False
        for clave in IrUiView._get_cached_template_prefetched_keys():
            assert info[clave] is None


class TestFetchTemplateViews:
    def test_mixed_refs_resolve_in_one_call(self):
        by_id = make_view('a', key='test.a')
        by_key = make_view('b', key='test.b')
        result = IrUiView._fetch_template_views([by_id.id, 'test.b'])
        assert result[by_id.id] == by_id
        assert result['test.b'] == by_key

    def test_misses_come_back_as_missing_error_values(self):
        result = IrUiView._fetch_template_views([99999999, 'test.nada'])
        assert isinstance(result[99999999], MissingError)
        assert isinstance(result['test.nada'], MissingError)
