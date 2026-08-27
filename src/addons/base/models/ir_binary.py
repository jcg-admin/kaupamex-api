"""``ir.binary`` — helper para servir campos binarios como respuesta HTTP.

Adaptación de ``odoo/addons/base/models/ir_binary.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 259 líneas). Su trabajo allá está
declarado en el propio ``_description``: *"File streaming helper model for
controllers"* — convierte el campo binario de un registro en un ``Stream`` que
los controladores ``/web/content`` y ``/web/image`` devuelven.

Por qué esta portación cambia de forma, y qué se conserva
=========================================================

Esa divergencia cubre los **2 enganches** que Enterprise 19 usa sobre este
modelo —``_get_stream_from`` y ``_record_to_stream``—: los dos devuelven un
``Stream``, el objeto que aquí no se porta porque Django ya lo tiene. Tarea
#78, :ref:`h-api-819`.

El ``Stream`` de la referencia es una clase de ``odoo.http`` que envuelve
werkzeug y sabe emitir por ruta, por datos o por URL, con ETag y
``last_modified``. Django ya tiene ese objeto: ``FileResponse`` sobre el
storage, con su propio manejo condicional. Portar ``Stream`` sería
reimplementar lo que el framework de abajo ya hace — y peor.

Lo que **sí** se porta, porque es conocimiento del dominio y no del transporte:

1. **La derivación del tamaño desde el nombre del campo**
   (``image_guess_size_from_field_name``, ``odoo/tools/image.py:540-562``).
   Reglas verbatim: ``'image'`` → ``(1024, 1024)``; un campo ``x_*``
   (personalizado) → ``(0, 0)``; si el sufijo tras el último ``_`` no es un
   entero → ``(0, 0)``; **si el sufijo es menor que 16 → ``(0, 0)``** porque
   *"probablemente no sea el tamaño"* (comentario de la fuente); en otro caso
   ``(sufijo, sufijo)``. Esa regla del 16 es exactamente lo que un port
   ingenuo pierde: ``image_5`` no mide 5 píxeles.
2. **La cadena de respaldo del marcador de posición.** Si el campo está vacío
   o el registro no es accesible, se sirve la imagen de relleno en vez de un
   404 — y el default es ``web/static/img/placeholder.png``, mismo path.
3. **El orden de las operaciones** al pedir una imagen: resolver → si no hay
   datos, marcador → si no es ``image/*``, degradar el mimetype a
   ``application/octet-stream`` → si no se pidió tamaño, derivarlo del nombre
   del campo → redimensionar.

Lo que NO se porta, con su medición
===================================

- **``_find_record`` por ``xmlid``.** **Actualizado** (porte de
  ``ir_model.py``): ``grep -rn "^class IrModelData\b" src/`` → **1** clase (el
  ancla de columna 0 distingue una definición de una cita indentada — ver
  H-API-141). [PROVEN] La medición de **0** clases que justificaba omitirlo
  dejó de ser cierta: ``ir.model.data`` **ya existe** y el ``xmlid`` tiene
  contra qué resolverse. Lo que sigue faltando es el **cargador** que puebla
  esa tabla desde datos declarativos, así que la resolución por ``xmlid``
  entra cuando haya filas que resolver, no antes. Mientras tanto se usa
  ``modelo + id``, que es la que usan los consumidores reales.
- **``access_token`` / ``verify_limited_field_access_token`` /
  ``_can_return_content`` / ``record.sudo()``.** Son el mecanismo de Odoo para
  servir un binario **saltándose** los derechos de acceso con un token de
  alcance limitado. Aquí la autorización es por capacidad y fail-closed
  (DEC-11): la vista gatea con ``HasCapability`` antes de llamar a este
  helper. Añadir un bypass por token sería abrir un camino paralelo al modelo
  de capacidades — exactamente lo que DEC-11 prohíbe. Ya está declarado así en
  ``avatar_mixin.py``, que por eso no porta ``_get_avatar_128_access_token``.
- **``field.attachment`` → búsqueda en ``ir.attachment``.** En la referencia un
  campo binario puede guardarse *fuera* de la tabla, como adjunto; el helper
  lo resuelve. Aquí los binarios son ``FileField``/``ImageField`` sobre el
  storage de Django: el archivo ya está fuera de la tabla por construcción, y
  el campo apunta a él.
- **ETag / ``is_resource_modified``.** ``FileResponse`` + el middleware
  condicional de Django los resuelven; reimplementarlos duplicaría el
  mecanismo del framework.
"""
import logging
import mimetypes

