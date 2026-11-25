"""``ir.attachment`` — adjuntos de archivo/URL (Odoo ``base``).

Portación fiel de ``IrAttachment``
(``scratchpad/odoo19x/odoo/addons/base/models/ir_attachment.py:61-985``, Odoo
19;
``scratchpad/odoo18/extracted/odoo/addons/base/models/ir_attachment.py:32-``
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
453-478) — ningún campo se agregó/retiró/renombró. La única diferencia de
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
  Odoo ``db_datas``(Binary)/``store_fname`` con ``_get_path``/sha1-sharding.
  ``raw`` sí se porta, como compute e inverso sobre ``datas`` (ver el campo).
  ``store_fname`` se preserva como campo fiel al
  nombre Odoo, pero aquí solo refleja el nombre asignado por el storage
  backend de Django (ver ``save()``), no una ruta sha1 propia. Ver hallazgo
  H-BASE candidato (reportado por el orquestador — filestore-GC no portado).
- **ACL por registro de attachments** (``_check_access``, override de
  ``_search`` con ``SECURITY_FIELDS``, tokens de acceso por campo;
  ``odoo19c: :504-620``). Desde que el modelo deriva de ``BaseModel`` su
  recordset ya comprueba la ACL de modelo (las dos filas del CSV, sembradas
  por ``0095``); lo que falta es la de registro, que hereda el acceso del
  registro adjuntado. **Pendiente**, con sucesor en la unidad
  ``attachment-record-access`` del plan de continuación (TASK-API-0397). Hasta
  que se porte, el recordset sólo lo usa ``tools.xml_utils``, y la superficie
  HTTP sigue gobernada por ``HasCapability`` (DEC-11).
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
import warnings
from collections import defaultdict

from django.apps import apps
from django.core.files.base import ContentFile

import fields
import models
from exceptions import AccessError, MissingError, ValidationError
from orm.domains import Domain
from orm.environments import env
from orm.models import AccessQuerySet, BaseModel
from tools.constants import PREFETCH_MAX
from tools.mimetypes import guess_mimetype
from tools.misc import OrderedSet
from tools.translate import _

#: ≙ ``SECURITY_FIELDS`` (``odoo19c: ir_attachment.py:42``).
SECURITY_FIELDS = ('res_model', 'res_id', 'create_uid', 'public', 'res_field')


def condition_values(model, field_name, domain):
    """Get the values in the domain for a specific field name.

    Returns the values appearing in the `in` conditions that would be
    restricted to by the domain.

    ≙ ``condition_values`` (``odoo19c: ir_attachment.py:45-58``), verbatim.
    """
    domain = domain.optimize(model)
    for condition in domain.map_conditions(
        lambda cond: cond
        if cond.field_expr == field_name and cond.operator == 'in'
        else Domain.TRUE
    ).optimize(model).iter_conditions():
        return condition.value
    return None


def _accessible_ids(comodel, res_ids, operation, user):
    """Los ids de ``res_ids`` que ``user`` puede ``operation`` en un
    comodelo de Django sin ``BaseModel``.

    Divergencia de mecanismo, declarada: la fuente hace
    ``records._filtered_access(operation)`` sobre el recordset del comodelo;
    un modelo de Django no tiene recordset, y la misma evaluación (ACL del
    modelo y reglas de fila) la hace su :class:`AccessQuerySet`, como en
    ``BaseModel._check_access``.
    """
    rows = AccessQuerySet(model=comodel).filter(pk__in=list(res_ids))
    result = rows._check_access(operation, user=user)
    present = set(rows.values_list('pk', flat=True))
    if result is None:
        return present
    return present - set(result[0].values_list('pk', flat=True))


class IrAttachment(BaseModel):
    """``ir.attachment`` — adjunto (archivo o URL) vinculado a un registro.

    Deriva de :class:`~orm.models.BaseModel`, como manda :ref:`h-api-1083`
    para los modelos portados: ``env['ir.attachment']`` es un recordset con
    ``search``, ``browse``, ``|`` y ``mapped``, que es el protocolo con que
    ``tools.xml_utils`` lo consulta (``odoo19c: odoo/tools/xml_utils.py``).
    ``RecordLoaderMixin`` aporta ``_check_field_access`` y la carga de
    campos, la misma adopción que ``res_bank`` y ``ir_cron``; no se hereda
    ``TimeStampedModel`` porque añadiría dos columnas que la tabla no tiene.
    """

    # Atributos de clase de la fuente (``odoo19c: odoo/addons/base/models/
    # ir_attachment.py:75-77``). ``_res_idx`` vive en ``Meta.indexes`` con su
    # nombre. Sin ``_name``, ``env['ir.attachment']`` no resolvía.
    _name = 'ir.attachment'
    _description = 'Attachment'
    _order = 'id desc'

    TYPE_BINARY = 'binary'
    TYPE_URL = 'url'
    TYPE_CHOICES = [
        (TYPE_BINARY, 'File'),
        (TYPE_URL, 'URL'),
    ]

    name = fields.Char(
        max_length=256, help_text='Nombre del adjunto (Odoo name).'
    )
    description = fields.Text(
        blank=True, default='', help_text='Odoo description.'
    )
    res_model = fields.Char(
        max_length=128,
        blank=True,
        default='',
        help_text=(
            'Modelo polimórfico referenciado, p. ej. "product.ProductProduct" '
            '(Odoo res_model). NO es una FK — vínculo plano igual que Odoo.'
        ),
    )
    res_field = fields.Char(
        max_length=128,
        blank=True,
        default='',
        help_text=(
            'Campo binary del modelo referenciado, si aplica (Odoo res_field).'
        ),
    )
    res_id = fields.Many2oneReference(
        model_field='res_model',
        null=True,
        blank=True,
        help_text='ID del registro referenciado (Odoo res_id).',
    )
    type = fields.Selection(
        max_length=8,
        choices=TYPE_CHOICES,
        default=TYPE_BINARY,
        help_text='Odoo type: binary (archivo) o url (enlace externo).',
    )
    url = fields.Char(
        max_length=1024, blank=True, default='', help_text='Odoo url.'
    )
    public = fields.Boolean(
        default=False, help_text='Odoo public — accesible sin auth.'
    )
    access_token = fields.Char(
        max_length=64,
        blank=True,
        default='',
        help_text='Token de acceso externo (Odoo access_token).',
    )
    mimetype = fields.Char(
        max_length=128, blank=True, default='', help_text='Odoo mimetype.'
    )
    file_size = fields.Integer(
        default=0, help_text='Tamaño en bytes (Odoo file_size).'
    )
    checksum = fields.Char(
        max_length=40,
        blank=True,
        default='',
        help_text='SHA1 del contenido (Odoo checksum, calculado en save()).',
    )
    store_fname = fields.Char(
        max_length=256,
        blank=True,
        default='',
        help_text=(
            'Nombre asignado por el storage backend de Django (Odoo '
            'store_fname — aquí no es una ruta sha1-sharded propia, ver '
            'docstring del módulo).'
        ),
    )
    datas = models.FileField(
        upload_to='attachments/%Y/%m/',
        null=True,
        blank=True,
        help_text=(
            'Contenido binario (Odoo datas/raw) — FileField de Django, no '
            'el filestore propio de Odoo (ver docstring del módulo).'
        ),
    )
    #: ≙ ``raw`` (``odoo19c: odoo/addons/base/models/ir_attachment.py:471``):
    #: ``fields.Binary(compute='_compute_raw', inverse='_inverse_raw')``,
    #: sin columna. Lee y escribe el contenido de :attr:`datas`, que aquí es
    #: el ``FileField`` donde vive el archivo.
    raw = fields.Binary(compute='_compute_raw', inverse='_inverse_raw')
    company = fields.Many2one(
        'base.ResCompany',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attachments',
        help_text='Empresa (Odoo company_id).',
    )

    class Meta:
        db_table = 'ir_attachment'
        ordering = ['-id']
        verbose_name = 'Adjunto'
        verbose_name_plural = 'Adjuntos'
        indexes = [
            models.Index(
                fields=['res_model', 'res_id'], name='ir_attachment_res_idx'
            ),
        ]

    def _compute_raw(self):
        """≙ ``_compute_raw`` (``:266-271``): el contenido almacenado.

        La fuente lo lee del filestore o de ``db_datas``; aquí hay un solo
        sitio, el archivo de :attr:`datas`.
        """
        for attach in self:
            if attach.datas:
                content = attach.datas.read()
                attach.datas.seek(0)
                attach.raw = content
            else:
                attach.raw = False

    def _inverse_raw(self):
        """≙ ``_inverse_raw`` (``:281-282``): guardar ``raw`` como archivo.

        ``_set_attachment_data`` de la fuente calcula tamaño, checksum y
        tipo, y valida el contenido; aquí eso lo hace :meth:`save` cuando
        cambia ``datas``, así que el inverso sólo deposita el archivo.
        """
        for attach in self:
            content = attach.raw or b''
            attach.datas = ContentFile(content, name=attach.name or 'raw')
            attach.mimetype = ''
            attach.save(update_fields=['datas', 'mimetype', 'file_size',
                                       'checksum'])

    def __str__(self) -> str:
        return self.name

    def clean(self):
        """
        ``_check_circular_attachment`` — un adjunto no se adjunta a si mismo.

        Su mensaje de la fuente, verbatim: *"You cannot attach an attachment to
        itself"*. Prohibe el **bucle**, no la relacion: un adjunto de OTRO
        adjunto es legitimo y se conserva.
        """
        super().clean()
        if (
            self.res_model == 'ir.attachment'
            and self.pk
            and self.res_id == self.pk
        ):
            raise ValidationError(
                'No se puede adjuntar un adjunto a si mismo. '
                f'El adjunto {self.pk} no puede tener res_id: {self.res_id}.'
            )

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
                # El contenido decide por su firma (``guess_mimetype``), como
                # en la fuente. Aqui decia que no habia equivalente en la
                # biblioteca estandar, y la fuente trae el suyo:
                # ``_odoo_guess_mimetype``, portado en ``tools.mimetypes``.
                mimetype = guess_mimetype(raw)
        return (mimetype or 'application/octet-stream').lower()

    @staticmethod
    def _can_write_views(user):
        """
        ¿El usuario puede escribir vistas? — ≙
        ``ir.ui.view.has_access('write')``.

        Es la condicion de permiso de ``_check_contents``, y desde la tarea #93
        la responde el resolvedor de la ACL, no una consulta escrita aqui:
        ``IrModelAccess.check('ir.ui.view', 'write')``, que es literalmente lo
        que la fuente pregunta.

        **Por que cambio, y es un defecto medido.** La primera version armaba
        la
        consulta a mano y filtraba ``model_id__model='ir.ui.view'`` — el nombre
        punteado de la fuente. Este arbol guarda el **label de Django** en
        ``ir_model.model``, asi que ese filtro no podia coincidir **nunca**, ni
        con la tabla poblada. Y la tabla ademas estaba vacia: ningun sembrador
        la escribia. Dos capas de lo mismo — una guarda que consulta un almacen
        que no puede responderle, y cuyo ``False`` constante se lee igual que
        una denegacion legitima. Ver :ref:`h-api-839`.

        Ahora la respuesta es la de la semilla, que copia el CSV de la
        referencia: escribir vistas es de ``group_system`` y de nadie mas
        (``ir.model.access.csv:35-36``).

        Sin usuario responde ``False``. No es un caso raro: es el de una
        creacion sin peticion detras, y ahi degradar es lo correcto — el
        resolvedor lo da solo, porque sin usuario no hay grupos y la unica ACL
        de ``ir.ui.view`` con ``perm_write`` es la de grupo.
        """
        if user is None or getattr(user, 'pk', None) is None:
            return False
        IrModelAccess = apps.get_model('base', 'IrModelAccess')
        return IrModelAccess.check(
            'ir.ui.view', 'write', raise_exception=False, user=user
        )

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
            and not mimetype.startswith('application/vnd.openxmlformats')
        )
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
            # ≙ ``attachment.write({'access_token': ...})``: por ``save()``,
            # con sus señales, y sin revalidar el contenido.
            self.access_token = self._generate_access_token()
            self.save(update_fields=['access_token'])
        return self.access_token

    def save(self, *args, user=None, trusted=False, **kwargs):
        """Calcula ``file_size``/``checksum`` cuando hay contenido — versión
        simplificada de ``_get_datas_related_values``/``_compute_checksum``
        de Odoo (sin el sharding sha1 propio del filestore; Django
        ``FileField``
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
        update_fields = kwargs.get('update_fields')
        # ≙ ``write`` (``odoo19c: ir_attachment.py:725-726``): el contenido se
        # revalida sólo si cambia. Un guardado parcial que no toca
        # ``mimetype`` ni ``datas`` —el token, el nombre— no degrada lo que
        # quien subió el archivo ya tenía permitido.
        if update_fields is None or {'mimetype', 'datas'} & set(update_fields):
            content = None
            if self.datas:
                content = self.datas.read()
                self.datas.seek(0)
                self.file_size = len(content)
                self.checksum = hashlib.sha1(content).hexdigest()
            # ``raw`` viaja como en los valores de alta de la fuente: sin él
            # ``_compute_mimetype`` no llega a su cuarta regla, la firma del
            # contenido, y todo archivo de nombre ambiguo salía
            # ``application/octet-stream``.
            self.mimetype = self._check_contents(
                {'mimetype': self.mimetype, 'name': self.name,
                 'url': self.url, 'raw': content},
                user=user,
                trusted=trusted,
            )['mimetype']
        super().save(*args, **kwargs)
        if (
            self.datas
            and self.datas.name
            and self.store_fname != self.datas.name
        ):
            self.store_fname = self.datas.name
            type(self).objects.filter(pk=self.pk).update(
                store_fname=self.store_fname
            )

    # --- Origen remoto ----------------------------------------------------
    #
    # ≙ ``_is_remote_source`` / ``_migrate_remote_to_local``
    # (``odoo19c: ir_attachment.py:961-963, 980-984``). Los consume
    # ``ir.actions.report._prepare_local_attachments``, que baja a local lo
    # que la plantilla vaya a incrustar antes de renderizar: un motor de PDF
    # no puede resolver una URL externa a mitad del dibujado.

    def _is_remote_source(self):
        """¿El contenido de este adjunto vive fuera, tras una URL?

        Las tres condiciones son de la fuente y las tres importan: hay
        ``url``, el ``file_size`` es cero —o sea, no se ha bajado nada— y el
        esquema es uno de los tres que se pueden ir a buscar.

        La fuente abre con ``self.ensure_one()`` porque allá el receptor es un
        conjunto de registros; aquí es una instancia y esa guarda no tiene
        forma que tomar.
        """
        return bool(
            self.url
            and not self.file_size
            and self.url.startswith(('http://', 'https://', 'ftp://'))
        )

    def _migrate_remote_to_local(self):
        """Baja a local el contenido de un adjunto remoto.

        **Aquí es el enganche, y eso es fiel, no un porte a medias.** En la
        fuente este método tiene cuatro líneas: sale si el adjunto ya es
        binario y rehúsa si es de tipo ``url``. Quien hace el trabajo de
        verdad es ``cloud_storage``, que lo extiende y llama a ``super()``
        (``odoo19c: addons/cloud_storage/models/ir_attachment.py:50-52``) —
        medido: son los dos únicos consumidores del símbolo en todo el árbol.

        Ese addon no está portado. Cuando lo esté, extiende este método y el
        cuerpo de la descarga vive allí, que es donde la referencia lo pone.
        """
        if self.type == 'binary':
            return
        if self.type == 'url':
            raise ValidationError(
                _('URL attachment (%s) shouldn\'t be migrated to local.')
                % self.pk
            )

    # ------------------------------------------------------------------
    # Acceso por registro — ≙ ``odoo19c: ir_attachment.py:504-795``
    # ------------------------------------------------------------------
    def check(self, mode, values=None):
        """Restricts the access to an ir.attachment, according to referred
        mode — ≙ ``check`` (``:504-512``), obsoleto desde 19.0."""
        warnings.warn("Since 19.0, use check_access", DeprecationWarning,
                      stacklevel=2)
        # Always require an internal user (aka, employee) to access to a
        # attachment
        if not (self.env.is_admin() or self.env.user._is_internal()):
            raise AccessError(
                _("Sorry, you are not allowed to access this document."))
        self.check_access(mode)
        if values and any(self._inaccessible_comodel_records(
                {values.get('res_model'): [values.get('res_id')]}, mode)):
            raise AccessError(
                _("Sorry, you are not allowed to access this document."))

    def _check_access(self, operation):
        """Check access for attachments — ≙ ``_check_access`` (``:514-588``).

        Rules:
        - `public` is always accessible for reading.
        - If we have `res_model and res_id`, the attachment is accessible if
          the referenced model is accessible. Also, when `res_field != False`
          and the user is not an administrator, we check the access on the
          field.
        - If we don't have a referenced record, the attachment is accessible
          to the administrator and the creator of the attachment.
        """
        res = super()._check_access(operation)
        remaining = self
        error_func = None
        forbidden_ids = OrderedSet()
        if res:
            forbidden, error_func = res
            if forbidden == self:
                return res
            remaining -= forbidden
            forbidden_ids.update(forbidden._ids)
        elif not self:
            return None

        if operation in ('create', 'unlink'):
            # check write operation instead of unlinking and creating for
            # related models and field access
            operation = 'write'

        # collect the records to check (by model)
        model_ids = defaultdict(set)            # {model_name: set(ids)}
        # [(att_id, (res_model, res_id))]
        att_model_ids = []
        remaining = remaining.sudo()
        remaining.fetch(SECURITY_FIELDS)  # fetch only these fields
        for attachment in remaining:
            if attachment.public and operation == 'read':
                continue
            att_id = attachment.id
            res_model, res_id = attachment.res_model, attachment.res_id
            if not self.env.is_system():
                # Un ``create_uid`` vacío se lee ``None`` aquí y recordset
                # vacío allá; en los dos casos no es el usuario.
                creator = attachment.create_uid
                if not res_id and (creator.id if creator else False) \
                        != self.env.uid:
                    forbidden_ids.add(att_id)
                    continue
                if res_field := attachment.res_field:
                    try:
                        field = self.env[res_model]._fields[res_field]
                    except (KeyError, AttributeError):
                        # field does not exist
                        field = None
                    if field is None or not self._has_field_access(
                            field, operation):
                        forbidden_ids.add(att_id)
                        continue
            if res_model and res_id:
                model_ids[res_model].add(res_id)
                att_model_ids.append((att_id, (res_model, res_id)))
        forbidden_res_model_id = set(
            self._inaccessible_comodel_records(model_ids, operation))
        forbidden_ids.update(att_id for att_id, res in att_model_ids
                             if res in forbidden_res_model_id)

        if forbidden_ids:
            forbidden = self.browse(forbidden_ids)
            # avoid cache pollution
            forbidden.invalidate_recordset(SECURITY_FIELDS)
            if error_func is None:
                def error_func():
                    return AccessError(self.env._(
                        "Sorry, you are not allowed to access this "
                        "document. Please contact your system "
                        "administrator.\n\n"
                        "(Operation: %(operation)s)\n\n"
                        "Records: %(records)s, User: %(user)s",
                        operation=operation,
                        records=forbidden[:6],
                        user=self.env.uid,
                    ))
            return forbidden, error_func
        return None

    def _inaccessible_comodel_records(self, model_and_ids, operation):
        """Los ``(res_model, res_id)`` a los que el usuario no llega —
        ≙ ``_inaccessible_comodel_records`` (``:590-618``)."""
        # check access rights on the records
        if self.env.su:
            return
        for res_model, res_ids in model_and_ids.items():
            res_ids = OrderedSet(filter(None, res_ids))
            if not res_model or not res_ids:
                # nothing to check
                continue
            # forbid access to attachments linked to removed models as we do
            # not know what persmissions should be checked
            if res_model not in self.env:
                for res_id in res_ids:
                    yield res_model, res_id
                continue
            comodel = self.env[res_model]
            if res_model == 'res.users' and len(res_ids) == 1 \
                    and self.env.uid in res_ids:
                # by default a user cannot write on itself, despite the list
                # of writeable fields e.g. in the case of a user inserting an
                # image into his image signature we need to bypass this check
                # which would needlessly throw us away
                continue
            if hasattr(comodel, '_filtered_access'):
                records = comodel.browse(res_ids)
                try:
                    records = records._filtered_access(operation)
                except MissingError:
                    records = records.exists()._filtered_access(operation)
                res_ids.difference_update(records._ids)
            else:
                res_ids.difference_update(_accessible_ids(
                    comodel, res_ids, operation, self.env.user))
            for res_id in res_ids:
                yield res_model, res_id

    @classmethod
    def _search(cls, domain, offset=0, limit=None, order=None, *,
                active_test=True, bypass_access=False):
        """≙ ``_search`` (``:620-708``): el dominio de seguridad de los
        adjuntos, sobre el de ``BaseModel``."""
        self = cls._from_ids(env(), (), ())
        assert not cls._active_field_name(), \
            "active name not supported on ir.attachment"
        disable_binary_fields_attachments = False
        domain = Domain(domain)
        if (
            not self.env.context.get('skip_res_field_check')
            and not any(d.field_expr in ('id', 'res_field')
                        for d in domain.iter_conditions())
            and not bypass_access
        ):
            disable_binary_fields_attachments = True
            domain &= Domain('res_field', '=', False)

        domain = domain.optimize(self)
        parent = super(IrAttachment, cls)._search
        if self.env.su or bypass_access or domain.is_false():
            return parent(domain, offset, limit, order,
                          active_test=active_test,
                          bypass_access=bypass_access)

        # General access rules
        # - public == True are always accessible
        sec_domain = Domain('public', '=', True)
        # - res_id == False needs to be system user or creator
        res_ids = condition_values(self, 'res_id', domain)
        if not res_ids or False in res_ids:
            if self.env.is_system():
                sec_domain |= Domain('res_id', '=', False)
            else:
                sec_domain |= (Domain('res_id', '=', False)
                               & Domain('create_uid', '=', self.env.uid))

        # Search by res_model and res_id, filter using permissions from
        # res_model
        # - res_id != False needs then check access on the linked res_model
        #   record
        # - res_field != False needs to check field access on the res_model
        res_model_names = condition_values(self, 'res_model', domain)
        if 0 < len(res_model_names or ()) <= 5:
            for res_model_name in res_model_names:
                if res_model_name not in self.env:
                    continue
                comodel = self.env[res_model_name]
                codomain = Domain('res_model', '=', res_model_name)
                comodel_res_ids = condition_values(
                    self, 'res_id', domain.map_conditions(
                        lambda cond: codomain & cond
                        if cond.field_expr == 'res_model' else cond))
                if hasattr(comodel, '_search'):
                    query = comodel.with_context(active_test=False)._search(
                        Domain('id', 'in', comodel_res_ids)
                        if comodel_res_ids else Domain.TRUE)
                    if query.is_empty():
                        continue
                    if query.where_clause:
                        codomain &= Domain('res_id', 'in', query)
                else:
                    # Un comodelo de Django: los ids accesibles los da su
                    # ``AccessQuerySet`` (ver :func:`_accessible_ids`).
                    candidates = comodel_res_ids or list(
                        comodel._default_manager.values_list('pk', flat=True))
                    allowed = _accessible_ids(comodel, candidates, 'read',
                                              self.env.user)
                    if not allowed:
                        continue
                    codomain &= Domain('res_id', 'in', sorted(allowed))
                if (not disable_binary_fields_attachments
                        and not self.env.is_system()
                        and hasattr(comodel, '_fields')):
                    accessible_fields = [
                        field.name
                        for field in comodel._fields.values()
                        if field.type == 'binary' or (
                            field.relational
                            and field.comodel_name == self._name)
                        if comodel._has_field_access(field, 'read')
                    ]
                    accessible_fields.append(False)
                    codomain &= Domain('res_field', 'in', accessible_fields)
                sec_domain |= codomain

            return parent(domain & sec_domain, offset, limit, order,
                          active_test=active_test)

        # We do not have a small restriction on res_model. We still need to
        # support other queries such as: `('id', 'in' ...)`.
        # Restrict with domain and add all attachments linked to a model.
        domain &= sec_domain | Domain('res_model', '!=', False)
        domain = domain.optimize_full(self)
        ordered = bool(order)
        if limit is None:
            records = self.sudo().with_context(active_test=False).search_fetch(
                domain, SECURITY_FIELDS, order=order).sudo(False)
            return records._filtered_access('read')[offset:]._as_query(ordered)
        # Fetch by small batches
        sub_offset = 0
        limit += offset
        result = []
        if not ordered:
            # By default, order by model to batch access checks.
            order = 'res_model nulls first, id'
        while len(result) < limit:
            records = self.sudo().with_context(active_test=False).search_fetch(
                domain,
                SECURITY_FIELDS,
                offset=sub_offset,
                limit=PREFETCH_MAX,
                order=order,
            ).sudo(False)
            result.extend(records._filtered_access('read')._ids)
            if len(records) < PREFETCH_MAX:
                # There are no more records
                break
            sub_offset += PREFETCH_MAX
        return self.browse(result[offset:limit])._as_query(ordered)

    def write(self, vals):
        """≙ ``write`` (``:710-722``): no se reasigna un adjunto a un
        registro inaccesible."""
        self.check_access('write')
        if vals.get('res_model') or vals.get('res_id'):
            model_and_ids = defaultdict(OrderedSet)
            if 'res_model' in vals and 'res_id' in vals:
                model_and_ids[vals['res_model']].add(vals['res_id'])
            else:
                for record in self:
                    model_and_ids[vals.get('res_model', record.res_model)].add(
                        vals.get('res_id', record.res_id))
            if any(self._inaccessible_comodel_records(model_and_ids, 'write')):
                raise AccessError(
                    _("Sorry, you are not allowed to access this document."))
        return super().write(vals)
