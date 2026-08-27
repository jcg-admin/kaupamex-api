"""AppConfig — ``addons.sale_timesheet``.

Quince módulos espejan ``odoo19c: sale_timesheet/{models,report,wizard}/*.py``
(el dieciseisavo, ``models/project_sale_line_employee_map.py``, declara un
modelo **propio** y lo importa ``models/__init__.py``, no ``ready()``) — ocho
cuelgan símbolos reales, siete son no-op declarado (mecanismo ausente, pieza
de otro addon, o capa que este proyecto sustituye). La extensión se aplica en
``ready()``, cuando el registro de modelos ya está poblado y
``add_to_class``/``chain_method``/``setattr`` sobre una clase ajena no rompe
con ``AppRegistryNotReady``. Mismo criterio que
``HrTimesheetConfig``/``ProjectAccountConfig``.

``controllers/portal.py`` no aparece en ``_EXTENSIONES``: no cuelga ningún
símbolo sobre ningún modelo — es documentación de por qué el portal QWeb de la
referencia no se porta (ver su docstring).

Orden — ``project_project`` antes que ``project_task`` y que ``hr_timesheet``
==============================================================================

``models/project_task.py`` delega en ``Project.pricing_type`` y
``Project.timesheet_product``, y ``models/hr_timesheet.py::_hourly_cost`` lee
``Project.pricing_type``: los tres símbolos los cuelga
``models/project_project.py``. El orden de ``_EXTENSIONES`` fija esa
precedencia, igual que ``HrTimesheetConfig`` la fija entre ``hr_employee`` y
``hr_employee_public``.

Ese orden es **necesario pero no suficiente** para ``project_task``: las dos
lecturas van dentro de una ``property``, así que se resuelven al invocarla,
no al colgarla. Lo que el orden garantiza de verdad es que
``models/hr_timesheet.py`` encuentre instalado el ``_hourly_cost`` de
``hr_timesheet`` cuando lo encadena — y eso lo garantiza el **grafo de
addons**, no este diccionario: ``sale_timesheet`` declara ``hr_timesheet`` en
su ``depends``, así que su ``ready()`` corre después.
"""
import importlib

from django.apps import AppConfig


class SaleTimesheetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.sale_timesheet'
    label              = 'sale_timesheet'
    verbose_name       = 'Venta de tiempo (sale_timesheet)'

    #: Módulo → función. Cada uno define ``apply_sale_timesheet_*_extensions``.
    #: Mismo patrón que ``HrTimesheetConfig._EXTENSIONES``.
    _EXTENSIONES = {
        'addons.sale_timesheet.models.project_project':
            'apply_sale_timesheet_project_project_extensions',
        'addons.sale_timesheet.models.project_task':
            'apply_sale_timesheet_project_task_extensions',
        'addons.sale_timesheet.models.hr_timesheet':
            'apply_sale_timesheet_hr_timesheet_extensions',
        'addons.sale_timesheet.models.hr_employee':
            'apply_sale_timesheet_hr_employee_extensions',
        'addons.sale_timesheet.models.product_product':
            'apply_sale_timesheet_product_product_extensions',
        'addons.sale_timesheet.models.product_template':
            'apply_sale_timesheet_product_template_extensions',
        'addons.sale_timesheet.models.sale_order':
            'apply_sale_timesheet_sale_order_extensions',
        'addons.sale_timesheet.models.sale_order_line':
            'apply_sale_timesheet_sale_order_line_extensions',
        'addons.sale_timesheet.models.account_move':
            'apply_sale_timesheet_account_move_extensions',
        'addons.sale_timesheet.models.account_move_line':
            'apply_sale_timesheet_account_move_line_extensions',
        'addons.sale_timesheet.models.account_move_reversal':
            'apply_sale_timesheet_account_move_reversal_extensions',
        'addons.sale_timesheet.models.res_config_settings':
            'apply_sale_timesheet_res_config_settings_extensions',
        'addons.sale_timesheet.report.project_report':
            'apply_sale_timesheet_project_report_extensions',
        'addons.sale_timesheet.report.timesheets_analysis_report':
            'apply_sale_timesheet_timesheets_analysis_report_extensions',
        'addons.sale_timesheet.wizard.sale_make_invoice_advance':
            'apply_sale_timesheet_sale_make_invoice_advance_extensions',
    }

    def ready(self):
        """Cuelga el vocabulario de venta de tiempo sobre ``analytic``/
        ``project``/``sale``/``account``/``product``/``hr``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: es una llamada de función, no un statement
        ``import``, así que el gate AST la deja pasar.
        """
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
