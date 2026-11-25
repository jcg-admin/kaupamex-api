# MC2c: `code` calculado sobre `code_store` y retirada de `company`/`code`

Unidad `account-account-mc2c-0397` (TASK-API-0397), tras MC2b
(`designs/account-account-mc2b.md`).

## Lo que dice la referencia

- `code` es calculado con búsqueda e inverso
  (odoo19c: addons/account/models/account_account.py:39, 333-353):
  `_compute_code` lee `code_store` en la raíz de `env.company`;
  `_search_code` busca en `code_store` con esa raíz; `_inverse_code` escribe
  `code_store` en esa raíz.
- `_check_company_domain = models.check_companies_domain_parent_of` (`:25`).
- `_ensure_code_is_unique` (`:1079-1130`), llamado al final de `create`
  (`:1050`) y desde `write`.
- No hay columna `company_id` en la cuenta: la pertenencia es `company_ids`.

## La tensión, medida antes de implementar

`env.company` de la fuente cae a `self.user.company_id` cuando el contexto no
trae `allowed_company_ids` (odoo19c: odoo/orm/environments.py:236-243). El
nuestro devuelve `None` sin empresa activa: es la decisión DEC-AISL-04
(«la ausencia de dato deniega»; `src/orm/environments.py:123-141`,
`kaupamex-docs: …/adaptar-familias-odoo-monolito-modular/progreso-…rst:1555-1580`).

Con `code` calculado sobre `env.company.root_id`, todo lector sin empresa
activa (pruebas con el usuario del sistema, comandos fuera de petición)
leería un código vacío. Antes de escribir código, MC2c mide cuántos lectores
hay en ese caso: se ejecuta la suite con `code` calculado y sin la columna, y
se clasifica cada fallo en (a) prueba sin empresa activa, (b) proceso sin
empresa que en la fuente la tendría y (c) defecto real.

- Si sólo hay (a): las pruebas declaran su empresa (`company_scope`), como
  la fuente siempre la tiene.
- Si hay (b): el proceso fija su empresa al arrancar, que es lo que hace el
  middleware para una petición.
- Si (b) exige que `env.company` caiga a la empresa del usuario, eso
  reabre DEC-AISL-04 y se eleva al ejecutor. No se decide aquí.

## La medición (2026-11-24)

`probes/mc2c/code_read_probe.py` (EXPERIMENTAL) registró cada lectura de
`account.account.code` hecha con `env().company is None` sobre los
directorios de pruebas que nombran cuentas o asientos: 15 086 lecturas en
224 pruebas, todas en `probes/mc2c/code-reads-without-company.tsv`.

- (b) Las lecturas internas del modelo durante el alta (`save`,
  `_compute_account_tags`, `_get_closest_parent_account`,
  `_sync_code_store`, `_compute_account_type`): la fuente las hace dentro
  de `create`, que fija `allowed_company_ids=companies.ids`
  (`:1042-1047`). MC2b dejó esa divergencia declarada; MC2c la porta.
- (b) Procesos: `seed_l0_chart.handle` (10) y el cargador del plan, que
  pasa por `create`.
- (a) Pruebas sin empresa: los placeholders analíticos
  (`account_analytic_plan`, `account_analytic_distribution_model`) y 14
  lecturas directas.
- (c) Ninguna depende de que `env.company` caiga a la empresa del usuario.

*Métrica:* lecturas del descriptor de `code` con `env().company is None`.
*Ciega a:* lecturas por SQL crudo de la columna, que no pasan por el
descriptor, y a las pruebas fuera de los directorios recorridos.

Conclusión: MC2c cabe sin reabrir DEC-AISL-04.

## La unidad, partida en dos

Medido el alcance, MC2c se parte para que cada mitad tenga un gate propio.

### MC2c-1 — `code` sobre `code_store` (`account-account-mc2c1-0397`)

1. `create` fija las empresas resueltas como activas mientras crea
   (≙ `allowed_company_ids=companies.ids`, `:1042-1047`). La divergencia
   que MC2b dejó declarada se cierra aquí. El instrumento es un contexto que
   active la lista entera, hermano de `company_scope`, en
   `src/orm/environments.py`.
2. `code` calculado (`_compute_code`), con `_search_code`, `_inverse_code`
   y la rama `code` de `_field_to_sql` (`:131-132`), todos sobre la raíz de
   `env.company`.
3. La migración copia la columna a `code_store` donde falte (MC1 ya lo
   replica) y retira la columna `code` con la restricción `(company, code)`.
   La unicidad pasa a `_ensure_code_is_unique` en MC2c-2; mientras tanto la
   cubre `search_new_account_code` al asignar.
4. Los lectores de la columna pasan al ORM:
   - `services._require_account` (3 llamadas) y
     `account_analytic_distribution_model._compute_prefix_placeholder`:
     `search` con el orden del modelo (`code, placeholder_code`);
   - `account_analytic_plan` (2 `order_by('code')`) y
     `account_account._get_closest_parent_account`: ídem;
   - el cargador `chart_template.load_model_data`: las cuentas por el
     `create` del ORM, bajo la empresa del plan, como la fuente
     (`chart_template.py:202`, `allowed_company_ids=[company.id]`);
   - `seed_l0_chart`: bajo la empresa del sistema;
   - las pruebas que filtran por `code=` (5) o leen `code` sin empresa: la
     declaran con `company_scope`.

