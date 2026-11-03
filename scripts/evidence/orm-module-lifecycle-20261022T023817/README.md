# Module lifecycle — continuidad contractual

Este expediente continúa `completar-raiz-orm`; no constituye aceptación global ni otro plan rector. Referencia Odoo fijada: `abe4040ec1a45beee90fb694e4eae4453e46b389`. Consumer funcional: `56b08be8`; Provider inspeccionado: `9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f`.

## Resultados comprobados

- `9971495d`, TASK-API-0174: detección de ciclos de dependencias con error de dominio y memo por recorrido. Baseline 5 FAIL / 3 PASS; control negativo 7 FAIL / 1 PASS. Odoo elimina módulos cíclicos tras capturar RecursionError; el adaptador Consumer rechaza la ordenación inválida, no reproduce literalmente ese algoritmo.
- `940e58c4`, TASK-API-0383: base/base_address_extended/base_geolocalize dejan el plano de control; alias de migración requiere roster registrado; relaciones respetan las bases de objetos vinculados. Baseline discriminante 7 FAIL / 2 PASS; 24 comprobaciones focalizadas PASS. Alcance parcial de la TASK.
- `56b08be8`, TASK-API-0382: auto_install=[]/() no equivale a False; candidatos installable=False excluidos. Baseline 3 FAIL / 9 PASS; conjunto focalizado definitivo 36 PASS. No acredita instalación por base.

Los resultados están en `outputs/*`; los scripts ejecutados están en `probes/`. Los registros de desarrollo fallidos se conservan como tales; `router-frozen-baseline-final.log` y `database-migrations-recovered.json` son las observaciones definitivas de esos experimentos.

## Dependencias y límites

El router y company_scope seleccionan conexiones; no componen clases por base. Dos bases propias conservaron conjuntos distintos de IrModule y lecturas concurrentes correctas, pero Registry.new copió el mismo universo global de clases en ambas. El catálogo derivado de INSTALLED_APPS no acredita instalación independiente.

MigrationExecutor verificó creación/upgrade/reversa de contenttypes en una base exclusiva. No acredita hooks ni desinstalación de addons. La migración contenttypes→auth pasó en default y falló en company por ausencia de django_content_type: DEC-AISL-05 no decide ubicación de esa infraestructura. No se modifica la decisión ni se declara completada TASK-API-0383. Los fixtures históricos con nombres fijos de base no se reactivaron por seguridad.

Se inspeccionaron 25 interfaces reales de Django/Gunicorn y versiones instaladas. Apps aislado retiene clases registradas al restaurarse; el experimento fork demuestra que cambios en memoria no se propagan al padre. No se cualifica recarga multiworker. No se ejecutó Odoo nativo ni inferencia local de Thyrox. Estados oficiales de las TASK conservados; las tres asignaciones de propietario se hicieron por TaskUpdate nativo y están exportadas en admission-*.json.

La suite completa anterior terminó 77 PASS, 1 SKIP, 1 ERROR en ProductProduct.display_name; el último lanzamiento, justificado por el cambio material de auto_install, conserva su resultado separado en ci-verify-final-with-auto.log. Un subconjunto PASS no sustituye CI ni autoriza integración.

## Conservación de instrumentos efímeros

`outputs/temporary-preservation.json` registra existencia, hashes, procesos visibles, descriptores abiertos, clasificación y copias. Se revisaron sólo ocho archivos conocidos de esta sesión; no se barrió el sistema. No se movió, eliminó ni reejecutó ninguno.

`/tmp/orm-module-admission.ts` existe: llama TaskGet/TaskUpdate/TaskGet para TASK-API-0174, comprueba propietario y bloqueos declarados, asigna sólo owner y guarda el resultado. No crea TASK, claims, un TaskStore ni un mecanismo de admisión completo; la elegibilidad requiere evidencia adicional registrada en admission-0174.json. Sus variantes 0382/0383 tienen igual responsabilidad. No se deben reproducir escrituras para comprobar preservación.

Cinco copias exactas no ejecutables quedaron en `probes/recovery/*.source.txt`: tres invocaciones históricas nativas, un adaptador de settings de importación sin acceso DB y una transformación AS IS del lote anterior. No son herramientas nuevas. Sus rutas absolutas son procedencia histórica; otra sesión debe resolver raíces Git y Provider antes de cualquier operación, sin reproducir admisiones automáticamente. Los mensajes temporales de commit son descartables: Git conserva su contenido. No se detectaron credenciales literales en los archivos revisados; los originales permanecen intactos. Visibilidad /proc limitada a procesos accesibles.

Las sondas contractuales ya residían en este expediente API. No se copia el almacén de Thyrox al Consumer. La persistencia local aún requiere publicación Git verificada; no confundir una copia dentro del workspace con respaldo remoto. La prueba activa no se interrumpió.

## Reproducción acotada

Resolver raíz con git rev-parse y referencia con scripts/reference_roots.py. Dependencias congeladas mediante uv; las sondas Django requieren settings válidos. Para PostgreSQL usar exclusivamente el qa_context.py existente en orm-bootstrap-compute-20261021T210528 y sus recursos propios; database_contract.py rechaza nombres sin prefijo orm_bootstrap_. No usar QA compartida ni ejecutar sondas de creación con el adaptador de importación recovery/orm_batch_env.py.

No repetir pruebas válidas sólo por conservación. Los hashes permiten comprobar copias sin efectuar escrituras de TASK ni nuevas migraciones. La aceptación requiere CI/revisión e integración autorizada, y los contratos de loader, estados, hooks, composición por base y señalización continúan pendientes.
