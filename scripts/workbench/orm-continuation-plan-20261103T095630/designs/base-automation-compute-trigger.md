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

## Aquí, medido (revisión 2026-11-18, mitad roja de la prueba)

La primera versión de esta sección afirmaba que el recálculo llega por
`save(update_fields)`; leía el docstring de `_write_multi`, que está
desactualizado. Medido con la prueba de abajo, antes de implementar:

1. **El recálculo almacenado NO dispara las reglas.** `_write_multi` →
   `_write_rows` → `_persist_columns`, un `UPDATE` directo que salta
   `save()` y los receptores de `pre_save`/`post_save` a propósito (su
   docstring nombra a `base_automation`; `designs/flush-writes-columns.md`).
   Caso 3 en rojo: `runs == []` tras alargar un tramo del calendario.
2. **`write()` de un `BaseModel` sí dispara**: pasa por `save()` (sonda:
   `partner.write({'name': 'B'})` → la acción corre una vez). Sólo el
   volcado de calculados queda fuera, que es exactamente lo que el parche
   de `_compute_field_value` cubre en la fuente.
3. **La precondición se borra en cada `save()` de la regla.**
   `BaseAutomation.save` corre `_recompute_dependent_fields`, y
   `_compute_filter_pre_domain` escribe `''` para todo disparador que no
   sea `on_tag_set`. En la fuente el cómputo depende de
   `('trigger', 'trg_field_ref')` (`:378`) y un valor dado al crear queda
   protegido; `_compute_filter_domain` depende de
   `('trigger', 'trg_selection_field_id', 'trg_field_ref')` (`:387`).
   Por eso el caso 1 pasaba sin filtrar nada y el caso 2 disparaba.
4. **La precondición de una escritura se evalúa después de escribir**
   (`_dispatch_create_write` es un receptor de `post_save`). Enmascarado
   hoy por 3.
5. La prosa «`_compute_field_value` bloqueado» del docstring es falsa: el
   motor existe y el punto de extensión es `BaseModel._compute_field_value`
   (`src/orm/models.py:9404`), que ningún modelo sobreescribe.

## El cambio

- **Recálculo.** `signals.py` instala, una vez desde `ready()`,
  `wrap_method(BaseModel, '_compute_field_value', …)` con el cuerpo de
  `make_compute_field_value`: si el método calcula campos almacenados y hay
  reglas `WRITE_TRIGGERS` del modelo, lee la precondición y los valores
  viejos de la base antes de la previa, llama a la previa, **vuelca esos
  campos** y evalúa la postcondición y `_process` con `old_values`. El
  volcado es la divergencia de mecanismo: la fuente filtra en memoria
  (`filtered_domain`) y aquí `_records_matching_domain` consulta la base.
  Misma guarda de reentrancia (`_processing_set`) y mismas exclusiones que
  los receptores (`_skip`, tabla de reglas existente).
- **Precondición.** `_capture_old_values` (`pre_save`) evalúa la
  precondición de cada regla aplicable y la guarda en la instancia;
  `_dispatch_create_write` la usa en vez de llamar a `_filter_pre` después.
- **Filtros protegidos.** `_recompute_dependent_fields` recalcula
  `filter_pre_domain` sólo al crear sin valor, o cuando cambian `trigger` o
  `trg_field_ref` y el llamador no escribió el filtro; `filter_domain`,
  igual con sus tres dependencias.
- Se retira la divergencia «bloqueado» del docstring y se corrige el de
  `_write_multi`, que nombra `save(update_fields)`.

## Pruebas — `tests/unit/base_automation/test_compute_and_pre_trigger.py`

| Caso | Espera |
|---|---|
| regla `on_write` con `filter_pre_domain` que el `write` deja de cumplir | dispara (pre sobre el valor viejo) |
| ídem, con un registro que no la cumplía antes y sí después | no dispara |
| regla `on_write` con `trigger_field_ids` sobre un calculado almacenado; se cambia su dependencia | la acción corre una vez sobre el registro |
| ídem, con un `filter_domain` que el valor recalculado no cumple | no corre |

Anulaciones: precondición de vuelta en `post_save` → caen los casos 1 y
2; sin el envoltorio de `_compute_field_value` → cae el 3; sin el volcado
previo a la postcondición → cae el 4 (la base aún tiene el valor viejo y
la postcondición lo aceptaría o rechazaría por él).

*Métrica:* ejecuciones de una acción de servidor registradas por la
prueba.
*Ciega a:* el orden entre varias reglas y la reentrancia, que ya cubre
`_processing_set`.
