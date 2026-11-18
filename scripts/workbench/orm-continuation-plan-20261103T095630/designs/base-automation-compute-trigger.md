# Automatizaciones disparadas por un recálculo, y la precondición antes de escribir

Fecha: 2026-11-18T07:42:11. Unidad: `base-automation-compute-trigger-0485`
(TASK-API-0485). Preparado en solo lectura mientras corría F2 de
`839d5cd4`.

## La fuente

`odoo19c: addons/base_automation/models/base_automation.py`:

- `make_write` (`:880-907`): `pre = {a: a._filter_pre(records)}` y
  `old_values` se leen **antes** de `write.origin`; la postcondición y
  `_process` corren después.
- `make_compute_field_value` (`:909-946`): lo mismo alrededor del
  recálculo. Sólo actúa si el método calcula algún campo almacenado
  (`stored_fnames`); la precondición se evalúa con el contexto
  `changed_fields` = los campos calculados por ese método; `old_values` son
  los de `stored_fnames`; después, `_filter_post_export_domain` y
  `_process` con `old_values` en el contexto.
- Los dos se instalan por modelo en `_register_hook` (`:1057`).

## Aquí, medido en el código

1. **El recálculo almacenado SÍ pasa por las señales.** `_flush` entrega a
   `_write_multi`, cuyo enunciado es `save(update_fields=...)` por fila
   (`src/orm/models.py:9427-9445`, `designs/write-multi-flush.md`). Su
   docstring ya lo declara: *"`save()` y sus señales alojan los cómputos y
   las automatizaciones que la fuente aloja en … el parche de
   `_compute_field_value`"*. El `post_save` de `signals.py` dispara las
   reglas `on_write` / `on_create_or_write` sobre la fila recalculada.
2. **La prosa de bloqueo es falsa.** El docstring de `base_automation.py`
   (`:51-56`) dice que no hay motor de recálculo; existe, y el punto único
   donde se ve un recálculo almacenado es `_write_multi`.
3. **Defecto nuevo, de toda escritura y no sólo del recálculo:** la
   precondición se evalúa **después** de escribir. `_filter_pre` dice
   *"evaluada ANTES de escribir"* (`base_automation.py:1090-1096`), pero su
   único llamador es `_dispatch_create_write`, un receptor de `post_save`
   (`signals.py:104-142`), que la consulta contra la base ya escrita. Una
   regla con `filter_pre_domain=[('state','=','draft')]` y un `write` que
   pasa el registro a `done` no dispara en la fuente si estaba en `draft`…
   al revés: dispara en la fuente (pre: estaba en draft) y aquí no (pre
   evaluada sobre `done`). Ninguna prueba cubre `filter_pre_domain` (0 hits
   en `tests/`).
4. `changed_fields` no viaja en el contexto de la precondición.

## El cambio

- `_capture_old_values` (`pre_save`) evalúa además la precondición de cada
  regla aplicable y guarda en la instancia `{automation.pk: pre_pks}`;
  `_dispatch_create_write` usa ese resultado en vez de llamar a
  `_filter_pre` después de escribir. Sin fila previa (creación) no hay
  precondición, como en la fuente (`make_create` no la evalúa).
- Si `update_fields` sólo contiene campos calculados, la precondición se
  evalúa con `changed_fields` en el contexto (≙ `:927-928`).
- Se retira la divergencia «`_compute_field_value` bloqueado» del
  docstring y se declara la forma: el recálculo llega por
  `save(update_fields)` desde `_write_multi`.

## Pruebas — `tests/unit/base_automation/test_compute_and_pre_trigger.py`

| Caso | Espera |
|---|---|
| regla `on_write` con `filter_pre_domain` que el `write` deja de cumplir | dispara (pre sobre el valor viejo) |
| ídem, con un registro que no la cumplía antes y sí después | no dispara |
| regla `on_write` con `trigger_field_ids` sobre un calculado almacenado; se cambia su dependencia | la acción corre una vez sobre el registro |
| ídem, con un `filter_domain` que el valor recalculado no cumple | no corre |

Anulaciones: precondición de vuelta en `post_save` → caen los casos 1 y
2; sin el `post_save` del recálculo (filtrar `update_fields`
calculados) → cae el 3.

*Métrica:* ejecuciones de una acción de servidor registradas por la
prueba.
*Ciega a:* el orden entre varias reglas y la reentrancia, que ya cubre
`_processing_set`.
