```yml
type: Regla de Proyecto
category: Documentacion de hallazgos durante implementacion
version: 1.0.0
created_at: 2026-05-28T22:46:19
updated_at: 2026-05-28T22:46:19
applies_to: e-comerce v1.0.0+
origen: directiva ejecutor 2026-05-28T22:46:19
```

# Hallazgos — Documentacion obligatoria antes del commit final

> Cargado automaticamente en cada sesion (I-009).
> Aplica a TODOS los agentes del loop y subagentes de implementacion.

## Regla principal

**Cada agente que encuentre hallazgos durante su implementacion
DEBE documentarlos en e-comerce-docs ANTES de hacer su commit final.**

Si un agente NO encontro hallazgos, NO crea el archivo. Solo cuando
hay algo que documentar.

## Ubicacion segun tipo de hallazgo

| Tipo de hallazgo | Ubicacion |
|---|---|
| Codigo API (bug, drift, gap) | `source/gestion/pm/api/audits/hallazgos-<slug>.rst` |
| Codigo UI (bug, drift, gap) | `source/gestion/pm/ui/audits/hallazgos-<slug>.rst` |
| Server (provisioners, scripts) | `source/gestion/pm/server/audits/hallazgos-<slug>.rst` |
| Docs (RST, estructura, naming) | `source/gestion/pm/docs/audits/hallazgos-<slug>.rst` |

**Slug:** usar el nombre de la iniciativa o tarea que produjo el hallazgo.
Ejemplos: `hallazgos-t709-migration.rst`, `hallazgos-uc-rev-02-cap6.rst`.

**Si ya existe el archivo del audit correspondiente:** agregar el hallazgo al final.
**Si no existe:** crearlo con Template B (ver abajo).

## Formato obligatorio por hallazgo

```rst
H-<TIPO>-<NN> — descripcion corta
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- **Severidad:** CRITICA / ALTA / MEDIA / BAJA
- **Archivo:** ``file.py:line``
- **Descripcion:** que estaba mal y por que
- **Estado:** RESUELTO en ``<repo>@<hash>``  |  DOCUMENTADO (sin fix inmediato)
```

Donde `<TIPO>` es: API, UI, SERVER, DB, DOCS.

## Template B (archivo nuevo)

```rst
.. meta::
   :fecha_creacion: <date -u +"%Y-%m-%dT%H:%M:%S">
   :autor: claude
   :estado: completado
   :submodulo: api|ui|server|db|docs
   :iniciativa: <slug-de-la-tarea>

Hallazgos — <Descripcion de la tarea>
======================================

:Fecha: <date -u +"%Y-%m-%dT%H:%M:%S">
:Rama: claude/great-fermat-N01N4
:Commits: <repo>@<hash>
:Total hallazgos: N

--------

H-<TIPO>-01 — descripcion corta
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- **Severidad:** ALTA
- **Archivo:** ``apps/modulo/archivo.py:42``
- **Descripcion:** descripcion clara de que estaba mal y por que
- **Estado:** RESUELTO en ``api@abc1234``
```

## Secuencia de commits obligatoria

Cuando hay hallazgos, el agente debe hacer DOS commits separados:

1. Commit en `<repo>` (api/ui/server): la implementacion + fixes
2. Commit en `e-comerce-docs`: el archivo de hallazgos
3. Push de ambos

Si no hay hallazgos, no hay segundo commit de docs.

## Timestamp

Todos los timestamps en metadata deben generarse con:

```bash
date -u +"%Y-%m-%dT%H:%M:%S"
```

**NUNCA** escribir segundos como `:00` manualmente — siempre usar el
valor real del comando.

## Aplicacion

- Aplica a todos los agentes del loop autonomo de bug sweep.
- Aplica a todos los agentes de implementacion de features.
- Aplica a los agentes de correcciones de hallazgos.
- El orquestador principal tambien documenta hallazgos retroactivos
  de agentes completados que encontraron algo pero no documentaron
  (porque la regla no existia antes).

## Severidad de esta regla

**ALTA** — Un hallazgo no documentado:
- Desaparece del historial cuando el agente termina.
- Impide que el ejecutor audite el trabajo del agente.
- Rompe la trazabilidad de la deuda tecnica.
- Puede llevar a que el mismo bug sea redescubierto en ciclos futuros.