#### MC2c-1 — lo que destapó la implementación

- `_get_closest_parent_account` ordenaba por la columna `code`: se porta
  entero en MC2c-1, como la fuente (`:613-633`), con
  `_check_company_domain(env.company)` y `search(order='code')`. Era de
  MC2c-2; pasa aquí porque sin columna no hay otro orden.
- `ir.default._evaluate_condition_with_fallback` resolvía el modelo con
  `apps.get_model(model_name)`, que lee `account.account` como app
  `account`, modelo `account`. El ORM le pasa `model._name`; la búsqueda por
  `code_store` es el primer camino que lo ejerce. Se resuelve con
  `registry.model_by_key`, que admite las dos formas.
- `code` depende de la empresa: su valor en caché va por empresa. El
  inverso lee `code` antes de activar la raíz y la búsqueda resuelve sus ids
  dentro del alcance, porque su SQL lee `code_store` en la empresa activa.
- Las pruebas de MC2c-1 corren sobre `orm_x2hokp_mc2c`, clonada de
  `orm_x2hokp_qa`: la migración retira la columna, y la base del gate no
  puede verla hasta que la unidad llegue a la rama.

#### MC2c-1 — símbolos tocados por archivo

- `addons/account/models/account_account.py`: `AccountAccount`,
  `_get_closest_parent_account`, `_compute_code`, `_search_code`,
  `_inverse_code`, `_field_to_sql`, `save`, `create`,
  `search_new_account_code` y su `search_new_account_code.is_free`
  (≙ `code_is_available`,
  odoo19c: addons/account/models/account_account.py:509-526: libre si
  ninguna cuenta con ese código pertenece a una empresa madre o hija; lo
  prueba `test_a_prefix_becomes_the_first_free_code`); se retira
  `_sync_code_store`.
- `addons/account/migrations/0056_account_code_over_code_store.py`.
- `addons/account/models/chart_template.py`: `load`, `_load_for_company`,
  `load_model_data`.
- `addons/account/services.py`: `_require_account`.
- `addons/account/models/account_analytic_plan.py`:
  `_default_account_prefix_placeholder`.
- `addons/account/models/account_analytic_distribution_model.py`:
  `_compute_prefix_placeholder`.
- `addons/sale_subscription/management/commands/seed_l0_chart.py`:
  `Command.handle`.
- `src/orm/environments.py`: `company_scope`.
- `src/addons/base/models/ir_default.py`:
  `_evaluate_condition_with_fallback`.

#### MC2c-1 — pruebas

`tests/unit/account/test_account_account_code_compute.py` (siete),
`tests/unit/orm/test_environments_channels.py::…list_with_the_first_as_company`
y `tests/unit/base/test_ir_default.py::…named_by_its_reference_name`.

Anulación, medida sobre las once pruebas de `code_compute` y `create`: sin
la raíz en `_compute_code` cae sólo la lectura en la sucursal; con el
inverso leyendo dentro del alcance caen la escritura, la búsqueda y el orden
(tres); sin las empresas activas en `create` caen cinco y dos dan error. La
búsqueda resuelta dentro del alcance no la exige ninguna prueba y se retiró:
`_search_code` devuelve la consulta, como la fuente.

#### MC2c-1 — el subconjunto derivado (2026-11-25)

24 directorios, 16 fallos en 9734 pruebas (`scratchpad/mc2c1-derived.log`).
Dos son del entorno del worktree (`test_check_workbench`, la variable
`THYROX_WORKBENCH_API_WT_MC2B`; pasan en la rama principal). Los 14
restantes, por causa:

- (a) Pruebas sin empresa o que leen `code` como columna:
  `test_analytic_prefix_compute_contract` (5, simulan el lector viejo),
  `test_chart_template` `TestCompanyIsolation` y `TestAccountCodeWidth`
  (`values_list('code')`), `test_compute_writes_m2m` (2) y
  `test_compute_before_insert` (sin empresa activa el vecino de código no
  existe). Se corrigen las pruebas: la fuente siempre tiene empresa.
- (b) El cargador del plan aplica los Many2many con el gestor de Django
  sobre la fila que devuelve el `create` del ORM, que no trae estado de
  base (`TestTaxTagMapper`, `TestAccountTags`). Los Many2many de la cuenta
  viajan en el mismo `create`, como comandos.
- (c) La unicidad del código (`test_unique_code_per_company`) la daba la
  restricción `(company, code)`, retirada con la columna. La fuente la
  verifica en `_ensure_code_is_unique` (`:1079-1130`); pasa de MC2c-2 a
  MC2c-1 para no dejar la ventana abierta.
- (d) `test_account_code_mapping` afirma que la restricción existe: es la
  premisa de la divergencia de `account.code.mapping` («una cuenta, una
  empresa»), que MC2c deja de cumplir. La prueba se reescribe sobre la
  premisa nueva y el modelo virtual queda como sucesor en este diseño.

### MC2c-2 — retirada de `company` (`account-account-mc2c2-0397`)

1. `_ensure_code_is_unique` al final de `create` y en `write`.
2. `_check_company_domain` en plural.
3. La lectura de `account.company` en `account_merge_wizard` pasa a la
   empresa activa; `create` deja de escribir el puente; la migración
   retira la columna `company`.

## Lo que este diseño no cierra

La medición del paso previo decide si MC2c cabe sin tocar DEC-AISL-04.
