# Comprobación de cumplimiento y cierre de brechas

Resultado: había dos brechas locales demostradas; se corrigieron en f5bb655c y0fc622dc. La aceptación/integración remota sigue pendiente de CI y revisión. Este lote no reinicia el análisis ni declara todoORM completo.

## Contraste con el mandato

| Requisitos del adjunto | Estado y evidencia |
|---|---|
|1–4 recuperación y reutilización |API5f0f759e,Docs b59763156,Provider9b13f2 fijados al inicio. Native identities/claims, Git y artefactos existentes recuperados; no78consultas repetidas ni inventario nuevo.|
|5–10 bootstrap |La migración d2001199 y controles PG/legacy permanecen válidos. El error posterior de teardown se reprodujo por separado y se corrigió en el fixture0416, sin crear res_users o actor manualmente.41pytestPASS incluidos teardown; composición final47PASS con teardown en native-pytest-final.log. CI observada por separado.|
|11–16 compute |La asignación/diagnóstico ya estaban corregidos. Faltaba el caso pkNone entre contextos: NewId privado en caché existente lo corrige con pruebas de instancia, contextos, valores explícitos/constructor, invalidación, segunda lectura, protección y excepciones.131PASS; controles negativos2/1fallos; replay original0SQL.|
|17–18 preservar0559 |Cuerposrecompute/_recompute_field intactos;16PGPASS por cambio material de lectura.0419/0420 y migración sin cambios; no reimplementación/admisión repetida.|
|19–23 AS IS y continuidad |Se actualizan sólo0415/0416/0417/0559 y grupos relacionados.0579 y0379 permanecen identidades existentes con alcance propio, sin nuevas TASK ni estados. Corrección independiente del verificador0416 avanzó mientras compute/CI continuaban.|
|24–26 código y compatibilidad |Identificadores nuevos en inglés; primitivos existentes NewId/cache/connection.close. PK/DB/schema/Provider sin cambios. No nuevo registry/cache/planner/store/runner. Hooks normales obligatorios.|
|27–29 metodología |No se bloquea por BABOK ni se reclama cualificación/inferencia local. La comparación red/green/negative aporta control concreto, sin framework metodológico.|
|30–33 evidencia y Git |Native job_runs/workbench/claims/readonly identities utilizados con revisión/interfaz/resultado. Artefactos/SHA y flujo feature→PR existentes; sin merge o cambio de protecciones.|
|34–43 aceptación |Resultados locales y pendientes remotos separados. No se infiere aceptación de completed, nombre, código presente o PR abierto. CI previa siguein_progress al observar, logs404; sin diagnóstico inventado. Publicación y heads se verifican al cierre.|

## Corrección del fixture

El control fixture_boundary.py retiene un Environment sin actor sobre PostgreSQL. La frontera anterior falla base.public_user/autocommit; cerrar conexión antes de DDL pasa. f5bb655c comprueba que field_dirty/tocompute/field_data_patches estén vacíos antes de cerrar. No descarta trabajo válido, no siembra usuario ni cambia Transaction.flush/seguridad. La prueba nativa de la corrección aislada termina41PASS en438.89s, incluido teardown. Es una corrección Consumer ligada0416, cuyo estado completed se conserva.0379 sigue siendo la obligación de actor público, no un prerrequisito necesario para este cierre de fixture.

## Corrección contextual sin pk

La hipótesis anterior de que este caso exigía implementar todoBaseModel.new era demasiado amplia.0fc622dc usa NewId ya portado sólo como clave privada del caché de campos contextuales sin columna. El valor sigue en los buckets existentes; no se cachea bajo None, no cambia pk y dos instancias no comparten identidad. Los kwargs explícitos se insertan cuando el registro está listo; los valores anteriores no esconden una falta de asignación después de invalidar. Se conserva protección recursiva usando la identidad pública original del flujo de cómputo.

131PASS focalizados y214PASS estructurales/1XFAIL heredado. Deshabilitar la clave falla dos tests; compartirla falla otro. Replay exacto del caso anterior:Admin/Operations→Operations→Admin/Operations,0SQL,pkNone. La prueba de segunda lectura ahora conserva los decoradores al mockear compute, para no ocultar depends_context. Contrato de14elementos, fuente NewId fijada abe4040 y logs completos en outputs.

Límites: no se implementó BaseModel.new completo, origin, recordsets o toda invalidación/persistencia virtual; tampoco se cualificó seguridad sudo de todos los Consumers. GEN0579 conserva su alcance y estado pendiente. La adaptación no convierte este caso acotado en aceptación del constructor virtual completo.

## Ejecución y reanudación

El verificador conjunto final vuelve a usar una base propia nueva, porque cambiaron materialmente fixture y lectura de caché; no se repiten experimentos sin causa ni se recrea QA compartida. native-pytest-final.log termina47PASS en440.48s, incluido teardown, con el código final conjunto. Es independiente de los41PASS aislados y131PASS de unidad; los recuentos se solapan y no se suman como cobertura global. Fallos históricos/controles permanecen como fallos, nunca se presentan como PASS.

Desde raíz Git API, declarar ORM_QA_CONTAINER, ORM_QA_HOST y ORM_QA_BRIDGE del entorno verificado y usar uv frozen. La fixture existente scripts/evidence/orm-bootstrap-compute-20261021T210528/probes/qa_context.py proporciona settings y recurso PostgreSQL exclusivo y elimina su base/rol/reglaSCRAM al finalizar. Puede ejecutar los probes de este lote o pytest. No depende de /workspace, un transcript, .env o scripts temporales del ejecutor.

admission-and-interfaces.json registra revisión Provider9b13f2, nueve interfaces reales y cinco identidades verificadas con mapping_from_store/lookup; claims en ledgers Consumer, state hash comprobado. No selección automatizada ni ejecución local Thyrox cualificada;1072 y demás bloqueos Provider se conservan, no se sustituyen con scripts Consumer.

CI39679481359/head5f0f759e seguía en ejecución tras más de dos horas al revisar. El endpoint de log devuelve404, observación guardada; eso no demuestra causa ni éxito. No se cancela ni se inventa resultado. El nuevo head se publica mediante PR109 y Docs154 y se verifica su check; sin merge. Esperar su resultado/revisión antes de integración. Los ocho ordinales históricos ambiguos siguen sin inventar identidad.
