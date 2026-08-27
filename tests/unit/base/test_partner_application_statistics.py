"""``application_statistics`` — el campo que existe para que otros lo llenen.

La referencia lo declara como ``fields.Json`` calculado
(``odoo19c: res_partner.py:313-324``) cuya implementación base devuelve un
mapa vacío. Su razón de ser es el enganche: el docstring de la fuente lo dice
—*"Hook for override, as overriding compute method does not update cache
accordingly"*—. Enterprise 19 lo hereda en dos clases con
``_inherit = 'res.partner'``.
"""
import pytest

from addons.base.models.res_partner import ResPartner


pytestmark = pytest.mark.django_db


def test_the_hook_returns_an_empty_mapping_by_default():
    partner = ResPartner.objects.create(name='Sin estadísticas')
    assert ResPartner._compute_application_statistics_hook([partner]) == {}


def test_the_property_is_empty_when_nobody_contributes():
    partner = ResPartner.objects.create(name='Sin estadísticas')
    assert partner.application_statistics == []


def test_the_batch_gives_one_entry_per_partner():
    uno = ResPartner.objects.create(name='Uno')
    dos = ResPartner.objects.create(name='Dos')
    result = ResPartner._compute_application_statistics([uno, dos])
    assert set(result) == {uno.pk, dos.pk}
    assert result[uno.pk] == [] and result[dos.pk] == []


def test_overriding_the_hook_changes_what_the_property_returns():
    """El control: si el enganche no se consultara, esto seguiría vacío.

    Es lo único que distingue un punto de extensión de un método que existe.
    """
    partner = ResPartner.objects.create(name='Con estadísticas')
    original = ResPartner._compute_application_statistics_hook.__func__

    ResPartner._compute_application_statistics_hook = classmethod(
        lambda cls, partners: {p.pk: [{'label': 'Pedidos', 'value': 3}]
                               for p in partners})
    try:
        assert partner.application_statistics == [
            {'label': 'Pedidos', 'value': 3}]
    finally:
        ResPartner._compute_application_statistics_hook = classmethod(original)

    assert partner.application_statistics == []
