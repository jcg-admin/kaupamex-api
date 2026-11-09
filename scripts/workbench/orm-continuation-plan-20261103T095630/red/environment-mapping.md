# RED — unidad 6e-0 (`Environment` como `Mapping`)

Revisión base: `d31f8f48`. Diseño: `designs/environment-mapping.md`.

```
uv run --frozen pytest -q --reuse-db -p no:cacheprovider \
    tests/unit/orm/test_environment_mapping.py
3 failed, 1 passed
```

Caen `isinstance(env, Mapping)`, `get` y `keys`; pasa la igualdad por
identidad, que no depende de `Mapping`.

## GREEN y anulación

`4 passed`, más `test_contract_environments_reference.py` y
`test_environments_channels.py` (`12 passed, 2 skipped` en total).
Sin la base `Mapping` caen exactamente los 3 que dependen de ella y la
identidad sigue verde.

## Supresión inerte retirada

`environments.py` tenía `# noqa: BLE001` sobre un `except Exception` que
registra el error. Ningún linter del repositorio lee `BLE001` (medido: 0
configuraciones de `ruff` en `Makefile`, `.githooks/`, `.github/workflows/`
y `pyproject.toml`), y `pycodestyle` no marca un `except Exception`. El
control de admisión rechaza cualquier supresión cuya huella cambie, y
cambiar las bases de `Environment` cambia la de esa línea; se conserva la
justificación como comentario normal.

Cambio transversal: la regresión amplia de la revisión que lo contiene es
obligatoria antes de publicar.

## Admisión: cambiar las bases de una clase renueva las huellas de su cuerpo

Primer intento con `from collections.abc import Mapping` en una línea nueva:
20 E501 heredados reaparecieron como "introducidos". La huella de cada
diagnóstico incluye el contexto sintáctico —el índice de la sentencia en el
módulo y la cabecera de cada contenedor—, así que:

- una sentencia nueva de módulo desplaza los índices de todo lo que sigue;
- cambiar las bases de `Environment` cambia la cabecera de la clase.

Se extendió la importación existente (`from collections import abc,
defaultdict`) y se pagaron las 20 líneas largas de `Environment` (envueltas,
sin cambio de conducta). Admisión: `PASS`. Suites del entorno:
`97 passed, 2 skipped`.
