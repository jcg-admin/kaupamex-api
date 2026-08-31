"""``ir.filters`` — filtros de búsqueda guardados (Odoo ``base``).

Portación fiel de ``IrFilters``
(``scratchpad/odoo18/extracted/odoo/addons/base/models/ir_filters.py:9-192``,
Odoo 18; ``scratchpad/odoo19x/odoo/addons/base/models/ir_filters.py:7-109``,
Odoo 19) — la **estructura de control** que persiste un filtro de búsqueda
(dominio + contexto + orden) nombrado, opcionalmente privado a un usuario o
compartido globalmente, y opcionalmente marcado "por defecto" para un
modelo. Parte de la iniciativa ``adaptar-familias-odoo-monolito-modular``
(SOL-096), backlog de control núcleo ``ir.*`` (H-BASE-01 C-2).

Drift 18→19 observado (ambas fuentes citadas arriba) — **se porta 18, no 19**:

- **``user_id`` (18, Many2one a ``res.users``) → ``user_ids`` (19, Many2many)**.
  Odoo 19 reemplaza la propiedad de un único usuario por una lista de
  usuarios con los que se comparte el filtro. Esta portación usa el
  **campo 18** (``user_id`` → aquí ``user``, Many2one nullable) porque el
  monolito modela "compartido vs privado" como propiedad binaria de un solo
  dueño (igual patrón que ``company`` en ``ir_sequence``/``ir_attachment``);
  extender a M2M queda fuera de este slice (candidato H-BASE futuro si se
  necesita compartir un filtro con un subconjunto de usuarios).
- **``_sql_constraints`` + ``_auto_init`` (18) ausentes en 19**: 18 declara
  ``name_model_uid_unique`` (unique constraint SQL) + un índice único
  case-insensitive vía ``_auto_init``/``tools.create_unique_index`` sobre
  ``(model_id, user_id, action_id, embedded_action_id, embedded_parent_res_id,
  lower(name))``. 19 los elimina — coherente con el cambio a ``user_ids``
  M2M, que no admite una columna única a nivel SQL. Aquí se porta la
  intención (unicidad de nombre por alcance modelo+usuario+acción) con un
  ``UniqueConstraint`` de Django sobre ``(model_id, user, action_id, name)``;
  la comparación case-insensitive de ``name`` es coherente sin índice
  funcional adicional porque el proyecto usa collation ``utf8mb4_unicode_ci``
  (comparación CI nativa en MariaDB).
- **``sort`` es ``Char``, no ``Text``**, en ambas versiones (18 línea 20, 19
  línea 16) — se porta como ``Char`` (no como ``Text``, que sería la
  suposición ingenua dado que ``domain``/``context`` sí son ``Text``).

Alcance de esta portación — deliberadamente NO se porta:

- **``embedded_action_id`` / ``embedded_parent_res_id``** — **YA NO se omiten.**
  Esta nota decía *"candidato H-BASE cuando/si ``ir.embedded.actions`` se
  porte"*; ese archivo se portó y los dos campos entraron con él
  (``embedded_action`` FK + ``embedded_parent_res_id``). Se conserva el
  registro de que estuvieron diferidos —y por qué— en vez de borrarlo: era
  dependencia ausente, no decisión de scope, y el destino estaba fechado.
- **``action_id`` degradado a Integer plano, sin FK** — **CERRADO** en
  ``base/migrations/0077``. El campo es ahora ``action``, un ``Many2one`` real
  a ``base.IrActionsActions`` con ``on_delete=CASCADE``, como la fuente
  (``:19``). Este bullet decía que el cambio *«se deja para su propio pase
  porque toca la migración de esta tabla»*; eso es diferir, y
  ``hallazgo-abierto-genera-sucesor.md`` no lo admite como bloqueo. Ver
  :ref:`h-api-982`.

  Con la FK entraron los **tres objetos de tabla** que la referencia declara
  (``:26-40``) y este porte tampoco traía: ``_get_filters_index``,
  ``_check_res_id_only_when_embedded_action`` y ``_check_sort_json``. Los tres
  viven en ``Meta`` con su nombre conservado.
- **``company_id``**: NO existe en ``ir.filters`` en ninguna de las dos
  fuentes (18 ni 19) — verificado leyendo el modelo completo. El campo
  especulado en el brief de esta tarea se OMITE por ausencia real en Odoo,
  no se inventa.
- **``_list_all_models`` (Selection dinámico vía SQL sobre ``ir_model``)**:
  UI-only (llena el picker de modelos en el form de Odoo). ``model_id`` se
  porta como ``Char`` plano (mismo patrón que ``res_model`` en
  ``ir_attachment`` — no es FK, es el ``_name`` técnico como string).
- **``copy_data`` / ``check_access`` en ``write()``**: capa de permisos y
  duplicación de UI de Odoo — fuera del modelo de control (DRF
  ``HasCapability``, DEC-11, cuando se exponga por vista).
- **``_get_eval_domain`` (``ast.literal_eval``/``safe_eval`` del dominio)**:
  utilidad de evaluación en runtime de búsqueda — pertenece a la capa de
  negocio que consume el filtro, no al modelo de control.

Comportamiento SÍ portado (adaptado a ``save()``, no a los decoradores
``@api``/``create_or_replace`` de Odoo): la invariante "un solo filtro por
defecto por (``model_id``, ``user``)" — al guardar con ``is_default=True``,
se desmarca cualquier otro filtro por defecto en el mismo alcance
modelo+usuario. Simplificación deliberada frente a Odoo: la fuente
distingue alcance global (``user_id`` NULL → ``UserError`` si ya hay un
default global distinto) de alcance personal (``user_id`` set → sobre-
escritura silenciosa); aquí ambos casos sobre-escriben silenciosamente por
uniformidad de mecanismo ``save()`` sin señal de error hacia arriba.
Candidato H-BASE si se requiere el guardrail de error en el caso global.

Cross-app: ``user`` → ``settings.AUTH_USER_MODEL`` (Odoo ``user_id``,
NULL = filtro compartido/global, igual semántica que Odoo 18 — set = filtro
privado de ese usuario).
"""
from django.conf import settings
from django.db.models.lookups import Exact

