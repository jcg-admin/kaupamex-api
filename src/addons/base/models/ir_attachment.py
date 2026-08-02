"""``ir.attachment`` — adjuntos de archivo/URL (Odoo ``base``).

Portación fiel de ``IrAttachment``
(``scratchpad/odoo19x/odoo/addons/base/models/ir_attachment.py:61-985``, Odoo
19; ``scratchpad/odoo18/extracted/odoo/addons/base/models/ir_attachment.py:32-``
para 18) — la **estructura de control** que vincula binarios o URLs a
cualquier registro del proyecto de forma polimórfica (``res_model``+``res_id``
como campos planos Char+Integer, sin ``GenericForeignKey`` — igual que Odoo,
que tampoco usa una FK real ahí; el vínculo se resuelve en la capa de negocio,
no en el ORM). Parte de la iniciativa
``adaptar-familias-odoo-monolito-modular`` (SOL-096), backlog de control
núcleo ``ir.*`` (H-BASE-01 C-2).

Drift 18→19 observado (ambas fuentes citadas arriba): el set de campos de la
definición del modelo (``name``, ``description``, ``res_model``, ``res_field``,
``res_id``, ``company_id``, ``type``, ``url``, ``public``, ``access_token``,
``store_fname``, ``file_size``, ``checksum``, ``mimetype``) es **idéntico**
línea por línea entre 18 y 19 (Odoo 18 líneas 410-435; Odoo 19 líneas
453-478) — ningún campo se agregó/removió/renombró. La única diferencia de
fondo entre versiones es de infraestructura interna (Odoo 19 migra de
``odoo.osv.expression`` a ``odoo.fields.Domain`` para las ACL de ``_search``,
y agrega ``_check_access``/``check_access`` en vez del ``check()`` legado) —
irrelevante aquí porque esa capa de ACL no se porta (ver abajo).

Alcance de la portación — deliberadamente NO se porta:

- **El filestore propio de Odoo** (``_file_read``/``_file_write``/
  ``_file_delete``/``_gc_file_store``, sharding sha1 en 256 subdirectorios,
  checklist de garbage collection). Django ya resuelve un storage backend-
  agnóstico con ``FileField`` (local o S3 vía ``django-storages``);
  reimplementar el filestore completo de Odoo duplicaría infraestructura que
  Django ya da. Por eso ``datas`` es un ``FileField`` directo — no el split
  Odoo ``raw``(compute)/``db_datas``(Binary)/``store_fname`` con
  ``_get_path``/sha1-sharding. ``store_fname`` se preserva como campo fiel al
  nombre Odoo, pero aquí solo refleja el nombre asignado por el storage
  backend de Django (ver ``save()``), no una ruta sha1 propia. Ver hallazgo
  H-BASE candidato (reportado por el orquestador — filestore-GC no portado).
- **ACL de attachments** (``_check_access``, override de ``_search`` con
  ``SECURITY_FIELDS``, tokens de acceso por campo). Pertenece a la capa de
  permisos (DRF ``HasCapability``, DEC-11), no al modelo de control. Fuera de
  este slice.
- **Compute fields de solo-UI** (``res_name`` vía ``display_name`` del
  registro referenciado, ``index_content`` full-text — Enterprise en Odoo).
- **Redimensionado de imágenes** (``_postprocess_contents``,
  ``image.ImageProcess``) — pertenece a la capa de negocio que sube el
  archivo, no al modelo de control.

Comportamiento SÍ portado (adaptado al mecanismo Django, no a los decoradores
``@api`` de Odoo): cómputo de ``file_size``+``checksum`` (sha1 del contenido)
al guardar cuando hay ``datas`` — equivalente simplificado de
``_get_datas_related_values``/``_compute_checksum`` de Odoo.

Cross-app: ``company`` → ``company.Company`` (Odoo ``company_id``,
DEC-SALE-01 — FK cross-app en vez de tenant scope implícito).
"""
import hashlib

