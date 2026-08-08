"""Modelos del addon ``digest`` (estructura Odoo: un archivo por modelo).

Cierre parcial: los 2 ``_name`` propios del addon (el digest + sus consejos
rotativos) y el motor de cómputo de KPIs/periodicidad/suscripción — el
motor de envío por correo (plantillas HTML + cron) queda DEFERIDO por falta
de consumidor, ver el docstring de ``digest.py`` y
``analisis-familia-digest``. La extensión de ``res.users`` (auto-suscripción)
vive en ``signals.py``, importada por ``DigestConfig.ready()`` — no en este
``__init__`` (no es un modelo).
"""
from .digest import DigestDigest, DigestPeriodicity, DigestState
from .digest_tip import DigestTip

__all__ = [
    'DigestDigest',
    'DigestPeriodicity',
    'DigestState',
    'DigestTip',
]
