# Timestamps ISO 8601 Obligatorios

Creado: 2026-05-29T03:02:51

## Regla

NUNCA escribir un timestamp manualmente. SIEMPRE obtenerlo con:

```bash
date -u +"%Y-%m-%dT%H:%M:%S"
```

## Cuándo ejecutar el comando

El comando `date -u` debe ejecutarse **en el mismo turno** en que se
va a usar el valor. No reutilizar un valor obtenido en un paso anterior
del mismo turno — el tiempo transcurrido entre pasos puede ser significativo.

Flujo correcto:

1. Bash: `date -u +"%Y-%m-%dT%H:%M:%S"` → obtiene `2026-05-29T14:33:07`
2. Write/Edit: usa `2026-05-29T14:33:07` en el campo correspondiente

## Campos afectados

- `:fecha_creacion:` — en todo archivo RST nuevo
- `:fecha_actualizacion:` — al actualizar cualquier artefacto
- Entradas de bitácora en el SMD y en archivos de progreso
- Cualquier campo de fecha en documentos gestionados

## Señal de fabricación

Cualquier timestamp con alguno de estos patrones es sospechoso:

- `THH:00:00` — hora redonda, minutos y segundos en cero
- `THH:MM:00` — segundos en cero (menos probable pero posible)
- Múltiples archivos distintos con exactamente el mismo timestamp

Si se detecta uno de estos en código propio o de un agente, reportarlo
como hallazgo y corregirlo con `date -u` en ese momento.

## Contextos de alto riesgo

El patrón de fabricación aparece más en estos contextos:

- Escritura en paralelo con subagentes (el agente "adivina" la hora)
- Actualización del SMD al final de un turno largo
- Creación de archivos RST nuevos en lote

En estos contextos: ejecutar `date -u` explícitamente antes de escribir
cada archivo o sección que requiera timestamp.
