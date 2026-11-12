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
