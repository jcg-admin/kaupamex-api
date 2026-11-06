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

1. clonar `jcg-admin/odoo-tools` en el job y exportar `ODOO_TOOLS`;
2. dejar el CI sin referencia y aceptar que esos contratos se verifican sólo
   en sesión.

No se elige aquí: cambia el workflow, que es de TASK-API-0478.

> **Corregido 2026-11-06T06:18:24.** La primera redacción de este punto, y la
> de dos secciones más abajo, decían que `jcg-admin/odoo-tools` es un
> repositorio privado que exige credencial. No se había medido, y es falso:
> la API de GitHub lo declara `"private": false`. Las mismas palabras
> quedaron en los mensajes de `api@ee9c31dd` y `api@8351cd20`, que no se
> reescriben; esta corrección las sustituye. Ver «Acceso de CI a la
> referencia», abajo.

## El gate contractual (2026-11-06)

Un SKIP por referencia ausente es «verificación contractual no ejecutada», no
«contrato satisfecho». El CI general sigue sin referencia —su workflow no
la clona—, y la verificación contractual tiene su propia ejecución, en el
ambiente con la revisión fijada:

```bash
CONTRACT_REFERENCE_REQUIRED=1 uv run pytest -m reference -n 4 -q -p no:cacheprovider --reuse-db
```


- `CONTRACT_REFERENCE_REQUIRED=1` convierte la ausencia del árbol en **fallo**
  de cada prueba marcada, no en omisión;
- el hook de la marca corre `tryfirst`: sin eso, 30 pruebas con `skipif`
  propio (`sale`, `mirrored_roots`, …) se omitían antes de que el modo
  obligatorio decidiera;
- el resumen imprime la revisión de `odoo-tools` verificada.

| ejecución contractual | resultado |
|---|---|
| con `odoo19c` (`odoo-tools@abe4040ec1`) | 259 passed, exit 0 |
| sin `odoo19c` | 259 errors, exit 2 |

El único skip en las dos ejecuciones es `tests/unit/sale/test_address_mx_validation.py`,
que se omite a sí mismo al colectarse (sus serializers esperan redomicilio) y
no depende de la referencia. Controles: sin la rama obligatoria cae un solo
caso de `tests/unit/test_reference_tree_plugin.py`; sin `tryfirst`, 30
pruebas vuelven a omitirse. Salidas: `outputs/check_contracts_*`.

**El target `make check-contracts` no se pudo publicar.** Tocar el
`Makefile` dispara la cualificación de `check_python_style_increment.py`, y
dentro del hook falla: su subproceso hereda el `GIT_INDEX_FILE` temporal del
commit por pathspec y 7 de sus 99 pruebas leen otro índice. Medido: sin la
variable, 99 passed; con un índice alterno, 7 failed. El mecanismo es de
TASK-API-0478 (owner `codex-ci-local`); el target se añade cuando se corrija.

**La dependencia que queda registrada:** ejecutar la verificación
contractual en GitHub Actions exige que el workflow clone la referencia; hasta
que eso se integre, la aceptación contractual se toma de esta ejecución en el
ambiente autorizado, nunca de una suite que omitió los contratos.

## Acceso de CI a la referencia — respuesta a los cinco puntos (2026-11-06)

Medido el 2026-11-06T06:18:24, no supuesto:

1. **Repositorio y revisión.** `jcg-admin/odoo-tools`, revisión contractual
   `abe4040ec1a45beee90fb694e4eae4453e46b389` (la que verificó las 259
   pruebas). El árbol que las pruebas leen es `19.x/odoo-19.0/` (47 862
   archivos versionados, 1.2 GB en disco); el `.git` completo pesa 1.5 GB,
   así que un checkout acotado a esa ruta y a esa revisión es lo
   proporcionado.
2. **Workflow y limitación.** `.github/workflows/api-tests.yml`, que hoy sólo
   ejecuta `actions/checkout@v4` sobre este repositorio. **No hay limitación
   de autenticación demostrada, y no la habrá**: la API de GitHub declara el
   repositorio `"private": false`. Un `actions/checkout` con
   `repository: jcg-admin/odoo-tools` y `ref:` fijado lo clona sin
   credencial adicional.
3. **GitHub App o PAT.** Ninguno de los dos hace falta para leer un
   repositorio público.
4. **Permisos, almacenamiento, rotación, revocación.** No aplican: no hay
   secreto que guardar ni rotar. El único permiso es el `contents: read`
   del `GITHUB_TOKEN` del propio workflow.
5. **Propietario.** El workflow es de TASK-API-0478 (owner
   `codex-ci-local`); no se modifica desde aquí. Además, tocar
   `.github/workflows/` dispara la cualificación del checker de admisión y
   hoy falla dentro del hook (H-API-1151), así que ese cambio depende
   también de su corrección.

La integración sólo se podrá declarar completa cuando una ejecución real del
workflow muestre las tres cosas: que ejecuta
`CONTRACT_REFERENCE_REQUIRED=1 pytest -m reference` contra esa revisión, que
falla si la referencia falta, y que conserva su evidencia.

## Ciega a

- una prueba que lea la referencia sin marca ni fixture: falla sin referencia
  en vez de omitirse, y ese fallo es la alarma; el conteo no la ve;
- un árbol presente pero parcial: el criterio es la raíz, y los guards finos
  de cada módulo siguen decidiendo por debajo;
- `odoo19e`, `odoo18c`, `odoo18e`: ninguna prueba de la población los exige.
