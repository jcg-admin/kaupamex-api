"""``ir.embedded.actions`` — acciones embebidas en la vista de un registro.

Adaptación de ``odoo/addons/base/models/ir_embedded_actions.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 111 líneas). Una acción embebida es la
que aparece **dentro** de la vista de otro registro, como una pestaña o un
atajo contextual.

Cierre de H-API-142
===================

Este archivo estuvo bloqueado, no descartado, y su destino estaba fechado: sus
dos FK obligatorios apuntan a ``ir.actions.act_window`` e
``ir.actions.actions``, y su M2M a ``res.groups``. Los tres modelos ya existen
—``grep -rn "^class IrActionsActWindow\b" src/`` → **1**,
``^class IrActionsActions`` → **1**, ``^class ResGroups\b`` → **1**— así que el
bloqueo se levanta. [PROVEN]

Cierra además los **dos campos diferidos de ``ir_filters``**
(``embedded_action_id`` / ``embedded_parent_res_id``), que su docstring dejó
anotados como *"candidato H-BASE cuando/si ``ir.embedded.actions`` se porte"*.
El FK inverso llega por el ``related_name='filter_ids'`` de este archivo, sin
tocar ``ir_filters.py``.

La invariante que define el modelo
==================================

La referencia declara **dos** constraints SQL, y las dos importan:

1. ``action_id`` **xor** ``python_method`` — una acción embebida se resuelve
   por acción declarada o por método Python, **nunca por ambos y nunca por
   ninguno**. Sin esta invariante el registro no dice qué ejecutar.
2. Si hay ``python_method``, **``name`` es obligatorio**. La razón está en el
   ``create`` de la fuente: cuando hay ``action_id`` el nombre se **deriva** de
   la acción, pero un método Python no tiene de dónde derivarlo.

El ``create`` de la referencia hace además una **desambiguación** que se porta:
si llegan ``python_method`` y ``action_id`` a la vez, se descarta uno —el
``action_id`` si el método viene con valor, el ``python_method`` si viene
vacío—. Es lo que permite que un formulario mande ambos campos sin violar la
constraint.

Visibilidad: tres condiciones, no una
=====================================

``_compute_is_visible`` sólo devuelve verdadero cuando se cumplen **todas**:

- el ``parent_res_id`` es falso **o** coincide con el registro activo — una
  acción sin ``parent_res_id`` vale para todos los registros del modelo;
- el ``user_id`` es falso **o** es el usuario actual — sin usuario es
  compartida, con usuario es privada;
- el registro activo **casa el dominio** declarado.

Y antes de eso hay dos filtros de guarda: si la acción declara grupos, el
usuario debe tener alguno; y si declara ``python_method``, el modelo padre debe
**tener** ese método. Un método que ya no existe oculta la acción en vez de
reventar al pulsarla.

``is_deletable`` distingue lo que vino de datos declarativos de lo que creó un
usuario: en la referencia, mirando si el ``xml_id`` empieza por ``__export__``
o ``__custom__``. **Actualizado** (porte de ``ir_model.py``):
``grep -rn "^class IrModelData\b" src/`` → **1** clase. La medición de **0**
que sostenía el booleano dejó de ser cierta; el booleano ``system`` **se
queda** igual, y por una razón mejor que la ausencia: leer la procedencia de
un prefijo del ``xml_id`` es un acuerdo implícito entre el cargador y este
modelo, mientras que un campo declarado dice lo mismo sin adivinar. Una
acción de sistema no se borra, una de usuario sí.

Qué NO se porta, con su medición
================================

- **``domain`` evaluado.** Se porta como dato; **no se evalúa aquí**. Misma
  decisión que ``ir_rule.domain_force`` (``api@020e965``) y
  ``ir_actions.server.code``: evaluar expresiones almacenadas es superficie de
  ejecución de código y exige decidir el evaluador explícitamente.
- **``parent_action_id`` como FK a ``ir.actions.act_window``** — **sí** se
  porta, ya no hay razón para degradarlo.
- **``_get_readable_fields``** — la allowlist de campos que el cliente puede
  leer. Pertenece a la capa de serialización; aquí eso lo declara el
  serializer DRF, que es donde el proyecto ya lo tiene (``Meta.fields``
  explícito, nunca ``'__all__'``).
"""
import logging

import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.ir_actions import (
    IrActionsActions,
    IrActionsActWindow,
)
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_users import ResUsers
from addons.base.models.timestamped_mixin import TimeStampedModel

_logger = logging.getLogger(__name__)


