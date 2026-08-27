"""``utm.mixin`` — el mixin que cuelga los tres ejes UTM de un modelo.

Adaptación fiel de Odoo ``utm/models/utm_mixin.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3). Los 7 símbolos de la fuente están portados; ninguno se
omite.

El mixin hace dos cosas distintas, y conviene no confundirlas:

1. **Cuelga los tres campos** (``campaign_id``/``source_id``/``medium_id``) del
   modelo que lo hereda — un prospecto, un pedido, una suscripción.
2. **Alberga el generador de nombres únicos** (``_get_unique_names``), que
   ``utm.campaign``, ``utm.medium`` y ``utm.source`` invocan al crearse. Vive
   aquí, y no en cada modelo, porque los tres comparten el algoritmo del
   contador ``[N]``; la fuente lo declara igual.

Divergencias declaradas (``porte-completo-no-parcial.md`` exige un desenlace
por símbolo, no el silencio):

- ``default_get`` **se porta con firma de este árbol** —
  ``default_get(cls, field_names, values=None, request=None)``, la forma que
  ya usan ``stock.location``, ``stock.move`` y ``stock.rule``. La fuente lo
  invoca el ORM al abrir un formulario; aquí lo invoca quien construye los
  valores (serializer o vista), pasándole la petición.
- **El filtro por vendedor no se porta**: la fuente salta la captura UTM si
  ``self.env.user.has_group('sales_team.group_sale_salesman')``. ``has_group``
  **no existe en este árbol** — medido: ``def has_groups`` da 0 en
  ``res_users.py``, y su porte es la tarea **#399**. Sin él la condición no se
  puede evaluar, y fabricar un sustituto (p. ej. mirar la pertenencia a un
  grupo de Django) cambiaría el criterio. Sucesor: tarea **#399**; se cablea
  al cerrarla.
- ``active_test=False`` de ``_find_or_create_record`` no tiene análogo: este
  ORM no filtra los archivados por defecto, así que la búsqueda ya los ve. La
  fuente necesita desactivarlo explícitamente; aquí es el estado base.
- **El nombre de las cookies diverge a propósito**: la fuente las llama
  ``odoo_utm_campaign``/``_source``/``_medium``
  (``odoo19c: utm_mixin.py:12-14``); aquí son ``kaupamex_utm_*``. Es el único
  dato de este porte que **sale al navegador del usuario**, y ahí la marca del
  producto es Kaupamex, no la del árbol que se adapta
  (``terminologia-l0-company.md``). El resto del contrato —parámetro de URL y
  campo del mixin— se conserva verbatim: son las dos mitades que sí hablan con
  la referencia. Ver :ref:`h-api-633`.
"""
import itertools
import re
from collections import defaultdict

import fields
import models
from orm.domains import Domain, to_q
from orm.registry import model_by_name

#: Los tres ejes, en el orden de la fuente: parámetro de URL, campo del mixin y
#: nombre de la cookie. Es el contrato que ``ir_http`` lee para saber qué
#: capturar, y ``default_get`` para saber qué rellenar.
TRACKING_FIELDS = [
    # ("URL_PARAMETER", "FIELD_NAME_MIXIN", "NAME_IN_COOKIES")
    ('utm_campaign', 'campaign_id', 'kaupamex_utm_campaign'),
    ('utm_source', 'source_id', 'kaupamex_utm_source'),
    ('utm_medium', 'medium_id', 'kaupamex_utm_medium'),
]


