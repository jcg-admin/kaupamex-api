# Hallazgo 2026-05-19: Orders admin cluster — sin bug de codigo

## Cluster investigado

`tests/integration/orders/test_admin_order_management.py` y
`tests/integration/orders/test_order_management.py` (UC-ORD-ADM-*).

## Sintoma reportado en baseline

Baseline original (pytest sin flags) reportaba 27 errors, varios de ellos
en este cluster con trazas tipo:

```
MySQLdb.OperationalError: (1213, 'Deadlock found when trying to get lock; try restarting transaction')
```

## Investigacion

1. Cluster ejecutado en aislamiento:
   `pytest tests/integration/orders/test_admin_order_management.py tests/integration/orders/test_order_management.py`
   -> 45 passed, 0 failed, 0 errors.
2. Full suite con `-p no:randomly` (orden determinista):
   639 passed, 18 failed, **0 errors**.
3. Full suite con orden aleatorio (`pytest-randomly` default):
   genera deadlocks intermitentes en tests que comparten transacciones
   con cart/checkout/payments cuando se mezclan en ciertos ordenes.

## Causa raiz

No hay bug de codigo en orders admin. Los errores reportados como
"orders admin cluster" eran efectos secundarios del plugin
`pytest-randomly`: al reordenar tests, fixtures con
`@pytest.fixture(scope="session")` + `transaction=True` colisionan con
locks pendientes de cart/inventory en MariaDB.

## Decision

No requiere fix en orders admin. Si se quiere eliminar el ruido en
re-baselines, dos opciones:

1. Ejecutar pytest con `-p no:randomly` por defecto (anadirlo a
   `pytest.ini > addopts`).
2. Aislar el cluster orders/checkout/payments con `pytest-django`
   `--reuse-db` y `pytest -x` para detectar la primera carrera.

## Impacto en re-baseline (tras fix de is_featured)

Antes:  612 passed, 18 failed, 27 errors.
Despues (orden determinista): 639 passed, 18 failed, 0 errors.
La diferencia de 27 passed proviene de catalogue is_featured (~17) +
orders deadlocks intermitentes que desaparecen sin tocar codigo.

## Pendiente

Las 18 failures restantes viven en `settings_app/test_site_settings_model.py`
y `test_site_settings_api.py` (cluster SiteSettings — proxima sesion).
