# El cron corre con su usuario, que al instalar es el raíz

Creado: 2026-11-18T19:17:32 (UTC). TASK-API-0485 (unidad de trabajo y su usuario),
requisito de `basemodel-adoption-auto-backup.md`. Referencia:
odoo-tools `abe4040ec1`, Odoo 19 Community.

## El contrato de la fuente

- `user_id = fields.Many2one('res.users', string='Scheduler User',
  default=lambda self: self.env.user, required=True)`
  (`odoo19c: odoo/addons/base/models/ir_cron.py:110`).
- Al instalar un módulo, sus datos se cargan con el entorno del instalador:
  el superusuario (`env = api.Environment(cr, api.SUPERUSER_ID, {})`,
  `odoo19c: odoo/modules/loading.py:404`; `SUPERUSER_ID = 1`,
  `odoo19c: odoo/orm/utils.py:19`; `base.user_root`,
  `odoo19c: odoo/addons/base/data/res_users_data.xml:5`). Un `ir.cron` declarado en XML queda con
  `user_id = base.user_root` y su trabajo corre como él
  (`env = api.Environment(job_cr, job['user_id'], …)`), que se salta
  `ir.model.access`.

## La prosa heredada, validada

| Afirmación | Medido | Veredicto |
|---|---|---|
| `ir_cron.py` (`help_text` de `user`): «aquí nullable porque no hay contexto de request implícito al registrar la tarea» | el contexto de la fuente al registrar la tarea es el instalador, el superusuario; no un request | **falso** |

## Este árbol, medido

- `IrCron.user`: `null=True`. Los **7** crons sembrados tienen
  `user` nulo (`IrCron.objects.filter(user__isnull=True).count()`).
- `_callback` corre bajo `user_scope(self.user_id)`: con `None` no hay
  usuario y `check_access` deniega a un `BaseModel`. Con `user_scope(1)`
  (`base.user_root`) la búsqueda de `db.backup.details` pasa: sonda en
  `auto_backup`, `test_root_reads` verde y `test_none_reads` rojo.
- Mientras los modelos que tocan los crons no eran `BaseModel`, el nulo
  no se notaba. Con `auto_backup` en `BaseModel`, `schedule_backup`
  falla bajo su cron.

## Decisión

1. `sembrar_cron` asigna `base.user_root` como usuario, igual que la
   carga de la fuente.
2. Una migración de datos en `base` rellena con `base.user_root` los
   crons con `user` nulo.
3. `user` pasa a obligatorio, con valor por defecto el usuario actual y,
   si no lo hay, `base.user_root` (el entorno del instalador).
4. El `help_text` deja de afirmar la razón falsa.

Se mide antes de cerrar el punto 3: quién crea `IrCron` sin usuario en
`src/`, `addons/` y `tests/`.

## RED

1. Un cron sembrado por `sembrar_cron` tiene `user_id == base.user_root`.
2. Tras la migración, ningún cron tiene `user` nulo.
3. `_callback` de un cron que busca en un `BaseModel` sin filas de
   acceso para `group_user` termina sin `PermissionDenied`.

## Ejecución (2026-11-18)

Símbolos:

- `_default_user_id` (`src/addons/base/models/ir_cron.py`) ≙
  `default=lambda self: self.env.user`
  (`odoo19c: odoo/addons/base/models/ir_cron.py:110`): el usuario actuante,
  o `SUPERUSER_ID` sin ninguno (el entorno de instalación,
  `odoo19c: odoo/modules/loading.py:404`).
- `IrCron.user`: `null=False`, `on_delete=RESTRICT`, `default=_default_user_id`.
  `RESTRICT` porque un Many2one obligatorio no puede quedar en `SET NULL`.
- `src/addons/base/migrations/0120_ir_cron_user_root.py`: rellena con
  `base.user_root` los crons nulos y altera la columna.

