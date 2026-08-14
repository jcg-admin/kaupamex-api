"""Modelos del addon ``base_iban`` (estructura Odoo: un archivo por modelo —
aquí, uno: ``res_partner_bank.py``).

**Deliberadamente vacío de imports** — mismo criterio que
``addons.account_qr_code_sepa.models``: ``BaseIbanConfig.ready()`` importa
``res_partner_bank`` y aplica su extensión, no este archivo. En tiempo de
import del paquete el registro de modelos aún no está poblado y ``setattr``
sobre ``base.ResPartnerBank`` fallaría con ``AppRegistryNotReady``.
"""
