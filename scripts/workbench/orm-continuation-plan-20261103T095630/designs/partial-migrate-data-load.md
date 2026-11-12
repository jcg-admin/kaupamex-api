# Carga de datos con el esquema a medio migrar

Unidad del ciclo de instalación (`designs/module-install-cycle.md`, L3).

## El defecto

`load_modules_after_migrate` corre en `post_migrate` y su docstring afirma
que ahí «el esquema de todas las apps está al día». Es falso tras una
migración parcial: `migrate <app> <migración>` también emite `post_migrate`
con `plan`, y entonces `load_modules` inicializa modelos y carga los datos
de módulos cuyas tablas todavía no tienen las columnas del modelo vivo. El
síntoma ya medido fue la carga de `post_migrate` sobre un esquema atrasado
(designs/compute-new-stored-columns.md).

## Lo que hace la fuente

`odoo19c: odoo/modules/loading.py` (`load_module_graph`): por módulo, en
orden de grafo, `registry.init_models(...)` crea o ajusta las tablas del
módulo **antes** de `load_data`, y el módulo queda `installed` sólo al final.
En Odoo el esquema lo construye el propio ORM, así que nunca va detrás de los
datos: la precondición «tablas del módulo al día antes de sus datos» se
cumple por construcción.

## Lo que hace este árbol

El esquema lo construyen las migraciones de Django, y su estado real lo
conoce `MigrationExecutor`: `migration_plan(loader.graph.leaf_nodes())`
lista las migraciones que faltan en el alias (TRAE; mismo cálculo que
`migrate --check`). Un módulo está listo para sus datos sólo si:

1. su app no tiene migraciones pendientes, y
2. ninguno de los módulos de los que depende fue omitido.

Si no está listo, `load_modules` lo omite: no inicializa sus modelos, no
carga sus datos, no lo marca `installed`, y lo registra con su lista de
migraciones pendientes. Un `migrate` posterior que complete el esquema
emite de nuevo `post_migrate` y lo instala en modo `init`.

No es un reintento ni oculta errores: un error de migración aborta antes de
`post_migrate`, y un error de datos sigue revirtiendo sólo ese módulo
(`test_a_failing_module_leaves_none_of_its_rows`).

## Verificación

- migración pendiente en `hr`: ni `hr` ni sus dependientes quedan
  `installed`, ni su XML-ID de modelo aparece; `base` sí se instala;
- sin migraciones pendientes, el ciclo instala todo (prueba existente);
- reejecución: completar el esquema y volver a correr instala lo omitido
  sin duplicar filas (XML-ID);
- base de empresa: el receptor ya retorna antes por el router.
