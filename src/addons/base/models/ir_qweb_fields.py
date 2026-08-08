"""``ir.qweb.field.*`` — los conversores de valor de campo a texto presentable.

Adaptación de ``odoo/addons/base/models/ir_qweb_fields.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 913 líneas). Diecinueve clases, una
por *widget* de ``t-field``: cómo se muestra un entero, un importe, una
duración, una fecha relativa, un contacto.

Estos conversores **valen sin QWeb**. El motor decide *cuándo* llamarlos; lo
que ellos saben es *cómo se escribe* un valor para que lo lea una persona, y
eso no depende del motor. Por eso este archivo se porta aunque su hermano
``ir_qweb.py`` dejara fuera el compilador.

Dónde formatea este árbol — y qué implica
=========================================

El formateo para presentación lo hace el **cliente**: ``ui: src/lib/intl.js``
(medido: el archivo existe). El API devuelve valores crudos — un
``fields.Monetary`` sale como *string* decimal por DRF, una fecha en ISO — y
React los formatea con la locale del navegador.

Consecuencia medida: ``python3 -c "import babel"`` → **ModuleNotFoundError**
[PROVEN]. La referencia apoya en ``babel`` todo lo dependiente de idioma
(``format_timedelta``, ``format_time``, símbolo y posición de la moneda). Sin
esa dependencia, este archivo se parte en dos mitades honestas:

- **Lo independiente de idioma se porta entero y se ejercita**: la
  descomposición en unidades de tiempo, el formato digital ``HH:MM:SS``, el
  troceo de horas fraccionarias, el escape a HTML.
- **Lo dependiente de idioma declara su punto de extensión** y levanta si
  nadie lo conectó, en vez de fabricar un formateo *ad hoc* que compita con el
  de ``intl.js`` y produzca dos formatos distintos para el mismo dato en la
  misma pantalla.

Añadir ``babel`` al backend sólo para esto sería mover la decisión de dónde
se formatea, que está tomada y documentada. Este archivo no la revisita.

``TIMEDELTA_UNITS`` — el dato que hace todo lo demás
====================================================

Las siete unidades con sus segundos, verbatim y **en orden descendente**. El
orden no es decorativo: el algoritmo de ``duration`` recorre la tupla haciendo
``divmod`` y arrastrando el resto, así que invertirla produce "0 años 0 meses
… 3 600 segundos" en vez de "1 hora".

El mes son 30 días y el año 365 — aproximaciones deliberadas de la fuente. Se
copian tal cual: cambiarlas por un cálculo de calendario daría un resultado
*más correcto* y **distinto** del de la referencia para el mismo dato, que es
justo lo que una adaptación fiel evita.

Qué NO se porta, con su medición
================================

- **``IrQwebFieldBarcode``** — genera la imagen del código de barras como
  ``data:`` URI. Medido: ``grep -rn "barcode" pyproject.toml`` → **0**; no hay
  generador de códigos de barras en las dependencias. La clase se declara con
  su punto de extensión.
- **``to_html`` / ``render_element`` / ``attributes``** de la clase base:
  envuelven el valor en el nodo raíz con los atributos ``data-oe-*`` que el
  editor web de Odoo usa para edición en línea. Sin ese editor —este árbol
  edita por formularios React contra DRF— los atributos no tienen lector.
- **``get_available_options``** de cada conversor: describe sus opciones para
  el constructor de vistas de Odoo. Las opciones **sí** se aceptan y se usan
  en ``value_to_html``; lo que no se porta es el catálogo que las anuncia a
  una UI que no existe aquí.
- **``record_to_html`` con ``with_context``**: la propagación de contexto del
  ORM de Odoo. Se porta la firma y la lectura del campo, sin el contexto.
"""
import logging
import re
from decimal import Decimal

import models
from django.utils.html import escape
from django.utils.safestring import mark_safe

_logger = logging.getLogger(__name__)

#: Las siete unidades con sus segundos, **en orden descendente** — verbatim.
#: Ver el docstring del módulo: el orden es parte del algoritmo, y el mes de
#: 30 días y el año de 365 son aproximaciones deliberadas de la fuente.
TIMEDELTA_UNITS = (
    ('year',   'año',     3600 * 24 * 365),
    ('month',  'mes',     3600 * 24 * 30),
    ('week',   'semana',  3600 * 24 * 7),
    ('day',    'día',     3600 * 24),
    ('hour',   'hora',    3600),
    ('minute', 'minuto',  60),
    ('second', 'segundo', 1),
)

