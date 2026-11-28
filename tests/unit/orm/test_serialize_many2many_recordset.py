"""El serializador de Django sobre un ``Many2many`` entre ``BaseModel``.

Leer el campo devuelve un recordset (``_x2many_descriptor_get``), y el
serializador de Django lo trata como gestor (``select_related``, ``only``,
``iterator``). Lo serializa por el gestor de Django que
``orm.commands.related_manager`` entrega. Diseño:
``designs/ir-module-country-ids.md``.
"""

import pytest
from django.core import serializers
from django.db import connection

from addons.base.models import IrModule, ResCountry

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def test_a_basemodel_many2many_serializes_its_ids():
    module = IrModule.objects.create(name='ser_owner', shortdesc='Owner')
    country = ResCountry.objects.order_by('id').first()
    with connection.cursor() as cursor:
        cursor.execute(
            'INSERT INTO module_country (module_id, country_id) '
            'VALUES (%s, %s)', [module.id, country.id])
    data = serializers.serialize(
        'python', IrModule.objects.filter(pk=module.pk))
    assert data[0]['fields']['country_ids'] == [country.id]