import fields
import models


class JsonbTypeOf(models.Func):
    """``jsonb_typeof(<expr>::jsonb)`` — el tipo JSON de una columna de texto.

    La referencia no necesita un ayudante: su ``models.Constraint`` recibe el
    SQL como cadena (``odoo19c: ir_filters.py:37-40``). Aquí la restricción se
    declara con el ORM, así que el ``::jsonb`` y la llamada se expresan como
    ``Func``.

    Vive aquí, junto a su **único** consumidor —medido: ``grep -rn
    jsonb_typeof src/ addons/`` daba 0 antes de este porte—. Si aparece un
    segundo, su hogar pasa a ser ``src/tools/sql.py``, que es donde la
    referencia guarda los ayudantes de SQL.
    """

    function = 'jsonb_typeof'
    template = '%(function)s(%(expressions)s::jsonb)'
    output_field = models.CharField()


class IrFilters(models.Model):
    """``ir.filters`` — filtro de búsqueda nombrado (dominio+contexto+orden)."""

    name = fields.Char(
        max_length=256, help_text='Nombre del filtro (Odoo name).',
    )
    user = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name='ir_filters',
        help_text=(
            'Dueño del filtro (Odoo user_id). NULL = filtro compartido/global '
            '(visible para todos); set = filtro privado de ese usuario.'
        ),
    )
    model_id = fields.Char(
        max_length=128,
        help_text=(
            'Modelo técnico referenciado, p. ej. "product.ProductProduct" (Odoo '
            'model_id — Selection dinámico en Odoo, aquí Char plano porque '
            'no es una FK real, igual criterio que res_model en '
            'ir_attachment).'
        ),
    )
    domain = fields.Text(default='[]', help_text='Dominio de búsqueda serializado (Odoo domain).')
    context = fields.Text(default='{}', help_text='Contexto serializado (Odoo context).')
    sort = fields.Char(
        max_length=512, default='[]',
        help_text='Orden serializado (Odoo sort — Char en la fuente, no Text).',
    )
    is_default = fields.Boolean(
        default=False, help_text='Filtro por defecto para el alcance modelo+usuario (Odoo is_default).',
    )
    #: Forma **C** de ADR-029 (#141): el símbolo lleva el nombre que la
    #: referencia declara (``action_id``) y ``db_column`` mantiene la columna
    #: en ``action_id`` — sin él Django la llamaría ``action_id_id``.
    action_id = fields.Many2one(
        'base.IrActionsActions', on_delete=models.CASCADE, db_column='action_id',
        null=True, blank=True, db_index=True, related_name='filter_ids',
        verbose_name='Acción',
        help_text=(
            'Acción/menú al que aplica el filtro (Odoo action_id). NULL = '
            'aplica a todos los menús del modelo. Docstring de la fuente, '
            'verbatim: "The menu action this filter applies to. When left '
            'empty the filter applies to all menus for this model."'
        ),
    )
    # Cierra los dos campos que este archivo dejó diferidos: la referencia
    # declara ``embedded_action_id`` + ``embedded_parent_res_id`` y ambos
    # esperaban a ``ir.embedded.actions``, que ya está portado.
    embedded_action = fields.Many2one(
        'base.IrEmbeddedActions', on_delete=models.CASCADE,
        null=True, blank=True, db_index=True, related_name='filter_ids',
        verbose_name='Acción embebida',
        help_text='Odoo embedded_action_id. Filtro por defecto de una acción '
                  'embebida.',
    )
    embedded_parent_res_id = fields.Integer(
        null=True, blank=True, verbose_name='ID del padre de la embebida',
        help_text='Odoo embedded_parent_res_id.',
    )
    active = fields.Boolean(default=True, help_text='Odoo active.')

    class Meta:
        db_table = 'ir_filters'
        ordering = ['model_id', 'name', '-id']
        verbose_name = 'Filtro'
        verbose_name_plural = 'Filtros'
        #: ≙ ``_get_filters_index`` (``odoo19c: ir_filters.py:26-28``), con
        #: su nombre conservado. Es la consulta que ``get_filters`` hace en
        #: cada apertura de vista.
        indexes = [
            models.Index(
                fields=['model_id', 'action_id', 'embedded_action',
                        'embedded_parent_res_id'],
                name='ir_filters_get_filters_index',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['model_id', 'user', 'action_id', 'name'],
                name='uq_ir_filters_model_user_action_name',
            ),
            #: ≙ ``_check_res_id_only_when_embedded_action`` (``:33-36``).
            #: Comentario de la fuente, verbatim: *"The embedded_parent_res_id
            #: can only be defined when the embedded_action_id field is set."*
            models.CheckConstraint(
                condition=~models.Q(embedded_parent_res_id__isnull=False,
                                    embedded_action__isnull=True),
                name='ir_filters_check_res_id_only_when_embedded_action',
            ),
            #: ≙ ``_check_sort_json`` (``:37-40``) — el ``sort`` se
            #: deserializa como lista, así que un objeto o un escalar
            #: revientan en el lector, lejos de aquí. La condición emite el
            #: SQL de la fuente palabra por palabra:
            #: ``CHECK ("sort" IS NULL OR jsonb_typeof("sort"::jsonb) =
            #: 'array')``.
            models.CheckConstraint(
                condition=(models.Q(sort__isnull=True)
                           | models.Q(Exact(JsonbTypeOf('sort'),
                                            models.Value('array')))),
                name='ir_filters_check_sort_json',
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        """Al guardar con ``is_default=True``, desmarca cualquier otro filtro
        por defecto del mismo alcance modelo+usuario — versión simplificada de
        ``_check_global_default``/``create_or_replace`` de Odoo (ver docstring
        del módulo: aquí sobre-escribe silenciosamente en vez de distinguir
        error-en-alcance-global vs sobre-escritura-en-alcance-personal)."""
        super().save(*args, **kwargs)
        if self.is_default:
            type(self).objects.filter(
                model_id=self.model_id, user_id=self.user_id, is_default=True,
            ).exclude(pk=self.pk).update(is_default=False)
