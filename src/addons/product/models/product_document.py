"""``product.document`` — un adjunto **publicable** de un producto.

Adaptación de ``odoo19c: addons/product/models/product_document.py``
(``odoo-tools@622ddc2aa5``, 60 líneas, licencia ``LGPL-3`` declarada en
``addons/product/__manifest__.py``).

Qué añade sobre un adjunto normal
=================================

Nada de contenido: un ``product.document`` **es** un ``ir.attachment`` más tres
cosas —``active``, ``sequence`` y su propio modelo—. Existe para poder tratar
"los documentos que acompañan a este producto" como una lista **ordenable y
archivable**, sin ensuciar la tabla general de adjuntos, donde conviven la
imagen de un correo y el PDF de una factura.

``_inherits`` otra vez, y la misma trampa
=========================================

La referencia declara ``_inherits = {'ir.attachment': 'ir_attachment_id'}``.
Igual que en ``product_product.py``, la traducción tentadora —herencia
multi-tabla de Django— **sería incorrecta**: aquella crea un
``OneToOneField(parent_link=True)`` y aquí el enlace es un ``Many2one``
declarado explícitamente (línea 16 de la fuente). Se porta como **FK real** más
delegación por propiedad de los campos del adjunto que este modelo usa.

La reversa **no** llega por ``related_name`` — el aviso que había era falso
=========================================================================

``product_product.py`` y ``product_template.py`` anotaban que
``product_document_ids`` *"aparece solo cuando product_document.py declare su
related_name, sin tocar éste"*. **Es falso, y este archivo lo prueba: no
declara ninguna FK a producto.** Medido en la fuente
(``odoo-tools@622ddc2aa5``):

- ``odoo19c: product_product.py:81-85`` y ``product_template.py:164-168``
  declaran ``product_document_ids`` como ``One2many`` con
  ``inverse_name='res_id'`` y ``domain=lambda self: [('res_model', '=',
  self._name)]``.

Es decir: el vínculo es la **referencia genérica** ``res_model``+``res_id`` que
el documento hereda del adjunto, no una clave foránea. Un ``related_name`` no
puede materializarla, porque no hay columna que apunte a producto. La reversa
se porta como **propiedad de consulta** en la ficha y en la variante, con el
mismo filtro que el ``domain`` de la fuente.

*Métrica:* declaraciones de ``product_document_ids = fields`` en
``odoo19c: addons/`` → 5, de las cuales 2 en ``product`` (ficha y variante) y 3
en ``sale_pdf_quote_builder`` (Many2many, otro addon).
*Ciega a:* una FK a producto declarada en un addon que **extienda**
``product.document`` sin tocar este archivo. No cambia la conclusión: el aviso
afirmaba que la reversa venía de *aquí*, y de aquí no viene.

``res_model`` guarda la etiqueta Django, no el ``_name`` de Odoo
================================================================

Convenio ya establecido en el árbol, no una decisión de este archivo:
``mail_thread.py:45-53`` lo enuncia —*"el identificador estable y único del
modelo es su label Django (``app_label.ModelName``)"*— y ``uom_uom.py:207-210``
ya consulta así (``model=cls._meta.label, res_id__in=ids``). Aquí se usa el
mismo ``_meta.label``, que es el equivalente exacto del ``self._name`` que la
fuente mete en su ``domain``.

Qué NO se porta, con su razón
=============================

- **``create`` con ``disable_product_documents_creation=True``.** Es una
  bandera del **contexto** del ORM de Odoo: evita que crear el documento
  dispare, a su vez, la creación automática de otro documento desde el adjunto.
  Django no tiene contexto de ORM propagable, y el bucle que la bandera corta
  tampoco existe aquí (no hay ese automatismo). Portarla sería copiar el
  parche de un problema que no tenemos.
- **``copy_data``.** Duplica el adjunto subyacente al duplicar el documento.
  Depende de la operación *copiar registro* del ORM de Odoo, que Django no
  tiene. Cuando se implemente una duplicación (en un serializer o un servicio),
  **debe** duplicar también el adjunto: si no, dos documentos compartirían
  fila de adjunto y borrar uno se llevaría el archivo del otro.
- **``@api.onchange``** como mecanismo: la validación de la URL sí se porta,
  al ``clean()``, que es donde el servidor la puede hacer cumplir. El
  ``onchange`` es reactividad de formulario.

El ``delete()`` va en la dirección que la FK no cubre
=====================================================

``ondelete='cascade'`` en el enlace da **adjunto → documento**: borrar el
adjunto se lleva el documento, y eso lo hace Django solo con
``on_delete=CASCADE``. Pero la fuente además define ``unlink()`` para el
sentido contrario —borrar el documento borra su adjunto— y **ese no lo da
ninguna FK**. Sin el ``delete()`` de abajo, cada documento borrado dejaría su
``ir.attachment`` huérfano, con el archivo ocupando disco y sin nada que lo
referencie.
"""
import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.ir_attachment import IrAttachment
from addons.base.models.timestamped_mixin import TimeStampedModel

