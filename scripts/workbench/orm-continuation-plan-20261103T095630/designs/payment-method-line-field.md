# `account.payment`: la línea de método de pago y lo que cuelga de ella

Unidad: `account-payment-method-line-field-0515` (TASK-API-0515), paso 4 de
`designs/payment-method-line-chain.md`. Referencia: odoo-tools
`abe4040ec1`. Escrito el 2026-11-17, antes de tocar
`addons/account/models/account_payment.py`.

## Contrato de la referencia

| Símbolo | Cita | Contrato |
|---|---|---|
| `available_payment_method_line_ids` | `odoo19c: addons/account/models/account_payment.py:85-86` | Many2many calculado, no almacenado |
| `_compute_payment_method_line_fields` | `odoo19c: addons/account/models/account_payment.py:585-591` | las líneas disponibles del diario para el `payment_type`, menos los códigos de `_get_payment_method_codes_to_exclude` |
| `_get_payment_method_codes_to_exclude` | `odoo19c: addons/account/models/account_payment.py:610-613` | `ensure_one()`; `[]` |
| `payment_method_line_id` | `odoo19c: addons/account/models/account_payment.py:74-84` | Many2one calculado, almacenado, editable, `copy=False` |
| `_compute_payment_method_line_id` | `odoo19c: addons/account/models/account_payment.py:565-583` | la preferida del partner si está disponible; si no la actual si sigue disponible; si no la primera; si no vacío |
| `payment_method_id` | `odoo19c: addons/account/models/account_payment.py:87-92` | relacionado almacenado |
| `payment_method_code` | `odoo19c: addons/account/models/account_payment.py:176-177` | relacionado no almacenado |
| `outstanding_account_id` | `odoo19c: addons/account/models/account_payment.py:123-129` y `:620-623` | calculado almacenado: `payment_account_id` de la línea |
| `_check_payment_method_line_id` | `odoo19c: addons/account/models/account_payment.py:863-873` | obligatoria; si la línea tiene diario, es el del pago |
| `partner_id` | `odoo19c: addons/account/models/account_payment.py:116-122` | `res.partner`, `ondelete='restrict'` |
| `AccountPaymentMethodLine.unlink` | `odoo19c: addons/account/models/account_payment_method.py:150-162` | la línea usada por un pago pierde el diario y no se borra |

## Nuestro estado (medido en `32da44b9`)

- `AccountPayment` es `models.Model`, 10 campos, ningún método de pago
  (`grep payment_method addons/account/models/account_payment.py` → 0).
- `partner` apunta a `settings.AUTH_USER_MODEL` (`base.ResUsers`) con
  `SET_NULL`. La prosa heredada dice «Odoo partner_id → party».
  Clasificación: **FALSE** como porte: la fuente declara `res.partner` con
  `restrict`, y el cómputo de la línea lee
  `partner_id.property_inbound_payment_method_line_id`, que aquí vive en
  `ResPartner` (`addons/account/models/partner.py:267-296`). Lectores de
  `payment.partner` en addons: 0 (`grep -rn "\.partner\b"` sobre
  `account_check_printing` y `account_payment`).
- Sitios que crean un pago: 8 (corregido el 2026-11-17: el noveno acierto
  del `grep` era la declaración de la clase), en `tests/unit/account_check_printing`,
  `tests/unit/account_payment`, `tests/unit/account`,
  `tests/integration/account`.
- `account_check_printing` declara por escrito («Divergencia 1») que modela
  el cheque sin `payment_method_line_id` porque el pago no lo tenía. Con
  este campo esa nota pasa a **OUTDATED**; reconciliarla es su propia
  unidad, registrada aquí como sucesor, no parte de este cambio.

## Pasos (cada uno con su prueba y su anulación)