class IrEmbeddedActions(TimeStampedModel):
    """Acción embebida en la vista de un registro (``ir.embedded.actions``)."""

    name = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Nombre')
    sequence = fields.Integer(null=True, blank=True, verbose_name='Secuencia')
    parent_action = fields.Many2one(
        IrActionsActWindow, on_delete=models.CASCADE, db_index=True,
        related_name='embedded_action_ids', verbose_name='Acción padre',
        help_text='Odoo parent_action_id, con ondelete cascade.',
    )
    parent_res_id = fields.Integer(
        null=True, blank=True, verbose_name='ID del padre activo',
        help_text='Vacío = la acción vale para todos los registros del modelo.',
    )
    parent_res_model = fields.Char(
        max_length=120, db_index=True, verbose_name='Modelo del padre activo')
    action = fields.Many2one(
        IrActionsActions, on_delete=models.CASCADE, null=True, blank=True,
        db_index=True, related_name='embedded_in', verbose_name='Acción',
        help_text='Exclusivo con python_method (constraint de la fuente).',
    )
    python_method = fields.Char(
        max_length=120, blank=True, default='', verbose_name='Método Python',
        help_text='Método del modelo padre que devuelve una acción. Exclusivo '
                  'con action.',
    )
    user = fields.Many2one(
        ResUsers, on_delete=models.CASCADE, null=True, blank=True,
        db_index=True, related_name='embedded_actions', verbose_name='Usuario',
        help_text='Acción privada de un usuario. Vacío = compartida.',
    )
    default_view_mode = fields.Char(
        max_length=32, blank=True, default='', verbose_name='Vista por defecto',
        help_text='Si está vacío, se usa la vista por defecto de la acción.',
    )
    domain = fields.Char(
        max_length=1024, blank=True, default='[]', verbose_name='Dominio',
        help_text='Se aplica al id activo del modelo padre. Este archivo NO lo '
                  'evalúa — ver el docstring del módulo.',
    )
    context = fields.Json(default=dict, verbose_name='Contexto')
    groups = fields.Many2many(
        ResGroups, blank=True, related_name='embedded_action_ids',
        verbose_name='Grupos',
        help_text='Grupos que pueden ejecutarla. Vacío = todos.',
    )
    system = fields.Boolean(
        default=False, verbose_name='De sistema',
        help_text='Una acción de sistema no se borra. Sustituye al chequeo de '
                  'xml_id de la referencia (no hay ir.model.data aquí).',
    )

    class Meta:
        db_table = 'ir_embedded_actions'
        ordering = ['sequence', 'id']
        verbose_name = 'Acción embebida'
        verbose_name_plural = 'Acciones embebidas'
        constraints = [
            # ``_check_only_one_action_defined``: acción XOR método Python.
            models.CheckConstraint(
                condition=(
                    models.Q(action__isnull=False, python_method='')
                    | models.Q(action__isnull=True) & ~models.Q(python_method='')
                ),
                name='ir_embedded_actions_only_one_action_defined',
            ),
            # ``_check_python_method_requires_name``: con método, hace falta
            # nombre — no hay acción de la que derivarlo.
            models.CheckConstraint(
                condition=(
                    models.Q(python_method='') | ~models.Q(name='')
                ),
                name='ir_embedded_actions_python_method_requires_name',
            ),
        ]

    def __str__(self):
        return self.name or f'acción embebida #{self.pk}'

    @classmethod
    def disambiguate(cls, values):
        """Descarta el campo sobrante cuando llegan los dos — ``create`` de la fuente.

        Si ``python_method`` viene con valor, la acción la da el método y se
        descarta ``action``; si viene vacío, se descarta ``python_method``.
        Es lo que permite que un formulario mande ambos campos sin violar la
        constraint.
        """
        values = dict(values)
        if 'python_method' in values and 'action' in values:
            if values.get('python_method'):
                values.pop('action')
            else:
                values.pop('python_method')
        return values

    def clean(self):
        """Valida las dos invariantes antes de tocar la base."""
        super().clean()
        has_action = self.action_id is not None
        has_method = bool(self.python_method)
        if has_action == has_method:
            raise ValidationError(
                'Debe definirse una acción o un método Python, pero no ambos '
                'ni ninguno.'
            )
        if has_method and not self.name:
            raise ValidationError(
                'Si se define un método Python, el nombre es obligatorio: no '
                'hay acción de la que derivarlo.'
            )

    @property
    def is_deletable(self):
        """¿Se puede borrar? — una acción de sistema, no.

        ≙ ``_compute_is_deletable`` (``odoo19c: base/models/ir_embedded_actions.py``).
        """
        return not self.system

    def check_deletable(self):
        """``_unlink_if_action_deletable`` de la fuente."""
        if not self.is_deletable:
            raise ValidationError(
                'No se puede eliminar una acción embebida por defecto.')

    def is_visible(self, active_record, user, group_ids=(),
                   domain_matches=None):
        """¿Es visible para ``user`` sobre ``active_record``?

        Las **tres** condiciones de ``_compute_is_visible`` más los dos
        filtros de guarda; devuelve falso, no excepción, cuando el método
        declarado ya no existe — una acción rota se oculta en vez de reventar
        al pulsarla.

        ``domain_matches`` es el resultado de evaluar ``domain`` contra el
        registro; se recibe del llamador porque este archivo no evalúa
        dominios (ver el docstring del módulo). ``None`` se lee como "sin
        dominio que restrinja".
        """
        if active_record is None:
            return False

        declared_groups = set(self.groups.values_list('pk', flat=True))
        if declared_groups and not (declared_groups & set(group_ids)):
            return False

        if self.python_method and not hasattr(
                type(active_record), self.python_method):
            return False

        if self.parent_res_id and self.parent_res_id != active_record.pk:
            return False
        if self.user_id and user is not None and self.user_id != user.pk:
            return False
        return domain_matches is not False