#: Segundos por unidad, por nombre.
UNIT_SECONDS = {name: seconds for name, _label, seconds in TIMEDELTA_UNITS}

#: Plural de cada unidad, para el formato largo sin ``babel``.
UNIT_PLURALS = {
    'año': 'años', 'mes': 'meses', 'semana': 'semanas', 'día': 'días',
    'hora': 'horas', 'minuto': 'minutos', 'segundo': 'segundos',
}

_NEWLINE = re.compile(r'\r\n|\r|\n')


def nl2br(text):
    """``nl2br`` — escapa el texto y convierte los saltos de línea en ``<br>``.

    El orden importa y es el de la fuente: **primero** se escapa, **después**
    se insertan las etiquetas. Al revés, un ``<br>`` recién insertado sería
    escapado y el usuario vería el literal.
    """
    escaped = escape(text or '')
    return mark_safe(_NEWLINE.sub('<br>\n', str(escaped)))


def nl2br_enclose(text, enclosure_tag='div'):
    """``nl2br_enclose`` — ``nl2br`` envuelto en una etiqueta.

    La fuente lo justifica así: los saltos de línea los añade el sistema y son
    **de confianza**; el resto del contenido viene del usuario y va escapado.
    Separarlo permite manipular las dos partes sin confundirlas.
    """
    inner = nl2br(text)
    return mark_safe(f'<{enclosure_tag}>{inner}</{enclosure_tag}>')


def format_duration_digital(hours):
    """Horas fraccionarias → ``HH:MM`` (``format_duration`` de la fuente).

    ``1.5`` → ``"01:30"``. El signo va delante del bloque completo, no del
    componente, que es lo que la fuente produce para valores negativos.
    """
    sign = '-' if hours < 0 else ''
    total_minutes = int(round(abs(float(hours)) * 60))
    whole_hours, minutes = divmod(total_minutes, 60)
    return f'{sign}{whole_hours:02d}:{minutes:02d}'


class IrQwebField(models.Model):
    """``ir.qweb.field`` — el conversor base.

    Abstracto en la referencia y abstracto aquí. ``value_to_html`` es el punto
    que cada subtipo redefine.
    """

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        """``value_to_html`` — un valor suelto a su forma presentable.

        Un ``None`` o un ``False`` dan cadena vacía, **no** ``"None"`` ni
        ``"False"``: la fuente lo hace así porque un campo sin valor debe
        verse vacío, no con el nombre de su ausencia.
        """
        if value is None or value is False:
            return ''
        if isinstance(value, bytes):
            value = value.decode()
        return escape(value)

    @classmethod
    def record_to_html(cls, record, field_name, options=None):
        """``record_to_html`` — el campo de un registro, ya convertido."""
        if not record:
            return ''
        value = getattr(record, field_name, None)
        return '' if value is False else cls.value_to_html(value, options)


class IrQwebFieldInteger(IrQwebField):
    """``integer`` — entero con separador de miles."""

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        if value is None or value is False:
            return ''
        # La fuente inserta U+FEFF tras el signo menos para que el navegador
        # no separe el signo del número al hacer salto de línea.
        return f'{int(value):,}'.replace('-', '-\N{ZERO WIDTH NO-BREAK SPACE}')


class IrQwebFieldFloat(IrQwebField):
    """``float`` — decimal con precisión declarada."""

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        if value is None or value is False:
            return ''
        digits = (options or {}).get('precision', 2)
        return f'{Decimal(str(value)):,.{digits}f}'


class IrQwebFieldDate(IrQwebField):
    """``date`` — fecha en ISO 8601.

    La fuente formatea con la locale del usuario (``babel.dates``). Aquí sale
    en **ISO**, que es el contrato que el API ya tiene con ``ui`` y el formato
    que ``intl.js`` espera recibir para presentarlo. No es un formateo
    empobrecido: es el punto de corte declarado entre las dos capas.
    """

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        if not value:
            return ''
        return escape(value.isoformat())


