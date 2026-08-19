"""``calendar.event`` — la reunión ligada a un candidato (Odoo
``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/calendar.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 61 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte BLOQUEADO — 0 de 5 símbolos: el addon destino no existe
==================================================================

La referencia extiende ``_inherit = 'calendar.event'`` (el addon
``calendar``, que agenda reuniones). Medido en este pase:
``ls addons/ | grep -i calendar`` → **0 hits** — el addon completo está
ausente de este árbol (confirmado también en el `depends` medido del
manifest de este addon).

===========================================================  ==========
Símbolo de la referencia (línea)                              Estado
===========================================================  ==========
``default_get`` (``:10-30``)                                  bloqueado
``applicant_id`` (M2O, ``:32``)                                bloqueado
``create`` (``:34-49``)                                        bloqueado
``_compute_is_highlighted`` (``:51-61``)                       bloqueado
===========================================================  ==========

Los cuatro cuelgan del MISMO ausente: no hay clase ``calendar.event`` a la
que colgar nada. Sucesor: portar el addon ``calendar`` completo (fuera del
write-set de ``hr_recruitment``) es condición previa a completar este
archivo. Hasta entonces ``hr.applicant.meeting_ids`` (``hr_applicant.py``
de este addon) también queda BLOQUEADO, por el mismo ausente.
"""


def apply_hr_recruitment_calendar_extensions():
    """No-op declarado — el addon ``calendar`` no existe (ver docstring)."""
    return None


__all__ = ['apply_hr_recruitment_calendar_extensions']
