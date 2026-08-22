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

## Dónde aplica — gobierna la FORMA del valor, no quién lleva la clave

Cuando un documento declara uno de estos campos, su valor se obtiene con
`date -u` y nunca a mano:

- `:fecha_creacion:` — en todo archivo RST nuevo
- `:fecha_actualizacion:` — al actualizar un artefacto **que ya la declare**
- Entradas de bitácora en el SMD y en archivos de progreso
- Cualquier campo de fecha en documentos gestionados

**Qué documento lleva `:fecha_actualizacion:` lo decide otra regla, no ésta.**
`.claude/CLAUDE.md` («Reglas de edición», punto 3) exime a los artefactos de
iniciativa —alcance, análisis, hallazgos, tareas, progreso— por una razón que
conviene tener presente: son **evidencia fechada de un episodio**, no
documentos vivos. Su cambio de estado se ancla al `repo@hash` del commit que
lo produjo, que ya trae fecha propia y no depende de que nadie se acuerde de
actualizar un campo.

> **Corregido 2026-08-22T05:03:49 (#746).** Esta línea decía *«al actualizar
> **cualquier** artefacto»*, que contradice literalmente esa exención. Las dos
> reglas se cargan en **toda** sesión, así que una podía citarse contra la
> otra y ambas lecturas parecían cumplir.
>
> El árbol sigue a `CLAUDE.md`, no a la línea vieja: medido sobre `source/`,
> **5 de 616** hallazgos declaran la clave (0.8 %), **349 de 2444** artefactos
> de iniciativa y **664 de 4370** archivos en total. La conducta correcta ya
> se ejercía; lo que estaba mal era una de las dos redacciones.
>
> Lo destapó una pregunta del ejecutor —*«¿por qué los documentos no tienen
> fecha_actualizacion?»*— no una relectura de la regla. Es la misma clase que
> H-DOCS-148 y H-DOCS-157: dos referentes siempre-cargados que no coinciden.
>
> *Métrica:* archivos con `^ *:fecha_actualizacion:` bajo `source/`.
> *Ciega a:* un documento que feche su actualización en prosa en vez de en el
> bloque `.. meta::`, y a la distinción entre «no la lleva por la exención» y
> «no la lleva por descuido».

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
