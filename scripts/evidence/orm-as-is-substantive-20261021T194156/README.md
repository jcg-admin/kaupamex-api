# Revisión AS IS sustantiva y continuación GEN0559

Este lote reemplaza las conclusiones genéricas del AS IS anterior; no borra sus resultados ni reconstruye el backlog. Reutiliza la población de 33 descriptores y 66 caracterizaciones completas de test_orm y conserva sus 14 elementos. Estos recuentos NO son un denominador de aceptación funcional.

## Resultado verificable

- TASK AS IS: outputs/task-assessments.json y .md. 60 identidades existentes (55 del alcance anterior más cinco referencias actuales omitidas: API0415/0405/0416/0404 y GEN0634), 73 fuentes acotadas. Cada fila tiene conclusión y siguiente condición específicas, identidad nativa, ownership/claims, dependencias raw, verificadores y resultados por nodeid. No nuevas TASK ni cambios de estado.
- Implementation AS IS/reconciliación: outputs/contractual-assessments.json e implementation-assessments.md. Cada descriptor y cada grupo tienen hallazgo concreto; no arrastre uniforme not_verified. Presencia de código, aceptación y equivalencia siguen siendo diferentes.
- Historia: outputs/github-history.json contiene 78 commits consultados y comandos/exit codes/resultados PR/check-runs; cero consultas fallidas. Commit asociado a PR no prueba aceptación. Lista vacía de checks no es PASS. Ancestry fijada a develop ed55e6d5ff4879f0e7170ed1daf5fb90eff6154f; -G sólo mide líneas coincidentes, historial -L del cuerpo y comparación de declaraciones se registran aparte. El helper _recompute_field de2f01be1b no está en ese develop.
- Ocho ordinales heredados: se consultaron candidatos de todas las sesiones mediante el store nativo; no hay mapeo legítimo de la sesión original. La raíz de board privada /root/.claude/tasks no es accesible. No se inventan identidades por coincidencia numérica ni se escala para leerla.

## Ejecución y aceptación

GEN0559 continúa la admisión previa, no se selecciona por ownerNULL. outputs/continuation-admission.json y retry-contract-14.json conservan alcance/dependencias/14 elementos. Field.recompute ahora comprueba ausencia real con _base_manager y el alias del registro, desmarca grupos ausentes o reintenta una vez; la segunda excepción y AccessError se propagan. No batching0558 ni cierre de toda0424.

16 casos PostgreSQL PASS (siete conservados y nueve adicionales). Control con helper99f: siete de ocho casos de retry fallan y AccessError pasa; mutación independiente que elimina sólo el alias produce un error en el noveno caso. No se sobreescribe código productivo para controles. Logs completos retry-final.log, retry-final-negative.log y retry-alias-negative.log. El primer intento sin PYTHONPATH y la regresión transitoria de import están reconocidos, no se cuentan como defectos del baseline.

Regresión existente:312PASS/1XFAIL. Lote incremental sin omitir fallos:29PASS/7FAIL/2errores de fixture. Los dos errores de field collection requieren provisión pytest-Django que el rol QA limitado no permite; no se aumentan privilegios. Muchas expectativas NonStored quedaron obsoletas tras0417, pero no son sólo tests viejos: el Consumer real ResGroups.full_name reproduce RecursionError sin SQL porque compute retorna y el descriptor requiere asignación. Es divergencia de contrato asociada0415/0417 pese a completed, no siete defectos nuevos ni reparación arbitraria bajo0559. El xfail sorted ejecutado con --runxfail falla por acceso DB no habilitado;0402 ya instala la terna, no se reimplementa.

CI39640828879/head99f: FAILURE,10656errores (10627 res_users ausente,29 transacción abortada),26skipped/1xfail. H-API-1120 conserva la deuda compartida. Cuerpos bloqueados no aceptados ni10656defectos independientes. Log íntegro ci-39640828879.log.gz; SHA256 crudo48f2d27d2e8f5c5a84316d49cd2630b4f9a6859ebfa5f78f4afb9e5b063222a9. No nueva suite global sin cambio material de setup. Sphinx NOT_EVALUATED.

## Procedencia y mecanismos existentes

Referencia Odoo19Community abe4040ec1a45beee90fb694e4eae4453e46b389, sin cambio a main. Consumer99f4a0445c163b8a5228e3df68121ce27905559b más diff explícito del lote. Provider9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f.

Interfaces realmente utilizadas: agents.agent_store.resolve_store_dir(create=False)/connect_readonly, task.task_ids.mapping_from_store/lookup, session.claim_fold.active_claims, session.job_runs.jobs_dir/scaffold_run/settle, workbench.manifest.declare_workbench/checkWorkbench y CLI claimsCommand. Invocación principal THYROX_ROOT=<Provider> uv run --frozen python probes/evidence_review.py; resultado60identidades/73fuentes/store sin cambios. Comandos y resultados remotos están en github-history.json; ledger conserva claim/release nativos. Contratos y firmas de selección/implementation_order/continuation_frontier ya examinados en el lote anterior a la misma revisión se reutilizan; no se repiten ni se sustituye el selector por estos instrumentos Consumer.

TASK1072 conserva claim ajeno; task_source pierde blockedBy/descripción. El grafo así obtenido no está cualificado para admisión. Runtime local Thyrox/Podman y ciclo TASK→modelo local→verificación→integración siguen no cualificados. Este trabajo es ingeniería autorizada de Codex, no inferencia local del Provider. Sin segundo store, coordinador, ejecutor o planner.

## Continuación delimitada

Primero revisar/aceptar el delta0559 publicado y sus regresiones; no merge en este lote. Reconciliar0415/0417 con consumidores que retornan valores y contrato de asignación antes de otra implementación. Preparar fixtures existentes para dos pruebas de collection sin permisos amplios. Recuperar autoridad original para ocho ordinales. El resto tiene condición individual de entrada en las tablas; NULL owner y ausencia de aristas no declaran elegibilidad. La auditoría global permanece abierta.

Las pruebas PG usan rol efímero CONNECT/TEMP y regla SCRAM limitada, con cleanup finally. No .env, tablas productivas, migraciones o TaskStore escritos. Pruebas previas0419/0420 se reutilizan por contrato y ausencia de cambios en sus mecanismos; no se declaran nuevamente ejecutadas. SHA256SUMS conserva integridad de outputs. El manifiesto cierra con exit1 agregado por fallos/bloqueos explícitos, no un PASS global.

## Consulta res_users

outputs/res-users-bootstrap-comparison.json conserva cuerpos/rangos/hashes de la revisión Odoo, migración Consumer y orden Django, más stack real CI. Odoo base precede test_orm y difiere FK hasta crear tablas. Django sincroniza apps sin migraciones antes de aplicar migraciones: test_orm no tiene migrations, base sí. La falla ocurre en sync_apps, antes de crear res_users. Investigación de H-API-1120, no corrección manual ni nueva TASK.
