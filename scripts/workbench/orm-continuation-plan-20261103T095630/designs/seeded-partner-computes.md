# Los contactos sembrados por migración, sin sus calculados almacenados

Diagnóstico medido el 2026-11-16T21:01:57 sobre el fallo del gate ci-multidb de
`a3723a61` (`outputs/gates/ci-multidb-a3723a61/`, revisión registrada
`9d1f1adf`: `a3723a61` más un commit sólo de diseño).

## El fallo

14 de 15 pruebas de `test_multidb_isolation.py` en `ERROR`, las 14 con la
misma causa al aprovisionar una base de empresa:

```text
tools.convert.ParseError: while parsing addons/account/security/account_security.xml:247
Dominio inválido: AttributeError("'NoneType' object has no attribute 'id'")
"[... ('partner_id','child_of',[user.commercial_partner_id.id])]"
```

## La causa, medida

1. `ir.rule._check_domain` evalúa el dominio con `user` = el usuario del
   entorno, que al cargar módulos es `SUPERUSER_ID` (`modules/loading.py:252`).
2. `base.partner_root` lo crea la migración `0106_seed_root_user` con el
   modelo **histórico**, que no ejecuta cómputos: su `commercial_partner_id`
   queda nulo. Lo mismo `base.public_partner` (`0113`).
3. En `orm_x2hokp_qa` el valor existe (`5730 → 5730`) porque los
   sembradores de `tests/conftest.py` vuelven a pasar con los modelos vivos.
   Por eso la suite completa sale verde y sólo una base construida desde
   cero falla.
4. La regla es la primera que lee `user.commercial_partner_id`; entró con
   `4068c254` («Load the account security of the reference»), posterior al
   último aprovisionamiento verde (`b314f6e7`). El arreglo de NewId de
   `a3723a61` no interviene.

Descartado midiendo: que el contacto no se calcule al crearse (por Django y
por el ORM se calcula, `7244 → 7244`), y que usuario y contacto se lean en
bases distintas (el router manda los dos a la base del entorno).

## La fuente

El contacto se crea por el ORM y `_compute_commercial_partner` lo apunta a
sí mismo cuando no tiene padre (`odoo19c: odoo/addons/base/models/
res_partner.py:515-528`). Una columna calculada sobre filas existentes la
calcula el ORM (`odoo19c: odoo/orm/models.py:3220-3238`).

## El arreglo

`base/migrations/0116_partner_commercial_fields.py`:
`ComputeStoredFields('base', 'respartner', ['commercial_partner_id',
'commercial_company_name'])`, después de toda migración que siembra
contactos. Es el mecanismo de TASK-API-0516; en una base de empresa corre
dentro del `company_scope` de `_migrate_company_database`, y si el esquema
va atrasado espera al `post_migrate`, que lo vacía antes de cargar datos
(`addons/base/apps.py:131-135`).

No se tocó `seed_root_user`: copiar el cómputo en la siembra sería una
segunda fuente de verdad del cómputo.

## Verificación

- `tests/unit/base/test_partner_commercial_fields_migration.py`, 5 pruebas.
  Anulación (calcular sólo `commercial_company_name`): caen exactamente las
  4 que dependen de `commercial_partner_id`; sobrevive la de dependencias.
- El contrato real es aprovisionar desde cero: ci-multidb vuelve a correr.

## Ejecución invalidada por la propia observación (2026-11-16T22:28:48)

El gate ci-multidb de `db586906` (`outputs/gates/ci-multidb-db586906/`)
salió 1 passed, 14 errors, todos `DeadlockDetected` en la migración de la
base de empresa. El registro del servidor nombra a los dos procesos:

```text
Process 20532: SET CONSTRAINTS "sale_order_user_id_9857f812_fk_res_users_id" IMMEDIATE; ALTER TABLE "sale_order" DROP CONSTRAINT "sale_order_user_id_9857f812_fk_res_users_id"
Process 22205: select string_agg(p.id||'->'||coalesce(p.commercial_partner_id::text,'NULL'),' ') from res_users u join res_partner p on p.id=u.partner_id
```

El 22205 era la consulta del `Monitor` de esta sesión, que cada 20 s leía
`res_users` y `res_partner` de la base que el gate migraba. Quitar una FK
toma `AccessExclusiveLock` sobre las dos tablas; la lectura tenía una y
esperaba la otra, y PostgreSQL mató a la migración. **La ejecución no prueba
ni refuta `0116`**: la migración murió antes del `post_migrate`.

Regla que se sigue desde aquí: mientras un gate corre, se le observa por su
log, su proceso y el sistema de archivos, **nunca con una consulta a sus
bases**. Lo que se quiera saber de esas bases se lee después, sobre la
evidencia que el gate deja.

## El gate de `eee4382f` refutó el arreglo: la causa estaba en la operación (2026-11-17T01:06:03)

`outputs/gates/ci-multidb-eee4382f/`: el mismo `ParseError` de
`account_security.xml:247` con `0116` aplicada. Las 5 pruebas de `0116`
pasaban porque llaman a la operación sobre `default`, donde no hay
diferencia que ver; eran ciegas al fenómeno de una base de empresa.

**Reproducido sin el gate**, con una sonda que copia QA por plantilla a un
`company_<N>_db`, anula el socio raíz en la copia y ejecuta
`compute_now` bajo `company_scope`, como `_migrate_company_database`:

```text
antes   default (5730, 5730) empresa (5730, None)
despues default (5730, 5730) empresa (5730, None)
```

**Causa.** `ComputeStoredFields.compute_now` abría `Environment(None,
SUPERUSER_ID, {})`, que no declara base: `_cr` queda sin fijar y el cálculo
no alcanzaba la conexión que se migra. La fuente calcula con el `env` del
cursor que migra. Afecta a toda migración con `ComputeStoredFields` (16
archivos) en toda base de empresa, no sólo a `0116`.

**Arreglo (TASK-API-0516).** `compute_now(using)` abre
`Environment(using, SUPERUSER_ID, {})`; `_compute` le pasa
`schema_editor.connection.alias` y `run_pending_computes` su `using`. La
lectura de los ids entra en el entorno. Con la sonda:

```text
antes   default (5730, 5730) empresa (5730, None)
despues default (5730, 5730) empresa (5730, 5730)
```

**Verificación.** Dos pruebas nuevas en
`tests/unit/orm/test_compute_stored_fields_operation.py` leen
`get_current_cr()` en el volcado, que es lo que el router usa para elegir la
base. Anulación (devolver `Environment(None, ...)`): caen exactamente esas
dos, 9 sobreviven.

La sonda dejó dos copias en su primera versión (`duplicate_database`
termina las conexiones al origen y el `finally` falló sobre la conexión
muerta): `company_825186220848_db` y `company_963269235496_db`, del rol
`orm_x2hokp`, retiradas. La versión corregida reabre `default` y retira su
copia.
