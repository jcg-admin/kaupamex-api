# `account.journal`: herencia efectiva de sus mixins

Unidad: `account-journal-mixins-0515` (TASK-API-0515). Revisión de partida:
`61a00d9b`. Continúa `designs/account-journal-inherited-prose.md`, acción 4.

## Fuente

`odoo19c: addons/account/models/account_journal.py:46` —

```
_inherit = ['portal.mixin',
            'mail.alias.mixin.optional',
            'mail.thread',
            'mail.activity.mixin',
           ]
```

Como `account.journal` no está en su propia lista, la fuente compone el
modelo con esos cuatro mixins como bases, en ese orden
(`odoo19c: odoo/orm/model_classes.py:150`).

## Estado medido (`61a00d9b`)

`class AccountJournal(models.BaseModel, TimeStampedModel)`: la lista
`_inherit` está declarada verbatim y es sólo metadato; el diario no hereda
ninguno de los cuatro. Tres existen aquí como clases abstractas y ya los
heredan otros modelos `BaseModel`:

| Mixin | Clase | Quién lo hereda ya |
|---|---|---|
| `portal.mixin` | `PortalMixin`, `addons/portal/models/portal_mixin.py` | `purchase.order`, `sale.order` |
| `mail.thread` | `MailThread`, `addons/mail/models/mail_thread.py` | `hr.employee`, `hr.job`, `purchase.order`… |
| `mail.activity.mixin` | `MailActivityMixin`, `addons/mail/models/mail_activity_mixin.py` | `hr.employee`, `hr.version`… |
| `mail.alias.mixin.optional` | no existe (0 clases con ese `_name`) | — |

`account` ya importa `addons.mail` y `addons.portal` desde otros cinco
archivos, y ni `mail` ni `portal` importan `account`: la herencia no crea
ciclo.

## Cambio

`class AccountJournal(models.BaseModel, PortalMixin, MailThread,
MailActivityMixin, TimeStampedModel)`, en el orden de `_inherit`.

Medido: `makemigrations --dry-run` pide una sola operación, la columna
`access_token` de `PortalMixin`
(`odoo19c: addons/portal/models/portal_mixin.py:16`). Migración
`0051_journal_portal_access_token` de `account`. `MailThread` y
`MailActivityMixin` no añaden columnas: sus mensajes, seguidores y
actividades viven en tablas propias con referencia polimórfica.

`mail.alias.mixin.optional` **no entra**: bloqueado por `TASK-GEN-0413`
(porte de `mail.alias.mixin`, `pending`), que es de donde hereda la
variante opcional. El comentario de la clase lo sigue declarando, y los
dos símbolos del diario que lo consumen (`alias_name`,
`_alias_get_creation_values`,
`odoo19c: addons/account/models/account_journal.py:829`) quedan sin
portar con esa misma condición. La obligación
`AccountJournal._inherit` queda cumplida en tres de sus cuatro nombres, y
la unidad lo declara así al asentarse.

## Pruebas

`tests/unit/account/test_journal_mixins.py`:

| Caso | Espera |
|---|---|
| las bases | el diario es subclase de `PortalMixin`, `MailThread` y `MailActivityMixin`, en ese orden en el MRO |
| `message_post` sobre un diario | crea un `mail.message` con `model` `account.journal` y el `res_id` del diario |
| `activity_schedule` sobre un diario | crea una actividad ligada al diario |
| `_portal_ensure_token` | escribe `access_token` en la fila y devuelve el mismo valor la segunda vez |
| la lista `_inherit` | sigue verbatim, con los cuatro nombres |

Anulación: con la base de partida (`BaseModel`, `TimeStampedModel`) caen
los cuatro primeros y queda el quinto, que mide el metadato.

*Métrica:* el MRO de la clase y las filas de `mail_message`,
`mail_activity` y `account_journal` leídas tras cada llamada.
*Ciega a:* el seguimiento de campos (`tracking=True`), que la fuente
declara en varios campos del diario y aquí ninguno lleva todavía; y al
alias de correo.