#: Esquemas admitidos por ``_onchange_url``, verbatim de la fuente.
URL_SCHEMES = ('https://', 'http://', 'ftp://')

#: Valor de ``ir.attachment.type`` que exige que ``url`` esté poblada.
TYPE_URL = 'url'


class ProductDocument(TimeStampedModel):
    """``product.document`` — adjunto de producto, ordenable y archivable."""

    ir_attachment = fields.Many2one(
        IrAttachment, on_delete=models.CASCADE, db_index=True,
        related_name='product_document_ids',
        verbose_name='Adjunto relacionado',
        help_text='Odoo ir_attachment_id: el enlace de _inherits. FK real, NO '
                  'herencia multi-tabla (ver el docstring del módulo).',
    )
    active = fields.Boolean(
        default=True, verbose_name='Activo',
        help_text='Desmarcar archiva el documento sin borrar el adjunto.')
    sequence = fields.Integer(
        default=10, verbose_name='Secuencia',
        help_text='Orden de presentación dentro del producto.')

    class Meta:
        db_table = 'product_document'
        # ``_order = 'sequence, name'`` de la fuente; ``name`` vive en el
        # adjunto, así que se ordena atravesando el enlace.
        ordering = ['sequence', 'ir_attachment__name']
        verbose_name = 'Documento de producto'
        verbose_name_plural = 'Documentos de producto'

    def __str__(self):
        return self.name or f'Documento {self.pk}'

    # === DELEGACIÓN AL ADJUNTO (el ``_inherits`` de la fuente) =============

    @property
    def name(self):
        """El nombre del adjunto — lo que la fuente usa en su ``_order``."""
        return self.ir_attachment.name

    @property
    def type(self):
        """``binary`` o ``url`` (``ir_attachment.py``)."""
        return self.ir_attachment.type

    @property
    def url(self):
        """La URL, cuando ``type == 'url'``."""
        return self.ir_attachment.url

    @property
    def mimetype(self):
        """El tipo MIME del adjunto."""
        return self.ir_attachment.mimetype

    @property
    def res_model(self):
        """Etiqueta del modelo al que acompaña el documento.

        La mitad "modelo" de la referencia genérica que la fuente usa como
        ``inverse_name``/``domain``. Ver el docstring del módulo.
        """
        return self.ir_attachment.res_model

    @property
    def res_id(self):
        """Id del registro al que acompaña el documento."""
        return self.ir_attachment.res_id

    # === CONSULTA POLIMÓRFICA (lo que la fuente resuelve con ``domain``) ===

    @classmethod
    def for_record(cls, record):
        """Los documentos de ``record``, en el orden de la fuente.

        Equivale al ``One2many`` con ``inverse_name='res_id'`` y
        ``domain=[('res_model', '=', self._name)]`` que declaran
        ``odoo19c: product_product.py:81-85`` y ``product_template.py:164-168``.
        El ``_name`` de la fuente es aquí ``_meta.label`` — convenio del árbol,
        no de este archivo (``mail_thread.py:45-53``).

        Filtra los archivados, que es lo que hace el ``active`` de Odoo por
        defecto en cualquier lectura.
        """
        if record.pk is None:
            return cls.objects.none()
        return cls.objects.filter(
            active=True,
            ir_attachment__res_model=type(record)._meta.label,
            ir_attachment__res_id=record.pk,
        )

    # === INVARIANTES ======================================================

    def clean(self):
        """``_onchange_url`` — una URL de documento tiene que ser una URL.

        La fuente lo declara como ``onchange`` (reactividad de formulario) pero
        levanta ``ValidationError``, no un aviso: es una regla, no una
        sugerencia. Aquí vive en ``clean()``, que es donde el servidor la puede
        hacer cumplir venga de donde venga el dato.

        Sólo aplica a ``type == 'url'``: un adjunto binario no tiene URL que
        validar.
        """
        super().clean()
        if not self.ir_attachment_id:
            return
        attachment = self.ir_attachment
        if attachment.type == TYPE_URL and attachment.url and \
                not attachment.url.startswith(URL_SCHEMES):
            raise ValidationError(
                f'La URL del documento no es válida. Ejemplo: '
                f'https://www.example.com — recibido: {attachment.url}')

    # === BORRADO ==========================================================

    def delete(self, *args, **kwargs):
        """``unlink()`` — borrar el documento borra su adjunto.

        La FK cubre el sentido contrario (borrar el adjunto se lleva el
        documento, por ``on_delete=CASCADE``); **éste no lo da ninguna FK**.
        Sin él, cada documento borrado dejaría su ``ir.attachment`` huérfano
        con el archivo ocupando disco. Ver el docstring del módulo.

        El orden es el de la fuente: primero el documento, después el adjunto.
        """
        attachment = self.ir_attachment if self.ir_attachment_id else None
        result = super().delete(*args, **kwargs)
        if attachment is not None:
            attachment.delete()
        return result
