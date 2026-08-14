"""Modelos del addon ``account_qr_code_emv`` (estructura Odoo: un archivo
por modelo — aquí, uno: ``res_bank.py``).

**Deliberadamente vacío de imports** — mismo criterio que
``addons.l10n_mx.models``: ``AccountQrCodeEmvConfig.ready()`` importa
``res_bank`` y aplica su extensión, no este archivo. En tiempo de import del
paquete el registro de modelos aún no está poblado y ``add_to_class``/
``setattr`` sobre ``base.ResPartnerBank`` fallaría con
``AppRegistryNotReady``.
"""
