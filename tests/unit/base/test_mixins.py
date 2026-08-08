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


def test_hogar_canonico_es_un_archivo_por_mixin():
    """Cada mixin se define en SU archivo, como en la referencia.

    Odoo tiene ``image_mixin.py`` / ``avatar_mixin.py`` /
    ``properties_base_definition_mixin.py`` — un archivo por mixin, no un
    ``mixins.py`` que los agrupe por naturaleza. El QuerySet y los managers de
    soft-delete viven **con su modelo**, no en un archivo de managers.
    """
    hogar = {
        TimeStampedModel: 'addons.base.models.timestamped_mixin',
        AppendOnlyModel: 'addons.base.models.append_only_mixin',
        SoftDeleteModel: 'addons.base.models.soft_delete_mixin',
        SoftDeleteQuerySet: 'addons.base.models.soft_delete_mixin',
        SoftDeleteManager: 'addons.base.models.soft_delete_mixin',
        AllObjectsManager: 'addons.base.models.soft_delete_mixin',
    }
    for cls, modulo in hogar.items():
        assert cls.__module__ == modulo, (
            f'{cls.__name__} se define en {cls.__module__}, no en {modulo}')


def test_abstractos_ya_no_se_definen_en_core():
    """``TimeStampedModel``/``SoftDeleteModel``/``AppendOnlyModel`` ya no se
    definen ni se importan en ``core.models``.

    (Slice 3 de ``adoptar-arquitectura-server-service-odoo``, DEC-08: con
    ``RequestLog`` movido a ``addons.observability``, ``core.models`` quedó
    sin modelos y sin necesidad de importar ``AppendOnlyModel``. ``AppLog``
    ya había migrado a ``IrLogging`` en ``addons.base`` en el slice 2. Ambos
    mixins/modelos se definen en ``addons.base``.)
    """
    assert getattr(core_models, 'TimeStampedModel', None) is None
    assert getattr(core_models, 'SoftDeleteModel', None) is None
    assert getattr(core_models, 'AppendOnlyModel', None) is None


def test_soft_delete_managers_disponibles():
    """Los managers de soft-delete acompañan al mixin en su nuevo hogar."""
    assert issubclass(SoftDeleteManager, dj_models.Manager)
    assert issubclass(AllObjectsManager, dj_models.Manager)
    assert issubclass(SoftDeleteQuerySet, dj_models.QuerySet)
