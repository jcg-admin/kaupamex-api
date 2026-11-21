"""Los lectores de bolsas de talento como recordsets.

``hr.applicant``, ``hr.talent.pool`` y ``hr.applicant.category`` son
``BaseModel``: los Many2many ``talent_pools``, ``talents`` y ``categs`` son
recordsets, como en la fuente, y estos sitios los leían o escribían con el
gestor de Django (``count``, ``all``, ``add``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-reverse-queryset.md``.

≙ ``_compute_talent_pool_count``
(``odoo19c: addons/hr_recruitment/models/hr_applicant.py:154-215``),
``_compute_talent_count`` (``hr_talent_pool.py:45-50``) y
``_add_applicants_to_pool`` (``wizard/talent_pool_add_applicants.py:22-49``).

*Métrica:* los dos contadores y los enlaces que deja el asistente.
*Ciega a:* la propagación indirecta por correo y teléfono, que el puerto
declara reducida.
"""
import pytest
from django.apps import apps

from addons.hr_recruitment.wizard.talent_pool_add_applicants import (
    TalentPoolAddApplicants)
from orm.commands import Command
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db

HrApplicantCategory = apps.get_model('hr_recruitment', 'HrApplicantCategory')


@pytest.fixture
def pool():
    with sudo():
        [pool] = env()['hr.talent.pool'].create([{'name': 'RRR Bolsa'}])
    return pool


def test_the_counts_read_the_pool_links(pool):
    with sudo():
        [applicant] = env()['hr.applicant'].create(
            [{'partner_name': 'RRR Uno',
              'talent_pools': [Command.link(pool.id)]}])
        assert applicant.talent_pool_count() == 1
        assert pool.talent_count() == 1


def test_the_wizard_links_a_talent_and_its_categories(pool):
    tag = HrApplicantCategory.objects.create(name='RRR Etiqueta')
    with sudo():
        [applicant] = env()['hr.applicant'].create(
            [{'partner_name': 'RRR Dos', 'categs': [Command.link(tag.pk)]}])
        [talent] = TalentPoolAddApplicants.add_applicants_to_pool(
            applicant, pool, [])
        assert talent.id != applicant.id
        assert talent.talent_pools.ids == [pool.id]
        assert talent.categs.ids == [tag.pk]


def test_the_wizard_adds_an_existing_talent_to_more_pools(pool):
    tag = HrApplicantCategory.objects.create(name='RRR Otra')
    with sudo():
        [other] = env()['hr.talent.pool'].create([{'name': 'RRR Otra bolsa'}])
        [talent] = env()['hr.applicant'].create(
            [{'partner_name': 'RRR Tres',
              'talent_pools': [Command.link(pool.id)]}])
        [same] = TalentPoolAddApplicants.add_applicants_to_pool(
            talent, other, [tag])
        assert same.id == talent.id
        assert set(talent.talent_pools.ids) == {pool.id, other.id}
        assert talent.categs.ids == [tag.pk]
