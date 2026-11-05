# Alcance de los contratos de `BaseModel` en los modelos de producción

Banco de la revisión metodológica de H-API-1145 (2026-11-05). Referencia:
`odoo-tools@abe4040ec1a45beee90fb694e4eae4453e46b389`; Django 6.0.5
instalado en `.venv/lib/python3.13/site-packages/django`.

## Search Existing

| Candidato | Qué mide | Por qué no basta |
|---|---|---|
| `basemodel-contract-20260911T030334/census_ours_models.py` | métodos declarados por clase en `src/orm/models.py` | nombre por clase, no por modelo concreto |
| `basemodel-trae-contracts-20260911T050421/probes/probe_who_declares.py` | qué clase del MRO declara un nombre de Django | sólo clases de Django, no nuestros modelos |
| `orm-symbol-presence-census-20260910T175850` | presencia de símbolos por archivo espejo | ciego a la vía de llegada |
| sonda original de H-API-1145 | `issubclass(model, BaseModel)` | no se versionó; ciega a mixins, parches y delegación |

Veredicto: EXTEND del criterio de `probe_who_declares` (dueño en el MRO),
aplicado a cada modelo concreto de producción.

## Comandos

```bash
cd src; eval "$(python3 ../scripts/reference_roots.py --env)"
PYTHONPATH=. DJANGO_SETTINGS_MODULE=config.settings.testing \
  ../.venv/bin/python "../$B/probes/channel_census.py" \
  "$ODOO19C/odoo/orm/models.py" "../$B/outputs"
cd ..; .venv/bin/python -m pytest -q --reuse-db -p no:cacheprovider \
  "$B/probes/test_probe_crm_lead_behaviour.py"
.venv/bin/python -m pytest -q --reuse-db -p no:cacheprovider \
  tests/integration/crm/test_basemodel_contract_reach.py
```

## Salidas

- `outputs/reference_chain.txt`: cadena `MetaModel`/`BaseModel`/`Model`/
  `AbstractModel`/`TransientModel` y la composición de `add_to_registry`.
- `outputs/django_installed.txt`: manager auto-creado, resolución de managers
  por MRO y `Model.__eq__` del Django instalado.
- `outputs/summary.json`, `channels_by_name.tsv`, `representative.tsv`: la vía
  de llegada de cada uno de los 188 nombres a cada modelo de producción.
- `outputs/crm_lead_behaviour.json`: tres contratos observados en `crm.lead`.
- `outputs/mutations.txt`: las tres mutaciones y la prueba que cae con cada una.

Métrica: clase del MRO que define el nombre, por modelo concreto.
Ciega a: el comportamiento. Un nombre presente por cualquier vía no prueba el
contrato; eso lo miden las pruebas y sus mutaciones.

Primer defecto del instrumento, corregido: `.venv` vive dentro del repo, y la
raíz entera hacía pasar el cuerpo de Django por nuestro (columna `django` en 0).
