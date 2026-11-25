"""Capacidades PostgreSQL y árbol de categorías del catálogo técnico.

Referencia Odoo19Community, revisión abe4040ec1a45beee90fb694e4eae4453e46b389,
``odoo/modules/db.py``. FunctionStatus, has_unaccent y has_trigram consultan
capacidades del motor; create_categories adapta las identidades y el árbol
mediante los modelos Django existentes, conservando la conexión del cursor.

La integración del helper con el FK del catálogo y su migración pertenece a
TASK-API-0267 y no queda acreditada por implementar esta función.

is_initialized e initialize (TASK-GEN-0058) son la fuente salvo dos
divergencias declaradas: el esquema lo crean las migraciones de ``base`` y no
``base_data.sql``, así que initialize rehúsa sobre una base sin
``ir_module_module``; y sus filas las escribe ``update_module_list``, el porte
de ``update_list``. Ver ``designs/orm-modules-db-initialize-0058.md``.
"""

import io
import logging
from enum import IntEnum

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import transaction
from exceptions import UserError
from orm import registry
from tools.sql import table_exists

_logger = logging.getLogger(__name__)


def is_initialized(cr):
    """¿La base tiene el catálogo de módulos? ≙ ``db.py:20-26``."""
    return table_exists(cr, 'ir_module_module')


def initialize(cr, *, skip_auto_install=False):
    """Inicializa el catálogo de una base sin módulos instalados.

    ≙ ``odoo19c: odoo/modules/db.py:29-124``. La fuente sólo llega aquí con
    ``is_initialized`` falso (``loading.py:371-376``), así que su punto fijo
    nunca ve un módulo ``installed``; esa precondición se porta como rechazo,
    en vez de excluir ``installed`` del SQL, que sería una divergencia.
    ``skip_auto_install`` es la opción de configuración de la fuente
    (``:85-89``), que este árbol no tiene.
    """
    if not is_initialized(cr):
        raise RuntimeError(
            'ir_module_module does not exist: run migrate for base first.')
    using = cr.db.alias
    module_rows = apps.get_model('base', 'IrModule')._base_manager.using(using)
    if module_rows.filter(state='installed').exists():
        raise UserError(
            'initialize only runs on a database without installed modules.')
    with transaction.atomic(using=using):
        call_command('update_module_list', database=using,
                     stdout=io.StringIO())
        _ensure_module_identities(using)
        if skip_auto_install:
            # even if skip_auto_install is enabled we still want to have base
            cr.execute("UPDATE ir_module_module SET state='to install'"
                       " WHERE name = 'base'")
            return
        _mark_auto_install(cr)


def _ensure_module_identities(using):
    """``base.module_<name>`` por módulo, ≙ ``db.py:72-76``.

    Idempotente: la fuente inserta sobre tablas recién creadas; aquí el
    catálogo puede existir de antes.
    """
    module_model = apps.get_model('base', 'IrModule')
    identity_rows = apps.get_model('base', 'IrModelData')._base_manager.using(
        using)
    model_identity = registry.identity_for_key(module_model._meta.label)
    present = set(identity_rows.filter(
        module='base', name__startswith='module_',
        model=model_identity).values_list('name', flat=True))
    for pk, name in module_model._base_manager.using(using).values_list(
            'pk', 'name'):
        if 'module_' + name not in present:
            identity_rows.create(module='base', name='module_' + name,
                                 model=model_identity, res_id=pk,
                                 noupdate=True)


def _mark_auto_install(cr):
    """Punto fijo de ``auto_install``, verbatim de ``db.py:91-124``."""
    while True:
        # this selects all the auto_install modules whose auto_install_required
        # deps are marked as to install
        cr.execute("""
        SELECT m.name FROM ir_module_module m
        WHERE m.auto_install
        AND state not in ('to install', 'uninstallable')
        AND NOT EXISTS (
            SELECT 1 FROM ir_module_module_dependency d
            LEFT JOIN ir_module_module mdep ON (d.name = mdep.name)
            WHERE d.module_id = m.id
              AND (
                  mdep.id IS NULL
                  OR (d.auto_install_required AND mdep.state != 'to install')
              )
        )""")
        to_auto_install = [x[0] for x in cr.fetchall()]
        # however if the module has non-required deps we need to install
        # those, so merge-in the modules which have a dependen*t* which is
        # *either* to_install or in to_auto_install and merge it in?
        cr.execute("""
        SELECT d.name FROM ir_module_module_dependency d
        JOIN ir_module_module m ON (d.module_id = m.id)
        JOIN ir_module_module mdep ON (d.name = mdep.name)
        WHERE (m.state = 'to install' OR m.name = any(%s))
            -- don't re-mark marked modules
        AND NOT (mdep.state = 'to install' OR mdep.name = any(%s))
        """, [to_auto_install, to_auto_install])
        to_auto_install.extend(x[0] for x in cr.fetchall())

        if not to_auto_install:
            break
        # ``IN %s`` con tupla no lo adapta psycopg3; ``= ANY`` es la misma
        # pregunta contra un arreglo (``tools/sql.py``, ``existing_tables``).
        cr.execute("UPDATE ir_module_module SET state='to install'"
                   " WHERE name = ANY(%s)", [to_auto_install])


