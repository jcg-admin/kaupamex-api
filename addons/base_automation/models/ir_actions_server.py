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
MRO real). ``base_automation_id``/``action_server_ids`` usan una tabla-liga
en vez de una columna — ver la sección "Decisión de mecanismo" del
docstring de ``base_automation.py``; esa pieza NO va aquí, va donde vive
``BaseAutomationAction``.

Lo que NO se porta de la referencia (bloqueado, pieza ausente)
=====================================================================

``usage`` (Selection ``selection_add``), ``_warning_depends``,
``_get_warning_messages``, ``_get_children_domain``,
``_compute_available_model_ids``: pertenecen al subsistema de
multi-acción + validación de warnings en UI de ``ir.actions.server``, que
esta plataforma no porta (medido: 0 hits de ese vocabulario en
``src/addons/base/models/ir_actions.py``). No hay base que extender.

``_get_eval_context`` (añade ``json``/``payload`` al contexto del modo
``code``): bloqueado — ``IrActionsServer.run()`` levanta
``NotImplementedError`` a propósito (el modo ``code`` no se evalúa; ver
``ir_actions.py``), así que no hay contexto de ejecución que extender
todavía.

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
from addons.base.models import IrActionsServer, IrCron
from addons.base_automation.models.base_automation import BaseAutomationAction
from orm.method_chain import chain_method


def _action_open_automation(self):
    """≙ ``IrActionsServer.action_open_automation`` de la referencia."""
    link = BaseAutomationAction.objects.filter(action=self).first()
    return link.automation if link else None


def _ircron_action_open_automation(self):
    """≙ ``IrCron.action_open_automation`` de la referencia — delega en la
    acción servidor delegada (``ir_actions_server``, ``_inherits``; ver
    ``src/addons/base/models/ir_cron.py``)."""
    return _action_open_automation(self.ir_actions_server)


chain_method(IrActionsServer, 'action_open_automation', _action_open_automation)
chain_method(IrCron, 'action_open_automation', _ircron_action_open_automation)
