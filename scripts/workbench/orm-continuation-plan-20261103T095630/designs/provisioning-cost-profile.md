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

## Causa medida (2026-11-12, `outputs/migration-call-profile-2668f944/`)

`probes/migration_call_profile.py` perfila con `cProfile` una sola
migración del log-access a través de `sqlmigrate`, que recorre el camino de
`migrate` sin escribir: `stock.0027_log_access_user_columns` (50
`AddField` de FK a `res.users`).

| Medida | Valor |
|---|---|
| estado previo (`project_state` + render) | 0.60 s |
| aplicar la migración | 37.91 s |
| `state_forwards` → `add_field` → `reload_model` | 37.63 s (99 %) |
| `_reload` → `render_multiple` | 36.24 s |
| `ModelState.render` | 8950 llamadas, 36.14 s |
| `ModelBase.__new__` (clases históricas) | 11 350 llamadas, 20.55 s |
| `orm.fields._field_clone_with_args` | 112 875 llamadas, 15.18 s |
| `orm.fields._field_contribute_to_class` | 131 675 llamadas, 6.41 s |

**Queda medido lo que antes era inferencia.** Para un campo relacional,
`add_field` fija `delay = not field.is_relation` = `False`
(`django/db/migrations/state.py:267`), `_find_reload_model` recoge los
modelos relacionados de forma recursiva (`:385-387`) y `_reload` los
vuelve a construir todos. Con una FK a `res.users` eso son unos 179
modelos por operación (8950 renders / 50 operaciones). El costo crece con
el número de operaciones de estado sobre campos relacionales, no con el
SQL.

Dentro de cada render, los ganchos del ORM sobre `clone` y
`contribute_to_class` pesan una fracción grande; es un segundo frente
medible, independiente de cuántas operaciones haya.

### Consecuencia para la decisión

- La consolidación reduce justo la cantidad medida: de tres operaciones de
  estado por campo (`AddField`, `RenameField`, `AlterField`) a una. La
  estimación es una reducción proporcional del costo del log-access; se
  comprueba midiendo `stock` consolidado con este mismo probe.
- El segundo frente —el costo de los ganchos del ORM por campo clonado en
  un modelo histórico— se mide aparte antes de tocarlo: los modelos
  históricos no necesitan la maquinaria del ORM vivo (la guarda de
  `640628ce` ya los separa de la transacción).

## Operaciones por app, sin base (2026-11-12)

`MigrationLoader(None)` sobre el árbol, sin conexión:

| App | Migraciones | Operaciones | `AddField`/`AlterField` relacionales | `RenameField` |
|---|---|---|---|---|
| `base` | 112 | 860 | 351 | 136 |
| `stock` | 29 | 360 | 172 | 50 |
| `account` | 36 | 226 | 79 | 21 |
| `sale` | 18 | 120 | 43 | 14 |

Cada operación relacional obliga a `ProjectState` a recargar los modelos
relacionados (medido antes: ~179 modelos por operación, 8950 renderizados en
50 operaciones). Por ese criterio el candidato a consolidar con más peso es
`base` (351), no `stock` (172). El experimento con `squashmigrations` se hace
primero sobre `stock` porque su grafo es más pequeño y sus migraciones no
llevan `RunPython`; la medición de `base` queda para después de validar el
procedimiento (instalación nueva, actualización histórica y esquema final
idénticos).

*Métrica:* operaciones declaradas en los archivos de migración.
*Ciega a:* el costo real de cada operación al aplicarla, que depende del
tamaño del grafo de modelos relacionados en ese punto del historial.

## Costo de los ganchos del ORM al renderizar el estado histórico (2026-11-12)

Muestra controlada, sin base: `ProjectState.from_apps(apps).apps` sobre los
450 modelos del árbol (`probes/historical_render_cost.py`,
`probes/historical_render_profile.py`).

- Un renderizado completo: **1.017 s** (media de 3). Saltar la instalación de
  descriptores del ORM en modelos de `StateApps`: **0.988 s** (−3 %).
- Perfil de un renderizado (1.78 s bajo cProfile): `Field.clone` 0.80 s, casi
  todo de Django (`deconstruct` de ForeignKey 0.43 s, con
  `swappable_setting`/`get_swappable_settings_name` 0.37 s);
  `_field_contribute_to_class` 0.34 s; `_field_setup_attrs` 0.16 s;
  `_field_deconstruct_without_copy` 0.17 s. El `deconstruct` de
  `fields_temporal.py:651` (0.30 s, 756 llamadas) sólo delega en el de
  ForeignKey: son `create_uid`/`write_uid` de 378 modelos.

Conclusión medida: los ganchos propios del ORM son una minoría del costo de
renderizar (del orden de un tercio bajo el perfilador, y saltar lo único que
no hace falta en un modelo histórico rinde un 3 %). Los 15.2 s y 6.4 s de la
medición anterior eran acumulados de todo un `migrate`, no de un
renderizado. La palanca es el **número de renderizados** (≈179 modelos por
operación relacional), no el costo de cada uno: la consolidación de
migraciones, no la poda de ganchos. No se cambia el gancho.

*Métrica:* reloj de pared de `StateApps` sobre el registro completo, y
tiempo acumulado por función con cProfile. Medido con el gate completo
ocupando la CPU: el valor absoluto varía (1.017 s y 1.344 s en dos
ejecuciones de `base`); la comparación base/skip se hizo en ejecuciones
consecutivas.
*Ciega a:* el costo de las operaciones SQL de la migración, que se mide
aparte con el perfil por migración.