class UtmMixin(models.Model):
    """``utm.mixin`` — los tres ejes de marketing sobre un modelo cualquiera."""

    _name = 'utm.mixin'
    _description = 'UTM Mixin'

    # Los tres son ``index='btree_not_null'`` en la fuente — índice B-tree
    # **parcial**, que excluye las filas con NULL. Aquí el FK ya lleva índice
    # por construcción de Django (``db_index=True`` es su defecto y se escribe
    # explícito para que se lea contra la fuente). El tramo parcial no se
    # declara: en un modelo **abstracto** un ``Meta.indexes`` propaga a cada
    # concreto y sus nombres colisionarían. Quien herede el mixin y necesite el
    # índice parcial lo declara en su propio ``Meta`` — el rodeo está dibujado,
    # no omitido.
    # ≙ ``campaign_id``.
    campaign_id = fields.Many2one(
        'utm.UtmCampaign', null=True, blank=True, on_delete=models.SET_NULL,
        db_index=True, related_name='+', verbose_name='Campaña',
        help_text='Nombre con el que se distingue cada esfuerzo de campaña, '
                  'p. ej. Fall_Drive, Christmas_Special.',
    )
    # ≙ ``source_id``.
    source_id = fields.Many2one(
        'utm.UtmSource', null=True, blank=True, on_delete=models.SET_NULL,
        db_index=True, related_name='+', verbose_name='Fuente',
        help_text='Origen del enlace: un buscador, otro dominio, o el nombre '
                  'de una lista de correo.',
    )
    # ≙ ``medium_id``.
    medium_id = fields.Many2one(
        'utm.UtmMedium', null=True, blank=True, on_delete=models.SET_NULL,
        db_index=True, related_name='+', verbose_name='Medio',
        help_text='Método de entrega: postal, correo, banner.',
    )

    class Meta:
        abstract = True

    # -- captura desde la petición -------------------------------------------

    @classmethod
    def default_get(cls, field_names, values=None, request=None):
        """≙ ``default_get`` (``odoo19c: utm_mixin.py:26-46``).

        Rellena los tres ejes desde las cookies que ``ir_http`` dejó puestas.
        Si el valor de la cookie es un texto (y no un id), se busca o se crea
        el registro correspondiente — igual que la fuente.
        """
        result = dict(values or {})
        # El filtro por vendedor de la fuente no se evalúa aquí — ver la
        # divergencia declarada en el docstring del módulo (tarea #399).
        for _url_param, field_name, cookie_name in cls.tracking_fields():
            if field_name not in field_names:
                continue
            value = None
            if request is not None:
                # ``ir_http`` guarda los parámetros de URL en una cookie.
                value = request.COOKIES.get(cookie_name)
            if isinstance(value, str) and value:
                comodel_name = _COMODEL_BY_FIELD[field_name]
                record = cls._find_or_create_record(comodel_name, value)
                value = record.pk if record is not None else None
            if value:
                result[field_name] = value
        return result

    @classmethod
    def tracking_fields(cls):
        """≙ ``tracking_fields`` (``:48-60``) — los tres ejes UTM.

        La fuente advierte que este método **no** se puede sobreescribir desde
        un modelo que herede el mixin: la herencia sobre ``AbstractModel`` no
        lo permite, y por eso allá se invoca siempre como
        ``self.env['utm.mixin'].tracking_fields()``. Aquí la limitación no
        existe —es un ``classmethod`` sobre una clase abstracta de Django—
        pero la lista sigue siendo una sola, declarada en el módulo, para que
        ``ir_http`` y ``default_get`` lean el mismo contrato.
        """
        return list(TRACKING_FIELDS)

    @classmethod
    def _tracking_models(cls):
        """≙ ``_tracking_models`` (``:62-68``) — los modelos que los ejes citan.

        La fuente lo deriva de ``self._fields[fname].comodel_name`` filtrando
        por ``type == 'many2one'``. Aquí los tres campos son FK por
        construcción, así que la derivación se hace sobre el mapa del módulo.
        """
        fnames = {fname for _, fname, _ in cls.tracking_fields()}
        return {
            _COMODEL_BY_FIELD[fname]
            for fname in fnames
            if fname in _COMODEL_BY_FIELD
        }

    @classmethod
    def find_or_create_record(cls, model_name, name):
        """≙ ``find_or_create_record`` (``:70-86``) — la versión de frontend.

        Para un modelo UTM delega en ``_find_or_create_record``; para
        cualquier otro crea sin más, apoyándose en el control de acceso
        estándar. Devuelve el par ``{'id', 'name'}`` y no el registro, igual
        que la fuente: quien la consume (``website_links``) es una llamada
        remota y necesita datos, no un recordset.
        """
        if model_name in cls._tracking_models():
            record = cls._find_or_create_record(model_name, name)
        else:
            model = model_by_name(model_name)
            if model is None:
                raise LookupError(f'Modelo desconocido: {model_name}')
            rec_name = getattr(model, '_rec_name', 'name')
            record = model.objects.create(**{rec_name: name})
        return {'id': record.pk, 'name': str(record)}

    @classmethod
    def _find_or_create_record(cls, model_name, name):
        """≙ ``_find_or_create_record`` (``:88-103``) — busca por nombre o crea.

        ``=ilike`` sin comodines es coincidencia exacta sin distinguir
        mayúsculas: aquí ``name__iexact``.

        **Divergencia de robustez, no de comportamiento:** la fuente sólo
        asigna ``record`` dentro del ``if cleaned_name:`` y lo lee después sin
        guarda — con un nombre en blanco levantaría ``UnboundLocalError``.
        Aquí ``record`` arranca en ``None``, así que un nombre en blanco crea
        el registro con el nombre en blanco, que es lo que la fuente pretende.
        """
        model = model_by_name(model_name)
        if model is None:
            raise LookupError(f'Modelo desconocido: {model_name}')

        record = None
        cleaned_name = (name or '').strip()
        if cleaned_name:
            record = model.objects.filter(name__iexact=cleaned_name).first()

        if record is None:
            record_values = {'name': cleaned_name}
            if any(f.name == 'is_auto_campaign' for f in model._meta.get_fields()):
                record_values['is_auto_campaign'] = True
            record = model.objects.create(**record_values)

        return record

    # -- el contador [N] -----------------------------------------------------

    @classmethod
    def _get_unique_names(cls, model_name, names, skip_record_ids=()):
        """≙ ``_get_unique_names`` (``:105-164``) — nombres únicos con contador.

        Toma una lista de nombres y devuelve, en el mismo orden, el nombre que
        hay que grabar (con su contador ``[N]`` si hiciera falta)::

            El nombre "test" ya existe en la base
            Entrada:  ['test', 'test [3]', 'bob', 'test', 'test']
            Salida:   ['test [2]', 'test [3]', 'bob', 'test [4]', 'test [5]']

        ``skip_record_ids`` es aquí un **parámetro**, no una clave de contexto
        (``utm_check_skip_record_ids``): este ORM no tiene el contexto de
        entorno de la fuente, y el dato es un argumento de la llamada, no
        ambiente. Sirve para lo mismo — que un registro no colisione consigo
        mismo al actualizarse, e incremente el contador en cada guardado.
        """
        model = model_by_name(model_name)
        if model is None:
            raise LookupError(f'Modelo desconocido: {model_name}')

        # Se quita el contador de cada nombre antes de buscar.
        names_without_counter = {cls._split_name_and_count(name)[0] for name in names}

        # Los nombres parecidos que ya están en la base.
        search_domain = Domain.OR(
            Domain('name', 'ilike', name) for name in names_without_counter
        )
        if skip_record_ids:
            search_domain &= Domain('id', 'not in', list(skip_record_ids))
        existing_names = set(
            model.objects.filter(to_q(search_domain, model))
            .values_list('name', flat=True)
        )

        # Contadores ya usados por cada nombre, tomando la lista del argumento
        # y los nombres que hay en la base.
        used_counters_per_name = {
            name: {
                cls._split_name_and_count(existing_name)[1]
                for existing_name in existing_names
                if existing_name == name or existing_name.startswith(f'{name} [')
            } for name in names_without_counter
        }
        # Contador que avanza solo por nombre; rellena los huecos del anterior.
        current_counter_per_name = defaultdict(lambda: itertools.count(1))

        result = []
        for name in names:
            if not name:
                result.append(None)
                continue

            name_without_counter, asked_counter = cls._split_name_and_count(name)
            existing = used_counters_per_name.setdefault(name_without_counter, set())
            if asked_counter and asked_counter not in existing:
                count = asked_counter
            else:
                # Avanzar hasta dar con un contador libre.
                for count in current_counter_per_name[name_without_counter]:
                    if count not in existing:
                        break
            existing.add(count)
            result.append(
                f'{name_without_counter} [{count}]' if count > 1 else name_without_counter
            )

        return result

    @staticmethod
    def _split_name_and_count(name):
        """≙ ``_split_name_and_count`` (``:166-180``) — el nombre y su contador.

        ::

            "Medium"        -> "Medium", 1
            "Medium [1234]" -> "Medium", 1234
        """
        name = name or ''
        name_counter_re = r'(.*)\s+\[([0-9]+)\]'
        match = re.match(name_counter_re, name)
        if match:
            return match.group(1), int(match.group(2) or '1')
        return name, 1


#: Campo del mixin → nombre del modelo destino en notación de punto. La fuente
#: lo lee de ``self._fields[fname].comodel_name`` en tiempo de ejecución; aquí
#: se declara porque ``_tracking_models`` y ``default_get`` lo consultan desde
#: la clase abstracta, donde los descriptores de FK aún no están resueltos.
_COMODEL_BY_FIELD = {
    'campaign_id': 'utm.campaign',
    'source_id': 'utm.source',
    'medium_id': 'utm.medium',
}
