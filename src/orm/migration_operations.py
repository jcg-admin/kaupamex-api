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
