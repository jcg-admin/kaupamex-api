"""Crea la extension ``unaccent`` en toda base que el ORM construya.

La fuente decide su ``ilike`` por la presencia de la **funcion**
``unaccent`` (``odoo19c: odoo/modules/db.py:168-189``) y, cuando esta,
envuelve los dos lados de la condicion (``odoo/orm/fields.py:1326-1327``).

**Por que una migracion y no solo el provisioner.** El provisioner de ``db``
ya la declara (``db: provisioners/postgresql/db_setup.sh:194-195``), pero solo
corre sobre las bases que el provisiona. pytest construye las suyas
—``kaupamex_core_qa`` y una por worker de ``xdist``— desde las migraciones, y
ahi el provisioner nunca pasa: por eso faltaba justo donde se mide. Con la
migracion la extension existe en **las dos** vias.

Medido antes de escribirla: ``pg_available_extensions`` declaraba ``unaccent``
1.1 con ``installed_version`` en ``NULL``. No era un impedimento — estaba
disponible y nadie la creaba.

``CreateExtension`` emite ``CREATE EXTENSION IF NOT EXISTS``, asi que es
idempotente sobre una base que ya la tenga.
"""
from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0083_rescompany_account_opening_date_and_more'),
    ]

    operations = [
        CreateExtension('unaccent'),
    ]
