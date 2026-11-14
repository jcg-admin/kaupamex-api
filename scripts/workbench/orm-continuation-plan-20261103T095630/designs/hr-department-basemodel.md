# `hr.department` sobre `BaseModel`, con `_parent_store`

Creado: 2026-11-14T11:46:47 (UTC). TASK-API-0397. Primer tramo de
`basemodel-adoption-hr-core-0397`.

## Búsqueda previa

- Árbol materializado: `BaseModel` ya porta `_parent_store_create` y
  `_parent_store_update` (`src/orm/models.py:1257`, `:9303`, `:9351`),
  y `_maintains_parent_store` los activa para un `BaseModel` con
  `_parent_store`. REUSE.
- Recursión: `BaseModel._has_cycle` (`src/orm/models.py:8937`). REUSE.

## Contrato (`odoo19c: addons/hr/models/hr_department.py`)

`_parent_store = True` (`:17`); `_check_parent_id` con `_has_cycle`
(`:115-118`); `create` con `mail_create_nosubscribe` (`:120-122`);
`write` que reasigna el gerente (`:129-137`).

## Medido aquí (`7df44d69`)

`HrDepartment` deriva de `MailThread, TimeStampedModel`, declara
`_parent_store` como pendiente y calcula `parent_path` en su `save()`.
`manager`/`member_ids` siguen DEFERIDOS (`hr.employee` en otro tramo).

## Decisión

1. Base `models.BaseModel` primero; `_parent_store = True`: el ORM
   mantiene el camino en `create`/`write`.
2. `save()` se conserva para el camino de Django (`objects.create`), que no
   pasa por `create` del ORM; escribe el mismo valor.
3. `_check_parent_id` con `_has_cycle`, como en la fuente.
4. `create`/`write` de la fuente quedan fuera y se declaran: el
   `MailThread` de aquí no lee `mail_create_nosubscribe`, y la reasignación
   del gerente depende de `manager_id`.

## RED y anulaciones (medido)

- RED 3 de 4: el caso de creación ya pasaba por el `save()` anterior; queda
  como regresión.
- El ciclo lo rechaza `_parent_store_update` con `UserError("Recursion
  Detected.")` antes que la restricción, como la fuente
  (`odoo19c: odoo/orm/models.py:5030`); el test espera eso.
- El primer intento dejó el subárbol con el prefijo viejo: el `save()`
  escribía el camino del propio nodo antes de que el ORM reescribiera el
  subárbol. Se aplicó el patrón de `ir.ui.menu` (delegar en
  `_parent_store_update` cuando cambia el padre).
- Anulación de la delegación del `save()` → cae exactamente el caso del
  subárbol.
- Anulación de `_parent_store = True` → los 4 siguen pasando. La bandera se
  declara por fidelidad (la consume también `_maintains_parent_store`), pero
  en estos casos su efecto no es observable: todo `write` vuelca por `save()`,
  y ahí la delegación ya mantiene el árbol.

*Métrica:* `parent_path` leído por SQL tras `create`/`write` del ORM.
*Ciega a:* los operadores `child_of`/`parent_of`, que con `_parent_store`
recorren `parent_path` y sin ella recursan; dan el mismo conjunto, así que
estos casos no los separan.
