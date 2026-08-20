"""Extensión de ``res.company`` — lo que ``hr`` le cuelga a la empresa.

Adaptación de Odoo hr/models/res_company.py (odoo-tools@622ddc2a, odoo19c:,
LGPL-3, 18 líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

La referencia agrega NUEVE columnas a ``res.company`` vía ``_inherit``; aquí
el análogo es ``extend_model(campos=…)`` → ``add_field_if_absent`` (mismo
mecanismo que ``account/models/res_company.py`` y
``website_sale/models/crm_team.py``).

Porte símbolo por símbolo — 9 de 9 campos
==========================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``hr_presence_control_email_amount`` (``:9``)
     - portado
   * - ``hr_presence_control_ip_list`` (``:10``)
     - portado
   * - ``employee_properties_definition`` (``:11``)
     - portado — ``fields.PropertiesDefinition`` (JSON en este árbol)
   * - ``hr_presence_control_login`` (``:12``)
     - portado
   * - ``hr_presence_control_email`` (``:13``)
     - portado
   * - ``hr_presence_control_ip`` (``:14``)
     - portado
   * - ``hr_presence_control_attendance`` (``:15``)
     - portado
   * - ``contract_expiration_notice_period`` (``:16``)
     - portado — es la pieza que ``hr_employee.py`` declaraba BLOQUEADA
       (sucesor #515): con esta columna, ``notify_expiring_contract_work_permit``
       ya tiene de dónde leer los plazos
   * - ``work_permit_expiration_notice_period`` (``:17``)
     - portado — ídem #515

``_inherit`` lo expresa ``extend_model``; par de Django porque
``base.ResCompany`` no declara ``_name`` (divergencia D-3 de
``stock/models/res_users.py``).

Divergencias declaradas
========================

1. **``fields.PropertiesDefinition``** de este árbol es un ``JSONField``
   (``src/orm/fields_properties.py:12``) — la definición del esquema de
   propiedades por empresa se guarda como JSON, no como el tipo propietario
   de la referencia. El cableado consumidor
   (``hr.employee.employee_properties`` leyendo esta definición) sigue
   BLOQUEADO en ``hr_employee.py`` — sucesor: tarea **#515**.
2. **La migración aditiva no se genera aquí** — mismo criterio que el resto
   de las extensiones por ``campos=``: el ``AddField`` de un campo colgado
   sobre un modelo ajeno se produce en el pase de wiring (ver
   ``website/models/ir_ui_view.py``, que documenta el mecanismo), no dentro
   del archivo de extensión.
"""
import fields

from orm.model_classes import extend_model


def apply_hr_res_company_extensions():
    """Cuelga sobre ``res.company`` lo que ``hr`` le añade — ≙ ``_inherit``."""
    extend_model('base', 'ResCompany', campos={
        'hr_presence_control_email_amount': fields.Integer(
            default=0,
            help_text='Odoo hr_presence_control_email_amount ("# emails to '
                      'send") — umbral de correos enviados para considerar '
                      'presente al empleado.',
        ),
        'hr_presence_control_ip_list': fields.Char(
            blank=True, default='',
            help_text='Odoo hr_presence_control_ip_list ("Valid IP '
                      'addresses") — lista de IPs válidas para el control de '
                      'presencia.',
        ),
        'employee_properties_definition': fields.PropertiesDefinition(
            null=True, blank=True,
            help_text='Odoo employee_properties_definition ("Employee '
                      'Properties") — esquema de propiedades dinámicas de '
                      'los empleados de la empresa.',
        ),
        'hr_presence_control_login': fields.Boolean(
            default=True,
            help_text='Odoo hr_presence_control_login ("Based on user status '
                      'in system").',
        ),
        'hr_presence_control_email': fields.Boolean(
            default=False,
            help_text='Odoo hr_presence_control_email ("Based on number of '
                      'emails sent").',
        ),
        'hr_presence_control_ip': fields.Boolean(
            default=False,
            help_text='Odoo hr_presence_control_ip ("Based on IP Address").',
        ),
        'hr_presence_control_attendance': fields.Boolean(
            default=False,
            help_text='Odoo hr_presence_control_attendance ("Based on '
                      'attendances").',
        ),
        'contract_expiration_notice_period': fields.Integer(
            default=7,
            help_text='Odoo contract_expiration_notice_period ("Contract '
                      'Expiry Notice Period") — días de aviso antes del fin '
                      'de contrato.',
        ),
        'work_permit_expiration_notice_period': fields.Integer(
            default=60,
            help_text='Odoo work_permit_expiration_notice_period ("Work '
                      'Permit Expiry Notice Period") — días de aviso antes '
                      'del vencimiento del permiso de trabajo.',
        ),
    })
