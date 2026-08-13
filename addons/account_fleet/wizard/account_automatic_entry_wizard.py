r"""``account.automatic.entry.wizard`` — DEFERIDO: no hay base que extender.

≙ Odoo ``account_fleet/wizard/account_automatic_entry_wizard.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3):

.. code-block:: python

    class AccountAutomaticEntryWizard(models.TransientModel):
        _inherit = 'account.automatic.entry.wizard'

        def _get_move_line_dict_vals_change_period(self, aml, date):
            res = super()._get_move_line_dict_vals_change_period(aml, date)
            if aml.vehicle_id:
                for move_line_data in res:
                    if move_line_data[2]['account_id'] == aml.account_id.id:
                        move_line_data[2]['vehicle_id'] = aml.vehicle_id.id
            return res

1 símbolo, 1 archivo — bloqueado por dependencia ausente, no omisión
=======================================================================

La referencia extiende (``_inherit``) ``account.automatic.entry.wizard``:
un ``TransientModel`` de ``account`` que reclasifica apuntes al cambiar de
periodo/cuenta, y que este addon parchea para que el nuevo apunte conserve
el ``vehicle_id`` de origen cuando reclasifica la misma cuenta.

**Medido:** ``grep -rln "AccountAutomaticEntryWizard\|automatic.entry.wizard\|automatic_entry_wizard" api: src/addons/account/`` → **0 archivos**. El
wizard base **no existe** en el puerto de ``account`` — no hay clase a la
que colgarse, ni con ``add_to_class`` ni con ``setattr``: ``_inherit`` de
Odoo reabre una clase que ya existe; aquí no hay ninguna.

Esto es la Clausula 4 de ``principio-rector-rup-arquitectura.md``
("bloqueado por algo medido — falta una pieza concreta, nombrada, con
sucesor registrado"), no la Clausula 5 (el anti-patrón "PARCIAL
JUSTIFICADO" que la Clausula 5 prohíbe exige justamente lo que este
docstring NO hace: declarar el símbolo "parcial por naturaleza" sin medir).
Aquí la ausencia está medida (0 archivos, comando citado arriba) y la causa
es nombrada (``account.automatic.entry.wizard`` no tiene puerto).

Condición de cierre — sucesor
================================

Cuando ``account.automatic.entry.wizard`` (o su equivalente funcional: un
servicio que reclasifica un lote de apuntes de una cuenta a otra en un
periodo) exista en el puerto de ``account``, este archivo es el lugar
natural para colgar la propagación de ``vehicle`` — el propio nombre del
archivo lo reserva. Hasta entonces, un cambio de periodo/cuenta sobre un
apunte con ``vehicle`` seteado **pierde** esa referencia en el apunte nuevo:
es el hueco que este DEFERIDO dice explícitamente que existe.

Este agente tiene prohibido escribir fuera de ``account_fleet/`` y sus
tests — portar el wizard base en ``account/models/`` (y su capa DRF, si la
referencia lo expone por wizard de UI, que en Odoo son transitorios sin
persistencia de por sí) queda para el orquestador.
"""
