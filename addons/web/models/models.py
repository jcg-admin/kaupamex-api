"""``web`` — capa de datos del cliente web. Adaptación de Odoo, licencia LGPL-3.

Fuente: ``odoo19c: addons/web/models/models.py`` (``odoo-tools@622ddc2a``,
2360 líneas). Cáscara de solo controladores hasta H-API-369 / DEC-FW-04
(2026-08-07). Primer pase (mismo día): 11 portados, 29 declarados ausentes
citando "sin consumidor, vista arch XML" (React explícito, DEC-03) para
``read_group`` (11 símbolos) y ``search_panel`` (7 símbolos) — esa razón
describía el estado a cambiar, no un bloqueo técnico (H-API-378: dos corridas
posteriores heredaron el docstring como si fuera decisión cerrada y no
cerraron nada; 3.7 M tokens, 0 símbolos). Segundo pase (mismo día,
``odoo-tools@622ddc2a``): se **cerraron** ambas familias con código
funcionando.

Medición símbolo-por-símbolo por AST (``scripts/pendientes_cascara.py``,
mide ``def``/``class`` por nombre, no substring — ver ``h-api-373``): **60**
símbolos de 4 clases (``lazymapping``, ``Base``, ``ResCompany``,
``RecordSnapshot``). **44 portados** (11 del primer pase + 21 del segundo:
9 de ``read_group`` + 4 formatters anidados + 7 de ``search_panel`` + 1
``get_parent_id`` anidado; + 8 del tercero: ``_web_read_group_fill_temporal``,
``onchange`` y ``RecordSnapshot`` con sus 5 métodos). **16 declarados
ausentes**, cada uno con razón medida **hoy** — ver abajo. Ninguna ausencia
hereda la redacción de un pase anterior.

Tercer pase (tarea #250) — el barrido de razones caducadas
===========================================================

Una razón de ausencia que cita un ``grep`` con resultado cero **caduca en
silencio**: el árbol crece, el cero deja de ser cierto, y la ausencia sigue
leyéndose como decisión cerrada. Es la misma forma que ``h-api-378`` ya
registró para este archivo, un nivel más abajo — allá se heredaba la
redacción, aquí se hereda la medición.

Las tres razones que este archivo declinaba con un cero se volvieron a
correr. **Ninguna de las tres seguía dando cero:**

.. code-block:: text

   grep -rln "date_utils|def start_of" src/tools/*.py src/orm/*.py
       citado: 0    hoy: 3   (src/tools/date_utils.py, orm/domains.py,
                              orm/fields_temporal.py)
   grep -rln "_update_cache|field_computed|def modified(|_apply_onchange_methods"
        src/orm/*.py src/addons/*/models/*.py
       citado: 0    hoy: 1   (orm/environments.py)
   grep -rln "update_field_translations|get_installed(" src/ --include="*.py"
       citado: 0    hoy: 2   (orm/models.py, base/models/res_partner.py)

Y las tres caducaron por motivos distintos, que es lo que hace falta separar
antes de decidir:

- La **primera** caducó de verdad: ``src/tools/date_utils.py`` existe, con
  ``start_of``/``end_of``/``date_range``/``weeknumber``. El símbolo se porta.
- La **segunda** caduca a medias. Su único acierto de hoy es una mención en
  un docstring, no un mecanismo; pero el comando miraba los símbolos
  equivocados — el árbol **sí** tiene ``@api.onchange``
  (``orm/decorators.py:37``), ``NewId`` (``orm/identifiers.py:16``),
  ``OriginMixin._origin`` (``orm/models.py:416``) y el grafo de dependencias
  (``orm.registry.field_depends``, ``registry.py:498``). Lo que faltaba era
  el **despachador**, y eso se construye: se porta.
- La **tercera** caduca sólo como instrumento: sus dos aciertos son prosa en
  docstrings. El mecanismo sigue ausente y **su sucesor ya estaba nombrado**
  en el árbol, en dos tareas distintas. Se repunta la razón a una medición
  que sí mide el mecanismo, y se citan los sucesores.

La lección operativa, y aplica a toda razón de ausencia de este árbol: un
``grep`` de **menciones** no mide un mecanismo. La forma que discrimina es
``def <símbolo>``, que no la satisface un docstring que nombre al símbolo
para decir que no está.

Recordset (Odoo) → QuerySet (Django) — la adaptación estructural
==================================================================

La referencia opera sobre un *recordset*: ``self`` puede contener 0..N ids
simultáneamente, y ``web_read``/``web_search_read``/``web_name_search`` son
métodos de instancia que leen ese conjunto. Django separa instancia
(una fila) de manager/queryset (N filas) — no hay tercer tipo que sea "0..N
filas con métodos propios". La adaptación:

- Los métodos que en la referencia procesan **varios registros a la vez**
  (``web_read``, ``web_search_read``, ``web_name_search``, ``web_save_multi``,
  ``web_resequence``, ``read_progress_bar``, ``_add_groupby_values``, y toda
  la familia ``read_group``/``search_panel`` del segundo pase) se portan como
  **``classmethod``** que reciben el ``QuerySet`` explícito en vez de leerlo
  de ``self`` — es la misma información (qué filas), pasada por parámetro en
  lugar de estado implícito del recordset.
- Los métodos que la referencia documenta como operando sobre **un solo
  registro objetivo** (``web_save``, que hace ``self.write`` o ``self =
  self.create(vals)``) se portan como método de **instancia** — ``self`` es
  la fila, igual que en la referencia cuando ``self`` tiene 0 o 1 registro.

Portados (44, adaptados)
=========================

Primer pase (11): ``lazymapping.__missing__`` · ``AND``/``OR`` (módulo) ·
``web_name_search`` · ``web_search_read`` · ``_format_web_search_read_results``
· ``web_save`` · ``web_save_multi`` · ``web_read`` · ``web_resequence`` ·
``_get_read_group_order`` · ``_add_groupby_values`` · ``read_progress_bar``.

Segundo pase — familia ``read_group`` (9 + 4 formatters anidados):
``web_read_group`` · ``_formatted_read_group_with_length`` · ``_open_groups``
· ``formatted_read_grouping_sets`` · ``formatted_read_group`` ·
``_web_read_group_field_expand`` · ``_web_read_group_expand`` ·
``_web_read_group_format`` · ``_web_read_group_groupby_formatter`` (fábrica
que produce ``formatter_many2one``/``formatter_many2many``/
``formatter_time_granularity``/``formatter_date_number_granularity``).
``.values().annotate()``/``.aggregate()`` de Django reemplaza el ``_read_group``
propio de Odoo; ``Trunc*``/``Extract*`` de ``django.db.models.functions``
reemplazan la resolución de granularidad temporal. Divergencia declarada: las
etiquetas de bucket temporal usan ``strftime``/ISO, no ``babel`` (ausente del
proyecto — ver "Ausentes" más abajo) — funcionales, no localizadas.
``formatter_follow_many2one`` de la referencia (recursión sobre
``campo.subcampo``) colapsa en un único lookup Django (``campo__subcampo``);
no existe como closure aparte porque no hace falta.

Segundo pase — familia ``search_panel`` (7 + 1 ``get_parent_id`` anidado):
``_search_panel_domain_image`` · ``_search_panel_field_image`` ·
``_search_panel_global_counters`` · ``_search_panel_sanitized_parent_hierarchy``
(con ``get_parent_id``) · ``_search_panel_selection_range`` ·
``search_panel_select_range`` · ``search_panel_select_multi_range``.
Divergencia declarada: la jerarquía usa la convención de campo literal
``parent_id`` (Many2one autorreferente) en vez de un ``_parent_name``
configurable (no existe esa metadata en este ORM); y
``search_panel_select_multi_range`` no soporta ``group_by``/``group_domain``
(agrupar valores del filtro por un segundo campo) — pieza acotada de un
método por lo demás completo, sin consumidor que fije su forma, distinto de
declarar el método entero ausente.

Tercer pase — ``fill_temporal`` (1) y el formulario (6)
=======================================================

``_web_read_group_fill_temporal`` rellena los huecos de una serie temporal
(Jun-Sep-Dic → Jun..Dic) para que el gráfico no pegue Diciembre contra
Septiembre. Se apoya en ``date_utils.start_of``/``date_range``, y llega a
``formatted_read_group``/``formatted_read_grouping_sets`` por un parámetro
``fill_temporal`` explícito en vez de la clave de contexto de la referencia
— misma convención por la que ``queryset`` reemplaza a ``domain``. La
ausencia de ``babel`` **deja de bloquearlo**: la referencia consulta el
locale sólo para corregir el inicio de semana, y aquí los dos extremos
—``TruncWeek`` de Django y ``date_utils.start_of(v, 'week')``— son ISO, así
que el desfase es cero por construcción.

``onchange`` + ``RecordSnapshot`` (5 métodos) portan el recálculo de
formulario: aislar lo cambiado, fotografiar el registro virtual, despachar
los ``@api.onchange`` del campo tocado, repetir mientras algún método siga
moviendo campos de la especificación, y devolver el diff de las dos fotos
más los avisos fusionados. El registro virtual es una copia sin guardar que
conserva el ``pk`` —así ``OriginMixin._origin`` sigue resolviendo a la fila,
que es lo que un ``@api.onchange`` compara—, y ``self`` nunca se muta.

Lo que ese porte **no** trae, medido: el ``record.modified(...)`` de la
referencia (``:2148``), que propaga el cambio por el grafo de dependencias e
invalida los campos calculados **con columna**. Aquí un cálculo sin columna
es una ``property`` que la foto final ya ve; uno con columna se recalcula en
``save()``. El grafo existe (``orm.registry.field_depends``); falta el motor
que lo recorra, y ése es un mecanismo de ``src/orm/models.py``, no un símbolo
de este archivo. El alcance de lo que desbloquearía son los ``@api.onchange``
ya declarados en el árbol —los despacha **todos** este método; lo que espera
es la cascada—, y el conteo lo publica el comando en vez de transcribirse
aquí, porque crece con el árbol:

.. code-block:: bash

   grep -rn "@api.onchange" src/ addons/ --include='*.py'

**Sucesor registrado — tarea #273:** *motor de recálculo de campos
calculados sobre registro virtual*, en ``src/orm/models.py``, con condición de
cierre medible — que ``def modified`` exista ahí y que ``onchange`` lo
invoque.

Ausentes (16) — con razón medida hoy, no heredada
====================================================

**``_web_read_group_groupby_properties_formatter`` (1 método) + sus 5
formatters anidados** (``formatter_property_selection``,
``formatter_property_many2one``, ``formatter_property_many2many``,
``formatter_property_tags``, ``formatter_property_datetime``). El campo
``properties`` es un ``JSONField`` liso (``orm/fields_properties.py``) sin la
metadata por-clave (``type``/``comodel``/``selection``/``tags``) que estos
formatters necesitan para decidir cómo agrupar cada propiedad — mismo hueco
ya documentado en ``web_read`` (rama ``properties`` de este mismo archivo).

**Cuatro closures internos** (``cleanup``, ``adapt``,
``formatter_follow_many2one``, ``group_id_name``). Los cuatro desaparecen
por la forma del puerto, no por una pieza que falte, y cada uno con su razón
propia:

- ``cleanup`` (dentro de ``web_read``) des-envuelve el ``NewId`` del ``id``
  de un registro virtual. Con ``onchange`` ya portado la razón vieja —*"sin
  onchange no hay NewId fluyendo"*— **ya no es la correcta**: la razón real
  es que el diff del formulario no pasa por ``web_read``. La referencia
  formatea los escalares con ``self.record.web_read(...)`` (``:2313``); aquí
  no puede, porque ``web_read`` de este módulo lee de un ``QuerySet`` y el
  registro del formulario no tiene fila. Los valores salen del propio
  snapshot, así que ``web_read`` sigue viendo sólo filas reales.
- ``adapt`` (dentro de ``read_progress_bar``) des-envuelve el ``(id,
  etiqueta)`` que ``formatted_read_group`` devuelve para un many2one. Aquí
  ``read_progress_bar`` agrega con ``.values().annotate()`` directo y nunca
  ve una tupla — es la divergencia que su propio docstring ya declara.
- ``formatter_follow_many2one`` recorre ``campo.subcampo`` recursivamente;
  aquí el path punteado colapsa en un único lookup Django (``campo__subcampo``).
- ``group_id_name`` (tres copias en las ramas de ``search_panel``) elige entre
  devolver el valor crudo o el par ``(valor, etiqueta)``; en el puerto esa
  decisión está en línea en cada rama, sin closure con nombre.

**``ResCompany`` (clase, 4 métodos: ``create``, ``write``,
``_get_asset_style_b64``, ``_update_asset_style``).** Regeneran un adjunto
CSS por-compañía (``web.asset_styles_company_report``) desde
``primary_color``/``secondary_color`` vía ``ir.qweb._render``. Medido hoy:
``grep -rn "styles_company_report" src/addons/`` → **0** (no existe ese
adjunto/vista); ``grep -n "def _render" src/addons/base/models/ir_template_expressions.py``
→ **0** — el compilador de QWeb no está portado y su ``render`` levanta
``NotImplementedError`` a propósito (``ir_template_expressions.py:708-720``).

  El segundo comando **se corrigió en el tercer pase**: citaba
  ``src/addons/*/models/template_expressions.py``, archivo que no existe (el
  puerto se llama ``ir_template_expressions.py``). Un ``grep`` contra una
  ruta inexistente falla y publica cero, así que el cero era del instrumento
  y no del árbol — la ceguera que ``metrica-decide-la-conclusion.md`` llama
  sub-patrón D. Contra el archivo real, ``_render`` da **2** aciertos, los
  dos en el docstring que enumera lo que no se porta.

El pipeline de *assets* de este proyecto ya es una decisión tomada, no una
laguna: ``base/models/assetsbundle.py`` documenta que Webpack (``ui``)
reemplaza el empaquetador dinámico de Odoo — no hay *bundle* CSS por-compañía
que invalidar en cada request porque no hay *bundle* dinámico de ningún tipo.

**``web_override_translations`` (1 método).** Sobrescribe la traducción
inline de un campo para el idioma activo. Su cuerpo consume dos símbolos que
el árbol no define: ``res.lang.get_installed()`` y
``update_field_translations``. Medido hoy con la forma que discrimina —una
**definición**, no una mención—: ``grep -rn "def update_field_translations\\|def
get_installed" src/ --include="*.py"`` → **0**.

  La razón vieja citaba ``grep -rln "update_field_translations|get_installed("``
  sin ``def``, y ese comando **hoy da 2**: sus dos aciertos son prosa en
  docstrings que nombran los símbolos **para decir que faltan**
  (``orm/models.py:1173`` y ``base/models/res_partner.py:2083``). El cero
  había caducado como instrumento sin que el mecanismo cambiara.

Y no es una razón sin sucesor: los dos que faltan **ya tienen tarea
nombrada** en el árbol, cada uno por su cuenta.

- ``update_field_translations`` espera al almacenamiento por idioma. La
  referencia guarda el campo traducible como columna ``jsonb``
  ``{lang: valor}``; aquí ``translate=True`` se **anota** en el campo
  (``field.odoo_translate``) y la columna sigue siendo ``varchar``. Sucesor:
  tarea **#333**, ya citada en ``orm/fields_textual.py:165`` y en
  ``orm/models.py:1177`` (donde ``copy_translations`` está bloqueado por lo
  mismo). El alcance de ese almacenamiento —una columna ``jsonb`` y su
  migración por cada campo que hoy declara la bandera— lo publica el propio
  comando, y aquí se nombra en vez de transcribirse: es una propiedad del
  árbol, que crece, no un hecho de este archivo.

  .. code-block:: bash

     # el conteo del día; descontar migraciones y los dos archivos del ORM
     # que sólo documentan la bandera, que no declaran campo
     grep -rn "translate=True" src/ addons/ --include='*.py' | grep -v /migrations/
- ``get_installed`` espera a la tarea **#104**, citada en
  ``base/models/res_partner.py:2085``.

Portar el método sin esas dos piezas sólo cabría como cuerpo que levanta o
que no escribe nada — un símbolo que el gate de porte contaría como presente
y que no traduciría nada. Eso es un verde que no discrimina, así que se
declara ausente con sus dos sucesores en vez de fabricarlo.
"""
import inspect
import re
from collections import defaultdict
from datetime import datetime

