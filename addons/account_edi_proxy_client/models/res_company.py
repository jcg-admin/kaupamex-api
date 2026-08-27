r"""``res.company`` — lo que ``account_edi_proxy_client`` le cuelga
(≙ ``_inherit``).

Adaptación de ``odoo19c: account_edi_proxy_client/models/res_company.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 9 líneas)
— atribución y aviso de licencia preservados (DEC-KX-03).

Un símbolo — automático, sin código que colgar
====================================================

``account_edi_proxy_client_ids`` (``fields.One2many('account_edi_proxy_
client.user', inverse_name='company_id', ...)``) es el lado O2M inverso del
M2O real, que vive en ``account_edi_proxy_client.user.company`` (``account_
edi_proxy_user.py``, este mismo addon). En Django el M2O ES el que se
declara, con ``related_name='account_edi_proxy_client_ids'`` — Django crea
el accesor inverso en ``base.ResCompany`` **sin tocar**
``src/addons/base/models/res_company.py`` (fuera del write-set de este
agente).

Este archivo existe por la misma razón que ``account/models/ir_attachment.
py::apply_account_extensions`` existe vacío: la referencia tiene el archivo
(el "SITIO se lee contra la referencia",
``atributos-de-clase-de-modelo.md``), aunque aquí no haya ningún ``setattr``
que aplicar.

**No portado** — el ``context={'active_test': True}`` de la referencia: es
un modificador de la capa de búsqueda de Odoo (incluye registros inactivos
por defecto en ese O2M concreto); el manager reverso de Django no tiene un
concepto de contexto de búsqueda por-campo. Quien necesite incluir usuarios
inactivos filtra explícito: ``company.account_edi_proxy_client_ids.filter()``
sin excluir ``active=False`` es ya el comportamiento por defecto de Django
(a diferencia de Odoo, que excluye inactivos salvo que se pida lo contrario)
— la divergencia es la opuesta a la que la referencia declara, y por eso se
señala en vez de callarse.
"""


def apply_account_edi_proxy_client_extensions():
    """No aplica — ver el docstring del módulo. Se define por uniformidad
    con ``AccountEdiProxyClientConfig.ready()``."""
    return None
