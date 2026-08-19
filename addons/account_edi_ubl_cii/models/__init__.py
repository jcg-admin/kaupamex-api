"""Modelos del addon ``account_edi_ubl_cii`` (estructura Odoo: un archivo por modelo).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/__init__.py``
(``odoo-tools@622ddc2a``, LGPL-3, 19 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

**Este addon no declara ningún modelo Django concreto.** Los catorce
constructores UBL/CII son ``AbstractModel`` en la referencia y aquí son clases
Python planas (ver ``account_edi_common.py``), así que no hay tabla que migrar;
todo lo que sí toca la base de datos son **campos colgados sobre modelos de
otros addons** (``account.tax``, ``account.move``, ``res.partner``), y eso lo
aplica ``AccountEdiUblCiiConfig.ready()``.

Se importan aquí los **catorce constructores**, en el orden de dependencia de
la referencia (que es también el orden en que las bases tienen que existir para
que la herencia de Python resuelva): cada uno declara su clase al importarse.

Los **cinco archivos de extensión** (``account_move``, ``account_move_send``,
``account_tax``, ``ir_actions_report``, ``res_partner``) **no** se importan
aquí: se cargan desde ``ready()``, cuando el registro de modelos ya está
poblado — mismo criterio que ``account_edi/models/__init__.py``.
"""
from .account_edi_common import AccountEdiCommon
from .account_edi_ubl import AccountEdiUBL
from .account_edi_ubl_cen_en16931 import AccountEdiUBLCenEn16931
from .account_edi_ubl_pint import AccountEdiUBLPint
from .account_edi_ubl_pint_eu import AccountEdiUBLPintEU
from .account_edi_xml_cii_facturx import AccountEdiXmlCii
from .account_edi_xml_ubl_20 import AccountEdiXmlUBL20
from .account_edi_xml_ubl_21 import AccountEdiXmlUbl_21
from .account_edi_xml_ubl_bis3 import AccountEdiXmlUBLBIS3
from .account_edi_xml_ubl_xrechnung import AccountEdiXmlUbl_De
from .account_edi_xml_ubl_nlcius import AccountEdiXmlUbl_Nl
from .account_edi_xml_ubl_efff import AccountEdiXmlUbl_Efff
from .account_edi_xml_ubl_a_nz import AccountEdiXmlUbl_A_Nz
from .account_edi_xml_ubl_sg import AccountEdiXmlUbl_Sg

__all__ = [
    'AccountEdiCommon',
    'AccountEdiUBL',
    'AccountEdiUBLCenEn16931',
    'AccountEdiUBLPint',
    'AccountEdiUBLPintEU',
    'AccountEdiXmlCii',
    'AccountEdiXmlUBL20',
    'AccountEdiXmlUbl_21',
    'AccountEdiXmlUBLBIS3',
    'AccountEdiXmlUbl_De',
    'AccountEdiXmlUbl_Nl',
    'AccountEdiXmlUbl_Efff',
    'AccountEdiXmlUbl_A_Nz',
    'AccountEdiXmlUbl_Sg',
]
