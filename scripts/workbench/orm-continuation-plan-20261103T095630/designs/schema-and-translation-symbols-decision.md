# Símbolos de esquema y de traducción de `BaseModel` — decisión pendiente

Fecha: 2026-11-10. Referencia: odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389`, `odoo19c: odoo/orm/models.py`.
Clasificación: `outputs/obligation_classification.tsv`, los seis
`absent / task_without_unit` bajo TASK-API-0485.

## Lo medido

| Símbolo | Referencia | Llamador en la fuente | Aquí |
|---|---|---|---|
| `_auto_init` | `:3170-3248` (79 líneas) | `registry.init_models` (`registry.py:751`) | `migrate` de Django crea y altera tablas; `_check_parent_path` ya vive en `check()` |
| `_check_removed_columns` | `:3109-3136` | `_auto_init` (`:3217`), `modules/loading.py:518` | sin equivalente: ninguna pieza quita el `NOT NULL` de una columna que el modelo ya no declara |
| `_add_sql_constraints` | `:3262-3268` | `_auto_init` (`:3244`) | `TableObject.apply_to_database` existe (`src/orm/table_objects.py:236,294,390`) y `_table_objects` también (`models.py:6101`), pero `apply_to_database` no tiene llamador fuera de pruebas: las restricciones van por `Meta.constraints` y migraciones |
| `get_field_translations` | `:3664-3703` | vistas y `web` | `translate=True` sólo se anota; la columna es `varchar` de un idioma (`models.py`, `copy_translations`) |
| `update_field_translations` | `:3492-3503` | `copy_translations`, `web` | ídem |
| `_update_field_translations` | `:3504-3663` (160 líneas) | `update_field_translations` | ídem |

## Por qué no se deriva aquí

- **Esquema:** portar los tres métodos sin llamador deja código muerto;
  cablearlos (por ejemplo, desde la instalación de módulos de
  `kaupamex-bin`) decide que el ORM, y no las migraciones, es dueño del
  esquema. Es una decisión de arquitectura.
- **Traducciones:** el cuerpo exige el almacenamiento `jsonb {lang: valor}`
  de los campos traducibles. El sucesor citado en `copy_translations` es
  «tarea **#333**», un ordinal del tablero sin cita durable.

## Opciones (para el ejecutor)

1. Esquema — (a) declarar la divergencia de mecanismo en `models.py`
   (las migraciones son dueñas del esquema) y cerrar los tres; (b) portar
   y cablear `_auto_init` en la instalación de módulos; (c) portar sólo
   `_check_removed_columns` como paso de `kaupamex-bin`, que es el único sin
   equivalente.
2. Traducciones — abrir la unidad del almacenamiento `jsonb` (migración de
   las columnas traducibles), con los tres métodos encima; o mantenerlas
   bloqueadas por esa pieza, con cita durable en lugar de `#333`.

Lo que este registro no cierra: la elección. Hasta entonces los seis
siguen `absent` en la clasificación y no se declaran resueltos.