from django.apps import apps
from django.core.files.storage import default_storage
from django.http import FileResponse

from addons.base.models.image_mixin import _resize

_logger = logging.getLogger(__name__)

#: Mismo path que ``DEFAULT_PLACEHOLDER_PATH`` de la referencia.
DEFAULT_PLACEHOLDER_PATH = 'web/static/img/placeholder.png'

#: Extensiones admitidas para un marcador de posición — la referencia pasa
#: ``filter_ext=('.png', '.jpg')`` a ``Stream.from_path``/``file_open``.
PLACEHOLDER_EXTENSIONS = ('.png', '.jpg')

#: Mimetype por defecto cuando no se puede determinar (igual que allá).
DEFAULT_IMAGE_MIMETYPE = 'image/png'

#: Umbral de la referencia: un sufijo menor a esto no es una medida.
_MIN_SIZE_SUFFIX = 16


def image_guess_size_from_field_name(field_name):
    """Deduce el tamaño de imagen desde el nombre del campo.

    Verbatim de ``odoo/tools/image.py:540-562`` (``odoo19c:``), incluida la
    regla del umbral 16. Devuelve ``(0, 0)`` cuando no se puede deducir o el
    campo es personalizado.
    """
    if field_name == 'image':
        return (1024, 1024)
    if field_name.startswith('x_'):
        return (0, 0)
    try:
        suffix = int(field_name.rsplit('_', 1)[-1])
    except ValueError:
        return (0, 0)
    if suffix < _MIN_SIZE_SUFFIX:
        # Si el sufijo es menor a 16, probablemente no sea el tamaño.
        return (0, 0)
    return (suffix, suffix)


class RecordNotFound(LookupError):
    """No hay registro para el par modelo+id — ``MissingError`` de la referencia."""


