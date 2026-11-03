# Continuidad de auditoría: contratos, taxonomías y evidencia

Análisis directo de Codex, sin inferencia local Thyrox. No se seleccionó una TASK
funcional ni se implementó/migró una taxonomía. No se modificó código productivo.
La autoridad documental es el análisis BaseModel EXISTENTE de Docs, ampliado en
esta revisión; el expediente existente conserva el resumen de continuidad.

## Revisiones y procedencia

API 4538cee5c81763fae0dfa0444f96c2a4fa19acd0, Docs
946156ceb812fe7d291f2c7366b3af8c4bded4db, Provider
9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f. Referencia funcional Odoo Community 19,
odoo-tools@abe4040ec1, extracción parcial de 32 archivos reutilizada. No se
repite el inventario de 86.008 archivos; no es un denominador funcional.

## Resultados nuevos

- Contraste de dos clasificadores existentes: con installed presente y primitive
  ausente, campos=BLOCKED y signaling=READY. Un atributo None también difiere.
  Ambos pueden dar READY a una función que falla al llamarla; el control la
  ejecuta y exige NotImplementedError. Las listas vacías clasificadas BUILDABLE
  son un caso sintético, no una afirmación sobre filas actuales del catálogo.
- INVENTORY no idéntico: 13 pares frente a 14; acentos y una fila adicional.
  No se normalizaron claves ni se hizo de ese inventario una autoridad nueva.
- Gate existente: basename alternativo y archivos en vez de directorios aceptados;
  JSONL histórico oculta JSON declarativo. Son contrastes sobre fixtures, no
  nuevos fallos introducidos en los documentos históricos.
- 60 pruebas existentes Provider PASS: esquema/vocabulario de TASK y manifiestos.
  No cualifican ejecución de modelos locales ni aceptación de contratos ORM.
- TASK_STATUSES tiene sólo pending/in_progress/completed; deleted es orden.
  Los trece diagnósticos del adjunto son prosa, no estados oficiales de TASK.
- PR snapshot: seis abiertos, sin aprobación registrada; #110 borrador. API #109
  falló con res_users ausente durante django_db_setup/sync_apps, H-API-1120.
- PostgreSQL observado vivo, dos bases public vacías, propietario django_user,
  permisos y extensiones presentes. Sin otros clientes al observar pg_stat_activity.
  Es infraestructura Codex/Docker, no un recurso de ejecución Thyrox/Podman.
  Sus tres logs anteriores de preparación se preservan como evidencia histórica.

La matriz conceptual y los requisitos para una eventual migración están en
source/gestion/pm/api/iniciativas/completar-raiz-orm/analisis-contrato-de-basemodel-trae-o-construye.rst,
sin crear enums, interfaces ni campos. No es un plan ejecutable autorizado.

## Comandos y resultados

Desde API, UV_CACHE_DIR de la sesión y uv run --frozen:
- python <este run>/outputs/contrast_existing_classifiers.py: exit 0.
  Importa ambos instrumentos originales, sustituye resolutores sólo en memoria;
  no ejecuta main ni toca outputs históricos. Es diagnóstico Consumer puntual.
Desde Thyrox, Bun 1.4.0 y TMPDIR de esta auditoría:
- bun <este run>/outputs/contrast_workbench_gate.ts: exit 0 de las aserciones.
- bun test ./src/packages/task/__tests__/schema.test.ts
  ./src/packages/workbench/__tests__/manifest.test.ts: exit 0, 60 pass/0 fail.
- bin/agent_store buscar-tareas --id 1167 1168 1191 1193 1194 1196 1197 1199 1204
  --sesion 168b0fdf --limit 12: exit 0, nueve filas.
- bin/agent_store buscar-tareas --query taxonom --detalle --limit 8: exit 0;
  tres coincidencias contextuales, no autorización para crear una TASK.
Se utilizó mapping_from_store y SELECT con SQLite mode=ro para completar owner y
aristas por identidad. No hubo SQL de escritura. Los cuatro ordinales sucesores
históricos H-API-1086 no aparecen en su sesión 29a5e555 en la consulta focalizada;
no se confundieron con ordinales iguales de otra sesión.

Provider usado realmente: workbench.paths.workbench_dir y session.job_runs.jobs_dir
(núcleo read-only para resolver hogares); scaffold_run, declare_workbench, settle
para este run; claimsCommand para reservas administrativas y liberación; lectura
de identidades y consulta nativa de TASK. Interfaces y revisión constan arriba.
No se desarrolló un segundo coordinador, store, registro o clasificador productivo.

CI: gh run view 39346338432 --repo jcg-admin/kaupamex-api --job 118379726762
--log-failed. Descarga exit 0 NO significa CI PASS; conclusión FAILURE.
Registro completo comprimido y hash en outputs; 50.681.616 bytes originales.
Las aserciones del lote pasan; las brechas funcionales/arquitectónicas siguen
abiertas. Sphinx y persistencia ORM NOT_EVALUATED. No migraciones productivas.
