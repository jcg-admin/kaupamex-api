# Un modelo de un registro de apps aislado no entra en el registro por nombre

Fecha: 2026-11-11T07:04:32 · TASK-API-0515 (unidad de raíz ORM)

## Síntoma medido

El derivado del tramo HR/órdenes de trabajo dio 3484 passed y 23 errors con
`-n 4`. La reejecución con traza dio en los 23 el mismo error, en el teardown:

```
ValueError: Table base_parentpathprobe0 of model test.parent.path.probe0
does not exist in database default: its migration is missing
```

Cadena de llamadas:

- `tests/conftest.py:481` `pytest_runtest_teardown` → `_install_modules` (`:396`)
- → `src/modules/loading.py:239` `load_modules`, que elige los modelos de cada
  paquete por `registry.models` filtrando por `_meta.app_label`
- → `src/orm/registry.py` `init_models` → `src/orm/models.py` `_auto_init`.
  Desde `555ac073`, `_auto_init` exige la tabla del modelo.

El error depende del orden de ejecución. Solo aparece en el worker que ya
ejecutó `tests/unit/orm/test_parent_path_check.py`, cuya `_probe()` crea
`test.parent.path.probe{N}` con `app_label='base'` dentro de
`isolate_apps()`. No lo causa PROTECT. El diseño de país atribuía los errores
a una causa «no determinada»; esta es la causa.

## Causa

`_register` (`src/orm/registry.py:347-367`) cuelga de `class_prepared` y
anota `MODELS_BY_NAME[name] = model` sin mirar a qué registro de apps
pertenece la clase. `isolate_apps()` crea un `Apps` propio
(`django/test/utils.py`, `isolate_apps`), pero `class_prepared` es una señal
global, así que la sonda entra en el mapa global y no sale nunca. A partir de
ahí `Registry.models = dict(MODELS_BY_NAME)` la trata como un modelo
instalado de `base`.

## Contrato de la fuente

En Odoo, un modelo pertenece al `Registry` de la base que lo carga
(`odoo19c: odoo/orm/registry.py:84`, `self.models`). No existe un mapa global
de clases fuera de ese registro: una clase que no carga el registro no forma
parte de él. El equivalente aquí del registro cargado es el `Apps` global de
Django (`django.apps.apps`). Un `Apps` aislado es otro registro.

## Decisión — CONSTRUYE, mínimo

`_register` ignora una clase de Django cuyo `_meta.apps` no es
`django.apps.apps`. Las clases sin `_meta` (el equivalente del
`AbstractModel`, por ejemplo `IrFieldsConverter`) siguen registrándose como
hasta ahora. `_ensure_seeded` recorre `apps.get_models()`, que ya es global.

Censo previo: de los 16 archivos de prueba que usan `isolate_apps`, solo las
sondas de `test_parent_path_check` declaran `_name`, y ninguna prueba
resuelve un modelo aislado por nombre. Esas pruebas llaman a métodos de la
propia clase. El filtro no retira nada que alguien consuma.

## Pruebas

- RED: crear una sonda con `_name` dentro de `isolate_apps()` y afirmar que no
  está en `MODELS_BY_NAME`, ni en `Registry(alias).models`, ni entre los
  `model_names` de `base` de `load_modules`.
- Control positivo: un modelo global sigue registrado (`ir.ui.menu`).
- Anulación: con el filtro retirado debe caer exactamente la aserción de
  ausencia y nada más.
- Derivado: `tests/unit/orm/` y, a continuación, el derivado HR con `-n 4`.
  Los 23 errores tienen que desaparecer.

## Lo que no cierra

No limpia las entradas de un `Apps` aislado que haya registrado algún otro
mecanismo (por ejemplo `_rec_name` en `model_classes`). Ese receptor solo
modifica la propia clase y no publica en un mapa global, así que no hay
fuga que cerrar.
