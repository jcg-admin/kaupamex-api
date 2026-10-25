"""Capacidades PostgreSQL y árbol de categorías del catálogo técnico.

Referencia Odoo19Community, revisión abe4040ec1a45beee90fb694e4eae4453e46b389,
``odoo/modules/db.py``. FunctionStatus, has_unaccent y has_trigram consultan
capacidades del motor; create_categories adapta las identidades y el árbol
mediante los modelos Django existentes, conservando la conexión del cursor.

La integración del helper con el FK del catálogo y su migración pertenece a
TASK-API-0267 y no queda acreditada por implementar esta función. initialize e
is_initialized requieren reconciliación de sus obligaciones de bootstrap;
INSTALLED_APPS o migraciones por sí solos no demuestran equivalencia completa.
La TASK-GEN-0058 más amplia no se ejecuta ni se cierra en este alcance.
"""
from enum import IntEnum

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import transaction


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
                raise ValidationError(f'colisión de rutas de categoría: base.{xml_id}.')


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
                    f'La identidad de categoría supera {name_limit} caracteres.')
            identity = identity_rows.select_for_update().filter(
                module='base', name=xml_id,
            ).first()
            if identity is not None:
                category = category_rows.filter(pk=identity.res_id).first()
                if (identity.model != category_model._meta.label
                        or category is None or category.parent_id != parent_id):
                    raise ValidationError(
                        f'Identidad de categoría incompatible: base.{xml_id}.')
            else:
                category = category_model(name=segment, parent_id=parent_id)
            # La validación de ciclos corre antes de Model.save y, por tanto,
            # antes de enlazar el alias de una fila nueva. Conservar la cadena
            # ya verificada evita que esa lectura consulte default por error.
            parent_field.set_cached_value(category, parent_record)
            if identity is None:
                category.save(using=using, force_insert=True)
                identity_rows.create(
                    module='base', name=xml_id, res_id=category.pk,
                    model=category_model._meta.label, noupdate=True,
                )
            parent_id = category.pk
            parent_record = category
    return parent_id


class FunctionStatus(IntEnum):
    """≙ ``FunctionStatus`` (``odoo19c: odoo/modules/db.py:162-165``)."""

    MISSING = 0    # la función no está (falsy)
    PRESENT = 1    # está, pero no es indexable (no inmutable)
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
    cr.execute("""
        SELECT p.provolatile
        FROM pg_proc p
        WHERE p.proname = 'unaccent'
              AND p.pronamespace = current_schema::regnamespace
              AND p.pronargs = 1
    """)
    result = cr.fetchone()
    if not result:
        return FunctionStatus.MISSING
    return FunctionStatus.INDEXABLE if result[0] == 'i' else FunctionStatus.PRESENT


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