from dateutil.relativedelta import relativedelta

from django.contrib.postgres.aggregates import ArrayAgg, BoolAnd, BoolOr
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.db.models.functions import (
    ExtractDay, ExtractHour, ExtractMinute, ExtractMonth, ExtractQuarter,
    ExtractSecond, ExtractWeek, ExtractYear, TruncDay, TruncMonth,
    TruncQuarter, TruncWeek, TruncYear,
)

from addons.base.models.ir_model import Base as _BaseRoot
from exceptions import UserError
from orm.domains import AND as _domain_and
from orm.domains import OR as _domain_or
from tools import date_utils
from tools.translate import _

__all__ = ['lazymapping', 'AND', 'OR', 'Base', 'RecordSnapshot']

#: ≙ referencia ``MAX_NUMBER_OPENED_GROUPS`` (``models.py:29``).
MAX_NUMBER_OPENED_GROUPS = 10

#: Granularidades de "bucket" temporal (``Trunc*``) — ≙ referencia
#: ``READ_GROUP_TIME_GRANULARITY`` (``odoo/models.py``), sin las etiquetas
#: localizadas (ver cabecera del módulo).
_READ_GROUP_TRUNC = {
    'day': TruncDay, 'week': TruncWeek, 'month': TruncMonth,
    'quarter': TruncQuarter, 'year': TruncYear,
}

#: Granularidades numéricas (``Extract*``) — ≙ referencia
#: ``READ_GROUP_NUMBER_GRANULARITY``. ``day_of_year``/``day_of_week`` de la
#: referencia no están: Django no expone un lookup de fecha ``__`` que
#: coincida 1:1 con el ``doy``/``dow`` de PostgreSQL para filtrar (sí para
#: extraer) sin SQL crudo — quedan fuera de esta iteración.
_READ_GROUP_NUMBER_GRANULARITY = {
    'year_number': ('year', ExtractYear),
    'quarter_number': ('quarter', ExtractQuarter),
    'month_number': ('month', ExtractMonth),
    'iso_week_number': ('week', ExtractWeek),
    'day_of_month': ('day', ExtractDay),
    'hour_number': ('hour', ExtractHour),
    'minute_number': ('minute', ExtractMinute),
    'second_number': ('second', ExtractSecond),
}

#: Paso de cada granularidad temporal — ≙ referencia
#: ``READ_GROUP_TIME_GRANULARITY`` (``odoo19c: odoo/orm/utils.py:22-29``),
#: verbatim salvo ``hour``, que no está en :data:`_READ_GROUP_TRUNC` (Django
#: expone ``TruncHour``, pero ninguna granularidad horaria llegó a este porte).
#: Lo consume :meth:`Base._web_read_group_fill_temporal` para avanzar de un
#: cubo al siguiente.
_READ_GROUP_TIME_GRANULARITY = {
    'day': relativedelta(days=1),
    'week': relativedelta(days=7),
    'month': relativedelta(months=1),
    'quarter': relativedelta(months=3),
    'year': relativedelta(years=1),
}

#: ``campo:agregador`` de la referencia → expresión Django. ``bool_and``/
#: ``bool_or``/``array_agg``/``array_agg_distinct`` vía
#: ``django.contrib.postgres.aggregates`` (motor PostgreSQL, ADR-028).
_READ_GROUP_AGGREGATORS = {
    'sum': Sum, 'avg': Avg, 'max': Max, 'min': Min,
    'count': lambda f: Count(f),
    'count_distinct': lambda f: Count(f, distinct=True),
    'bool_and': BoolAnd, 'bool_or': BoolOr,
    'array_agg': lambda f: ArrayAgg(f),
    'array_agg_distinct': lambda f: ArrayAgg(f, distinct=True),
}

#: ≙ referencia ``SEARCH_PANEL_ERROR_MESSAGE`` (``models.py:28``).
SEARCH_PANEL_ERROR_MESSAGE = _('Demasiados elementos para mostrar.')


# === Utilidades de módulo ====================================================
# ≙ referencia ``models.py:34-48`` (``lazymapping``, ``AND``, ``OR``).

class lazymapping(defaultdict):
    """≙ referencia ``lazymapping`` — ``defaultdict`` que memoiza por clave.

    Genérica, sin acoplamiento a Odoo; se porta verbatim como utilidad
    disponible para quien retome la familia ``read_group`` (ver cabecera).
    """

    def __missing__(self, key):
        value = self.default_factory(key)
        self[key] = value
        return value


def AND(domains):
    """≙ referencia ``AND(domains)`` — conjunción de dominios.

    Divergencia declarada: la referencia combina listas polacas de leaves
    vía ``Domain.AND`` y devuelve otra lista polaca; aquí los dominios ya
    son objetos ``Q`` (``orm/domains.py``), así que se delega directo y el
    retorno es un ``Q``, no una lista.
    """
    return _domain_and(domains)


def OR(domains):
    """≙ referencia ``OR(domains)`` — disyunción de dominios. Misma
    divergencia de tipo de retorno que :func:`AND`."""
    return _domain_or(domains)


# === Helpers de introspección — no existen en la referencia ================
# Estos NO son símbolos portados: son el pegamento que traduce
# ``self._fields[name].type in ('many2one', ...)`` (metadata Odoo) a
# ``model._meta.get_field(name).many_to_one`` (metadata Django), porque el
# "ORM" de este proyecto es Django liso reexportado bajo nombres Odoo
# (``orm/models.py``: ``from django.db.models import *``) — no hay registro
# de campos con ``.type`` propio que replicar.

def _split_field_kinds(model, field_names):
    """Separa ``field_names`` en (escalares/FK-simple, x2many) según Django.

    ``many_to_one``/``one_to_one`` se leen junto con los escalares porque
    ``QuerySet.values()`` ya los trae como el id crudo, igual que
    ``self.read()`` de la referencia antes de la expansión por
    ``field_spec``. ``one_to_many``/``many_to_many`` no caben en
    ``.values()`` con la misma forma (cardinalidad N por fila) — se
    resuelven aparte en :meth:`Base.web_read`.
    """
    scalar, to_many = [], []
    for name in field_names:
        try:
            field = model._meta.get_field(name)
        except FieldDoesNotExist:
            scalar.append(name)
            continue
        if getattr(field, 'many_to_many', False) or getattr(field, 'one_to_many', False):
            to_many.append(name)
        else:
            scalar.append(name)
    return scalar, to_many


