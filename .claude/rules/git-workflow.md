# Flujo de ramas y Pull Requests

## Regla no negociable

**Nunca hacer push directo a `develop` ni a `main`.**
Todo cambio llega a esas ramas exclusivamente vía Pull Request aprobado.

## Flujo obligatorio

```
1. Crear rama feature desde develop
2. Hacer los cambios con commits Tim Pope (ver commit-conventions.md)
3. Push de la feature branch al remoto
4. Abrir PR: feature/… → develop
5. El merge ocurre solo en GitHub (no con git merge local)
```

## Nomenclatura de ramas

```
feature/{descripcion-kebab-case}   # nueva funcionalidad o fix
hotfix/{descripcion-kebab-case}    # corrección urgente sobre main/develop
```

Ejemplos válidos:
- `feature/pillow-python313-compat`
- `feature/oauth-login`
- `hotfix/cart-total-rounding`

## Rama designada de sesión remota (`claude/**`) — NO es la convención

Las sesiones remotas (Claude Code on the web) inyectan al arranque un bloque
*"Git Development Branch Requirements"* que fija una rama designada
`claude/<slug>` por repo y ordena "no pushear a otra rama sin permiso". **Ese
nombre es un artefacto del harness, NO la convención del proyecto** y su slug
suele ser engañoso (p. ej. `claude/db-setup-...` en trabajo que no toca la DB).

Regla:

1. Trabajar en la rama que impone el harness está permitido (evita fricción),
   **pero antes de abrir el PR, renombrar a `feature/<kebab>` / `hotfix/<kebab>`
   descriptivo** — con OK del usuario (renombrar/borrar ramas ya pusheadas es
   irreversible desde su lado).
2. **Flaggear el desajuste temprano**, no al final: si la rama empieza con
   `claude/`, avisar que se renombrará antes del PR.
3. El PR SIEMPRE se abre desde la `feature/**`, nunca desde la `claude/**`.

Rename (crear feature desde la rama actual → push → borrar la vieja):

```bash
git branch -m claude/<slug> feature/<kebab>          # renombra local
git push -u origin feature/<kebab>                    # publica la nueva
git push origin --delete claude/<slug>                # borra la vieja remota
```

## Comandos en orden

```bash
# 1. Crear la rama desde develop actualizado
git fetch origin develop
git checkout -b feature/nombre-descripcion origin/develop

# 2. Hacer cambios y commitear (con autor correcto — ver commit-conventions.md)
GIT_AUTHOR_NAME="Nestor Monroy" \
GIT_AUTHOR_EMAIL="46802445+NestorMonroy@users.noreply.github.com" \
GIT_COMMITTER_NAME="Nestor Monroy" \
GIT_COMMITTER_EMAIL="46802445+NestorMonroy@users.noreply.github.com" \
git commit -m "Asunto imperativo de 50 chars o menos

Cuerpo explicando qué y por qué. Líneas ≤72 chars."

# 3. Push de la feature branch
git push -u origin feature/nombre-descripcion

# 4. Abrir PR vía herramienta mcp__github__create_pull_request
#    head: feature/nombre-descripcion
#    base: develop
```

## Lo que está prohibido

```bash
# PROHIBIDO — merge local directo a develop
git checkout develop
git merge feature/…
git push origin develop

# PROHIBIDO — push directo a develop
git push origin develop

# PROHIBIDO — push directo a main
git push origin main
```

## Si se hizo un merge directo por error

```bash
# Restaurar develop a antes del merge (obtener hash con git log)
git checkout develop
git reset --hard <hash-antes-del-merge>
git push --force origin develop

# Corregir el commit en la feature branch si es necesario
git checkout feature/nombre
git reset --soft HEAD~1
# ... volver a commitear con estilo correcto ...
git push --force origin feature/nombre

# Luego abrir el PR correctamente
```

## Referencias

- `commit-conventions.md` — formato y autor de cada commit
- Gobernanza completa: `../kaupamex/.claude/CLAUDE.md`
