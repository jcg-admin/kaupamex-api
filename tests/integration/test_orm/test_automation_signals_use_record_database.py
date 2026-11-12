"""Las automatizaciones se consultan en la base de la fila que se escribe.

≙ ``base_automation`` de la fuente (``base_automation.py:909-1015``): las
reglas, los filtros y el proceso usan ``self.env`` del registro, es decir, el
cursor de su base. La señal de Django trae esa base en ``using``. Sin entrar
en ella, el enrutador resolvía por la empresa activa y, con varias bases y
ninguna empresa, rechazaba la consulta: ci-multidb ``5dc2e8c1``,
``test_django_creations_compute_in_their_own_base``.

El alias de sondeo apunta a la misma base con otra conexión; declarar que
hay bases de empresa reproduce el rechazo del enrutador sin aprovisionarlas.
"""
from django.apps import apps

from orm import routers
from orm.environments import Environment
from tests.integration.test_orm import test_env_alias_recordset as alias_probe

probe_alias = alias_probe.probe_alias


def test_a_django_creation_on_another_base_dispatches_automations_there(
        probe_alias, monkeypatch):
    monkeypatch.setattr(routers, '_has_company_databases', lambda: True)
    model = type(Environment(probe_alias, 1, {})['test_orm.shared.compute'])
    row = model.objects.using(probe_alias).create(name='5->25')
    row.name = '6->25'
    row.save(using=probe_alias)
    assert model.objects.using(probe_alias).filter(pk=row.pk).exists()
    row.delete(using=probe_alias)
    assert not model.objects.using(probe_alias).filter(pk=row.pk).exists()
