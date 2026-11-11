"""Operaciones de migración del ORM.

La autoridad del esquema en este árbol son las migraciones de Django
(TASK-API-0515 vigila que sigan a los modelos). Lo que la referencia hace en
``BaseModel._auto_init`` al crear una columna (``odoo19c:
odoo/orm/models.py:3170-3248``) y que una ``AddField`` no hace vive aquí,
como operación de migración, para no abrir una segunda autoridad.
"""
from django.apps import apps as live_apps
from django.db import migrations
from django.db.models import Model

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
        self.compute_now()

    def compute_now(self):
        model = live_apps.get_model(self.app_label, self.model_name)
        ids = list(model._base_manager.values_list('pk', flat=True))
        if not ids:
            return
        fields_of = model_field_registry(model)
        with Environment(None, SUPERUSER_ID, {}) as environment:
            # La columna es nueva: su valor almacenado es desconocido. Sin
            # retirar la caché, un cómputo que coincide con lo que la caché
            # ya tenía no marca nada sucio y el volcado no escribe.
            Model._invalidate_cache(model, self.field_names, ids)
            for name in self.field_names:
                environment.add_to_compute(fields_of[name], ids)
            Model.flush_model(model, self.field_names)

    def deconstruct(self):
        return (self.__class__.__qualname__,
                [self.app_label, self.model_name, self.field_names], {})

    def describe(self):
        return (f'Compute {", ".join(self.field_names)} on '
                f'{self.app_label}.{self.model_name}')


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
    ``using`` con el esquema ya completo, y vacía su cola."""
    for operation in PENDING_COMPUTES.pop(using, []):
        operation.compute_now()
