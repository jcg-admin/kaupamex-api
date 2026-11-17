# `check_reference_flow.py` sobre addons, con anterioridad del estudio

Instrucción 4.3.3 §8. Autoridad que se extiende (EXTEND, no un gate nuevo):
`scripts/check_reference_flow.py` (`a11887b3`), cableado al final de
`.githooks/pre-commit`; pruebas `tests/unit/scripts/test_check_reference_flow.py`.

## 1. Lo que hoy no ve (medido)

`ROOT = 'src/orm/'`: un commit que sólo toca addons publica
`OK — 0 hallazgo(s) (alcance medido: 0 archivo(s) de src/orm/)`. Medido en
`ed74f56d` (cambio de `unlink`, dos políticas de FK y una migración en
`account`): alcance 0. Y el diseño basta con que esté **en el índice**: el
mismo commit que cambia el código puede traer el estudio que lo «precede».

## 2. Clases (§8.3) y qué exige cada una

| Clase | Qué la dispara | Exige |
|---|---|---|
| A | cuerpo de función cambiado en `src/orm/` | diseño previo que la nombre, con cita que resuelva y prueba existente (lo que ya hay) |
| B | cuerpo de método cambiado en `addons/*/models/*.py` o `src/addons/*/models/*.py` con archivo espejo en la referencia | lo mismo que A; la cita se resuelve contra el archivo espejo del addon |
| C | declaración de campo cambiada en esos modelos (asignación de clase cuyo valor es una llamada a `fields.*` o `models.*`), o migración nueva en `*/migrations/*.py` | diseño previo que nombre el campo (o el nombre de la migración), con cita que resuelva y prueba existente |
| D | sólo docstring, comentario o formato (el volcado AST no cambia) | nada |
| E | cuerpo cambiado en un modelo de addon **sin** archivo espejo en la referencia | diseño previo que la nombre y una prueba existente; **no** se exige cita (no se inventa una contraparte) |

## 3. Anterioridad (§8.5)

El diseño cuenta sólo si su versión en **`HEAD`** ya cubre el símbolo: el
estudio se commitea antes que la implementación. Un diseño que existe sólo en
el índice del mismo commit produce el hallazgo «el diseño que la cubre no
precede al cambio». La prueba nombrada sí se busca en el índice (nace con la
implementación, en TDD). Un mapa vigente en `HEAD` se reutiliza sin cambios.

La evidencia es el orden de commits en la rama, no el `mtime`.

## 4. Pruebas

Negativas: cita a símbolo inexistente en un addon; cuerpo de método de
addon sin diseño; campo cambiado sin diseño; migración nueva sin diseño;
diseño sólo en el índice; diseño sin prueba existente.
Positivas: porte fiel con diseño previo; cambio sólo de docstring; modelo sin
espejo con diseño sin cita (clase E); mapa previo reutilizado.
Anulaciones: retirar el eje de addons (caen los negativos B y C), retirar el
eje de anterioridad (cae el de diseño sólo en el índice).

## 5. Lo que sigue sin ver

Si la conducta coincide con la de la referencia (lo deciden las pruebas
discriminantes); dependencias no reconciliadas y divergencias sin decisión
(no tienen forma léxica); controladores, wizards y archivos fuera de
`models/` y `migrations/`; `src/tools`.

## 6. Medición previa a integrar (2026-11-17, sobre `f66047bd`)

Prototipo fuera del árbol (el árbol estaba bajo la F2 de `ed74f56d`).
Pruebas del gate: 43 passed. Anulaciones, restauradas por copia:

| Anulación | Cae exactamente |
|---|---|
| sin eje de addons (`change_kind` → `None` fuera de `src/orm`) | 9: las cuatro clases B/C/E de `test_each_path_has_its_change_kind`, los rechazos de método, campo y migración, el modelo sin espejo y el de anterioridad |
| sin anterioridad (el índice cuenta como `HEAD`) | 1: `test_a_design_only_in_the_index_does_not_precede_the_change` |

**Reproducción sobre los últimos 40 commits** (`probes/replay_reference_flow.py`,
sólo lectura, diseños del padre de cada commit; el eje A ya existía y no se
recuenta): 11 commits tocan modelos o migraciones de addon.

- Primera versión: 6 con hallazgo, 36 hallazgos. 13 eran citas cortas
  (`odoo19c: purchase_order.py:1274-1278`, relativas al addon) que el gate
  resolvía sólo desde la raíz: falso positivo. Corregido: una ruta sin
  directorio se busca en el paquete espejo (3 pruebas nuevas).
- Tras la corrección: 4 con hallazgo, 16 hallazgos. En los 4 el diseño entró
  en el mismo commit que el código (`9b913a70`, `d6ec96e9`, `c3521359`,
  `ffdcfa69`): es exactamente lo que el eje de anterioridad prohíbe hacia
  adelante. El resto son migraciones o métodos que ningún diseño previo
  nombraba. No se reescriben esos commits: la regla es prospectiva.
