# Revisión de los seis hogares y del workbench completo de API

Revisión de cobertura solicitada el 2026-10-19. Es análisis directo de Codex,
registrado mediante Thyrox; no es una TASK ejecutada por un modelo local.
No se cambió código de producto, configuración, dependencias ni estado de TASK.

## Universo y alcance efectivo

`summary.json` fija revisiones y rutas resueltas por Thyrox. El inventario
`inventory.jsonl.gz` contiene ruta, tamaño y SHA256 de los 86.008 archivos
versionados de los seis hogares (1.793.975.163 bytes). Es una instantánea ANTERIOR
a este run. No comprende archivos ignorados/no versionados ni otras ramas.
No equivale a haber leído semánticamente 1,79 GB.

API workbench: 355 archivos, 50 piezas; 50 JSON y un JSONL. Se indexaron todas
las piezas, sus instrumentos declarados, métricas y cegueras en `api-coverage.json`.
Sólo 10 piezas tienen README propio. Tres archivos viven directamente en la raíz.
No se ejecutaron indiscriminadamente los 121 Python ni sus copias de anulación:
varios escriben datos, mutan fuentes o reescriben resultados históricos.

Se leyeron los 3.641 manifiestos de nombre manifest.json/jsonl con el lector
existente de Thyrox: ninguno produjo error de parseo. Esto NO certifica su
conformidad. Se localizaron además 80 manifiesto.json heredados y se parsearon
como JSON sin traducirlos ni someterlos al contrato inglés del Provider.
La búsqueda léxica complementaria encontró 111 archivos en los otros hogares
(51 API jobs, 34 Docs workbench, 26 Thyrox workbench). `cross-home-index.json`
registra rutas y líneas. Filtró extensiones textuales y excluyó node_modules y
bunfs-root; un cero no demuestra ausencia de evidencia ni aceptación.
Los registros de recuperación, embeddings, copias de tableros y prompts
con coincidencias no son ejecuciones ORM ni cualificación actual de modelos.

## Hallazgos contrastados

1. El gate histórico API acepta 50/50 (exit 0). `checkWorkbench` de Thyrox
   devuelve exit 1 con cuatro piezas observadas: basemodel-trae-contracts,
   cascara-de-store-del-consumidor, fetch-contract y two-caches-descriptor.
   Tres incluyen rutas relativas al repositorio donde Provider espera rutas
   relativas al run; los archivos existen. Fetch también carece de tests/.
   En cascara coexisten JSON declarativo y JSONL de bitácora: resolve_manifest
   prioriza este último, cuyo parseo no falla pero pierde las cinco claves.
   Son límites de metadatos/compatibilidad heredados, no regresiones ORM.
2. verify_premise --workbench --strict: 9.616 símbolos / 2.421 archivos,
   tres señales entre 50 piezas, exit 1. No autoriza cerrar TASK. En fachadas,
   la ruta de Odoo addons/base/models/res_company.py se interpreta como ruta
   local; setup_related encuentra un homónimo. En filter_function la presencia
   refleja trabajo ya aterrizado. El prefijo .js de census_open_api_tasks.json
   surge de una expresión regular que acepta la extensión corta dentro de json;
   no prueba que falte un instrumento .js. Las señales requieren contexto.
3. probe_merge_seam ahora imprime dos CharField e isinstance True/True,
   pero conserva el veredicto textual constante «NUNCA … sólo object» y sale 0.
   Ese veredicto quedó obsoleto. fields_textual documenta TASK-API-0417.
4. probe_declarations_survive conserva claves en 5/5 casos actuales.
   TestOrmCategory.display_name conserva compute, inverse y recursive.
   La otra sonda histórica sigue exigiendo NonStored y compara un search de
   base todavía sin setup (None) con el override preparado: esos False no
   demuestran pérdida de contrato. El censo histórico da cero cruces
   stored/NonStored sobre 399 modelos; no certifica toda herencia de campos.
5. Pruebas existentes test_field_definition_collection: 19 PASS,
   2 django_db DESELECCIONADAS explícitamente; cero conexiones intentadas.
   No constituye validación de lectura persistida ni del SELECT real.
