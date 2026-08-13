"""Modelos del addon ``l10n_mx`` (estructura Odoo: un archivo por modelo).

**Deliberadamente vacío de imports.** Los seis módulos de extensión y
``template_mx`` los importa ``L10nMxConfig.ready()``, no este archivo: en
tiempo de import del paquete el registro de modelos aún no está poblado y
``add_to_class`` sobre ``account.account`` fallaría con ``AppRegistryNotReady``.
"""
