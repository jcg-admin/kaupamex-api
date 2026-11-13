"""ACL de ``utm`` — el rol de ``utm/security/ir.model.access.csv``.

≙ ``odoo19c: addons/utm/security/ir.model.access.csv`` (odoo-tools
``abe4040ec1``, LGPL-3). Lo que allá carga el instalador con el módulo,
aquí lo siembra una migración de datos (``utm/0007``) y lo re-aplica el
catálogo de ``tests/conftest.py``: el mismo cuerpo que la ACL de ``base``
(:func:`addons.base.security.ir_model_access._seed`), con estas filas.

Las filas se **derivan** del CSV con ``derive_base_acl.py`` (``probes/`` del
banco ``orm-continuation-plan-20261103T095630``), permisos verbatim:
``(read, write, create, unlink)``. El CSV repite ``mail.utm.stage`` y
``utm.tag`` con grupos distintos; la clave es la terna
``(nombre, modelo, grupo)``.
"""

from django.apps import apps as _live_apps
from django.db import DEFAULT_DB_ALIAS

from addons.base.models.ir_model import (
    IrModel as _IrModel,
    IrModelAccess as _IrModelAccess,
    IrModelData as _IrModelData,
)
from addons.base.models.res_groups import ResGroups as _ResGroups
from addons.base.security.ir_model_access import _seed

_ACCESS = (
    ('access_utm_campaign_user', 'utm.UtmCampaign', 'group_user',
     (1, 1, 1, 0)),
    ('utm.campaign.system', 'utm.UtmCampaign', 'group_system', (1, 1, 1, 1)),
    ('access_utm_medium_user', 'utm.UtmMedium', 'group_user', (1, 1, 1, 0)),
    ('utm.medium.system', 'utm.UtmMedium', 'group_system', (1, 1, 1, 1)),
    ('access_utm_source_user', 'utm.UtmSource', 'group_user', (1, 1, 1, 0)),
    ('utm.source.system', 'utm.UtmSource', 'group_system', (1, 1, 1, 1)),
    ('mail.utm.stage', 'utm.UtmStage', 'group_user', (1, 0, 0, 0)),
    ('mail.utm.stage', 'utm.UtmStage', 'group_system', (1, 1, 1, 1)),
    ('utm.tag', 'utm.UtmTag', 'group_user', (1, 0, 0, 0)),
    ('utm.tag', 'utm.UtmTag', 'group_system', (1, 1, 1, 1)),
)


def seed(using=DEFAULT_DB_ALIAS):
    """Sobre los modelos vivos — entrada del catálogo de tests."""
    return _seed(_live_apps, _IrModel, _IrModelAccess, _IrModelData,
                 _ResGroups, using, rows=_ACCESS)


def seed_utm_acl(apps, alias):
    """Sobre los modelos históricos — entrada de la migración."""
    return _seed(
        apps,
        apps.get_model('base', 'IrModel'),
        apps.get_model('base', 'IrModelAccess'),
        apps.get_model('base', 'IrModelData'),
        apps.get_model('base', 'ResGroups'),
        alias,
        rows=_ACCESS,
    )