class Base(_BaseRoot):
    """≙ referencia ``Base(models.AbstractModel): _inherit = 'base'``.

    Extiende el ``Base`` abstracto raíz (``addons.base.models.ir_model.Base``)
    — el mismo destino que ese archivo documenta como blanco de toda cita
    ``_inherit = 'base'`` de la referencia (``ir_model.py:209``). Igual que
    ese ``Base``, **no está en el MRO de ningún modelo concreto todavía**
    (medido: ``grep -rn "models.Base)" src/addons`` → 0 hits) — mismo estado
    "raíz aspiracional, sin wiring" ya documentado ahí, no una regresión de
    este porte.
    """

    class Meta:
        abstract = True

    # --- web_name_search / web_search_read ---------------------------------

    @classmethod
    def web_name_search(cls, name, specification, domain=None, operator='icontains',
                         limit=100, name_field='name'):
        """≙ referencia ``web_name_search`` (``models.py:55-67``).

        Divergencia declarada: la referencia usa ``self.name_search`` (que
        resuelve internamente el/los campo(s) de nombre del modelo, incluido
        ``rec_name`` compuesto). Aquí no hay ese registro — ``name_field``
        se pasa explícito (default ``'name'``) porque no todo modelo lo
        declara igual (p. ej. ``ResPartner`` compone desde varios campos).
        """
        qs = cls._default_manager.all()
        if domain is not None:
            qs = qs.filter(domain)
        if name:
            qs = qs.filter(**{'%s__%s' % (name_field, operator): name})
        qs = qs[:limit]

        if len(specification) == 1 and 'display_name' in specification:
            return [{'id': obj.pk, 'display_name': str(obj)} for obj in qs]
        return cls.web_read(qs, specification)

    @classmethod
    def web_search_read(cls, domain, specification, offset=0, limit=None,
                         order=None, count_limit=None):
        """≙ referencia ``web_search_read`` (``models.py:68-72``)."""
        qs = cls._default_manager.filter(domain) if domain is not None else cls._default_manager.all()
        if order:
            qs = qs.order_by(*(part.strip() for part in order.split(',')))
        full_qs = qs
        if offset:
            qs = qs[offset:]
        if limit:
            qs = qs[:limit]
        values_records = cls.web_read(qs, specification)
        return cls._format_web_search_read_results(full_qs, values_records, offset, limit, count_limit)

    @staticmethod
    def _format_web_search_read_results(full_queryset, records, offset=0, limit=None, count_limit=None):
        """≙ referencia ``_format_web_search_read_results`` (``models.py:73-91``).

        ``full_queryset`` reemplaza ``self.search_count(domain, ...)``: aquí
        no hay un ``self`` recordset del que recortar el ``count`` — se pasa
        el queryset completo (sin offset/limit) explícito.
        """
        if not records:
            return {'length': 0, 'records': []}
        current_length = len(records) + offset
        limit_reached = len(records) == limit
        count_limit_reached = bool(count_limit) and count_limit <= current_length
        if limit and ((limit_reached and not count_limit_reached)):
            total = full_queryset.count()
            length = min(total, count_limit) if count_limit else total
        else:
            length = current_length
        return {'length': length, 'records': records}

    # --- web_save / web_save_multi ------------------------------------------

    def web_save(self, vals, specification, next_id=None):
        """≙ referencia ``web_save`` (``models.py:92-100``).

        ``self`` es UN registro (con o sin ``pk``) — ≙ la referencia cuando
        el recordset tiene 0 o 1 elementos. Con ``pk`` hace *write*; sin
        ``pk``, *create* (equivalente a ``self.create(vals)`` de la
        referencia, aquí como guardado del objeto ya instanciado).
        """
        for field_name, value in vals.items():
            setattr(self, field_name, value)
        self.save()
        target = self
        if next_id:
            target = type(self)._default_manager.get(pk=next_id)
        qs = type(self)._default_manager.filter(pk=target.pk)
        return type(self).web_read(qs, specification)

    @classmethod
    def web_save_multi(cls, records, vals_list, specification):
        """≙ referencia ``web_save_multi`` (``models.py:101-110``).

        ``records`` reemplaza al ``self`` recordset — se recibe la lista de
        instancias explícita en vez de leerla del estado implícito.
        """
        records = list(records)
        if len(records) != len(vals_list):
            raise ValueError('Each record must have a corresponding vals entry.')
        for record, vals in zip(records, vals_list):
            for field_name, value in vals.items():
                setattr(record, field_name, value)
            record.save()
        qs = cls._default_manager.filter(pk__in=[r.pk for r in records])
        return cls.web_read(qs, specification)

    # --- web_read -------------------------------------------------------------

    @classmethod
    def web_read(cls, records, specification):
        """≙ referencia ``web_read`` (``models.py:111-323``, 212 líneas).

        ``records`` es el ``QuerySet`` a leer — ≙ el ``self`` recordset de la
        referencia, recibido explícito (ver nota de adaptación al inicio del
        módulo). Expande ``many2one``/``one2many``/``many2many`` de forma
        recursiva, igual que la fuente.

        Tres ramas de la fuente NO se replican (declaradas, no calladas):

        - ``reference``/``many2one_reference`` (FK polimórfico): ``orm/
          fields_reference.py`` los mapea a ``GenericForeignKey`` pero
          ningún addon portado lo usa (comentario propio del archivo,
          ``fields_reference.py:6``) — no hay caso real que fije el contrato
          de expansión.
        - ``properties``: ``orm/fields_properties.py`` mapea ``Properties``
          a ``JSONField`` liso, sin la metadata por-clave
          (``type``/``comodel``) que la fuente usa para decidir si expandir
          cada propiedad — no hay qué expandir.
        - El filtro de seguridad por fila de los x2many (``ir.model.access``
          + ``sudo`` + ``_filtered_access`` de la fuente): este proyecto
          autoriza por CAPACIDAD en la vista DRF (DEC-11), no por fila a
          nivel de modelo — ese filtro es responsabilidad del
          ``permission_class`` que invoque este helper, no de ``web_read``.
        """
        model = records.model
        fields_to_read = list(specification) or ['id']

        if fields_to_read == ['id']:
            return [{'id': pk} for pk in records.values_list('pk', flat=True)]

        scalar_fields, to_many_fields = _split_field_kinds(model, fields_to_read)
        base_fields = ['id'] + [f for f in scalar_fields if f != 'id']
        values_list = list(records.values(*base_fields))

        if not values_list:
            return values_list

        values_by_id = {v['id']: v for v in values_list}

        # many2one / one2one — vienen ya como el id crudo en `values()`.
        for field_name in scalar_fields:
            if field_name == 'id':
                continue
            try:
                field = model._meta.get_field(field_name)
            except FieldDoesNotExist:
                continue
            if not getattr(field, 'many_to_one', False) and not getattr(field, 'one_to_one', False):
                continue
            field_spec = specification.get(field_name) or {}
            if 'fields' not in field_spec:
                continue

            related_model = field.related_model
            related_ids = {v[field_name] for v in values_list if v.get(field_name) is not None}
            extra_fields = dict(field_spec['fields'])
            want_display_name = extra_fields.pop('display_name', None) is not None

            related_qs = related_model._default_manager.filter(pk__in=related_ids)
            related_data = {r['id']: r for r in cls.web_read(related_qs, extra_fields)} if extra_fields else {
                obj.pk: {'id': obj.pk} for obj in related_qs
            }
            if want_display_name:
                for obj in related_qs:
                    related_data.setdefault(obj.pk, {'id': obj.pk})['display_name'] = str(obj)

            for values in values_list:
                fk_id = values.get(field_name)
                values[field_name] = related_data.get(fk_id, False) if fk_id is not None else False

        # one2many / many2many — no caben en `.values()`; se resuelven aparte.
        for field_name in to_many_fields:
            field_spec = specification.get(field_name)
            if not field_spec:
                continue

            field = model._meta.get_field(field_name)
            related_model = field.related_model
            owner_ids = list(values_by_id.keys())

            pairs = list(
                model._default_manager.filter(pk__in=owner_ids)
                .values_list('pk', '%s__pk' % field_name)
            )
            related_ids_by_owner = defaultdict(list)
            all_related_ids = set()
            for owner_id, rel_id in pairs:
                if rel_id is not None:
                    related_ids_by_owner[owner_id].append(rel_id)
                    all_related_ids.add(rel_id)

            limit = field_spec.get('limit')
            if limit is not None:
                for owner_id in list(related_ids_by_owner):
                    related_ids_by_owner[owner_id] = related_ids_by_owner[owner_id][:limit]

            if 'fields' in field_spec:
                related_qs = related_model._default_manager.filter(pk__in=all_related_ids)
                related_data = {r['id']: r for r in cls.web_read(related_qs, field_spec['fields'])}

            for owner_id, values in values_by_id.items():
                ids = related_ids_by_owner.get(owner_id, [])
                if 'fields' in field_spec:
                    values[field_name] = [related_data.get(i) or {'id': i} for i in ids]
                else:
                    values[field_name] = ids

        return values_list

    # --- web_resequence ---------------------------------------------------

    @classmethod
    def web_resequence(cls, records, specification, field_name='sequence', offset=0):
        """≙ referencia ``web_resequence`` (``models.py:324-350``).

        ``records`` reemplaza al ``self`` recordset ordenado — se recibe la
        lista/queryset ya en el orden deseado (la referencia asume lo mismo:
        "starts at the first record of ``ids``").
        """
        try:
            cls._meta.get_field(field_name)
        except FieldDoesNotExist:
            return []

        records = list(records)
        for i, record in enumerate(records, start=offset):
            setattr(record, field_name, i)
            record.save(update_fields=[field_name])

        qs = cls._default_manager.filter(pk__in=[r.pk for r in records])
        return cls.web_read(qs, specification)

    # --- read_group: bloques de construcción autocontenidos -----------------
    # Portados en el primer pase (2026-08-07), antes del resto de la familia
    # ``read_group`` (portada en el segundo pase del mismo día, más abajo,
    # después de ``read_progress_bar``): son autocontenidos y ya los usa
    # ``web_read_group``/``_open_groups``.

    @classmethod
    def _get_read_group_order(cls, dict_order, groupby, aggregates):
        """≙ referencia ``_get_read_group_order`` (``models.py:559-585``).

        Divergencia declarada: la referencia usa ``field.aggregator`` (p.
        ej. ``fields.Integer(aggregator='sum')``) para inferir el agregado
        por defecto de un campo sin especificación explícita en
        ``aggregates``. Ese atributo no existe en ``orm/fields*.py``
        (medido: ``grep -n aggregator src/orm/*.py`` → vacío) — la rama se
        degrada con ``getattr(field, 'aggregator', None)`` y simplemente no
        aporta término de orden cuando falta, en vez de fallar.
        """
        if not dict_order:
            return ', '.join(groupby)

        groupby = list(groupby)
        order_spec = []
        for fname, direction in dict_order.items():
            if fname == '__count':
                order_spec.append('%s %s' % (fname, direction))
                continue
            matched = False
            for group in list(groupby):
                if fname == group or group.startswith('%s:' % fname):
                    groupby.remove(group)
                    order_spec.append('%s %s' % (group, direction))
                    matched = True
                    break
            if matched:
                continue
            for agg_spec in aggregates:
                if agg_spec.startswith('%s:' % fname):
                    order_spec.append('%s %s' % (agg_spec, direction))
                    matched = True
                    break
            if matched:
                continue
            field = None
            try:
                field = cls._meta.get_field(fname)
            except FieldDoesNotExist:
                pass  # silent OK because fname puede ser un alias de agregado
                      # sin campo propio (p. ej. "field:sum"); field queda
                      # None y la rama de abajo simplemente no aporta orden.
            aggregator = getattr(field, 'aggregator', None) if field is not None else None
            if aggregator:
                order_spec.append('%s:%s %s' % (fname, aggregator, direction))

        return ', '.join(order_spec + groupby)

    @classmethod
    def _add_groupby_values(cls, groupby_read_specification, groupby, current_groups):
        """≙ referencia ``_add_groupby_values`` (``models.py:534-558``).

        Lee la info extra del campo relacional por el que se agrupó (p. ej.
        el ``display_name`` del ``many2one`` usado como columna kanban) y la
        agrega a cada grupo bajo ``'__values'``. Llama a
        :meth:`web_read`, que sí está portado.
        """
        if not groupby_read_specification or groupby_read_specification.keys().isdisjoint(groupby):
            return

        for groupby_spec in groupby:
            if groupby_spec not in groupby_read_specification:
                continue
            field = cls._meta.get_field(groupby_spec)
            related_model = field.related_model
            if related_model is None:
                raise AssertionError('We can only read extra info from a relational field')

            group_ids = [
                id_label[0] for group in current_groups if (id_label := group.get(groupby_spec))
            ]
            related_qs = related_model._default_manager.filter(pk__in=group_ids)
            result_read = related_model.web_read(related_qs, groupby_read_specification[groupby_spec])
            result_read_map = {r['id']: r for r in result_read}
            for group in current_groups:
                id_label = group.get(groupby_spec)
                group['__values'] = result_read_map[id_label[0]] if id_label else {'id': False}

    # --- read_progress_bar (kanban) -----------------------------------------

    @classmethod
    def read_progress_bar(cls, queryset, group_by, progress_bar):
        """≙ referencia ``read_progress_bar`` (``models.py:1352-1400``).

        Adaptación directa por agregación Django en vez de delegar en
        :meth:`formatted_read_group` (portado más abajo, familia
        ``read_group``): el resultado observable — conteo por valor de
        ``group_by`` × valor de ``progress_bar['field']`` — es el mismo; el
        camino para producirlo es ``.values().annotate(Count)`` en vez del
        pipeline completo de grouping sets (que aquí sería sobre-ingeniería
        para un conteo de dos ejes).
        """
        colors = progress_bar['colors']
        field = progress_bar['field']
        result = defaultdict(lambda: dict.fromkeys(colors, 0))

        rows = (
            queryset
            .values(group_by, field)
            .annotate(__count=Count('pk'))
        )
        for row in rows:
            field_value = row[field]
            if field_value in colors:
                group_by_value = str(row[group_by])
                result[group_by_value][field_value] += row['__count']

        return result
    # --- search_panel: backend del widget de panel de búsqueda --------------
    # ≙ referencia ``_search_panel_*`` / ``search_panel_select_*``
    # (``models.py:1403-1971``, 7 métodos). Puerto completo — la ausencia
    # previa citaba "sin consumidor, vista declarada en arch XML" (React
    # explícito, DEC-03); esa razón describía el estado a cambiar, no un
    # bloqueo técnico: el backend de conteo/listado no depende de arch XML,
    # sólo el widget que lo consumiría (que sí está fuera de scope, DEC-03).
    # Adaptación QuerySet-first: ``queryset`` reemplaza ``domain``/``self``.

    @classmethod
    def _search_panel_domain_image(cls, queryset, field_name, set_count=False, limit=False):
        """≙ referencia ``_search_panel_domain_image`` (``models.py:1457-1505``)."""
        model = queryset.model
        field = model._meta.get_field(field_name)
        is_relational = bool(
            getattr(field, 'many_to_many', False) or getattr(field, 'many_to_one', False)
            or getattr(field, 'one_to_one', False)
        )
        qs = queryset.exclude(**{'%s__isnull' % field_name: True})

        if is_relational:
            related_model = field.related_model
            distinct_owner = getattr(field, 'many_to_many', False)
            rows = qs.values(field_name).annotate(__count=Count('pk', distinct=distinct_owner)).order_by()
            if limit:
                rows = rows[:limit]
            rows = list(rows)
            related_ids = [row[field_name] for row in rows]
            names = {
                obj.pk: str(obj)
                for obj in related_model._default_manager.filter(pk__in=related_ids)
            }
            domain_image = {}
            for row in rows:
                rel_id = row[field_name]
                if rel_id not in names:
                    continue
                values = {'id': rel_id, 'display_name': names[rel_id]}
                if set_count:
                    values['__count'] = row['__count']
                domain_image[rel_id] = values
            return domain_image

        choices = dict(field.choices or ())
        rows = qs.values(field_name).annotate(__count=Count('pk')).order_by()
        if limit:
            rows = rows[:limit]
        domain_image = {}
        for row in rows:
            value = row[field_name]
            values = {'id': value, 'display_name': choices.get(value, value)}
            if set_count:
                values['__count'] = row['__count']
            domain_image[value] = values
        return domain_image

    @classmethod
    def _search_panel_field_image(cls, queryset, field_name, extra_domain=None,
                                   enable_counters=False, only_counters=False,
                                   limit=None, set_limit=False, **kwargs):
        """≙ referencia ``_search_panel_field_image`` (``models.py:1403-1455``).

        ``queryset`` ≙ ``model_domain`` ya aplicado; ``extra_domain`` (``Q``)
        es el refinamiento de categoría/filtro que sólo afecta el conteo —
        misma composición que la referencia (``count_domain = model_domain &
        extra_domain``), expresada con ``Q`` en vez de dominio polaco.
        """
        extra_domain = extra_domain if extra_domain is not None else Q()
        no_extra = not extra_domain.children
        count_qs = queryset.filter(extra_domain)

        if only_counters:
            return cls._search_panel_domain_image(count_qs, field_name, set_count=True)

        model_domain_image = cls._search_panel_domain_image(
            queryset, field_name,
            set_count=enable_counters and no_extra,
            limit=set_limit and limit,
        )
        if enable_counters and not no_extra:
            count_domain_image = cls._search_panel_domain_image(count_qs, field_name, set_count=True)
            for id_, values in model_domain_image.items():
                element = count_domain_image.get(id_)
                values['__count'] = element['__count'] if element else 0

        return model_domain_image

    @classmethod
    def _search_panel_global_counters(cls, values_range, parent_name):
        """≙ referencia ``_search_panel_global_counters`` (``models.py:1508-1538``).

        Verbatim — algoritmo puro sobre dicts, sin acoplamiento a Odoo.
        """
        local_counters = lazymapping(lambda id_: values_range[id_]['__count'])
        for id_ in values_range:
            values = values_range[id_]
            count = local_counters[id_]
            if count:
                parent_id = values[parent_name]
                while parent_id:
                    values = values_range[parent_id]
                    local_counters[parent_id]
                    values['__count'] += count
                    parent_id = values[parent_name]

    @classmethod
    def _search_panel_sanitized_parent_hierarchy(cls, records, parent_name, ids):
        """≙ referencia ``_search_panel_sanitized_parent_hierarchy`` (``models.py:1541-1588``).

        Divergencia declarada: ``record[parent_name]`` es el id crudo (int u
        ``None``) aquí, no la tupla ``(id, display_name)`` de la referencia —
        ver :meth:`search_panel_select_range`, que arma los dicts así.
        """
        def get_parent_id(record):
            return record.get(parent_name)

        allowed_records = {record['id']: record for record in records}
        records_to_keep = {}
        for id_ in ids:
            record_id = id_
            ancestor_chain = {}
            chain_is_fully_included = True
            while chain_is_fully_included and record_id:
                known_status = records_to_keep.get(record_id)
                if known_status is not None:
                    chain_is_fully_included = known_status
                    break
                record = allowed_records.get(record_id)
                if record:
                    ancestor_chain[record_id] = record
                    record_id = get_parent_id(record)
                else:
                    chain_is_fully_included = False

            for r_id in ancestor_chain:
                records_to_keep[r_id] = chain_is_fully_included

        return [rec for rec in records if records_to_keep.get(rec['id'])]

    @classmethod
    def _search_panel_selection_range(cls, queryset, field_name, **kwargs):
        """≙ referencia ``_search_panel_selection_range`` (``models.py:1591-1639``)."""
        model = queryset.model
        enable_counters = kwargs.get('enable_counters')
        expand = kwargs.get('expand')
        domain_image = None
        if enable_counters or not expand:
            domain_image = cls._search_panel_field_image(
                queryset, field_name, extra_domain=kwargs.get('extra_domain'),
                enable_counters=enable_counters, only_counters=bool(expand),
            )

        if not expand:
            return list(domain_image.values())

        field = model._meta.get_field(field_name)
        selection_range = []
        for value, label in field.choices or ():
            values = {'id': value, 'display_name': label}
            if enable_counters:
                image_element = domain_image.get(value)
                values['__count'] = image_element['__count'] if image_element else 0
            selection_range.append(values)
        return selection_range

    @classmethod
    def search_panel_select_range(cls, queryset, field_name, comodel_domain=None, **kwargs):
        """≙ referencia ``search_panel_select_range`` (``models.py:1642-1780``).

        ``queryset`` ≙ ``search_domain``; ``comodel_domain`` es un ``Q``
        sobre el comodelo (o ``None``). ``kwargs``: ``category_domain`` /
        ``filter_domain`` (``Q``), ``enable_counters``, ``expand``,
        ``hierarchize`` (default ``True``), ``limit``.

        Divergencia declarada: la jerarquía usa la convención de campo
        ``parent_id`` (Many2one autorreferente) — no hay ``_parent_name``
        configurable por modelo en este ORM (sólo lo declara ``ir.model``,
        que no aplica aquí); si el comodelo tiene un campo literal
        ``parent_id`` se jerarquiza, si no, no.
        """
        model = queryset.model
        field = model._meta.get_field(field_name)
        is_many2one = bool(getattr(field, 'many_to_one', False) or getattr(field, 'one_to_one', False))
        is_selection = bool(field.choices)
        if not (is_many2one or is_selection):
            raise UserError(_(
                'Sólo se admiten campos many2one o de selección para '
                'categoría (encontrado %(field_name)s).'
            ) % {'field_name': field_name})

        extra_domain = _domain_and([
            kwargs.get('category_domain') or Q(),
            kwargs.get('filter_domain') or Q(),
        ])

        if is_selection:
            return {
                'parent_field': False,
                'values': cls._search_panel_selection_range(
                    queryset, field_name, extra_domain=extra_domain, **kwargs),
            }

        related_model = field.related_model
        hierarchize = kwargs.get('hierarchize', True)
        parent_name = None
        if hierarchize:
            try:
                related_model._meta.get_field('parent_id')
                parent_name = 'parent_id'
            except FieldDoesNotExist:
                parent_name = None
        hierarchize = bool(parent_name)

        comodel_domain = comodel_domain if comodel_domain is not None else Q()
        enable_counters = kwargs.get('enable_counters')
        expand = kwargs.get('expand')
        limit = kwargs.get('limit')

        domain_image = None
        if enable_counters or not expand:
            domain_image = cls._search_panel_field_image(
                queryset, field_name, extra_domain=extra_domain,
                enable_counters=enable_counters, only_counters=bool(expand),
                limit=limit,
                set_limit=bool(limit and not (expand or hierarchize or comodel_domain.children)),
            )

        if not (expand or hierarchize or comodel_domain.children):
            values = list(domain_image.values())
            if limit and len(values) == limit:
                return {'error_msg': str(SEARCH_PANEL_ERROR_MESSAGE)}
            return {'parent_field': parent_name, 'values': values}

        comodel_qs = related_model._default_manager.filter(comodel_domain)
        if not expand:
            comodel_qs = comodel_qs.filter(pk__in=list(domain_image.keys()))
        if limit:
            comodel_qs = comodel_qs[:limit]
        comodel_records = list(comodel_qs)

        if hierarchize:
            allowed_ids = (
                [rec.pk for rec in comodel_records] if expand
                else list(domain_image.keys())
            )
            pre_hierarchy = [
                {'id': rec.pk, parent_name: getattr(rec, '%s_id' % parent_name, None)}
                for rec in comodel_records
            ]
            kept_ids = {
                row['id'] for row in
                cls._search_panel_sanitized_parent_hierarchy(pre_hierarchy, parent_name, allowed_ids)
            }
            comodel_records = [rec for rec in comodel_records if rec.pk in kept_ids]

        if limit and len(comodel_records) == limit:
            return {'error_msg': str(SEARCH_PANEL_ERROR_MESSAGE)}

        field_range = {}
        for record in comodel_records:
            values = {'id': record.pk, 'display_name': str(record)}
            if hierarchize:
                values[parent_name] = getattr(record, '%s_id' % parent_name, None)
            if enable_counters:
                image_element = domain_image.get(record.pk) if domain_image else None
                values['__count'] = image_element['__count'] if image_element else 0
            field_range[record.pk] = values

        if hierarchize and enable_counters:
            cls._search_panel_global_counters(field_range, parent_name)

        return {'parent_field': parent_name, 'values': list(field_range.values())}

    @classmethod
    def search_panel_select_multi_range(cls, queryset, field_name, comodel_domain=None, **kwargs):
        """≙ referencia ``search_panel_select_multi_range`` (``models.py:1783-1971``).

        ``group_by``/``group_domain`` de la referencia (agrupar los valores
        del filtro por un segundo campo, con conteos por combinación) **no**
        se soportan aquí: ningún widget de este proyecto los consume (React
        explícito, DEC-03) y añadir el group-by anidado sin un caso de uso
        real sería arquitectura especulativa
        (``auto-audit-before-writing.md``) sobre una porción concreta del
        método, no el método completo. El resto (m2m/m2o/selection, conteos,
        expand, límite) sí está portado.
        """
        model = queryset.model
        field = model._meta.get_field(field_name)
        is_m2m = bool(getattr(field, 'many_to_many', False))
        is_m2o = bool(getattr(field, 'many_to_one', False) or getattr(field, 'one_to_one', False))
        is_selection = bool(field.choices)
        if not (is_m2m or is_m2o or is_selection):
            raise UserError(_(
                'Sólo se admiten campos many2one, many2many o de selección '
                'para filtro (encontrado %(field_name)s).'
            ) % {'field_name': field_name})

        extra_domain = _domain_and([
            kwargs.get('category_domain') or Q(),
            kwargs.get('filter_domain') or Q(),
        ])

        if is_selection:
            return {'values': cls._search_panel_selection_range(
                queryset, field_name, extra_domain=extra_domain, **kwargs)}

        related_model = field.related_model
        limit = kwargs.get('limit')
        enable_counters = kwargs.get('enable_counters')
        expand = kwargs.get('expand')
        comodel_domain = comodel_domain if comodel_domain is not None else Q()

        if is_m2m:
            if not expand:
                domain_image = cls._search_panel_domain_image(queryset, field_name, limit=limit)
                comodel_domain = comodel_domain & Q(pk__in=list(domain_image.keys()))
            comodel_qs = related_model._default_manager.filter(comodel_domain)
            if limit:
                comodel_qs = comodel_qs[:limit]
            comodel_records = list(comodel_qs)
            if limit and len(comodel_records) == limit:
                return {'error_msg': str(SEARCH_PANEL_ERROR_MESSAGE)}

            field_range = []
            for record in comodel_records:
                values = {'id': record.pk, 'display_name': str(record)}
                if enable_counters:
                    values['__count'] = (
                        queryset.filter(**{field_name: record.pk}).filter(extra_domain).count()
                    )
                field_range.append(values)
            return {'values': field_range}

        # many2one
        domain_image = None
        if enable_counters or not expand:
            domain_image = cls._search_panel_field_image(
                queryset, field_name, extra_domain=extra_domain,
                enable_counters=enable_counters, only_counters=bool(expand),
                limit=limit, set_limit=bool(limit and not (expand or comodel_domain.children)),
            )
        if not (expand or comodel_domain.children):
            values = list(domain_image.values())
            if limit and len(values) == limit:
                return {'error_msg': str(SEARCH_PANEL_ERROR_MESSAGE)}
            return {'values': values}

        comodel_qs = related_model._default_manager.filter(comodel_domain)
        if not expand:
            comodel_qs = comodel_qs.filter(pk__in=list(domain_image.keys()))
        if limit:
            comodel_qs = comodel_qs[:limit]
        comodel_records = list(comodel_qs)
        if limit and len(comodel_records) == limit:
            return {'error_msg': str(SEARCH_PANEL_ERROR_MESSAGE)}

        field_range = []
        for record in comodel_records:
            values = {'id': record.pk, 'display_name': str(record)}
            if enable_counters:
                image_element = domain_image.get(record.pk) if domain_image else None
                values['__count'] = image_element['__count'] if image_element else 0
            field_range.append(values)
        return {'values': field_range}
    # --- read_group: familia completa de agrupamiento/formato ---------------
    # ≙ referencia ``web_read_group`` y su familia (``models.py:347-1271``,
    # 11 métodos). Puerto — misma corrección que ``search_panel``: "sin
    # consumidor" describía el estado a cambiar, no un bloqueo técnico. Dos
    # piezas quedan **ausentes** con razón medida hoy, no heredada:
    # ``_web_read_group_fill_temporal`` (necesita ``date_utils.start_of``/
    # ``end_of``/``date_range`` y ``babel`` para las etiquetas localizadas —
    # medido: ``grep -rln "date_utils\\|def start_of" src/tools/*.py
    # src/orm/*.py`` → 0, y ``python3 -c "import babel"`` → ``ModuleNotFoundError``)
    # y ``_web_read_group_groupby_properties_formatter`` (el campo
    # ``properties`` es un ``JSONField`` liso sin metadata por-clave
    # —``type``/``comodel``/``selection``— que la fuente usa para decidir
    # cómo formatear cada propiedad; ya documentado en ``web_read`` arriba,
    # mismo archivo).
    #
    # Divergencia de tipo de dato para las etiquetas de fecha: sin ``babel``
    # los buckets ``day``/``week``/``month``/``quarter``/``year`` usan
    # ``strftime``/ISO en vez de nombres de mes localizados — funcional, no
    # localizado.

    @classmethod
    def _web_read_group_field_expand(cls, model, groupby):
        """≙ referencia ``_web_read_group_field_expand`` (``models.py:916-926``).

        Se degrada igual que ``_get_read_group_order`` con ``aggregator``
        (mismo archivo, arriba): ningún campo de este ORM declara
        ``group_expand`` (medido: ``grep -rn group_expand src/orm/fields*.py``
        → 0) — la función existe y compara el atributo con
        ``getattr(..., None)``, así que nunca dispara, en vez de fallar.
        """
        if len(groupby) != 1 or '.' in groupby[0]:
            return None
        field_name = groupby[0].split(':')[0]
        try:
            field = model._meta.get_field(field_name)
        except FieldDoesNotExist:
            return None
        return field if getattr(field, 'group_expand', None) else None

    @classmethod
    def _web_read_group_expand(cls, model, domain, groups, groupby_spec, aggregates, order):
        """≙ referencia ``_web_read_group_expand`` (``models.py:928-967``).

        Código inalcanzable hoy (ver ``_web_read_group_field_expand``): se
        porta para que exista si algún campo llega a declarar
        ``group_expand`` — mismo criterio que ``_get_read_group_order``.
        """
        field_name = groupby_spec.split('.')[0].split(':')[0]
        field = model._meta.get_field(field_name)
        expand_fn = getattr(field, 'group_expand', None)
        if not expand_fn:
            return groups
        present = {group[groupby_spec]: group for group in groups if group[groupby_spec]}
        expand_values = list(expand_fn(model, list(present), domain))
        if order and 'desc' in order.lower():
            expand_values = list(reversed(expand_values))
        empty = dict.fromkeys(aggregates, 0)
        return [
            present.get(value) or dict({groupby_spec: value}, **empty)
            for value in expand_values
        ]


    @classmethod
    def _read_group_empty_value(cls, spec):
        """≙ referencia ``_read_group_empty_value``
        (``odoo19c: odoo/orm/models.py:2230-2246``).

        El valor con que se rellena una columna en un cubo que no existe en
        base. Vive aquí y no en ``src/orm/models.py`` —que es su hogar en la
        referencia— porque su único consumidor es
        :meth:`_web_read_group_fill_temporal`; moverlo a la raíz espejada es
        trabajo de la raíz, no de este pase (ver la sección "Ausentes").

        Dos divergencias, las dos del mismo origen:

        - **El nulo es ``None``, no ``False``.** La referencia devuelve
          ``False`` en el caso general porque su ORM representa así el vacío;
          aquí es ``None``, que es lo que ``QuerySet.values()`` pone en las
          filas con las que estas otras tienen que convivir. Mezclar los dos
          haría que una fila rellenada no comparase igual que una leída.
        - **No recibe el modelo**, y la referencia sí (por ``self``). Allá lo
          necesita para su rama relacional: un groupby sobre un ``many2one``
          vacío devuelve el *recordset* vacío de ese comodelo. Aquí
          ``.values()`` ya entrega ``None`` para toda columna nula, relacional
          o no, así que la rama no tiene nada que decidir y el parámetro no
          tendría uso.
        """
        if spec == '__count':
            return 0
        _field_spec, _sep, func = spec.rpartition(':')
        if func in ('count', 'count_distinct'):
            return 0
        if func in ('array_agg', 'array_agg_distinct'):
            return []
        return None

    @classmethod
    def _web_read_group_fill_temporal(cls, model, rows, groupby, spec_to_key, aggregates,
                                       fill_from=False, fill_to=False, min_groups=False):
        """≙ referencia ``_web_read_group_fill_temporal`` (``models.py:970-1127``).

        Rellena los huecos de fecha del **primer** agrupamiento. Agrupando por
        mes con datos sólo en Jun, Sep y Dic, el gráfico pega Dic contra Sep y
        engaña al lector; con los ceros explícitos salen los siete meses. Las
        tres palancas de la referencia se conservan con su semántica:
        ``fill_from``/``fill_to`` acotan el tramo a rellenar (los grupos fuera
        de las cotas **no** se borran) y ``min_groups`` garantiza un número
        mínimo de cubos contiguos desde ``fill_from``.

        Tres divergencias de mecanismo, declaradas:

        1. **Filas, no tuplas.** La referencia recibe las tuplas crudas de
           ``_read_group`` e indexa por posición (``group[0]`` es el primer
           agrupamiento). ``.values().annotate()`` de Django da **dicts**, así
           que la columna se localiza por el alias que
           :meth:`formatted_read_group` ya calcula (``spec_to_key``) — misma
           información, resuelta por nombre en vez de por posición.

        2. **Sin ``babel`` y sin desfase de semana.** La referencia corrige el
           inicio de semana con ``get_lang(self.env).week_start`` porque su
           ``_read_group`` agrupa por semana según el locale. Aquí la semana
           la fija ``TruncWeek`` de Django, que es ISO (lunes), y
           ``date_utils.start_of(value, 'week')`` usa esa misma referencia ISO
           (``src/tools/date_utils.py:441-443``). Los dos extremos coinciden,
           así que el desfase es cero por construcción y no hay locale que
           consultar — es la razón por la que la ausencia de ``babel`` deja de
           bloquear este método.

        3. **``zoneinfo`` en vez de ``pytz``.** La referencia localiza las
           cotas con ``pytz.timezone(...)``. Aquí las cotas heredan el
           ``tzinfo`` de los cubos ya existentes (que Django produce ya
           convertidos), y ``date_utils.date_range`` propaga esa zona a cada
           paso (``date_utils.py:527-542``). Misma sustitución que
           ``date_utils`` documenta para todo el módulo: Django 6 abandonó
           ``pytz``.
        """
        if not groupby:
            return rows
        groupby_name = groupby[0]
        field_path, _colon, granularity = groupby_name.partition(':')
        if granularity not in _READ_GROUP_TIME_GRANULARITY:
            return rows
        field = cls._web_read_group_leaf_field(model, field_path)
        if not getattr(field, 'get_internal_type', None) or \
                field.get_internal_type() not in ('DateField', 'DateTimeField'):
            return rows

        key = spec_to_key[groupby_name]
        existing = sorted(value for row in rows if (value := row.get(key)) is not None)
        existing_from = existing[0] if existing else None
        existing_to = existing[-1] if existing else None
        sample = existing_from

        fill_from = cls._read_group_fill_bound(fill_from, granularity, sample) or existing_from
        fill_to = cls._read_group_fill_bound(fill_to, granularity, sample) or existing_to
        if not fill_to and fill_from:
            fill_to = fill_from
        elif not fill_from and fill_to:
            fill_from = fill_to
        if not fill_from and not fill_to:
            return rows

        interval = _READ_GROUP_TIME_GRANULARITY[granularity]
        if min_groups and min_groups > 0:
            fill_to = max(fill_to, fill_from + (min_groups - 1) * interval)
        if fill_from > fill_to:
            return rows

        required = list(date_utils.date_range(fill_from, fill_to, interval))
        wanted = sorted(set(existing).union(required)) if existing else required

        empty_row = {
            spec_to_key[spec]: cls._read_group_empty_value(spec)
            for spec in tuple(groupby[1:]) + tuple(aggregates)
        }

        rows_by_bucket = defaultdict(list)
        for row in rows:
            rows_by_bucket[row.get(key)].append(row)

        result = []
        for bucket in wanted:
            if bucket in rows_by_bucket:
                result.extend(rows_by_bucket[bucket])
            else:
                result.append(dict(empty_row, **{key: bucket}))
        result.extend(rows_by_bucket.get(None, ()))
        return result

    @classmethod
    def _read_group_fill_bound(cls, bound, granularity, sample):
        """Normaliza una cota de :meth:`_web_read_group_fill_temporal`.

        No existe como símbolo en la referencia — allá el mismo trabajo está
        escrito dos veces en línea (``models.py:1080-1089``), una por cota,
        con ``Date.to_date`` + ``start_of`` + ``tz.localize``. Aquí se
        extrae porque la parte de zona horaria (punto 3 del docstring de
        arriba) la hace más larga que un duplicado tolerable.

        ``sample`` es un cubo ya existente: de él sale el ``tzinfo`` y si el
        eje es ``date`` o ``datetime``, que es lo que la referencia deduce
        del tipo del campo y del contexto.
        """
        if not bound:
            return None
        value = date_utils.parse_iso_date(bound) if isinstance(bound, str) else bound
        if isinstance(sample, datetime) and not isinstance(value, datetime):
            value = datetime.combine(value, datetime.min.time())
        elif sample is not None and not isinstance(sample, datetime) and isinstance(value, datetime):
            value = value.date()
        value = date_utils.start_of(value, granularity)
        if isinstance(sample, datetime) and sample.tzinfo is not None \
                and isinstance(value, datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=sample.tzinfo)
        return value
    @classmethod
    def _web_read_group_leaf_field(cls, model, field_path):
        """Resuelve el campo hoja de un ``path`` punteado tipo Odoo
        (``'partner_id.country_id'``), recorriendo ``related_model`` en cada
        punto. No existe en la referencia — es el pegamento que permite que
        el resto de la familia acepte paths punteados igual que ella, con la
        traversal de relación resuelta por Django (``__``) en vez de un
        recordset intermedio.
        """
        cur_model, field = model, None
        for part in field_path.split('.'):
            field = cur_model._meta.get_field(part)
            cur_model = getattr(field, 'related_model', None) or cur_model
        return field

    @classmethod
    def _web_read_group_bucket_expr(cls, django_path, granularity):
        """Expresión de anotación Django para un ``campo:granularidad``.

        No existe en la referencia — reemplaza la resolución SQL propia de
        ``_read_group`` de Odoo por ``Trunc*``/``Extract*`` de
        ``django.db.models.functions`` sobre PostgreSQL.
        """
        if granularity in _READ_GROUP_TRUNC:
            return _READ_GROUP_TRUNC[granularity](django_path)
        if granularity in _READ_GROUP_NUMBER_GRANULARITY:
            _lookup, extract_cls = _READ_GROUP_NUMBER_GRANULARITY[granularity]
            return extract_cls(django_path)
        raise ValueError('%r no es una granularidad soportada' % granularity)

    @classmethod
    def _read_group_bucket_label(cls, value, granularity):
        """Etiqueta legible de un bucket temporal — sin ``babel`` (ausente
        del proyecto, ver cabecera de la familia): ISO/``strftime`` en vez de
        nombres de mes localizados.
        """
        if granularity == 'day':
            return value.strftime('%Y-%m-%d')
        if granularity == 'week':
            iso_year, iso_week, _wd = value.isocalendar()
            return 'W%02d %04d' % (iso_week, iso_year)
        if granularity == 'month':
            return value.strftime('%Y-%m')
        if granularity == 'quarter':
            quarter = (value.month - 1) // 3 + 1
            return 'Q%d %04d' % (quarter, value.year)
        if granularity == 'year':
            return value.strftime('%Y')
        return str(value)

    @classmethod
    def _read_group_aggregate_expression(cls, django_field, agg_name):
        """``campo:agregador`` de la referencia → expresión Django."""
        ctor = _READ_GROUP_AGGREGATORS.get(agg_name)
        if ctor is None:
            raise ValueError('Agregador no soportado: %r' % agg_name)
        return ctor(django_field)

    @classmethod
    def _web_read_group_groupby_formatter(cls, model, groupby_spec):
        """≙ referencia ``_web_read_group_groupby_formatter`` (``models.py:1168-1271``).

        Divergencia declarada: en vez de una fábrica que recibe la columna
        completa (``values``) y decide con eso, el formateador se resuelve
        por **field-path completo** (Django ``__`` recorre la relación,
        ``field.subfield`` de la referencia colapsa en un único lookup) — no
        hace falta ``formatter_follow_many2one`` como recursión aparte: el
        path punteado ya es un solo lookup Django.
        """
        field_path, _colon, granularity = groupby_spec.partition(':')
        django_path = field_path.replace('.', '__')
        field = cls._web_read_group_leaf_field(model, field_path)

        if getattr(field, 'many_to_many', False):
            related_model = field.related_model

            def formatter_many2many(value):
                if not value:
                    return False, Q(**{'%s__isnull' % django_path: True})
                obj = related_model._default_manager.filter(pk=value).first()
                label = str(obj) if obj else value
                return (value, label), Q(**{django_path: value})
            return formatter_many2many

        if getattr(field, 'many_to_one', False) or getattr(field, 'one_to_one', False):
            related_model = field.related_model

            def formatter_many2one(value):
                if not value:
                    return False, Q(**{'%s__isnull' % django_path: True})
                obj = related_model._default_manager.filter(pk=value).first()
                label = str(obj) if obj else value
                return (value, label), Q(**{django_path: value})
            return formatter_many2one

        if granularity:
            if granularity in _READ_GROUP_TRUNC:
                def formatter_time_granularity(value):
                    if not value:
                        return value, Q(**{'%s__isnull' % django_path: True})
                    label = cls._read_group_bucket_label(value, granularity)
                    return (value.isoformat(), label), Q(**{django_path: value})
                return formatter_time_granularity
            if granularity in _READ_GROUP_NUMBER_GRANULARITY:
                lookup, _extract_cls = _READ_GROUP_NUMBER_GRANULARITY[granularity]

                def formatter_date_number_granularity(value):
                    if value is None:
                        return value, Q(**{'%s__isnull' % django_path: True})
                    return value, Q(**{'%s__%s' % (django_path, lookup): value})
                return formatter_date_number_granularity
            raise ValueError("%r isn't a valid granularity" % granularity)

        if field_path == 'id' or django_path == 'pk':
            def formatter_id(value):
                return value, Q(pk=value)
            return formatter_id

        def formatter_plain(value):
            if value is None:
                return value, Q(**{'%s__isnull' % django_path: True})
            return value, Q(**{django_path: value})
        return formatter_plain

    @classmethod
    def _web_read_group_format(cls, model, groupby, spec_to_key, aggregates, rows):
        """≙ referencia ``_web_read_group_format`` (``models.py:1130-1166``).

        Divergencia declarada: la referencia recibe columnas paralelas
        (tuplas zippeadas) porque ``_read_group`` de Odoo devuelve tuplas por
        fila. ``.values().annotate()``/``.aggregate()`` de Django ya dan
        **dicts por fila** — se formatea cada fila en el lugar en vez de
        transponer a columnas y volver a armar.

        Nota de rendimiento (no de corrección): el formatter de un ``spec``
        many2one/many2many hace **una consulta por fila** para el
        ``display_name`` del valor agrupado (``related_model.filter(pk=…)``),
        no un lote — aceptable para el número de grupos típico de un
        agrupamiento (decenas, no miles); optimizar a un solo ``IN`` por
        columna queda para cuando haya un consumidor real que lo note.
        """
        formatters = {spec: cls._web_read_group_groupby_formatter(model, spec) for spec in groupby}
        result = []
        for row in rows:
            dict_group = {'__extra_domains': []}
            for spec in groupby:
                value, extra_domain = formatters[spec](row[spec_to_key[spec]])
                dict_group[spec] = value
                dict_group['__extra_domains'].append(extra_domain)
            dict_group['__extra_domain'] = _domain_and(dict_group.pop('__extra_domains'))
            for spec in aggregates:
                dict_group[spec] = row[spec_to_key[spec]]
            result.append(dict_group)
        return result

    @classmethod
    def formatted_read_group(cls, queryset, groupby=(), aggregates=(), having=None,
                              offset=0, limit=None, order=None, fill_temporal=None):
        """≙ referencia ``formatted_read_group`` (``models.py:800-914``).

        ``queryset`` reemplaza ``domain`` (convención QuerySet-first del
        módulo, ya establecida en :meth:`read_progress_bar`). Sin soporte de
        ``group_expand`` real (ver ``_web_read_group_field_expand``).
        ``having``, si se pasa, es un ``Q`` que ya referencia los alias
        internos que produce esta función para cada ``spec`` de
        ``aggregates`` — no hay traducción automática spec→alias expuesta hoy
        porque ningún llamador del árbol lo necesita todavía.

        ``fill_temporal`` reemplaza la clave de contexto homónima de la
        referencia (``:911``): allá el cliente la deja en ``env.context`` y
        el método la recoge; aquí no hay contexto de entorno que atraviese la
        llamada, así que viaja como **parámetro explícito** — misma
        convención por la que ``queryset`` reemplaza a ``domain``. Los dos
        valores de la referencia se conservan: un dict con
        ``fill_from``/``fill_to``/``min_groups``, o cualquier valor cierto
        para rellenar con las cotas que den los datos.
        """
        model = queryset.model
        groupby = tuple(groupby)
        aggregates = tuple(aggregates)

        pre_annotate, group_keys, spec_to_key = {}, [], {}
        for spec in groupby:
            field_path, _colon, granularity = spec.partition(':')
            django_path = field_path.replace('.', '__')
            if granularity:
                alias = 'gb_%s' % re.sub(r'\W', '_', spec)
                pre_annotate[alias] = cls._web_read_group_bucket_expr(django_path, granularity)
                key = alias
            else:
                key = django_path
            group_keys.append(key)
            spec_to_key[spec] = key

        qs = queryset.annotate(**pre_annotate) if pre_annotate else queryset

        agg_kwargs = {}
        for spec in aggregates:
            alias = '__count' if spec == '__count' else 'agg_%s' % re.sub(r'\W', '_', spec)
            spec_to_key[spec] = alias
            if spec == '__count':
                agg_kwargs[alias] = Count('pk')
                continue
            if ':' in spec:
                field_spec, _sep, agg_name = spec.rpartition(':')
            else:
                field_spec, agg_name = spec, 'sum'
            agg_kwargs[alias] = cls._read_group_aggregate_expression(
                field_spec.replace('.', '__'), agg_name)

        if not group_keys:
            row = qs.aggregate(**agg_kwargs) if agg_kwargs else {}
            return cls._web_read_group_format(model, groupby, spec_to_key, aggregates, [row])

        qs = qs.values(*group_keys).annotate(**agg_kwargs) if agg_kwargs else qs.values(*group_keys).distinct()
        if having is not None:
            qs = qs.filter(having)
        if order:
            qs = qs.order_by(*cls._read_group_order_by(order, spec_to_key))
        else:
            qs = qs.order_by(*group_keys)

        rows = list(qs[offset:offset + limit]) if limit else list(qs[offset:]) if offset else list(qs)
        rows = cls._apply_fill_temporal(
            model, rows, groupby, spec_to_key, aggregates, fill_temporal, offset, limit)
        return cls._web_read_group_format(model, groupby, spec_to_key, aggregates, rows)

    @classmethod
    def _apply_fill_temporal(cls, model, rows, groupby, spec_to_key, aggregates,
                              fill_temporal, offset=0, limit=None):
        """Puerta de :meth:`_web_read_group_fill_temporal`.

        No existe como símbolo en la referencia: allá el mismo bloque está
        escrito **dos veces** en línea, una en ``formatted_read_group``
        (``:910-913``) y otra en ``formatted_read_grouping_sets``
        (``:800-806``), con el rechazo de limit/offset sólo en la primera.
        Aquí se comparte para que las dos entradas se comporten igual.

        El rechazo se porta verbatim: rellenar una página produce cubos que
        la página siguiente vuelve a emitir, y el paginador del cliente
        cuenta dos veces.
        """
        if not (fill_temporal or isinstance(fill_temporal, dict)):
            return rows
        if limit or offset:
            raise ValueError('No se puede usar fill_temporal con limit u offset')
        options = fill_temporal if isinstance(fill_temporal, dict) else {}
        return cls._web_read_group_fill_temporal(
            model, rows, groupby, spec_to_key, aggregates, **options)

    @classmethod
    def _read_group_order_by(cls, order, spec_to_key):
        """``"campo desc, campo2"`` (sintaxis de ``order`` de la referencia)
        → lista de argumentos para ``QuerySet.order_by`` usando los alias
        internos de :meth:`formatted_read_group`. No existe en la
        referencia — allá el ``order`` se arma como *string* SQL propio.
        """
        parts = []
        for chunk in order.split(','):
            chunk = chunk.strip()
            if not chunk:
                continue
            tokens = chunk.split()
            spec = tokens[0]
            desc = len(tokens) > 1 and tokens[1].upper().startswith('DESC')
            key = spec_to_key.get(spec, spec.replace('.', '__'))
            parts.append('-%s' % key if desc else key)
        return parts

    @classmethod
    def _formatted_read_group_with_length(cls, queryset, groupby, aggregates, offset=0, limit=None, order=None):
        """≙ referencia ``_formatted_read_group_with_length`` (``models.py:515-530``)."""
        groups = cls.formatted_read_group(queryset, groupby, aggregates, offset=offset, limit=limit, order=order)
        if not groups:
            length = 0
        elif limit and len(groups) == limit:
            length = limit + len(cls.formatted_read_group(queryset, groupby, (), offset=limit))
        else:
            length = len(groups) + offset
        return groups, length

    @classmethod
    def _open_groups(cls, *, records_opening_info, groups, queryset, groupby, aggregates,
                      dict_order, auto_unfold, opening_info, unfold_read_default_limit,
                      parent_opening_info, parent_group_domain):
        """≙ referencia ``_open_groups`` (``models.py:584-698``).

        ``queryset`` reemplaza ``domain`` (ya filtrado); ``parent_group_domain``
        es un ``Q`` — misma convención ``AND``/``OR`` del módulo, no dominio
        polaco.
        """
        model = queryset.model
        max_number_opened_group = MAX_NUMBER_OPENED_GROUPS

        parent_opening_info_dict = {
            info_opening['value']: info_opening
            for info_opening in parent_opening_info or ()
        }
        groupby_spec = groupby[0]
        field = cls._web_read_group_leaf_field(model, groupby_spec.split(':')[0].split('.')[0])
        nb_opened_group = 0

        last_level = len(groupby) == 1
        read_group_order = None
        if not last_level:
            read_group_order = cls._get_read_group_order(dict_order, [groupby[1]], aggregates)

        for group in groups:
            fold_info = '__fold' in group
            fold = group.pop('__fold', False)

            groupby_value = group[groupby_spec]
            raw_groupby_value = groupby_value[0] if isinstance(groupby_value, tuple) else groupby_value

            limit = unfold_read_default_limit
            offset = 0
            progressbar_domain = None
            subgroup_opening_info = None
            if opening_info and raw_groupby_value in parent_opening_info_dict:
                group_info = parent_opening_info_dict[raw_groupby_value]
                if group_info['folded']:
                    continue
                limit = group_info['limit']
                offset = group_info['offset']
                progressbar_domain = group_info.get('progressbar_domain')
                subgroup_opening_info = group_info.get('groups')
            elif (
                (not auto_unfold and not fold_info)
                or nb_opened_group >= max_number_opened_group
                or fold
                or (getattr(field, 'is_relation', False) and not group[groupby_spec])
            ):
                continue

            nb_opened_group += 1
            if last_level:
                records_domain = parent_group_domain & group['__extra_domain']
                if progressbar_domain is not None:
                    records_domain &= progressbar_domain
                if offset and offset >= group['__count']:
                    group['__offset'] = offset = 0
                records_opening_info.append({
                    'domain': records_domain,
                    'limit': limit,
                    'offset': offset,
                    'group': group,
                })
            else:
                subgroup_domain = parent_group_domain & group['__extra_domain']
                subgroups, length = cls._formatted_read_group_with_length(
                    model._default_manager.filter(subgroup_domain),
                    [groupby[1]], aggregates, offset=offset, limit=limit, order=read_group_order)
                group['__groups'] = {'groups': subgroups, 'length': length}
                cls._open_groups(
                    records_opening_info=records_opening_info,
                    groups=subgroups,
                    queryset=queryset,
                    groupby=groupby[1:],
                    aggregates=aggregates,
                    dict_order=dict_order,
                    auto_unfold=False,
                    opening_info=opening_info,
                    unfold_read_default_limit=unfold_read_default_limit,
                    parent_opening_info=subgroup_opening_info,
                    parent_group_domain=subgroup_domain,
                )

    @classmethod
    def formatted_read_grouping_sets(cls, queryset, grouping_sets, aggregates=(), order=None,
                                      fill_temporal=None):
        """≙ referencia ``formatted_read_grouping_sets`` (``models.py:702-798``).

        Divergencia declarada: la referencia arma **una** consulta SQL con
        ``GROUPING SETS`` (agrega varias combinaciones de agrupamiento a la
        vez). PostgreSQL soporta ``GROUPING SETS``, pero el ORM de Django no
        expone esa cláusula (``QuerySet`` no tiene un equivalente). Se emula
        con **una consulta por combinación**, reusando
        :meth:`formatted_read_group`: mismo resultado observable (lista de
        listas de grupos formateados), distinto plan SQL — N consultas en
        vez de 1.
        """
        return [
            cls.formatted_read_group(queryset, list(groupby), aggregates, order=order,
                                     fill_temporal=fill_temporal)
            for groupby in grouping_sets
        ]

    @classmethod
    def web_read_group(cls, queryset, groupby, aggregates=(), limit=None, offset=0, order=None, *,
                        auto_unfold=False, opening_info=None, unfold_read_specification=None,
                        unfold_read_default_limit=80, groupby_read_specification=None):
        """≙ referencia ``web_read_group`` (``models.py:347-513``).

        ``queryset`` reemplaza ``domain`` (convención QuerySet-first). Sin el
        ajuste de "active" que hace la referencia sobre el dominio (repara
        que el optimizador de ``Domain`` de Odoo puede quitar la condición
        del campo activo antes de ejecutar) — aquí ``queryset`` ya viene tal
        como el llamador lo filtró, y este ORM no tiene un optimizador de
        dominios propio que reescriba condiciones.

        Divergencia declarada en el des-anidado de registros: la referencia
        hace **un** ``web_read`` por lotes sobre la unión de todos los
        subgrupos abiertos (optimización de un solo query); aquí se hace un
        ``web_read`` **por subgrupo** — mismo resultado observable, más
        queries.
        """
        assert isinstance(groupby, (list, tuple)) and groupby
        model = queryset.model
        groupby = list(groupby)
        aggregates = list(aggregates)
        if '__count' not in aggregates:
            aggregates.append('__count')

        dict_order = {}
        for order_part in (order.split(',') if order else ()):
            order_part = order_part.strip()
            if not order_part:
                continue
            tokens = order_part.split()
            fname = tokens[0]
            direction = tokens[1].upper() if len(tokens) > 1 else 'ASC'
            dict_order[fname] = direction

        first_groupby = [groupby[0]]
        read_group_order = cls._get_read_group_order(dict_order, first_groupby, aggregates)
        groups, length = cls._formatted_read_group_with_length(
            queryset, first_groupby, aggregates, offset=offset, limit=limit, order=read_group_order,
        )

        records_opening_info = []
        cls._open_groups(
            records_opening_info=records_opening_info,
            groups=groups,
            queryset=queryset,
            groupby=groupby,
            aggregates=aggregates,
            dict_order=dict_order,
            auto_unfold=auto_unfold,
            opening_info=opening_info,
            unfold_read_default_limit=unfold_read_default_limit,
            parent_opening_info=opening_info,
            parent_group_domain=Q(),
        )

        if records_opening_info:
            order_specs = [
                fname if direction == 'ASC' else '-%s' % fname
                for fname, direction in dict_order.items()
                if fname not in groupby and fname != '__count'
            ]
            for sub_search in records_opening_info:
                if not sub_search['group']['__count']:
                    sub_search['group']['__records'] = []
                    continue
                sub_qs = model._default_manager.filter(sub_search['domain'])
                if order_specs:
                    sub_qs = sub_qs.order_by(*order_specs)
                off, lim = sub_search['offset'], sub_search['limit']
                sub_qs = sub_qs[off:off + lim] if lim else sub_qs[off:]
                sub_search['group']['__records'] = cls.web_read(sub_qs, unfold_read_specification or {})

        cls._add_groupby_values(groupby_read_specification, groupby, groups)

        return {'groups': groups, 'length': length}

    # --- onchange -----------------------------------------------------------

    def onchange(self, values, field_names, fields_spec):
        """≙ referencia ``onchange`` (``models.py:1973-2195``).

        Recalcula el formulario tras editar ``field_names`` y devuelve **sólo
        lo que cambió**, más los avisos que los métodos ``@api.onchange``
        hayan levantado. Con ``field_names`` vacío es un alta desde cero: se
        siembran los defaults y se devuelven todos los campos de la
        especificación.

        ``self`` es UN registro, con o sin ``pk`` — misma lectura que
        :meth:`web_save` hace del ``self`` recordset de la referencia cuando
        tiene 0 o 1 elementos. **No se muta**: todo ocurre sobre la copia sin
        guardar que devuelve :func:`_virtual_record`.

        Qué se porta y qué no, medido
        ==============================

        Se porta el ciclo entero de la referencia: aislar lo cambiado de lo
        inicial, la foto previa, el despacho por campo, las **pasadas
        sucesivas** mientras un método siga moviendo campos de la
        especificación, la foto final, el diff y la fusión de avisos.

        **No se porta el recálculo de los campos calculados almacenados** —el
        ``record.modified(...)`` de la referencia (``:2148``) dentro de su
        ``env.protecting``, que propaga el cambio por el grafo de
        dependencias y vuelve a calcular lo que dependa de lo tocado. Aquí un
        cálculo es una ``property`` o un ``compute`` que Django resuelve al
        leer, así que la foto final ya lo ve; lo que **no** ocurre es la
        invalidación de un campo calculado **con columna**, que en este árbol
        se recalcula en ``save()`` y no antes. El grafo existe
        (``orm.registry.field_depends``, ``registry.py:498``); lo que falta es
        el motor que lo recorra invalidando caché, y ése es un mecanismo de
        ``src/orm/``, no un símbolo de este archivo.

        Alcance de lo que ese motor desbloquearía: los ``@api.onchange``
        declarados en el árbol, que este método **ya despacha todos** — lo que
        espera es la cascada. El conteo se pide al comando y no se transcribe
        (crece con el árbol): ``grep -rn "@api.onchange" src/ addons/
        --include='*.py'``. La minoría que escribe otro campo del registro
        —y no sólo avisa— es la que hace visible la diferencia.

        Sucesor propuesto —no existe todavía—: *motor de recálculo de campos
        calculados sobre registro virtual*, en ``src/orm/models.py``, con
        condición de cierre medible: que ``def modified`` exista ahí y que
        este método lo invoque en lugar de esta nota.
        """
        model = type(self)
        field_names = list(field_names or ())
        if any(_model_field(model, name) is None and not hasattr(model, name)
               for name in field_names):
            return {}

        first_call = not field_names
        values = dict(values or {})

        if first_call:
            field_names = [name for name in values if name != 'id']
            missing = [name for name in fields_spec if name not in values]
            defaults = model.default_get(missing) if hasattr(model, 'default_get') else {}
            for name in missing:
                if name in defaults:
                    values[name] = defaults[name]
                    field_names.append(name)

        changed_values = {name: values[name] for name in field_names if name in values}
        initial_values = {name: value for name, value in values.items()
                          if name not in changed_values}

        record = _virtual_record(self, initial_values)
        snapshot0 = RecordSnapshot(record, fields_spec, fetch=not first_call)
        for name, value in changed_values.items():
            _assign(record, name, value)
        for name in field_names:
            if name in fields_spec:
                snapshot0.fetch(name)

        result = {'warnings': []}
        todo = (list(dict.fromkeys(list(field_names) + list(fields_spec)))
                if first_call else list(field_names))
        done = set()
        while todo:
            visited = set()
            for name in todo:
                for method_name in _onchange_methods_for(model, name):
                    if method_name in visited:
                        continue
                    _apply_onchange_method(record, method_name, result)
                    visited.add(method_name)
                done.add(name)
            todo = [name for name in fields_spec
                    if name not in done and snapshot0.has_changed(name)]

        snapshot1 = RecordSnapshot(record, fields_spec)
        result['value'] = snapshot1.diff(snapshot0, force=first_call)

        warnings = result.pop('warnings')
        if len(warnings) == 1:
            title, message, kind = warnings[0]
            result['warning'] = {'title': title, 'message': message,
                                 'type': kind or 'dialog'}
        elif len(warnings) > 1:
            result['warning'] = {
                'title': _('Avisos'),
                'message': '\n\n'.join('%s\n\n%s' % (title, message)
                                       for title, message, _kind in warnings),
                'type': 'dialog',
            }
        return result


