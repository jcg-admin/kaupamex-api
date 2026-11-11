# Propagación del alias en init: el entorno de init_models

Fecha: 2026-11-11T05:13:26. Estado: diseño, RED por escribir. Revisión de partida:
`d2b87463` (HEAD = origin).

## Hallazgo

`ResCompany.init` escribe con `company.write(...)` (lo exige
`check_write_path`, ver `paperformat-company-init.md`). `write` termina
en `Model.save()`, que resuelve la base con
`router.db_for_write(model, instance=self)`. El router del proyecto
(`src/orm/routers.py:132-176`, `CompanyDatabaseRouter`) resuelve:

1. plano de control → `default`;
2. `get_current_cr()` (el `env.cr` de la fuente) si un entorno lo fijó;
3. si no, la empresa activa; sin empresa y con bases de compañía
   registradas (N>1) **lanza `CompanyContextRequired`**.

`ResCompany.init(using=B)` no fija ni el entorno ni la empresa: bajo N>1
el `write` falla, y bajo `company_scope(A)` escribiría en A. Lo leído
con `using(B)` y lo escrito pueden quedar en bases distintas.

`ResUsers.init` no tiene el problema: escribe con
`db_manager(using).filter(...).update(...)`, que pasa la base explícita
(y su camino de escritura coincide con el de la fuente, que baja a SQL en
`_set_encrypted_password`).

## Contrato de la fuente

`odoo19c: odoo/orm/registry.py:741-752` (odoo-tools `abe4040ec1`):

    env = Environment(cr, SUPERUSER_ID, context)
    models = [env[model_name] for model_name in model_names]
    ...
    for model in models:
        model._auto_init()
        model.init()

`init` corre con el cursor de la base que se instala y como superusuario;
todo `write` de `init` va a esa base por construcción. Nuestro
`init_models` (`src/orm/registry.py`) no construye el entorno.

## TRAE / CONSTRUYE

- TRAE: `Environment(cr, uid, context, su)` con `cr` = alias
  (`src/orm/environments.py:839`), cuyo `__enter__` fija `_cr`
  (`:1030-1049`); el router ya lo lee primero (`routers.py:138-140`).
- CONSTRUYE: nada nuevo. Dos cambios:
  1. `init_models` abre `with Environment(using, SUPERUSER_ID, context)`
     alrededor de su cuerpo, como la fuente;
  2. `ResCompany.init(using)` abre el mismo entorno, porque su contrato
     propio (`init(using=...)`) debe valer también llamado directamente.

## Pruebas (RED primero) en `test_multidb_isolation.py`

Sobre las dos bases de compañía del fixture, más `default`:

1. `ResCompany.init(using=B)` sin `company_scope`: la compañía sin
   formato de B recibe el `base.paperformat_euro` **de B** (XML-ID
   resuelto en B); las de A y `default` siguen sin formato. Hoy: RED por
   `CompanyContextRequired`.
2. Lo mismo bajo `company_scope(A)` activo: escribe en B, no en A.
3. Reejecución: idempotente; no toca la compañía que ya tiene formato.
4. Las tres identidades XML de los formatos existen en cada base y apuntan
   a filas de esa base.
5. Error y transacción: sin el XML-ID en B (dentro de un `atomic` con
   rollback) no se asigna nada ni se lanza; el rollback deja B intacta.
6. `ResUsers.init(using=B)`: una contraseña en claro en B se cifra; la de
   A sigue en claro y la de `default` no cambia; los valores originales
   se restauran al final (bases desechables, pero sin credenciales nuevas).
7. `init_models` del registro con alias B ejecuta los dos `init` en B.

Controles: sin el entorno en `ResCompany.init` cae 1 y 2; sin el
`using` en `ResUsers.init` cae 6.

*Métrica:* filas de cada base antes y después, por alias.
*Ciega a:* un tercer router o base no declarada; la ejecución con
`init_models` desde el cargador real de módulos (`modules/loading.py`),
que se mide aparte si el registro lo invoca con otro alias.

## RED, implementación y controles (2026-11-11T05:18:37)

