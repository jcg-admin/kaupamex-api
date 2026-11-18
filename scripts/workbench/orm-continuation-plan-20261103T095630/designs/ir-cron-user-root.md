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
