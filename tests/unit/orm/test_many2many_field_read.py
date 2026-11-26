"""``Many2many.read`` como la lectura del campo.

≙ ``odoo19c: odoo/orm/fields_relational.py:1370-1410``: ``_fetch_query`` lee
cada campo sin columna con ``field.read``, y el ``Many2many`` se lee de su
tabla de relación, en el orden del comodelo, una tupla por registro. Diseño:
``designs/orm-many2many-field-read.md``.
"""

import pytest
from django.contrib.auth import get_user_model

from addons.utm.models import UtmCampaign, UtmStage, UtmTag
from orm.environments import Environment, sudo

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def test_a_basemodel_comodel_is_read_in_its_order():
    with sudo():
        stage = UtmStage.objects.create(name='m2m-read')
        beta = UtmTag.objects.create(name='m2m-read beta')
        alpha = UtmTag.objects.create(name='m2m-read alpha')
        campaign = UtmCampaign.objects.create(name='m2m-read', stage_id=stage)
        campaign.write({'tag_ids': [(6, 0, [beta.pk, alpha.pk])]})
        empty = UtmCampaign.objects.create(name='m2m-empty', stage_id=stage)
        rows = Environment(uid=1)['utm.campaign'].browse(
            [campaign.pk, empty.pk]).read(['tag_ids'])
    assert {row['id']: row['tag_ids'] for row in rows} == {
        campaign.pk: [alpha.pk, beta.pk], empty.pk: []}


def test_a_django_comodel_is_read_from_the_relation_table():
    with sudo():
        users = [get_user_model().objects.create_user(
            login=f'm2m-read-{n}', password=None, name=f'm2m-read {n}')
            for n in ('b', 'a')]
        record = Environment(uid=1)['ir.filters'].create({
            'name': 'm2m-read', 'model_id': 'res.partner',
            'user_ids': [(6, 0, [u.pk for u in users])]})
        rows = record.read(['user_ids'])
    assert rows[0]['user_ids'] == [users[1].pk, users[0].pk]
