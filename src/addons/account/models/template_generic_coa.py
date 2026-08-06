"""``generic_coa`` — el plan contable genérico.

Adaptación fiel de ``odoo19c: account/models/template_generic_coa.py`` (addon
**LGPL-3**, copia con atribución por DEC-KX-03). Allá es un ``_inherit`` de
``account.chart.template`` con dos métodos decorados; aquí es una **subclase**
del cargador con los mismos dos, que es lo que ``_inherit`` significa cuando la
clase base no es un modelo del ORM sino una clase de Python.

Las tablas del plan —46 cuentas, 2 grupos de impuesto, 4 impuestos con sus 16
líneas de reparto, 2 posiciones fiscales— viven en ``data/template/*.csv``,
copiados verbatim de la referencia. Este módulo sólo aporta lo que **no cabe en
una tabla**: cómo se llama el plan y qué se escribe en la empresa.
"""
from addons.account.models.chart_template import ChartTemplate, template


class GenericCoaChartTemplate(ChartTemplate):
    """≙ el ``_inherit = "account.chart.template"`` de la referencia."""

    @template('generic_coa')
    def get_generic_coa_template_data(cls, template_code):
        """Los valores sueltos del plan — ≙ ``_get_generic_coa_template_data``.

        ``property_account_*`` no nombran una cuenta: nombran **el papel** que
        una cuenta cumple para la empresa. El identificador se resuelve contra
        las cuentas recién creadas, así que ``receivable`` acaba siendo la
        cuenta 1210 *de esta empresa*.
        """
        return {
            'name': 'Plan de cuentas genérico',
            'country': None,
            'property_account_receivable_id': 'receivable',
            'property_account_payable_id': 'payable',
        }

    @template('generic_coa', 'res.company')
    def get_generic_coa_res_company(cls, template_code):
        """Lo que el plan escribe en la empresa — ≙ ``_get_generic_coa_res_company``.

        La referencia escribe aquí 18 claves; se conservan las que este puerto
        tiene campo donde poner. ``post_load_data`` descarta el resto en
        silencio y a propósito: la lista es de la referencia y describe campos
        que aún no existen aquí, así que abortar por uno accesorio impediría
        cargar el plan entero. Los que faltan entran solos cuando su campo
        llegue.
        """
        return {
            'account_sale_tax': 'sale_tax_template',
            'account_purchase_tax': 'purchase_tax_template',
        }
