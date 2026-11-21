"""``product.document`` — un adjunto **publicable** de un producto.

Adaptación de ``odoo19c: addons/product/models/product_document.py``
(``odoo-tools@622ddc2aa5``, licencia ``LGPL-3`` declarada en
``addons/product/__manifest__.py``).

Un ``product.document`` **es** un ``ir.attachment`` más ``active`` y
``sequence``: la delegación es el ``_inherits`` del ORM, así que crear un
documento crea su adjunto y los campos del adjunto se leen y escriben desde
el documento, como en la fuente.

El vínculo con el producto es la referencia genérica ``res_model`` +
``res_id`` que el documento hereda del adjunto. ``res_model`` guarda la
etiqueta Django (``_meta.label``), convenio del árbol (``mail_thread.py``).
"""

import api
import fields
import models

from addons.base.models.ir_attachment import IrAttachment
from addons.base.models.timestamped_mixin import TimeStampedModel
from exceptions import ValidationError
from tools.translate import _


class ProductDocument(models.BaseModel, TimeStampedModel):
    """``product.document`` — adjunto de producto, ordenable y archivable."""

    _name = 'product.document'
    _description = "Product Document"
    _inherits = {
        'ir.attachment': 'ir_attachment_id',
    }
    _order = 'sequence, name'

    ir_attachment_id = fields.Many2one(
        IrAttachment,
        string="Related attachment",
        db_column='ir_attachment_id',
        null=False, on_delete=models.CASCADE,
        db_index=True,
        related_name='product_document_ids',
    )

    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    class Meta:
        db_table = 'product_document'
        # ``_order = 'sequence, name'``; ``name`` vive en el adjunto.
        ordering = ['sequence', 'ir_attachment_id__name']
        verbose_name = 'Documento de producto'
        verbose_name_plural = 'Documentos de producto'

    def __str__(self):
        return self.name or f'Documento {self.pk}'

    @classmethod
    def for_record(cls, record):
        """Los documentos activos de ``record``, en el orden de la fuente.

        Es el ``domain`` del ``One2many`` ``product_document_ids`` que la
        fuente declara en la plantilla y la variante
        (``odoo19c: product_template.py:164-168``,
        ``product_product.py:81-85``). Su porte como campo espera un
        ``One2many`` sobre ``Many2oneReference``: unidad sucesora
        ``product-document-ids-0397``.
        """
        if record.pk is None:
            return cls.objects.none()
        return cls.objects.filter(
            active=True,
            ir_attachment_id__res_model=type(record)._meta.label,
            ir_attachment_id__res_id=record.pk,
        )

    @api.onchange('url')
    def _onchange_url(self):
        for attachment in self:
            if attachment.type == 'url' and attachment.url and\
                    not attachment.url.startswith(
                        ('https://', 'http://', 'ftp://')):
                raise ValidationError(_(
                    "Please enter a valid URL.\nExample: "
                    "https://www.odoo.com\n\nInvalid URL: %s",
                    attachment.url
                ))

    # === CRUD METHODS === #

    @api.model_create_multi
    def create(self, vals_list):
        return super(
            ProductDocument,
            self.with_context(disable_product_documents_creation=True),
        ).create(vals_list)

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        ir_default = default
        if ir_default:
            ir_fields = list(self.env['ir.attachment']._fields)
            ir_default = {field: default[field] for field in default
                          if field in ir_fields}
        for document, vals in zip(self, vals_list):
            vals['ir_attachment_id'] = document.ir_attachment_id.with_context(
                no_document=True,
                disable_product_documents_creation=True,
            ).copy(ir_default).id
        return vals_list

    def unlink(self):
        attachments = self.ir_attachment_id
        res = super().unlink()
        return res and attachments.unlink()
