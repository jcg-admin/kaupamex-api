# Consolidación contractual y transición a planificación

Autoridad: Docs completar-raiz-orm/tareas-completar-raiz-orm.rst.
15 obligaciones, 14 elementos y seis unidades candidatas. No nuevas TASK,
plan ejecutable, migración, inferencia, implementación ni aceptación funcional.
Reutiliza resultados previos; no se repitieron pruebas ORM ni censos.

## Evidencia

outputs conserva procedencia, lecturas readonly, interfaces reales y resultados
de PR/CI. El artefacto population es analítico, no otro TaskStore o scheduler.
La arista histórica 0417→0418 se corrige a condicional conforme al progreso.
El código cero del manifiesto representa validación de la consolidación,
no aceptación de ninguna unidad ORM.

## Registro CI

Registro completo comprimido: outputs/ci-api-5183ac7b-full.log.gz.
El original de 43,736,070 bytes tiene SHA256
f2967b8dc3e225e6663dd6d8e03c0c28033f1f3f858d9f9008c8a65f27db2437.
BASELINE_FAILURE en setup; no NEW_REGRESSION funcional demostrada por este lote.
Sphinx: NOT_EVALUATED.

## Validación de publicación

Los 19 hashes pasan desde outputs. La primera invocación desde la raíz API
falló por directorio de trabajo (exit1); la repetición en outputs terminó exit0.
El gate workbench pasó tras corregir a ruta relativa la referencia al instrumento.
Git fsck connectivity-only: exit0 en API y Docs; árboles dangling heredados
se preservan. diff --check detectó línea vacía final nueva y se corrigió.
