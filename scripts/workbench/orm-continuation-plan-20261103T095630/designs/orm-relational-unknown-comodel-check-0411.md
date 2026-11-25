# Check de `comodel_name` desconocido (`orm-relational-unknown-comodel-check-0411`)

TASK-API-0411. Fila de propuesta: `candidates/orm-relational-unknown-comodel-check-0411.jsonl`
del commit `fd816c6e` (rama `wt/account-mc2c2`; no está en esta rama, se
leyó con `git show`).

## Lo que dice la referencia

`odoo19c: odoo/orm/fields_relational.py:90-94` — `Relational.setup_nonrelated`
afirma la existencia del comodelo contra el registro:

    assert self.comodel_name in model.pool, \
        f"Field {self} with unknown comodel_name {self.comodel_name or '???'!r}"

`{self}` es `modelo.campo`. El registro es la tabla de nombres punteados:
un `AbstractModel` también está en él, así que un comodelo abstracto pasa.

## Lo que tiene el puerto (medido)

- `src/orm/fields_relational.py:1420-1463` — `_deferred_comodel`: si el
  `_name` no está registrado al construir el campo, a Django se le entrega
  la etiqueta centinela `orm.<nombre_con_guiones_bajos>` y el nombre de la
  fuente queda en `field.comodel_name`. Su docstring ya declara que el
  check de existencia es el sucesor de este caso.
- `src/orm/registry.py:353-428` — `SENTINEL_APP_LABEL`, `sentinel_label`,
  `sentinel_key`, `flush_sentinel`: el centinela se vacía en `class_prepared`
  del destino. Si el destino nunca se declara, la clave queda en
  `_pending_operations` y `remote_field.model` sigue siendo la cadena.
- `src/orm/checks.py` no registra ningún check (sólo envuelve
  `run_checks`), y ningún módulo de `src/` lo importa: hoy no corre en el
  arranque.

Medido con una sonda en `isolate_apps('addons.stock')` y `Many2one('res.partnerr')`:

- `remote_field.model == 'orm.res_partnerr'`, `comodel_name == 'res.partnerr'`,
  `_pending_operations == [('orm', 'res_partnerr')]`;
- Django ya lo detecta, pero con `fields.E300` *"Field defines a relation with
  model 'orm.res_partnerr', which is either not installed, or is abstract."*:
  nombra el centinela, no el nombre que el autor escribió. `fields.E307`
  (sólo en el registro global) nombra también la etiqueta centinela y la app
  `orm` inexistente;
- `Many2many('res.partnerr')` deja igual `remote_field.model = 'orm.res_partnerr'`;
- `Many2one('ir.fields.converter')` (registrado con `register_abstract`) queda
  con centinela permanente, y la fuente lo admitiría (está en el registro).
- pytest-django no corre system checks (`pytest_django/plugin.py` y
  `fixtures.py` no llaman `run_checks`) y `tests/conftest.py` tampoco.

## Símbolos

- `src/orm/checks.py`: nuevas `unknown_comodel_errors(models)` (la regla) y
  `check_unknown_comodel(app_configs=None, **kwargs)` (el check registrado
  con la etiqueta `models`, id `orm.E001`); constante `UNKNOWN_COMODEL_ID`.
  El registro se omite cuando el módulo corre como `__main__` (`python -m
  orm.checks`): allí el módulo se importa dos veces y el check quedaría
  duplicado.
- `src/orm/registry.py`: `import orm.checks` al final del módulo, para que el
  check quede registrado en todo proceso que cargue el ORM.

Regla: un campo de `local_fields` o `local_many_to_many` cuyo
`remote_field.model` es todavía una cadena con `app_label` `orm` y cuyo
`comodel_name` no está en `MODELS_BY_NAME` (`model_by_name`) produce un
`Error` con el mensaje de la fuente: `Field <modelo>.<campo> with unknown
comodel_name '<nombre>'`, donde `<modelo>` es el `_name` o la etiqueta de
Django.

## Pruebas (`tests/unit/orm/test_checks_unknown_comodel.py`)

Modelos sonda dentro de `isolate_apps('addons.stock')`, consultados con
`app_configs=[<la app aislada>]`, para no dejar un modelo roto en el
registro global.

1. `Many2one('res.partnerr')`: un error `orm.E001` que nombra el campo y
   `'res.partnerr'`, y no el centinela;
2. `Many2many('res.partnerr')`: lo mismo;
3. `Many2one('res.partner')`: ningún `orm.E001`;
4. `Many2one('ir.fields.converter')` (abstracto registrado): ningún
   `orm.E001`, como la fuente;
5. el check está en el registro de Django con la etiqueta `models`;
6. el árbol real (`run_checks()`): ningún `orm.E001`.

Anulación: `unknown_comodel_errors` devuelve `[]`; deben caer 1 y 2.

## Lo que no cierra

- `One2many` (`fields_relational.py:134`) no es un campo de Django y no deja
  centinela: su comodelo desconocido falla al usarse (`apps.get_model`), no
  en este check. DESCONOCIDO con condición de cierre: medir si un
  `One2many` con comodelo inexistente llega al arranque sin error.
- `fields.E300`/`E307` siguen apareciendo junto a `orm.E001` para el mismo
  campo; silenciarlos no es parte de esta unidad.
