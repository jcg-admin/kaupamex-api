"""Datos semilla de ``res.company`` — equivalente nativo de
``base/data/res_company_data.xml``.

Adaptación de ``odoo19c: odoo/addons/base/data/res_company_data.xml:4``
(idéntico en ``odoo18c:``), donde la compañía principal **no es una constante
de código**: es un registro con identificador estable::

    <record id="main_company" model="res.company">

y el código la resuelve por ese identificador, con un fallback determinista
(``odoo19c: odoo/addons/base/models/res_company.py:436-440``)::

    def _get_main_company(self):
        try:
            main_company = self.sudo().env.ref('base.main_company')
        except ValueError:
            main_company = self.env['res.company'].sudo().search(
                [], limit=1, order="id")

En este árbol el análogo del XML id es la columna ``code`` de ``ResCompany``
(``SlugField`` único). Por eso los códigos viven aquí, en el módulo de datos,
y no en el modelo: son **semilla**, no comportamiento.

Historia: estas constantes vivían en ``platform/models/company.py`` junto al
modelo ``Company`` paralelo que se disolvió. Ver
``analisis-extension-de-company-tres-motores``.
"""

# Código del tenant L1 insignia (PracticaYoruba). Análogo de ``base.main_company``:
# el primer L1 real, destino del backfill de las filas de dominio existentes.
# En prosa NO se le llama "founder" (ver ``terminologia-l0-company.md``); el
# nombre de la constante se conserva porque es el identificador real en uso.
FOUNDER_COMPANY_CODE = 'practicayoruba'

# Compañía de datos compartidos de la plataforma (``is_system=True``). Los datos
# globales (SEPOMEX, catálogos de referencia) cuelgan de aquí, con fallback por
# whitelist en el manager scopeado — NO ``company_id`` nullable.
SYSTEM_COMPANY_CODE = 'kaupamex_global'

# Valores L1 de contacto/newsletter/transaccional del tenant insignia, sembrados
# como sus propios ``CompanySetting``. Tal cual existían en
# ``config.settings.base`` antes de ser per-tenant: PracticaYoruba es L1, no L0,
# así que no estaban stale — estaban mal ubicados como ``default=`` global.
#
# ``notifications.from_email`` es el remitente no-reply transaccional **único**
# del tenant: bajo el diseño previo todo el correo transaccional salía de un
# solo ``DEFAULT_FROM_EMAIL``. Se conserva esa unicidad como una sola clave
# per-tenant, en vez de una clave por addon.
FOUNDER_L1_SETTINGS = {
    'contact.from_email': 'hola@practicayoruba.com',
    'contact.notify_email': 'hola@practicayoruba.com',
    'newsletter.from_email': 'newsletter@practicayoruba.com',
    'notifications.from_email': 'noreply@practicayoruba.com',
}
