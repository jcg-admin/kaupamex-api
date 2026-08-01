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

Qué NO se porta, con su medición
================================

- **Toda la mitad relacional**: ``db_id_for``, ``_xmlid_to_record_id``,
  ``_referencing_subfield``, ``_str_to_many2one``, ``_str_to_many2many``,
  ``_str_to_one2many``, ``_str_to_many2one_reference``. Resuelven una
  referencia por ``xmlid`` (contra ``ir.model.data``) o por ``name_search``
  (la búsqueda por nombre visible del ORM de Odoo). **Actualizado** (porte de
  ``ir_model.py``): ``grep -rn "^class IrModelData\b" src/`` → **1** clase;
  ``grep -rn "def name_search" src/`` sigue en **0** definiciones. [PROVEN]
  Cambia **uno** de los dos caminos, no los dos: la tabla del ``xmlid``
  existe pero nadie la puebla —falta el cargador declarativo—, y
  ``name_search`` no existe en absoluto. La mitad relacional sigue sin portar
  por la misma razón de fondo; inventar una tercera vía sería inventar
  semántica.
- **``_str_to_properties``** (95 líneas) — convierte contra el campo
  ``Properties`` de Odoo, cuyo esquema vive en un campo hermano
  ``PropertiesDefinition``. El vocabulario los declara como ``JSONField``
  (``orm/fields_properties.py``), sin la maquinaria de definición que este
  converter recorre.
- **Las traducciones de etiquetas** (``_get_boolean_translations``,
  ``_get_selection_translations``, ``code_translations``). Aceptan ``sí``/``oui``
  además de ``yes`` según el idioma del usuario, leyendo el catálogo de
  traducciones de código de Odoo. Aquí la comparación es contra los literales
  en inglés más las etiquetas declaradas en el propio ``choices``, que es de
  donde sale el texto visible en este árbol.
"""
import datetime
import functools
import itertools
import logging

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

_logger = logging.getLogger(__name__)

#: Campos que referencian a otro registro — ``REFERENCING_FIELDS`` verbatim.
REFERENCING_FIELDS = {None, 'id', '.id'}

#: Literales verdaderos, sin traducir (la fuente advierte de no usar valores
#: potencialmente traducidos en esta lista base).
TRUE_LITERALS = ('1', 'true', 'yes')
#: Literales falsos — nótese que la **cadena vacía** cuenta como falso.
FALSE_LITERALS = ('', '0', 'false', 'no')

#: Formatos que el error sugiere al usuario, iguales a los de la fuente.
DATE_HINT = '2012-12-31'
DATETIME_HINT = '2012-12-31 23:59:59'


def only_ref_fields(record):
    """Sólo las claves que referencian — verbatim de la fuente."""
    return {k: v for k, v in record.items() if k in REFERENCING_FIELDS}


def exclude_ref_fields(record):
    """Todo salvo las claves que referencian — verbatim de la fuente."""
    return {k: v for k, v in record.items() if k not in REFERENCING_FIELDS}


class ImportWarning(Warning):
    """Advertencia emitida hacia arriba durante la importación."""


class ConversionNotFound(ValueError):
    """No hay converter para el par (tipo origen, tipo campo)."""


class IrFieldsConverter:
    """Convierte valores de importación a valores de campo (``ir.fields.converter``).

    En la referencia es un ``AbstractModel``; aquí es una clase de métodos de
    clase por la misma razón que ``ir_binary``: no tiene columnas.
    """

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
    def to_field(cls, model, field, fromtype=str):
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
        return functools.partial(converter, model, field)

    @staticmethod
    def _field_type(field):
        """Nombre del tipo de campo, en el vocabulario del despacho.

        En la referencia ``field.type`` ya es ``'boolean'``/``'char'``/…; aquí
        se deriva de la clase de campo de Django, que es su equivalente.
        """
        return type(field).__name__.replace('Field', '').lower() or 'char'

    # === Conversores escalares ============================================

    @classmethod
    def _str_to_boolean(cls, model, field, value):
        """``1``/``true``/``yes`` → True; ``''``/``0``/``false``/``no`` → False."""
        trues = {w.lower() for w in itertools.chain(TRUE_LITERALS)}
        if value.lower() in trues:
            return True, []
        falses = {w.lower() for w in itertools.chain(FALSE_LITERALS)}
        if value.lower() in falses:
            return False, []
        raise cls._format_import_error(
            ValueError,
            "Valor desconocido '%s' para el campo booleano '%%(field)s'",
            value,
            {'moreinfo': "Usa '1' para sí y '0' para no"},
        )

    @classmethod
    def _str_to_integer(cls, model, field, value):
        try:
            return int(value), []
        except ValueError:
            raise cls._format_import_error(
                ValueError,
                "'%s' no parece un entero para el campo '%%(field)s'",
                value,
            ) from None

    @classmethod
    def _str_to_float(cls, model, field, value):
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
    def _str_id(cls, model, field, value):
        """La identidad — la fuente la reusa para varios tipos textuales."""
        return value, []

    # Alias verbatim de la fuente: reference/char/text/binary/html comparten
    # la identidad.
    _str_to_char = _str_id
    _str_to_text = _str_id
    _str_to_binary = _str_id
    _str_to_html = _str_id

    @classmethod
    def _str_to_date(cls, model, field, value):
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
    def _str_to_datetime(cls, model, field, value):
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
    def _str_to_selection(cls, model, field, value):
        """Casa contra el valor interno o la etiqueta, sin distinguir mayúsculas.

        La comparación insensible es explícita en la fuente: permite fijar el
        valor aunque el dato importado no venga con la caja exacta.
        """
        selection = list(getattr(field, 'choices', None) or [])
        needle = value.lower()
        for item, label in selection:
            if needle == str(item).lower() or needle == str(label).lower():
                return item, []
        raise cls._format_import_error(
            ValueError,
            "El valor '%s' no está en el campo de selección '%%(field)s'",
            value,
            {'moreinfo': [str(label or item) for item, label in selection]},
        )
