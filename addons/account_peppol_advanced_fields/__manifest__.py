# Adaptado de Odoo `account_peppol_advanced_fields/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
#
# El nombre y el summary van VERBATIM de la fuente, marca [DEPRECATED]
# incluida: es la propia referencia la que declara este addon como
# prematuramente mergeado. Ver `__init__.py` para por qué se porta igual.
{
    'name': '[DEPRECATED] Account Peppol Advanced Fields',
    'summary': (
        "Merged prematurly, not working correctly. Please don't use. "
        'Better solution coming soon.'
    ),
    'author': 'Odoo S.A.',
    'category': 'Accounting/Accounting',
    'version': '1.0',
    # `depends` MEDIDO contra los imports reales de este addon:
    # - account → AccountMove, destino de la extensión (import de Python).
    #
    # DIVERGE de la referencia, que declara ['account', 'account_edi_ubl_cii']:
    # ese segundo addon se está portando en otro pase, en paralelo, Y este
    # addon NO lo necesita — sus siete campos son Char planos; medido, el único
    # archivo de modelo de la referencia importa sólo `fields` y `models`
    # (odoo19c: .../models/account_move.py:1). La dependencia existe allá
    # porque el generador UBL de ese addon los CONSUME, no porque éste lo
    # importe. Consecuencia declarada: los campos existen y no alimentan
    # ningún XML hasta que ese addon aterrice.
    'depends': ['account'],
    # `data` (1 XML: la pestaña del formulario con los siete campos) no se
    # porta: cliente web de Odoo.
    'installable': True,
    'application': False,
    'auto_install': False,
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1).
    'license': 'LGPL-3',
}