RED barato y discriminante, sin crear bases: `_has_company_databases()`
(`routers.py:114-123`) sólo mira `settings.DATABASES`; declarar un alias
`company_<N>_db` (sin abrirlo) activa la rama N>1.
`test_company_init_writes_in_its_base_with_company_databases` falló con

    res_company.py:664: in init -> res_company.py:1036: in save
    orm.routers.CompanyContextRequired: operacion de dominio base.rescompany
    sin empresa activa bajo multi-DB (N>1)

(un primer intento falló en el `create` del montaje — `res.partner` —,
no en `init`; se movió el montaje antes de declarar el alias).

Implementación:

- `ResCompany.init`: `with Environment(alias, SUPERUSER_ID, {})`
  alrededor del bucle de `write`.
- `Registry.init_models`: `with orm.environments.Environment(using,
  SUPERUSER_ID, context)` alrededor del bucle `_auto_init`/`init`, como
  `:741`. No envuelve el reflejo ni las verificaciones (usan su alias
  explícito); envolverlos desplazaría las huellas de las violaciones
  heredadas del archivo sin cambiar conducta medida.
- Prueba nueva `test_init_models_runs_init_in_the_environment_of_its_base`
  (`get_current_cr()` dentro de `init` == alias del registro).

| Mutación | Cae |
|---|---|
| E1: quitar el entorno de `ResCompany.init` | exactamente `test_company_init_writes_in_its_base_with_company_databases` |
| E2: quitar el entorno de `init_models` | exactamente `test_init_models_runs_init_in_the_environment_of_its_base` |

Suites de la unidad: 11 + 19 en verde. Los casos con bases reales (punto
"Pruebas" 1-7) están en `test_multidb_isolation.py` y sólo corren por el
procedimiento ci-multidb sobre base desechable.

## Primer ci-multidb (c5adb3ee): 8 PASSED, 4 ERROR de montaje (2026-11-11T05:57:14)

`outputs/gates/ci-multidb-c5adb3ee`. Pasaron los 6 previos,
`test_paperformat_xml_ids_exist_in_every_base` y
`test_users_init_encrypts_only_in_the_selected_base` (verificación real de
`res.users.init` bajo alias). Los cuatro casos de `res.company.init`
fallaron en el **fixture**, no en `init`: `ResCompany.objects.using(alias).create`
evaluó el default `stock._default_confirmation_mail_template`, que
resuelve un XML-ID por el router, y bajo N>1 sin contexto el router lo
rechazó (`CompanyContextRequired` sobre `base.irmodeldata`).

Dos trampas medidas al rehacer el fixture (sonda unitaria con alias N>1
declarado, archivo temporal ya retirado):

- `objects.using(alias)` devuelve un QuerySet cuyo `create` se salta
  `ResCompanyManager.create`, el que fabrica el partner como la fuente:
  falla con `ResCompany has no partner`.
- `company_scope(id)` con un id sin base registrada no degenera a
  `default` bajo N>1: `_target` devuelve `None` y `_route` lo rechaza.

Forma que funciona (sonda verde): `with Environment(alias):
ResCompany.objects.db_manager(alias).create(...)`, y lo mismo para el
borrado. Se repite el ci-multidb sobre un snapshot nuevo.

## Segundo ci-multidb (e2c7ba00): 8 PASSED, 4 FAILED de la prueba (2026-11-11T06:31:30)

`outputs/gates/ci-multidb-e2c7ba00`. El fixture ya monta bien; los cuatro
casos de `res.company.init` fallaron por la prueba:

- `NameError: _format_of` en tres: el ayudante se borró al reemplazar el
  bloque del fixture. La recolección no lo ve porque no ejecuta cuerpos.
- `CompanyContextRequired` (`base_automation.baseautomation`) en el de
  rollback: el borrado del XML-ID pasa por el colector y sus señales, que
  leen por el router; va dentro de `Environment(alias_b)`.

Para no pagar otro ciclo de 35 min por un error así:

- `probes/undefined_names.py`: nombres leídos en funciones que no define
  el módulo, la función ni `builtins`. Control: denuncia `_format_of` en
  la versión de `e2c7ba00` (10 lecturas) y nada en la corregida.
- Sonda unitaria con alias N>1 declarado, sobre `default`, de los cuatro
  caminos (montaje, `init`, `init` bajo `company_scope`, borrado del
  XML-ID con rollback, `init_models` por `env.registry`): 4 passed
  (archivo temporal ya retirado).

Se repite el ci-multidb sobre un snapshot nuevo.
