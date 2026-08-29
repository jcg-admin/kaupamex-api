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
``RecordSnapshot``). **32 portados** (11 del primer pase + 21 del segundo:
9 de ``read_group`` + 4 formatters anidados + 7 de ``search_panel`` + 1
``get_parent_id`` anidado). **24 declarados ausentes**, cada uno con razón
medida **hoy** — ver abajo. Ninguna ausencia hereda la redacción del primer
pase.

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

Portados (32, adaptados)
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

Ausentes (24) — con razón medida hoy, no heredada
====================================================

**``_web_read_group_fill_temporal`` (1 método).** Rellena huecos de fecha en
series para gráficos (Jun-Sep-Dic → Jun-Jul-Ago-Sep-Oct-Nov-Dic). Necesita
``date_utils.start_of``/``end_of``/``date_range``/``weeknumber`` y ``babel``
para las etiquetas — medido hoy: ``grep -rln "date_utils\\|def start_of"
src/tools/*.py src/orm/*.py`` → **0**; ``python3 -c "import babel"`` →
``ModuleNotFoundError``. Ninguna utilidad genérica de calendario existe en
el proyecto para construirlo sin reinventar ``date_utils`` entero.

**``_web_read_group_groupby_properties_formatter`` (1 método) + sus 5
formatters anidados** (``formatter_property_selection``,
``formatter_property_many2one``, ``formatter_property_many2many``,
``formatter_property_tags``, ``formatter_property_datetime``). El campo
``properties`` es un ``JSONField`` liso (``orm/fields_properties.py``) sin la
metadata por-clave (``type``/``comodel``/``selection``/``tags``) que estos
formatters necesitan para decidir cómo agrupar cada propiedad — mismo hueco
ya documentado en ``web_read`` (rama ``properties`` de este mismo archivo).

**``onchange`` (1 método) + ``RecordSnapshot`` (clase, 5 métodos: ``__init__``,
``__eq__``, ``fetch``, ``has_changed``, ``diff``).** Requiere el motor de
caché/cómputo de recordset de Odoo: registros virtuales (``self.new()``),
``_update_cache``, el pool de dependencias (``field_computed``/
``field_depends``), ``modified()`` y el despachador
``_apply_onchange_methods`` que invoca los métodos ``@api.onchange``
registrados. Medido hoy: ``grep -rln "_update_cache\\|field_computed\\|def
modified(\\|_apply_onchange_methods" src/orm/*.py src/addons/*/models/*.py``
→ **0**; ``grep -rn "def new(" src/orm/*.py`` → **0**. No es una pieza
faltante puntual del ORM (como ``sequence.mixin`` o el campo
``store=False``, que sí se construyeron) — es el subsistema de cómputo
entero de Odoo, ausente por diseño (Django computa en ``save()``/``clean()``,
explícito por modelo, ver ``orm/decorators.py``). Construirlo sería un
proyecto de infraestructura propio, no un símbolo de este archivo.
``cleanup``/``adapt`` (closures internos de ``web_read``/``read_progress_bar``
en la referencia, para des-envolver ``NewId``) no aplican: sin ``onchange``
no hay registros ``NewId`` fluyendo por este archivo — ``web_read`` y
``read_progress_bar`` ya operan sobre filas reales de la base.

**``ResCompany`` (clase, 4 métodos: ``create``, ``write``,
``_get_asset_style_b64``, ``_update_asset_style``).** Regeneran un adjunto
CSS por-compañía (``web.asset_styles_company_report``) desde
``primary_color``/``secondary_color`` vía ``ir.qweb._render``. Medido hoy:
``grep -rn "styles_company_report" src/addons/`` → **0** (no existe ese
adjunto/vista); ``grep -n "_render" src/addons/*/models/template_expressions.py`` → **0**
(``ir.qweb`` no tiene método de render HTML). El pipeline de *assets* de
este proyecto ya es una decisión tomada, no una laguna:
``base/models/assetsbundle.py`` documenta que Webpack (``ui``) reemplaza el
empaquetador dinámico de Odoo — no hay *bundle* CSS por-compañía que
invalidar en cada request porque no hay *bundle* dinámico de ningún tipo.

**``web_override_translations`` (1 método).** Sobrescribe la traducción
inline de un campo para el idioma activo. Medido hoy: ``grep -rln
"update_field_translations\\|get_installed(" src/ --include="*.py"`` → **0**.
``res.lang`` existe (``base/models/res_lang.py``) pero es catálogo de
locales/formatos (config), no una capa de **almacenamiento** de traducciones
por campo (no hay ``JSONField`` por-idioma en ningún campo del árbol) — sin
esa capa, no hay qué sobrescribir.
"""
import re
from collections import defaultdict

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
from tools.translate import _

__all__ = ['lazymapping', 'AND', 'OR', 'Base']

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
                              offset=0, limit=None, order=None):
        """≙ referencia ``formatted_read_group`` (``models.py:800-914``).

        ``queryset`` reemplaza ``domain`` (convención QuerySet-first del
        módulo, ya establecida en :meth:`read_progress_bar`). Sin soporte de
        ``group_expand`` real (ver ``_web_read_group_field_expand``) ni de
        ``fill_temporal`` (declarado ausente, familia arriba). ``having``,
        si se pasa, es un ``Q`` que ya referencia los alias internos que
        produce esta función para cada ``spec`` de ``aggregates`` — no hay
        traducción automática spec→alias expuesta hoy porque ningún
        llamador del árbol lo necesita todavía.
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
        return cls._web_read_group_format(model, groupby, spec_to_key, aggregates, rows)

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
    def formatted_read_grouping_sets(cls, queryset, grouping_sets, aggregates=(), order=None):
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
            cls.formatted_read_group(queryset, list(groupby), aggregates, order=order)
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
