"""Operaciones de migración del ORM.

La autoridad del esquema en este árbol son las migraciones de Django
(TASK-API-0515 vigila que sigan a los modelos). Lo que la referencia hace en
``BaseModel._auto_init`` al crear una columna (``odoo19c:
odoo/orm/models.py:3170-3248``) y que una ``AddField`` no hace vive aquí,
como operación de migración, para no abrir una segunda autoridad.
"""
from django.apps import apps as live_apps
from django.db import connections, migrations
from django.db.models import Model
from psycopg import sql as pg_sql

from orm import registry
from orm.environments import Environment
from orm.utils import SUPERUSER_ID, model_field_registry


class ComputeStoredFields(migrations.RunPython):
    """Calcula sobre las filas existentes unos calculados almacenados nuevos.

    ≙ ``odoo19c: odoo/orm/models.py:3220-3238``: una columna calculada nueva
    marca para cómputo todas las filas que ya existen (*"so that computed
    required fields are flushed before the NOT NULL constraint is added to
    the database"*). Aquí la migración que añade la columna la sigue con esta
    operación (TASK-API-0516).

    Usa la clase vigente del modelo y no la histórica: el cómputo necesita
    sus métodos, que el modelo histórico no tiene, igual que la fuente
    calcula con el código instalado. La reversa no deshace nada.
    """

    def __init__(self, app_label, model_name, field_names):
        self.app_label = app_label
        self.model_name = model_name
        self.field_names = list(field_names)
        super().__init__(self._compute, migrations.RunPython.noop)

    def _compute(self, apps, schema_editor):
        model = live_apps.get_model(self.app_label, self.model_name)
        connection = schema_editor.connection
        # El modelo vigente puede declarar columnas que añade una migración
        # posterior; calcular ahora nombraría columnas que la tabla aún no
        # tiene. Se espera al ``post_migrate`` (designs/compute-new-stored-
        # columns.md, revisión 2026-11-11).
        if _schema_lags(model, connection):
            PENDING_COMPUTES.setdefault(connection.alias, []).append(self)
            return
        self.compute_now(connection.alias)

    def compute_now(self, using):
        """Calcula sobre las filas de la base ``using``, la que migra.

        ≙ la fuente, que calcula con el ``env`` del cursor que migra. El
        entorno declara esa conexión: ``get_current_cr()`` manda sobre la
        empresa activa en el router (``orm.routers.domain_alias``), así que
        la lectura de los ids, el cómputo y el volcado van a ``using``. Con
        ``Environment(None, ...)`` el entorno no declaraba base y, en una
        base de empresa, el cálculo no la alcanzaba
        (``designs/seeded-partner-computes.md``).
        """
        model = live_apps.get_model(self.app_label, self.model_name)
        fields_of = model_field_registry(model)
        with Environment(using, SUPERUSER_ID, {}) as environment:
            ids = list(model._base_manager.values_list('pk', flat=True))
            if not ids:
                return
            # La columna es nueva: su valor almacenado es desconocido. Sin
            # retirar la caché, un cómputo que coincide con lo que la caché
            # ya tenía no marca nada sucio y el volcado no escribe.
            # Por el registro de campos y no por ``_fields``: un modelo de
            # Django con un relacionado almacenado (``account.move.line``
            # ``parent_state``) no lleva ``_fields``. Es lo que
            # ``_invalidate_cache`` hace campo a campo.
            for name in self.field_names:
                invalidate = getattr(fields_of[name], '_invalidate_cache',
                                     None)
                if invalidate is not None:
                    invalidate(environment, ids)
            for name in self.field_names:
                environment.add_to_compute(fields_of[name], ids)
            Model.flush_model(model, self.field_names)

    def deconstruct(self):
        return (self.__class__.__qualname__,
                [self.app_label, self.model_name, self.field_names], {})

    def describe(self):
        return (f'Compute {", ".join(self.field_names)} on '
                f'{self.app_label}.{self.model_name}')