import fields
import models


class IrAttachment(models.Model):
    """``ir.attachment`` — adjunto (archivo o URL) vinculado a un registro."""

    TYPE_BINARY = 'binary'
    TYPE_URL = 'url'
    TYPE_CHOICES = [
        (TYPE_BINARY, 'File'),
        (TYPE_URL, 'URL'),
    ]

    name = fields.Char(max_length=256, help_text='Nombre del adjunto (Odoo name).')
    description = fields.Text(blank=True, default='', help_text='Odoo description.')
    res_model = fields.Char(
        max_length=128, blank=True, default='',
        help_text=(
            'Modelo polimórfico referenciado, p. ej. "product.ProductProduct" '
            '(Odoo res_model). NO es una FK — vínculo plano igual que Odoo.'
        ),
    )
    res_field = fields.Char(
        max_length=128, blank=True, default='',
        help_text='Campo binary del modelo referenciado, si aplica (Odoo res_field).',
    )
    res_id = fields.Integer(
        null=True, blank=True,
        help_text=(
            'ID del registro referenciado (Odoo res_id / Many2oneReference '
            'simplificado a Integer plano — el ORM shim del proyecto no '
            'tiene un tipo Many2oneReference fiel; Odoo tampoco lo trata '
            'como FK real).'
        ),
    )
    type = fields.Selection(
        max_length=8, choices=TYPE_CHOICES, default=TYPE_BINARY,
        help_text='Odoo type: binary (archivo) o url (enlace externo).',
    )
    url = fields.Char(max_length=1024, blank=True, default='', help_text='Odoo url.')
    public = fields.Boolean(default=False, help_text='Odoo public — accesible sin auth.')
    access_token = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Token de acceso externo (Odoo access_token).',
    )
    mimetype = fields.Char(max_length=128, blank=True, default='', help_text='Odoo mimetype.')
    file_size = fields.Integer(default=0, help_text='Tamaño en bytes (Odoo file_size).')
    checksum = fields.Char(
        max_length=40, blank=True, default='',
        help_text='SHA1 del contenido (Odoo checksum, calculado en save()).',
    )
    store_fname = fields.Char(
        max_length=256, blank=True, default='',
        help_text=(
            'Nombre asignado por el storage backend de Django (Odoo '
            'store_fname — aquí no es una ruta sha1-sharded propia, ver '
            'docstring del módulo).'
        ),
    )
    datas = models.FileField(
        upload_to='attachments/%Y/%m/', null=True, blank=True,
        help_text=(
            'Contenido binario (Odoo datas/raw) — FileField de Django, no '
            'el filestore propio de Odoo (ver docstring del módulo).'
        ),
    )
    company = fields.Many2one(
        'company.Company', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='attachments', help_text='Empresa (Odoo company_id).',
    )

    class Meta:
        db_table = 'ir_attachment'
        ordering = ['-id']
        verbose_name = 'Adjunto'
        verbose_name_plural = 'Adjuntos'
        indexes = [
            models.Index(fields=['res_model', 'res_id'], name='ir_attachment_res_idx'),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        """Calcula ``file_size``/``checksum`` cuando hay contenido — versión
        simplificada de ``_get_datas_related_values``/``_compute_checksum``
        de Odoo (sin el sharding sha1 propio del filestore; Django ``FileField``
        ya resuelve dónde vive el archivo)."""
        if self.datas:
            content = self.datas.read()
            self.datas.seek(0)
            self.file_size = len(content)
            self.checksum = hashlib.sha1(content).hexdigest()
            if not self.mimetype:
                self.mimetype = 'application/octet-stream'
        super().save(*args, **kwargs)
        if self.datas and self.datas.name and self.store_fname != self.datas.name:
            self.store_fname = self.datas.name
            type(self).objects.filter(pk=self.pk).update(store_fname=self.store_fname)