# === Piezas del onchange ====================================================
#
# ≙ lo que en la referencia resuelve el ORM: ``_onchange_methods`` (el mapa
# campo → métodos que el setup del registro puebla), ``self.new()`` (el
# registro virtual) y ``_apply_onchange_methods``
# (``odoo19c: odoo/orm/models.py:6975-6994``).
#
# DIVERGENCIA DE SITIO, declarada: el hogar de esas tres piezas en la
# referencia es ``odoo/orm/models.py``, o sea ``src/orm/models.py`` en la raíz
# espejada. Aquí aterrizan como funciones privadas de módulo junto a su único
# consumidor porque este pase sólo toca ``addons/web/models/models.py``;
# subirlas a ``src/orm/`` —y con ellas el ``@api.onchange`` que 37 archivos del
# árbol ya declaran sin despachador— es trabajo de la raíz espejada, no de este
# archivo. Se anotan como funciones privadas y no como métodos de ``Base`` para
# que la comparación símbolo a símbolo con la referencia no las lea como
# símbolos de ``Base`` que la fuente no tiene.


def _model_field(model, field_name):
    """El campo declarado, o ``None`` si el modelo no lo tiene."""
    try:
        return model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return None


def _is_x2many(field):
    """Si el campo es ``one2many``/``many2many`` — ≙ el
    ``field.type in ('one2many', 'many2many')`` de la referencia."""
    return bool(getattr(field, 'many_to_many', False)
                or getattr(field, 'one_to_many', False))


