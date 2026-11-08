# Reconciliación de TASK-API-0485 — instrucción 3.2.12, frente C

## Identidad

- **Una sola fila** con la cita `TASK-API-0485` en el store del Provider
  (`thyrox: agent-results/agent_store.sqlite3`): `task_id` 8 de la sesión
  `0390150a-…`, ordinal de board 11, origen `task_ids ingest-board`,
  creada el 2026-11-04T17:26:35, `in_progress`. Cero citas duplicadas en el
  store.
- **Acuñada localmente y no publicada.** En el store de
  `origin/claude/bold-fermat-x2hokp` la cita API más alta es
  `TASK-API-0478`, y ninguna rama de `origin` contiene una cita entre
  `TASK-API-0479` y `TASK-API-0510`. Las 25 citas `0479`…`0503` viven sólo en
  los commits locales de thyrox, cuya publicación espera la decisión del
  ejecutor. Hoy no colisionan; mientras no se publiquen, otra VM puede acuñar
  las mismas.

## Cardinalidad

```
TASK-API-0485 (1 fila)
  └─ 77 unidades del plan, 77 aceptadas (modelo registrado: conversational-session)
       └─ 319 obligaciones nombradas
            ├─ 275 satisfied en el inventario
            ├─  43 task_units_settled en la clasificación (aún no satisfied)
            └─   1 fuera de las raíces del censo (src/api/__init__.py::Self)
  └─ 917 filas de la clasificación asignadas a la TASK (874 sin unidad)
```

Una unidad aceptada no cierra sus obligaciones —43 siguen sin `satisfied`—, y
77 unidades aceptadas no cierran la TASK: 874 obligaciones no tienen unidad.
La TASK es la **padre** de sus unidades; no hay colisión de identificador ni
obligación asignada a dos TASK dentro de este plan.

## Ninguna unidad la ejecutó un worker local

Las 144 unidades aceptadas del plan registran `conversational-session`. La
causa está medida en H-API-1169.
