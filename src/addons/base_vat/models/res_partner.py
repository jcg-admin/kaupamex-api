"""Extensión de ``res.partner`` — el análogo nativo de ``_inherit``.

La referencia valida el identificador fiscal EXTENDIENDO al partner
(``odoo19c: base_vat/models/res_partner.py``, ``_inherit = 'res.partner'``):
el ``vat`` vive en ``res.partner`` y la compañía lo lee por delegación
(``ResCompany.vat`` es property al partner). Aquí el addon engancha su
validador al campo del modelo del núcleo al importarse — mismo alcance que
``_inherit``: activo sólo con ``base_vat`` instalado.
"""
from addons.base.models import ResPartner
from addons.base_vat.validators import validate_rfc

_vat_field = ResPartner._meta.get_field('vat')
if validate_rfc not in _vat_field.validators:
    _vat_field.validators.append(validate_rfc)
