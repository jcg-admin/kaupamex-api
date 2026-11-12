# Perfil del costo de aprovisionamiento de una base nueva

Unidad de TASK-API-0485 (hija B, consecuencia medida). La ejecución de
ci-multidb sobre `640628ce` tardó 8142 s con `--create-db`, contra un
máximo de unos 2000 s por prueba en las ejecuciones anteriores. La
hipótesis —las 752 `AlterField` de las columnas de usuario borran y
recrean su FK— **no está medida**. Este diseño fija cómo se mide antes de
decidir ninguna corrección.

## Qué se mide y con qué

Instrumento: `probes/provisioning_profile.py`, que ejecuta el `migrate`
real de Django sobre una base desechable y atribuye cada sentencia SQL a la
fase y a la migración que la emitió. Usa sólo lo instalado:

| Necesidad | Primitiva de Django (TRAE) |
|---|---|
| sentencias, duración y filas | `connection.execute_wrapper` (`django/db/backends/utils.py`) |
| migración en curso y su pared | envoltura de `Migration.apply` en el proceso del probe |
| pared de la carga de datos | envoltura de `emit_post_migrate_signal` en el proceso del probe |
| pared total | `call_command('migrate')` |

El probe no modifica el producto: las envolturas viven en su proceso.

Por migración registra: aplicación, nombre, operaciones y sus tipos, pared,
tiempo en SQL, sentencias, FK eliminadas, FK creadas, índices, renombres,
DML y filas afectadas. La diferencia entre pared y SQL es el costo de
Python: mutar y renderizar el estado de migraciones.

Clases de sentencia: `drop_constraint`, `add_fk`, `add_constraint`,
`create_index`, `drop_index`, `create_table`, `rename_column`,
`alter_column`, `dml`, `select`, `other`.

## Lo que el perfil no ve

- Esperas por bloqueo: el probe es la única sesión sobre su base, así que
  no hay contención por construcción; la duración de un `ALTER` incluye su
  propia adquisición de bloqueo.
- El costo de las pruebas mismas y de la creación de varias bases en una
  prueba: el perfil mide **una** instalación. ci-multidb construye la base
  de pruebas y una base por empresa; el total se compara multiplicando y
  se declara como estimación.
- El tamaño del registro de modelos vivo (arranque de Django), que se mide
  aparte como pared del arranque.

## Criterio de decisión

Se elige entre tres alternativas sólo con el perfil delante:

1. corregir las operaciones que emiten DDL innecesario;
2. consolidar migraciones con el mecanismo de Django sin romper las rutas
   de actualización;
3. mantener la secuencia cuando la operación sea contractual.

## Resultado (2026-11-12, revisión 32085975, base desechable)

Salidas: `outputs/provisioning-profile-32085975-20261112T002155/` (`migrations.tsv`, `phases.tsv`,
`slow_statements.tsv`).

| Fase | Pared (s) | SQL (s) |
|---|---|---|
| arranque de Django | 1.5 | — |
| 710 migraciones aplicadas (`Migration.apply`) | 2599.6 | 17.5 |
| `post_migrate` (carga de módulos) | 7.2 | 3.0 |
| fuera de `apply` (estado, `createcachetable`) | 0.0 | 5.6 |
| **`migrate` total** | **2621.4** | — |

**El 99.3 % del costo es Python, no SQL**: 2582 s de 2600 en las
migraciones. Las 12 974 sentencias SQL suman 17.5 s.

**La hipótesis queda refutada.** Las 230 migraciones del log-access cuestan
1875 s (72 %), y de ellos 7 s son SQL; sus 752 `ADD CONSTRAINT … FOREIGN
KEY` suman menos de un segundo por migración. El costo no está en borrar y
recrear las FK sino en la maquinaria de estado de Django.

Por tipo de operación (Python atribuido al tipo dominante de la migración):

| Operación | Operaciones | Python (s) | s/op |
|---|---|---|---|
| AddField | 1476 | 911 | 0.62 |
| AlterField | 1194 | 838 | 0.70 |
| RenameField | 822 | 613 | 0.75 |
| CreateModel | 453 | 161 | 0.36 |

Las tres migraciones más caras son de `test_orm` (164, 119 y 112 s, 106
operaciones cada una); la app de pruebas suma 437 s en sus 48 migraciones.

**Causa inferida, no medida todavía:** cada operación sobre un campo que
apunta a `res.users` recarga en el `ProjectState` los modelos
relacionados, y con cientos de FK hacia el usuario el costo por operación
es alto. Condición de cierre: un `cProfile` de una sola migración del
log-access que muestre el tiempo en `StateApps`/`reload_model`.

ci-multidb construye la base de pruebas y las de empresa: tres
instalaciones de unos 2600 s explican los 8142 s observados (estimación).

## Decisión

Con el costo en el número de operaciones de estado, no en el SQL:

1. **Descartada** la corrección del DDL (alternativa 1): no hay DDL caro.
2. **Elegida para medir primero** la consolidación del trío del log-access
   por app (`*_log_access_user_columns`, `*_date_names`,
   `*_user_column_names`) con `squashmigrations`: el optimizador de Django
   funde `AddField` + `AlterField` en un `AddField` y `AddField` +
   `RenameField` en uno, de unas tres operaciones por campo a una. Las bases
   ya migradas siguen la historia por `replaces`. Antes de adoptarla: medir
   la reducción en una app (`stock`, 150 s hoy) y probar las dos rutas
   (instalación nueva y base en la revisión anterior).
3. Medir aparte si `test_orm` tiene que migrarse en una instalación de
   producción.