class RewriteModelIdentities(migrations.RunPython):
    """Reescribe una columna que nombra modelos a su identidad contractual.

    ≙ el valor que la fuente guarda en esas columnas: ``'model':
    model._name`` (``odoo19c: odoo/addons/base/models/ir_model.py:428``).
    Este árbol guardó la etiqueta de Django (``base.ResPartner``) hasta el
    corte C3 de ``designs/model-identity-contract.md``; la operación lleva
    cada valor a :func:`orm.registry.identity_for_key`, que resuelve contra
    el registro vigente —el mismo criterio que :class:`ComputeStoredFields`:
    la identidad la declara el código instalado, no el modelo histórico—.

    Un valor que ya es identidad, o que no nombra ningún modelo vigente, se
    queda como está. Si ``unique_with`` nombra las columnas de una restricción
    única y la reescritura chocaría con una fila existente, la operación
    rehúsa y lista los choques en vez de fundir filas que pueden tener
    referencias propias. La reversa no deshace nada.
    """

    def __init__(self, table, column, unique_with=None):
        self.table = table
        self.column = column
        self.unique_with = tuple(unique_with or ())
        super().__init__(self._rewrite, migrations.RunPython.noop)

    def _rewrite(self, apps, schema_editor):
        table = pg_sql.Identifier(self.table)
        column = pg_sql.Identifier(self.column)
        with schema_editor.connection.cursor() as cr:
            cr.execute(pg_sql.SQL(
                'SELECT DISTINCT {col} FROM {tbl} WHERE {col} IS NOT NULL'
            ).format(col=column, tbl=table))
            mapping = {}
            for (value,) in cr.fetchall():
                identity = registry.identity_for_key(value)
                if identity != value:
                    mapping[value] = identity
            if not mapping:
                return
            self._reject_collisions(cr, table, column, mapping)
            for old, new in mapping.items():
                cr.execute(pg_sql.SQL(
                    'UPDATE {tbl} SET {col} = %s WHERE {col} = %s'
                ).format(tbl=table, col=column), [new, old])

    def _reject_collisions(self, cr, table, column, mapping):
        """Rehúsa si la reescritura duplicaría una clave única."""
        if self.column not in self.unique_with:
            return
        partners = [
            pg_sql.Identifier(name) for name in self.unique_with
            if name != self.column]
        key = pg_sql.SQL(', ').join(
            [pg_sql.SQL('a.{}').format(name) for name in partners]
            or [pg_sql.SQL('1')])
        on = pg_sql.SQL(' AND ').join(
            [pg_sql.SQL('b.{0} = a.{0}').format(name) for name in partners]
            or [pg_sql.SQL('TRUE')])
        collisions = []
        for old, new in mapping.items():
            cr.execute(pg_sql.SQL(
                'SELECT {key} FROM {tbl} a JOIN {tbl} b ON {on} '
                'AND b.{col} = %s WHERE a.{col} = %s'
            ).format(key=key, tbl=table, on=on, col=column), [new, old])
            collisions.extend((old, new, row) for row in cr.fetchall())
        if collisions:
            raise ValueError(
                f'{self.table}.{self.column}: la identidad contractual ya '
                f'existe para {len(collisions)} filas: {collisions[:20]!r}')


class ConvertColumnTranslatable(migrations.AlterField):
    """``AlterField`` que convierte la columna por el campo de destino.

    ≙ ``Field.update_db_column`` → ``_convert_db_column`` (``odoo19c:
    odoo/orm/fields.py:1112-1143``, ``fields_textual.py:64-68``): cuando el
    tipo de la columna no coincide con el del campo, el ORM la convierte, y
    hacia o desde ``jsonb`` traducible pasa por
    ``convert_column_translatable`` (el texto queda bajo ``en_US``).

    El estado lo cambia ``AlterField`` y la base la convierte el campo del
    estado de destino con su propio ``_convert_db_column``; en la reversa el
    destino es el estado anterior, así que el ``jsonb`` vuelve a texto. No va
    dentro de un ``SeparateDatabaseAndState``: ahí cada operación de base
    recibe el estado viejo más su propio ``state_forwards``, y vería el campo
    anterior (medido: la columna seguía en ``varchar`` con la migración
    aplicada). TASK-GEN-0060.
    """

    def database_forwards(self, app_label, schema_editor, from_state,
                          to_state):
        self._convert(app_label, schema_editor, to_state)

    def database_backwards(self, app_label, schema_editor, from_state,
                           to_state):
        self._convert(app_label, schema_editor, to_state)

    def _convert(self, app_label, schema_editor, state):
        model = state.apps.get_model(app_label, self.model_name)
        if not self.allow_migrate_model(schema_editor.connection.alias,
                                        model):
            return
        field = model._meta.get_field(self.name)
        with schema_editor.connection.cursor() as cr:
            cr.execute(
                'SELECT udt_name FROM information_schema.columns'
                ' WHERE table_schema = current_schema()'
                ' AND table_name = %s AND column_name = %s',
                [model._meta.db_table, field.column])
            row = cr.fetchone()
            if row is None or row[0] == field.column_type[0]:
                return
            field._convert_db_column(model, {'udt_name': row[0]}, cr=cr)

    def describe(self):
        return (f'Alter field {self.name} on {self.model_name} and convert'
                ' its column')


#: Cómputos que esperan a que el esquema del modelo esté completo, por alias
#: de base. Los llena ``ComputeStoredFields`` y los vacía el ``post_migrate``.
PENDING_COMPUTES = {}


def _schema_lags(model, connection):
    """¿Le falta a la tabla alguna columna concreta del modelo vigente?"""
    with connection.cursor() as cursor:
        present = {column.name for column in
                   connection.introspection.get_table_description(
                       cursor, model._meta.db_table)}
    declared = {field.column for field in model._meta.concrete_fields}
    return not declared <= present


def run_pending_computes(using='default', **kwargs):
    """Receptor de ``post_migrate``: ejecuta los cómputos en espera de la base
    ``using`` cuyo esquema ya está completo.

    Un ``migrate`` parcial (``migrate base 0106``) también emite
    ``post_migrate`` con el esquema aún atrasado: lo que sigue atrasado
    queda en la cola para el siguiente.
    """
    connection = connections[using]
    waiting = []
    for operation in PENDING_COMPUTES.pop(using, []):
        model = live_apps.get_model(operation.app_label, operation.model_name)
        if _schema_lags(model, connection):
            waiting.append(operation)
        else:
            operation.compute_now(using)
    if waiting:
        PENDING_COMPUTES[using] = waiting
