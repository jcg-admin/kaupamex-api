# Ejecutores de referencia dentro de Kaupamex — inventario y deuda (3.2.14-C.2)

Fecha: 2026-11-09T04:51:56

Medido con `rg -l -e "import_module\(['\"]odoo" -e "^\s*(from|import) odoo\b"` y
`rg -l "spec_from_file_location|exec_module|import_module"` sobre el árbol, sin `.venv`.

| Archivo | Cómo carga Odoo | Proceso | Consumidores |
|---|---|---|---|
| `tests/fixtures/reference_process.py` | lanza `CONTRACT_REFERENCE_PYTHON -I -B` | aislado | `run_script`, `trace` |
| `tests/fixtures/reference_tree.py` | resuelve la raíz de `odoo-tools` | pytest (sólo rutas) | 5 |
| `tests/fixtures/reference_model_trace.py` | `importlib.import_module('odoo…')` | aislado | 2 |
| `tests/fixtures/reference_field_groups.py` | ídem | aislado | 1 |
| `tests/fixtures/reference_access_on_read.py` | ídem | aislado | 1 |
| `tests/fixtures/reference_res_groups_implied.py` | ídem | aislado | 1 |
| `tests/fixtures/reference_domains.py` | `spec_from_file_location` de módulos de `odoo19c` | **dentro de pytest** | 2 |
| `reference/provenance/probe_implicit_access_message.py` | copia del driver de acceso | aislado | ninguno (sólo procedencia) |

No son importaciones: `addons/account_test/data/accounting_assert_tests.py:156` (cadena
`code_exec` verbatim de la referencia) y `src/tools/profiler.py:67` (docstring).

## Estado

- Deuda arquitectónica identificada: las pruebas de contrato de `tests/unit/**/test_contract_*_reference.py`
  dependen de estos ejecutores. Se conservan mientras su uso está permitido y **no se amplían**.
- `reference_domains.py` es el caso más fuerte: ejecuta código de la referencia en el proceso de pytest.
- Ruta de separación: el ejecutor vive fuera del Consumer (Provider, cuando exista la capacidad cualificada)
  y entrega resultados estructurados a `reference/observations/`; la prueba de Kaupamex compara contra el dato.
  Primer caso aplicado: `observations/inherited-implicit-access-message.json`.
- La 3.2.14-C.1 amplió `reference_access_on_read.py` con el párrafo de acceso implícito; esa ampliación se
  revirtió antes de commitear y el escenario se registró como observación.
- Capacidad del Provider pendiente: ejecución gestionada de escenarios de referencia del Consumer
  (no se construye aquí).
