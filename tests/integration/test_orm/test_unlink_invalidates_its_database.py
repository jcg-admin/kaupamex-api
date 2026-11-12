"""Todo borrado vacía la caché del registro de la base de la fila.

≙ el ``clear_cache`` de ``unlink`` en la fuente (``ir_model.py:2328-2334`` y
sus análogos). Django no llama a ``Model.delete()`` en un ``QuerySet.delete()``
pero sí emite ``post_delete`` por cada fila; el vaciado vive en la señal y va
al registro de la base que Django entrega (``using``), no al activo.
"""
import pytest
from django.db.models.signals import post_delete

from addons.base.models.decimal_precision import DecimalPrecision
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_default import IrDefault
from addons.base.models.ir_rule import IrRule
from addons.base.models.properties_base_definition import (
    PropertiesBaseDefinition)
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_lang import ResLang
from orm import registry as orm_registry
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

CASES = [(DecimalPrecision, 'stable'), (SystemParameter, 'stable'),
         (IrDefault, 'default'), (IrRule, 'default'),
         (PropertiesBaseDefinition, 'stable'), (ResGroups, 'groups'),
         (ResLang, 'stable')]


@pytest.mark.parametrize('model, cache_name', CASES,
                         ids=[model.__name__ for model, _ in CASES])
def test_post_delete_clears_the_registry_of_the_row(model, cache_name):
    base = orm_registry.Registry('default')
    base._caches[cache_name]['sentinel'] = 1
    base.cache_invalidated.clear()
    with Environment('default', SUPERUSER_ID, {}):
        post_delete.send(sender=model, instance=model(), using='default')
    assert 'sentinel' not in base._caches[cache_name]
    assert cache_name in base.cache_invalidated
    base.cache_invalidated.clear()
