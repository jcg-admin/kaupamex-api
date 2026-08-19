r"""``res.country.group`` extendido por ``account`` — excepciones fiscales por estado.

Adaptación de ``addons/account/models/res_country_group.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 12 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 de 1
====================================

Un único campo M2M, sin métodos. ``ResCountryGroup`` (grupo de países, p. ej.
la zona SEPA) y ``ResCountryState`` existen los dos en ``base``
(``src/addons/base/models/res_country_group.py`` y ``res_country.py:204``),
así que el porte es directo.

Qué es
========

Una posición fiscal puede aplicar a un grupo de países completo (``odoo19c:
account_fiscal_position.py:81`` ya lo porta como
``account.AccountFiscalPosition.country_group``). ``exclude_state_ids``
acota esa aplicación: los estados/provincias listados aquí quedan FUERA del
grupo a efectos fiscales, aunque su país sí pertenezca a él — el caso de uso
de la referencia es un grupo continental que excluye territorios con régimen
fiscal propio (islas, zonas francas).
"""
import fields

from addons.base.models.res_country_group import ResCountryGroup


def apply_account_extensions():
    """≙ ``_inherit = 'res.country.group'`` de ``account``.

    Se llama desde ``AccountConfig.ready()``, no al importar: en tiempo de
    import el registro de modelos aún no está poblado.
    """
    if not hasattr(ResCountryGroup, 'exclude_state_ids'):
        ResCountryGroup.add_to_class('exclude_state_ids', fields.Many2many(
            'base.ResCountryState', blank=True,
            related_name='excluded_from_groups',
            db_table='res_country_group_exclude_state_rel',
            help_text='Estados/provincias excluidos de este grupo a efectos '
                      'fiscales, aunque su país sí pertenezca (Odoo '
                      'exclude_state_ids).',
        ))