class IrQwebFieldDatetime(IrQwebFieldDate):
    """``datetime`` — fecha y hora en ISO 8601.

    Mismo criterio que ``date``. La fuente además convierte a la zona horaria
    del usuario; aquí el valor viaja en UTC y la zona la aplica el cliente,
    que es donde se sabe cuál es.
    """

    class Meta:
        abstract = True


class IrQwebFieldText(IrQwebField):
    """``text`` — texto con los saltos de línea preservados."""

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        return nl2br(value) if value else ''


class IrQwebFieldSelection(IrQwebField):
    """``selection`` — la **etiqueta** del valor, no el valor."""

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        choices = dict((options or {}).get('selection', ()))
        if value not in choices:
            # La fuente levanta aquí. Un valor fuera de las opciones es un
            # dato corrupto, y mostrarlo crudo lo escondería.
            raise ValueError(
                f'El valor {value!r} no está entre las opciones declaradas.')
        return escape(choices[value])

    @classmethod
    def record_to_html(cls, record, field_name, options=None):
        options = dict(options or {})
        if 'selection' not in options:
            field = record._meta.get_field(field_name)
            options['selection'] = list(field.choices or ())
        return super().record_to_html(record, field_name, options)


class IrQwebFieldMany2one(IrQwebField):
    """``many2one`` — el nombre visible del registro apuntado."""

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        return escape(str(value)) if value else ''


class IrQwebFieldMany2many(IrQwebField):
    """``many2many`` — los nombres, separados por coma."""

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        if not value:
            return ''
        return escape(', '.join(str(item) for item in value))


class IrQwebFieldOne2many(IrQwebFieldMany2many):
    """``one2many`` — igual que ``many2many`` en la fuente."""

    class Meta:
        abstract = True


class IrQwebFieldHtml(IrQwebField):
    """``html`` — contenido HTML **ya saneado**.

    La fuente lo devuelve como ``Markup``: sin escapar. Aquí igual, con el
    mismo requisito que el proyecto ya aplica en ``ui`` con ``dompurify``:
    **el saneo ocurre antes de llegar aquí**. Este conversor no sanea; si se
    le pasa HTML sin sanear, lo emite sin sanear.
    """

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        return mark_safe(value) if value else ''


class IrQwebFieldImage(IrQwebField):
    """``image`` — imagen embebida como ``data:`` URI."""

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        raise NotImplementedError(
            'La imagen se sirve por URL desde ir.binary en este árbol, no '
            'embebida como data: URI. Ver el docstring del módulo.')


class IrQwebFieldImage_Url(IrQwebField):
    """``image_url`` — imagen por URL."""

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        if not value:
            return ''
        return mark_safe(f'<img src="{escape(value)}">')


class IrQwebFieldMonetary(IrQwebField):
    """``monetary`` — importe con su moneda.

    El **punto de extensión declarado**: el símbolo de la moneda y su posición
    (antes o después del número) dependen de la locale, y aquí eso lo resuelve
    ``ui: src/lib/intl.js``. Ver el docstring del módulo sobre por qué no se
    fabrica un formateo paralelo.
    """

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        raise NotImplementedError(
            'El formateo monetario depende de la locale y lo hace el cliente '
            '(ui/src/lib/intl.js). El API devuelve el decimal crudo.')


class IrQwebFieldFloat_Time(IrQwebField):
    """``float_time`` — horas fraccionarias como ``HH:MM`` (``1.5`` → ``01:30``)."""

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        if value is None or value is False:
            return ''
        return format_duration_digital(value)


class IrQwebFieldTime(IrQwebField):
    """``time`` — horas fraccionarias como hora del día (``1.5`` → ``1:30``).

    La unidad del valor son **horas** y la fuente exige ``0 <= value < 24``.
    Los dos límites se conservan como error, no como recorte: un 25 recortado
    a 23:59 escondería el dato malo.
    """

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        if value is None or value is False:
            return ''
        if value < 0:
            raise ValueError(f'El valor ({value}) debe ser positivo.')
        hours, minutes = divmod(int(abs(value) * 60), 60)
        if hours > 23:
            raise ValueError('La hora debe estar entre 0 y 23.')
        return f'{hours}:{minutes:02d}'


