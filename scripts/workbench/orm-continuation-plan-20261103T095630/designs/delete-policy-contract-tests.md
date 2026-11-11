# Pruebas discriminantes de las 96 políticas de borrado destructivas

Fecha: 2026-11-11T05:25:47. Fuente de la población: `outputs/fk_reference_ondelete.tsv`
(probe `probes/fk_reference_ondelete.py`, odoo-tools `abe4040ec1`), diseño
de contrato `designs/foreign-keys-delete-contract.md`.

## Población

Filas cuya política de Django es `CASCADE` donde la fuente conserva
(`set null`) o rehúsa (`restrict`):

| Fuente → Django | Filas |
|---|---|
| `set null` (defecto del Many2one) → `CASCADE` | 48 |
| `restrict` (defecto) → `CASCADE` | 45 |
| `restrict` explícito → `CASCADE` | 3 |
| **total** | **96** |

`fk_destructive_reproduce.tsv`: sobre la base de QA, 137 filas del
apéndice «no verificable: sin fila hija», 3 «diferencia semántica sin
pérdida». Ninguna de las 96 tenía filas hijas: la pérdida no se ha
reproducido sobre datos, sólo se deduce de la política.

## Tres planos, tres pruebas distintas

1. **Declarativo (atributo).** Por fila, `field.remote_field.on_delete`
   frente a la política que corresponde al `ondelete` de la fuente
   (`set null` → `SET_NULL`; `restrict` → `PROTECT`/`RESTRICT`).
   Paramétrica sobre las 96, `xfail(strict=True)`: hoy falla por la
   divergencia; si alguien corrige una fila, su caso pasa y obliga a retirar
   la marca de esa fila. Mide el atributo, **no** la pérdida.
2. **ORM (Collector).** Por familia, un caso con filas reales: borrar el
   padre por el ORM borra hoy el hijo (`today_*`, sin `xfail`, para que
   el `xfail` del contrato no oculte otra causa) y la fuente lo conserva o
   rehúsa (`xfail` estricto). Representantes: `res.device.log.user_id`
   (`set null`) e `ir.actions.todo.action_id` (`restrict`).
3. **PostgreSQL.** Las FK de Django 6.0.5 son `DEFERRABLE INITIALLY
   DEFERRED` con `confdeltype = 'a'` (NO ACTION; medido en
   `fk_census.out`): un `DELETE` en SQL del padre con hijo presente **no**
   borra en cascada; falla al comprobar la restricción. Prueba: con
   `SET CONSTRAINTS ALL IMMEDIATE`, el `DELETE` crudo lanza
   `IntegrityError` y el hijo sigue. La pérdida, si existe, es sólo del
   camino ORM.

## Lo que no se hace

No se reescriben las 1 089 FK ni se cambia ninguna política en este paso.
No se actualiza Django (6.1 sólo se estudió como candidato). Cada
corrección futura es por fila, con su caso pasando de `xfail` a verde.

*Métrica:* atributo `on_delete` por fila; filas existentes antes y
después de borrar por ORM y por SQL en los representantes.
*Ciega a:* el efecto de cada fila concreta sobre datos reales (sólo los
representantes crean filas); ondelete de campos sin FK física (los 245 «sin
contraparte»), que quedan fuera de esta población.

## Resultado (2026-11-11T05:27:30)

`tests/unit/orm/test_delete_policy_contract.py`: **4 passed, 98 xfailed**
(96 filas del plano declarativo + 2 contratos ORM). Pasan: el conteo de la
población (96 = 48 `set null` + 48 `restrict`), los dos `today_*` (el
ORM borra hoy el hijo) y el `DELETE` crudo, que no cascada (`IntegrityError`
con `SET CONSTRAINTS ALL IMMEDIATE`, el hijo sigue).

Control: aceptar `CASCADE` como política válida de `set null` hace que
exactamente las 48 filas de esa familia pasen a XPASS estricto y fallen
(`48 failed, 4 passed, 50 xfailed`); las 48 `restrict` y los 2 contratos
ORM siguen `xfail`. Restaurado y comparado con `cmp`.

Progreso sobre las 96: las 96 tienen ahora una prueba declarativa que
falla mientras difieran y que obliga a retirar su marca al corregirse; las
dos familias tienen un representante con filas reales por el ORM y por
SQL. Siguiente: corregir por fila, empezando por las `restrict` (la
fuente rehúsa; `CASCADE` borra en silencio), cada una con su migración
`AlterField` y su caso pasando de `xfail` a verde.