def _x2many_lines(record, field_name):
    """Las líneas de un x2many, o vacío si la fila aún no existe.

    Django prohíbe tocar una relación de muchos sobre una fila sin guardar
    (``Direct assignment to the forward side of a many-to-many set is
    prohibited``) — la misma restricción que
    ``orm.models.RecordLoaderMixin._load_records_split_relational`` declara.
    La referencia no la tiene porque su registro virtual vive en caché.
    """
    if record.pk is None:
        return ()
    return list(getattr(record, field_name).all())


def _snapshot_value(record, field_name):
    """El valor de un campo escalar tal como lo ve el formulario.

    Un ``many2one`` se lee por su ``attname`` (el id crudo) y no por el
    atributo: leer el atributo dispararía una consulta por campo y por
    pasada, y el id es lo que el cliente manda y compara.
    """
    field = _model_field(type(record), field_name)
    if field is not None and (getattr(field, 'many_to_one', False)
                              or getattr(field, 'one_to_one', False)):
        return getattr(record, field.attname)
    return getattr(record, field_name, None)


def _assign(record, field_name, value):
    """Escribe un valor sobre el registro virtual.

    Un x2many se ignora a propósito: no hay dónde escribirlo sin fila (ver
    :func:`_x2many_lines`), y tragárselo aquí es preferible a reventar la
    llamada entera por un campo que el resto del ``onchange`` no necesita.
    """
    field = _model_field(type(record), field_name)
    if field is not None and _is_x2many(field):
        return
    if field is not None and (getattr(field, 'many_to_one', False)
                              or getattr(field, 'one_to_one', False)) \
            and not hasattr(value, 'pk'):
        setattr(record, field.attname, value)
        return
    setattr(record, field_name, value)


