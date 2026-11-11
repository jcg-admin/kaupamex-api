# DEC-09: autoinyección del log-access en los modelos sin la base común

Fecha: 2026-11-11 · TASK-API-0485, hija C de `designs/log-access-columns-audit.md`.
Directiva del ejecutor del 2026-11-11: «DEC-09 no debe permanecer diferida
únicamente porque determinados modelos no heredan `TimeStampedModel`».

## Contrato (odoo-tools `abe4040ec1`)

- `odoo19c: odoo/orm/models.py:283-292`: el metaclase añade las cuatro
  columnas si `attrs.get('_log_access', self._auto)`. Es decir, a todo modelo
  con tabla salvo que declare `_log_access = False`. `add_default` no pisa un
  campo declarado.
- `odoo/orm/model_classes.py:267`: `_log_access = _auto`. `:278` lo hereda de
  las bases. `:556-574`: en un modelo `_auto=False` (una vista) vale
  `set(LOG_ACCESS_COLUMNS) <= columns`, es decir, solo si la vista expone las
  cuatro.
- Las tablas de relación de un Many2many no son modelos y no llevan columnas.

## Población medida (2026-11-11)

De 96 modelos concretos sin `TimeStampedModel` ni `TransientModel`:

- 28 llevan `_name` propio (`model.__dict__['_name']`); los demás son tablas
  intermedias de M2M y modelos propios sin contraparte.
- De los 28: 26 son administrados. `ir.autovacuum` no lo es (en la fuente es
  `AbstractModel`) y `hr.employee.public` es una vista con `_auto=False`.
- `ir.model.inherit` declara `_log_access = False` → se excluye.
- **Ninguno** de los 26 tiene alguna de las cuatro columnas. Les faltan
  también las fechas, no solo los usuarios.

Población a inyectar: 25 modelos administrados con `_name` propio, `_auto`
verdadero y `_log_access` no falso. Entre ellos están `ir.attachment`
(desbloquea la regla «solo su creador» de `attachment-record-access`),
`ir.cron`, `res.country`, `res.currency`, `res.lang`, `account.account`,
`account.move.line`, `account.journal` y `account.tax`.

## Decisión — CONSTRUYE con el mecanismo existente

**TRAE:** Django contribuye un campo a una clase ya preparada con
`add_to_class` (`django/db/models/base.py`, `ModelBase.add_to_class`), y
`Options.add_field` vacía sus cachés. El árbol ya lo usa así en
`adopt_display_name` (`src/orm/model_classes.py:424-561`): una
`copy.deepcopy` del campo declarado en el mixin, con un discriminador por
contenido.

**CONSTRUYE:** `adopt_log_access(model_cls)` en `src/orm/model_classes.py`,
colgado de `class_prepared` como sus hermanos. Instala las cuatro columnas
(`create_uid`, `created_at`, `write_uid` y `updated_at` mientras dure el
nombre de la hija B) copiando los campos de `TimeStampedModel`, que es la
única fuente de su declaración. Se instalan si se cumple todo esto:

- el modelo es concreto, no proxy y administrado;
- declara `_name` en su propio `__dict__` (los que lo heredan de un mixin,
  como `mail.thread` en `analytic`, no cuentan como nombre propio; se
  verifica);
- es administrado (`Meta.managed`, la equivalencia de `_auto` que el árbol
  declara en `src/orm/models.py:10938-10939`) y
  `getattr(model, '_log_access', True)` es verdadero. **No** se lee el
  atributo `_auto`: `orm.models.BaseModel` declara `_auto = False`, como la
  `BaseModel` de la fuente (`:370`), pero aquí no hay una `Model` que lo
  devuelva a `True` (`:7060`). Medido: los 86 herederos concretos de
  `BaseModel`, `ir.attachment` y `res.users` incluidos, leen `_auto=False`
  teniendo tabla;
- ninguna columna existe ya: ni en el modelo ni en un padre multitabla, para
  que `add_default` no pise y Django no dé `fields.E005`.

Devuelve cuántas columnas instaló, para medir en lugar de suponer.

`hr.employee.public` (`_auto=False`): **corregido tras medir.** La fuente
declara `_auto = False` y `_log_access = True  # Include magic fields`
(`odoo19c: addons/hr/models/hr_employee_public.py:14-15`), así que la vista
expone las cuatro columnas. Aquí declara solo `create_date`. La regla
general no la cubre, porque `_auto` es falso. Se trata aparte: la vista
selecciona también `create_uid`, `write_uid` y `write_date` desde
`hr_employee`, que ya los tiene por la unidad A, y el modelo no administrado
declara los cuatro campos. Prueba: leer las cuatro columnas de la vista
devuelve los valores de su empleado.

## Migraciones

Las columnas inyectadas forman parte del estado de los modelos, así que
`makemigrations` las detecta. Se genera una migración por app afectada, solo
con `AddField` y columnas nulas. Las filas existentes quedan con `NULL` en
los usuarios y la fecha de la migración en las fechas: `auto_now_add` en un
`AddField` necesita un valor por defecto, y se usa `django.utils.timezone.now`
en la migración, como el `ALTER` de la fuente, que rellena con `now()`.

## Pruebas

- Inyección: los 25 modelos tienen las cuatro columnas; `ir.model.inherit`
  (`_log_access=False`) y una tabla de M2M no las tienen.
- Funcional: alta y escritura en un modelo inyectado (`res.country`) fijan
  los usuarios y las fechas por `write()` del ORM.
- Idempotencia: llamar dos veces a `adopt_log_access` devuelve 0 la segunda.
- Registro tardío: una clase creada después del arranque (dentro de
  `isolate_apps`) recibe las columnas por la señal.
- Anulación: sin el receptor, caen los casos de inyección y los funcionales.
- `makemigrations --check` vacío y ci-multidb, porque las columnas llegan a
  las bases de compañía.

## Lo que no cierra

El nombre de las fechas sigue la hija B (`designs/log-access-date-names.md`).

## Incidencia registrada (2026-11-11)

Para generar las migraciones con el valor por defecto de `auto_now_add`
(`makemigrations --no-input` se niega: «impossible to add a field with
'auto_now_add=True' without specifying a default»), un script llamó al
`MigrationAutodetector` con un questioner que responde `timezone.now`. El
script no recortaba los cambios a las apps del proyecto y escribió cuatro
archivos en `.venv/…/django/contrib/{contenttypes,sessions,admin,auth}/migrations/`.

- Se retiraron en el mismo pase (`find .venv -name '*log_access_auto*'` → 0).
- Ninguna base los aplicó: `django_migrations` da 0 filas con ese nombre en
  las 15 bases `orm_x2hokp*`.
- `makemigrations --check --dry-run` en el worktree: «No changes detected».
- El script rehúsa ahora escribir fuera del árbol del proyecto.

El stack instalado no se modificó de forma persistente.