1. **Adopción**: `class AccountPayment(models.BaseModel, TimeStampedModel)`.
   Los ocho sitios de creación pasan a ejecutarse con entorno (`sudo`).
   Medido en `646f085d` (2026-11-18): con sólo el cambio de base,
   `makemigrations --check` no detecta cambios y la regresión derivada de
   cinco directorios da 4259 que pasan y ningún fallo. Los ocho sitios de
   creación usan el gestor de Django y no necesitaron `sudo`.

   **1a — `date`, `name` y la secuencia (requisito de la adopción,
   medido).** El verde de arriba no cubría la búsqueda: una sonda
   `env()['account.payment'].search([('id', '=', 0)])` da `ValueError:
   Invalid field 'date' on model 'account.payment'`. Es el mismo defecto que
   C2a encontró en el apunte: la clase declara `_order = "date desc, name
   desc"` como la fuente (`odoo19c: addons/account/models/
   account_payment.py:11`) y ninguno de los dos campos está portado. Se
   portan con la adopción, en el mismo commit:

   | Símbolo | Fuente | Aquí |
   |---|---|---|
   | `date` | `odoo19c: addons/account/models/account_payment.py:16` — `fields.Date(default=fields.Date.context_today, required=True, tracking=True)` | igual. Filas existentes: la fecha de su `create_date`, que es el día en que el valor por defecto se habría evaluado |
   | `name` | `odoo19c: addons/account/models/account_payment.py:15` — `fields.Char(string="Number", compute='_compute_name', store=True)` | igual |
   | `_compute_name` | `odoo19c: addons/account/models/account_payment.py:414` | con `id` y estado `in_process` o `paid` y sin nombre, el siguiente número de la secuencia `account.payment` de la empresa, con `sequence_date=payment.date`. `pendiente:` la rama de `move_id.name`: el pago no tiene `move_id` aquí |
   | `seq_account_payment` | `odoo19c: addons/account/data/ir_sequence.xml:4` — `ir.sequence` «Payment», código `account.payment`, prefijo `PAY`, relleno 5, sin empresa, `noupdate` | `seed_payment_sequence` en `addons/account/data/sequences.py`, con su identificador externo, idempotente por `(module, name)` como `seed_manual_payment_methods` |

   La secuencia es `standard` (el valor por defecto del campo), así que su
   numeración sale de una secuencia nativa de PostgreSQL que
   `IrSequence.save` crea al dar de alta la fila. La siembra corre sobre
   modelos históricos y no pasa por `save`: `seed_payment_sequence` crea la
   nativa con `_create_sequence` si `pg_class` no la tiene.
   **Divergencia de mecanismo, declarada:** la fuente carga el XML una vez
   por el ORM; aquí la siembra se repite tras cada prueba transaccional y
   tiene que ser idempotente también sobre la secuencia nativa.

   **Defecto heredado que el cómputo destapó: `next_by_code` con empresa
   no ve la secuencia global.** `_compute_name` pide el número con la
   empresa del pago, y la secuencia sembrada no tiene empresa. Medido con
   una sonda: `IrSequence.next_by_code('account.payment')` da `PAY00001` y
   `IrSequence.next_by_code('account.payment', company=company)` da `None`.
   La fuente busca `('company_id', 'in', [company_id, False])`
   (`odoo19c: odoo/addons/base/models/ir_sequence.py:287`), que incluye las
   filas sin empresa; aquí se tradujo a `company__in=[company, None]`, y en
   SQL `IN (…, NULL)` no casa con una columna nula. La prosa del método
   afirma que «la propia gana sobre la global»: como porte es **FALSE** en
   su mitad global. Se corrige a `Q(company=company) |
   Q(company__isnull=True)` en `next_by_code` de
   `src/addons/base/models/ir_sequence.py`; el orden —la propia primero—
   no cambia. Pruebas en
   `tests/unit/base/test_ir_sequence_next_by_code_company.py`: con empresa
   y sólo secuencia global, sale la global; con las dos, sale la propia;
   con secuencia de otra empresa y ninguna global, `None`.

   Migración `0048_payment_date_name` de `account`: las dos columnas, el
   relleno de `date`, la siembra de la secuencia y `ComputeStoredFields`
   para `name`. Semilla de pruebas `_payment_sequence_seed` en
   `tests/conftest.py`.

   Pruebas en `tests/unit/account/test_payment_date_name.py`:

   | Caso | Espera |
   |---|---|
   | buscar pagos | no falla; el orden es `date desc, name desc` |
   | pago nuevo sin fecha | `date` es hoy |
   | pago en borrador | `name` vacío |
   | pago que pasa a `in_process` | `name` es `PAY` y cinco dígitos |
   | segundo cómputo del mismo pago | `name` no cambia: no consume otro número |
   | la siembra, dos veces | una sola fila `account.payment` y su identificador externo `account.seq_account_payment` |
   | la operación de relleno de la migración | una fila con `date` nula recibe la fecha de su `create_date` |

   Anulaciones: sin la guarda `not payment.name` cae el caso del segundo
   cómputo; sin la siembra, el del nombre; sin el relleno, el de la
   migración.