6. Contraste adicional: Django permite redeclarar un campo de una base
   abstracta. La sonda construye la clase hija sin FieldError; conserva inverse
   y max_length, pero compute del padre no se hereda y la colección devuelve
   un eslabón. Refuta la prohibición general afirmada por el docstring de
   _collect_field_definitions y por LabelMixin en el test. El impacto respecto
   de la jerarquía Odoo necesita mapear consumidores y clases de definición;
   no se convierte automáticamente en TASK nueva ni regresión actual.
   La primera ejecución falló AL GUARDAR el JSON por NameError de Path tras
   completar las aserciones; se corrigió sólo la sonda y la repetición salió 0.
7. fetch_dependencies responde 0 ausencias/9 preguntas sobre cuatro campos
   concretos y una relación de ResPartner. Su instrumento admite que mide
   disponibilidad, NO semántica ni fetch/prefetch/persistencia aceptados.
8. create-por-contenido conserva evidencia histórica 12/12 y el código actual
   DefaultGetMixin.create(vals_list), commit c1161377. El banco fachadas conserva
   cuatro vías de escritura/inverso sobre country con lectura persistida.
   No se reejecutaron contra DB ni se generalizan a todos los campos.

## TASK y dependencias comprobadas

Se consultó mapping_from_store y después SELECT mode=ro por identidad estable;
`tasks-related.json` contiene resultado sin cambiar el store. 0415, 0416, 0421,
0426 figuran completed; no se duplican. 0418, 0419, 0422, 0424 y GEN-0634
siguen pending, owner NULL: ninguna queda elegible sólo por ese estado.
0416 corresponde a 67252948; create a c1161377. 0418 debe reconciliarse por
familia: Char ya no usa NonStored, y la clase NonStored aún existe/exporta.
0419 trata reconstrucción relacional, no bloquea toda lectura de relaciones.
0422 depende del contrato de acceso durante create/_inherits; 0424 del campo
sin columna searchable en recompute; GEN-0634 de campos delegados navegables.
Los deps NULL del store no prueban independencia. Sigue faltando cualificación
local de selección→ejecución→verificación→aceptación→integración en Thyrox.

## Interfaces, ejecución y resultados

Provider 9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f:
- inspect.unwrap(workbench.paths.workbench_dir)(root) y
  inspect.unwrap(session.job_runs.jobs_dir)(root): lectura sin crear hogares.
- workbench.manifest.read_manifest_file/resolve_manifest: contratos inspeccionados;
  no se añadió lector genérico ni se convirtió el corpus heredado.
- session.job_runs.scaffold_run/declare_workbench/settle: registro de este run.
- CLI claimsCommand: reservas administrativas sin TASK ficticia; se liberan al cerrar.
- TypeScript checkWorkbench: se ejecutó sobre las 50 piezas, resultados en JSON.

Comandos Consumer desde raíz API, con UV_CACHE_DIR de la sesión y PYTHONPATH
src + Thyrox/src, sin editar .env:

```sh
uv run --frozen python scripts/check_workbench.py --strict
uv run --frozen python scripts/verify_premise.py --workbench --strict
uv run --frozen python scripts/evidence/six-homes-review-20261019T225615/outputs/revalidate_existing.py
uv run --frozen python scripts/evidence/six-homes-review-20261019T225615/outputs/revalidate_override.py
uv run --frozen python scripts/evidence/six-homes-review-20261019T225615/outputs/field_definition_tests.py
uv run --frozen python scripts/evidence/six-homes-review-20261019T225615/outputs/abstract_override.py
```

Los cuatro últimos son envoltorios diagnósticos conservados en outputs; las
rutas de escritura scratch reflejan esta sesión, no instalación del producto.
Usan credenciales sintéticas en memoria y un guard que rehúsa conexiones. Los
instrumentos originales no se modificaron. Los logs completos acompañan a cada
prueba; el índice mecánico usa git ls-files -z y hashlib.sha256. El inventario
completo no se emite en la terminal por su volumen.

Sphinx NOT_EVALUATED. Persistencia NOT_EVALUATED. Ningún build completo repetido.
El run se asienta exit 1 por los verificadores no conformes, preservando sus
resultados; no se presenta como aceptación global del ORM.
