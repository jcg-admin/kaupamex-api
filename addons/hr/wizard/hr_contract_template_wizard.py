"""``hr.version.wizard`` — cargar una plantilla de contrato sobre un
empleado.

Adaptación de Odoo hr/wizard/hr_contract_template_wizard.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, 30 líneas) — atribución y aviso de
licencia preservados (DEC-KX-03).

Nota de forma de la REFERENCIA (no de este puerto): su clase se llama
``HrDepartureWizard`` aunque declara ``_name = 'hr.version.wizard'`` y
``_description = 'Contract Template Wizard'`` — un nombre de clase heredado
por copy-paste del wizard de baja. Se conserva **verbatim** (renombrarla
cegaría al gate de porte, :ref:`h-api-579`); los dos módulos homónimos no
colisionan porque viven en archivos distintos, igual que allá.

``TransientModel`` → clase sin tabla con classmethods (patrón
``account_debit_note``).

Porte símbolo por símbolo — 4 símbolos
=======================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_name`` / ``_description`` (``:7-8``)
     - portados verbatim
   * - ``contract_template_id`` (``:10-13``)
     - resuelto con otra forma — argumento ``contract_template`` de
       ``action_load_template``; su dominio (plantillas = versiones sin
       empleado, de la empresa activa) se porta como
       ``_template_candidates``
   * - ``action_load_template`` (``:15-30``)
     - portado

Divergencias declaradas
========================

1. **``self.env.context['active_id']`` → argumento ``employee``** — la
   selección activa era mecánica del cliente Odoo.
2. **``copy_data()`` + whitelist + filtro de ``related``** — resuelto con la
   pieza ya portada ``hr.version.get_values_from_contract_template``
   (``hr_version.py``), que aplica el MISMO whitelist
   (``_get_whitelist_fields_from_template``); el filtro de campos
   ``related`` no aplica (aquí son columnas reales).
3. **``employee.write(val_list)``** — en la referencia los valores aterrizan
   en la versión vía la delegación ``_inherits``; aquí se escriben
   directamente en ``employee.version``, que es donde viven.
4. **``groups="hr.group_hr_user"``** — ACL por grupo (familia (d) de
   ``hr_employee.py``); el enforcement por capacidad es de la capa DRF.
"""
from addons.hr.models.hr_version import HrVersion
from orm.environments import get_current_company
from orm.models_transient import TransientModel


class HrDepartureWizard(TransientModel):
    """Cargar plantilla de contrato — ≙ ``hr.version.wizard`` (el nombre de
    clase es el de la referencia, ver la nota del docstring del módulo)."""

    class Meta:
        abstract = True
        managed = False

    # ---- Atributos de clase de modelo — verbatim (``:7-8``) ----
    _name = 'hr.version.wizard'
    _description = 'Contract Template Wizard'

    @classmethod
    def _template_candidates(cls):
        """El dominio del campo ``contract_template_id`` (``:12``) como
        queryset: versiones-plantilla (sin empleado) de la empresa activa."""
        queryset = HrVersion.objects.filter(employee__isnull=True)
        company_id = get_current_company()
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        return queryset

    @classmethod
    def action_load_template(cls, employee, contract_template):
        """Aplica la plantilla al contrato del empleado — ≙
        ``action_load_template`` (``:15-30``)."""
        if employee is None or contract_template is None:
            return None
        version = employee.version if employee.version_id else None
        if version is None:
            return None
        values = version.get_values_from_contract_template(contract_template)
        for field_name, value in values.items():
            # ``get_values_from_contract_template`` devuelve la PK para las
            # FKs (lee ``<field>_id`` primero); se asigna por el attname
            # cuando el valor es una PK cruda y por el nombre cuando es una
            # instancia o un escalar (``wage``).
            if hasattr(version, f'{field_name}_id') and not hasattr(value, 'pk'):
                setattr(version, f'{field_name}_id', value)
            else:
                setattr(version, field_name, value)
        version.contract_template = contract_template
        version.save()
        return version
