# Entorno de referencia aislado de odoo19c

TASK-API-0498 decía que cargar `odoo.orm.models` exigía añadir werkzeug,
lxml_html_clean, psycopg2 y rnc2rng al Consumer. Esa premisa no estaba
demostrada: el `ModuleNotFoundError` describía el intérprete con que se cargó
la referencia, no una necesidad de Kaupamex.

## Separación

| Entorno | Qué contiene | Quién lo declara |
|---|---|---|
| Referencia | venv desechable fuera del repositorio, instalado desde `odoo19c: requirements.txt` | la propia referencia |
| Consumer | `.venv` desde `pyproject.toml` y `uv.lock`, sin cambios | Kaupamex |

El proceso de referencia corre con `-I -B`: no ve `src/`, ni los settings de
Django, ni los parches que el Consumer cuelga sobre Django (el defecto de
medición de H-API-1089). Los diferenciales con modelo comparan trazas
serializadas entre ese subproceso y el puerto.

## Sustituciones declaradas

- `python-ldap` retirado: compila contra `lber.h`, ausente en el contenedor.
  Sólo lo usa `auth_ldap`.
- `psycopg2==2.9.10` → `psycopg2-binary==2.9.10`: mismo código en rueda; la
  compilación exige `libpq-fe.h`.

## Resultado

Ver `outputs/record.json`: referencia exit 0 (59 módulos `odoo`, Django
ausente del proceso), control con el intérprete del Consumer exit 1, y
`odoo-tools` sin cambios.

## Base de referencia y diferencial con modelo

Un `Registry` real necesita `base` instalado (sin él, `KeyError: 'ir.model'`).
`initialize_reference_database.py` crea `orm_refproc_<sufijo>` con el rol de QA
y ejecuta `odoo.cli.main -i base` con el intérprete de referencia; imprime las
variables que lee `tests/fixtures/reference_process.py`:

```bash
.venv/bin/python scripts/workbench/reference-environment-isolated-20261106T071536/initialize_reference_database.py \
    <venv>/bin/python orm_refproc_contract <data_dir> scripts/workbench/reference-environment-isolated-20261106T071536/outputs
CONTRACT_REFERENCE_REQUIRED=1 uv run pytest tests/unit/orm/test_contract_domains_model_reference.py -q
```

Resultado: 1 144 de 1 144 pasos iguales en modo `user` y en modo `su`. El
modo existe porque `Environment.__new__` fuerza `su=True` para el uid 1
(`odoo19c: odoo/orm/environments.py:64-67`): sin declararlo, la primera
comparación dio cuatro diferencias que eran de la configuración de la prueba
diferencial, no del puerto (H-API-1154).

## Frontera del ORM central y siguiente trabajo ejecutable

`outputs/core_orm_frontier.tsv` clasifica, desde el inventario vigente, cada
obligación no satisfecha de `domains.py`, `environments.py`, `registry.py` y
`models.py`:

| Estado | Qué significa | Cómo se cierra |
|---|---|---|
| `pending_verification` | estructura igual, sin evidencia | una prueba diferencial que la ejerza y discrimine |
| `signature_divergence` | firma distinta de la fuente | alinear, o declarar la divergencia y dejarla `not_verified` |
| `name_divergence` | homónimo o emparejado por nombre | decidir si es el mismo contrato |
| `not_resolved_in_port` | el censo no resuelve el símbolo aquí | portarlo o declarar su ausencia |
| `not_implemented` | ausente en el puerto | portar con TDD |
| `value_divergence` | atributo con otro valor | igualar o declarar |

Divergencias declaradas que quedan `not_verified` a propósito:
`_value_to_date`/`_value_to_datetime` (sin `env`: la zona y el idioma salen
del canal de `orm.environments`), `_as_predicate` (la hoja no admite `any`
sobre relaciones ni valores `Query`/`SQL`), `Environment.__getitem__` (clase
contra recordset vacío), `Environment.__eq__`/`__ne__` (por valor contra
identidad), `check_company_domain_parent_of` y
`check_companies_domain_parent_of` (leen `parent_path` de la base).

Siguiente trabajo ejecutable: los `pending_verification` de `registry.py` y
`environments.py` que no dependen de datos de la base (las vistas de la
transacción y las guardas de elevación), con la misma prueba diferencial
contra el proceso de referencia.
