# `Command` como `IntEnum`

Banco del análisis `docs: source/gestion/pm/api/iniciativas/completar-raiz-orm/analisis-command-como-intenum.rst`.
Referencia: `odoo19c` en `odoo-tools@abe4040ec1a45beee90fb694e4eae4453e46b389`.

## Search Existing

| Candidato | Qué mide | Por qué no basta |
|---|---|---|
| `tests/unit/orm/test_command_declarative.py` | triples y forma ejecutiva | no mide el tipo del triple ni el enum |
| `basemodel-contract-reach-20261105T021145/probes/channel_census.py` | vía de llegada de miembros de `BaseModel` | no cubre `Command` |

Veredicto: MISSING para el censo de uso en la referencia y la conducta del
`IntEnum` instalado; se escriben los dos instrumentos de `probes/`.

## Comandos

```bash
eval "$(python3 scripts/reference_roots.py --env)"
.venv/bin/python "$B/probes/reference_usage_census.py" "$ODOO19C" "$B/outputs/reference_usage_census.txt"
.venv/bin/python "$B/probes/intenum_behaviour.py" > "$B/outputs/intenum_behaviour.txt"
.venv/bin/python -m pytest -q --reuse-db -p no:cacheprovider tests/integration/test_orm/test_contract_commands_command_class.py
```

## Salidas

- `outputs/reference.txt`: definición de `Command` y reconocimiento de listas de comandos en la referencia.
- `outputs/reference_usage_census.txt`: uso de `Command` en los 8566 `*.py` de `odoo19c`, por forma.
- `outputs/intenum_behaviour.txt`: conducta del `IntEnum` frente a `int` en Python 3.13.18, y la falla de `tuple()` sobre una clase plana.
- `outputs/mutations.txt`: cuatro mutaciones y las pruebas que cae cada una.

Métrica: AST de la referencia por forma de uso; conducta medida en el intérprete.
Ciega a: un consumidor que reciba el código sin nombrar `Command`.

Primer defecto del instrumento, corregido: el clasificador dejaba
`tuple(Command)` e `isinstance(x, Command | int)` como «otras» apariciones.
