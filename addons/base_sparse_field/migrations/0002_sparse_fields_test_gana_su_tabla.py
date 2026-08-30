"""``sparse_fields_test`` gana la tabla que su modelo dice tener.

El modelo declara ``managed`` por omisión —es decir, **gestionado**— pero su
``0001_initial`` lo registró con ``"managed": False``, así que su ``CreateModel``
era un ``-- (no-op)`` y la tabla nunca se creó. El desacuerdo no se notaba
mientras nadie la consultara.

Lo destapó ``serialize_db_to_string``, que Django ejecuta al preparar la base de
pruebas y que recorre **todos** los modelos registrados: al llegar a éste falla
con ``relation "sparse_fields_test" does not exist`` y tumba el *setup* de
cualquier caso, sin relación con lo que ese caso mida.

Misma forma que ``base/0072``: ``AlterModelOptions`` por sí solo no crea nada
—medido con ``sqlmigrate``—, así que la tabla se crea en la base y el estado
recibe sólo el cambio de opciones.
"""
import addons.base_sparse_field.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base_sparse_field", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.CreateModel(
                    name="SparseFieldsTest",
                    fields=[
                        ("id", models.BigAutoField(
                            auto_created=True, primary_key=True,
                            serialize=False, verbose_name="ID")),
                        ("data",
                         addons.base_sparse_field.models.fields.Serialized(
                             verbose_name="Datos")),
                    ],
                    options={
                        "db_table": "sparse_fields_test",
                        "verbose_name": "Prueba de campos dispersos",
                        "verbose_name_plural": "Pruebas de campos dispersos",
                    },
                ),
            ],
            state_operations=[
                migrations.AlterModelOptions(
                    name="sparsefieldstest",
                    options={
                        "verbose_name": "Prueba de campos dispersos",
                        "verbose_name_plural": "Pruebas de campos dispersos",
                    },
                ),
            ],
        ),
    ]
