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
