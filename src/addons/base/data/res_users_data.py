"""``base.partner_root`` y ``base.user_root`` — el superusuario de la base.

≙ ``odoo19c: odoo/addons/base/data/base_data.sql:134`` (``insert into
res_users (id, login, password, active, partner_id, …) VALUES (1,
'__system__', NULL, false, 1, …)``) más el XML-ID que le da
``res_users_data.xml:5-11``. En la fuente no lo crea el cargador de datos
sino la inicialización de la base; aquí esa inicialización son las
migraciones de ``base``, y por eso vive en una (mismo patrón que
``res_groups_data.py``). Sin esta fila ``get_current_user()`` es ``None`` bajo
``SUPERUSER_ID`` y los dominios de regla que leen ``user`` no se pueden
validar al instalar. Diseño: ``designs/module-install-cycle.md``, L4e (e5).

Divergencias, declaradas:

- Sin empresa: la fuente enlaza ``main_company``, que este árbol no siembra
  (DEC-3 de ``tenants-sin-clases-en-codigo``). ``ResUsers.company`` admite
  nulo.
- Contraseña inutilizable en vez de ``NULL``: el campo de Django es
  obligatorio; el efecto es el mismo, nadie entra con ella.
- Si la fila ``SUPERUSER_ID`` ya existe, recibe los dos XML-ID y no se toca:
  este árbol ya la trata como superusuario.
"""
from django.apps import apps
from django.contrib.auth.hashers import make_password
from django.core.management.color import no_style
from django.db import DEFAULT_DB_ALIAS, connections

from addons.base.data.res_groups_data import _xmlid_row
from orm.utils import SUPERUSER_ID


def seed_root_user(apps, alias):
    """Crea o señala el superusuario y su contacto, con sus XML-ID."""
    IrModelData = apps.get_model('base', 'IrModelData')
    ResPartner = apps.get_model('base', 'ResPartner')
    ResUsers = apps.get_model('base', 'ResUsers')
    user = ResUsers.objects.using(alias).filter(pk=SUPERUSER_ID).first()
    if user is None:
        partner = ResPartner.objects.using(alias).create(
            name='System', email='odoobot@example.com', active=False)
        user = ResUsers.objects.using(alias).create(
            pk=SUPERUSER_ID, login='__system__', partner=partner,
            password=make_password(None), active=False)
        # ``select setval(...)`` de la fuente: un id explícito no avanza la
        # secuencia, y el siguiente alta chocaría con él.
        connection = connections[alias]
        with connection.cursor() as cursor:
            for statement in connection.ops.sequence_reset_sql(
                    no_style(), [ResUsers]):
                cursor.execute(statement)
    _xmlid_row(IrModelData, alias, 'partner_root', user.partner)
    _xmlid_row(IrModelData, alias, 'user_root', user)
    return user


def seed(using=DEFAULT_DB_ALIAS):
    """Siembra sobre los modelos vivos — entrada del catálogo de tests.

    Va en ``_SEEDERS`` de ``tests/conftest.py`` por lo mismo que los grupos:
    el ``flush`` de un test transaccional borra la fila que sembró la
    migración y ``django_migrations`` la sigue dando por aplicada. Sin ella,
    ``get_current_user()`` es ``None`` bajo ``SUPERUSER_ID`` y la carga de
    los datos de seguridad de ``hr`` falla al validar sus dominios.
    """
    return seed_root_user(apps, using)


def seed_public_user(apps, alias):
    """Crea o señala el usuario público y su contacto, con sus XML-ID.

    ≙ ``res_users_data.xml:28-37`` y ``res_partner_data.xml:27-30``: el
    contacto ``Public user`` archivado y el usuario ``public`` archivado y
    sin grupos (``Command.set([])``). Lo consume el respaldo de
    ``Transaction.flush`` (``odoo/orm/environments.py:591-597``), que vuelca
    como este usuario lo que no tiene ``default_env``.

    Divergencias, las mismas que el superusuario: sin empresa y con una
    contraseña inutilizable en vez de vacía. Sin la imagen (``image_1920``).
    Si ya hay una fila ``login='public'``, recibe los XML-ID y no se toca.
    """
    IrModelData = apps.get_model('base', 'IrModelData')
    ResPartner = apps.get_model('base', 'ResPartner')
    ResUsers = apps.get_model('base', 'ResUsers')
    user = ResUsers.objects.using(alias).filter(login='public').first()
    if user is None:
        partner = ResPartner.objects.using(alias).create(
            name='Public user', active=False)
        user = ResUsers.objects.using(alias).create(
            login='public', partner=partner,
            password=make_password(None), active=False)
    _xmlid_row(IrModelData, alias, 'public_partner', user.partner)
    _xmlid_row(IrModelData, alias, 'public_user', user)
    return user


def public_user_seed(using=DEFAULT_DB_ALIAS):
    """Siembra sobre los modelos vivos — entrada de ``_SEEDERS``."""
    return seed_public_user(apps, using)
