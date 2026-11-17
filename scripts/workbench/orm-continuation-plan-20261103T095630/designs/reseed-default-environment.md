# La resiembra tras un test transaccional vuelca como superusuario

Fecha: 2026-11-17. Lo destapa la F2 de `29285b00` (unidad
`account-journal-payment-method-lines-0515`); el defecto es de
`tests/conftest.py`, no de esa unidad.

## Fallo medido

Tres ejecuciones completas (`29285b00`, y dos sobre `7994ec00`, de código
de producto idéntico) terminan con el mismo error y `EXIT=2`:

```
ERROR tests/integration/service/test_db_provision.py::test_database_exists_catalog
tests/conftest.py:494: in pytest_runtest_teardown  ->  seed()
src/addons/base/data/res_users_data.py:51: in seed_root_user
src/orm/environments.py:559: in flush
    public_user = environment.ref('base.public_user')
ValueError: Identificador externo no encontrado: base.public_user
```

Traza de un plugin desechable sobre `Transaction.flush` en la tercera
ejecución (`gw1`, fase `teardown`):

```
tocompute={} dirty={'base.ResPartner.commercial_partner_id': [18265],
 'base.ResPartner.commercial_company_name': [18265],
 'base.ResUsers.create_date': [1], 'base.ResUsers.write_date': [1]}
default_env=None
```

Antes de la resiembra no había nada pendiente (`pending={} dirty={}` en las
29 pruebas transaccionales trazadas).

## Causa

`pytest_runtest_teardown` repone las filas de migración después del
`TRUNCATE`. El cuarto sembrador crea `base.user_root` y su contacto; esas
altas dejan campos sucios y el `commit` del `atomic` los vuelca. Sin
`default_env`, `Transaction.flush` vuelca como usuario público
(`odoo19c: odoo/orm/environments.py:591-597`), y `base.public_user` lo
repone el **quinto** sembrador. Si la búsqueda del identificador no está en
caché, falla. En las demás pruebas transaccionales la caché conserva la
entrada anterior al `TRUNCATE` y el volcado sale con un id obsoleto: pasan
por un valor en caché que ya no describe la base.

Por qué esta prueba: usa `databases='__all__'` y crea y borra bases, lo que
vacía esa caché. Por qué ahora: UNVERIFIED. La misma prueba pasó en las F2
de `9f23b2fc` y `73d845ac`; no se midió qué cambio de la sesión la dejó sin
la entrada en caché.

## Contrato de la referencia

La carga de datos corre con un entorno de superusuario explícito
(`odoo19c: odoo/modules/loading.py:404`,
`env = api.Environment(cr, api.SUPERUSER_ID, {})`): el volcado nunca recurre
al usuario público.

## Cambio

`tests/conftest.py`: la resiembra pasa a una función `reseed(seeders)` que,
si la transacción no tiene `default_env`, crea
`Environment(DEFAULT_DB_ALIAS, SUPERUSER_ID, {})` antes de sembrar; el gancho
la llama con `_SEEDERS`. Así el volcado de cada sembrador no depende del
orden entre `root_user_seed` y `public_user_seed` ni de una entrada de caché.

## Prueba

`tests/unit/base/test_reseed_default_environment.py`: sin `default_env`, sin
la fila `base.public_user` y con la caché vacía, un sembrador que deja
campos sucios y vuelca termina sin error y sin nada pendiente. Anulación:
retirar la creación del entorno hace caer ese caso con el `ValueError` de
arriba.

*Métrica:* la excepción del volcado y `_has_pending()` tras sembrar.
*Ciega a:* un sembrador que vuelque antes de existir la fila del usuario 1
con una columna `write_uid` que la exija; hoy los tres primeros no dejan
nada sucio (medido en la traza).
