"""Extensión de ``res.partner`` — el contacto que es empleado (Odoo ``hr``).

Adaptación de Odoo hr/models/res_partner.py (odoo-tools@622ddc2a, odoo19c:,
LGPL-3, 111 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Porte símbolo por símbolo — 10 símbolos: 6 portados, 1 ya existente, 3 BLOQUEADOS
==================================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
     - Forma aquí
   * - ``employee_ids`` (One2many, ``:11-13``)
     - portado sin código
     - reverso automático de ``hr.HrEmployee.work_contact``
       (``related_name='employee_work_contacts'``) — mismo criterio que
       ``resource_calendar_ids`` en ``resource/models/res_company.py``
   * - ``employees_count`` (compute, ``:14``)
     - portado
     - propiedad ``employees_count``
   * - ``employee`` (Boolean compute+store, ``:15``)
     - ya existente
     - ``base.ResPartner.employee`` ya es columna
       (``src/addons/base/models/res_partner.py:176``);
       ``add_field_if_absent`` sería no-op — se porta sólo el recómputo
   * - ``_compute_employees_count`` (``:17-19``)
     - portado
     - el cuerpo de la propiedad ``employees_count``
   * - ``action_open_employees`` (``:21-38``)
     - BLOQUEADO
     - framework de acciones cliente de Odoo (``ir.actions.act_window``) sin
       equivalente en este stack DRF+React — familia (b) de
       ``hr_employee.py``
   * - ``_get_all_addr`` (``:40-56``)
     - portado
     - la dirección privada vive en ``hr.version`` (``private_street``…);
       se lee vía ``employee.version``
   * - ``_compute_employee`` (``:58-65``)
     - portado
     - método que recalcula la columna existente
   * - ``_unlink_contact_rel_employee`` (``:67-79``)
     - portado (divergencia)
     - el gancho ``@api.ondelete`` no existe; el método queda disponible
       para el flujo de borrado que lo invoque, y el ``RedirectWarning``
       (acción de navegación) degrada a ``UserError`` con los nombres
   * - ``_action_show`` (``:81-100``)
     - BLOQUEADO
     - misma familia (b): arma un ``ir.actions.act_window``
   * - ``_get_store_avatar_card_fields`` (``:102-108``)
     - BLOQUEADO
     - depende de ``mail.tools.discuss.Store`` (0 hits en este árbol) — la
       infraestructura de discuss no está portada (ver
       ``discuss_channel.py`` de este pase)

La cabecera ``_inherit = 'res.partner'`` que la fuente declara en su clase se
declara aquí a nivel de módulo (la extensión no es clase), y es la que consume
``extend_model`` — un solo sitio donde vive el destino.

Hasta este pase la llamada nombraba el destino con el **par de Django**
(``'base', 'ResPartner'``) y lo justificaba con *"el destino no declara
``_name``"*. Eso dejó de ser cierto: ``src/addons/base/models/res_partner.py:280``
declara ``_name = 'res.partner'`` con espaciado alineado, así que un grep de
``_name = 'res.partner'`` no lo ve. Medido en runtime,
``resolve_model_key('res.partner')`` devuelve ``('base', 'respartner')``.

Divergencias declaradas
========================

1. **``self.env.companies`` → ``orm.environments.get_current_companies()``**
   — el análogo vivo del árbol (mismo criterio que
   ``account/models/res_company.py``). Con lista vacía (sin request activo)
   no se filtra por empresa.
2. **``groups="hr.group_hr_user"``** en ``employee_ids``/``employees_count``
   es ACL por grupo de la referencia — familia (d) de ``hr_employee.py``;
   el enforcement por capacidad es de la capa DRF, no del modelo.
3. **``sudo()``** no existe ni hace falta: no hay record rules que eludir en
   la lectura del modelo.
"""
from exceptions import UserError
from orm.environments import get_current_companies
from orm.model_classes import extend_model
from tools.translate import _


#: ≙ la cabecera que la fuente declara en su clase (la extensión aquí no es clase).
_inherit = 'res.partner'


def _current_company_employees(partner):
    """Los empleados del partner acotados a las empresas activas.

    Helper propio del puerto (la referencia inlinea el filtro
    ``e.company_id in self.env.companies`` dos veces).
    """
    employees = partner.employee_work_contacts.all()
    company_ids = get_current_companies()
    if company_ids:
        employees = employees.filter(company_id__in=company_ids)
    return employees


def _compute_employees_count(self):
    """≙ ``_compute_employees_count`` (``:17-19``)."""
    return _current_company_employees(self).count()


def employees_count(self):
    """≙ ``employees_count`` (``:14``) — la propiedad que expone el cómputo."""
    return self._compute_employees_count()


def _compute_employee(self):
    """Recalcula la marca ``employee`` — ≙ ``_compute_employee`` (``:58-65``).

    La referencia lo dispara con ``@api.depends('employee_ids')``; aquí no
    hay recómputo automático, así que lo invoca quien altere el vínculo
    (``hr.HrEmployee`` al escribir ``work_contact``). No persiste: asigna y
    devuelve, igual que ``_compute_current_version_id`` de
    ``hr_employee.py``.
    """
    self.employee = self.employee_work_contacts.exists()
    return self.employee


def _get_all_addr(self):
    """Las direcciones del contacto, con la privada del empleado primero —
    ≙ ``_get_all_addr`` (``:40-56``).

    DIVERGENCIA: la dirección privada vive en ``hr.version`` (no en
    ``hr.employee``, que la delega); sin versión asignada no hay dirección
    de empleado y se releva. La lista del ``super()`` es el relevo por
    ``None`` de ``chain_method`` — la implementación base de
    ``res.partner`` no existe hoy (medido: 0 hits de ``_get_all_addr`` en
    ``src/addons/base``).
    """
    employee = self.employee_work_contacts.first()
    version = employee.version if employee is not None and employee.version_id else None
    if version is None:
        return None
    pstl_addr = {
        'contact_type': 'employee',
        'street': version.private_street,
        'zip': version.private_zip,
        'city': version.private_city,
        'country': version.private_country.code if version.private_country_id else '',
    }
    return [pstl_addr]


def _unlink_contact_rel_employee(self):
    """Veta borrar un contacto ligado a empleados — ≙
    ``_unlink_contact_rel_employee`` (``:67-79``).

    DIVERGENCIA: el gancho ``@api.ondelete(at_uninstall=False)`` no existe
    en este ORM — el flujo de borrado que se cablee sobre ``res.partner``
    debe invocarlo antes de ``delete()``. El ``RedirectWarning`` (mensaje +
    acción de navegación) degrada a ``UserError``: la acción era UI.
    """
    if self.employee_work_contacts.exists():
        raise UserError(
            _('No puedes eliminar contactos ligados a empleados.\n'
              'Archívalos en su lugar.\n\n'
              'Contacto afectado: %(names)s', names=str(self)),
        )


def apply_hr_res_partner_extensions():
    """Cuelga sobre ``res.partner`` lo que ``hr`` le añade — ≙ ``_inherit``."""
    extend_model(
        _inherit,
        metodos={
            '_compute_employees_count': _compute_employees_count,
            '_compute_employee': _compute_employee,
            '_get_all_addr': _get_all_addr,
            '_unlink_contact_rel_employee': _unlink_contact_rel_employee,
        },
        propiedades={
            'employees_count': employees_count,
        },
    )
