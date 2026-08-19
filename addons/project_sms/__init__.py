"""Addon ``project_sms`` — puente Proyecto ↔ SMS.

Espejo de ``odoo19c: project_sms/__init__.py`` (``from . import models``).
Aquí el paquete raíz no importa modelos: las extensiones van por
``apps.py:ready()`` (patrón ``addons/utm``/``addons/hr_fleet``).

``upgrades/1.1/pre-migrate.py`` de la referencia NO se porta: es un script
de upgrade de Odoo que reescribe el ``domain_force`` de una ``ir.rule`` de
seguridad de vistas — ni las ``ir.rule`` de plantillas ni las migraciones
de datos son de este addon aquí (las migraciones Django son del
orquestador, y la seguridad es de la capa DRF).
"""
