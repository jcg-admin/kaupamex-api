# Convenciones de commit — Tim Pope style

## Regla no negociable

Todo commit en este repositorio sigue el estilo Tim Pope **sin excepción**.
No usar Conventional Commits (`fix:`, `feat:`, `chore:` …) — ese formato
está explícitamente descartado en este proyecto.

## Autor obligatorio

Cada commit debe tener este autor, sin importar qué usuario tenga configurado
el sistema:

```bash
GIT_AUTHOR_NAME="Nestor Monroy"
GIT_AUTHOR_EMAIL="46802445+NestorMonroy@users.noreply.github.com"
GIT_COMMITTER_NAME="jcg-admin"
GIT_COMMITTER_EMAIL="169318663+jcg-admin@users.noreply.github.com"
```

Pasar las cuatro variables antes de cada `git commit`:

```bash
GIT_AUTHOR_NAME="Nestor Monroy" \
GIT_AUTHOR_EMAIL="46802445+NestorMonroy@users.noreply.github.com" \
GIT_COMMITTER_NAME="jcg-admin" \
GIT_COMMITTER_EMAIL="169318663+jcg-admin@users.noreply.github.com" \
git commit -m "..."
```

## Las 7 reglas Tim Pope

| # | Regla | Correcto | Incorrecto |
|---|-------|----------|------------|
| 1 | Línea en blanco entre asunto y cuerpo | `Asunto\n\nCuerpo` | `Asunto\nCuerpo` |
| 2 | Asunto ≤ 50 caracteres | `Fix login race condition` | `fix(auth): solve the race condition in login flow` |
| 3 | Asunto capitalizado | `Add OAuth support` | `add OAuth support` |
| 4 | Asunto sin punto final | `Fix typo` | `Fix typo.` |
| 5 | Imperativo en asunto | `Fix bug` | `Fixed bug` / `Fixes bug` |
| 6 | Cuerpo con líneas ≤ 72 caracteres | (envolver manualmente) | líneas largas sin corte |
| 7 | Cuerpo explica QUÉ y POR QUÉ, no CÓMO | problema + solución | descripción del diff |

## Plantilla

```
Resumen imperativo de 50 chars o menos

Párrafo explicando el contexto del problema. Por qué existía
el bug o por qué era necesario el cambio. Máximo 72 chars
por línea.

Segundo párrafo si hace falta: consecuencias, alternativas
descartadas, referencias a issues o ADRs relacionados.

Closes #123
```

## Ejemplo canónico

```
Upgrade Pillow to fix Python 3.13 build failure

pillow==10.2.0 predates Python 3.13 and raises KeyError:
'__version__' during compilation. uv resolves 3.13.14 as the
newest version within the declared >=3.11,<3.14 range, so
production installs with uv sync --no-dev fail on Ubuntu 26.04.

Raise the constraint to >=10.3.0, the first release with 3.13
support. uv lock resolves v12.2.0 (current stable).
```

## Gate de verificación

Antes de dar por válido un commit, verificar:

```bash
git log -1 --format="%an <%ae>%n%n%B"
```

- Primera línea: `Nestor Monroy <46802445+NestorMonroy@users.noreply.github.com>`
- Asunto: ≤50 chars, capitalizado, imperativo, sin punto
- Cuerpo separado por línea en blanco, líneas ≤72 chars
