"""``web`` — capa de datos del cliente web. Adaptación de Odoo, licencia LGPL-3.

Fuente: ``odoo19c: addons/web/models/models.py`` (``odoo-tools@622ddc2a``,
2360 líneas). Completado 2026-08-07 contra H-API-369 / DEC-FW-04 — el addon
era una cáscara de solo controladores (``controllers/session.py`` +
``schema.py`` + ``serializers.py`` + ``urls.py``, 0 modelos).

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)``,
igual criterio que ``porte-completo-no-parcial.md``): **40** métodos de 4
clases (``lazymapping``, ``Base``, ``ResCompany``, ``RecordSnapshot``).
**11 portados** (adaptados), **29 declarados ausentes** con razón — ver abajo.
No hay recorte silencioso: cada ausencia cita por qué.

Recordset (Odoo) → QuerySet (Django) — la adaptación estructural
==================================================================

La referencia opera sobre un *recordset*: ``self`` puede contener 0..N ids
simultáneamente, y ``web_read``/``web_search_read``/``web_name_search`` son
métodos de instancia que leen ese conjunto. Django separa instancia
(una fila) de manager/queryset (N filas) — no hay tercer tipo que sea "0..N
filas con métodos propios". La adaptación:

- Los métodos que en la referencia procesan **varios registros a la vez**
  (``web_read``, ``web_search_read``, ``web_name_search``, ``web_save_multi``,
  ``web_resequence``, ``read_progress_bar``, ``_add_groupby_values``) se
  portan como **``classmethod``** que reciben el ``QuerySet`` explícito en
  vez de leerlo de ``self`` — es la misma información (qué filas), pasada
  por parámetro en lugar de estado implícito del recordset.
- Los métodos que la referencia documenta como operando sobre **un solo
  registro objetivo** (``web_save``, que hace ``self.write`` o ``self =
  self.create(vals)``) se portan como método de **instancia** — ``self`` es
  la fila, igual que en la referencia cuando ``self`` tiene 0 o 1 registro.

Portados (11, adaptados)
=========================

``lazymapping.__missing__`` · ``AND``/``OR`` (módulo, no cuentan en los 40 —
ver nota) · ``web_name_search`` · ``web_search_read`` ·
``_format_web_search_read_results`` · ``web_save`` · ``web_save_multi`` ·
``web_read`` · ``web_resequence`` · ``_get_read_group_order`` ·
``_add_groupby_values`` · ``read_progress_bar``.

Ausentes (29) — con razón, no con silencio
============================================

**Familia ``read_group`` de formato de vista (11 métodos: ``web_read_group``,
``_formatted_read_group_with_length``, ``_open_groups``,
``formatted_read_grouping_sets``, ``formatted_read_group``,
``_web_read_group_field_expand``, ``_web_read_group_expand``,
``_web_read_group_fill_temporal``, ``_web_read_group_format``,
``_web_read_group_groupby_formatter``,
``_web_read_group_groupby_properties_formatter``).** Implementan el motor de
agrupamiento con *grouping sets*, relleno de huecos temporales (calendario
para vistas de gráfico/pivote) y formato de propiedades dinámicas para
list/kanban/pivot/graph — la vista **dinámica declarada en arch XML** de
Odoo. Sin esa vista (este proyecto usa componentes React explícitos, DEC-03
de ``ui-adaptacion-nativa``) no hay consumidor ni contrato que fije la forma
del *fold*/*grouping set*. ``web_read_group`` en sí se deja fuera porque
llama a ``formatted_read_group``/``_open_groups`` — portar la entrada sin sus
dependientes produciría una llamada a un método inexistente, no un símbolo
funcional (``porte-completo-no-parcial.md``, "cuenta como portado cuando hace
lo que hace el de la referencia"). ``_get_read_group_order`` y
``_add_groupby_values`` SÍ se portan pese a esto: son autocontenidos (no
llaman a los ausentes) y quedan como bloques de construcción para quien
retome el pipeline completo.

**Familia ``search_panel`` (7 métodos: ``_search_panel_field_image``,
``_search_panel_domain_image``, ``_search_panel_global_counters``,
``_search_panel_sanitized_parent_hierarchy``,
``_search_panel_selection_range``, ``search_panel_select_range``,
``search_panel_select_multi_range``).** Backend del widget de panel de
búsqueda (facetas jerárquicas con contador, categoría + filtro) declarado en
``<search_panel>`` del arch XML. El frontend de este proyecto implementa cada
filtro como componente React explícito (mismo DEC-03) — no hay vista genérica
que declare "estas son las facetas de este modelo".

**``onchange`` (1 método).** Requiere un grafo de dependencias declarado por
la vista (``_onchange_spec`` derivado del arch XML) más un despachador que lo
recorra. El decorador ``@api.onchange`` de este proyecto
(``orm/decorators.py:37``) sólo anota metadata (``func._onchange = fields``)
— **no existe despachador que la consuma** (medido: 0 usos de
``.onchange(`` sobre un modelo en todo ``src/addons``). Construir el grafo +
despachador sin un solo consumidor sería arquitectura especulativa,
justo lo que ``auto-audit-before-writing.md`` prohíbe.

**``web_override_translations`` (1 método).** Edición inline multi-idioma del
cliente web. Este proyecto no tiene capa de traducción de contenido en tiempo
de ejecución (equivalente a ``ir.translation``) — es de locale único
(``redaccion-tecnica-es.md``: identificadores en inglés, prosa en español,
sin capa de traducción de datos).

**``ResCompany.create``/``write`` (2 métodos).** En la referencia sólo
invalidan la caché de plantillas de ensamblado de *assets* tras cambiar
colores/logo de la compañía. Este proyecto compila los estáticos con Webpack
en build-time (``ui: webpack.config.js``); no hay *asset bundle* dinámico
por-compañía que invalidar en cada request.

**``ResCompany._get_asset_style_b64``/``_update_asset_style`` (2 métodos).**
Generan un snippet SCSS en base64 desde ``primary_color``/``secondary_color``
del ``res.company`` (que sí existen aquí:
``base/models/res_company.py:273-276``) y lo escriben en un adjunto que el
motor de ensamblado de *assets* de Odoo sirve al cliente. No hay ese motor de
adjuntos-como-bundle aquí. A diferencia de ``search_panel``/``onchange``, esto
NO es "arquitectura ajena" — es una feature de theming de reportes impresos
genuinamente posible (los campos de color ya existen, sin consumidor) y
queda como trabajo futuro nombrado, no como divergencia de mecanismo.

**``RecordSnapshot`` (5 métodos: ``__init__``, ``__eq__``, ``fetch``,
``has_changed``, ``diff``).** Clase de diffing usada exclusivamente por
``onchange()`` para calcular qué cambió antes/después del recálculo. Sin
``onchange`` portado, no tiene consumidor — dependiente directo de la
ausencia anterior.
"""
from collections import defaultdict

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Count

from addons.base.models.ir_model import Base as _BaseRoot
from orm.domains import AND as _domain_and
from orm.domains import OR as _domain_or

__all__ = ['lazymapping', 'AND', 'OR', 'Base']


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
    # El pipeline completo (``web_read_group`` + 10 formatters) está
    # declarado ausente arriba. Estos dos SÍ se portan: no llaman a ningún
    # ausente, y son utilidad genérica de agrupamiento aunque hoy no tengan
    # llamador (quedan como scaffolding, DEC-FW-04 "sin recorte").

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
        ``formatted_read_group`` (declarado ausente arriba): el resultado
        observable — conteo por valor de ``group_by`` × valor de
        ``progress_bar['field']`` — es el mismo; el camino para producirlo
        es ``.values().annotate(Count)`` en vez del pipeline de grouping
        sets.
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