def _onchange_methods_for(model, field_name):
    """Nombres de los ``@api.onchange`` registrados para un campo.

    ≙ ``self._onchange_methods[field_name]`` de la referencia, que allá es un
    mapa que el setup del registro construye una vez. Aquí se **deriva** de lo
    declarado —``@api.onchange`` deja su tupla en ``func._onchange``
    (``orm/decorators.py:37-41``)—, que es el mismo camino que
    ``orm.registry.field_depends`` ya toma para ``@api.depends``.

    **Sin caché, y es deliberado:** aquel mapa se cachea porque lo consulta
    todo campo de todo modelo; éste lo consulta un puñado de campos de un solo
    modelo cuando alguien edita un formulario. Una caché aquí exigiría una
    invalidación que nada dispara, y haría invisible un método añadido en
    caliente.

    ``getattr_static`` en vez de ``getattr``: el modelo puede declarar
    descriptores que se resuelven al leerlos (``orm.fields_nonstored.NonStored``
    calcula su default llamando al registro), y recorrer la clase entera no
    debe ejecutar ninguno.
    """
    found = []
    for name in dir(model):
        if name.startswith('__'):
            continue
        try:
            attr = inspect.getattr_static(model, name)
        except AttributeError:
            continue
        func = getattr(attr, '__func__', attr)
        declared = getattr(func, '_onchange', None)
        if declared and field_name in declared:
            found.append(name)
    return tuple(sorted(found))


