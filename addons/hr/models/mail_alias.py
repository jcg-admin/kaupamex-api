"""Extensión de ``mail.alias`` — la política "sólo empleados" (Odoo ``hr``).

Adaptación de Odoo hr/models/mail_alias.py (odoo-tools@622ddc2a, odoo19c:,
LGPL-3, 17 líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 2 de 2
===================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
     - Forma aquí
   * - ``alias_contact`` (``selection_add=[('employees', …)]``, ``:10-12``)
     - portado como DIVERGENCIA de mecanismo
     - ``mail.MailAlias.alias_contact`` es un ``Char`` en este árbol
       (``addons/mail/models/mail_alias.py:180``), no un ``Selection``: no
       hay lista que extender — ``'employees'`` es simplemente un valor
       válido más de la columna, y este módulo lo declara como constante
       (``ALIAS_CONTACT_EMPLOYEES``) para que exista un nombre greppeable.
   * - ``_get_alias_contact_description`` (``:14-17``)
     - portado
     - ``extend_model('mail', 'MailAlias', metodos=…)``; nombre **verbatim**

``_inherit`` lo expresa ``extend_model``; par de Django porque el destino no
declara ``_name``.

Divergencias declaradas
========================

1. **``ondelete={'employees': 'cascade'}``** — es la política de Odoo para
   cuando el addon que aportó el valor del Selection se desinstala; sobre un
   ``Char`` no hay valor de enum que retirar, así que no aplica (la
   desinstalación de addons tampoco es un mecanismo de este árbol).
2. **La rama ``super()`` es el relevo por ``None`` de ``chain_method``** —
   el ``MailAlias`` de este árbol no declara
   ``_get_alias_contact_description``; si algún día el addon ``mail`` lo
   porta, la cadena lo preserva sin tocar este archivo.
"""
from orm.model_classes import extend_model
from tools.translate import _

#: ≙ el valor que ``selection_add`` agrega ('Authenticated Employees').
ALIAS_CONTACT_EMPLOYEES = 'employees'


def _get_alias_contact_description(self):
    """Descripción legible de la política del alias — ≙
    ``_get_alias_contact_description`` (``odoo19c: hr/models/mail_alias.py:14-17``).

    Devuelve ``None`` para cualquier otra política: es el relevo de
    ``chain_method`` hacia la implementación que ``mail`` instale (el
    ``super()`` de la referencia).
    """
    if self.alias_contact == ALIAS_CONTACT_EMPLOYEES:
        return _('addresses linked to registered employees')
    return None


def apply_hr_mail_alias_extensions():
    """Cuelga sobre ``mail.alias`` lo que ``hr`` le añade — ≙ ``_inherit``."""
    extend_model('mail', 'MailAlias', metodos={
        '_get_alias_contact_description': _get_alias_contact_description,
    })
