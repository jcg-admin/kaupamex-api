"""Paquete de migraciones — addons.account_qr_code_sepa.

Vacío a propósito: este addon no declara ningún modelo propio (extiende
`base.ResPartnerBank` con métodos vía `setattr`, no con columnas nuevas — ver
`models/res_bank.py`). Sin campos que migrar, no hay operaciones que generar.
El paquete existe sólo porque Django exige `migrations/` en toda app
registrada en `INSTALLED_APPS`. Mismo criterio que `l10n_mx/migrations/` y
`account_qr_code_emv/migrations/` — ninguno de los tres tiene archivos de
operación.
"""
