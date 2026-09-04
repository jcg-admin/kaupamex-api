"""``account.add.gln`` — Global Location Number del partner.

Adaptación de ``odoo19c: addons/account_add_gln/models/res_partner.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 — atribución
y aviso de licencia preservados, DEC-KX-03).

La referencia extiende ``res.partner`` con ``_inherit`` y declara un único
campo::

    global_location_number = fields.Char(string="GLN", help="Global Location
    Number")

Es el único símbolo del archivo — sin métodos, sin computados — y se porta
íntegro. Django no permite inyectar una columna en un modelo de OTRO addon
sin migrar la app dueña de la tabla (``res.partner`` vive en ``base`` en
este árbol); se modela como RELATED OneToOne, el mismo criterio que
``base_address_extended`` ya fijó para el mismo problema (DEC-SALE-01):
``PartnerGln`` cuelga de ``res.partner`` sin tocar la tabla de ``base`` ni su
migración.

El GLN es un identificador GS1 de trece dígitos (sin dígito verificador
propio distinto del EAN-13 estándar); la referencia no impone longitud al
campo (``Char`` sin ``size``), así que aquí se mapea a ``max_length=255``,
el mismo criterio ya usado en ``base.ResPartner.website`` para un ``Char``
de la referencia sin tamaño declarado.
"""
import fields
import models


class PartnerGln(models.Model):
    """GLN de un ``res.partner`` — ≙ ``res.partner.global_location_number``.

    Usado principalmente en direcciones de entrega (``partner.type ==
    'delivery'``) para identificar la ubicación de stock ante eInvoices
    UBL/CII (mismo uso que documenta el ``summary`` del manifiesto de la
    referencia).
    """
    _inherit = 'res.partner'

    partner = models.OneToOneField(
        'base.ResPartner', on_delete=models.CASCADE, related_name='gln',
        help_text='Partner al que pertenece (Odoo _inherit res.partner).',
    )
    global_location_number = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='GLN',
        help_text='Global Location Number (Odoo global_location_number).',
    )

    class Meta:
        db_table = 'res_partner_gln'
        verbose_name = 'GLN del partner'
        verbose_name_plural = 'GLN de partners'

    def __str__(self) -> str:
        return self.global_location_number or f'GLN de {self.partner_id}'
