# Implementación acotada de TASK-API-0420

Cambio funcional: src/orm/fields_misc.py::Json usa el mecanismo callable de
Django con partial(deepcopy, literal). No cambia la declaración fiel history.
El nuevo mandato autoriza la ejecución con claim nativo válido; no se deduce
admisión de owner=NULL. Se reservaron código y pruebas sin conflicto.
No se alteró el TaskStore. Codex ejecutó ingeniería; no modelos de Thyrox.

Reproducción desde el Consumer API, PYTHONPATH=src; caché uv del entorno:
- uv run --frozen python <run>/probes/json_default_contract.py
  baseline.log: exit1, 5PASS/2FAIL; after.log: exit0, 7PASS.
- uv run --frozen python <run>/probes/postgresql_models.py
  postgresql-models.log: exit1, HBA rechaza rol de fixture; cleanup ejecutado.
  postgresql-models-scoped-auth.log: exit0; 7 pruebas nuevas y persistencia real.
  El rol QA aleatorio sólo recibe CONNECT/TEMP. Regla SCRAM efímera limitada
  al host del bridge local, rol y QA; retirada en finally, junto al rol.
  Se verificó después: cero roles y reglas json_contract_. No tablas persistentes.
- uv run --frozen python <run>/probes/django_contracts.py
  regressions-final.log: exit1, 47PASS/3FAIL heredados de vocabulario declarado.
- mismo comando con --baseline: original Json de API6d8c0afb sólo en memoria;
  baseline-negative-control.log: exit1, 41PASS/9FAIL; los mismos3 y seis JSON.
  No se altera código o HEAD para el control. No se ocultan los tres fallos.

Los primeros contextos aislados carecían de contenttypes o del orden de
inicialización ORM; logs django-unit.log y field-regressions.log preservados
con exit1/2. Se corrigió únicamente el contexto de prueba. Se usa contenttypes
real y carga orm.models; sin desconectar señales o silenciar checks.
El contexto aislado evita el conftest de addons incompleto; no reemplaza CI.
No se acredita ejecución de la suite normal ni makemigrations global.

14 elementos vigentes en outputs/unit-contract.json. Referencia fijada a
abe4040ec1a45beee90fb694e4eae4453e46b389, por procedencia anterior verificada;
consumidor test_orm.models.test_orm.history sin modificación. get_default()
es contrato existente de default_get e _init_column. Callable/None/missing,
escalares, nested mutable, deconstruct/clone/serialization y metadata pasan.
Related integral, addon Discussion completo, fixtures QA y aceptación siguen
not_verified. No merge, migración de TASK, nuevo Field, enum o Provider.

Mecanismos Thyrox@9b13f2d7: session.job_runs.jobs_dir/scaffold_run/settle;
workbench.manifest.declare_workbench; checkWorkbench: [] exit0;
claimsCommand --claim/--release --task TASK-API-0420; resolve_store_dir,
connect_readonly, mapping_from_store/lookup, active_claims para identidad y
aristas crudas. admission-and-provider.json guarda revisiones, claims y hash
antes/después. Claim vm-r/1072 preservado; no se afirma ejecución remota viva.

Frontera: revisión/CI de este cambio, preparación completa de QA y aceptación
Consumer. No cerrar la TASK por este commit ni depender de cualificar BABOK.
Los resultados BABOK se publican separados en el expediente vigente de Docs.

Portabilidad: los paths físicos observados en JSON son procedencia, no
contratos de recuperación. Recuperar con latest_run(jobs_dir(consumer_root()),
"json-default-implementation") usando el Consumer declarado; los punteros
scratch sólo facilitaron comandos temporales y no son entradas del verificador.
