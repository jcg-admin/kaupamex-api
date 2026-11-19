# `onboarding` sobre `BaseModel`, con su ACL

Unidad hija `basemodel-adoption-onboarding-0397` del paraguas
`basemodel-adoption-0397` (TASK-API-0397), con la forma de
`basemodel-adoption-utm.md`.

## Contrato medido en la referencia

`odoo19c: addons/onboarding/models/` declara cuatro modelos, cada uno con sus
atributos de clase (`scripts/census_class.py`):

| Modelo | Atributos | Objeto de tabla |
|---|---|---|
| `onboarding.onboarding` | `_name`, `_description = 'Onboarding'`, `_order = 'sequence asc, id desc'` | `_route_name_uniq` (`odoo19c: addons/onboarding/models/onboarding_onboarding.py:40`) |
| `onboarding.onboarding.step` | `_name`, `_description = 'Onboarding Step'`, `_order = 'sequence asc, id asc'`, `_rec_name = 'title'` | — |
| `onboarding.progress` | `_name`, `_description = 'Onboarding Progress Tracker'`, `_rec_name = 'onboarding_id'` | `_onboarding_company_uniq` (`odoo19c: addons/onboarding/models/onboarding_progress.py:28`) |
| `onboarding.progress.step` | `_name`, `_description = 'Onboarding Progress Step Tracker'`, `_rec_name = 'step_id'` | `_company_uniq` (`odoo19c: addons/onboarding/models/onboarding_progress_step.py:21`) |

`odoo19c: addons/onboarding/security/ir.model.access.csv`: doce filas, tres
por modelo (todos sin permiso, `base.group_user` sin permiso y
`base.group_system` con los cuatro).

## Estado de este árbol (medido)

- Sólo el paso declara la cabecera; los otros tres no tienen `_name`, así que
  el censo de `test_basemodel_reach.py` no los ve y el CSV no puede resolver su
  `model_*`.
- Ninguno es `BaseModel`. Los tres primeros derivan de `TimeStampedModel`; el
  paso, de `RecordLoaderMixin, models.Model`, con un comentario que justifica
  no llevar `TimeStampedModel` porque «ningún campo de la fuente lee esas
  columnas». La prosa es falsa por partida doble: en la fuente todo modelo con
  `_log_access` lleva `create_uid`, `create_date`, `write_uid` y `write_date`
  (`LOG_ACCESS_COLUMNS`, `odoo19c: odoo/orm/models.py:296`), y aquí el paso ya
  las tiene, inyectadas por `onboarding/0003_log_access_auto_injection`. El
  paso pasa a `(models.BaseModel, TimeStampedModel)` como los otros tres; si
  `makemigrations` detecta cambios, la migración se nombra en la ejecución.
- Las claves foráneas están en forma A: `onboarding` y `step`, donde la
  fuente declara `onboarding_id` y `step_id`. Por eso `_rec_name =
  'onboarding_id'` y `_rec_name = 'step_id'` no pueden declararse todavía: el
  nombre no resolvería a ningún campo. Siguen la forma de
  `basemodel-adoption-resource.md`: la forma C es la unidad sucesora
  `onboarding-fk-names-0397` (sólo renombra, la columna se conserva con
  `db_column`), que declara además esos dos `_rec_name`.
- No hay `security/`: el addon no tiene ACL.

## Cambios

1. Los cuatro modelos derivan de `(models.BaseModel, TimeStampedModel)` y
   declaran verbatim los atributos de la tabla, salvo los dos `_rec_name` que
   nombran una clave foránea (sucesor `onboarding-fk-names-0397`).
2. `addons/onboarding/security/ir.model.access.csv`, copia fiel, declarada en
   `data` del manifiesto (`designs/security-data-by-manifest.md`).
3. `test_basemodel_reach.py`: `onboarding` sale de `PENDING`.

## Pruebas

`tests/unit/onboarding/test_onboarding_basemodel_acl.py`: los cuatro modelos
son `BaseModel` con los atributos de la fuente; las filas de ACL son las del
CSV; un usuario interno no lee un paso y el administrador sí.

## Los consumidores, medidos al cambiar la base

Con `BaseModel`, el acceso a una relación devuelve un recordset y no un
gestor de Django: `.all()`, `.filter()`, `.count()`, `.exists()` y `.set()`
dejan de existir sobre él, como en la fuente, que usa `filtered`, `len`, la
verdad del recordset, `unlink` y `write` con `Command`. Medido con la suite
del addon: 21 de 26 pruebas caían. Se pasan al API de recordset, sin cambiar
la conducta, estos métodos:

- `onboarding.onboarding`: `is_per_company` (≙ `_compute_is_per_company`,
  `odoo19c: addons/onboarding/models/onboarding_onboarding.py:45-54`),
  `get_current_progress` (≙ `_compute_current_progress`, `:56-69`),
  `set_steps` (la porción de `write`, `:71-77`), `action_refresh_progress_ids`
  (`:92-102`), `_create_progress` (`:113-123`) y `_prepare_rendering_values`
  (`:125-136`), más la extensión `_prepare_rendering_values` de `account`;
- `onboarding.onboarding.step`: `check_step_on_onboarding_has_action`
  (`odoo19c: addons/onboarding/models/onboarding_onboarding_step.py:65-72`),
  `link_onboarding` (la porción de `write`, `:74-92`),
  `_compute_current_progress` (`:47-63`) y `_create_progress_steps`
  (`:113-133`);
- `onboarding.progress`: `onboarding_state` (≙ `_compute_onboarding_state`,
  `odoo19c: addons/onboarding/models/onboarding_progress.py:30-39`),
  `recompute_progress_step_ids` (`:41-44`) y `get_and_update_onboarding_state`
  (`:53-78`).

Las pruebas de la fuente corren como superusuario (`TransactionCase`); las de
`tests/unit/onboarding/test_onboarding.py` pasan a hacerlo con un entorno de
`SUPERUSER_ID`, porque la ACL sólo da permisos a `base.group_system`.

## Fuera de esta unidad

La forma de la fuente de esos métodos —campos calculados en lugar de
propiedades, y `write` en lugar de `set_steps`/`link_onboarding`— es la unidad
sucesora `onboarding-methods-0397`, bajo TASK-API-0397, junto a
`onboarding-fk-names-0397`.
