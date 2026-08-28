"""``ir.fields.converter`` — conversión de valores de importación a valores de campo.

Adaptación de ``odoo/addons/base/models/ir_fields.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 740 líneas). Es la capa que traduce lo
que llega de una importación (una celda de CSV, un string) al valor que el
campo acepta, con sus errores y advertencias.

El mecanismo de despacho, portado tal cual
==========================================

``to_field`` de la referencia no tiene un ``if`` por tipo: busca un método
llamado ``_{tipo_origen}_to_{tipo_campo}`` y lo devuelve parcializado. Ese
despacho por nombre es lo que hace la capa extensible —un addon añade un
converter declarando un método— y se porta igual, con
``getattr(cls, f'_{typename}_to_{fieldtype}', None)``.

Se conservan también los dos contratos del converter:

- devuelve ``(valor, advertencias)``, donde las advertencias son instancias de
  ``ImportWarning``; o
- levanta ``ValueError`` con un mensaje de usuario que puede llevar el
  marcador ``%(field)s``, y opcionalmente un diccionario de contexto que el
  llamador funde en su error. ``_format_import_error`` preserva el saneado de
  ``%`` → ``%%`` en los parámetros, sin el cual un valor con porcentaje
  reventaría el formateo aguas arriba.

Los alias de tipo también son de la fuente: ``_str_to_monetary`` es
``_str_to_float``, y ``reference``/``char``/``text``/``binary``/``html``
comparten ``_str_id`` (la identidad).

Semántica que importa, conservada al detalle
============================================

- **Booleano.** Verdadero: ``1``, ``true``, ``yes``. Falso: **cadena vacía**,
  ``0``, ``false``, ``no``. La comparación es en minúsculas. Que la cadena
  vacía cuente como falso —y no como "sin valor"— es la decisión que un port
  ingenuo pierde. Ante un valor desconocido, el error sugiere *"usa 1 para sí
  y 0 para no"*, igual que allá.
- **Selection.** Compara **sin distinguir mayúsculas** contra el valor interno
  *y* contra la etiqueta; la fuente lo comenta explícitamente. El error lista
  las opciones válidas en ``moreinfo``.
- **Fecha y hora.** El ``datetime`` entra **ingenuo**, se localiza en la zona
  de entrada y se convierte a UTC antes de escribirlo — sin ese paso una
  importación desde otra zona guarda la hora corrida. Los formatos sugeridos
  en el error son los mismos: ``2012-12-31`` y ``2012-12-31 23:59:59``.

La mitad relacional, portada en la tarea #132
=============================================

Hasta esta tarea el archivo declaraba **no portada** toda la resolución de
referencias —``for_model``, ``db_id_for``, ``_xmlid_to_record_id``,
``_referencing_subfield`` y los cuatro conversores relacionales—, con esta
razón: *"``grep -rn "def name_search" src/`` sigue en 0 definiciones"*.

**Esa premisa caducó.** Medido de nuevo: ``name_search`` está en
``src/orm/models.py:1603`` y ``name_create`` en ``:1585``, y la tabla del
identificador externo la puebla ``IrModelData._update_xmlids`` desde la tarea
#115. Los dos caminos que faltaban existen, así que la mitad relacional se
porta (Clausula 2 del principio rector: estado incorrecto heredado se corrige
en el pase que lo encuentra, no se re-declara).

Tres divergencias quedan declaradas, y ninguna es un hueco de alcance:

- **La forma del valor relacional.** La fuente devuelve ``Command`` diferidos
  que su ``write`` interpreta; el ``Command`` de este árbol es **ejecutivo**
  (:ref:`h-api-589`, tarea **#345**). El valor lo portan
  :class:`orm.commands.ManyToManySet`, :class:`~orm.commands.ManyToManyLink` y
  :class:`~orm.commands.One2manyChild`, y lo aplica el cargador cuando el
  registro ya existe — que es el momento en que Django admite tocar una
  relación de muchos.
- **El origen de las traducciones.** ``_get_boolean_translations`` lee de
  :data:`BOOLEAN_TRANSLATIONS` en vez del catálogo de gettext, que este árbol
  no tiene; ``_get_selection_translations`` lee la misma tabla que la fuente
  (``ir.model.fields.selection``) con el ORM en vez de con SQL tejido a mano.
- **El nombre del tipo en el despacho.** ``to_field`` busca
  ``_{origen}_to_{tipo}``, y aquí el tipo sale de la clase de campo de Django:
  de ahí los alias ``_str_to_foreignkey``, ``_str_to_manytomany`` y
  ``_str_to_manytoonerel`` junto a los nombres de la fuente.
"""
import datetime
import functools
import itertools
import json
import logging
from typing import NamedTuple

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from addons.base.models.ir_model import IrModelData, IrModelFieldsSelection
from orm import registry
from tools.misc import OrderedSet
from orm.commands import ManyToManyLink, ManyToManySet, One2manyChild
from orm.environments import context_scope, get_context

