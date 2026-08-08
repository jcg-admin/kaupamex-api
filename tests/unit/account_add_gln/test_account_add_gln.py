"""Contrato de ``account_add_gln`` — ``PartnerGln`` (GLN del partner).

Portación fiel del addon ``account_add_gln`` de Odoo 19
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:
addons/account_add_gln/models/res_partner.py`` — único campo,
``global_location_number``). Cada test verifica un comportamiento del
original o del RELATED OneToOne que lo porta (DEC-SALE-01, mismo criterio
que ``base_address_extended``):

- El campo existe con default vacío (Odoo ``Char`` sin ``required``).
- Es RELATED OneToOne de ``base.ResPartner`` — no inyecta columna en su tabla.
- ``delete()`` en el partner hace CASCADE sobre el GLN enlazado.
- Archivar el partner (``active=False``) no toca la fila del GLN.
"""
import pytest

from addons.account_add_gln.models import PartnerGln
from addons.base.models import ResPartner

pytestmark = pytest.mark.django_db


def _make_partner(**kwargs):
    defaults = {'name': 'Nestor', 'type': ResPartner.TYPE_DELIVERY}
    defaults.update(kwargs)
    return ResPartner.objects.create(**defaults)


class TestPartnerGln:
    def test_global_location_number_defaults_empty(self):
        partner = _make_partner()
        gln = PartnerGln.objects.create(partner=partner)
        assert gln.global_location_number == ''

    def test_stores_and_reads_gln(self):
        partner = _make_partner()
        PartnerGln.objects.create(
            partner=partner, global_location_number='0614141000005')
        partner.refresh_from_db()
        assert partner.gln.global_location_number == '0614141000005'

    def test_one_to_one_reverse_on_partner(self):
        partner = _make_partner()
        gln = PartnerGln.objects.create(partner=partner)
        assert partner.gln == gln
        assert gln.partner == partner

    def test_one_to_one_is_unique(self):
        partner = _make_partner()
        PartnerGln.objects.create(partner=partner)
        with pytest.raises(Exception):
            PartnerGln.objects.create(partner=partner)

    def test_str_returns_gln_when_set(self):
        partner = _make_partner()
        gln = PartnerGln.objects.create(
            partner=partner, global_location_number='0614141000005')
        assert str(gln) == '0614141000005'

    def test_str_falls_back_to_partner_when_gln_empty(self):
        partner = _make_partner()
        gln = PartnerGln.objects.create(partner=partner)
        assert str(gln) == f'GLN de {partner.id}'

    def test_archiving_partner_keeps_gln_row(self):
        # ``res.partner`` no se borra logicamente: se ARCHIVA con ``active``
        # (odoo19c: base/models/res_partner.py, campo ``active``). Archivar no
        # toca la BD -> la fila del GLN persiste.
        partner = _make_partner()
        PartnerGln.objects.create(partner=partner)
        partner.active = False
        partner.save(update_fields=['active'])
        assert PartnerGln.objects.count() == 1

    def test_delete_cascades_gln_row(self):
        # delete() en ResPartner si borra la fila -> CASCADE elimina el
        # PartnerGln enlazado (on_delete=CASCADE en el OneToOne).
        partner = _make_partner()
        PartnerGln.objects.create(partner=partner)
        partner.delete()
        assert PartnerGln.objects.count() == 0
