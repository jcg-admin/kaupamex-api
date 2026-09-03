# El eje de campos de `Registry` — que trae el stack y que hay que construir

Pieza de banco de la tarea **#342** (tramo 2) y de la **#209**.

## La pregunta

De los ocho simbolos que `odoo19c: odoo/orm/registry.py` declara entre
`field_inverses` (`:506`) e `is_modifying_relations` (`:670`), cual cae en cada
uno de los dos cubos del criterio del ejecutor:

- **el stack lo trae hecho** — hay un simbolo instalado y basta llamarlo;
- **el stack tiene con que construirlo** — no hay simbolo hecho, pero las
  primitivas estan y no hace falta ninguna dependencia de fuera.

Y con que entrada del `INVENTORY` se paga cada uno.

## Lo que se midio

```
READY:     1 de 8 — field_inverses
BUILDABLE: 7 de 8 — field_computed, get_trigger_tree, get_dependent_fields,
                    _discard_fields, get_field_trigger_tree, _field_triggers,
                    is_modifying_relations
BLOCKED:   0 de 8 — ninguno
```

`BLOCKED: 0` es el resultado que importa: **ningun simbolo del tramo tiene un
bloqueo medido**, asi que los ocho se implementan. No se deriva ninguno.

`field_inverses` es el unico READY, y por una razon concreta: la fuente lo
construye llamando a un `setup_inverses` **por clase de campo** porque su ORM
no guarda la vuelta de una relacion. Django si la guarda —la relacion inversa
es un objeto propio que `Options.get_fields()` publica— asi que el mapa se
deriva de lo que ya existe. Es divergencia de mecanismo con el mismo contenido.

Los dos que estaban **ausentes del arbol**, no solo del objeto:

| simbolo | que faltaba |
|---|---|
| `_discard_fields` (`:573`) | no existia en ninguna forma |
| las tres comprobaciones de `field_computed` (`:526-550`) | el agrupamiento estaba; los avisos de `compute_sudo`, `precompute` y `store` no |

## El control que discrimina

```bash
bash scripts/workbench/registry-field-axis-support-20260903T053330/neutralize_and_measure.sh
```

Retira `src/` del `PYTHONPATH` y vuelve a correr el clasificador. Con las
primitivas propias fuera de alcance, seis de los ocho pasan a `BLOCKED` y el
guion nombra cual falta en cada uno. Sin ese contraste, un clasificador que
dijera `BUILDABLE` sin resolver nada pasaria los ocho y el verde no
distinguiria «las primitivas estan» de «el instrumento no las mira» — el
sub-patron D de `metrica-decide-la-conclusion.md`.

El control de unidad, escrito antes del instrumento, vive en `tests/`.

## Como se corre

```bash
DJANGO_SETTINGS_MODULE=config.settings.testing PYTHONPATH=src \
    uv run python scripts/workbench/registry-field-axis-support-20260903T053330/classify_field_axis_support.py

DJANGO_SETTINGS_MODULE=config.settings.testing PYTHONPATH=src \
    uv run pytest scripts/workbench/registry-field-axis-support-20260903T053330/tests -q
```

`--json` emite el reparto como JSON; `--strict` sale 1 si algo quedara
bloqueado. El reparto se persiste en `outputs/verdicts.json` en cada corrida.

## Que NO responde

Lo declara el `blind_to` del `manifest.json`. Lo principal: mide que el nombre
**resuelve**, no que su conducta coincida con la de la referencia. Un `READY`
dice que hay donde apoyarse, no que la semantica sea la misma; eso lo miden los
casos de `tests/unit/orm/test_registry_field_axis.py`.
