"""Contrato de los mixins abstractos tras moverlos a ``addons.base`` (DEC-09).

Slice 1 de ``adoptar-arquitectura-server-service-odoo``: las bases abstractas
``TimeStampedModel``/``AppendOnlyModel``/``SoftDeleteModel`` viven en el addon
fundacional ``addons.base``, no en ``core``. Este test fija el nuevo hogar
canónico. El comportamiento append-only/soft-delete se cubre en
``tests/unit/core/test_log_immutability.py`` y
``tests/integration/test_soft_delete_contract.py`` (que ya importan desde el
nuevo hogar).
"""
import core.models as core_models
from django.db import models as dj_models

from addons.base.models import (
    AllObjectsManager,
    AppendOnlyModel,
    SoftDeleteManager,
    SoftDeleteModel,
    SoftDeleteQuerySet,
    TimeStampedModel,
)


def test_mixins_son_abstractos():
    """Los tres mixins son bases abstractas (no crean tabla)."""
    for cls in (TimeStampedModel, AppendOnlyModel, SoftDeleteModel):
        assert cls._meta.abstract is True


def test_hogar_canonico_es_addons_base():
    """El módulo de definición canónico es ``addons.base.models.mixins``."""
    for cls in (TimeStampedModel, AppendOnlyModel, SoftDeleteModel,
                SoftDeleteQuerySet, SoftDeleteManager, AllObjectsManager):
        assert cls.__module__ == 'addons.base.models.mixins', (
            f'{cls.__name__} se define en {cls.__module__}, '
            f'no en addons.base.models.mixins')


def test_abstractos_ya_no_se_definen_en_core():
    """``TimeStampedModel``/``SoftDeleteModel`` ya no se definen en ``core``.

    (``AppendOnlyModel`` sí queda importado en ``core.models`` como base del
    modelo de log ``RequestLog`` hasta el slice 3 lo mueva a
    ``addons.observability``; ``AppLog`` ya migró a ``IrLogging`` en
    ``addons.base`` en el slice 2. Su definición vive en ``addons.base``.)
    """
    assert getattr(core_models, 'TimeStampedModel', None) is None
    assert getattr(core_models, 'SoftDeleteModel', None) is None
    # AppendOnlyModel presente por import, pero definido en addons.base:
    assert core_models.AppendOnlyModel.__module__ == 'addons.base.models.mixins'


def test_soft_delete_managers_disponibles():
    """Los managers de soft-delete acompañan al mixin en su nuevo hogar."""
    assert issubclass(SoftDeleteManager, dj_models.Manager)
    assert issubclass(AllObjectsManager, dj_models.Manager)
    assert issubclass(SoftDeleteQuerySet, dj_models.QuerySet)
