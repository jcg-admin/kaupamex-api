"""``res.partner`` — el contacto ligado a un candidato (Odoo
``hr_recruitment``).

Adaptación fiel de Odoo ``hr_recruitment/models/res_partner.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 7 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03). Porte completo — 1 de 1 símbolo.

.. list-table::
   :header-rows: 1

   * - Símbolo
     - Estado
   * - ``applicant_ids`` (One2many, ``:7``)
     - portado sin código — reverso automático del FK
       ``HrApplicant.partner`` (``related_name='applicant_ids'``, ver
       ``hr_applicant.py`` de este addon)
"""

#: ≙ la cabecera que la fuente declara en su clase (la extensión aquí no es clase).
_inherit = 'res.partner'


__all__ = []
