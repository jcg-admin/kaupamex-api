"""``ir.actions.server`` / ``ir.cron`` — extensión de ``base_automation``
(≙ los dos ``_inherit`` de la referencia,
``base_automation/models/ir_actions_server.py``).

Por qué es ``chain_method``, no una subclase ni una columna nueva
=====================================================================

Django no admite declarar un método NI un campo nuevo sobre una clase de
modelo ya definida en otro addon evaluando su cuerpo de nuevo — la
extensión de un modelo ajeno en este árbol se hace desde ``ready()``,
colgando funciones con ``orm.method_chain.chain_method`` (ver su
docstring: es el reemplazo de ``super()`` para el idioma ``_inherit`` sin
MRO real). El campo nuevo, ``base_automation_id``, lo cuelga
``extend_model(campos=…)`` desde el mismo ``ready()``
(:func:`add_base_automation_id`).

Los seis que este docstring declaraba sin receptor — y su medición nueva
=====================================================================

Decía: *«``usage`` (Selection ``selection_add``), ``_warning_depends``,
``_get_warning_messages``, ``_get_children_domain``,
``_compute_available_model_ids`` … medido: 0 hits de ese vocabulario en
``src/addons/base/models/ir_actions.py``. No hay base que extender»*, y
declaraba ``_get_eval_context`` sin contexto que extender.

**Los seis tienen base hoy.** Medido de nuevo sobre el mismo archivo:

.. code-block:: text

   grep -nE "def _warning_depends|def _get_warning_messages\
   |def _get_children_domain|def _compute_available_model_ids\
   |def _get_eval_context" \
       src/addons/base/models/ir_actions.py
   → 1181, 1204, 1431, 1308, 2089   (cinco, ninguno ausente)

   grep -n "usage = fields.Selection" src/addons/base/models/ir_actions.py
   → 903                            (el campo que ``selection_add`` amplía)

La medición vieja era correcta el día que se escribió y dejó de serlo sin
que nadie tocara este archivo: ``ir_actions.py`` creció después. Es la misma
clase de veredicto caducado que :ref:`h-api-1018` registró para
``base_install_request``, y la razón por la que un bloqueo se declara **por
símbolo con su medición** y se vuelve a medir al retomarlo.

``base_automation_id``, columna de la acción de servidor
=====================================================================

La fuente lo declara en este ``_inherit`` (``:17``). Una tabla-liga
(``BaseAutomationAction``, ``OneToOneField`` sobre la acción) lo sustituyó
hasta la migración ``base_automation/0010``; hoy es la columna de la fuente
y los tres métodos que la leen la leen directamente.

``_get_eval_context`` se porta **entero** aunque ningún corredor de este
árbol evalúe el modo ``code``: es el contrato que un corredor propio
recibiría, y el mismo criterio con que ``ir_actions.py`` porta su versión
base (*"se porta entero aunque aquí ningún corredor lo evalúe"*).

Lo que SÍ se instala
=====================================================================

``action_open_automation`` sobre ambas clases — sin base previa (métodos
nuevos), ``chain_method`` los instala tal cual (misma forma que
``account_payment/models/account_journal.py``, rama ``previous is None``).
Devuelve el registro ``BaseAutomation`` en vez de un dict ``ir.actions.
act_window`` — no hay cliente web al que devolvérselo.

Se instala desde ``BaseAutomationConfig.ready()`` (excepción #4 de
``no-lazy-imports.md``), nunca por import directo de otro módulo — el
propio ``chain_method(...)`` de abajo corre una sola vez, al importarse
este módulo.
"""

from fields import Domain, Many2one
from tools.json import scriptsafe
from tools.translate import _

from addons.base.models import IrActionsServer, IrCron
from addons.base_automation.models.base_automation import (
    get_webhook_request_payload,
)
from orm.method_chain import chain_method, extend_list, wrap_method
from orm.model_classes import extend_model, extend_selection_choices

#: ≙ el valor que ``selection_add`` añade a ``usage``
#: (``odoo19c: addons/base_automation/models/ir_actions_server.py:14-16``).
USAGE_BASE_AUTOMATION = 'base_automation'


def _automation_of(action):
    """La regla ligada a esta acción, o ``None``.

    ≙ leer ``action.base_automation_id`` en la fuente.
    """
    return action.base_automation_id or None


def _action_open_automation(self):
    """≙ ``IrActionsServer.action_open_automation`` de la referencia."""
    return self.base_automation_id or None


def _ircron_action_open_automation(self):
    """≙ ``IrCron.action_open_automation`` de la referencia — delega en la
    acción servidor delegada (``ir_actions_server``, ``_inherits``; ver
    ``src/addons/base/models/ir_cron.py``)."""
    return _action_open_automation(self.ir_actions_server)


def _warning_depends(cls):
    """≙ ``_warning_depends`` (``odoo19c: :20-25``) — ACUMULA sobre la base.

    La fuente escribe ``super()._warning_depends() + ['model_id',
    'base_automation_id']``. Aquí la acumulación la hace
    ``combine=extend_list``
    de :mod:`orm.method_chain`, que es el mecanismo de este árbol para el
    ``super() + [...]`` de la referencia.

    Los dos nombres son campos de la acción de servidor: ``model_id`` (la
    base) y ``base_automation_id`` (este addon).
    """
    return ['model_id', 'base_automation_id']


