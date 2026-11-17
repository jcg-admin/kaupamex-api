# `account.journal`: conciliación de la prosa heredada sobre sus mixins

Instrucción 4.4.0 §3. Tres investigaciones de sólo lectura delegadas
(referencia, Consumer y TASK, verificadores) el 2026-11-17; lo decisivo se
contrastó a mano contra la fuente y el árbol antes de escribirlo aquí.
Referencia: odoo-tools `abe4040ec1`.

## Referencia (medida)

`odoo19c: addons/account/models/account_journal.py:43-53`: `_name`,
`_description = "Journal"`, `_order = 'sequence, type, code'`,
`_inherit = ['portal.mixin', 'mail.alias.mixin.optional', 'mail.thread',
'mail.activity.mixin']`, `_check_company_auto = True`,
`_check_company_domain = models.check_company_domain_parent_of`,
`_rec_names_search = ['name', 'code']`.

Como `account.journal` no está en su propia lista, la fuente crea un modelo
nuevo cuyas bases son los cuatro mixins (`odoo19c: odoo/orm/
model_classes.py:150-212`). Del diario, sólo `mail.alias.mixin.optional` se
consume de forma explícita (`alias_name`, `_alias_get_creation_values`,
`odoo19c: addons/account/models/account_journal.py:829-842`); de
`portal.mixin` hay 0 usos en el archivo.

`unlink` (`odoo19c: addons/account/models/account_journal.py:725-733`):
borra las líneas de método de pago del diario con su `unlink`, luego el
diario, y después las cuentas bancarias que sólo usaban los diarios
borrados.

## Afirmaciones del comentario de `addons/account/models/account_journal.py`

| Afirmación | Clasificación | Evidencia |
|---|---|---|
| «`mail.thread` y `mail.activity.mixin` SÍ están (`mail_thread.py`)» | PARTIALLY_TRUE | existen (`addons/mail/models/mail_thread.py:51`, `addons/mail/models/mail_activity_mixin.py:127`: el segundo no está en el archivo citado); el diario no los hereda |
| «`portal.mixin` NO» | OUTDATED | `class PortalMixin` en `addons/portal/models/portal_mixin.py:36`, heredada por `sale.order` y `purchase.order`; no declara `_name` |
| «`mail.alias.mixin.optional` NO» | VERIFIED_CURRENT | 0 clases con ese `_name` |
| «su porte es la tarea #163» (portal) | WRONG_TASK_MAPPING | el ordinal resuelve a `TASK-GEN-0415` (hilo de mail de `crm.team`), que no trata de `portal.mixin` |
| «#161 (mail.alias.mixin)» | VERIFIED_CURRENT (con matiz) | `TASK-GEN-0413`, pending; porta `mail.alias.mixin`, no la variante `.optional` que el diario nombra |
| «sin `_name` no entra en el registro (tarea #333)» | mecanismo VERIFIED_CURRENT; tarea UNVERIFIED | `_register` exige `_name`; el ordinal tiene tres candidatas y ninguna nombra el tema |
| «`_inherit` verbatim: nombra la extensión» | PARTIALLY_TRUE | en este ORM la lista es metadato: nada la lee en ejecución; el comportamiento sale del MRO |
| (omitidos) `_check_company_auto`, `_check_company_domain`, `_rec_names_search` | VERIFIED_CURRENT (ya declarados) | `sed -n 38,50p addons/account/models/account_journal.py`: los tres están, con su cita a `:51-53` |

## Acciones

1. Reescribir el comentario con lo medido y las identidades canónicas
   (`TASK-GEN-0413`); retirar los ordinales `#161`, `#163`, `#333`.
2. Portar `AccountJournal.unlink` en la unidad
   `account-journal-payment-method-lines-0515` (ya adopta `BaseModel`).
3. (Retirada.) Los tres atributos de clase ya están declarados.
4. Herencia efectiva de los cuatro mixins: no se cambia aquí. Ningún
   consumidor usa hoy `message_`, `activity_`, `alias_` ni `access_url`
   sobre un diario (0 resultados); el alias depende de `TASK-GEN-0413`.
   Unidad sucesora: `account-journal-mixins-0515`.

*Métrica:* símbolos y líneas leídos en la fuente y en el árbol; filas del
store leídas en modo sólo lectura.
*Ciega a:* consumidores indirectos (una variable que contenga un diario sin
llamarse `journal`) y el contenido en ejecución de `MODELS_BY_NAME`.

## Corrección del coordinador (mismo día)

La fila de los tres atributos de clase se escribió como
IMPLEMENTATION_REQUIRED copiando el informe del lote 0, que leyó la fuente
y no el Consumer. Medido después: el diario ya los declara. Es el defecto
que 4.4.1 §8 nombra —una propuesta tratada como verificación—; la tabla
`outputs/account-journal-payment-method-lines-0515/research/verdicts.tsv`
la tenía como UNVERIFIED y ahora la cierra con su comando.
