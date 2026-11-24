# MC2b: las altas de `account.account` declaran `company_ids`

Unidad `account-account-mc2b-0397` (TASK-API-0397), tras U6 + MC3
(`designs/account-basemodel-u6.md`) y antes de MC2c
(`designs/account-account-multicompany-code.md`).

## Lo que dice la referencia

- `company_ids` es requerido, con la empresa activa por defecto
  (odoo19c: addons/account/models/account_account.py:97-99).
- `create` (odoo19c: addons/account/models/account_account.py:1011-1051)
  agrupa las altas por su `company_ids`, resuelve las empresas con la activa
  primero (`self.env.company | companies` cuando la activa está entre ellas o
  no se dio ninguna), traduce `prefix`/`code_digits` a un código libre con
  `_search_new_account_code` en la primera empresa, toma el código del
  `code_mapping_ids` de esa empresa si falta, y crea con
  `allowed_company_ids=companies.ids`. Al final llama a
  `_ensure_code_is_unique`.

## Lo que este árbol tiene hoy

Las 90 altas pasan `company=` a `AccountAccount.objects.create` o
`get_or_create` (`grep -rnE "AccountAccount\.objects\.(create|get_or_create)"`):
89 en pruebas y una en `addons/sale_subscription/management/commands/seed_l0_chart.py`.
El cargador del plan contable (`chart_template.load_model_data`) fija
`company` en todo modelo. `save` replica `company` en `company_ids` desde MC1.

## La unidad

1. **`AccountAccount.create`**, porte de la referencia:
   - resuelve las empresas de cada alta desde sus comandos de `company_ids`
     (`SET`, `LINK`, ids sueltos o filas) con la regla de la activa primero;
     sin ninguna y sin empresa activa levanta `ValidationError`, que es lo
     que `required=True` produce en la fuente;
   - `prefix`/`code_digits` → `search_new_account_code` en la primera empresa,
     con la caché de los códigos ya reservados en el lote;
   - escribe `company_ids` con `Command.set` de las empresas resueltas.
   - **Puente hasta MC2c**: la columna `company` toma la primera empresa
     resuelta. MC2c la retira junto con `code`.
2. **Las 90 altas** pasan a `AccountAccount.create({... 'company_ids':
   [Command.set([company.pk])]})` bajo `sudo()`, y `seed_l0_chart` al
   `search` + `create` del ORM.

## Divergencias declaradas

- `code_mapping_ids` no viaja: `account.code.mapping` es aquí un modelo
  virtual sin campo inverso en la cuenta (`account_code_mapping.py`). Sin
  ese campo no hay comando que leer.
- `allowed_company_ids` no se fija en el contexto del alta: ningún default de
  la cuenta depende hoy de la empresa activa salvo `company_ids`, que la
  unidad resuelve antes de llamar a `super`. Se revisa en MC2c, cuando `code`
  pase a calculado sobre `code_store` de la empresa activa.
- `_ensure_code_is_unique` es MC2c: hoy la unicidad la da la restricción
  `(company, code)` de la tabla.

## Símbolos tocados por archivo

- `addons/account/models/account_account.py`: `AccountAccount.create`,
  `_resolve_companies`.
- `addons/sale_subscription/management/commands/seed_l0_chart.py`: `Command.handle`.

## Pruebas

`tests/unit/account/test_account_account_create.py`:
`test_the_active_company_comes_first`,
`test_explicit_companies_without_the_active_one_are_kept`,
`test_without_companies_the_active_company_is_used`,
`test_without_any_company_the_create_is_refused` y
`test_a_prefix_becomes_the_first_free_code`.

Anulación: sin la regla de la activa primero caen las dos primeras; sin el
default, la tercera; sin la traducción del prefijo, la quinta.
