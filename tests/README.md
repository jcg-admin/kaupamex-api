# Tests — kaupamex-api

## Base de datos

Los tests usan una BD **completamente separada** de produccion:

| Entorno | BD | Settings |
|---------|----|----------|
| Produccion | `kaupamex_core` | `config.settings.production` |
| Desarrollo | `kaupamex_core` | `config.settings.development` |
| Tests (QA) | `kaupamex_core_qa` | `config.settings.testing` |

Nunca se toca `kaupamex_core` al correr tests.

## Estructura

```
tests/
  conftest.py          fixtures globales (user, api_client, auth_client)
  factories/
    user_factory.py    UserFactory, AdminUserFactory
  unit/
    users/
      test_user_model.py
  integration/
    auth/
      test_jwt_endpoints.py
  fixtures/            datos JSON para loaddata (cuando aplique)
  mocks/               mocks de servicios externos (pagos, email)
```

## Correr tests

```bash
cd src

# Todos
pytest ../tests/

# Solo unitarios
pytest ../tests/ -m unit

# Solo integracion
pytest ../tests/ -m integration

# Un archivo especifico
pytest ../tests/unit/users/test_user_model.py

# Con detalle
pytest ../tests/ -v

# Con cobertura
pytest ../tests/ --cov=apps --cov-report=term-missing
```

## Convenciones TDD

1. Escribir el test primero — debe fallar (RED)
2. Escribir el codigo minimo para que pase (GREEN)
3. Refactorizar sin romper tests (REFACTOR)

Cada test documenta un comportamiento esperado del sistema.
Los nombres de los tests son la documentacion: `test_login_con_credenciales_validas_retorna_200`.

## Marcadores

```python
@pytest.mark.unit         # Test de modelo o servicio aislado
@pytest.mark.integration  # Test de endpoint o flujo completo
@pytest.mark.api          # Test de contrato de API (estructura de respuesta)
```