def _category_xml_id(segments):
    return 'module_category_' + '_'.join(
        part.lower() for part in segments
    ).replace('&', 'and').replace(' ', '_')


def validate_category_paths(paths):
    """Rechaza rutas fuente distintas que compartirían una identidad nativa.

    Es una comprobación del corpus que va a escribirse, no una interpretación
    del nombre visible de categorías ya renombradas. No escribe ni renumera.
    """
    identities = {}
    for path in paths:
        if not path:
            continue
        prefix = []
        for segment in path.split('/'):
            prefix.append(segment)
            xml_id = _category_xml_id(prefix)
            source = tuple(prefix)
            previous = identities.setdefault(xml_id, source)
            if previous != source:
                raise ValidationError(
                    f'colisión de rutas de categoría: base.{xml_id}.'
                )


def create_categories(cr, categories):
    """Resuelve una ruta de categorías conservando sus identidades externas.

    Adapta create_categories de Odoo19Community, revisión abe4040e. El cursor
    Django determina la conexión; los modelos existentes aportan timestamps
    y el label Django que ya consume IrModuleCategory._compute_xml_id.
    No muta la lista ni confirma la transacción exterior. Un XMLID incompatible
    bloquea la operación completa, en lugar de sobrescribir otra identidad.

    La identidad nativa permite renombrar el texto visible. Por eso un nombre
    distinto no se repara ni se interpreta por sí solo como colisión. El
    llamador que migre rutas crudas debe verificar sus colisiones previamente.
    """
    using = cr.db.alias
    category_model = apps.get_model('base', 'IrModuleCategory')
    identity_model = apps.get_model('base', 'IrModelData')
    category_rows = category_model._base_manager.using(using)
    identity_rows = identity_model._base_manager.using(using)
    name_limit = identity_model._meta.get_field('name').max_length
    parent_field = category_model._meta.get_field('parent')
    parent_id = None
    parent_record = None
    path = []

    with transaction.atomic(using=using):
        for segment in categories:
            path.append(segment)
            xml_id = _category_xml_id(path)
            if name_limit is not None and len(xml_id) > name_limit:
                raise ValidationError(
                    'La identidad de categoría supera'
                    f' {name_limit} caracteres.'
                )
            identity = (
                identity_rows.select_for_update()
                .filter(
                    module='base',
                    name=xml_id,
                )
                .first()
            )
            if identity is not None:
                category = category_rows.filter(pk=identity.res_id).first()
                if (
                    identity.model != registry.identity_for_key(
                        category_model._meta.label)
                    or category is None
                    or category.parent_id != parent_id
                ):
                    raise ValidationError(
                        f'Identidad de categoría incompatible: base.{xml_id}.'
                    )
            else:
                category = category_model(name=segment, parent_id=parent_id)
            # La validación de ciclos corre antes de Model.save y, por tanto,
            # antes de enlazar el alias de una fila nueva. Conservar la cadena
            # ya verificada evita que esa lectura consulte default por error.
            parent_field.set_cached_value(category, parent_record)
            if identity is None:
                category.save(using=using, force_insert=True)
                identity_rows.create(
                    module='base',
                    name=xml_id,
                    res_id=category.pk,
                    model=registry.identity_for_key(
                        category_model._meta.label),
                    noupdate=True,
                )
            parent_id = category.pk
            parent_record = category
    return parent_id


class FunctionStatus(IntEnum):
    """≙ ``FunctionStatus`` (``odoo19c: odoo/modules/db.py:162-165``)."""

    MISSING = 0  # la función no está (falsy)
    PRESENT = 1  # está, pero no es indexable (no inmutable)
    INDEXABLE = 2  # está y es indexable (inmutable)


def has_unaccent(cr):
    """≙ ``has_unaccent`` (``odoo19c: odoo/modules/db.py:168-189``).

    ¿Existe la función ``unaccent`` y en qué estado? La provee normalmente el
    módulo contrib ``unaccent`` de PostgreSQL, pero cualquier función homónima
    de un argumento sirve — mismo criterio que la fuente.

    El ``provolatile`` distingue si sirve para **crear índices**: sólo una
    función inmutable (``'i'``) es indexable.

    :param cr: cursor de base de datos abierto.
    :returns: un :class:`FunctionStatus`.
    """
    cr.execute(
        """
        SELECT p.provolatile
        FROM pg_proc p
        WHERE p.proname = 'unaccent'
              AND p.pronamespace = current_schema::regnamespace
              AND p.pronargs = 1
    """
    )
    result = cr.fetchone()
    if not result:
        return FunctionStatus.MISSING
    return (
        FunctionStatus.INDEXABLE
        if result[0] == 'i'
        else FunctionStatus.PRESENT
    )


def has_trigram(cr):
    """≙ ``has_trigram`` (``odoo19c: odoo/modules/db.py:192-200``).

    ¿Existe ``word_similarity``? La provee ``pg_trgm``, pero —igual que la
    fuente— cualquier función con ese nombre cuenta: se pregunta por el
    símbolo, no por la extensión.

    :param cr: cursor de base de datos abierto.
    :returns: ``True`` si la función existe.
    """
    cr.execute("SELECT proname FROM pg_proc WHERE proname='word_similarity'")
    return len(cr.fetchall()) > 0