def _get_warning_messages(self, previous, seen=None):
    """≙ ``_get_warning_messages`` (``:27-39``) — un aviso más, el séptimo.

    Va por ``overrides=`` (``wrap_method``) y no por ``combine=``: la fuente
    llama a ``super()`` **primero**, guarda su lista y le añade la suya, y el
    mensaje que añade se redacta con datos que sólo se leen después. El
    ``ensure_one()`` de la fuente no se porta — aquí ``self`` es una instancia.

    El aviso es el mismo: si la acción está ligada a una regla y el modelo de
    las dos no coincide, se avisa nombrando a ambas.
    """
    warnings = previous(seen=seen)
    automation = _automation_of(self)
    if automation is not None and self.model_id != automation.model_id:
        warnings.append(
            _(
                'El modelo de la acción %(action_name)s debería coincidir con'
                ' el de la regla automatizada %(rule_name)s.',
                action_name=self.name,
                rule_name=automation.name,
            )
        )
    return warnings


def _get_children_domain(cls, previous):
    """≙ ``_get_children_domain`` (``:41-45``) — y su comentario, verbatim.

    *"As automation rules' actions does not have a parent, we make sure multi
    actions can not link to automation rules' actions."*

    La fuente lo escribe ``super() & Domain("base_automation_id", "=",
    False)``.
    Va por ``overrides=`` porque el ``&`` necesita el dominio de la base **en
    la mano**, no un resultado que se combine después.
    """
    return previous() & Domain("base_automation_id", "=", False)


def _compute_available_model_ids(self, previous):
    """≙ ``_compute_available_model_ids`` (``:47-53``) — el límite estricto.

    Docstring de la fuente, verbatim: *"Stricter model limit: based on
    automation rule"*. Corre el cómputo de la base y, si el uso es
    ``base_automation``, recorta al modelo de la regla — y a **nada** si ese
    modelo no estaba en el universo que la base devolvió, que es la asimetría
    que la fuente escribe con ``if rule_model in action.available_model_ids``.

    Va por ``overrides=`` porque el recorte opera sobre lo que la base
    devolvió, no junto a ello. Asigna el campo, como la fuente
    (``action.available_model_ids = rule_model``): la base ya lo asignó con
    el universo entero, y sin reasignarlo el recorte se perdería.
    """
    available = previous()
    if self.usage != USAGE_BASE_AUTOMATION:
        return available
    automation = _automation_of(self)
    rule_model = automation.model_id if automation else None
    value = [rule_model] if rule_model in available else []
    self.available_model_ids = value
    return value


def _get_eval_context(self, previous, action=None):
    """
    ≙ ``_get_eval_context`` (``:55-62``) — ``json`` y ``payload`` en modo
    código.

    La fuente añade dos claves al contexto que su evaluador restringido recibe:
    ``json`` (el ``dumps`` seguro para incrustar en una etiqueta ``<script>``)
    y, si la petición trae cuerpo, ``payload``. Se porta entero por el mismo
    criterio con que la base porta su versión: es el contrato que un corredor
    propio recibiría, aunque hoy ninguno evalúe el modo ``code``.

    ``scriptsafe`` es el símbolo de este árbol para
    ``odoo.tools.json.scriptsafe`` (``src/tools/json.py:72``), y se publica
    bajo la clave ``json`` que la fuente usa.
    """
    context = previous(action=action)
    action = self if action is None else action
    if getattr(action, 'state', None) == 'code':
        context['json'] = scriptsafe
        payload = get_webhook_request_payload()
        if payload:
            context['payload'] = payload
    return context


def add_base_automation_usage():
    """≙ ``usage = fields.Selection(selection_add=[('base_automation', …)])``.

    Con su ``ondelete={'base_automation': 'cascade'}``, que la fuente declara
    en la misma expresión: la política dice qué pasa con las filas que
    guardaban el valor si el valor desaparece.
    """
    extend_selection_choices(
        IrActionsServer,
        'usage',
        [(USAGE_BASE_AUTOMATION, 'Automation Rule')],
        ondelete={USAGE_BASE_AUTOMATION: 'cascade'},
    )


def add_base_automation_id():
    """≙ ``base_automation_id = fields.Many2one('base.automation',
    string='Automation Rule', index='btree_not_null', ondelete='cascade')``
    (``odoo19c: addons/base_automation/models/ir_actions_server.py:17``)."""
    extend_model('base', 'IrActionsServer', campos={
        'base_automation_id': Many2one(
            'base_automation.BaseAutomation',
            ondelete='cascade',
            index='btree_not_null',
            db_index=False,
            related_name='+',
            db_column='base_automation_id',
            verbose_name='Automation Rule',
        ),
    })


add_base_automation_usage()
add_base_automation_id()
chain_method(
    IrActionsServer, 'action_open_automation', _action_open_automation
)
chain_method(IrCron, 'action_open_automation', _ircron_action_open_automation)
chain_method(
    IrActionsServer,
    '_warning_depends',
    classmethod(_warning_depends),
    combine=extend_list,
)
wrap_method(IrActionsServer, '_get_warning_messages', _get_warning_messages)
wrap_method(
    IrActionsServer, '_get_children_domain', classmethod(_get_children_domain)
)
wrap_method(
    IrActionsServer,
    '_compute_available_model_ids',
    _compute_available_model_ids,
)
wrap_method(IrActionsServer, '_get_eval_context', _get_eval_context)