Respecto al diseño: el punto 1 (`sembrar_cron` asigna el raíz) no hace
falta como cambio propio. Los modelos históricos conservan el `default`, y
en una migración no hay usuario actuante, así que el cron sembrado queda
con `SUPERUSER_ID`, que es `base.user_root` (`IrModelData` `res_id` 1).

`makemigrations --check --dry-run`: «No changes detected».
RED: 4 fallos de 4 (`tests/unit/base/test_ir_cron_user_root.py`); GREEN:
4 passed.

**Consumidores que codificaban el contrato anterior.** El subconjunto
derivado (36 archivos de `tests/` que nombran el cron o su callback) dio 5
fallos de 443, todos de pruebas que afirmaban el usuario nulo: el defecto
`None` en `test_create_minimo_aplica_defaults`, `test_user_nullable_por_defecto` (hoy `test_user_defaults_to_root`),
`test_user_set_null_al_borrar_usuario` (hoy `test_deleting_the_user_is_restricted`), el scope `None` en
`test_cron_sin_usuario_deja_el_scope_en_none` y, en `auto_backup`, el
`update(user=None)` de `test_no_authenticated_user_either`. Se portaron al
contrato de la fuente: defecto `SUPERUSER_ID`, borrado del usuario
rehusado (`RestrictedError`), callback como el raíz, y la guarda de
`_take_dump` probada por el lado del llamador sin usuario, que sigue
cerrada. Tras el cambio: 61 passed en los cuatro archivos.

**Anulación.** Sin el respaldo `or SUPERUSER_ID` en `_default_user_id`
caen 20 y dan error 3 de 38: todo cron creado sin usuario choca con
`NOT NULL`. El respaldo carga el peso de cada creación, no sólo el de las
pruebas nuevas.

**La función por defecto se movió a `orm.environments`.** La primera
versión la declaraba a nivel de módulo en `ir_cron.py`, con un import
nuevo. La admisión de estilo la rechazó (`New or changed suppression
requires review`): la huella de un diagnóstico incluye la posición de su
sentencia en el contenedor (`syntax_context`,
`scripts/check_python_style_increment.py:144`), y la sentencia nueva
desplazaba la clase que contiene el `# noqa: BLE001` heredado. Ahora es
`orm.environments.current_uid_or_superuser`, al final del módulo y junto a
`get_current_uid`, que es su hogar natural; `ir_cron.py` y la prueba del
runner sólo amplían imports que ya existían. Los `noqa` no se tocan.

Subconjunto derivado tras la reubicación: 427 passed, 16 skipped.

## F2 en c1b695c2: la guarda del super-usuario llegaba tarde

F2 cayó en `tests/unit/base/test_res_users_constraints.py::test_the_superuser_cannot_be_deleted`:
borrar `base.user_root` daba `RestrictedError` de `IrCron.user` en vez del
`UserError` de la fuente. La guarda era un receptor de `pre_delete`, que
Django emite **después** de reunir el borrado; reunir comprueba
`RESTRICT`, y ahora los siete crons apuntan al raíz.

En la fuente es `@api.ondelete(at_uninstall=True)`
(`odoo19c: odoo/addons/base/models/res_users.py:647`). Este árbol ya
ejecuta esos ganchos al entrar en `Collector.collect`
(`_run_ondelete_on_delete`, `src/orm/models.py`), antes de `RESTRICT`. La
guarda pasa a ser `ResUsers._unlink_except_master_data` con ese decorador,
como la fuente, y el receptor se retira.

**Anulación.** Sin el decorador caen 6 de 17 en
`test_res_users_constraints.py`: el super-usuario, los tres logins de
sistema y los dos borrados en lote. Subconjunto derivado (siete archivos que
borran usuarios, más las dos pruebas del cron): 183 passed.

Símbolo: `ResUsers._unlink_except_master_data` ≙
`odoo19c: odoo/addons/base/models/res_users.py:647`, declarado al final de
la clase para no desplazar las sentencias que la siguen. Pruebas:
`tests/unit/base/test_res_users_constraints.py::test_the_superuser_cannot_be_deleted`
y `test_the_batch_delete_refuses_the_superuser`.
