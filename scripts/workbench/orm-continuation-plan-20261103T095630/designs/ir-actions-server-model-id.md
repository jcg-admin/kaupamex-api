# `model_id` de `ir.actions.server` como Many2one a `ir.model` (5b)

TASK-GEN-0391. Candidato: `candidates/base-ir-actions-server-model-id-0391.jsonl`
(su número de migración, `0129`, quedó viejo: la siguiente libre es `0149`).
Depende de `ir-actions-server-parent-id-0397`.

## Contrato medido en la referencia

`odoo19c: odoo/addons/base/models/ir_actions.py`:

- `:635-636` `model_id = fields.Many2one('ir.model', string='Model',
  required=True, ondelete='cascade', index=True, help=...)`.
- `:638` `model_name = fields.Char(related='model_id.model',
  string='Model Name')`: un `related` sin `store`, que se lee de `model_id`.
- `:746-760` `_warning_depends` y `:803-804` `@api.depends(lambda self:
  self._warning_depends())` sobre `_compute_warning`.

## Estado del árbol (medido)

- `IrActionsServer.model_name` es `Char` con índice
  (`src/addons/base/models/ir_actions.py:1509`); no hay `model_id`.
- `_warning_depends` ya lista `model_id` y `parent_id`
  (`:1872-1884`); `_compute_warning` no lleva el `@api.depends` porque
  `resolve_depends` rehúsa un nombre ausente, y su docstring nombra esta
  TASK.
- Precedente del mismo archivo para el `related`:
  `crud_model_name = fields.Char(related='crud_model_id.model',
  readonly=True)` (`:1774`).
- Escritores de `model_name=` en el árbol (medido con
  `grep -rlE "IrActionsServer|ir\.actions\.server"` y `model_name[=:]`):
  12 archivos de `src`, 5 de `addons` y 22 de `tests`. Las migraciones
  históricas que siembran acciones usan su propio estado histórico y no
  cambian. Los sembradores vivos son `src/addons/base/data/cron.py:181`
  (por `identity_for_key`) y los `data/__init__.py` de `auto_backup`,
  `mail` y `loyalty`, que nombran el modelo por su etiqueta de Django.
- `ir.cron` delega en `ir.actions.server` (`_inherits`): crear un cron con
  `model_name` escribe en la acción.

## Cambio

1. `IrActionsServer.model_id` (forma C, `db_column='model_id'`), requerido,
   `ondelete='cascade'`, indexado; `model_name` pasa a
   `Char(related='model_id.model', string='Model Name')`.
2. Migración `0149`: columna `model_id` en `ir_act_server`, valor resuelto
   contra `ir_model.model` con `identity_for_key` (la columna guardaba la
   etiqueta de Django o el `_name`), fila de `ir.model` creada si falta,
   `NOT NULL`, clave foránea e índice; retiro de la columna `model_name`.
3. `@api.depends(lambda self: self._warning_depends())` sobre
   `_compute_warning`, y fuera la nota de bloqueo.
4. Los escritores pasan a `model_id`: sembradores, `create` de los
   hijos, `base_automation`, y las pruebas.

## Pregunta abierta antes de implementar

La lectura de `model_name` hoy acepta las dos formas de nombrar un modelo
(etiqueta de Django y `_name`); con el `related`, el valor es siempre el
`ir.model.model` de la fila. Hay que medir qué consumidores comparan
`model_name` contra una etiqueta de Django antes de cambiarlo.

### Respuesta medida

Lectores de `IrActionsServer.model_name` en `ir_actions.py`, `ir_cron.py` y
`base_automation` (`grep -nE "\.model_name\b"`, 21 líneas):

- resuelven por `model_by_key` (`:2141, :2668, :2716, :2858`) o comparan con
  `identity_for_key` (`:2863`): admiten las dos formas;
- comparan contra otro valor que también sale de `ir.model.model`:
  `child.model_name != self.model_name` (`:1938`), `link.model ==
  self.model_name` (`:2331`, `ir.model.fields.model`) y los filtros
  `model=self.model_name` (`:2766, :2786`);
- lo copian o lo exponen (`:2137, :2267, :2614, :2657, :3020`,
  `ir_cron.py:530`).

Ninguno compara contra una etiqueta de Django escrita a mano. Con el
`related`, el valor es siempre la clave de `ir.model`, que es la forma con la
que ya se comparan `:1938` y `:2331`: el cambio los vuelve coherentes en vez
de romperlos.

## Ampliación: `base_automation_id`, medido al implementar

`_warning_depends` de `base_automation` acumula `'base_automation_id'`
(`odoo19c: addons/base_automation/models/ir_actions_server.py:20-25`). Con
`@api.depends` cableado, `resolve_depends` rehúsa el nombre: aquí el campo no
existía, lo sustituía la tabla-liga `BaseAutomationAction` (`OneToOneField`
sobre la acción), con el argumento de que Django no admite un campo nuevo
sobre el modelo de otro addon. `extend_model(campos=…)` ya lo hace (`hr`,
`account`, `base_vat`), así que la divergencia no se sostiene y se porta en
esta unidad:

- `base_automation_id = Many2one('base.automation', index='btree_not_null',
  ondelete='cascade')` (`:17`) por `extend_model`, con `db_index=False` para
  que el único índice sea el parcial, como en la fuente;
- los tres lectores (`_automation_of`, `action_open_automation`,
  `_get_children_domain`) leen la columna;
  `BaseAutomation.action_server_ids`, `copy` y
  `_compute_action_server_ids` (`odoo19c: base_automation.py:312-320`, que
  desvincula con `(3, id)`) también;
- migración `base/0150` (columna, índice parcial, copia de la liga) y
  `base_automation/0010` (retiro de la liga), en ese orden: el detector las
  generaba al revés, retirando la liga antes de copiarla.

Y dos hallazgos del paso de datos de `0149`:

- las claves foráneas son `DEFERRABLE INITIALLY DEFERRED`; los disparadores
  del paso de datos quedan pendientes y PostgreSQL rehúsa el `ALTER TABLE`
  siguiente (`cannot ALTER TABLE "ir_model" because it has pending trigger
  events`). `SET CONSTRAINTS ALL IMMEDIATE` entre los dos pasos lo resuelve;
- el sembrador de crons es compartido por migraciones de dos estados: antes
  de `0149` la acción tiene `model_name` y desde ahí `model_id`, y una
  migración de addon que corre después recibe el segundo.
  `data/cron.py::_model_key` elige la forma por los campos del modelo que
  recibe.
