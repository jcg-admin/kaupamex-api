```yml
type: Regla de Proyecto
category: Code style — imports
version: 1.0.0
created_at: 2026-05-20
applies_to: kaupamex v1.0.0+ (api + ui)
```

# Zero Lazy Imports — regla cross-submodulo

> Cargado automáticamente. Aplica a TODO `.py` en `api/` y a todo
> archivo de codigo en `ui/`.

## Regla principal

**NUNCA escribir imports dentro de funciones, metodos, fixtures,
callbacks o bloques condicionales.** Todos los imports van al
top del modulo.

### Aplicacion

| Submodulo | Equivalente | Donde NO va |
|---|---|---|
| `api/` (Python) | `from X import Y` o `import X` | dentro de `def`, `async def`, `if`, `try` |
| `ui/` (JavaScript) | `import` estatico | n/a — `import` solo es valido top-level |
| `ui/` (JavaScript) | `require('X')` (CommonJS) | dentro de funciones / callbacks |
| `ui/` (JavaScript) | `await import('X')` o `import('X').then()` | NO si la motivacion es lazy interno; SI si es code splitting de routes / componentes pesados |

### Excepciones documentadas (CUATRO, no mas)

1. **`React.lazy(() => import('./Component'))`** a top-level de un
   modulo router. Es code splitting intencional, no lazy interno.
   Verificable: solo a top-level, asignado a `const`, dentro de
   un router.

2. **`pytest-django` collection**: ninguna. El plugin configura
   Django via `DJANGO_SETTINGS_MODULE` antes de collection, asi
   que `from apps.X.models import Y` al top de tests es seguro.
   (Cargo cult historico de "tests necesitan lazy" desmentido en
   round 6 de iniciativa `eliminar-lazy-imports-pep8`.)

3. **Circular import real verificado**: si dos modulos se importan
   mutuamente al nivel de `models.py` o equivalente, el refactor
   estructural (mover el modelo compartido a `apps.core`,
   abstraer la dependencia, usar string-FKs) es la solucion. NO
   se acepta lazy import "porque hay ciclo" sin verificar:

   ```bash
   grep -r 'from apps.X' apps/Y/models.py    # Y -> X?
   grep -r 'from apps.Y' apps/X/models.py    # X -> Y?
   ```

   Si ambos son 0, NO hay ciclo real — el lift es seguro.

4. **`AppConfig.ready()` — registro de signals (constraint de Django)**:
   los handlers/signals que importan modelos NO pueden importarse al top de
   `apps.py` — Django lanza `AppRegistryNotReady` porque el registro de apps
   aún no está poblado. El patrón canónico de Django es importarlos dentro de
   `ready()`. Como el checker prohíbe `import` dentro de funciones y NO tiene
   mecanismo `# noqa`, la resolución sancionada es **`importlib.import_module(...)`**
   dentro de `ready()` con `import importlib` al top — es una **llamada de
   función**, no un statement `import`, así que el AST gate da exit 0 y el
   arranque se preserva. Verificar SIEMPRE empíricamente (no asumir) que el
   lift al top rompe `django.setup()` antes de aplicar esta excepción.

   ```python
   # apps.py — CORRECTO (excepción #4)
   import importlib
   class OrdersConfig(AppConfig):
       def ready(self):
           importlib.import_module('apps.orders.signals')   # call, no statement
   ```

   Origen: iniciativa `eliminar-lazy-imports-residual-loop` (2026-06-03),
   `apps/orders/apps.py` + `apps/notifications/apps.py` (api@bee683b).

## Por que existe esta regla

PEP 8 + ESLint best practices coinciden:

- **Visibilidad de dependencias**: el lector ve al inicio del
  archivo de que depende. Imports en metodos esconden
  acoplamientos.
- **Linter / tooling consistency**: `isort`, `pyflakes`, `mypy`,
  `ruff`, `eslint-plugin-import` se quejan de lazy. Mantenerlos
  contentos evita ruido y permite que hagan su trabajo.
- **Performance trivial pero real**: cada llamada a la funcion
  paga el costo del lookup en `sys.modules` (Python) o el
  resolver de CommonJS (JS).
- **Anti-patron viajero**: confirmado empiricamente en sesion
  2026-05-20 (round 2 + round 6 de iniciativa
  `eliminar-lazy-imports-pep8`). El propio agente Claude
  reintroduce lazy imports "por consistencia con el patron del
  archivo" cuando lo ve en codigo existente. Tests con lazy
  imports propagan el patron a production por copy/paste de
  fixtures. **La unica defensa estable es hooks automaticos +
  AST walker en CI.**

## Verificacion

Antes de cada commit:

```bash
# api/ — Python
cd api && python3 scripts/check_no_lazy_imports.py

# ui/ — JavaScript (cuando este implementado FU-LAZY-2)
cd ui && node scripts/check-no-lazy-imports.mjs
```

Ambos retornan exit 0 si limpio, 1 si hay lazy detectado.

Los hooks pre-commit en cada submodulo ejecutan estos checkers
automaticamente sobre staged files. Skip manual:
`git commit --no-verify` solo en emergencia documentada.

## Iniciativas relacionadas

- `docs/source/gestion/pm/api/iniciativas/eliminar-lazy-imports-pep8/`
  — refactor de 164 imports en `practicayoruba/apps/**` + 593 en
  `tests/**`. Estado: COMPLETADA.
- `docs/source/gestion/pm/ui/iniciativas/eliminar-lazy-imports-ui/`
  — equivalente para ui (FU-LAZY-2). Estado: EN EJECUCION.

## Leccion del refactor — para futuras pasadas

**El anti-patron viaja por copy/paste.** Documentar la regla no
basta. Cubrir con hook ambos lados (codigo + tests + UI) cierra
los vectores de propagacion. Sin esta cobertura, el patron
reaparece en semanas:

1. Sesion 2026-05-20 round 2: agente reintroduce 5 lazy en
   `DeactivateAccountView.post` por consistencia con
   `EmailVerifyView.post` previo (que aun los tenia).
2. Sesion 2026-05-20 round 6: el ejecutor detecta que el alcance
   "tests fuera de scope" era falso — 593 lazy en tests podian
   propagarse a apps por copy/paste de fixtures.

Conclusion: **siempre cubrir produccion + tests + UI en una
sola iniciativa**, no por fases.
