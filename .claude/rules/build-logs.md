```yml
type: Convención de Proyecto
category: Build Artifacts y Trazabilidad
version: 1.0.0
created_at: 2026-05-05 16:10:00
updated_at: 2026-05-05 16:10:00
applies_to: e-comerce v1.0.0+
```

# Build Logs — Persistencia obligatoria en WP activo

> Cargado automáticamente. Aplica a TODA ejecución de `make html`,
> `make clean`, `sphinx-build`, `validate-plantuml.sh`, y cualquier
> comando de build/validación que produzca diagnóstico.

> **Adaptacion e-comerce (2026-05-19):** En el template original los logs
> se persistian en `.thyrox/context/work/<WP>/<stage>/build-logs/`.
> En e-comerce `.thyrox/` no existe y `source/` solo acepta archivos
> `.rst`, por lo que los `.log` NO pueden vivir en la iniciativa
> (`docs/source/gestion/pm/<submodulo>/iniciativas/<slug>/`).
>
> Politica en e-comerce: los build-logs se guardan **fuera de
> `source/`**, en `docs/build-logs/<slug>/<descripcion>-<ISO>.log`
> (carpeta git-ignored). Las conclusiones del log se citan dentro de
> `progreso-<slug>.rst` con un extracto verbatim del warning/error
> relevante y la afirmacion calibrada que se desprende. Asi el RST
> sigue siendo reproducible y el `.log` queda en filesystem para
> diagnostico inmediato.

## Regla principal

**Los logs de build NUNCA viven en `/tmp` o stdout efímero.**

Cada ejecución de un comando de build debe redirigirse a un archivo
dentro del WP activo:

```
.thyrox/context/work/{wp-activo}/{stage-dir}/build-logs/{descripcion}-{timestamp}.log
```

## Por qué

Los build logs son **evidencia diagnóstica**:

- Reproducen exactamente qué warning/error rompió el strict build.
- Anclan el estado del repo a un commit/branch específico.
- Permiten comparar runs (antes vs después de un fix).
- Sirven como soporte de claims OBSERVABLE en artefactos del WP.

Si el log se pierde en stdout o `/tmp`, el claim "el build pasó" o
"falló por X" pierde su observable de origen y se degrada a SPECULATIVE
(ver `evidence-classification.md`).

## Estructura

```
.thyrox/context/work/{wp}/
├── discover/
│   └── build-logs/
│       ├── sphinx-strict-{contexto}-{ISO}.log
│       ├── make-clean-{ISO}.log
│       └── validate-plantuml-{ISO}.log
├── analyze/
│   └── build-logs/    ← logs de fase ANALYZE
└── track/
    └── build-logs/    ← logs finales de cierre
```

**Stage directory:** el del stage activo del WP. Si el log diagnóstica
algo cross-stage (ej: investigar fallo de CI antes de mergear), va al
stage activo (donde se está trabajando).

**Naming — formato ISO 8601 obligatorio:**
`{comando}-{contexto}-{ISO}.log` donde:

- `{comando}`: `sphinx-strict`, `make-clean`, `validate-plantuml`,
  `prerender-plantuml`, etc.
- `{contexto}`: branch, PR, o tema (`pr14`, `cnst-033`, `pre-merge`).
  Opcional cuando no aplica.
- `{ISO}`: timestamp ISO 8601 con `:` reemplazado por `-` para
  compatibilidad de filesystem: `YYYY-MM-DDTHH-MM-SS`.

Generación canónica del timestamp:

```bash
ISO=$(date -u +%Y-%m-%dT%H-%M-%S)   # UTC, recomendado
ISO=$(date    +%Y-%m-%dT%H-%M-%S)   # local, aceptable si consistente
```

**NUNCA** usar formatos no-ISO como `HH-MM`, `YYYYMMDD-HHMMSS`,
`MM-DD-HH-MM` u otros — pierden información de fecha completa
y rompen ordenamiento alfabético cronológico.

Ejemplos:

```
sphinx-strict-pr14-2026-05-05T16-15-23.log
make-clean-cnst-033-2026-05-05T15-45-08.log
validate-plantuml-post-rename-2026-05-05T09-30-12.log
sphinx-strict-2026-05-05T17-30-45.log         (sin contexto)
```

## Patrón de invocación

```bash
# CORRECTO — ISO 8601 + WP path + redirección 2>&1
WP=.thyrox/context/work/{wp-activo}
ISO=$(date -u +%Y-%m-%dT%H-%M-%S)
LOG="$WP/{stage-dir}/build-logs/sphinx-strict-{contexto}-${ISO}.log"
mkdir -p "$(dirname "$LOG")"
sphinx-build -W -j auto -b html -d build/doctrees source build/html \
    >"$LOG" 2>&1
echo "EXIT=$?" >> "$LOG"

# INCORRECTO — log efímero
sphinx-build -W ... 2>&1 | tail -50            # ❌ se pierde
sphinx-build -W ... > /tmp/sphinx.log 2>&1     # ❌ no traza al WP

# INCORRECTO — formato de tiempo no-ISO
LOG=...sphinx-strict-16-15.log                  # ❌ sin fecha
LOG=...sphinx-strict-20260505-161523.log        # ❌ no separa fecha/hora
```

## Excepción

Builds de exploración rápida (< 30 segundos) que no producen warnings
ni errores nuevos pueden ir a stdout sin persistencia. Si producen
diagnóstico (warnings, errors, cambios en behavior), persistirlos.

Regla práctica: **si vas a citar el output en un artefacto del WP,
el log tiene que existir como archivo.**

## Trazabilidad

Cualquier afirmación del tipo "el build da N warnings" o "el strict
build falla" en un artefacto del WP debe referenciar el archivo de log:

```markdown
## Diagnóstico

El strict build con `-W` falla con 14 warnings de ref. cruzada rota.
Ver: `discover/build-logs/sphinx-strict-pr14-16-10.log` (líneas 1234-1300).
```

## Anti-patrones prohibidos

```bash
# PROHIBIDO: ejecutar sin redirección
make html

# PROHIBIDO: redirigir a /tmp
sphinx-build ... > /tmp/log.txt 2>&1

# PROHIBIDO: usar log de WP previo
echo "..." >> .thyrox/context/work/{wp-anterior}/track/build-logs/...

# CORRECTO: log en WP activo, stage activo, naming descriptivo
sphinx-build ... > .thyrox/context/work/{wp}/discover/build-logs/sphinx-strict-pr14-$(date +%H-%M).log 2>&1
```

## Relación con otras reglas

- **calibration-verified-numbers.md**: los warnings count se obtienen
  de `wc -l` del log, no se inventan.
- **metadata-standards.md**: artefactos que citan logs deben usar
  el path relativo `{stage}/build-logs/...` desde la raíz del WP.
- **changelog-policy.md**: cambios que rompen/arreglan el build se
  registran en `track/{wp}-changelog.md` con ref al log.