_logger = logging.getLogger(__name__)

#: Campos que referencian a otro registro — ``REFERENCING_FIELDS`` verbatim.
REFERENCING_FIELDS = {None, 'id', '.id'}

#: Literales verdaderos, sin traducir (la fuente advierte de no usar valores
#: potencialmente traducidos en esta lista base).
TRUE_LITERALS = ('1', 'true', 'yes')
#: Literales falsos — nótese que la **cadena vacía** cuenta como falso.
FALSE_LITERALS = ('', '0', 'false', 'no')

#: Los equivalentes en español de los cuatro literales que la fuente traduce
#: (``BOOLEAN_TRANSLATIONS`` de ``odoo19c: :22-28``). Allá los resuelve el
#: catálogo de gettext por idioma instalado; aquí se declaran, porque el
#: idioma del producto es uno.
BOOLEAN_TRANSLATIONS = {
    'true': ('verdadero',),
    'yes': ('si', 'sí'),
    'false': ('falso',),
    'no': ('no',),
}

#: Formatos que el error sugiere al usuario, iguales a los de la fuente.
DATE_HINT = '2012-12-31'
DATETIME_HINT = '2012-12-31 23:59:59'


def only_ref_fields(record):
    """Sólo las claves que referencian — verbatim de la fuente."""
    return {k: v for k, v in record.items() if k in REFERENCING_FIELDS}


def exclude_ref_fields(record):
    """Todo salvo las claves que referencian — verbatim de la fuente."""
    return {k: v for k, v in record.items() if k not in REFERENCING_FIELDS}


class FakeField(NamedTuple):
    """Campo sintético — verbatim de la fuente (``odoo19c: :31-33``).

    Lo usa :meth:`IrFieldsConverter._str_to_properties`: una propiedad
    relacional no tiene campo declarado en el modelo, pero ``db_id_for``
    necesita uno del que leer ``comodel_name`` y ``name``.
    """
    comodel_name: str
    name: str


class ImportWarning(Warning):
    """Advertencia emitida hacia arriba durante la importación."""


class ConversionNotFound(ValueError):
    """No hay converter para el par (tipo origen, tipo campo)."""


