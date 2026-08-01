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
- **``action_id`` degradado a Integer plano, sin FK**: Odoo lo declara
  Many2one a ``ir.actions.actions``. **Actualizado** (porte de
  ``ir_actions.py``): ese modelo **ya existe**
  (``grep -rn "^class IrActionsActions" src/`` → **1**), así que el Integer
  plano es ahora deuda cerrable — el FK real cabe. Se deja el cambio para su
  propio pase porque toca la migración de esta tabla, no de rebote desde
  ``ir_actions``. Mientras tanto sigue siendo campo de control mínimo (mismo
  criterio que ``res_id`` en ``ir_attachment``) en vez de omitirse, porque el
  invariante "un filtro por defecto por acción" lo referencia.
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

import fields
import models


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
            'Modelo técnico referenciado, p. ej. "catalogue.Product" (Odoo '
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
    action_id = fields.Integer(
        null=True, blank=True,
        help_text=(
            'ID de la acción/menú al que aplica el filtro (Odoo action_id — '
            'Many2one a ir.actions.actions). NULL = aplica a todos los menús '
            'del modelo. Sigue siendo Integer plano: ir.actions.actions ya '
            'está portado, así que el FK real cabe, pero cambiarlo migra esta '
            'tabla y va en su propio pase.'
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
        constraints = [
            models.UniqueConstraint(
                fields=['model_id', 'user', 'action_id', 'name'],
                name='uq_ir_filters_model_user_action_name',
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