def _apply_onchange_method(record, method_name, result):
    """≙ referencia ``_apply_onchange_methods``
    (``odoo19c: odoo/orm/models.py:6975-6994``), para **un** método.

    Las asignaciones se aplican sobre el registro virtual; los avisos se
    acumulan en ``result``. La referencia itera los métodos aquí dentro porque
    su mapa ya está construido; aquí el bucle vive en :meth:`Base.onchange`,
    que es quien decide el orden de las pasadas.
    """
    res = getattr(record, method_name)()
    if not res:
        return
    for key, value in (res.get('value') or {}).items():
        if key != 'id' and _model_field(type(record), key) is not None:
            _assign(record, key, value)
    warning = res.get('warning')
    if warning:
        entry = (warning.get('title') or _('Aviso'),
                 warning.get('message') or '',
                 warning.get('type') or '')
        if entry not in result['warnings']:
            result['warnings'].append(entry)


def _virtual_record(record, values):
    """El registro del formulario: una copia **sin guardar** de ``record``.

    ≙ ``self.new(cache_values, origin=self)`` de la referencia (``:2098``).
    Allá el registro virtual lleva un ``NewId`` y su ``origin`` apunta a la
    fila; aquí la copia conserva el ``pk`` —así ``OriginMixin._origin`` sigue
    resolviendo a la fila guardada (``orm/models.py:416-428``) y los x2many
    siguen siendo legibles— y lo que la distingue del original es que nadie
    la guarda. Es el mismo eje que ``OriginMixin`` ya declara para este árbol:
    lo que separa "en formulario" de "guardado" no es el tipo del id sino el
    estado de la instancia.
    """
    model = type(record)
    virtual = model()
    for field in model._meta.concrete_fields:
        setattr(virtual, field.attname, getattr(record, field.attname))
    virtual._state.db = record._state.db
    virtual._state.adding = record._state.adding
    for field_name, value in values.items():
        _assign(virtual, field_name, value)
    return virtual


