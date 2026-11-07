# El contrato de `MetaModel` frente a `ModelBase` de Django

Referencia: `odoo19c: odoo/orm/models.py:206-292` en `odoo-tools@abe4040ec1`.
Consumer: `kaupamex-api`, `src/models/__init__.py` (pendiente #209).

`MetaModel` es la metaclase de todo modelo en la fuente
(`class BaseModel(metaclass=MetaModel)`, `:334`). Aquí ese papel lo tiene
`django.db.models.base.ModelBase`, porque los modelos del puerto son modelos
de Django. Sustituir la metaclase es una decisión arquitectónica que nadie ha
autorizado, así que el contrato se parte en subcontratos y cada uno se
clasifica por separado.

## Django prístino

Medido con `.venv/bin/python -I` y sin cargar los settings del Consumer:
`ModelBase` declara `__new__`, `add_to_class`, `_prepare`, `_base_manager` y
`_default_manager`. Su `__new__` construye `_meta`, aplica
`contribute_to_class`, resuelve `app_label`, respeta `abstract` y llama a
`apps.register_model`.

## Subcontratos

| Subcontrato (fuente) | Capacidad | Procedencia aquí | Conformidad | Siguiente paso |
|---|---|---|---|---|
| `_module_to_models__`: modelos por módulo, consumido por `Registry.load` (`registry.py:372-375`) | lo trae el stack | `apps.register_model` por `app_label`; `Registry.load` del puerto recorre `apps.get_models()` | divergencia de mecanismo ya declarada en el docstring de `Registry.load` | ninguno |
| `pool`: registro de una clase de registro, `None` en una de definición | no aplica igual | en Django la clase es del proceso, no de una base | divergencia declarada en `Registry` («los ejes derivados se comparten con el proceso») | ninguno |
| `__slots__ = ()` por defecto sobre recordsets | construido | `BaseModel.__slots__` verbatim | `satisfied` en el inventario | ninguno |
| `_field_definitions` / `_table_object_definitions` vía `__set_name__` | lo trae el stack con otra forma | `Field.contribute_to_class` y `Meta.constraints`/`Meta.indexes` | sin medir aquí | pendiente, ligado al porte de campos |
| `_module` derivado de `__module__` (`odoo.addons.<m>`) | lo trae el stack con otra forma | `_meta.app_label` | divergencia de forma | ninguno |
| `_inherit` como texto → lista y `_name` por defecto (`:241-244`) | construible | `extend_model` y el registro por nombre | sin medir aquí | candidato |
| `_name` derivado del nombre de clase con aviso (`:246-249`) | construible | los modelos propios del L0 no declaran `_name` y se nombran por `app.Modelo` | **divergente** | **requiere decisión**: derivarlo cambiaría el nombre de todos los modelos sin `_name` |
| aviso por `__init__` con firma distinta de 4 parámetros (`:258-259`) | construible | sin equivalente | sin medir aquí | candidato menor |
| campos mágicos `create_uid`/`create_date`/`write_uid`/`write_date` según `_log_access` (`:268-292`) | construido | `TimeStampedModel` | divergencia de mecanismo declarada en `atributos-de-clase-de-modelo.md` | ninguno |

## Decisión sobre la clase

No se declara `MetaModel = ModelBase` en `src/models/__init__.py`: ligar el
nombre sería afirmar por coincidencia nominal un contrato que se cumple sólo
en parte. El pendiente #209 queda con esta tabla como su análisis.

*Métrica:* el cuerpo de `MetaModel` en la referencia y los atributos de
`ModelBase` medidos en Django prístino.
*Ciega a:* los subcontratos marcados «sin medir aquí», que necesitan su propia
prueba.
