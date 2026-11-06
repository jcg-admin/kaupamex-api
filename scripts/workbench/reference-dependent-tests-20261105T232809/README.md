# Pruebas que dependen del árbol de referencia — TASK-API-0494

## Pregunta

¿Qué pruebas de la suite dependen de `odoo19c` (odoo-tools), y qué hacen en
un entorno sin él, como el CI?

## Instrumento

`run_with_and_without_reference.sh` ejecuta la suite completa dos veces con
`-n 4`: con la referencia y con `ODOO_TOOLS=/nonexistent-odoo-tools`.
`compare_junit.py` compara los dos JUnit prueba por prueba. La población
dependiente es la que cambia de resultado entre las dos ejecuciones, medida por
ejecución y no por mención textual (la palabra `odoo-tools` aparece en 128
archivos, casi todos citas de procedencia).

## Antes de la marca (2026-11-05)

| | con referencia | sin referencia |
|---|---|---|
| passed | 12 116 | 11 859 |
| skipped | 31 | 256 |
| failure | 0 | **32** |
| error | 5 | 5 |

257 pruebas cambian de resultado: 225 se omitían con un guard propio de cada
módulo y **32 fallaban**, en cinco archivos de `tests/unit/scripts/`, porque
el script que miden lee el árbol sin comprobar antes que exista.
`make ci-verify` ejecuta `pytest --maxfail=1` y el CI no clona odoo-tools: la
primera de las 32 detiene la ejecución.

Los 5 errores son los mismos en las dos ejecuciones:
`tests/integration/company/test_multidb_isolation.py` rehúsa, por diseño, una
base por defecto que no sea desechable (`CI_DATABASE_DISPOSABLE`). No dependen
de la referencia.

## La corrección

`tests/fixtures/reference_tree.py`, reexportado en `tests/conftest.py`:

- marca `reference` registrada en `pytest.ini`;
- criterio único: existe el directorio de `reference_roots.tree('odoo19c')`;
- marca automática para la prueba que pide el fixture `reference` (174 de las
  257); explícita en las otras 83, que leen el árbol a través del script que
  miden (44 declaraciones, `outputs/explicit_marks.txt`);
- línea de resumen que cuenta las pruebas marcadas omitidas: un CI «verde» sin
  referencia lo dice.

La granularidad es por clase o función, no por módulo: 28 de los 30 módulos
mezclan pruebas dependientes con casos escritos a mano que se ejecutan sin la
referencia, y marcar el módulo los habría ocultado en el CI.

## Después de la marca

| | con referencia | sin referencia |
|---|---|---|
| passed | 12 127 | 11 870 |
| skipped | 31 | 288 |
| failure | 0 | **0** |
| error | 5 | 5 |

Las 11 pruebas nuevas son `tests/unit/test_reference_tree_plugin.py`. Las 257
transiciones son ahora todas passed → skipped. La línea de resumen sin
referencia: `referencia: 257 de 257 pruebas marcadas se omitieron (… no
existe); sus contratos NO se verificaron en esta ejecución`.

## Controles de mutación

Cada mutación cambia comportamiento ejecutable y se restauró con `cmp`:

| Mutación | Cae |
|---|---|
| `mark_items` no marca | 1 caso: el de la marca automática |
| el skip no se aplica | 1 caso unitario, y en la población sin referencia vuelven **exactamente 32 failed** |
| el conteo no suma omisiones | 1 caso: el del conteo |

El segundo control destapó una prueba que pasaba sin medir nada:
`test_no_column_is_required_only_by_omission` da 0 infractores sobre un índice
vacío. Lleva ahora un piso (`assert declared`), verificado contra un árbol
que existe y está vacío: falla con «el índice de la referencia salió vacío».

## Decisión pendiente del ejecutor: la referencia en el CI

Hoy el CI no clona odoo-tools, así que **ninguno de los 257 contratos se
verifica en el CI**; sólo en una sesión con la referencia montada. La marca
lo hace visible, no lo resuelve. Las dos salidas:

1. clonar `jcg-admin/odoo-tools` en el job (repositorio privado: exige una
   credencial de lectura en el workflow) y exportar `ODOO_TOOLS`;
2. dejar el CI sin referencia y aceptar que esos contratos se verifican sólo
   en sesión.

No se elige aquí: cambia el workflow y sus credenciales.

## Ciega a

- una prueba que lea la referencia sin marca ni fixture: falla sin referencia
  en vez de omitirse, y ese fallo es la alarma; el conteo no la ve;
- un árbol presente pero parcial: el criterio es la raíz, y los guards finos
  de cada módulo siguen decidiendo por debajo;
- `odoo19e`, `odoo18c`, `odoo18e`: ninguna prueba de la población los exige.