class RecordSnapshot(dict):
    """≙ referencia ``RecordSnapshot`` (``models.py:2252-2360``).

    Los valores de un registro siguiendo el árbol de prefijos de
    ``fields_spec``: escalares en el sitio, x2many como un mapa
    ``{id: RecordSnapshot}``. Es lo que permite a :meth:`Base.onchange`
    responder **sólo** lo que cambió, comparando dos fotos del mismo registro
    virtual.

    Divergencia declarada — de dónde salen los valores del ``diff``: la
    referencia formatea los escalares con ``self.record.web_read(...)``
    (``:2313``). Aquí no se puede: ``web_read`` de este módulo lee de un
    ``QuerySet`` y el registro del formulario no tiene fila que consultar.
    Los valores salen del propio snapshot, que ya los leyó del registro — es
    la misma información sin el viaje a la base.
    """

    __slots__ = ['record', 'fields_spec']

    def __init__(self, record, fields_spec, fetch=True):
        """≙ referencia ``RecordSnapshot.__init__`` (``:2256-2263``)."""
        super().__init__()
        self.record = record
        self.fields_spec = fields_spec
        if fetch:
            for field_name in fields_spec:
                self.fetch(field_name)

    def __eq__(self, other):
        """≙ referencia ``RecordSnapshot.__eq__`` (``:2265-2266``).

        El registro entra en la comparación a propósito: dos etapas distintas
        con los mismos valores no son la misma foto.
        """
        if not isinstance(other, RecordSnapshot):
            return NotImplemented
        return self.record == other.record and dict(self) == dict(other)

    def __ne__(self, other):
        """No está en la referencia y hace falta aquí: ``dict`` implementa su
        propia comparación para los dos operadores, así que sin esto ``!=``
        ignoraría el ``__eq__`` de arriba y compararía sólo los valores.
        """
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    __hash__ = None

    def fetch(self, field_name):
        """≙ referencia ``RecordSnapshot.fetch`` (``:2268-2278``)."""
        field = _model_field(type(self.record), field_name)
        if field is not None and _is_x2many(field):
            sub_spec = (self.fields_spec.get(field_name) or {}).get('fields') or {}
            self[field_name] = {
                line.pk: RecordSnapshot(line, sub_spec)
                for line in _x2many_lines(self.record, field_name)
            }
        else:
            self[field_name] = _snapshot_value(self.record, field_name)

    def has_changed(self, field_name):
        """≙ referencia ``RecordSnapshot.has_changed`` (``:2280-2290``)."""
        if field_name not in self:
            return True
        field = _model_field(type(self.record), field_name)
        if field is None or not _is_x2many(field):
            return self[field_name] != _snapshot_value(self.record, field_name)
        if set(self[field_name]) != {line.pk for line in _x2many_lines(self.record, field_name)}:
            return True
        sub_spec = (self.fields_spec.get(field_name) or {}).get('fields') or {}
        return any(line_snapshot.has_changed(sub_name)
                   for line_snapshot in self[field_name].values()
                   for sub_name in sub_spec)

    def diff(self, other, force=False):
        """≙ referencia ``RecordSnapshot.diff`` (``:2292-2360``).

        Los valores de ``self`` que difieren de ``other``; con ``force``,
        todos (es el alta desde cero, donde el cliente no tiene nada con que
        comparar).
        """
        result = {}
        for field_name in self.fields_spec:
            if field_name == 'id':
                continue
            if not force and other.get(field_name) == self.get(field_name):
                continue
            field = _model_field(type(self.record), field_name)
            if field is not None and _is_x2many(field):
                result[field_name] = self._x2many_value(field_name, other, force)
            else:
                result[field_name] = self.get(field_name)
        return result

    def _x2many_value(self, field_name, other, force):
        """El cambio de un x2many, con los dos verbos de la referencia.

        No existe como símbolo aparte en la referencia —allá es el bloque
        ``:2317-2360`` dentro de ``diff``—; se extrae porque la traducción del
        vocabulario lo hace más largo que el resto del método junto.

        **La información se porta entera**: qué líneas quedan y qué valores
        cambió cada una. Lo que no se porta es su *codificación*, y hay dos
        razones medidas, ninguna de ellas "este ORM no lo tiene":

        1. La fuente serializa el cambio como **tuplas** ``Command``
           (``delete``/``update``/``create``) que su ``write`` interpreta
           después. El ``Command`` de este árbol es **ejecutivo** —escribe al
           llamarlo (:ref:`h-api-589`, tarea **#345**)—, así que no hay tupla
           que emitir.
        2. Los tres portadores diferidos que ``orm/commands.py`` sí tiene
           (``ManyToManySet``, ``ManyToManyLink``, ``One2manyChild``) son
           vocabulario **interno del ORM**: la fachada pública sólo exporta
           ``Command`` (``src/fields/__init__.py:75``), y
           ``tests/unit/orm/test_fields_facade.py`` mide que ningún archivo de
           ``addons/`` importe ``orm.commands`` (:ref:`h-api-604`). Un addon
           que los emitiera cruzaría esa frontera.

        Así que los dos verbos viajan como un dict, y los dos nombres son los
        de la fuente (``Command.set`` y ``Command.update``): ``'set'`` con los
        ids que quedan —una baja se expresa por omisión— y ``'update'`` con el
        diff de cada línea que cambió por dentro. Sin llaves inventadas y sin
        cruzar la fachada.

        Que esto vuelva a ser el vocabulario propio del árbol pide las dos
        piezas de arriba: la tarea **#345** (``Command`` diferido) y, con
        ella, exportar los portadores por la fachada.
        """
        current = self[field_name]
        previous = {} if force else (other.get(field_name) or {})
        value = {}
        if set(current) != set(previous):
            value['set'] = list(current)
        updates = {}
        for line_id, line_snapshot in current.items():
            if line_id not in previous:
                continue
            line_diff = line_snapshot.diff(previous[line_id])
            if line_diff:
                updates[line_id] = line_diff
        if updates:
            value['update'] = updates
        return value
