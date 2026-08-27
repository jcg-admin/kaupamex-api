"""``hr.employee`` — lo que ``hr_recruitment`` le cuelga al empleado (Odoo
``hr_recruitment``).

Adaptación de Odoo ``hr_recruitment/models/hr_employee.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 27 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 2 de 4
=====================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``applicant_ids`` (``:9``)
     - portado sin código — reverso automático del FK
       ``HrApplicant.employee`` (``related_name='applicant_ids'``)
   * - ``_get_partner_count_depends``/``_get_related_partners`` (``:11-16``)
     - BLOQUEADO — ``@api.depends`` y el cómputo de ``partner_count`` que
       extienden no existen en ``hr.HrEmployee`` de este árbol (medido: 0
       hits de ambos símbolos)
   * - ``create`` (``:18-26``)
     - BLOQUEADO — ``_message_log_with_view`` (plantilla QWeb
       ``hr_recruitment.applicant_hired_template``) no tiene análogo: el
       chatter de este árbol (``MailThread.message_post``) no renderiza
       vistas Odoo, sólo texto/HTML directo. Sucesor: cuando el addon
       tenga una plantilla propia, se cablea con
       ``message_post_with_template`` (ya existe en ``MailThread``).

``applicant_ids`` es la ÚNICA pieza con efecto — se declara en
``HrApplicant.employee`` (``related_name='applicant_ids'``, ver
``hr_applicant.py`` de este addon), no aquí.
"""

__all__ = []
