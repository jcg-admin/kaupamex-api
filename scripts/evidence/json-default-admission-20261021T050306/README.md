# Preparación de TASK-API-0420

No se alteró el TaskStore. No hay implementación funcional ORM.
La unidad no está admitida: owner operativo NULL; dependencias funcionales
no acreditadas por las columnas NULL. El claim es de preparación de evidencia.
Codex ejecutó sondas; no hubo inferencia de modelos locales de Thyrox.

Resultados: siete casos sobre Json real, cinco PASS y dos BASELINE_FAILURE,
exit 1. La sonda está deliberadamente roja contra API7416b78e; no se añade
como prueba verde ni se sustituye el gate normal. El control Django sin adaptar
confirma que el detector puede reconocer el objeto compartido y E010.
Faltan dos instancias reales y aceptación Consumer completa.

PostgreSQL16.15: contenedor existente recuperado, tabla JSONB TEMP y ROLLBACK
PASS (exit0), sin modificar esquemas persistentes. QA sin public.res_users.
Canal administrativo, no validación de permisos de aplicación. Una consulta
con config.settings.options.get falló por DB_QA_NAME ausente; no se modificaron
.env para ocultarlo. pg_lsclusters/pg_isready externos no existen; el servidor
sí vive dentro del contenedor. No fue necesaria otra instalación.

Interfaces nativas de Thyrox@9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f:
- session.job_runs.jobs_dir, scaffold_run y settle: manifiesto de este run.
- workbench.manifest.declare_workbench: pregunta, instrumento y límites.
- agents.agent_store.resolve_store_dir(create=False), connect_readonly;
  task.task_ids.mapping_from_store/lookup: identidad estable, lecturas SQL.
- session.claim_fold.active_claims: lectura de claims propios/ajenos.
- claimsCommand --claim/--release --owner codex-json-default-preparation
  --branch feature/codex-workspace-bootstrap: reserva de esta evidencia y
  autoridades documentales; no asignación del propietario de la TASK.
- checkWorkbench(dir): [] y exit0. No runner o TaskStore adicional.

Comandos específicos ejecutados desde API (UV_CACHE_DIR=/workspace/.cache/uv):
PYTHONPATH=src uv run --frozen python probes/json_default_contract.py
  (ruta de probes relativa a este run; código1, log completo outputs/json-default-tests.log).
PYTHONPATH=/workspace/thyrox/src uv run --frozen python probes/task_admission.py
  (misma ruta relativa; código0, outputs/task-admission.log).
docker start kaupamex-postgres-cloud (código0).
docker exec -u postgres kaupamex-postgres-cloud pg_isready (código0).
docker exec -i -u postgres kaupamex-postgres-cloud psql -v ON_ERROR_STOP=1
  -d kaupamex_core_qa (SQL BEGIN/TEMP/INSERT/SELECT/ROLLBACK, código0;
  outputs/postgresql-resource.log conserva resultados íntegros).

La primera reserva omitió el sufijo horario: se liberó inmediatamente y se
reservó el directorio exacto. El ledger preserva ambas operaciones; no se forzó
ningún solape. Claim ajeno TASK-THYROX-1072/vm-r continúa preservado; este lote
no usa su proyección de dependencias ni acredita progreso del agente remoto.

Trazabilidad: 14 elementos en outputs/unit-contract.json, referencias fijadas
por hash en provenance.json. La plantilla XLSX es ejemplo metodológico,
no autoridad para introducir IDs de negocio. Se actualizaron el plan y el
progreso existentes, sin nuevo plan rector ni inventario global.

API109 OPEN/UNSTABLE, CI FAILURE, head7416b78e; Docs154 OPEN sin checks,
head4f24ff841 (estado de entrada). gh run view39529351795 --log-failed terminó
con código0 y salida vacía: /workspace/scratch/api-ci-39529351795.log, 0bytes.
No se atribuye causa nueva a esa descarga. Publicación posterior se verifica
contra los nuevos heads; no hubo merge. Sphinx NOT_EVALUATED, sin cambios RST
funcionales del sitio. No se desactivan gates ni se presenta un rojo como PASS.
