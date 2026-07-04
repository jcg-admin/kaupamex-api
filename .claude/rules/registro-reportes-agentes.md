# Registro obligatorio de reportes y análisis de agentes

## Alcance

Aplica a todo agente y subagente que produzca un output analítico:
inventario, auditoría, síntesis, comparación, deep-review, o cualquier
reporte que no sea un hallazgo de bug/drift/gap (esos van a
`hallazgos-<slug>.rst` según la regla existente).

## Principio: el productor persiste, no el padre

El subagente escribe su reporte completo antes de devolver su resumen.
El padre solo ve el resumen —el análisis completo se pierde si no lo
persiste el propio productor.

## Ubicación

| Tipo de análisis | Destino |
|---|---|
| Específico de un submódulo | `<submodulo>/audits/reporte-<slug>-<YYYY-MM-DD>.rst` |
| Cross-cutting / supramodular | `docs/audits/reporte-<slug>-<YYYY-MM-DD>.rst` |
| Lección retrospectiva | `docs/lecciones-aprendidas/<slug>-<YYYY-MM-DD>.rst` |

`<slug>` describe el tema en kebab-case (ej. `inventario-submodulos`,
`analisis-openapi-drift`, `revision-schema-db`).

## Cabecera de procedencia obligatoria

Todo archivo `reporte-*.rst` debe abrir con el bloque:

```rst
.. reporte::
   :agente: <tipo-agente>
   :tarea: <descripcion-una-linea>
   :fecha: <YYYY-MM-DD>
   :herramientas: <lista-de-herramientas-usadas>
   :basado-en: <sha-o-rama-o-url-de-fuentes>
```

## Triggeres (default-ON)

El reporte se crea **siempre** que el agente complete un análisis, sin
importar si encontró problemas o no. Un análisis limpio también es
información de estado.

No crear archivo solo si el agente fue interrumpido antes de completar
su análisis (estado parcial no vale como reporte).

## Verificación antes de declarar hecho

Antes de devolver el resumen al padre, el subagente verifica que el
archivo aterrizó (react-verification-gate punto 5):

```
git ls-files --error-unmatch <ruta-del-reporte>
```

Si el archivo no existe, el agente reintenta la escritura una vez. Si
falla de nuevo, eleva el error —no declara completado.

## Relación con otras reglas

- `hallazgos-documentacion-obligatoria.md`: complementaria. Hallazgos
  van a `hallazgos-<slug>.rst`. Reportes van a `reporte-<slug>.rst`.
  Un mismo análisis puede generar ambos archivos.
- `react-verification-gate.md`: la verificación de aterrizaje del
  archivo es una `learning action` (punto 5 de esa regla).
- `calibration-verified-numbers.md`: toda cifra en un reporte debe
  citarse desde la salida de herramienta que la produjo.
