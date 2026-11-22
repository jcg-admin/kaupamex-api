"""``website.configurator.feature``, ``website.route`` y ``website.rewrite``
sobre ``BaseModel``.

≙ ``odoo19c: addons/website/models/website_rewrite.py:38-57``, ``:90-157`` y
``odoo19c: addons/website/models/website_configurator_feature.py:9-13``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
website-basemodel-u1a.md``.

*Métrica:* la base de cada clase, las filas que deja ``_refresh`` y las
llamadas a ``_invalidate_routing``.
*Ciega a:* el middleware que sirve las 308/404 desde estas filas (#562).
"""
import pytest

from addons.website.models import (
    WebsiteConfiguratorFeature, WebsiteRewrite, WebsiteRoute,
)
from exceptions import ValidationError
from orm.environments import env, sudo
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _elevated():
    with sudo():
        yield


def _rewrites():
    return env()['website.rewrite']


@pytest.fixture
def invalidations(monkeypatch):
    """Registra cada ``_invalidate_routing``. Es una función y no un
    doble de ``unittest.mock``: el colector de ``@api.ondelete`` busca en la
    clase los atributos con ``_ondelete``, un doble responde a cualquiera y
    el borrado lo llamaría como comprobación."""
    calls = []
    monkeypatch.setattr(WebsiteRewrite, '_invalidate_routing',
                        lambda self: calls.append(self.ids))
    return calls


@pytest.mark.parametrize('model', [
    WebsiteConfiguratorFeature, WebsiteRoute, WebsiteRewrite,
])
def test_the_three_models_are_base_models(model):
    assert issubclass(model, BaseModel)


def test_refresh_creates_and_unlinks_routes():
    routes = env()['website.route']
    stale = routes.create([{'path': '/u1a-no-such-route'}])
    WebsiteRoute._refresh()
    assert not routes.search([('id', '=', stale.id)])
    assert routes.search([])


def test_unlinking_a_308_invalidates_the_routing(invalidations):
    rewrite = _rewrites().create([{
        'name': 'u1a 308', 'redirect_type': '308',
        'url_from': '/u1a-from', 'url_to': '/u1a-to'}])
    # Lo pendiente de la creación se vuelca antes: ``unlink`` empieza con
    # ``flush_all`` y ese ``write`` diferido también invalidaría.
    env().flush_all()
    invalidations.clear()
    rewrite.unlink()
    assert invalidations


def test_writing_into_a_404_invalidates_the_routing(invalidations):
    rewrite = _rewrites().create([{
        'name': 'u1a 302', 'redirect_type': '302',
        'url_from': '/u1a-a', 'url_to': '/u1a-b'}])
    env().flush_all()
    invalidations.clear()
    rewrite.write({'redirect_type': '404'})
    assert invalidations


def test_url_to_slash_is_rejected():
    with pytest.raises(ValidationError):
        _rewrites().create([{
            'name': 'u1a slash', 'redirect_type': '308',
            'url_from': '/u1a-slash', 'url_to': '/'}])


def test_display_name_joins_type_and_name():
    rewrite = _rewrites().create([{
        'name': 'u1a nombre', 'redirect_type': '302',
        'url_from': '/u1a-n', 'url_to': '/u1a-m'}])
    assert rewrite.display_name == '302 - u1a nombre'
