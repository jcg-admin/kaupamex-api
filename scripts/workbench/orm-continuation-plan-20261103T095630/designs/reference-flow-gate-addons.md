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
