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
import base64
import hashlib
import mimetypes
import uuid

from django.apps import apps

import fields
import models
from exceptions import ValidationError


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
        'base.ResCompany', on_delete=models.SET_NULL, null=True, blank=True,
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

    def clean(self):
        """``_check_circular_attachment`` — un adjunto no se adjunta a si mismo.

        Su mensaje de la fuente, verbatim: *"You cannot attach an attachment to
        itself"*. Prohibe el **bucle**, no la relacion: un adjunto de OTRO
        adjunto es legitimo y se conserva.
        """
        super().clean()
        if self.res_model == 'ir.attachment' and self.pk and \
                self.res_id == self.pk:
            raise ValidationError(
                'No se puede adjuntar un adjunto a si mismo. '
                f'El adjunto {self.pk} no puede tener res_id: {self.res_id}.')

    @staticmethod
    def _compute_mimetype(values):
        """≙ ``_compute_mimetype`` — el tipo, del valor dado o adivinado.

        Su docstring de la fuente, verbatim: *"compute the mimetype of the
        given values … :return mime : string indicating the mimetype, or
        application/octet-stream by default"*.

        El orden de la fuente se conserva y es el que importa: el valor
        explicito, el nombre, la **url sin su cadena de consulta**, y por
        ultimo el contenido. Sale siempre en minusculas.
        """
        mimetype = values.get('mimetype')
        if not mimetype and values.get('name'):
            mimetype = mimetypes.guess_type(values['name'])[0]
        if not mimetype and values.get('url'):
            mimetype = mimetypes.guess_type(values['url'].split('?')[0])[0]
        if not mimetype or mimetype == 'application/octet-stream':
            raw = values.get('raw')
            if raw is None and values.get('datas'):
                raw = base64.b64decode(values['datas'])
            if raw:
                # DIVERGENCIA DE MECANISMO: la fuente adivina por los magic
                # bytes con su `guess_mimetype`. Aqui no hay equivalente en la
                # biblioteca estandar, asi que se conserva lo adivinado por
                # nombre o url y no se inventa un detector propio. Lo que NO
                # cambia es el desenlace por defecto.
                mimetype = mimetype or None
        return (mimetype or 'application/octet-stream').lower()

    @staticmethod
    def _can_write_views(user):
        """¿El usuario puede escribir vistas? — ≙ ``ir.ui.view.has_access('write')``.

        Es la condicion de permiso de ``_check_contents``, derivada de la ACL
        que este arbol **si** tiene portada: ``ir.model.access``, con su
        ``perm_write`` por modelo y grupo.

        Dos casos, los dos de la fuente: una ACL **sin grupo** abre el modo a
        todos (``has_global_access``), y una con grupo lo abre a quien
        pertenezca a el —incluidos los grupos implicados, que es lo que
        ``_get_group_ids`` devuelve—.

        Sin usuario responde ``False``. No es un caso raro: es el de una
        creacion sin peticion detras, y ahi degradar es lo correcto.
        """
        if user is None or getattr(user, 'pk', None) is None:
            return False
        IrModelAccess = apps.get_model('base', 'IrModelAccess')
        if IrModelAccess.has_global_access('ir.ui.view', 'write'):
            return True
        return IrModelAccess.objects.filter(
            model_id__model='ir.ui.view', active=True, perm_write=True,
            group_id__in=user._get_group_ids()).exists()

    @classmethod
    def _check_contents(cls, values, user=None, trusted=False):
        """≙ ``_check_contents`` — degrada a texto lo que puede ejecutarse.

        La fuente convierte a ``text/plain`` todo lo que huela a HTML o XML
        —``ht`` en el mimetype, o ``xml`` **sin** ser un formato Office— cuando
        quien sube **no** puede escribir vistas. No es una comprobacion de
        formato: es la que evita el XSS almacenado. Un ``.svg`` con un
        ``<script>`` dentro, servido de vuelta con su propio mimetype, se
        ejecuta en el navegador de quien lo abra y en el origen del producto.

        La excepcion de Office la fija la fuente por nombre
        (``application/vnd.openxmlformats``) y se conserva: un ``.docx`` lleva
        ``xml`` en su mimetype y no se degrada.

        **La condicion de permiso SI se porta, contra la ACL.** Alla es
        ``not self.env['ir.ui.view'].sudo(False).has_access('write')``. Este
        arbol tiene ``ir.model.access`` portada —como **dato**, porque el gate
        efectivo del producto es ``HasCapability`` (DEC-11)— y consultarla es
        exactamente lo que hace la fuente: ¿tiene este usuario permiso de
        escritura sobre ``ir.ui.view``, por una ACL global o por una de sus
        grupos? Eso lo responde :meth:`_can_write_views`.

        Dos vias, y las dos hacen falta:

        - ``user`` — la fiel. Se deriva de la ACL, como la fuente.
        - ``trusted`` — el atajo para el llamador que **ya** resolvio la
          autorizacion en la capa DRF y no quiere que el modelo la repita.

        Sin ninguna de las dos se degrada: fail-closed, como la propia
        ``HasCapability``, para que olvidarse del argumento degrade de mas y
        nunca de menos.
        """
        values = dict(values)
        trusted = trusted or cls._can_write_views(user)
        mimetype = values['mimetype'] = cls._compute_mimetype(values)
        xml_like = 'ht' in mimetype or (
            'xml' in mimetype
            and not mimetype.startswith('application/vnd.openxmlformats'))
        if xml_like and not trusted:
            values['mimetype'] = 'text/plain'
        return values

    @staticmethod
    def _generate_access_token():
        """≙ ``_generate_access_token`` — un uuid4 en su forma canonica."""
        return str(uuid.uuid4())

    def generate_access_token(self):
        """≙ ``generate_access_token`` — devuelve el token, creandolo si falta.

        La fuente devuelve el que ya hay cuando lo hay, y esa es la mitad que
        importa: un token que cambia en cada llamada invalida los enlaces ya
        repartidos.

        **Divergencia de forma:** alla opera sobre un conjunto y devuelve una
        lista; aqui ``self`` es una instancia y devuelve **su** token.
        """
        if not self.access_token:
            self.access_token = self._generate_access_token()
            type(self).objects.filter(pk=self.pk).update(
                access_token=self.access_token)
        return self.access_token

    def save(self, *args, user=None, trusted=False, **kwargs):
        """Calcula ``file_size``/``checksum`` cuando hay contenido — versión
        simplificada de ``_get_datas_related_values``/``_compute_checksum``
        de Odoo (sin el sharding sha1 propio del filestore; Django ``FileField``
        ya resuelve dónde vive el archivo).

        Y **aquí se cablea** ``_check_contents``: la fuente lo llama desde su
        ``create`` y su ``write``, que son los dos únicos caminos por los que
        un adjunto llega a la base. Sin ese cableado la degradación existiría
        y no protegería a nadie — el defecto que :ref:`h-api-836` acaba de
        registrar en otro modelo del mismo addon.

        ``trusted`` viaja hasta ``_check_contents`` y su valor por defecto es
        falso: quien tenga permiso para subir HTML lo declara, y quien se
        olvide degrada de más.
        """
        if self.datas:
            content = self.datas.read()
            self.datas.seek(0)
            self.file_size = len(content)
            self.checksum = hashlib.sha1(content).hexdigest()
        self.mimetype = self._check_contents(
            {'mimetype': self.mimetype, 'name': self.name, 'url': self.url},
            user=user, trusted=trusted)['mimetype']
        super().save(*args, **kwargs)
        if self.datas and self.datas.name and self.store_fname != self.datas.name:
            self.store_fname = self.datas.name
            type(self).objects.filter(pk=self.pk).update(store_fname=self.store_fname)
