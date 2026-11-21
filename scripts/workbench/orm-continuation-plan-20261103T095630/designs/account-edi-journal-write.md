# account-edi-journal-write-0397 — `write` de `account.journal` en `account_edi`

## Referencia

`odoo19c: addons/account_edi/models/account_journal.py:25-41` — `write`:

1. si `vals` trae `edi_format_ids`, guarda los formatos anteriores, delega en
   `super().write(vals)` y calcula los quitados (`old - self.edi_format_ids`);
2. busca los `account.edi.document` de los asientos de esos diarios, con un
   formato quitado y `state` en `to_cancel`/`to_send`;
3. si alguno es de un formato que `_needs_web_services()` → `UserError`
   (la transacción del llamador deshace la escritura);
4. si no, **borra** esos documentos (`documents.unlink()`, `:39-41`).

## Estado heredado (consumidor)

`addons/account_edi/models/account_journal.py` declaraba la escritura como
"portada (mecanismo distinto)": un receptor `m2m_changed` en `pre_remove`.
La premisa era que el M2M se escribe fuera de `save()`
(`journal.edi_format_ids.set(...)`). Medido hoy:

- `AccountJournal` es `BaseModel` (`addons/account/models/account_journal.py:18`)
  y el addon escribe el M2M con `journal.write({'edi_format_ids': [Command.set(...)]})`
  (`account_journal.py:124`);
- no hay ninguna llamada a `.set`/`.add`/`.remove`/`.clear` del manager sobre
  `edi_format_ids` ni sobre `journals` en `addons/`, `src/` o `tests/`;
- el receptor bloquea pero **no implementa el paso 4**: los documentos de un
  formato sin web-service sobreviven a la desactivación.

| Contrato | Clase |
|---|---|
| bloqueo por documentos pendientes de un formato con web-service | ABSENT por la vía de `write` (medido, ver abajo) |
| borrado de los pendientes de un formato sin web-service | ABSENT |
| punto de intercepción `write` | DIVERGENT (señal declarada como divergencia) |

## Cambio

- `write(self, previous, vals)` en `account_edi/models/account_journal.py`,
  instalado con `extend_model('account.journal', overrides={'write': write})`
  dentro de `apply_account_edi_extensions()`: sigue los cuatro pasos de la
  fuente sobre el recordset.
- Se retira `_guard_edi_format_removal` y su `@receiver`: la intercepción vive
  donde la fuente la pone. La prosa del módulo (tabla y sección
  "`write` → `m2m_changed`") se reescribe con la evidencia.
- No se añade ninguna transacción: la de la fuente es la del llamador, igual
  aquí.

## Pruebas

`tests/unit/account_edi/test_account_journal_write.py`:

- quitar un formato con web-service y un documento `to_send` → `UserError`, y
  bajo el `atomic` del llamador el diario conserva el formato;
- quitar un formato sin web-service → la escritura se aplica y el documento
  `to_send` se borra (rojo hoy);
- un documento `sent` del formato quitado no se borra;
- una escritura que no toca `edi_format_ids` no consulta documentos.

Control de anulación: sin el override, cae el caso del borrado y el del
bloqueo.

## Medición del control de anulación (2026-11-21)

Con el módulo de `630ceca4` (receptor `m2m_changed`, sin override) y la
suite nueva: `2 failed, 2 passed`. Caen el borrado **y el bloqueo**: una
escritura por `write({'edi_format_ids': [Command.set(...)]})` no llega al
receptor en `pre_remove`, así que la fila «SATISFIED (por señal)» del
inventario heredado era falsa — la prosa la afirmaba y nada la medía. Con el
override: `10 passed` en `tests/unit/account_edi`.
