"""Modelos del addon ``account_qr_code_sepa`` (estructura Odoo: un archivo
por modelo — aquí, uno: ``res_bank.py``).

**Deliberadamente vacío de imports** — mismo criterio que
``addons.l10n_mx.models`` y ``addons.account_qr_code_emv.models``:
``AccountQrCodeSepaConfig.ready()`` importa ``res_bank`` y aplica su
extensión, no este archivo. En tiempo de import del paquete el registro de
modelos aún no está poblado y ``setattr`` sobre ``base.ResPartnerBank``
fallaría con ``AppRegistryNotReady``.
"""