class IrQwebFieldDuration(IrQwebField):
    """``duration`` — un número como lapso legible (``1.5`` → ``1 hora 30 minutos``).

    Opciones de la fuente que se conservan:

    - ``unit``: en qué unidad viene el valor (por defecto ``second``);
    - ``round``: hasta qué unidad se redondea (por defecto ``second``);
    - ``digital``: ``01:00`` en vez de ``1 hora``.

    Los sub-segundos se ignoran, igual que allá.
    """

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        if value is None or value is False:
            return ''
        options = options or {}
        factor = UNIT_SECONDS[options.get('unit', 'second')]
        round_to = UNIT_SECONDS[options.get('round', 'second')]
        digital = bool(options.get('digital'))

        # En formato digital nunca se agrupa por encima de la hora: 90 minutos
        # son 01:30, no "1 hora 30" partido en dos columnas.
        if digital and round_to > 3600:
            round_to = 3600

        remainder = round((value * factor) / round_to) * round_to
        sign = ''
        if value < 0:
            remainder = -remainder
            sign = '-'

        if digital:
            sections = []
            for _unit, _label, secs in TIMEDELTA_UNITS:
                if secs > 3600:
                    continue
                amount, remainder = divmod(remainder, secs)
                if not amount and (secs > factor or secs < round_to):
                    continue
                sections.append('%02.0f' % int(round(amount)))
            return sign + ':'.join(sections)

        sections = []
        for _unit, label, secs in TIMEDELTA_UNITS:
            amount, remainder = divmod(remainder, secs)
            amount = int(amount)
            if not amount:
                continue
            noun = label if amount == 1 else UNIT_PLURALS[label]
            sections.append(f'{amount} {noun}')
        if sign:
            sections.insert(0, sign)
        return ' '.join(sections)


class IrQwebFieldRelative(IrQwebField):
    """``relative`` — "hace 3 días" respecto de una fecha de referencia.

    Punto de extensión declarado: la frase depende del idioma
    (``babel.dates.format_timedelta(add_direction=True)`` en la fuente). Lo
    que sí se porta es el **cálculo**: la diferencia contra la referencia.
    """

    class Meta:
        abstract = True

    @classmethod
    def delta_seconds(cls, value, reference):
        """Segundos entre el valor y la referencia — la mitad calculable.

        Negativo = el valor está en el pasado, igual que la resta de la
        fuente (``value - reference``).
        """
        return (value - reference).total_seconds()

    @classmethod
    def value_to_html(cls, value, options=None):
        raise NotImplementedError(
            'La frase relativa depende del idioma y la compone el cliente. '
            'Use delta_seconds() para el cálculo.')


class IrQwebFieldBarcode(IrQwebField):
    """``barcode`` — imagen del código de barras.

    No portado: medido ``grep -n "barcode" pyproject.toml`` → **0**; no hay
    generador en las dependencias. Se declara la clase para que el mapa de
    conversores esté completo y el punto de extensión sea explícito.
    """

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        raise NotImplementedError(
            'No hay generador de códigos de barras en las dependencias de '
            'este árbol.')


class IrQwebFieldContact(IrQwebField):
    """``contact`` — la ficha de un contacto compuesta desde sus campos.

    Se porta la **composición de la dirección**, que es lógica de datos: el
    orden de las líneas y el descarte de las vacías. El marcado concreto lo
    pone la UI.
    """

    class Meta:
        abstract = True

    #: Orden de las líneas de una dirección, de lo más específico a lo más
    #: general. Es el orden postal, no el de declaración del modelo.
    ADDRESS_FIELDS = ('street', 'street2', 'zip', 'city', 'state', 'country')

    @classmethod
    def address_lines(cls, record):
        """Las líneas no vacías de la dirección, en orden postal."""
        lines = []
        for name in cls.ADDRESS_FIELDS:
            value = getattr(record, name, None)
            if not value:
                continue
            lines.append(str(value))
        return lines

    @classmethod
    def value_to_html(cls, value, options=None):
        if not value:
            return ''
        return escape(' — '.join(cls.address_lines(value)) or str(value))


class IrQwebFieldQweb(IrQwebField):
    """``qweb`` — renderiza una plantilla dentro del campo.

    No portado: depende del compilador, que ``ir_qweb.py`` deja fuera con su
    razón medida.
    """

    class Meta:
        abstract = True

    @classmethod
    def value_to_html(cls, value, options=None):
        raise NotImplementedError(
            'Requiere el compilador de QWeb, no portado (ver ir_qweb.py).')
