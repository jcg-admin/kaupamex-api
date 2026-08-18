"""``hr.mixin`` — mixin de acceso a campos many2many hacia ``hr.employee``
(Odoo ``hr``).

Adaptación fiel de Odoo hr/models/hr_mixin.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

.. list-table:: Desenlaces de símbolos no portados verbatim
   :header-rows: 1

   * - Símbolo
     - Desenlace
     - Detalle
   * - ``create`` (override ``@api.model_create_multi``)
     - BLOQUEADO
     - El mecanismo entero existe para eludir el chequeo de acceso de
       lectura de ``hr.employee`` al escribir un many2many hacia ese
       modelo (``with_context(_allow_read_hr_employee=...)`` + el
       centinela ``_ALLOW_READ_HR_EMPLOYEE`` que ``hr_employee.py``
       declara y consume en su chequeo de ACL). ``hr_employee.py`` está
       explícitamente fuera de alcance de este tramo — el centinela no
       tiene de dónde importarse, y sin ``hr.employee`` el propio
       mecanismo no tiene consumidor. Sucesor: el porte de
       ``hr_employee.py`` en el tramo siguiente, que es donde nace tanto
       el centinela como su chequeo de ACL.
   * - ``write``
     - BLOQUEADO
     - Mismo motivo que ``create`` — mismo sucesor.
"""
import models


class HrMixin(models.Model):
    """``hr.mixin`` — mixin abstracto (Odoo ``models.AbstractModel``).

    ``models.AbstractModel`` de la fuente ≙ ``models.Model`` con
    ``Meta.abstract = True`` en este stack — mismo mapeo que
    ``addons.mail.models.mail_thread.MailThread`` ya usa en este árbol.
    """

    # Atributo de clase de modelo — la referencia lo declara con una
    # asignación encadenada (``odoo19c: hr/models/hr_mixin.py:9``), verbatim.
    _name = _description = 'hr.mixin'

    class Meta:
        abstract = True

    # create()/write() — BLOQUEADO, ver tabla del docstring del módulo.