class IrFieldsConverter:
    """Convierte valores de importación a valores de campo (``ir.fields.converter``).

    En la referencia es un ``AbstractModel``; aquí es una clase de métodos de
    clase por la misma razón que ``ir_binary``: no tiene columnas.
    """

    #: Memoria de las etiquetas traducidas de una opción — ≙ el
    #: ``env.cr.cache`` que la fuente usa para lo mismo. La vacía el cargador
    #: al empezar cada archivo.
    _selection_translation_cache: dict = {}

    @staticmethod
    def _format_import_error(error_type, error_msg, error_params=(),
                             error_args=None):
        """Construye el error de importación saneando sus parámetros.

        El saneado de ``%`` → ``%%`` es de la fuente y no es cosmético: sin él,
        un valor que contenga un porcentaje rompe el formateo que el sistema de
        importación aplica después.
        """
        def sanitize(param):
            return param.replace('%', '%%') if isinstance(param, str) else param

        if error_params:
            if isinstance(error_params, str):
                error_params = sanitize(error_params)
            elif isinstance(error_params, dict):
                error_params = {k: sanitize(v) for k, v in error_params.items()}
            elif isinstance(error_params, tuple):
                error_params = tuple(sanitize(v) for v in error_params)
        return error_type(error_msg % error_params, error_args)

    @classmethod
    def to_field(cls, model, field, fromtype=str, *, savepoint=None):
        """Devuelve el converter para ``field`` desde ``fromtype``, o ``None``.

        Despacho por nombre, igual que la fuente: busca
        ``_{tipo_origen}_to_{tipo_campo}``. Un addon extiende la capa
        declarando un método con ese patrón, sin tocar este archivo.

        El converter devuelto es un callable ``(valor) -> (valor, advertencias)``
        que puede levantar ``ValueError`` ante un dato inconvertible.
        """
        assert isinstance(fromtype, (type, str))
        typename = fromtype.__name__ if isinstance(fromtype, type) else fromtype
        fieldtype = cls._field_type(field)
        converter = getattr(cls, '_%s_to_%s' % (typename, fieldtype), None)
        if not converter:
            return None
        return functools.partial(converter, model, field, savepoint=savepoint)

    @staticmethod
    def _field_type(field):
        """Nombre del tipo de campo, en el vocabulario del despacho.

        En la referencia ``field.type`` ya es ``'boolean'``/``'char'``/…; aquí
        se deriva de la clase de campo de Django, que es su equivalente.
        """
        return type(field).__name__.replace('Field', '').lower() or 'char'

    # === Conversores escalares ============================================

    @classmethod
    def _str_to_boolean(cls, model, field, value, savepoint=None):
        """``1``/``true``/``yes`` → True; ``''``/``0``/``false``/``no`` → False.

        Ante un valor desconocido **devuelve** ``(True, [error])`` — no lo
        levanta. La diferencia no es de estilo: :meth:`db_id_for` llama a este
        método sobre una referencia cualquiera (``'base.country_zy'``) sólo
        para preguntar «¿es un vacío?», y con un ``raise`` esa pregunta
        reventaría en vez de responder «no». La fuente lo devuelve por eso
        mismo (``odoo19c: :318-322``), y el error viaja en la lista de
        advertencias hasta el ``log`` del converter.

        > Corregido en la tarea **#132**: el porte anterior lo levantaba. Era
        > estado incorrecto heredado (Clausula 2 del principio rector) y
        > bloqueaba los dos caminos de referencia de :meth:`db_id_for`.
        """
        # all translatables used for booleans
        trues = {word.lower() for word in itertools.chain(
            TRUE_LITERALS,
            cls._get_boolean_translations('true'),
            cls._get_boolean_translations('yes'),
        )}
        if value.lower() in trues:
            return True, []

        falses = {word.lower() for word in itertools.chain(
            FALSE_LITERALS,
            cls._get_boolean_translations('false'),
            cls._get_boolean_translations('no'),
        )}
        if value.lower() in falses:
            return False, []

        if field.name in get_context().get('import_skip_records', []):
            return None, []

        return True, [cls._format_import_error(
            ValueError,
            "Valor desconocido '%s' para el campo booleano '%%(field)s'",
            value,
            {'moreinfo': "Usa '1' para sí y '0' para no"},
        )]

    @classmethod
    def _get_boolean_translations(cls, src):
        """≙ ``_get_boolean_translations`` (``odoo19c: :414-419``).

        Las traducciones de ``yes``/``no``/``true``/``false`` en los idiomas
        instalados, para que una celda con ``sí`` u ``oui`` cuente como
        verdadera.

        DIVERGENCIA DE FUENTE, declarada: allá salen del catálogo de
        traducciones de código (``code_translations.get_python_translations``),
        que es un mecanismo de gettext que este árbol no tiene. Aquí salen de
        :data:`BOOLEAN_TRANSLATIONS`, que declara los equivalentes del idioma
        del producto — español — junto a los literales en inglés que la fuente
        ya trae sin traducir.
        """
        return BOOLEAN_TRANSLATIONS.get(src, ())

    @classmethod
    def _str_to_integer(cls, model, field, value, savepoint=None):
        try:
            return int(value), []
        except ValueError:
            raise cls._format_import_error(
                ValueError,
                "'%s' no parece un entero para el campo '%%(field)s'",
                value,
            ) from None

    @classmethod
    def _str_to_float(cls, model, field, value, savepoint=None):
        try:
            return float(value), []
        except ValueError:
            raise cls._format_import_error(
                ValueError,
                "'%s' no parece un número para el campo '%%(field)s'",
                value,
            ) from None

    #: Alias de la fuente: el monetario se convierte como un flotante.
    _str_to_decimal = _str_to_float

    @classmethod
    def _str_id(cls, model, field, value, savepoint=None):
        """La identidad — la fuente la reusa para varios tipos textuales."""
        return value, []

    # Alias verbatim de la fuente: reference/char/text/binary/html comparten
    # la identidad.
    _str_to_char = _str_id
    _str_to_text = _str_id
    _str_to_binary = _str_id
    _str_to_html = _str_id

    @classmethod
    def _str_to_date(cls, model, field, value, savepoint=None):
        parsed = parse_date(value)
        if parsed is None:
            raise cls._format_import_error(
                ValueError,
                "'%s' no parece una fecha válida para el campo '%%(field)s'",
                value,
                {'moreinfo': "Usa el formato '%s'" % DATE_HINT},
            )
        return parsed.isoformat(), []

    @staticmethod
    def _input_tz():
        """Zona horaria en la que llega el dato — ``self.env.tz`` de la fuente."""
        return timezone.get_current_timezone()

    @classmethod
    def _str_to_datetime(cls, model, field, value, savepoint=None):
        """Convierte a UTC desde la zona de entrada.

        La fuente localiza el ``datetime`` ingenuo en la zona de entrada y
        **después** lo pasa a UTC. Saltarse ese paso guarda la hora corrida
        cuando la importación viene de otra zona.
        """
        parsed = parse_datetime(value)
        if parsed is None:
            raise cls._format_import_error(
                ValueError,
                "'%s' no parece una fecha y hora válidas para el campo '%%(field)s'",
                value,
                {'moreinfo': "Usa el formato '%s'" % DATETIME_HINT},
            )
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, cls._input_tz())
        return parsed.astimezone(datetime.timezone.utc).isoformat(sep=' '), []

    @classmethod
    def _get_selection_translations(cls, field, src):
        """≙ ``_get_selection_translations`` (``odoo19c: :420-444``).

        Las etiquetas traducidas de una opción, para casar una celda escrita en
        otro idioma. Salen de ``ir.model.fields.selection``, que es la misma
        tabla que la fuente consulta —allá con SQL a mano, aquí con el ORM: el
        modelo ya está portado y tejer un segundo SQL sobre su tabla sería una
        segunda fuente de verdad.

        La fuente memoriza el resultado en la caché del cursor porque lo llama
        **por fila del archivo**; aquí la memoria es el diccionario de clase
        :data:`_selection_translation_cache`, que el cargador vacía al empezar
        (:meth:`orm.models.RecordLoaderMixin.load`).
        """
        if not src:
            return []
        cached = cls._selection_translation_cache.get(src)
        if cached is not None:
            return cached

        model_name = registry.name_of(field.model) if hasattr(field, 'model') else None
        rows = IrModelFieldsSelection.objects.filter(
            field__model=model_name, field__name=field.name, value=src,
        ).values_list('name', flat=True)
        result = cls._selection_translation_cache[src] = list(OrderedSet(rows))
        return result

    @classmethod
    def _str_to_selection(cls, model, field, value, savepoint=None):
        """Casa contra el valor interno o la etiqueta, sin distinguir mayúsculas.

        La comparación insensible es explícita en la fuente: permite fijar el
        valor aunque el dato importado no venga con la caja exacta. Las
        etiquetas traducidas las aporta :meth:`_get_selection_translations`.

        Las dos salidas de escape del contexto son las de la fuente y no son lo
        mismo: ``import_skip_records`` devuelve ``None`` —la fila entera se
        salta— y ``import_set_empty_fields`` devuelve el vacío —la fila entra
        con la columna en blanco—.
        """
        selection = list(getattr(field, 'choices', None) or [])
        needle = value.lower()
        for item, label in selection:
            labels = [str(label)] + [
                str(other) for other in cls._get_selection_translations(field, label)
            ]
            if needle == str(item).lower() or any(
                    needle == other.lower() for other in labels):
                return item, []

        if field.name in get_context().get('import_skip_records', []):
            return None, []
        elif field.name in get_context().get('import_set_empty_fields', []):
            return False, []
        raise cls._format_import_error(
            ValueError,
            "El valor '%s' no está en el campo de selección '%%(field)s'",
            value,
            {'moreinfo': [str(label or item) for item, label in selection]},
        )

    # === La mitad relacional ==============================================
    #
    # Traduce una **referencia** —un nombre visible, un identificador externo,
    # un id de base— al registro al que apunta. Estuvo declarada como no
    # portada hasta la tarea #132; ver la nota de la cabecera del módulo, que
    # ya registra por qué su premisa caducó.

    @classmethod
    def for_model(cls, model, fromtype=str, *, savepoint):
        """≙ ``for_model`` (``odoo19c: :95-155``).

        «Returns a converter object for the model. A converter is a callable
        taking a record-ish (a dictionary representing a record with values of
        typetag ``fromtype``) and returning a converted record matching what
        ``write`` expects.»

        Devuelve ``fn(record, log)``. Las tres decisiones de la fuente se
        portan enteras:

        - las claves que **referencian** (``id``, ``.id``, ``None``) no se
          convierten: las consume el cargador, no el campo;
        - un valor **vacío** es el valor vacío del campo, sin pasar por el
          converter — de ahí que una celda en blanco borre en vez de fallar;
        - un error de conversión **se registra** con ``log`` y no se levanta:
          el cargador quiere el archivo entero con sus errores, no el primero.
        """
        converters = {
            field.name: cls.to_field(model, field, fromtype, savepoint=savepoint)
            for field in model._meta.get_fields()
            if hasattr(field, 'name')
        }

        def fn(record, log):
            converted = {}
            import_file_context = get_context().get('import_file')
            for field, value in record.items():
                if field in REFERENCING_FIELDS:
                    continue
                if not value:
                    converted[field] = False
                    continue
                converter = converters.get(field)
                if converter is None:
                    log(field, ValueError(
                        "No hay converter para el campo '%s'" % field))
                    continue
                try:
                    converted[field], ws = converter(value)
                    for w in ws:
                        if isinstance(w, str):
                            # wrap warning string in an ImportWarning for
                            # uniform handling
                            w = ImportWarning(w)
                        log(field, w)
                except (UnicodeEncodeError, UnicodeDecodeError) as exc:
                    log(field, ValueError(str(exc)))
                except ValueError as exc:
                    if import_file_context:
                        # La ruta del campo permite atribuir el error a la
                        # columna correcta de la UI de importación; sólo se
                        # anota en el hijo más profundo, y sin pisarla si ya
                        # venía puesta.
                        error_info = len(exc.args) > 1 and exc.args[1]
                        if error_info and not error_info.get('field_path'):
                            error_info['field_path'] = cls._get_import_field_path(
                                field, value)
                    log(field, exc)
            return converted

        return fn

    @classmethod
    def _get_import_field_path(cls, field, value):
        """≙ ``_get_import_field_path`` (``odoo19c: :58-93``).

        Reconstruye la ruta del campo para atribuir el error a la columna
        correcta. El campo que falla es el último de la cadena
        (``child_id/child_id2/campo``), así que la jerarquía de padres la
        aporta ``parent_fields_hierarchy``, que ``_str_to_one2many`` va
        acumulando en el contexto.
        """
        field_path = [field]
        parent_fields_hierarchy = get_context().get('parent_fields_hierarchy')
        if parent_fields_hierarchy:
            field_path = parent_fields_hierarchy + field_path

        field_path_value = value
        while isinstance(field_path_value, list):
            key = list(field_path_value[0].keys())[0]
            if key:
                field_path.append(key)
            field_path_value = field_path_value[0][key]
        return field_path

    @classmethod
    def _referencing_subfield(cls, record):
        """≙ ``_referencing_subfield`` (``odoo19c: :620-641``).

        Cuál de las tres formas de referencia trae el registro, y su lista de
        advertencias. Las dos guardas de la fuente son el contrato:

        - una clave que **no** referencia significa que alguien intenta crear
          el registro relacionado de paso, y eso se rechaza;
        - **dos** referencias a la vez son ambiguas y también se rechazan.
        """
        # Can import by display_name, external id or database id
        fieldset = set(record)
        if fieldset - REFERENCING_FIELDS:
            raise ValueError(
                'No se pueden crear registros Many-To-One indirectamente; '
                'importa el campo por separado')
        if len(fieldset) > 1:
            raise ValueError(
                "Especificación ambigua para el campo '%(field)s': indica sólo "
                'uno de nombre, identificador externo o id de base')

        # only one field left possible, unpack
        [subfield] = fieldset
        return subfield, []

    @classmethod
    def _comodel(cls, field):
        """El modelo al que apunta el campo — ≙ ``self.env[field.comodel_name]``.

        Un campo de Django ya trae la clase en ``related_model``; un
        :class:`FakeField` (el de una propiedad relacional) trae el nombre
        punteado, que resuelve el registro por nombre.
        """
        related = getattr(field, 'related_model', None)
        if related is not None:
            return related
        return registry.model_by_name(field.comodel_name)

    @classmethod
    def db_id_for(cls, model, field, subfield, value, savepoint):
        """≙ ``db_id_for`` (``odoo19c: :477-585``).

        «Finds a database id for the reference ``value`` in the referencing
        subfield ``subfield`` of the provided field of the provided model.»

        :param model: modelo al que pertenece el campo.
        :param field: campo relacional para el que llega la referencia.
        :param subfield: ``None`` para buscar por nombre visible, ``id`` para
            un identificador externo, ``.id`` para un id de base.
        :param value: la referencia a casar con un registro real.
        :param savepoint: punto de retorno al que volver ante un error.
        :return: el par ``(id, advertencias)``.

        Los tres caminos son los de la fuente y no son intercambiables: el id
        de base **se comprueba que exista**, el externo pasa por
        ``ir.model.data`` con su guarda de modelo, y el nombre visible por
        ``name_search`` —que puede devolver varios, y entonces avisa en vez de
        fallar—.
        """
        # the function 'flush' comes from load(), and forces the
        # creation/update of former records (batch creation)
        flush = get_context().get('import_flush', lambda **kw: None)

        id = None
        warnings = []
        error_msg = ''
        RelatedModel = cls._comodel(field)

        if subfield == '.id':
            field_type = 'id de base'
            if isinstance(value, str) and not cls._str_to_boolean(
                    model, field, value, savepoint=savepoint)[0]:
                return False, warnings
            try:
                tentative_id = int(value)
            except ValueError:
                raise cls._format_import_error(
                    ValueError,
                    "Id de base inválido '%s' para el campo '%%(field)s'",
                    value) from None
            if RelatedModel.objects.filter(pk=tentative_id).exists():
                id = tentative_id
        elif subfield == 'id':
            field_type = 'identificador externo'
            if not cls._str_to_boolean(model, field, value,
                                       savepoint=savepoint)[0]:
                return False, warnings
            if '.' in value:
                xmlid = value
            else:
                xmlid = '%s.%s' % (
                    get_context().get('_import_current_module', ''), value)
            flush(xml_id=xmlid)
            id = cls._xmlid_to_record_id(xmlid, RelatedModel)
        elif subfield is None:
            field_type = 'nombre'
            if value == '':
                return False, warnings
            flush(model=RelatedModel)
            ids = RelatedModel.name_search(name=value, operator='=')
            if ids:
                if len(ids) > 1:
                    warnings.append(ImportWarning(
                        'Varias coincidencias para el valor "%s" en el campo '
                        '"%%(field)s" (%s coincidencias)'
                        % (str(value).replace('%', '%%'), len(ids))))
                id, _name = ids[0]
            else:
                name_create_enabled_fields = get_context().get(
                    'name_create_enabled_fields') or {}
                if name_create_enabled_fields.get(field.name):
                    try:
                        id, _name = RelatedModel.name_create(name=value)
                    except Exception:  # noqa: BLE001
                        savepoint.rollback()
                        error_msg = (
                            "No se pueden crear registros '%s' sólo con su "
                            'nombre. Créalos a mano e importa de nuevo.'
                            % RelatedModel._meta.verbose_name)
        else:
            raise cls._format_import_error(
                Exception, 'Subcampo desconocido "%s"', subfield)

        set_empty = False
        skip_record = False
        if get_context().get('import_file'):
            import_set_empty_fields = get_context().get(
                'import_set_empty_fields') or []
            field_path = '/'.join(
                get_context().get('parent_fields_hierarchy', []) + [field.name])
            set_empty = field_path in import_set_empty_fields
            skip_record = field_path in get_context().get(
                'import_skip_records', [])
        if id is None and not set_empty and not skip_record:
            if error_msg:
                message = ("No se encontró registro para el %(field_type)s "
                           "'%(value)s' en el campo '%%(field)s', y al intentar "
                           'crearlo ocurrió: %(error_message)s')
            else:
                message = ("No se encontró registro para el %(field_type)s "
                           "'%(value)s' en el campo '%%(field)s'")
            raise cls._format_import_error(
                ValueError,
                message,
                {'field_type': field_type, 'value': value,
                 'error_message': error_msg},
                {'value': value, 'field_type': field_type})
        return id, warnings

    @classmethod
    def _xmlid_to_record_id(cls, xmlid, model):
        """≙ ``_xmlid_to_record_id`` (``odoo19c: :595-619``).

        «Return the record id corresponding to the given external id, provided
        that the record actually exists; otherwise return ``None``.»

        La guarda del modelo es lo que impide que un identificador reusado
        entre módulos apunte a la tabla equivocada, y se conserva con el
        mensaje de la fuente.

        DIVERGENCIA DE VÍA, declarada: la fuente teje el SQL a mano (un JOIN
        contra la tabla del modelo). Aquí lo resuelve
        :meth:`IrModelData._xmlid_lookup`, que ya está portado **y memorizado**
        — tejer un segundo SQL sería una segunda fuente de verdad sobre la
        misma tabla.
        """
        import_cache = get_context().get('import_cache')
        if import_cache is not None and xmlid in import_cache:
            result = import_cache[xmlid]
        else:
            try:
                result = IrModelData._xmlid_lookup(xmlid)
            except ValueError:
                return None
            if import_cache is not None:
                import_cache[xmlid] = result

        res_model, res_id = result
        expected = registry.name_of(model)
        if expected is None:
            # Sin ``_name`` la guarda no puede discriminar, y un paso mudo
            # sería el verde que no distingue «el modelo coincide» de «no sé
            # mirar» — sub-patrón D de ``metrica-decide-la-conclusion.md``.
            raise ValueError(
                'El modelo %s no declara ``_name``, así que no se puede '
                'comprobar a qué modelo apunta el identificador externo %s'
                % (model.__name__, xmlid))
        if res_model != expected:
            MSG = ('Identificador externo inválido %s: se esperaba el modelo '
                   '%r, se encontró %r')
            raise ValueError(MSG % (xmlid, expected, res_model))
        return res_id

    @classmethod
    def _str_to_many2one(cls, model, field, values, savepoint=None):
        """≙ ``_str_to_many2one`` (``odoo19c: :643-651``)."""
        # Should only be one record, unpack
        [record] = values

        subfield, w1 = cls._referencing_subfield(record)

        id, w2 = cls.db_id_for(model, field, subfield, record[subfield], savepoint)
        return id, w1 + w2

    #: El campo de Django que porta un ``Many2one`` — el despacho por nombre
    #: busca ``_str_to_{tipo}``, y aquí el tipo es ``foreignkey``.
    _str_to_foreignkey = _str_to_many2one

    @classmethod
    def _str_to_many2one_reference(cls, model, field, value, savepoint=None):
        """≙ ``_str_to_many2one_reference`` (``odoo19c: :653-655``)."""
        return cls._str_to_integer(model, field, value, savepoint)

    @classmethod
    def _str_to_many2many(cls, model, field, value, savepoint=None):
        """≙ ``_str_to_many2many`` (``odoo19c: :657-677``).

        Devuelve la **lista de ids** con la que el campo queda: las referencias
        vienen separadas por coma en una sola celda.

        DIVERGENCIA DE FORMA, declarada: la fuente devuelve
        ``[Command.set(ids)]`` o ``[Command.link(id), …]`` — valores diferidos
        que su ``write`` interpreta. El ``Command`` de este árbol es
        **ejecutivo** (escribe al llamarlo; :ref:`h-api-589`, tarea **#345**),
        así que no hay valor que devolver. Se devuelve la lista de ids, que es
        lo que ``Command.set`` significa, y quien la aplica es
        :meth:`orm.models.RecordLoaderMixin.write` con ``.set(ids)`` — el
        mismo reparto que allá, con el verbo del ORM de este lado.

        ``update_many2many`` del contexto conserva su papel: **añade** en vez
        de reemplazar, que es la diferencia entre ``link`` y ``set``.
        """
        [record] = value

        subfield, warnings = cls._referencing_subfield(record)

        ids = []
        for reference in record[subfield].split(','):
            id, ws = cls.db_id_for(model, field, subfield, reference, savepoint)
            ids.append(id)
            warnings.extend(ws)

        if field.name in get_context().get('import_set_empty_fields', []) \
                and any(id is None for id in ids):
            ids = [id for id in ids if id]
        elif field.name in get_context().get('import_skip_records', []) \
                and any(id is None for id in ids):
            return None, warnings

        if get_context().get('update_many2many'):
            return ManyToManyLink(ids), warnings
        return ManyToManySet(ids), warnings

    #: El campo de Django que porta un ``Many2many``.
    _str_to_manytomany = _str_to_many2many

    @classmethod
    def _str_to_one2many(cls, model, field, records, savepoint=None):
        """≙ ``_str_to_one2many`` (``odoo19c: :679-740``).

        Devuelve la lista de hijos a crear o actualizar. El caso de una sola
        fila con **sólo** referencias se expande, verbatim de la fuente:
        ``{subfield: 'a,b,c'}`` se convierte en tres registros de un campo.

        Misma divergencia de forma que :meth:`_str_to_many2many`: allá el
        resultado son ``Command.create``/``Command.link``+``Command.update``;
        aquí es una lista de :class:`One2manyChild`, que dice lo mismo — con
        id, se enlaza y se escribe encima; sin id, se crea.

        El ``log`` interno **levanta** el error de un hijo en vez de
        registrarlo, y le antepone el nombre del campo hijo al mensaje: es la
        forma en que la fuente atribuye el fallo a la columna correcta.
        """
        name_create_enabled_fields = get_context().get(
            'name_create_enabled_fields') or {}
        prefix = field.name + '/'
        relative_name_create_enabled_fields = {
            k[len(prefix):]: v
            for k, v in name_create_enabled_fields.items()
            if k.startswith(prefix)
        }
        commands = []
        warnings = []

        if len(records) == 1 and exclude_ref_fields(records[0]) == {}:
            # only one row with only ref field, field=ref1,ref2,ref3 as in
            # m2o/m2m
            record = records[0]
            subfield, ws = cls._referencing_subfield(record)
            warnings.extend(ws)
            # transform [{subfield:ref1,ref2,ref3}] into
            # [{subfield:ref1},{subfield:ref2},{subfield:ref3}]
            records = ({subfield: item}
                       for item in record[subfield].split(','))

        comodel = cls._comodel(field)

        def log(f, exception):
            if not isinstance(exception, Warning):
                current_field_name = comodel._meta.get_field(f).verbose_name
                arg0 = exception.args[0].replace(
                    '%(field)s', '%(field)s/' + str(current_field_name))
                exception.args = (arg0, *exception.args[1:])
                raise exception
            warnings.append(exception)

        # Complete the field hierarchy path
        # E.g. For "parent/child/subchild", field hierarchy path for "subchild"
        # is ['parent', 'child']
        parent_fields_hierarchy = get_context().get(
            'parent_fields_hierarchy', []) + [field.name]

        with context_scope(
                name_create_enabled_fields=relative_name_create_enabled_fields,
                parent_fields_hierarchy=parent_fields_hierarchy):
            convert = cls.for_model(comodel, savepoint=savepoint)

            for record in records:
                id = None
                refs = only_ref_fields(record)
                writable = convert(exclude_ref_fields(record), log)
                if refs:
                    subfield, w1 = cls._referencing_subfield(refs)
                    warnings.extend(w1)
                    try:
                        id, w2 = cls.db_id_for(model, field, subfield,
                                               record[subfield], savepoint)
                        warnings.extend(w2)
                    except ValueError:
                        if subfield != 'id':
                            raise
                        writable['id'] = record['id']

                commands.append(One2manyChild(id, writable))

        return commands, warnings

    #: El campo de Django que porta un ``One2many`` es el lado inverso de una
    #: FK; su descriptor se llama ``ManyToOneRel``.
    _str_to_manytoonerel = _str_to_one2many

    @classmethod
    def _str_to_json(cls, model, field, value, savepoint=None):
        """≙ ``_str_to_json`` (``odoo19c: :226-231``)."""
        try:
            return json.loads(value), []
        except ValueError:
            raise cls._format_import_error(
                ValueError,
                "'%s' no parece un JSON válido para el campo '%%(field)s'",
                value) from None

    @classmethod
    def _str_to_properties(cls, model, field, value, savepoint=None):
        """≙ ``_str_to_properties`` (``odoo19c: :233-307``).

        Convierte cada propiedad **contra su definición**, que es lo que la
        distingue de un JSON suelto: el tipo no está en el valor sino en el
        esquema declarado, y por eso una selección se casa contra sus opciones
        y una relación pasa por :meth:`db_id_for` con un :class:`FakeField`.

        La entrada admite las dos formas de la fuente: la cadena JSON con
        todas las propiedades, y la lista de diccionarios que
        ``_extract_records`` compone columna a columna.
        """
        # If we want to import the all properties at once (with the technical
        # value)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                raise cls._format_import_error(
                    ValueError,
                    "No se puede importar '%(field)s' como un todo; importa "
                    'cada propiedad por separado') from None

        if not isinstance(value, list):
            raise cls._format_import_error(
                ValueError,
                "No se puede importar '%(field)s' como un todo; importa cada "
                'propiedad por separado')

        warnings = []
        for property_dict in value:
            if not (property_dict.keys() >= {'name', 'type', 'string'}):
                raise cls._format_import_error(
                    ValueError,
                    "'%s' no parece un valor de propiedad válido para el campo "
                    "'%%(field)s'. Cada propiedad necesita al menos 'name', "
                    "'type' y 'string'.",
                    str(property_dict))

            val = property_dict.get('value')
            if not val:
                continue

            property_type = property_dict['type']

            if property_type == 'selection':
                # either label or the technical value
                new_val = next(iter(
                    sel_val for sel_val, sel_label in property_dict['selection']
                    if val in (sel_val, sel_label)
                ), None)
                if not new_val:
                    raise cls._format_import_error(
                        ValueError,
                        "'%s' no es una opción válida de la propiedad "
                        "'%s' (subcampo de '%%(field)s')",
                        (str(val), str(property_dict['string'])))
                property_dict['value'] = new_val

            elif property_type == 'tags':
                tags = val.split(',')
                new_val = []
                for tag in tags:
                    val_tag = next(iter(
                        tag_val for tag_val, tag_label, _color
                        in property_dict['tags']
                        if tag in (tag_val, tag_label)
                    ), None)
                    if not val_tag:
                        raise cls._format_import_error(
                            ValueError,
                            "'%s' no es una etiqueta válida de la propiedad "
                            "'%s' (subcampo de '%%(field)s')",
                            (str(tag), str(property_dict['string'])))
                    new_val.append(val_tag)
                property_dict['value'] = new_val

            elif property_type == 'boolean':
                new_val, ws = cls._str_to_boolean(model, field, val,
                                                  savepoint=savepoint)
                if not ws:
                    property_dict['value'] = new_val
                else:
                    raise cls._format_import_error(
                        ValueError,
                        "Valor desconocido '%s' para la propiedad booleana "
                        "'%s' (subcampo de '%%(field)s')",
                        (str(val), str(property_dict['string'])))

            elif property_type in ('many2one', 'many2many'):
                [record] = property_dict['value']

                subfield, w1 = cls._referencing_subfield(record)
                if w1:
                    warnings.extend(w1)

                values = record[subfield]

                references = (values.split(',')
                              if property_type == 'many2many' else [values])
                ids = []
                fake_field = FakeField(comodel_name=property_dict['comodel'],
                                       name=property_dict['string'])
                for reference in references:
                    id_, ws = cls.db_id_for(model, fake_field, subfield,
                                            reference, savepoint)
                    ids.append(id_)
                    warnings.extend(ws)

                property_dict['value'] = (ids if property_type == 'many2many'
                                          else ids[0])

            elif property_type == 'integer':
                try:
                    property_dict['value'] = int(val)
                except ValueError:
                    raise cls._format_import_error(
                        ValueError,
                        "'%s' no parece un entero para la propiedad '%s' "
                        "(subcampo de '%%(field)s')",
                        (str(val), str(property_dict['string']))) from None

            elif property_type == 'float':
                try:
                    property_dict['value'] = float(val)
                except ValueError:
                    raise cls._format_import_error(
                        ValueError,
                        "'%s' no parece un número para la propiedad '%s' "
                        "(subcampo de '%%(field)s')",
                        (str(val), str(property_dict['string']))) from None

        return value, warnings

    #: El campo de este árbol que porta un ``Properties``.
    _str_to_properties_field = _str_to_properties