class IrBinary:
    """Helper de streaming de archivos para las vistas (``ir.binary``).

    En la referencia es un ``AbstractModel`` (comportamiento sin tabla); aquí
    es una clase plana por la misma razón: no tiene columnas.

    **El llamador debe haber verificado la capacidad antes** (DEC-11). Este
    helper no autoriza: resuelve y sirve.
    """

    @staticmethod
    def find_record(res_model, res_id):
        """Resuelve un registro por ``app_label.ModelName`` + id.

        La referencia acepta además un ``xmlid``; aquí no hay
        ``ir.model.data`` que lo resuelva (ver docstring del módulo).

        :raises RecordNotFound: cuando no hay registro — equivale al
            ``MissingError`` de la fuente.
        """
        try:
            model = apps.get_model(res_model)
        except (LookupError, ValueError) as exc:
            raise RecordNotFound(
                f'Modelo desconocido res_model={res_model}') from exc
        record = model.objects.filter(pk=res_id).first()
        if record is None:
            raise RecordNotFound(
                f'Sin registro para res_model={res_model}, id={res_id}')
        return record

    @staticmethod
    def _field_file(record, field_name):
        """El archivo del campo, o ``None`` si está vacío."""
        file = getattr(record, field_name, None)
        if not file or not getattr(file, 'name', ''):
            return None
        return file

    @classmethod
    def _guess_mimetype(cls, filename, default=DEFAULT_IMAGE_MIMETYPE):
        mimetype, _ = mimetypes.guess_type(filename or '')
        return mimetype or default

    @classmethod
    def get_response_from(cls, record, field_name='raw', filename=None,
                          filename_field='name', mimetype=None,
                          default_mimetype='application/octet-stream'):
        """Respuesta HTTP desde el campo binario de un registro.

        Equivale a ``_get_stream_from``: el nombre de descarga sale de
        ``filename``, o del campo ``filename_field`` del registro, o —como
        allá— se compone ``{tabla}-{id}-{campo}.{extensión}``.
        """
        file = cls._field_file(record, field_name)
        if file is None:
            return None
        if not filename:
            filename = getattr(record, filename_field, None)
        if not filename:
            extension = (
                mimetypes.guess_extension(mimetype or '')
                or f'.{file.name.rsplit(".", 1)[-1]}' if '.' in file.name else ''
            )
            filename = (
                f'{record._meta.db_table}-{record.pk}-{field_name}{extension}'
            )
        response = FileResponse(
            file.open('rb'), as_attachment=False, filename=filename)
        response['Content-Type'] = (
            mimetype or cls._guess_mimetype(file.name, default_mimetype))
        return response

    @classmethod
    def get_placeholder_path(cls, path=None):
        """Ruta del marcador de posición — ``_get_placeholder_stream``."""
        return path or DEFAULT_PLACEHOLDER_PATH

    @classmethod
    def placeholder(cls, path=None):
        """Bytes del marcador de posición; ``b''`` si no está desplegado.

        La referencia revienta si falta el asset. Aquí un marcador ausente no
        debe tumbar una respuesta: el vacío es observable por el consumidor,
        mismo criterio que ``avatar_mixin._avatar_get_placeholder``.
        """
        path = cls.get_placeholder_path(path)
        if not path.endswith(PLACEHOLDER_EXTENSIONS):
            _logger.warning('Marcador de posición con extensión no admitida: %s', path)
            return b''
        try:
            with default_storage.open(path, 'rb') as file:
                return file.read()
        except (OSError, ValueError):
            return b''

    @classmethod
    def get_image_response_from(cls, record, field_name='raw', filename=None,
                                filename_field='name', mimetype=None,
                                default_mimetype=DEFAULT_IMAGE_MIMETYPE,
                                placeholder=None, width=0, height=0):
        """Respuesta HTTP de imagen, con respaldo y redimensionado.

        Conserva el orden de la referencia (``_get_image_stream_from``):

        1. resolver el campo; si no hay datos → marcador de posición;
        2. si el mimetype no es ``image/*`` → ``application/octet-stream``;
        3. si no se pidió tamaño → derivarlo del nombre del campo;
        4. redimensionar.

        ``crop`` y ``quality`` de la referencia no se portan: ``_resize`` de
        ``image_mixin`` preserva la proporción y no recorta, que es la única
        política de imagen que este árbol tiene declarada. Ampliarla a recorte
        es una decisión de producto, no una traducción.
        """
        file = cls._field_file(record, field_name)
        if file is None:
            data = cls.placeholder(placeholder)
            response = FileResponse(
                iter([data]), as_attachment=False,
                filename=filename or 'placeholder.png')
            response['Content-Type'] = DEFAULT_IMAGE_MIMETYPE
            return response

        resolved = mimetype or cls._guess_mimetype(file.name, default_mimetype)
        if not resolved.startswith('image/'):
            resolved = 'application/octet-stream'

        if (width, height) == (0, 0):
            width, height = image_guess_size_from_field_name(field_name)

        if width or height:
            content = _resize(file, max(width, height))
            response = FileResponse(
                content, as_attachment=False,
                filename=filename or file.name.rsplit('/', 1)[-1])
        else:
            response = cls.get_response_from(
                record, field_name, filename, filename_field,
                resolved, default_mimetype)
        response['Content-Type'] = resolved
        return response
