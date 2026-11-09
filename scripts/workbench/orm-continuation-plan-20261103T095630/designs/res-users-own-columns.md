# Análisis — lectura de columnas propias de `res.users` (TASK-API-0182, #96)

Fecha: 2026-11-09T00:57:54 · rama `feature/vm-x2hokp-orm-root`.

## Contrato (odoo19c)

Leer `login` de un usuario cuyo partner oculta una regla levanta
`AccessError`: `Field.__get__` → `_fetch_field` → `fetch` →
`check_access('read')` (`odoo/orm/models.py:3775-3818`), y las reglas del
padre de `_inherits` aplican al hijo (`ir_rule.py:144-150`). Medido en el
contrato `test_contract_access_on_read_reference.py`: escenario
`users own login` → `AccessError`; aquí devuelve el valor (está en `OPEN`).

## Por qué aquí no ocurre (medido en el código)

- `ResUsers` deriva de `models.DefaultGetMixin, TimeStampedModel`
  (`src/addons/base/models/res_users.py:471`), no de `BaseModel`.
- `login` es `fields.Char` (`res_users.py:705`). La comprobación de
  lectura de un campo almacenado vive en `FieldDescriptor.__get__`
  (`src/orm/fields.py`, rama de caché fallida) y exige
  `hasattr(instance, 'check_access')` y `instance._ids`. Una fila de
  Django no tiene ninguna de las dos: `check_access` es del
  `AccessQuerySet` (`src/orm/models.py:339`), no de la instancia.
- `ResUsers.objects.get(pk=…)` no filtra por reglas: el contrato de la
  referencia tampoco filtra en `browse`; filtra al leer.

## Consumidores expuestos

`grep -rn "\.login\b" src addons --include=*.py` sin `tests/`: **61** lecturas
en **23** archivos. Bajo el modelo de acceso de este árbol —sin actor no hay
permiso (fail-closed)— cualquier comprobación nueva en la lectura alcanza a
todos ellos. Es el mismo efecto que obligó a elevar `ir.cron` y `res.users`
al leer `tz` (H-API-1182).

## Opciones

| Opción | Qué toca | Riesgo |
|---|---|---|
| A. `ResUsers` deriva de `BaseModel` | jerarquía, managers, migraciones, todos los consumidores | el mayor; la instrucción 3.2.14-C pide no asumir que es seguro |
| B. comprobación de lectura para filas de Django cuyo manager es `AccessQuerySet`, en la ruta de `FieldDescriptor` | todos los modelos con `AccessQuerySet`, no sólo `res.users` | transversal; exige el censo de esos modelos y de sus lectores |
| C. excepción especial para `login` | un campo | prohibida por la instrucción (§9.1) |

## Decisión de esta unidad

No se implementa en este pase: A y B son transversales y exigen su propio
censo de consumidores antes de la prueba RED; C está prohibida. Queda abierta
bajo TASK-API-0182 con esta condición de cierre: medir cuántos modelos tienen
`AccessQuerySet` sin derivar de `BaseModel` y cuántas lecturas sin actor los
alcanzan, y elegir entre A y B con esa cifra.

## Condición de cierre, medida

`apps.get_models()` con el registro cargado (`config.settings.testing`):
**444** modelos, **437** con `AccessQuerySet` como queryset del manager por
defecto, de ellos **389** sin derivar de `BaseModel`.

*Métrica:* clase del queryset del `_default_manager` y herencia de
`BaseModel`.
*Ciega a:* modelos que comprueben la lectura por otra vía propia (vista,
serializer); el conteo mide el ORM, no la API.

Consecuencia: la lectura de columnas propias sin `check_access` no es un
defecto de `res.users` sino de 389 modelos. Ni la opción A (migrar uno) ni
una excepción por modelo lo cierran; la forma que lo cierra es la B o la
migración progresiva de esos modelos a `BaseModel`, y elegir entre ellas es
una decisión de arquitectura del ejecutor. Mientras tanto
`users own login` sigue en `OPEN` del contrato, con esta cifra como su
evidencia.