2. **`partner`**: `res.partner`, `ondelete='restrict'`
   (`odoo19c: addons/account/models/account_payment.py:116` —
   `Many2one('res.partner', string="Customer/Vendor", ondelete='restrict',
   domain="['|', ('parent_id','=', False), ('is_company','=', True)]",
   tracking=True, check_company=True)`). La columna sigue siendo
   `partner_id`; cambia a quién apunta.

   Migración `0049_payment_partner_res_partner` de `account`, en tres
   operaciones, porque el valor guardado es un id de usuario y la
   restricción de clave ajena no puede cambiar de tabla con esos valores
   dentro:

   1. la clave deja de tener restricción en la base (`db_constraint=False`);
   2. `users_to_partners` sustituye cada id de usuario por el `partner_id`
      de ese usuario (todo usuario tiene uno: `res_users.partner_id` es
      obligatorio);
   3. la clave pasa a `base.ResPartner` con `ondelete='restrict'`,
      declarado como en la fuente. Este ORM lo traduce a `models.RESTRICT`
      (`ON_DELETE_POLICY`, `src/orm/fields_relational.py`), que emite el
      `ON DELETE RESTRICT` de la base; el contrato de políticas admite
      `RESTRICT` y `PROTECT` para `restrict`. Corrección de este diseño:
      decía `PROTECT`, que es lo que se obtiene escribiendo el `on_delete`
      de Django a mano y deja el atributo `ondelete` del campo en su valor
      por defecto (`'set null'`), medido en la primera versión de la prueba.

   Medido antes de escribirla: ningún sitio de `addons/`, `src/` ni
   `tests/` escribe `partner=` en un pago, y nadie lee
   `account_payments` (el nombre inverso), que se conserva.

   Pruebas en `tests/unit/account/test_payment_partner.py`:

   | Caso | Espera |
   |---|---|
   | el campo | apunta a `res.partner`, con `ondelete` `restrict` |
   | borrar un `res.partner` con pagos | rehúsa (`RestrictedError`); el pago sigue |
   | `users_to_partners` | una fila con el id de un usuario queda con el id de su partner |

   Anulaciones: con `SET_NULL` cae el segundo; con la sustitución anulada,
   el tercero.

3. **Campos y cómputos** de la tabla, con los nombres de la fuente
   (`payment_method_line_id` como columna `payment_method_line_id`,
   `SET_NULL`, el default de un Many2one no requerido).
   Migración de `account` (el número lo fija el paso al llegar; `0044`
   quedó tomado por el bloque D) con `ComputeStoredFields` para
   `payment_method_line_id`, `payment_method_id`, `outstanding_account_id`.
   Migración `0050_payment_method_line_fields` de `account`.

   **Requisito del ORM, medido al implementarlo: un Many2one hacia un
   modelo de Django leído sobre el conjunto vacío.**
   `_compute_outstanding_account_id` hace
   `pay.payment_method_line_id.payment_account_id`, y con un diario sin
   líneas `payment_method_line_id` es el conjunto vacío. Aquí esa lectura
   lanzaba `KeyError: 'payment_account'` y después `DoesNotExist`:
   `_forward_get` (`src/orm/models.py`) devolvía el vacío sólo cuando el
   comodelo es `BaseModel` y dejaba el resto a Django, que busca una fila.
   La fuente devuelve el valor nulo del campo
   (`odoo19c: odoo/orm/fields.py:1659` — «null record -> return the null
   value for this field»). Para un comodelo de Django el valor nulo de este
   árbol es `None`. Prueba en
   `tests/unit/orm/test_many2one_read_on_empty_recordset.py`: sobre el
   conjunto vacío, un Many2one a un `BaseModel` es el vacío del comodelo y
   uno a un modelo de Django es `None`, sin consultas. Anulación: sin la
   rama cae el caso del modelo de Django.

4. **`_check_payment_method_line_id`**.
5. **`AccountPaymentMethodLine.unlink`** y, con él, `AccountJournal.unlink`
   deja de borrar líneas usadas.

## Pruebas

`tests/unit/account/test_payment_method_line_field.py`:

| Caso | Espera |
|---|---|
| pago entrante en diario de banco | `payment_method_line_id` es la línea manual entrante; `payment_method_code == 'manual'` |
| partner con preferida disponible | gana la preferida |
| partner con preferida de otro diario | se ignora; primera disponible |
| diario sin líneas | `ValidationError` de `_check_payment_method_line_id` |
| línea de otro diario escrita a mano | `ValidationError` |
| `outstanding_account_id` | sigue a `payment_account_id` de la línea |
| `unlink` de línea usada | la fila sigue, `journal_id` nulo |
| `unlink` de línea sin uso | la fila desaparece |
| borrar un `res.partner` con pagos | rehúsa |

Anulaciones: retirar la rama de la preferida; retirar la segunda rama de la
restricción; retirar el filtro de uso en `unlink`. Cada una tumba sólo sus
casos.

*Métrica:* valores leídos de la base tras `flush_all`.
*Ciega a:* los lectores de la línea fuera de esta cadena (`:248-250`,
`:271`, `:326`, `:433`, `:649-655`, `:977`, `:1138`), que entran con el
porte de cada método que los contiene.
